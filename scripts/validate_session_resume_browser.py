#!/usr/bin/env python3
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8022').rstrip('/')
RECORD_DIR = ROOT / 'docs' / 'records' / 'session-resume'
REPORT = RECORD_DIR / 'SESSION_RESUME_BROWSER_VALIDATION.json'
SCREENSHOT = RECORD_DIR / 'session_resumed_game.png'


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks = []
    console_errors = []

    def record(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.goto(BASE_URL, wait_until='networkidle')
        page.fill('#playerName', '續戰玩家')
        page.click('#createRoomBtn')
        page.wait_for_function("() => localStorage.getItem('redline.sessions.v1')")
        identity = page.evaluate("""() => {
          const sessions = JSON.parse(localStorage.getItem('redline.sessions.v1'));
          return Object.values(sessions)[0];
        }""")
        record(
            'identity_saved_in_browser',
            bool(identity.get('game_id') and identity.get('player_id') and identity.get('resume_token')),
            {
                'game_id': identity.get('game_id'),
                'player_id': identity.get('player_id'),
                'resume_token': '[REDACTED]',
                'name': identity.get('name'),
            },
        )

        setup = page.evaluate("""async ({gameId, playerId}) => {
          await fetch('/choose-faction', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId, player_id: playerId, faction_id: 'red_army', base_name: '北京'}),
          });
          await fetch('/ready', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId, player_id: playerId, ready: true}),
          });
          return true;
        }""", {'gameId': identity['game_id'], 'playerId': identity['player_id']})
        assert setup

        page.reload(wait_until='networkidle')
        page.wait_for_function("() => document.getElementById('roomId')?.value", timeout=10000)
        restored = page.evaluate("""() => ({
          room: document.getElementById('roomId')?.value,
          name: document.getElementById('playerName')?.value,
          roster: document.getElementById('lobbyRoster')?.innerText,
          status: document.getElementById('lobbyStatusHint')?.innerText,
        })""")
        record('reload_restores_room_and_name', restored['room'] == identity['game_id'] and restored['name'] == '續戰玩家', restored)
        record('reload_restores_same_faction_and_ready_state', '紅軍' in restored['roster'] and '已準備' in restored['roster'], restored)
        sessions_after = page.evaluate("() => JSON.parse(localStorage.getItem('redline.sessions.v1'))")
        same_player_id = sessions_after[identity['game_id']]['player_id'] == identity['player_id']
        record(
            'reload_keeps_same_player_id',
            same_player_id,
            {'game_id': identity['game_id'], 'player_id': sessions_after[identity['game_id']]['player_id']},
        )

        started_setup = page.evaluate("""async ({gameId, hostId, deviceId}) => {
          const guest = await fetch('/join', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId, name: '測試對手', device_id: `${deviceId}-guest`}),
          }).then(response => response.json());
          await fetch('/choose-faction', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId, player_id: guest.player_id, faction_id: 'hong_kong', base_name: '香港城'}),
          });
          await fetch('/ready', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId, player_id: guest.player_id, ready: true}),
          });
          return fetch('/start', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId, player_id: hostId}),
          }).then(response => response.json());
        }""", {
            'gameId': identity['game_id'],
            'hostId': identity['player_id'],
            'deviceId': page.evaluate("() => localStorage.getItem('redline.device_id.v1')"),
        })
        assert started_setup.get('success') is True
        page.reload(wait_until='domcontentloaded')
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.wait_for_function("() => window.lastGameState?.players?.some(player => player.id)", timeout=15000)
        started_state = page.evaluate("""() => ({
          lobbyDisplay: getComputedStyle(document.getElementById('lobby')).display,
          shellDisplay: getComputedStyle(document.getElementById('gameShell')).display,
          me: window.lastGameState.players.find(player => player.id === JSON.parse(localStorage.getItem('redline.sessions.v1'))[Object.keys(JSON.parse(localStorage.getItem('redline.sessions.v1')))[0]].player_id),
        })""")
        record(
            'reload_reconnects_started_game_with_same_faction',
            started_state['lobbyDisplay'] == 'none'
            and started_state['shellDisplay'] != 'none'
            and started_state['me'].get('faction') == 'red_army',
            started_state,
        )
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    record('browser_console_has_no_errors', not console_errors, console_errors)
    payload = {
        'base_url': BASE_URL,
        'status': 'passed' if all(item['ok'] for item in checks) else 'failed',
        'checks_passed': sum(item['ok'] for item in checks),
        'checks_total': len(checks),
        'checks': checks,
        'console_errors': console_errors,
        'screenshot': str(SCREENSHOT.relative_to(ROOT)),
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: payload[key] for key in ('status', 'checks_passed', 'checks_total')}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
