#!/usr/bin/env python3
"""Formal UI proof for non-red base protection and per-turn Red Army base durability."""
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'base-dissolve'
JSON_OUT = RECORD_DIR / 'BASE_DISSOLVE_UI_VALIDATION.json'
MD_OUT = RECORD_DIR / 'BASE_DISSOLVE_UI_VALIDATION.md'
BEFORE_SHOT = RECORD_DIR / 'base-dissolve-legal-targets.png'
MAP_SHOT = RECORD_DIR / 'base-dissolve-map-targets.png'
CONTROLS_SHOT = RECORD_DIR / 'base-dissolve-disabled-controls.png'
AFTER_SHOT = RECORD_DIR / 'red-base-second-hit.png'
BASE_URL = 'http://127.0.0.1:8000'


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks = []
    console_errors = []

    def record(name, ok, detail):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100})
        page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
        page.on('pageerror', lambda exc: console_errors.append(str(exc)))

        setup = page.request.post(
            f'{BASE_URL}/test/setup-intel-network-proof',
            data={
                'viewer_faction': 'liberals',
                'viewer_base': '香港城',
                'viewer_organizations': {'承德': 1},
                'intel_card_count': 2,
                'enemy_a_faction': 'red_army',
                'enemy_a_base': '北京',
                'enemy_a_organizations': {'北京': 1},
                'enemy_b_faction': 'youyan',
                'enemy_b_base': '天津',
                'enemy_b_organizations': {'天津': 1, '朝陽': 1},
                'enemy_c_organizations': {},
            },
        ).json()
        game_id = setup['game_id']
        player_id = setup['player_id']
        page.goto(f'{BASE_URL}/?game_id={game_id}&player_id={player_id}', wait_until='networkidle')
        page.wait_for_function("window.lastGameState?.players?.[0]?.hand?.filter(name => name === '情報網').length === 2")
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          document.getElementById('closeFactionActionModal')?.click();
          for (const id of ['eventRevealModal', 'eraAchievementModal', 'factionActionModal']) {
            const el = document.getElementById(id);
            if (el?.classList.contains('hidden')) {
              el.style.display = 'none';
              el.style.pointerEvents = 'none';
            }
          }
        }""")

        def start_intel_dissolve():
            page.evaluate("""() => {
              const choiceModal = document.getElementById('choiceModal');
              if (choiceModal) choiceModal.style.pointerEvents = '';
              document.getElementById('closeFactionActionModal')?.click();
              const modal = document.getElementById('factionActionModal');
              if (modal?.classList.contains('hidden')) {
                modal.style.display = 'none';
                modal.style.pointerEvents = 'none';
              }
            }""")
            page.locator("button.hand-card-action-btn[data-card-name='情報網'][data-card-mode='action']").first.click()
            page.wait_for_function("window.lastGameState?.pending_choice?.choice_key === 'choose_one'")
            page.get_by_role('button', name='瓦解己方組織1格內的1個對手組織').click()
            page.wait_for_function("window.lastGameState?.pending_choice?.choice_key === 'intel_network_dissolve_target'")
            return page.evaluate("window.lastGameState.pending_choice")

        def open_map():
            # 瓦解 target 選擇（interaction_kind='dissolve_organization'）建立 pending choice
            # 後會自動隱藏 choice modal 並切到戰略地圖，不再需要（也點不到）手動關閉 modal
            # 或手動切分頁（2026-08-02：見 server/game.py 的 interaction_kind 統一與
            # app.js 的 isMapDissolveChoice 分支）。
            page.wait_for_function("document.querySelector('#choiceModal').style.display === 'none'")
            page.wait_for_function("document.querySelector('#mapView')?.classList.contains('active')")
            frame_el = page.locator('#strategicMapFrame')
            frame_el.wait_for(state='visible')
            frame_handle = frame_el.element_handle()
            frame = frame_handle.content_frame() if frame_handle else None
            assert frame is not None
            frame.wait_for_function("window.__redlinePlayableMap && window.__lastMapState?.pending_choice?.choice_key === 'intel_network_dissolve_target'")
            return frame

        pending_first = start_intel_dissolve()
        target_towns = sorted(entry.get('town') for entry in pending_first.get('targets', []) if entry.get('town'))
        record(
            'formal_pending_targets_exclude_non_red_base',
            target_towns == ['北京', '朝陽'],
            {'target_towns': target_towns, 'excluded_non_red_base': '天津'},
        )

        frame = open_map()
        candidate_info = frame.evaluate("""() => ({
          targetTowns: (window.__lastMapState.pending_choice.targets || []).map(entry => entry.town).sort(),
          highlightLayerCount: typeof supportChoiceHighlightLayer !== 'undefined' ? supportChoiceHighlightLayer.getLayers().length : null,
          hint: document.getElementById('interactionHint')?.innerText || ''
        })""")
        frame.evaluate("window.selectTownForCurrentMapAction('天津', {autoFocus: false})")
        frame.evaluate("""() => {
          const coords = GEO_COORDS['北京'];
          window.__redlinePlayableMap.setView([coords[1], coords[0]], 7, {animate: false});
        }""")
        # modal 在 open_map() 階段已自動隱藏，不需要再手動關閉。
        page.wait_for_function("getComputedStyle(document.querySelector('#choiceModal')).display === 'none'")
        non_red_base_disabled = frame.locator('#dissolveBtn').is_disabled()
        non_red_hint = frame.locator('#dissolveHint').inner_text()
        record(
            'formal_map_non_red_base_is_not_clickable_dissolve_target',
            non_red_base_disabled and candidate_info['targetTowns'] == ['北京', '朝陽'] and candidate_info['highlightLayerCount'] == 4,
            {'candidate_info': candidate_info, 'button_disabled': non_red_base_disabled, 'hint': non_red_hint},
        )
        record(
            'formal_map_proof_is_unobscured',
            page.evaluate("getComputedStyle(document.querySelector('#choiceModal')).display === 'none'"),
            {'choice_modal_display': page.evaluate("getComputedStyle(document.querySelector('#choiceModal')).display")},
        )
        frame.locator('#dissolveBtn').locator(
            'xpath=ancestor::div[contains(@class,"card")][1]'
        ).screenshot(path=str(CONTROLS_SHOT))
        frame.evaluate("""() => {
          const coords = GEO_COORDS['北京'];
          window.__redlinePlayableMap.setView([coords[1], coords[0]], 8, {animate: false});
        }""")
        frame.locator('#map').screenshot(path=str(MAP_SHOT))
        page.screenshot(path=str(BEFORE_SHOT), full_page=True)

        frame.evaluate("window.selectTownForCurrentMapAction('北京', {autoFocus: false})")
        record(
            'formal_map_red_base_is_clickable_dissolve_target',
            not frame.locator('#dissolveBtn').is_disabled(),
            {'selected_town': '北京', 'button_text': frame.locator('#dissolveBtn').inner_text()},
        )
        frame.locator('#dissolveBtn').click()
        page.wait_for_function("!window.lastGameState.pending_choice")
        first_state = page.evaluate("window.lastGameState")
        red_first = next(player for player in first_state['players'] if player['faction'] == 'red_army')
        record(
            'first_red_base_hit_keeps_physical_organization',
            red_first['orgs'].get('北京') == 1 and any('（1/2）' in line and '根據地組織仍保留' in line for line in first_state.get('action_log', [])),
            {'red_player': red_first, 'log_tail': first_state.get('action_log', [])[-6:]},
        )

        page.evaluate("setActiveGameView('command')")
        page.wait_for_function("document.querySelector('#commandView')?.classList.contains('active')")
        page.wait_for_function("window.lastGameState?.players?.[0]?.hand?.filter(name => name === '情報網').length === 1")
        page.locator("button.hand-card-action-btn[data-card-name='情報網'][data-card-mode='action']").first.wait_for(state='visible')
        pending_second = start_intel_dissolve()
        second_targets = sorted(entry.get('town') for entry in pending_second.get('targets', []) if entry.get('town'))
        record(
            'red_base_remains_targetable_for_second_hit',
            '北京' in second_targets and '天津' not in second_targets,
            {'target_towns': second_targets},
        )
        frame = open_map()
        frame.evaluate("window.selectTownForCurrentMapAction('北京', {autoFocus: false})")
        frame.locator('#dissolveBtn').click()
        page.wait_for_function("!window.lastGameState.pending_choice && window.lastGameState.red_army_base_build_blocks.includes('北京')")
        final_state = page.evaluate("window.lastGameState")
        red_final = next(player for player in final_state['players'] if player['faction'] == 'red_army')
        youyan_final = next(player for player in final_state['players'] if player['faction'] == 'youyan')
        record(
            'second_hit_removes_org_keeps_base_and_blocks_rebuild_this_turn',
            red_final['orgs'].get('北京', 0) == 0
            and red_final.get('base') == '北京'
            and final_state.get('red_army_base_build_blocks') == ['北京']
            and youyan_final['orgs'].get('天津') == 1,
            {
                'red_player': red_final,
                'youyan_player': youyan_final,
                'build_blocks': final_state.get('red_army_base_build_blocks'),
                'log_tail': final_state.get('action_log', [])[-8:],
            },
        )

        page.evaluate("""() => {
          document.getElementById('closeFactionActionModal')?.click();
          document.getElementById('closeChoiceModal')?.click();
          for (const id of ['factionActionModal', 'choiceModal', 'eventRevealModal', 'eraAchievementModal']) {
            const modal = document.getElementById(id);
            if (modal) {
              modal.style.display = 'none';
              modal.style.pointerEvents = 'none';
            }
          }
          setActiveGameView('log');
        }""")
        page.wait_for_function("document.querySelector('#logView')?.classList.contains('active')")
        page.wait_for_function("document.querySelector('#logViewContent')?.innerText.includes('紅軍本回合不能在該地建立組織')")
        log_text = page.locator('#logViewContent').inner_text()
        record(
            'formal_log_shows_second_hit_and_current_turn_build_block',
            '（2/2）' in log_text and '紅軍本回合不能在該地建立組織' in log_text,
            {'log_tail': log_text.splitlines()[-8:]},
        )
        page.wait_for_timeout(200)
        page.screenshot(path=str(AFTER_SHOT), full_page=True)
        record('browser_console_has_no_errors', not console_errors, {'console_errors': console_errors})
        browser.close()

    payload = {
        'status': 'passed' if all(item['ok'] for item in checks) else 'failed',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'base_url': BASE_URL,
        'checks_passed': sum(1 for item in checks if item['ok']),
        'checks_total': len(checks),
        'checks': checks,
        'console_errors': console_errors,
        'screenshots': [
            str(path.relative_to(ROOT))
            for path in (BEFORE_SHOT, MAP_SHOT, CONTROLS_SHOT, AFTER_SHOT)
        ],
    }
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# BASE DISSOLVE UI VALIDATION', '',
        f"- status: **{payload['status']}**",
        f"- checks: **{payload['checks_passed']}/{payload['checks_total']}**",
        f"- console errors: **{len(console_errors)}**", '',
    ]
    lines.extend(f"- {'PASS' if item['ok'] else 'FAIL'} {item['name']}: `{item['detail']}`" for item in checks)
    MD_OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': payload['checks_passed'], 'checks_total': payload['checks_total']}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
