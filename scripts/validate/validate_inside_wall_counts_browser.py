#!/usr/bin/env python3
"""Formal WebSocket/UI proof for canonical inside/outside-wall organization counts."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'era-cards' / 'inside-wall-counts'
REPORT_JSON = RECORD_DIR / 'INSIDE_WALL_COUNTS_UI_VALIDATION.json'
REPORT_MD = RECORD_DIR / 'INSIDE_WALL_COUNTS_UI_VALIDATION.md'
OUTSIDE_SHOT = RECORD_DIR / 'taiwan-eight-outside-not-achieved.png'
BOUNDARY_SHOT = RECORD_DIR / 'taiwan-seven-inside-achieved.png'
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
    scenarios = [
        {'name': 'eight_outside', 'inside': 0, 'outside': 8, 'expected_total': 8, 'expected_achieved': False, 'shot': OUTSIDE_SHOT},
        {'name': 'seven_inside_boundary', 'inside': 7, 'outside': 8, 'expected_total': 15, 'expected_achieved': True, 'shot': BOUNDARY_SHOT},
    ]
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

        for scenario in scenarios:
            setup = post_json('/test/setup-inside-wall-proof', {
                'inside_count': scenario['inside'],
                'outside_count': scenario['outside'],
            })
            if not setup.get('success'):
                raise RuntimeError(setup)
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
                "expected => window.lastGameState?.players?.find(player => player.name === 'Taiwan')?.organization_counts?.total === expected",
                arg=scenario['expected_total'],
                timeout=15000,
            )
            page.evaluate("""() => {
              if (typeof closeEventReveal === 'function') closeEventReveal();
              if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
              const modal = document.getElementById('factionActionModal');
              if (modal) { modal.classList.add('hidden'); modal.style.display = 'none'; }
            }""")

            state = page.evaluate('window.lastGameState')
            taiwan = next(player for player in state['players'] if player['name'] == 'Taiwan')
            counts = taiwan['organization_counts']
            stage = state['my_era_stage']
            prefix = scenario['name']
            record(f'{prefix}_server_projects_canonical_counts', counts == {
                'total': scenario['expected_total'],
                'inside_wall': scenario['inside'],
                'outside_wall': scenario['outside'],
            }, counts)
            record(f'{prefix}_counts_conserve_total', counts['inside_wall'] + counts['outside_wall'] == counts['total'], counts)
            record(f'{prefix}_era_achievement_matches_inside_count', stage['achieved'] is scenario['expected_achieved'], {
                'achieved': stage['achieved'], 'expected': scenario['expected_achieved'], 'trigger': stage.get('trigger_text'),
            })

            page.evaluate("""() => {
              if (typeof closeEventReveal === 'function') closeEventReveal();
              if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
              if (typeof closeEraAchievementModal === 'function') closeEraAchievementModal();
              for (const id of ['eventRevealModal', 'eraAchievementModal', 'factionActionModal']) {
                const modal = document.getElementById(id);
                if (modal) { modal.classList.add('hidden'); modal.style.display = 'none'; }
              }
            }""")
            page.locator(".game-tab[data-view='log']").click()
            page.locator('#logView').wait_for(state='visible', timeout=5000)
            taiwan_card = page.locator('.player-status-card', has=page.locator('.player-status-name', has_text='Taiwan'))
            taiwan_card.wait_for(state='visible', timeout=5000)
            card_text = taiwan_card.inner_text()
            expected_split = f"牆內 {scenario['inside']}／牆外 {scenario['outside']}"
            record(f'{prefix}_formal_player_status_shows_total', f"組織\n{scenario['expected_total']}" in card_text, card_text)
            record(f'{prefix}_formal_player_status_shows_inside_outside_split', expected_split in card_text, card_text)
            page.screenshot(path=str(scenario['shot']), full_page=True)
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
        'screenshots': [str(OUTSIDE_SHOT.relative_to(ROOT)), str(BOUNDARY_SHOT.relative_to(ROOT))],
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 臺灣時代關卡牆內／牆外正式UI驗證', '',
        f"- 結果：**{passed}/{len(checks)} passed**",
        '- 8個臺灣統治城鎮、0牆內：不得達成；玩家戰況顯示組織8、牆內0／牆外8。',
        '- 7個牆內、8個牆外：達成；玩家戰況顯示組織15、牆內7／牆外8。', '',
        '## Checks',
    ]
    lines.extend(f"- {'PASS' if check['ok'] else 'FAIL'} `{check['name']}`" for check in checks)
    lines.extend(['', '## Screenshots', f'- `{OUTSIDE_SHOT.relative_to(ROOT)}`', f'- `{BOUNDARY_SHOT.relative_to(ROOT)}`', ''])
    REPORT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': passed, 'checks_total': len(checks)}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
