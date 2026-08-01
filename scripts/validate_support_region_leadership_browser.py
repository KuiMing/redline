#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-region-leadership'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
REPORT_JSON = RECORD_DIR / 'SUPPORT_REGION_LEADERSHIP_UI_VALIDATION.json'
REPORT_MD = RECORD_DIR / 'SUPPORT_REGION_LEADERSHIP_UI_VALIDATION.md'
BEFORE_SHOT = RECORD_DIR / 'support-region-leadership-before.png'
AFTER_SHOT = RECORD_DIR / 'support-region-leadership-tier1-after.png'


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def browser_executable(playwright) -> str | None:
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
    candidates = []
    for pattern in patterns:
        candidates.extend(cache.glob(pattern))
    candidates = sorted((path for path in candidates if path.exists()), reverse=True)
    return str(candidates[0]) if candidates else None


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json('/test/setup-support-card-play', {
        'support_name': '英美奧援',
        'variant_index': 0,
        'faction_id': 'liberals',
        'base': '巴黎',
        'orgs': {'巴黎': 1},
        'enemy_faction_id': 'red_army',
        'enemy_base': '北京',
        'enemy_orgs': {'北京': 1, '日內瓦': 1, '慕尼黑': 1},
        'resources': {'money': 0, 'propaganda': 0},
    })

    checks: list[dict] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    actor_state = next(player for player in setup['state']['players'] if player['id'] == setup['player_id'])
    enemy_state = next(player for player in setup['state']['players'] if player['id'] != setup['player_id'])
    record('fixture_actor_has_one_europe_organization', actor_state['orgs'] == {'巴黎': 1}, actor_state['orgs'])
    record(
        'fixture_enemy_has_two_europe_organizations',
        enemy_state['orgs'].get('日內瓦') == 1 and enemy_state['orgs'].get('慕尼黑') == 1,
        enemy_state['orgs'],
    )
    record('authoritative_setup_downgrades_presence_to_tier_one', setup['support_tier'] == 1, setup['support_tier'])

    console_errors: list[str] = []
    with sync_playwright() as playwright:
        launch_options: dict[str, object] = {'headless': True}
        executable = browser_executable(playwright)
        if executable:
            launch_options['executable_path'] = executable
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(viewport={'width': 1280, 'height': 720}, device_scale_factor=1)
        page = context.new_page()
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.on('pageerror', lambda error: console_errors.append(str(error)))
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until='domcontentloaded')
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.includes('英美奧援')",
            arg=setup['player_id'],
            timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          document.getElementById('closeFactionActionModal')?.click();
          const actionModal = document.getElementById('factionActionModal');
          if (actionModal?.classList.contains('hidden')) actionModal.style.display = 'none';
        }""")
        command_tab = page.locator(".game-tab[data-view='command']")
        if 'active' not in (command_tab.get_attribute('class') or '').split():
            command_tab.click()
        card = page.locator('#hand .hand-card').filter(has=page.locator('img[alt="英美奧援完整卡面"]')).first
        card.wait_for(state='visible', timeout=10000)
        page.wait_for_function(
            """() => {
              const image = document.querySelector('#hand .hand-card img[alt="英美奧援完整卡面"]');
              return image?.complete && image.naturalWidth > 0;
            }""",
            timeout=10000,
        )
        face_evidence = card.evaluate("""element => {
          const image = element.querySelector('img[alt="英美奧援完整卡面"]');
          return {
            variantIndex: element.dataset.cardVariantIndex,
            imagePath: image ? decodeURIComponent(new URL(image.src).pathname) : '',
          };
        }""")
        record(
            'formal_card_face_uses_variant_zero_regions',
            face_evidence['variantIndex'] == '0' and face_evidence['imagePath'].endswith('/01_英美奧援_歐洲-天方.png'),
            face_evidence,
        )
        page.screenshot(path=str(BEFORE_SHOT), full_page=False)

        card.locator("[data-card-mode='action']").click()
        page.wait_for_function(
            """(id) => {
              const player = window.lastGameState?.players?.find(entry => entry.id === id);
              return player?.resources?.money === 1 && player?.hand?.length === 0;
            }""",
            arg=setup['player_id'],
            timeout=10000,
        )
        fresh = page.evaluate(
            "(id) => window.lastGameState.players.find(player => player.id === id)",
            arg=setup['player_id'],
        )
        record('formal_action_resolves_tier_one_money_gain', fresh['resources']['money'] == 1, fresh['resources'])
        record('support_card_moves_from_hand_to_discard', fresh['hand'] == [] and fresh['discard_pile'] == ['英美奧援'], {
            'hand': fresh['hand'], 'discard_pile': fresh['discard_pile'],
        })

        page.evaluate("""() => {
          document.getElementById('closeFactionActionModal')?.click();
          const actionModal = document.getElementById('factionActionModal');
          if (actionModal?.classList.contains('hidden')) actionModal.style.display = 'none';
        }""")
        page.locator(".game-tab[data-view='log']").click()
        page.locator('#logView').wait_for(state='visible', timeout=5000)
        log_text = page.locator('#logViewContent').inner_text()
        record('formal_action_log_records_tier_one', '英美奧援 at tier 1' in log_text, log_text)
        record('formal_action_log_does_not_claim_tier_two', '英美奧援 at tier 2' not in log_text, log_text)
        page.screenshot(path=str(AFTER_SHOT), full_page=False)
        context.close()
        browser.close()

    record('browser_console_has_no_errors', not console_errors, console_errors)
    passed = sum(1 for check in checks if check['ok'])
    payload = {
        'generated_at': datetime.now().astimezone().isoformat(),
        'base_url': BASE_URL,
        'status': 'passed' if passed == len(checks) else 'failed',
        'checks_passed': passed,
        'checks_total': len(checks),
        'checks': checks,
        'console_errors': console_errors,
        'screenshots': [str(BEFORE_SHOT), str(AFTER_SHOT)],
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 奧援卡區域最多組織門檻 UI Validation', '',
        f"- 結果：**{passed}/{len(checks)} passed**",
        f"- 正式端點：`{BASE_URL}`",
        '- Fixture：玩家巴黎 1；對手日內瓦＋慕尼黑 2；英美奧援 variant 0（II：歐洲／天方）。',
        '- 預期：玩家在歐洲有組織但不是最多，故只結算 I 級並獲得 1 資金。', '',
        '## Checks',
    ]
    for check in checks:
        lines.append(f"- {'PASS' if check['ok'] else 'FAIL'} `{check['name']}`")
    lines.extend(['', '## Screenshots', f'- `{BEFORE_SHOT.relative_to(ROOT)}`', f'- `{AFTER_SHOT.relative_to(ROOT)}`', ''])
    REPORT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': passed, 'checks_total': len(checks)}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
