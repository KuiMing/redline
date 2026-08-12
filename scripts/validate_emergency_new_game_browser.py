#!/usr/bin/env python3
import json
import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8022').rstrip('/')


def main():
    checks = []
    errors = []

    def record(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
        page.goto(BASE_URL, wait_until='networkidle')
        page.fill('#playerName', '故障復原測試')
        page.click('#createRoomBtn')
        page.wait_for_function("() => localStorage.getItem('redline.sessions.v1')")
        old_session = page.evaluate("() => Object.values(JSON.parse(localStorage.getItem('redline.sessions.v1')))[0]")

        page.on('dialog', lambda dialog: dialog.accept())
        page.click('#emergencyNewGameBtn')
        page.wait_for_load_state('networkidle')
        lobby = page.evaluate("""() => ({
          lobby: getComputedStyle(document.getElementById('lobby')).display,
          shell: getComputedStyle(document.getElementById('gameShell')).display,
          room: document.getElementById('roomId').value,
          url: location.href,
        })""")
        record('emergency_link_returns_to_clean_lobby', lobby['lobby'] != 'none' and lobby['shell'] == 'none' and lobby['room'] == '', lobby)
        record('old_session_does_not_auto_resume', old_session['game_id'] not in lobby['url'] and 'new_game' not in lobby['url'], lobby)

        page.fill('#playerName', '新遊戲玩家')
        page.click('#createRoomBtn')
        page.wait_for_function("() => document.getElementById('roomId').value")
        new_room = page.input_value('#roomId')
        record('new_room_can_be_created', bool(new_room) and new_room != old_session['game_id'], {'old_room': old_session['game_id'], 'new_room': new_room})
        record('browser_console_has_no_errors', not errors, errors)
        browser.close()

    result = {'status': 'passed' if all(check['ok'] for check in checks) else 'failed', 'checks': checks}
    print(json.dumps({'status': result['status'], 'checks_passed': sum(c['ok'] for c in checks), 'checks_total': len(checks)}, ensure_ascii=False))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
