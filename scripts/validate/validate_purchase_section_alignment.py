#!/usr/bin/env python3
"""Validate the command centre's random/static/hand three-row layout."""
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

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_URL = 'http://127.0.0.1:8000'
RECORDS_DIR = ROOT / 'docs' / 'records' / 'purchase'
RECORDS_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = RECORDS_DIR / 'PURCHASE_SECTION_ALIGNMENT_VALIDATION.json'
OUT_MD = RECORDS_DIR / 'PURCHASE_SECTION_ALIGNMENT_VALIDATION.md'
SCREENSHOT = RECORDS_DIR / 'purchase_section_alignment_validation.png'


def post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def validate_page(page) -> dict:
    setup = post('/test/force-base-selection', {
        'faction_ids': ['red_army', 'hong_kong'],
        'player_names': ['玩家1', '玩家2'],
        'bases': {'p1': ['北京'], 'p2': ['香港城']},
    })
    game_id = setup['game_id']
    player_id = setup['players'][0]['id']

    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.evaluate(
        "([gameIdValue, playerIdValue]) => { gameId = gameIdValue; playerId = playerIdValue; connect(); }",
        [game_id, player_id],
    )
    page.wait_for_selector('#purchaseSection .panel-title', timeout=10000)
    page.wait_for_selector('#randomMarketPanel .panel-title', timeout=10000)
    page.wait_for_timeout(600)

    random_panel_box = page.locator('#randomMarketPanel').bounding_box()
    static_panel_box = page.locator('#controlPanel').bounding_box()
    hand_panel_box = page.locator('#handPanel').bounding_box()
    static_card_box = page.locator('#purchaseStatic .card').first.bounding_box()
    random_card_box = page.locator('#purchaseRandom .card').first.bounding_box()
    hand_card_box = page.locator('#hand .card').first.bounding_box()
    static_cards = page.locator('#purchaseStatic .card').count()
    random_cards = page.locator('#purchaseRandom .card').count()
    hand_cards = page.locator('#hand .card').count()
    base_panel_display = page.locator('#baseSelectionPanel').evaluate("el => getComputedStyle(el).display")
    focus_visual = page.evaluate("""() => {
      const card = document.querySelector('#purchaseStatic .card');
      if (!card) return null;
      card.classList.add('rl-pad-focus', 'purchase-card-selected');
      const button = card.closest('.purchase-card-item')?.querySelector('.purchase-card-select-button');
      button?.classList.add('is-selected');
      const focusStyle = getComputedStyle(card, '::after');
      const selectedOverlay = card.querySelector('.purchase-card-selected-overlay');
      return {
        card_name: card.dataset.cardName,
        focus_background: focusStyle.backgroundColor,
        focus_pointer_events: focusStyle.pointerEvents,
        selected_overlay_display: selectedOverlay ? getComputedStyle(selectedOverlay).display : null,
        button_background: button ? getComputedStyle(button).backgroundColor : null,
      };
    }""")
    row_overflow = page.evaluate("""() => Object.fromEntries(
      ['purchaseRandom', 'purchaseStatic', 'hand'].map((id) => {
        const el = document.getElementById(id);
        return [id, {
          client_width: el.clientWidth,
          scroll_width: el.scrollWidth,
          overflow_x: getComputedStyle(el).overflowX,
          has_horizontal_overflow: el.scrollWidth > el.clientWidth,
        }];
      })
    )""")

    panel_ordered = bool(
        random_panel_box
        and static_panel_box
        and hand_panel_box
        and random_panel_box['y'] < static_panel_box['y'] < hand_panel_box['y']
    )
    row_heights = [box['height'] for box in (random_panel_box, static_panel_box, hand_panel_box) if box]
    equal_rows = len(row_heights) == 3 and max(row_heights) - min(row_heights) <= 1
    cards_inside_rows = bool(
        random_panel_box
        and static_panel_box
        and hand_panel_box
        and random_card_box
        and static_card_box
        and hand_card_box
        and random_panel_box['y'] <= random_card_box['y'] < random_panel_box['y'] + random_panel_box['height']
        and static_panel_box['y'] <= static_card_box['y'] < static_panel_box['y'] + static_panel_box['height']
        and hand_panel_box['y'] <= hand_card_box['y'] < hand_panel_box['y'] + hand_panel_box['height']
    )

    page.screenshot(path=str(SCREENSHOT), full_page=True)

    results = [
        {
            'name': 'command_centre_uses_equal_random_static_hand_rows',
            'ok': panel_ordered and equal_rows,
            'detail': {
                'random_panel_box': random_panel_box,
                'static_panel_box': static_panel_box,
                'hand_panel_box': hand_panel_box,
                'row_heights': row_heights,
                'base_selection_panel_display': base_panel_display,
            },
        },
        {
            'name': 'first_card_stays_inside_each_assigned_row',
            'ok': cards_inside_rows,
            'detail': {
                'random_first_card_box': random_card_box,
                'static_first_card_box': static_card_box,
                'hand_first_card_box': hand_card_box,
            },
        },
        {
            'name': 'purchase_zones_populated_for_visual_comparison',
            'ok': static_cards >= 6 and random_cards >= 5,
            'detail': {'static_cards': static_cards, 'random_cards': random_cards, 'hand_cards': hand_cards},
        },
        {
            'name': 'card_rows_never_show_horizontal_scrollbars',
            'ok': all(
                not detail['has_horizontal_overflow'] and detail['overflow_x'] == 'hidden'
                for detail in row_overflow.values()
            ),
            'detail': row_overflow,
        },
        {
            'name': 'controller_focus_uses_yellow_overlay_distinct_from_selected_state',
            'ok': bool(
                focus_visual
                and focus_visual['focus_background'] == 'rgba(255, 216, 61, 0.16)'
                and focus_visual['focus_pointer_events'] == 'none'
                and focus_visual['selected_overlay_display'] == 'block'
                and focus_visual['button_background'] == 'rgb(21, 128, 61)'
            ),
            'detail': focus_visual,
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
        'screenshot': str(SCREENSHOT.relative_to(ROOT)),
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
        '# Purchase Section Alignment Validation',
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
