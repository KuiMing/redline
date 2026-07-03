#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8770')
RECORD_DIR = BASE / 'docs' / 'records' / 'event-cards'


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode('utf-8'))


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_dir = RECORD_DIR / f'elite-defection-failure-{stamp}'
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    setup = post_json('/test/setup-event-card-proof', {
        'event_name': '紅軍權貴出逃',
        'current_event_active': True,
    })
    if setup.get('error'):
        raise AssertionError(setup)
    game_id = setup['game_id']
    player_id = setup['player_id']

    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.goto(f'{BASE_URL}/?game_id={game_id}&player_id={player_id}&v=elite-defection-failure-{stamp}', wait_until='domcontentloaded')
        page.wait_for_function('window.lastGameState && window.lastGameState.current_event && document.querySelector("#advanceStepBtn")', timeout=15000)
        if page.locator('#factionActionModal').is_visible(timeout=1000):
            page.locator('#closeFactionActionModal').click(timeout=5000)
            page.wait_for_function('document.querySelector("#factionActionModal").style.display === "none"', timeout=5000)
        page.wait_for_timeout(350)
        initial = page.evaluate('window.lastGameState')
        panel_text = page.locator('#eventCardPanel').inner_text(timeout=5000)
        action_text = page.locator('#advanceStepBtn').inner_text(timeout=5000)
        shot1 = screenshot_dir / '01_initial_elite_defection_event_visible.png'
        page.screenshot(path=str(shot1), full_page=True)
        checks.append({
            'name': 'elite_defection_event_visible_at_action_start',
            'passed': initial.get('turn_phase') == 'action' and (initial.get('current_event') or {}).get('name') == '紅軍權貴出逃' and '紅軍權貴出逃' in panel_text and action_text == '開始購買階段',
            'details': {'turn_phase': initial.get('turn_phase'), 'event': initial.get('current_event'), 'panel_text': panel_text, 'advance_text': action_text},
        })

        page.evaluate("sendAction('advance')")
        page.wait_for_function('window.lastGameState && window.lastGameState.turn_phase === "end"', timeout=10000)
        page.wait_for_timeout(250)
        page.evaluate("sendAction('advance')")
        page.wait_for_function('window.lastGameState && window.lastGameState.pending_choice && window.lastGameState.pending_choice.choice_key === "event_discard_self"', timeout=10000)
        page.wait_for_timeout(350)
        pending = page.evaluate('window.lastGameState')
        shot2 = screenshot_dir / '02_failure_discard_choice_before_red_turn.png'
        page.screenshot(path=str(shot2), full_page=True)
        choice = pending.get('pending_choice') or {}
        checks.append({
            'name': 'failure_discard_choice_triggers_before_red_turn',
            'passed': pending.get('current_player') == 'viewer' and choice.get('player_id') == player_id and choice.get('choice_key') == 'event_discard_self' and (pending.get('current_event') or {}).get('status') == 'failure',
            'details': {'current_player': pending.get('current_player'), 'turn_phase': pending.get('turn_phase'), 'current_event': pending.get('current_event'), 'pending_choice': choice},
        })
        browser.close()

    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    report = {'summary': summary, 'checks': checks, 'screenshots': [str(p.relative_to(BASE)) for p in sorted(screenshot_dir.glob('*.png'))]}
    json_path = RECORD_DIR / f'ELITE_DEFECTION_FAILURE_BROWSER_{stamp}.json'
    md_path = RECORD_DIR / f'ELITE_DEFECTION_FAILURE_BROWSER_{stamp}.md'
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text('# Elite defection failure browser validation\n\n```json\n' + json.dumps(report, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    print(json.dumps({'summary': summary, 'reports': [str(json_path), str(md_path)], 'screenshots': [str(BASE / p) for p in report['screenshots']]}, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
