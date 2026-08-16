#!/usr/bin/env python3
import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
ROOT = Path(__file__).resolve().parents[1]
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui' / 'hong-kong-base-relocation'
REPORT = RECORD_DIR / 'HONG_KONG_BASE_RELOCATION_BROWSER_VALIDATION.json'
SCREENSHOT = RECORD_DIR / 'hong_kong_base_relocation_ui.png'
FAILURE_READY_SCREENSHOT = RECORD_DIR / 'failed_event_relocation_ready.png'
FAILURE_SUCCESS_SCREENSHOT = RECORD_DIR / 'failed_event_relocation_success.png'


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
        expected_relocatable_labels = [
            f'{town}（可遷移根據地）'
            for town in ['臺北', '倫敦', '卡加利', '多倫多']
        ]
        record('lobby_hong_kong_details_list_all_bases_and_abilities', all(text in lobby_detail for text in expected_base_text), lobby_detail)
        record(
            'lobby_uses_relocatable_base_label_without_old_typo',
            all(text in lobby_detail for text in expected_relocatable_labels) and '可前移根據地' not in lobby_detail,
            lobby_detail,
        )
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
        record(
            'free_relocation_moves_anchor_without_spending_moves',
            after['base'] == '倫敦' and after['orgs'].get('倫敦') == 1 and '香港城' not in after['orgs'] and after['moves_left'] == before['moves_left'],
            {
                'before': {'base': before['base'], 'orgs': before['orgs'], 'moves_left': before['moves_left']},
                'after': {'base': after['base'], 'orgs': after['orgs'], 'moves_left': after['moves_left']},
            },
        )
        record('free_window_is_consumed_after_move', after_state['hk_free_base_relocation'] is False, after_state['hk_free_base_relocation'])
        page.click('#myFactionBtn') if not page.locator('#myFactionView').evaluate("el => el.classList.contains('active')") else None
        my_faction_text = page.locator('#myFactionBody').inner_text()
        record('new_base_ability_is_shown_as_active', '倫敦（目前根據地）：國際線' in my_faction_text and '目前生效能力\n國際線' in my_faction_text, my_faction_text)

        # Failure-path proof: the event's mandatory discard must finish before relocation opens.
        # The old runtime exposed every destination button too early; all clicks were rejected by
        # the pending-choice guard with 「請先完成目前的選擇」.
        for target_index, target_town in enumerate(['臺北', '倫敦', '卡加利', '多倫多']):
            failed_setup = post_json('/test/setup-event-card-proof', {
                'event_name': '香港抗暴之戰',
                'viewer_faction': 'hong_kong',
                'hk_failed_relocation': True,
            })
            page.goto(f"{BASE_URL}{failed_setup['url']}&v=hk-failed-event-relocation", wait_until='domcontentloaded')
            page.wait_for_function(
                "window.lastGameState?.pending_choice?.choice_key === 'event_discard_self'",
                timeout=15000,
            )
            if page.locator('#eventRevealModal').is_visible():
                page.locator('#eventRevealModal').click(position={'x': 5, 'y': 5})
                page.locator('#eventRevealModal').wait_for(state='hidden', timeout=5000)
            pending_state = page.evaluate('window.lastGameState')
            if target_index == 0:
                record(
                    'failed_event_does_not_expose_relocation_before_required_discard',
                    pending_state.get('hk_free_base_relocation') is False
                    and page.locator('.hk-base-relocation-panel').count() == 0,
                    {
                        'pending_choice': pending_state.get('pending_choice', {}).get('choice_key'),
                        'hk_free_base_relocation': pending_state.get('hk_free_base_relocation'),
                    },
                )
                record(
                    'failed_event_prioritizes_required_discard_choice',
                    page.locator('#choiceModal').is_visible()
                    and '請選擇 1 張手牌棄掉' in page.locator('#choiceModal').inner_text(),
                    page.locator('#choiceModal').inner_text(),
                )

            page.locator('#choiceModal .choice-card-btn-multi').first.click()
            page.locator('#choiceModalCards .modal-choice-btn').click()
            page.wait_for_function(
                "window.lastGameState?.pending_choice == null && window.lastGameState?.hk_free_base_relocation === true",
                timeout=10000,
            )
            page.click('#myFactionBtn')
            panel = page.locator('.hk-base-relocation-panel')
            panel.wait_for(state='visible', timeout=10000)
            target_button = panel.locator(f'[data-hk-relocate-town="{target_town}"]')
            target_button.wait_for(state='visible', timeout=5000)
            if target_index == 0:
                FAILURE_READY_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(FAILURE_READY_SCREENSHOT), full_page=True)
            target_button.click()
            page.wait_for_function(
                "([town]) => window.lastGameState?.players?.some(p => p.faction === 'hong_kong' && p.base === town)",
                arg=[target_town],
                timeout=10000,
            )
            moved_state = page.evaluate('window.lastGameState')
            moved_hk = next(player for player in moved_state['players'] if player['faction'] == 'hong_kong')
            record(
                f'failed_event_relocation_button_moves_base_to_{target_town}',
                moved_hk['base'] == target_town
                and moved_hk.get('orgs', {}).get(target_town) == 1
                and moved_state.get('hk_free_base_relocation') is False,
                {
                    'base': moved_hk['base'],
                    'orgs': moved_hk.get('orgs', {}),
                    'moves_left': moved_hk.get('moves_left'),
                },
            )
            if target_index == 3:
                page.click('#myFactionBtn') if not page.locator('#myFactionView').evaluate("el => el.classList.contains('active')") else None
                page.screenshot(path=str(FAILURE_SUCCESS_SCREENSHOT), full_page=True)

        record('browser_console_has_no_errors', not console_errors, console_errors)
        browser.close()

    result = {
        'status': 'passed' if all(check['passed'] for check in checks) else 'failed',
        'checks_passed': sum(check['passed'] for check in checks),
        'checks_total': len(checks),
        'base_url': '[REDACTED]',
        'screenshots': [
            str(SCREENSHOT.relative_to(ROOT)),
            str(FAILURE_READY_SCREENSHOT.relative_to(ROOT)),
            str(FAILURE_SUCCESS_SCREENSHOT.relative_to(ROOT)),
        ],
        'checks': checks,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
