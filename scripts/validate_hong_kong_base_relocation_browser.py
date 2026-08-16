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
OWN_ORG_BASE_MAP_SCREENSHOT = RECORD_DIR / 'own_organization_relocation_and_base_markers.png'
END_TURN_DECISION_SCREENSHOT = RECORD_DIR / 'end_turn_relocation_decision_before_handoff.png'


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
        record(
            'lobby_uses_correct_event_name_and_rule',
            '香港抗暴之戰' in lobby_detail
            and '香港抗爭之烈' not in lobby_detail
            and '免費遷移一次根據地' in lobby_detail
            and '亦可留在香港城' in lobby_detail,
            lobby_detail,
        )

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
        expected_buttons = ['遷移至臺北', '遷移至倫敦', '遷移至卡加利', '遷移至多倫多', '留在香港城']
        record('settled_event_marks_my_faction_tab', '可遷移' in tab_text and '可前移' not in tab_text, tab_text)
        record(
            'free_relocation_panel_has_four_targets_and_keep',
            buttons == expected_buttons
            and '香港抗暴之戰：免費遷移根據地' in panel_text
            and '亦可留在目前的 香港城' in panel_text
            and '前移' not in panel_text
            and '維留' not in panel_text,
            {'panel': panel_text, 'buttons': buttons},
        )

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

        # Exact playtest regression: pressing End Turn must pause the handoff until Hong Kong
        # completes the event discard and then chooses relocation or keep.
        occupied_setup = post_json('/test/setup-event-card-proof', {
            'event_name': '香港抗暴之戰',
            'viewer_faction': 'hong_kong',
            'hk_end_turn_relocation_timing': True,
            'viewer_orgs': {'香港城': 1, '臺北': 1},
            'red_orgs': {'北京': 1},
        })
        page.goto(f"{BASE_URL}{occupied_setup['url']}&v=hk-end-turn-relocation-timing", wait_until='domcontentloaded')
        page.wait_for_function(
            "window.lastGameState?.current_player === 'viewer' && window.lastGameState?.turn_phase === 'end'",
            timeout=15000,
        )
        if page.locator('#eventRevealModal').is_visible():
            page.locator('#eventRevealModal').click(position={'x': 5, 'y': 5})
            page.locator('#eventRevealModal').wait_for(state='hidden', timeout=5000)
        page.click('#advanceStepBtn')
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'event_discard_self'",
            timeout=10000,
        )
        end_turn_pending = page.evaluate('window.lastGameState')
        record(
            'end_turn_keeps_hong_kong_seat_during_required_event_discard',
            end_turn_pending.get('current_player') == 'viewer'
            and end_turn_pending.get('turn_phase') == 'end'
            and end_turn_pending.get('hk_free_base_relocation') is False,
            {
                'current_player': end_turn_pending.get('current_player'),
                'turn_phase': end_turn_pending.get('turn_phase'),
                'pending_choice': end_turn_pending.get('pending_choice', {}).get('choice_key'),
            },
        )
        page.locator('#choiceModal .choice-card-btn-multi').first.click()
        page.locator('#choiceModalCards .modal-choice-btn').click()
        page.wait_for_function(
            "window.lastGameState?.pending_choice == null && window.lastGameState?.hk_free_base_relocation === true",
            timeout=10000,
        )
        relocation_ready = page.evaluate('window.lastGameState')
        record(
            'hong_kong_relocation_decision_opens_before_turn_handoff',
            relocation_ready.get('current_player') == 'viewer'
            and relocation_ready.get('turn_phase') == 'end',
            {'current_player': relocation_ready.get('current_player'), 'turn_phase': relocation_ready.get('turn_phase')},
        )
        record(
            'end_turn_button_waits_for_relocation_decision',
            page.locator('#advanceStepBtn').is_disabled()
            and '請先決定香港根據地' in page.locator('#phaseActionMeta').inner_text(),
            {
                'disabled': page.locator('#advanceStepBtn').is_disabled(),
                'message': page.locator('#phaseActionMeta').inner_text(),
            },
        )
        page.click('#myFactionBtn')
        own_taipei_button = page.locator('[data-hk-relocate-town="臺北"]')
        own_taipei_button.wait_for(state='visible', timeout=10000)
        record(
            'own_organization_destination_is_enabled_without_redundant_label',
            own_taipei_button.is_enabled()
            and own_taipei_button.inner_text() == '遷移至臺北'
            and '已有香港組織' not in page.locator('.hk-base-relocation-panel').inner_text(),
            {'button': own_taipei_button.inner_text(), 'enabled': own_taipei_button.is_enabled()},
        )
        END_TURN_DECISION_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(END_TURN_DECISION_SCREENSHOT), full_page=True)
        own_taipei_button.click()
        page.wait_for_function(
            "window.lastGameState?.current_player === 'red' && window.lastGameState?.players?.some(p => p.faction === 'hong_kong' && p.base === '臺北')",
            timeout=10000,
        )
        occupied_after = page.evaluate('window.lastGameState')
        occupied_hk = next(player for player in occupied_after['players'] if player['faction'] == 'hong_kong')
        record(
            'next_player_starts_only_after_hong_kong_relocation_decision',
            occupied_after.get('current_player') == 'red'
            and occupied_after.get('turn_phase') == 'action'
            and occupied_hk.get('base') == '臺北'
            and occupied_after.get('hk_free_base_relocation') is False,
            {'current_player': occupied_after.get('current_player'), 'turn_phase': occupied_after.get('turn_phase'), 'base': occupied_hk.get('base')},
        )
        record(
            'own_destination_becomes_base_without_removing_old_organization',
            occupied_hk.get('orgs', {}).get('香港城') == 1
            and occupied_hk.get('orgs', {}).get('臺北') == 1
            and occupied_hk.get('organization_counts', {}).get('total') == 2,
            {'orgs': occupied_hk.get('orgs'), 'counts': occupied_hk.get('organization_counts')},
        )

        page.click('button.game-tab[data-view="map"]')
        map_frame = page.frame_locator('#strategicMapFrame')
        map_frame.locator('.base-badge').first.wait_for(state='visible', timeout=15000)
        base_badges = map_frame.locator('.base-badge').evaluate_all(
            "nodes => nodes.map(node => ({faction: node.dataset.baseFaction, town: node.dataset.baseTown, text: node.textContent}))"
        )
        badge_pairs = {(badge['faction'], badge['town']) for badge in base_badges}
        record(
            'map_marks_every_participating_faction_current_base',
            len(base_badges) == len(occupied_after['players'])
            and ('hong_kong', '臺北') in badge_pairs
            and ('red_army', '北京') in badge_pairs
            and ('hong_kong', '香港城') not in badge_pairs
            and all(badge['text'] == '🏕' for badge in base_badges),
            base_badges,
        )
        map_frame.locator('#focusAsia').click()
        page.wait_for_timeout(500)
        base_badge_visibility = map_frame.locator('.base-badge').evaluate_all(
            "nodes => nodes.map(node => { const r = node.getBoundingClientRect(); return {faction: node.dataset.baseFaction, town: node.dataset.baseTown, visible: r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight}; })"
        )
        record(
            'focus_asia_shows_all_participating_base_badges_in_viewport',
            len(base_badge_visibility) == len(occupied_after['players'])
            and all(item['visible'] for item in base_badge_visibility),
            base_badge_visibility,
        )
        OWN_ORG_BASE_MAP_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OWN_ORG_BASE_MAP_SCREENSHOT), full_page=True)

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
            str(OWN_ORG_BASE_MAP_SCREENSHOT.relative_to(ROOT)),
            str(END_TURN_DECISION_SCREENSHOT.relative_to(ROOT)),
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
