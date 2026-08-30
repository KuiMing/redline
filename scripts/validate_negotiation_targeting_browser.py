#!/usr/bin/env python3
"""Formal four-player UI proof for 合作談判 targeting an enemy."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'shared-actions'
REPORT_JSON = RECORD_DIR / 'NEGOTIATION_ENEMY_TARGET_UI_VALIDATION.json'
REPORT_MD = RECORD_DIR / 'NEGOTIATION_ENEMY_TARGET_UI_VALIDATION.md'
CHOICE_SHOT = RECORD_DIR / 'negotiation-enemy-target-choice.png'
RESULT_SHOT = RECORD_DIR / 'negotiation-enemy-target-result.png'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


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
    setup = post_json('/test/setup-negotiation-proof', {})
    if not setup.get('success'):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

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
            "() => window.lastGameState?.players?.find(player => player.name === 'Actor')?.hand?.includes('合作談判')",
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

        action_button = page.locator(
            "button.hand-card-action-btn[data-card-name='合作談判'][data-card-mode='action']"
        ).first
        action_button.wait_for(state='visible', timeout=10000)
        record('negotiation_action_button_is_available', action_button.is_enabled(), action_button.is_enabled())
        action_button.click()

        modal = page.locator('#factionActionModal')
        modal.wait_for(state='visible', timeout=10000)
        title = page.locator('#factionActionModalTitle').inner_text()
        hint = page.locator('#factionActionModalRewardHint').inner_text()
        buttons = page.locator('#factionActionModalChoices .modal-choice-btn')
        candidate_names = buttons.all_inner_texts()
        record('formal_target_modal_is_for_negotiation', title == '合作談判' and '各抽 1 張牌' in hint, {
            'title': title, 'hint': hint,
        })
        record('all_three_other_players_are_candidates', candidate_names == ['Ally', 'Enemy', 'Observer'], candidate_names)
        record('actor_is_not_a_candidate', 'Actor' not in candidate_names, candidate_names)
        page.screenshot(path=str(CHOICE_SHOT), full_page=True)

        enemy_button = page.locator('#factionActionModalChoices .modal-choice-btn', has_text='Enemy')
        record('enemy_candidate_is_visible_and_enabled', enemy_button.is_visible() and enemy_button.is_enabled(), {
            'visible': enemy_button.is_visible(), 'enabled': enemy_button.is_enabled(),
        })
        enemy_button.click()
        page.wait_for_function(
            """() => {
              const players = window.lastGameState?.players || [];
              const actor = players.find(player => player.name === 'Actor');
              const enemy = players.find(player => player.name === 'Enemy');
              return actor?.hand?.includes('ActorDraw')
                && actor?.resources?.propaganda === 2
                && enemy?.hand?.length === 1
                && !window.lastGameState?.pending_choice;
            }""",
            timeout=10000,
        )

        state = page.evaluate('window.lastGameState')
        players = {player['name']: player for player in state['players']}
        actor = players['Actor']
        enemy = players['Enemy']
        ally = players['Ally']
        observer = players['Observer']
        record('actor_and_enemy_each_draw_exactly_one', actor['hand'] == ['ActorDraw'] and len(enemy['hand']) == 1, {
            'actor_hand': actor['hand'], 'enemy_hand': enemy['hand'],
        })
        record('ally_and_observer_do_not_draw', len(ally['hand']) == 0 and len(observer['hand']) == 0, {
            'ally_hand': ally['hand'], 'observer_hand': observer['hand'],
        })
        record('actor_gains_two_propaganda_only', actor['resources']['propaganda'] == 2 and enemy['resources']['propaganda'] == 0, {
            'actor_resources': actor['resources'], 'enemy_resources': enemy['resources'],
        })
        record('negotiation_commits_to_discard_and_clears_pending', actor['discard_pile'] == ['合作談判'] and state.get('pending_choice') is None, {
            'discard': actor['discard_pile'], 'pending': state.get('pending_choice'),
        })

        page.evaluate("""() => {
          document.getElementById('closeFactionActionModal')?.click();
          const modal = document.getElementById('factionActionModal');
          if (modal) { modal.classList.add('hidden'); modal.style.display = 'none'; }
        }""")
        page.locator(".game-tab[data-view='log']").click()
        page.locator('#logView').wait_for(state='visible', timeout=5000)
        log_text = page.locator('#logViewContent').inner_text()
        record(
            'formal_traditional_chinese_log_names_actor_enemy_and_negotiation',
            'Actor 與 Enemy 因合作談判各抽了 1 張牌' in log_text,
            log_text,
        )
        page.screenshot(path=str(RESULT_SHOT), full_page=True)
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
        'screenshots': [str(CHOICE_SHOT.relative_to(ROOT)), str(RESULT_SHOT.relative_to(ROOT))],
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 合作談判敵對玩家正式UI驗證', '',
        f"- 結果：**{passed}/{len(checks)} passed**",
        '- 四人正式UI：候選包含 Ally、Enemy、Observer，不包含行動者自己。',
        '- 實際指定 Enemy：Actor與Enemy各抽1張，其他兩人不抽；Actor獲得2宣傳。', '',
        '## Checks',
    ]
    lines.extend(f"- {'PASS' if check['ok'] else 'FAIL'} `{check['name']}`" for check in checks)
    lines.extend(['', '## Screenshots', f'- `{CHOICE_SHOT.relative_to(ROOT)}`', f'- `{RESULT_SHOT.relative_to(ROOT)}`', ''])
    REPORT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': passed, 'checks_total': len(checks)}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
