#!/usr/bin/env python3
"""Formal UI proof for accumulating heterogeneous card-build entitlements."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards' / 'build-entitlement-queue'
REPORT_JSON = RECORD_DIR / 'BUILD_ENTITLEMENT_QUEUE_UI_VALIDATION.json'
REPORT_MD = RECORD_DIR / 'BUILD_ENTITLEMENT_QUEUE_UI_VALIDATION.md'
COLLECT_SHOT = RECORD_DIR / 'build-queue-collecting.png'
MAP_SHOT = RECORD_DIR / 'build-queue-three-remaining.png'
FINAL_SHOT = RECORD_DIR / 'build-queue-resolved.png'
PROMOTER_COLLECT_SHOT = RECORD_DIR / 'duplicate-propagandists-collecting.png'
PROMOTER_MAP_SHOT = RECORD_DIR / 'duplicate-propagandists-map.png'
DISSOLVE_COLLECT_SHOT = RECORD_DIR / 'duplicate-dissolve-cards-collecting.png'
DISSOLVE_MAP_SHOT = RECORD_DIR / 'duplicate-dissolve-cards-map.png'
SUPPORT_COLLECT_SHOT = RECORD_DIR / 'support-map-cards-collecting.png'
SUPPORT_MAP_SHOT = RECORD_DIR / 'support-map-cards-map.png'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
UUID_RE = re.compile(r'\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b', re.IGNORECASE)


def sanitize_proof(value):
    if isinstance(value, dict):
        return {
            key: ('[REDACTED]' if key in {'game_id', 'player_id', 'acting_player_id'} else sanitize_proof(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_proof(item) for item in value]
    if isinstance(value, str):
        return UUID_RE.sub('[REDACTED]', value)
    return value


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def browser_executable() -> str | None:
    configured = os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
    if configured and Path(configured).exists():
        return configured
    cache = Path.home() / 'Library/Caches/ms-playwright'
    patterns = [
        'chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell',
        'chromium_headless_shell-*/chrome-headless-shell-mac/headless_shell',
        'chromium-*/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium',
        'chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium',
    ]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(cache.glob(pattern))
    candidates = sorted((path for path in candidates if path.exists()), reverse=True)
    return str(candidates[0]) if candidates else None


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json('/test/setup-build-queue-proof', {})
    if not setup.get('success'):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    actor_initial = next(player for player in setup['state']['players'] if player['id'] == setup['player_id'])
    record(
        'fixture_has_two_different_build_cards',
        actor_initial['hand'] == ['組織經驗丙', '組織經驗乙'],
        actor_initial['hand'],
    )

    with sync_playwright() as playwright:
        launch_options: dict[str, object] = {'headless': True}
        executable = browser_executable()
        if executable:
            launch_options['executable_path'] = executable
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
        page = context.new_page()
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.on('pageerror', lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until='domcontentloaded',
        )
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.length === 2",
            arg=setup['player_id'],
            timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          document.getElementById('closeFactionActionModal')?.click();
          const modal = document.getElementById('factionActionModal');
          if (modal?.classList.contains('hidden')) modal.style.display = 'none';
          setActiveGameView('command');
        }""")

        first_button = page.locator(
            "button.hand-card-action-btn[data-card-name='組織經驗丙'][data-card-mode='action']"
        ).first
        first_button.wait_for(state='visible', timeout=10000)
        first_button.click()
        page.wait_for_function(
            """() => window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'
              && window.lastGameState.pending_choice.remaining_builds === 1
              && window.lastGameState.pending_choice.queueable_card_names?.includes('組織經驗乙')""",
            timeout=10000,
        )
        command_active = 'active' in (page.locator(".game-tab[data-view='command']").get_attribute('class') or '').split()
        second_button = page.locator(
            "button.hand-card-action-btn[data-card-name='組織經驗乙'][data-card-mode='action']"
        ).first
        record('first_build_card_keeps_formal_ui_in_command_center', command_active, command_active)
        record('second_build_card_action_remains_enabled', second_button.is_visible() and second_button.is_enabled(), {
            'visible': second_button.is_visible(), 'enabled': second_button.is_enabled(),
        })
        page.screenshot(path=str(COLLECT_SHOT), full_page=True)

        second_button.click()
        page.wait_for_function(
            """() => window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'
              && window.lastGameState.pending_choice.remaining_builds === 3
              && window.lastGameState.pending_choice.queueable_card_names?.length === 0""",
            timeout=10000,
        )
        page.wait_for_function(
            "document.querySelector(\".game-tab[data-view='map']\")?.classList.contains('active')",
            timeout=10000,
        )
        frame = page.frame_locator('#strategicMapFrame')
        frame.locator('#map').wait_for(state='visible', timeout=15000)
        page.wait_for_timeout(300)
        map_hint = frame.locator('#interactionHint')
        map_hint.wait_for(state='visible', timeout=10000)
        hint_text = map_hint.inner_text()
        record(
            'formal_leaflet_map_shows_three_remaining_builds',
            '尚可建立組織：3 個' in hint_text and '可建立城鎮' in hint_text,
            hint_text,
        )
        frame.locator('#interactionHint').evaluate("(element) => element.scrollIntoView({block: 'start'})")
        page.wait_for_timeout(100)
        page.locator('#strategicMapFrame').screenshot(path=str(MAP_SHOT))

        built_towns: list[str] = []
        remaining_sequence: list[int] = []
        for expected_remaining in (2, 1, 0):
            state = page.evaluate('window.lastGameState')
            pending = state.get('pending_choice') or {}
            town = pending['towns'][0]['town']
            built_towns.append(town)
            map_frame = page.frames[-1]
            selected = map_frame.evaluate(
                """town => {
                  const candidate = byName.get(town);
                  if (!candidate) return {ok: false, reason: 'town-not-on-map'};
                  return selectTownForCurrentMapAction(town, {autoFocus: true}) || {ok: true};
                }""",
                town,
            )
            if isinstance(selected, dict) and selected.get('ok') is False:
                raise AssertionError({'town': town, 'selection': selected})
            build_button = frame.locator('#directBuildBtn')
            page.wait_for_function(
                """() => {
                  const frame = document.getElementById('strategicMapFrame');
                  const button = frame?.contentDocument?.getElementById('directBuildBtn');
                  return button && !button.disabled && button.textContent.includes('效果');
                }""",
                timeout=10000,
            )
            build_button.click()
            if expected_remaining:
                page.wait_for_function(
                    "expected => window.lastGameState?.pending_choice?.remaining_builds === expected",
                    arg=expected_remaining,
                    timeout=10000,
                )
            else:
                page.wait_for_function("() => !window.lastGameState?.pending_choice", timeout=10000)
            remaining_sequence.append(expected_remaining)
            page.wait_for_timeout(200)

        final_state = page.evaluate('window.lastGameState')
        actor = next(player for player in final_state['players'] if player['id'] == setup['player_id'])
        record('three_builds_resolve_through_leaflet_selection_and_visible_build_button', len(set(built_towns)) == 3, built_towns)
        record('remaining_builds_decrements_three_two_one_zero', remaining_sequence == [2, 1, 0], remaining_sequence)
        record(
            'authoritative_state_has_base_plus_three_new_organizations',
            len(actor['orgs']) == 4 and all(actor['orgs'].get(town) == 1 for town in built_towns),
            actor['orgs'],
        )
        record(
            'both_cards_commit_to_discard_and_queue_clears',
            actor['hand'] == []
            and actor['discard_pile'] == ['組織經驗丙', '組織經驗乙']
            and final_state.get('pending_choice') is None,
            {'hand': actor['hand'], 'discard': actor['discard_pile'], 'pending': final_state.get('pending_choice')},
        )
        page.evaluate("""() => {
          document.getElementById('closeFactionActionModal')?.click();
          const modal = document.getElementById('factionActionModal');
          if (modal) {
            modal.classList.add('hidden');
            modal.style.display = 'none';
          }
        }""")
        page.locator(".game-tab[data-view='log']").click()
        page.locator('#logView').wait_for(state='visible', timeout=5000)
        log_text = page.locator('#logViewContent').inner_text()
        record(
            'formal_log_records_each_card_build',
            log_text.count('built organization') >= 3
            and '組織經驗丙' in log_text
            and '組織經驗乙' in log_text,
            log_text,
        )
        page.screenshot(path=str(FINAL_SHOT), full_page=True)

        promoter_setup = post_json('/test/setup-build-queue-proof', {'cards': ['宣傳家', '宣傳家']})
        page.goto(
            f"{BASE_URL}/?game_id={promoter_setup['game_id']}&player_id={promoter_setup['player_id']}",
            wait_until='domcontentloaded',
        )
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.length === 2",
            arg=promoter_setup['player_id'], timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          setActiveGameView('command');
        }""")
        page.wait_for_timeout(700)
        page.evaluate("() => typeof closeEventReveal === 'function' && closeEventReveal()")
        promoter_button = page.locator(
            "button.hand-card-action-btn[data-card-name='宣傳家'][data-card-mode='action']"
        ).first
        promoter_button.click()
        page.wait_for_function(
            """() => window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'
              && window.lastGameState.pending_choice.queueable_card_names?.includes('宣傳家')""",
            timeout=10000,
        )
        promoter_command_active = 'active' in (page.locator(".game-tab[data-view='command']").get_attribute('class') or '').split()
        second_promoter = page.locator(
            "button.hand-card-action-btn[data-card-name='宣傳家'][data-card-mode='action']"
        ).first
        record('first_propagandist_keeps_command_center_active', promoter_command_active, promoter_command_active)
        record('second_propagandist_action_remains_enabled', second_promoter.is_visible() and second_promoter.is_enabled(), {
            'visible': second_promoter.is_visible(), 'enabled': second_promoter.is_enabled(),
        })
        page.screenshot(path=str(PROMOTER_COLLECT_SHOT), full_page=True)
        second_promoter.click()
        page.wait_for_function(
            """() => window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'
              && window.lastGameState.pending_choice.queueable_card_names?.length === 0""",
            timeout=10000,
        )
        page.wait_for_function(
            "document.querySelector(\".game-tab[data-view='map']\")?.classList.contains('active')",
            timeout=10000,
        )
        record('duplicate_propagandists_switch_to_map_only_after_all_actions', True, None)
        page.screenshot(path=str(PROMOTER_MAP_SHOT), full_page=True)

        dissolve_setup = post_json('/test/setup-build-queue-proof', {
            'cards': ['內應間諜', '內應間諜'],
            'organizations': {'香港城': 1},
            'enemy_organizations': {'北京': 1, '澳門': 1, '赤柱': 1},
        })
        page.goto(
            f"{BASE_URL}/?game_id={dissolve_setup['game_id']}&player_id={dissolve_setup['player_id']}",
            wait_until='domcontentloaded',
        )
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.length === 2",
            arg=dissolve_setup['player_id'], timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          setActiveGameView('command');
        }""")
        page.wait_for_timeout(700)
        page.evaluate("() => typeof closeEventReveal === 'function' && closeEventReveal()")
        spy_button = page.locator(
            "button.hand-card-action-btn[data-card-name='內應間諜'][data-card-mode='action']"
        ).first
        spy_button.click()
        page.wait_for_function(
            """() => window.lastGameState?.pending_choice?.interaction_kind === 'dissolve_organization'
              && window.lastGameState.pending_choice.queueable_card_names?.includes('內應間諜')""",
            timeout=10000,
        )
        dissolve_command_active = 'active' in (page.locator(".game-tab[data-view='command']").get_attribute('class') or '').split()
        second_spy = page.locator(
            "button.hand-card-action-btn[data-card-name='內應間諜'][data-card-mode='action']"
        ).first
        record('first_dissolve_card_keeps_command_center_active', dissolve_command_active, dissolve_command_active)
        record('second_dissolve_card_action_remains_enabled', second_spy.is_visible() and second_spy.is_enabled(), {
            'visible': second_spy.is_visible(), 'enabled': second_spy.is_enabled(),
        })
        page.screenshot(path=str(DISSOLVE_COLLECT_SHOT), full_page=True)
        second_spy.click()
        page.wait_for_function(
            """() => window.lastGameState?.pending_choice?.interaction_kind === 'dissolve_organization'
              && window.lastGameState.pending_choice.queueable_card_names?.length === 0""",
            timeout=10000,
        )
        page.wait_for_function(
            "document.querySelector(\".game-tab[data-view='map']\")?.classList.contains('active')",
            timeout=10000,
        )
        record('duplicate_dissolve_cards_switch_to_map_only_after_all_actions', True, None)
        page.screenshot(path=str(DISSOLVE_MAP_SHOT), full_page=True)

        support_setup = post_json('/test/setup-build-queue-proof', {
            'cards': ['內應間諜', '東洋奧援', '北國奧援', '臺灣奧援'],
            'organizations': {'北京': 1, '廣州': 1},
            'enemy_organizations': {'天津': 1, '深圳': 1},
            'support_tiers': {'東洋奧援': 3, '北國奧援': 3, '臺灣奧援': 3},
        })
        page.goto(
            f"{BASE_URL}/?game_id={support_setup['game_id']}&player_id={support_setup['player_id']}",
            wait_until='domcontentloaded',
        )
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.length === 4",
            arg=support_setup['player_id'], timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          setActiveGameView('command');
        }""")
        page.wait_for_timeout(700)
        page.evaluate("() => typeof closeEventReveal === 'function' && closeEventReveal()")
        page.locator("button.hand-card-action-btn[data-card-name='內應間諜'][data-card-mode='action']").click()
        page.wait_for_function(
            """() => ['東洋奧援', '北國奧援', '臺灣奧援'].every(
              name => window.lastGameState?.pending_choice?.queueable_card_names?.includes(name)
            )""",
            timeout=10000,
        )
        support_buttons = {
            name: page.locator(f"button.hand-card-action-btn[data-card-name='{name}'][data-card-mode='action']")
            for name in ('東洋奧援', '北國奧援', '臺灣奧援')
        }
        record(
            'all_three_map_support_actions_remain_enabled',
            all(button.is_visible() and button.is_enabled() for button in support_buttons.values()),
            {name: {'visible': button.is_visible(), 'enabled': button.is_enabled()} for name, button in support_buttons.items()},
        )
        support_buttons['東洋奧援'].click()
        page.wait_for_function(
            "() => !window.lastGameState?.pending_choice?.queueable_card_names?.includes('東洋奧援')",
            timeout=10000,
        )
        page.locator("button.hand-card-action-btn[data-card-name='北國奧援'][data-card-mode='action']").click()
        page.wait_for_function(
            "() => !window.lastGameState?.pending_choice?.queueable_card_names?.includes('北國奧援')",
            timeout=10000,
        )
        page.screenshot(path=str(SUPPORT_COLLECT_SHOT), full_page=True)
        page.locator("button.hand-card-action-btn[data-card-name='臺灣奧援'][data-card-mode='action']").click()
        page.wait_for_function(
            "() => window.lastGameState?.pending_choice?.queueable_card_names?.length === 0",
            timeout=10000,
        )
        page.wait_for_function(
            "document.querySelector(\".game-tab[data-view='map']\")?.classList.contains('active')",
            timeout=10000,
        )
        final_support_state = page.evaluate('() => window.lastGameState.pending_choice')
        record(
            'east_north_taiwan_supports_queue_before_map_switch',
            final_support_state.get('interaction_kind') == 'dissolve_organization'
            and final_support_state.get('queueable_card_names') == [],
            final_support_state,
        )
        page.screenshot(path=str(SUPPORT_MAP_SHOT), full_page=True)
        context.close()
        browser.close()

    record('browser_console_has_no_errors', not console_errors, console_errors)
    passed = sum(1 for check in checks if check['ok'])
    payload = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'base_url': BASE_URL,
        'status': 'passed' if passed == len(checks) else 'failed',
        'checks_passed': passed,
        'checks_total': len(checks),
        'checks': checks,
        'console_errors': console_errors,
        'screenshots': [
            str(COLLECT_SHOT.relative_to(ROOT)),
            str(MAP_SHOT.relative_to(ROOT)),
            str(FINAL_SHOT.relative_to(ROOT)),
            str(PROMOTER_COLLECT_SHOT.relative_to(ROOT)),
            str(PROMOTER_MAP_SHOT.relative_to(ROOT)),
            str(DISSOLVE_COLLECT_SHOT.relative_to(ROOT)),
            str(DISSOLVE_MAP_SHOT.relative_to(ROOT)),
            str(SUPPORT_COLLECT_SHOT.relative_to(ROOT)),
            str(SUPPORT_MAP_SHOT.relative_to(ROOT)),
        ],
    }
    payload = sanitize_proof(payload)
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 多張建立牌累積結算 UI Validation', '',
        f"- 結果：**{passed}/{len(checks)} passed**",
        '- 正式流程：先在指揮中心依序打出組織經驗丙、組織經驗乙，再由正式Leaflet地圖連續建立3次。',
        '- 驗證：第二張按鈕在首張pending期間仍可用；剩餘數1→3→2→1→0；每次重新投影合法城鎮。', '',
        '## Checks',
    ]
    lines.extend(f"- {'PASS' if check['ok'] else 'FAIL'} `{check['name']}`" for check in checks)
    lines.extend([
        '', '## Screenshots',
        f'- `{COLLECT_SHOT.relative_to(ROOT)}`',
        f'- `{MAP_SHOT.relative_to(ROOT)}`',
        f'- `{FINAL_SHOT.relative_to(ROOT)}`',
        f'- `{PROMOTER_COLLECT_SHOT.relative_to(ROOT)}`',
        f'- `{PROMOTER_MAP_SHOT.relative_to(ROOT)}`',
        f'- `{DISSOLVE_COLLECT_SHOT.relative_to(ROOT)}`',
        f'- `{DISSOLVE_MAP_SHOT.relative_to(ROOT)}`',
        f'- `{SUPPORT_COLLECT_SHOT.relative_to(ROOT)}`',
        f'- `{SUPPORT_MAP_SHOT.relative_to(ROOT)}`', '',
    ])
    REPORT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': passed, 'checks_total': len(checks)}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
