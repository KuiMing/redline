#!/usr/bin/env python3
import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
SCREENSHOT = Path('/Users/benmini/.hermes/cache/images/hong_kong_base_relocation_ui.png')


def post_json(path, payload):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def main():
    checks = []
    console_errors = []

    def record(name, passed, detail=None):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)

        # Lobby proof: Hong Kong's initial faction explanation lists every movable base and ability.
        page.goto(BASE_URL, wait_until='networkidle')
        page.fill('#playerName', '香港說明測試')
        page.click('#createRoomBtn')
        page.locator('#factionPicker').wait_for(state='visible', timeout=15000)
        page.get_by_role('button', name='香港', exact=True).click()
        page.get_by_role('button', name='香港城', exact=True).click()
        page.wait_for_function("() => document.getElementById('factionDetailPanel')?.innerText.includes('多倫多')", timeout=5000)
        lobby_detail = page.locator('#factionDetailPanel').inner_text()
        expected_base_text = ['香港城', '臺北', '倫敦', '卡加利', '多倫多', '安全屋', '國際線', '商貿組織']
        record('lobby_hong_kong_details_list_all_bases_and_abilities', all(text in lobby_detail for text in expected_base_text), lobby_detail)
        record('lobby_uses_correct_event_name_and_rule', '香港抗暴之戰' in lobby_detail and '香港抗爭之烈' not in lobby_detail and '免費前移一次根據地' in lobby_detail, lobby_detail)

        # Runtime proof: event settlement exposes the free relocation controls in My Faction.
        setup = post_json('/test/setup-event-card-proof', {
            'event_name': '香港抗暴之戰',
            'viewer_faction': 'hong_kong',
            'hk_free_relocation': True,
        })
        page.goto(f"{BASE_URL}{setup['url']}&v=hk-base-relocation", wait_until='domcontentloaded')
        page.wait_for_function("window.lastGameState?.hk_free_base_relocation === true", timeout=15000)
        if page.locator('#eventRevealModal').is_visible():
            page.locator('#eventRevealModal').click(position={'x': 5, 'y': 5})
            page.locator('#eventRevealModal').wait_for(state='hidden', timeout=5000)
        before = page.evaluate("window.lastGameState.players.find(p => p.id === new URLSearchParams(location.search).get('player_id'))")
        page.click('#myFactionBtn')
        page.locator('.hk-base-relocation-panel').wait_for(state='visible', timeout=10000)
        panel_text = page.locator('.hk-base-relocation-panel').inner_text()
        tab_text = page.locator('#myFactionBtn').inner_text()
        buttons = page.locator('.hk-base-relocation-actions button').all_inner_texts()
        record('settled_event_marks_my_faction_tab', '可前移' in tab_text, tab_text)
        record('free_relocation_panel_has_four_targets_and_keep', all(text in '｜'.join(buttons) for text in ['臺北', '倫敦', '卡加利', '多倫多', '維留香港城']) and '香港抗暴之戰' in panel_text, {'panel': panel_text, 'buttons': buttons})

        SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        page.evaluate("() => document.querySelector('[data-hk-relocate-town=\"倫敦\"]')?.click()")
        page.wait_for_function("window.lastGameState?.players?.some(p => p.faction === 'hong_kong' && p.base === '倫敦')", timeout=10000)
        after_state = page.evaluate("window.lastGameState")
        after = next(player for player in after_state['players'] if player['faction'] == 'hong_kong')
        record('free_relocation_moves_anchor_without_spending_moves', after['base'] == '倫敦' and after['orgs'].get('倫敦') == 1 and '香港城' not in after['orgs'] and after['moves_left'] == before['moves_left'], {'before': before, 'after': after})
        record('free_window_is_consumed_after_move', after_state['hk_free_base_relocation'] is False, after_state['hk_free_base_relocation'])
        page.click('#myFactionBtn') if not page.locator('#myFactionView').evaluate("el => el.classList.contains('active')") else None
        my_faction_text = page.locator('#myFactionBody').inner_text()
        record('new_base_ability_is_shown_as_active', '倫敦（目前根據地）：國際線' in my_faction_text and '目前生效能力\n國際線' in my_faction_text, my_faction_text)
        record('browser_console_has_no_errors', not console_errors, console_errors)
        browser.close()

    result = {
        'status': 'passed' if all(check['passed'] for check in checks) else 'failed',
        'checks_passed': sum(check['passed'] for check in checks),
        'checks_total': len(checks),
        'screenshot': str(SCREENSHOT),
        'checks': checks,
    }
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
