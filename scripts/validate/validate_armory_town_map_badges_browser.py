#!/usr/bin/env python3
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
SCREENSHOT = Path('/Users/benmini/.hermes/cache/images/armory_town_map_badges.png')


def main():
    map_data = json.loads((ROOT / 'data' / 'map.json').read_text(encoding='utf-8'))
    expected = sorted(name for name, town in map_data['towns'].items() if town.get('type') == '軍火庫')
    checks = []
    console_errors = []

    def record(name, passed, detail=None):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})

    def diagnostics(page):
        return page.evaluate('window.__armoryBadgeDiagnosticsForTest()')

    def aligned(entries, baseline=None):
        if not entries:
            return False
        for item in entries:
            if abs(item['townLat'] - item['badgeLat']) > 1e-9 or abs(item['townLon'] - item['badgeLon']) > 1e-9:
                return False
            if item['screenOffsetX'] is None or item['screenOffsetY'] is None:
                return False
            if baseline:
                original = baseline[item['town']]
                if abs(item['screenOffsetX'] - original['screenOffsetX']) > 0.75:
                    return False
                if abs(item['screenOffsetY'] - original['screenOffsetY']) > 0.75:
                    return False
        return True

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
        page.goto(f'{BASE_URL}/static/leaflet_game_map.html?v=armory-proof', wait_until='domcontentloaded')
        page.wait_for_function(f"document.querySelectorAll('.armory-badge').length === {len(expected)}", timeout=15000)
        page.wait_for_timeout(250)

        badge_towns = sorted(page.locator('.armory-badge').evaluate_all("els => els.map(el => el.dataset.armoryTown)"))
        badge_texts = page.locator('.armory-badge').all_inner_texts()
        record('all_armory_towns_have_permanent_badges', badge_towns == expected, {'expected': expected, 'actual': badge_towns})
        record('all_permanent_badges_show_explosive_icon', len(badge_texts) == len(expected) and all(text == '🧨' for text in badge_texts), badge_texts)

        initial = diagnostics(page)
        baseline = {item['town']: item for item in initial}
        record('initial_badges_are_bound_to_correct_town_coordinates', aligned(initial), initial)

        for _ in range(3):
            page.locator('.leaflet-control-zoom-in').click()
            page.wait_for_timeout(450)
        zoomed_in = diagnostics(page)
        record('badges_remain_aligned_after_three_zoom_ins', aligned(zoomed_in, baseline), zoomed_in)

        for _ in range(2):
            page.locator('.leaflet-control-zoom-out').click()
            page.wait_for_timeout(450)
        zoomed_out = diagnostics(page)
        record('badges_remain_aligned_after_two_zoom_outs', aligned(zoomed_out, baseline), zoomed_out)

        target = expected[0]
        payload = {
            'mode': 'support-targets',
            'actionKind': 'dissolve',
            'choiceKey': 'armory_browser_proof',
            'sourceName': '軍火庫圖示驗證',
            'prompt': '選擇一個可瓦解目標',
            'towns': [{'town': target, 'label': target}],
            'focusTown': target,
        }
        page.evaluate("payload => window.postMessage({type: 'redline-choice-highlight', payload}, location.origin)", payload)
        page.wait_for_function("document.querySelectorAll('.dissolve-target-badge').length === 1", timeout=5000)
        coexistence = page.evaluate('town => window.__armoryDissolveCoexistenceForTest(town)', target)
        record('armory_and_dissolve_icons_are_visible_together', coexistence == {
            'armoryVisible': True,
            'skullVisible': True,
            'armoryText': '🧨',
            'skullText': '💀',
        }, {'town': target, **coexistence})

        SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        record('browser_console_has_no_errors', not console_errors, console_errors)
        browser.close()

    result = {
        'status': 'passed' if all(check['passed'] for check in checks) else 'failed',
        'checks_passed': sum(check['passed'] for check in checks),
        'checks_total': len(checks),
        'armory_town_count': len(expected),
        'screenshot': str(SCREENSHOT),
        'checks': checks,
    }
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
