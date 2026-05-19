import json
import os
import sys
import time
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'lobby'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'LOBBY_READY_SYNC_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LOBBY_READY_SYNC_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'lobby_ready_sync_validation.png'


def request_json(path, payload=None):
    if payload is None:
        return json.loads(urllib.request.urlopen(BASE_URL + path, timeout=20).read().decode('utf-8'))
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def check_page(page):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.click('#createRoomBtn')
    page.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
    game_id = page.locator('#roomId').input_value()

    # Host sees setup controls, but should not be able to start until the room is fully ready.
    start_initial = page.evaluate("""() => {
      const btn = document.querySelector('#startGameBtn');
      return {
        exists: !!btn,
        disabled: !!btn?.disabled,
        text: btn?.textContent || '',
        title: btn?.title || '',
      };
    }""")
    record('host_start_button_locked_until_ready', start_initial['exists'] and start_initial['disabled'], start_initial)

    ready_initial = page.evaluate("""() => {
      const btn = document.querySelector('#toggleReadyBtn');
      return {
        exists: !!btn,
        text: btn?.textContent || '',
        disabled: !!btn?.disabled,
      };
    }""")
    record('ready_toggle_visible_in_lobby', ready_initial['exists'] and '準備' in ready_initial['text'], ready_initial)

    # Simulate a second player entering through the API. The host page should refresh on its own.
    joined = request_json('/join', {'game_id': game_id, 'name': 'ally'})
    second_player_id = joined.get('player_id')
    try:
        page.wait_for_function("() => document.querySelector('#lobbyRoster')?.innerText.includes('ally')", timeout=7000)
    except Exception:
        pass
    roster_after_poll = page.locator('#lobbyRoster').inner_text()
    record('lobby_roster_auto_syncs_joined_players', 'ally' in roster_after_poll, {
        'roster_text': roster_after_poll,
        'second_player_id': second_player_id,
    })

    # The backend should expose and enforce ready state before game start.
    lobby_state = request_json(f'/lobby/{game_id}')
    has_ready_state = isinstance(lobby_state.get('ready'), dict)
    record('lobby_state_exposes_ready_map', has_ready_state, {'lobby_state_keys': sorted(lobby_state.keys())})

    not_ready_start = request_json('/start', {'game_id': game_id, 'player_id': lobby_state.get('host_id'), 'market_mode': 'sample_53'})
    record('backend_rejects_start_before_all_ready', bool(not_ready_start.get('error')) and 'ready' in not_ready_start.get('error', '').lower(), not_ready_start)

    request_json('/choose-faction', {'game_id': game_id, 'player_id': lobby_state.get('host_id'), 'faction_id': 'red_army'})
    request_json('/choose-faction', {'game_id': game_id, 'player_id': second_player_id, 'faction_id': 'taiwan_green'})
    request_json('/ready', {'game_id': game_id, 'player_id': lobby_state.get('host_id'), 'ready': True})
    request_json('/ready', {'game_id': game_id, 'player_id': second_player_id, 'ready': True})
    page.wait_for_function("""() => {
      const text = document.querySelector('#lobbyRoster')?.innerText || '';
      return text.includes('host') && text.includes('ally') && (text.match(/已準備/g) || []).length >= 2;
    }""", timeout=7000)
    ready_text = page.locator('#lobbyRoster').inner_text()
    start_ready = page.evaluate("""() => {
      const btn = document.querySelector('#startGameBtn');
      return {disabled: !!btn?.disabled, title: btn?.title || '', text: btn?.textContent || ''};
    }""")
    record('host_start_button_unlocks_when_all_players_ready', not start_ready['disabled'] and '已準備' in ready_text, {
        'start_button': start_ready,
        'roster_text': ready_text,
    })

    page.screenshot(path=str(SCREENSHOT), full_page=True)
    return {
        'game_id': game_id,
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshot': str(SCREENSHOT),
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = ctx.new_page()
        payload = check_page(page)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# LOBBY READY SYNC VALIDATION', '', '日期：2026-05-09', '', f"summary: {payload['summary']}", '', f"screenshot: {payload['screenshot']}", '']
    for r in payload['results']:
        lines.append(f"## {r['name']}")
        lines.append(f"- result: {'PASS' if r['ok'] else 'FAIL'}")
        lines.append(f"- detail: {json.dumps(r['detail'], ensure_ascii=False)}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
