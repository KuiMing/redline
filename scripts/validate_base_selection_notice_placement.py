#!/usr/bin/env python3
"""Validate that the base-selection waiting notice lives beside the phase button.

When the current player has no remaining base choice but another player does, the
message "等待其他玩家選擇根據地" should be in the top phase action bar next to
結束/disabled action controls, not inside the left purchase/control column.
"""
from __future__ import annotations

import json
import os
import sys
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
RECORD_DIR = ROOT / 'docs' / 'records' / 'setup-ui'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'BASE_SELECTION_NOTICE_PLACEMENT_VALIDATION.json'
OUT_MD = RECORD_DIR / 'BASE_SELECTION_NOTICE_PLACEMENT_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'base_selection_notice_placement_validation.png'


def post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def validate_page(page) -> dict:
    setup = post('/test/force-base-selection', {
        'faction_ids': ['red_army', 'hong_kong'],
        'player_names': ['玩家1', '玩家2'],
    })
    game_id = setup['game_id']
    player_id = setup['players'][0]['id']

    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.evaluate(
        "([gameIdValue, playerIdValue]) => { gameId = gameIdValue; playerId = playerIdValue; connect(); }",
        [game_id, player_id],
    )
    page.wait_for_selector('#phaseActionBar', timeout=10000)
    page.wait_for_selector('#purchaseSection .panel-title', timeout=10000)
    page.wait_for_timeout(600)

    notice = page.locator('#phaseActionNotice')
    notice_count = notice.count()
    notice_text = notice.inner_text().strip() if notice_count else ''
    notice_box = notice.bounding_box() if notice_count else None
    button_box = page.locator('#advanceStepBtn').bounding_box()
    phase_bar_box = page.locator('#phaseActionBar').bounding_box()
    base_panel_display = page.locator('#baseSelectionPanel').evaluate("el => getComputedStyle(el).display")
    left_column_contains_waiting = '等待其他玩家選擇根據地' in page.locator('#controlPanel').inner_text()

    notice_inside_bar = False
    notice_near_button = False
    if notice_box and button_box and phase_bar_box:
        notice_inside_bar = (
            notice_box['x'] >= phase_bar_box['x']
            and notice_box['y'] >= phase_bar_box['y']
            and notice_box['x'] + notice_box['width'] <= phase_bar_box['x'] + phase_bar_box['width'] + 1
            and notice_box['y'] + notice_box['height'] <= phase_bar_box['y'] + phase_bar_box['height'] + 1
        )
        vertical_delta = abs((notice_box['y'] + notice_box['height'] / 2) - (button_box['y'] + button_box['height'] / 2))
        horizontal_gap = max(0, button_box['x'] - (notice_box['x'] + notice_box['width']))
        notice_near_button = vertical_delta <= 12 and horizontal_gap <= 24
    else:
        vertical_delta = None
        horizontal_gap = None

    page.screenshot(path=str(SCREENSHOT), full_page=True)

    results = [
        {
            'name': 'waiting_notice_is_in_phase_action_bar_next_to_button',
            'ok': notice_text == '等待其他玩家選擇根據地' and notice_inside_bar and notice_near_button,
            'detail': {
                'notice_text': notice_text,
                'notice_box': notice_box,
                'button_box': button_box,
                'phase_bar_box': phase_bar_box,
                'vertical_center_delta_px': vertical_delta,
                'horizontal_gap_px': horizontal_gap,
            },
        },
        {
            'name': 'waiting_notice_does_not_occupy_left_purchase_column',
            'ok': base_panel_display == 'none' and not left_column_contains_waiting,
            'detail': {
                'base_selection_panel_display': base_panel_display,
                'left_column_contains_waiting': left_column_contains_waiting,
            },
        },
    ]
    return {
        'setup': {'game_id': game_id, 'player_id': player_id},
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshot': str(SCREENSHOT),
    }


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = ctx.new_page()
        payload = validate_page(page)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Base Selection Notice Placement Validation',
        '',
        f"summary: {payload['summary']}",
        '',
        f"screenshot: {payload['screenshot']}",
        '',
    ]
    for result in payload['results']:
        lines.append(f"## {'PASS' if result['ok'] else 'FAIL'} — {result['name']}")
        lines.append('')
        lines.append('```json')
        lines.append(json.dumps(result['detail'], ensure_ascii=False, indent=2))
        lines.append('```')
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
