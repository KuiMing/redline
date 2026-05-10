#!/usr/bin/env python3
"""Validate that the permanent/static purchase area aligns with the random market.

The command screen can show a base-selection notice above the permanent purchase
area. That notice must not push the permanent purchase cards downward; the
permanent purchase title should align vertically with the random market title.
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
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = ROOT / 'PURCHASE_SECTION_ALIGNMENT_VALIDATION.json'
OUT_MD = ROOT / 'PURCHASE_SECTION_ALIGNMENT_VALIDATION.md'
SCREENSHOT = ROOT / 'purchase_section_alignment_validation.png'


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
    page.wait_for_selector('#purchaseSection .panel-title', timeout=10000)
    page.wait_for_selector('#randomMarketPanel .panel-title', timeout=10000)
    page.wait_for_timeout(600)

    static_box = page.locator('#purchaseSection .panel-title').bounding_box()
    random_box = page.locator('#randomMarketPanel .panel-title').bounding_box()
    static_cards = page.locator('#purchaseStatic .card').count()
    random_cards = page.locator('#purchaseRandom .card').count()
    base_panel_display = page.locator('#baseSelectionPanel').evaluate("el => getComputedStyle(el).display")

    top_delta = None
    aligned = False
    if static_box and random_box:
        top_delta = round(abs(static_box['y'] - random_box['y']), 2)
        aligned = top_delta <= 4

    page.screenshot(path=str(SCREENSHOT), full_page=True)

    results = [
        {
            'name': 'static_purchase_title_aligns_with_random_market_title',
            'ok': bool(aligned),
            'detail': {
                'static_title_box': static_box,
                'random_title_box': random_box,
                'top_delta_px': top_delta,
                'allowed_delta_px': 4,
                'base_selection_panel_display': base_panel_display,
            },
        },
        {
            'name': 'purchase_zones_populated_for_visual_comparison',
            'ok': static_cards >= 6 and random_cards >= 5,
            'detail': {'static_cards': static_cards, 'random_cards': random_cards},
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
