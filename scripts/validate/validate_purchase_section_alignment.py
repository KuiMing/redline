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
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
RECORDS_DIR = ROOT / 'docs' / 'records' / 'purchase'
RECORDS_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = RECORDS_DIR / 'PURCHASE_SECTION_ALIGNMENT_VALIDATION.json'
OUT_MD = RECORDS_DIR / 'PURCHASE_SECTION_ALIGNMENT_VALIDATION.md'
SCREENSHOT = RECORDS_DIR / 'purchase_section_alignment_validation.png'
HOVER_SCREENSHOT = RECORDS_DIR / 'purchase_card_mouse_hover_focus_validation.png'


def post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def validate_page(page) -> dict:
    created = post('/create', {})
    game_id = created['game_id']
    host_id = created['host_id']
    joined = post('/join', {'game_id': game_id, 'name': '香港'})
    player_id = joined['player_id']
    for pid, faction_id, base_name in (
        (host_id, 'red_army', '北京'),
        (player_id, 'hong_kong', '香港城'),
    ):
        chosen = post('/choose-faction', {
            'game_id': game_id,
            'player_id': pid,
            'faction_id': faction_id,
            'base_name': base_name,
        })
        if chosen.get('error'):
            raise AssertionError(chosen)
        ready = post('/ready', {'game_id': game_id, 'player_id': pid, 'ready': True})
        if ready.get('error'):
            raise AssertionError(ready)
    started = post('/start', {'game_id': game_id, 'player_id': host_id, 'resume_token': created['resume_token'], 'market_mode': 'sample_53'})
    if started.get('error'):
        raise AssertionError(started)
    prepared = post('/test/set-hand', {
        'game_id': game_id,
        'player_id': player_id,
        'cards': ['追隨者', '樂捐者', '追隨者', '樂捐者', '宣傳家'],
        'turn_phase': 'action',
        'set_current_player': True,
    })
    if prepared.get('error'):
        raise AssertionError(prepared)

    page.goto(
        f"{BASE_URL}/?game_id={game_id}&player_id={player_id}&resume_token={joined.get('resume_token', '')}&v=alignment",
        wait_until='networkidle',
    )
    page.wait_for_selector('#purchaseSection .panel-title', timeout=10000)
    page.wait_for_selector('#randomMarketPanel .panel-title', timeout=10000)
    page.wait_for_timeout(600)
    event_reveal = page.locator('#eventRevealModal')
    if event_reveal.count() and event_reveal.is_visible():
        page.evaluate('closeEventReveal()')
        page.wait_for_timeout(250)

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
      const cards = [...document.querySelectorAll('#purchaseStatic .card')];
      const selectedCard = cards[0];
      const card = cards[1];
      const neutralCard = cards[2];
      if (!selectedCard || !card || !neutralCard) return null;
      selectedCard.classList.add('purchase-card-selected', 'rl-pad-focus');
      const selectedFocusStyle = getComputedStyle(selectedCard, '::after');
      const selectedFocus = {
        content: selectedFocusStyle.content,
        border_color: selectedFocusStyle.borderTopColor,
        border_width: selectedFocusStyle.borderTopWidth,
        background_image: selectedFocusStyle.backgroundImage,
        z_index: selectedFocusStyle.zIndex,
      };
      selectedCard.classList.remove('rl-pad-focus');
      card.classList.add('rl-pad-focus');
      const button = selectedCard.closest('.purchase-card-item')?.querySelector('.purchase-card-select-button');
      button?.classList.add('is-selected');
      const focusStyle = getComputedStyle(card, '::after');
      const selectedOverlay = selectedCard.querySelector('.purchase-card-selected-overlay');
      const neutralFocusStyle = getComputedStyle(neutralCard, '::after');
      return {
        card_name: card.dataset.cardName,
        focus_background: focusStyle.backgroundColor,
        focus_background_image: focusStyle.backgroundImage,
        focus_border_width: focusStyle.borderTopWidth,
        focus_border_style: focusStyle.borderTopStyle,
        focus_border_color: focusStyle.borderTopColor,
        focus_pointer_events: focusStyle.pointerEvents,
        selected_overlay_display: selectedOverlay ? getComputedStyle(selectedOverlay).display : null,
        button_background: button ? getComputedStyle(button).backgroundColor : null,
        selected_focus: selectedFocus,
        selected_overlay_background: selectedOverlay ? getComputedStyle(selectedOverlay).backgroundColor : null,
        selected_overlay_z_index: selectedOverlay ? getComputedStyle(selectedOverlay).zIndex : null,
        neutral_focus_content: neutralFocusStyle.content,
        focused_card_count: document.querySelectorAll('#purchaseStatic .card.rl-pad-focus').length,
      };
    }""")
    hover_visual = {}
    for zone in ('purchaseRandom', 'purchaseStatic', 'hand'):
        page.locator(f'#{zone} .card').first.hover()
        hover_visual[zone] = page.evaluate("""(zone) => {
          const hovered = document.querySelector(`#${zone} .card:hover`);
          const padFocus = document.querySelector('#commandGrid .card.rl-pad-focus:not(:hover)');
          if (!hovered) return null;
          const hoverStyle = getComputedStyle(hovered, '::after');
          const padStyle = padFocus ? getComputedStyle(padFocus, '::after') : null;
          return {
            content: hoverStyle.content,
            background: hoverStyle.backgroundColor,
            background_image: hoverStyle.backgroundImage,
            border_width: hoverStyle.borderTopWidth,
            border_style: hoverStyle.borderTopStyle,
            border_color: hoverStyle.borderTopColor,
            pointer_events: hoverStyle.pointerEvents,
            controller_focus_content: padStyle?.content || null,
          };
        }""", zone)
    page.locator('#purchaseRandom .card').first.hover()
    page.screenshot(path=str(HOVER_SCREENSHOT), full_page=True)
    page.mouse.move(0, 0)
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

    living_room_layout = page.evaluate("""() => {
      document.documentElement.dataset.display = 'living-room';
      const panelIds = ['randomMarketPanel', 'controlPanel', 'handPanel'];
      const boxes = Object.fromEntries(panelIds.map((id) => {
        const rect = document.getElementById(id).getBoundingClientRect();
        return [id, {x: rect.x, y: rect.y, width: rect.width, height: rect.height}];
      }));
      const rows = Object.fromEntries(['purchaseRandom', 'purchaseStatic', 'hand'].map((id) => {
        const el = document.getElementById(id);
        return [id, {
          client_width: el.clientWidth,
          scroll_width: el.scrollWidth,
          overflow_x: getComputedStyle(el).overflowX,
          has_horizontal_overflow: el.scrollWidth > el.clientWidth,
        }];
      }));
      const controls_outside_panel = [
        ['#purchaseRandom .purchase-card-select-button', 'randomMarketPanel'],
        ['#purchaseStatic .purchase-card-select-button', 'controlPanel'],
        ['#hand .hand-card-action-btn', 'handPanel'],
      ].map(([selector, panelId]) => {
        const panel = document.getElementById(panelId).getBoundingClientRect();
        const controls = [...document.querySelectorAll(selector)];
        return {
          selector,
          count: controls.length,
          outside: controls.filter((el) => {
            const r = el.getBoundingClientRect();
            return r.height < 5 || r.bottom > panel.bottom + 0.5 || r.right > innerWidth + 0.5;
          }).length,
        };
      });
      const focusCard = document.querySelector('#purchaseStatic .card.rl-pad-focus');
      const peerCard = [...document.querySelectorAll('#purchaseStatic .card')].find((card) => card !== focusCard && !card.classList.contains('rl-pad-focus'));
      return {
        boxes,
        rows,
        controls_outside_panel,
        focus_background: focusCard ? getComputedStyle(focusCard, '::after').backgroundColor : null,
        focus_border_width: focusCard ? getComputedStyle(focusCard, '::after').borderTopWidth : null,
        focus_border_style: focusCard ? getComputedStyle(focusCard, '::after').borderTopStyle : null,
        focus_border_color: focusCard ? getComputedStyle(focusCard, '::after').borderTopColor : null,
        focus_outline: focusCard ? getComputedStyle(focusCard).outlineStyle : null,
        focus_shadow: focusCard ? getComputedStyle(focusCard).boxShadow : null,
        peer_outline: peerCard ? getComputedStyle(peerCard).outlineStyle : null,
        peer_shadow: peerCard ? getComputedStyle(peerCard).boxShadow : null,
      };
    }""")

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
            'name': 'controller_focus_uses_opaque_yellow_border_with_transparent_interior',
            'ok': bool(
                focus_visual
                and focus_visual['focus_background'] == 'rgba(0, 0, 0, 0)'
                and focus_visual['focus_background_image'] != 'none'
                and focus_visual['focus_border_width'] == '2px'
                and focus_visual['focus_border_style'] == 'solid'
                and focus_visual['focus_border_color'] == 'rgb(255, 216, 61)'
                and focus_visual['focus_pointer_events'] == 'none'
                and focus_visual['selected_overlay_display'] == 'block'
                and focus_visual['button_background'] == 'rgb(21, 128, 61)'
                and focus_visual['selected_focus']['content'] != 'none'
                and focus_visual['selected_focus']['border_color'] == 'rgb(255, 216, 61)'
                and focus_visual['selected_focus']['border_width'] == '2px'
                and focus_visual['selected_focus']['background_image'] != 'none'
                and focus_visual['selected_overlay_background'] == 'rgba(255, 255, 255, 0.28)'
                and int(focus_visual['selected_focus']['z_index']) > int(focus_visual['selected_overlay_z_index'])
                and focus_visual['neutral_focus_content'] == 'none'
                and focus_visual['focused_card_count'] == 1
            ),
            'detail': focus_visual,
        },
        {
            'name': 'mouse_hover_uses_single_yellow_border_and_crosshair_in_all_card_rows',
            'ok': all(
                detail
                and detail['content'] != 'none'
                and detail['background'] == 'rgba(0, 0, 0, 0)'
                and detail['background_image'] != 'none'
                and detail['border_width'] == '2px'
                and detail['border_style'] == 'solid'
                and detail['border_color'] == 'rgb(255, 216, 61)'
                and detail['pointer_events'] == 'none'
                and detail['controller_focus_content'] == 'none'
                for detail in hover_visual.values()
            ),
            'detail': hover_visual,
        },
        {
            'name': 'living_room_keeps_three_rows_without_scrollbars_or_focus_glow',
            'ok': bool(
                living_room_layout['boxes']['randomMarketPanel']['y']
                < living_room_layout['boxes']['controlPanel']['y']
                < living_room_layout['boxes']['handPanel']['y']
                and all(
                    not detail['has_horizontal_overflow'] and detail['overflow_x'] == 'hidden'
                    for detail in living_room_layout['rows'].values()
                )
                and all(c['count'] > 0 and c['outside'] == 0 for c in living_room_layout['controls_outside_panel'])
                and living_room_layout['focus_background'] == 'rgba(0, 0, 0, 0)'
                and float(living_room_layout['focus_border_width'].removesuffix('px')) >= 2.5
                and living_room_layout['focus_border_style'] == 'solid'
                and living_room_layout['focus_border_color'] == 'rgb(255, 216, 61)'
                and living_room_layout['focus_outline'] == living_room_layout['peer_outline']
                and living_room_layout['focus_shadow'] == living_room_layout['peer_shadow']
            ),
            'detail': living_room_layout,
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
