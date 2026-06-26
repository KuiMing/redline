#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8767')
RECORD_DIR = BASE / 'docs' / 'records' / 'event-cards'


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode('utf-8'))


def assert_check(checks, name, passed, details):
    checks.append({'name': name, 'passed': bool(passed), 'details': details})


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_dir = RECORD_DIR / f'event-effect-text-browser-{stamp}'
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    checks = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})

        auto_setup = post_json('/test/setup-belt-road-red-turn-proof', {'event_name': '一帶一路 南洋'})
        auto_url = f"{BASE_URL}{auto_setup['url']}&v=event-effect-text-{stamp}"
        page.goto(auto_url, wait_until='domcontentloaded')
        page.wait_for_function('window.lastGameState && window.lastGameState.current_event', timeout=15000)
        page.wait_for_timeout(350)
        auto_text = page.locator('#eventCardContent').inner_text(timeout=5000)
        auto_state = page.evaluate('window.lastGameState.current_event')
        auto_shot = screenshot_dir / '01_auto_event_red_army_effect_text.png'
        page.screenshot(path=str(auto_shot), full_page=True)
        assert_check(
            checks,
            'auto_event_shows_red_army_effect_text',
            '自動效果：紅軍：在南洋免費建立 1 個組織' in auto_text,
            {'text': auto_text, 'event': auto_state, 'screenshot': str(auto_shot.relative_to(BASE))},
        )

        mission_setup = post_json('/test/setup-national-people-congress-red-dissolve-proof', {})
        mission_url = f"{BASE_URL}{mission_setup['url']}&v=event-effect-text-{stamp}"
        page.goto(mission_url, wait_until='domcontentloaded')
        page.wait_for_function('window.lastGameState && window.lastGameState.current_event', timeout=15000)
        page.wait_for_timeout(350)
        mission_text = page.locator('#eventCardContent').inner_text(timeout=5000)
        mission_state = page.evaluate('window.lastGameState.current_event')
        mission_shot = screenshot_dir / '02_mission_failure_red_army_effect_text.png'
        page.screenshot(path=str(mission_shot), full_page=True)
        assert_check(
            checks,
            'mission_failure_labels_red_army_effect_text',
            '失敗／紅軍效果：紅軍：瓦解 1 個組織（牆內）' in mission_text,
            {'text': mission_text, 'event': mission_state, 'screenshot': str(mission_shot.relative_to(BASE))},
        )
        browser.close()

    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    report = {'summary': summary, 'checks': checks}
    json_path = RECORD_DIR / f'EVENT_EFFECT_TEXT_BROWSER_{stamp}.json'
    md_path = RECORD_DIR / f'EVENT_EFFECT_TEXT_BROWSER_{stamp}.md'
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    md_lines = ['# Event Effect Text Browser Validation', '', f'Generated: {stamp}', '', f"Summary: {summary['passed']}/{summary['total']} passed", '']
    for item in checks:
        status = 'PASS' if item['passed'] else 'FAIL'
        md_lines += [f"## {status} — {item['name']}", '', '```json', json.dumps(item['details'], ensure_ascii=False, indent=2), '```', '']
    md_path.write_text('\n'.join(md_lines), encoding='utf-8')
    print(json.dumps({'summary': summary, 'reports': [str(json_path), str(md_path)], 'screenshots': [str(p) for p in sorted(screenshot_dir.glob('*.png'))]}, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
