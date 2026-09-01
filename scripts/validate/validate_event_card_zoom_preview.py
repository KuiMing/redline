#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
RECORD_DIR = BASE / 'docs' / 'records' / 'event-cards'
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
JSON_PATH = RECORD_DIR / 'EVENT_CARD_ZOOM_PREVIEW_VALIDATION.json'
MD_PATH = RECORD_DIR / 'EVENT_CARD_ZOOM_PREVIEW_VALIDATION.md'
OPEN_SHOT = RECORD_DIR / 'EVENT_CARD_ZOOM_PREVIEW_OPEN_2026_08_20.png'
PINNED_SHOT = RECORD_DIR / 'EVENT_CARD_TAB_MAP_1280_2026_08_23.png'
PINNED_NARROW_SHOT = RECORD_DIR / 'EVENT_CARD_TAB_MAP_1024_2026_08_23.png'
IDLE_UNOBSTRUCTED_SHOT = RECORD_DIR / 'EVENT_CARD_IDLE_TAB_2026_08_23.png'


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

    def record(name: str, passed: bool, details) -> None:
        checks.append({'name': name, 'passed': bool(passed), 'details': details})

    html = (BASE / 'static/index.html').read_text(encoding='utf-8')
    css = (BASE / 'static/style.css').read_text(encoding='utf-8')
    record(
        'event_card_uses_tab_not_floating_panel',
        'id="eventCardTab"' in html and 'id="eventCardPanel"' not in html and '.event-card-panel' not in css,
        'event tab exists; floating event panel removed',
    )

    setup = post_json('/test/setup-event-card-proof', {
        'event_name': '紅軍權貴出逃',
        'current_event_active': True,
        'viewer_faction': 'taiwan',
    })
    url = f"{BASE_URL}{setup['url']}&v=event-card-tab-preview"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        console_errors: list[str] = []
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_function('window.lastGameState?.current_event', timeout=15000)
        page.locator('#eventRevealModal').wait_for(state='visible', timeout=8000)
        page.wait_for_timeout(400)

        expanded = page.evaluate("""() => {
          const overlay = document.getElementById('eventRevealModal');
          const card = document.getElementById('eventRevealCard');
          const image = card.querySelector('.event-card-art-image');
          const status = card.querySelector('.event-art-runtime-status');
          const cardRect = card.getBoundingClientRect();
          const statusRect = status?.getBoundingClientRect();
          return {
            display: getComputedStyle(overlay).display,
            animation: getComputedStyle(card).animationName,
            label: overlay.getAttribute('aria-label'),
            text: card.innerText,
            imageAlt: image?.alt || '',
            imageSize: image ? [image.naturalWidth, image.naturalHeight] : null,
            centered: Math.abs(cardRect.left + cardRect.width / 2 - innerWidth / 2) < 2 && Math.abs(cardRect.top + cardRect.height / 2 - innerHeight / 2) < 2,
            statusInside: Boolean(statusRect && statusRect.top >= cardRect.top && statusRect.bottom <= cardRect.bottom),
          };
        }""")
        record('turn_start_auto_opens_centered_zoom_preview', expanded['display'] == 'flex' and expanded['animation'] == 'event-card-zoom-in' and expanded['centered'], expanded)
        record('expanded_preview_keeps_complete_art_and_progress', expanded['imageSize'] == [1350, 1100] and expanded['imageAlt'] == '紅軍權貴出逃完整卡面' and '達成次數' in expanded['text'] and expanded['statusInside'], expanded)
        page.screenshot(path=str(OPEN_SHOT), full_page=True)

        page.locator('#eventRevealCard').click(position={'x': 20, 'y': 20})
        page.wait_for_function("getComputedStyle(document.getElementById('eventRevealModal')).display === 'none'")
        page.evaluate('render(window.lastGameState)')
        page.wait_for_timeout(180)
        record('dismissed_preview_does_not_reopen_same_turn', page.locator('#eventRevealModal').evaluate("el => getComputedStyle(el).display") == 'none', 'same turn remained closed')

        page.locator('#gameTabs [data-view="map"]').click()
        page.wait_for_timeout(250)
        tab_state = page.evaluate("""() => {
          const tab = document.getElementById('eventCardTab');
          const tabs = document.getElementById('gameTabs').getBoundingClientRect();
          const box = tab.getBoundingClientRect();
          return {
            text: tab.innerText,
            title: tab.title,
            display: getComputedStyle(tab).display,
            insideTabs: box.left >= tabs.left && box.right <= tabs.right && box.top >= tabs.top && box.bottom <= tabs.bottom,
            mapActive: document.querySelector('.game-tab[data-view="map"]')?.classList.contains('active'),
            visibleView: document.querySelector('.game-view.active')?.id,
          };
        }""")
        record('event_tab_remains_visible_without_changing_active_view', tab_state['display'] != 'none' and tab_state['insideTabs'] and tab_state['mapActive'] and tab_state['visibleView'] == 'mapView' and '紅軍權貴出逃' in tab_state['text'], tab_state)
        page.screenshot(path=str(PINNED_SHOT), full_page=True)

        page.locator('#eventCardTab').click()
        page.locator('#eventRevealModal').wait_for(state='visible', timeout=5000)
        reopened = page.evaluate("""() => ({
          label: document.getElementById('eventRevealModal').getAttribute('aria-label'),
          imageAlt: document.querySelector('#eventRevealCard .event-card-art-image')?.alt || '',
          mapStillActive: document.querySelector('.game-tab[data-view="map"]')?.classList.contains('active'),
          visibleView: document.querySelector('.game-view.active')?.id,
        })""")
        record('event_tab_reopens_preview_without_hiding_map', '紅軍權貴出逃' in reopened['label'] and reopened['imageAlt'] == '紅軍權貴出逃完整卡面' and reopened['mapStillActive'] and reopened['visibleView'] == 'mapView', reopened)
        page.keyboard.press('Escape')

        page.set_viewport_size({'width': 1024, 'height': 768})
        page.wait_for_timeout(300)
        narrow = page.evaluate("""() => {
          const tab = document.getElementById('eventCardTab').getBoundingClientRect();
          const tabs = document.getElementById('gameTabs').getBoundingClientRect();
          return {tab: {left: tab.left, top: tab.top, right: tab.right, bottom: tab.bottom}, tabs: {left: tabs.left, top: tabs.top, right: tabs.right, bottom: tabs.bottom}, viewport: {width: innerWidth, height: innerHeight}};
        }""")
        record('event_tab_stays_inside_narrow_viewport', narrow['tab']['left'] >= 0 and narrow['tab']['right'] <= 1024 and narrow['tab']['top'] >= 0 and narrow['tab']['bottom'] <= 768 and narrow['tab']['left'] >= narrow['tabs']['left'] and narrow['tab']['right'] <= narrow['tabs']['right'], narrow)
        page.screenshot(path=str(PINNED_NARROW_SHOT), full_page=True)

        idle_setup = post_json('/test/setup-event-card-proof', {
            'event_name': '歲月靜好',
            'current_event_active': True,
            'event_status': 'idle',
            'viewer_faction': 'taiwan',
        })
        page.goto(f"{BASE_URL}{idle_setup['url']}&v=event-card-idle-tab", wait_until='domcontentloaded')
        page.wait_for_function('window.lastGameState?.current_event', timeout=15000)
        page.locator('#eventRevealModal').wait_for(state='visible', timeout=8000)
        page.keyboard.press('Escape')
        idle_tab = page.evaluate("""() => ({text: document.getElementById('eventCardTab').innerText, title: document.getElementById('eventCardTab').title, panelExists: Boolean(document.getElementById('eventCardPanel'))})""")
        record('idle_event_uses_tab_with_no_effect_status', not idle_tab['panelExists'] and '歲月靜好' in idle_tab['text'] and '無效果' in idle_tab['title'], idle_tab)
        page.screenshot(path=str(IDLE_UNOBSTRUCTED_SHOT), full_page=True)
        record('browser_console_has_no_errors', not console_errors, console_errors)
        browser.close()

    summary = {
        'total': len(checks),
        'passed': sum(1 for item in checks if item['passed']),
        'failed': sum(1 for item in checks if not item['passed']),
    }
    report = {
        'summary': summary,
        'checks': checks,
        'screenshots': [
            str(OPEN_SHOT.relative_to(BASE)),
            str(PINNED_SHOT.relative_to(BASE)),
            str(PINNED_NARROW_SHOT.relative_to(BASE)),
            str(IDLE_UNOBSTRUCTED_SHOT.relative_to(BASE)),
        ],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MD_PATH.write_text('\n'.join([
        '# Event Card Tab and Zoom Preview Validation', '',
        f"Summary: {summary['passed']}/{summary['total']} passed", '',
        *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}`" for item in checks], '',
        *[f'- `{path}`' for path in report['screenshots']], '',
    ]), encoding='utf-8')
    print(json.dumps({'status': 'passed' if not summary['failed'] else 'failed', **summary}, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
