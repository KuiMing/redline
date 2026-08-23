#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
RECORD_DIR = ROOT / 'docs' / 'records' / 'ui-layout' / 'command-header-tabs'
REPORT_JSON = RECORD_DIR / 'COMMAND_HEADER_TABS_VALIDATION.json'
REPORT_MD = RECORD_DIR / 'COMMAND_HEADER_TABS_VALIDATION.md'
SHOT_1280 = RECORD_DIR / 'command-header-tabs-1280x720.png'
SHOT_1024 = RECORD_DIR / 'command-header-tabs-1024x768.png'
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def record(name: str, ok: bool, detail) -> None:
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    setup = post_json('/test/setup-event-card-proof', {
        'event_name': '紅軍權貴出逃',
        'current_event_active': True,
        'viewer_faction': 'taiwan',
    })
    url = f"{BASE_URL}{setup['url']}&v=command-header-tabs"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        console_errors: list[str] = []
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_function('window.lastGameState?.current_event', timeout=15000)
        page.wait_for_timeout(700)
        page.evaluate("() => typeof closeEventReveal === 'function' && closeEventReveal()")

        state = page.evaluate("""() => {
          const rect = id => {
            const element = document.getElementById(id);
            if (!element) return null;
            const box = element.getBoundingClientRect();
            return {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height, display: getComputedStyle(element).display};
          };
          const top = rect('topBar');
          const tabs = rect('gameTabs');
          const meta = rect('phaseActionMeta');
          const fresh = rect('emergencyNewGameBtn');
          const advance = rect('advanceStepBtn');
          const eventTab = rect('eventCardTab');
          const inside = (child, parent, pad = 0) => Boolean(child && parent && child.left >= parent.left + pad && child.right <= parent.right - pad && child.top >= parent.top && child.bottom <= parent.bottom);
          return {
            titleExists: Boolean(document.querySelector('#topBar .title')),
            hudText: document.getElementById('hud')?.innerText || '',
            eventPanelExists: Boolean(document.getElementById('eventCardPanel')),
            eventTabText: document.getElementById('eventCardTab')?.innerText || '',
            advanceText: document.getElementById('advanceStepBtn')?.innerText || '',
            top, tabs, meta, fresh, advance, eventTab,
            metaInsideTop: inside(meta, top),
            freshInsideTop: inside(fresh, top, 12),
            advanceInsideTabs: inside(advance, tabs, 12),
            eventTabInsideTabs: inside(eventTab, tabs),
            freshRightGap: fresh && top ? top.right - fresh.right : null,
            advanceRightGap: advance && tabs ? tabs.right - advance.right : null,
          };
        }""")
        record('yellow_header_title_removed', not state['titleExists'], state['titleExists'])
        record('yellow_hand_chip_removed', '手牌 ' not in state['hudText'], state['hudText'])
        record('yellow_market_mode_chip_removed', '牌庫模式' not in state['hudText'], state['hudText'])
        record('phase_description_moved_inside_top_bar', state['metaInsideTop'], {'meta': state['meta'], 'top': state['top']})
        record('new_game_moved_to_top_right', state['freshInsideTop'] and state['freshRightGap'] is not None and state['freshRightGap'] <= 24, {'button': state['fresh'], 'top': state['top'], 'rightGap': state['freshRightGap']})
        record('advance_button_uses_old_new_game_tab_position', state['advanceInsideTabs'] and state['advanceRightGap'] is not None and state['advanceRightGap'] <= 24, {'button': state['advance'], 'tabs': state['tabs'], 'rightGap': state['advanceRightGap']})
        record('event_card_is_a_visible_tab', not state['eventPanelExists'] and state['eventTabInsideTabs'] and '事件卡' in state['eventTabText'] and '紅軍權貴出逃' in state['eventTabText'], state)
        page.screenshot(path=str(SHOT_1280), full_page=True)

        event_tab = page.locator('#eventCardTab')
        if event_tab.count():
            event_tab.click()
            page.locator('#eventRevealModal').wait_for(state='visible', timeout=5000)
            reveal_label = page.locator('#eventRevealModal').get_attribute('aria-label') or ''
            record('event_tab_opens_complete_event_card', '紅軍權貴出逃' in reveal_label, reveal_label)
            page.evaluate('closeEventReveal()')
        else:
            record('event_tab_opens_complete_event_card', False, 'missing #eventCardTab')

        page.set_viewport_size({'width': 1024, 'height': 768})
        page.wait_for_timeout(300)
        narrow = page.evaluate("""() => {
          const ids = ['topBar', 'phaseActionMeta', 'emergencyNewGameBtn', 'gameTabs', 'eventCardTab', 'advanceStepBtn'];
          return Object.fromEntries(ids.map(id => {
            const element = document.getElementById(id);
            if (!element) return [id, null];
            const box = element.getBoundingClientRect();
            return [id, {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height}];
          }));
        }""")
        record('narrow_layout_keeps_header_controls_inside_viewport', all(box and box['left'] >= 0 and box['right'] <= 1024 and box['top'] >= 0 and box['bottom'] <= 768 for box in narrow.values()), narrow)
        page.screenshot(path=str(SHOT_1024), full_page=True)
        browser.close()

    record('browser_console_has_no_errors', not console_errors, console_errors)
    passed = sum(1 for item in checks if item['ok'])
    payload = {'status': 'passed' if passed == len(checks) else 'failed', 'checks_passed': passed, 'checks_total': len(checks), 'checks': checks, 'screenshots': [str(SHOT_1280.relative_to(ROOT)), str(SHOT_1024.relative_to(ROOT))]}
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    REPORT_MD.write_text('\n'.join([
        '# 指揮中心頂列與事件分頁 UI Validation', '',
        f'- 結果：**{passed}/{len(checks)} passed**', '',
        *[f"- {'PASS' if item['ok'] else 'FAIL'} `{item['name']}`" for item in checks], '',
        f'- `{SHOT_1280.relative_to(ROOT)}`',
        f'- `{SHOT_1024.relative_to(ROOT)}`', '',
    ]), encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': passed, 'checks_total': len(checks)}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
