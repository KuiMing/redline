#!/usr/bin/env python3
"""Formal UI proof: Taiwan support counts for 東突厥集中營 before pending target resolution."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'event-cards' / 'support-event-progress'
REPORT_JSON = RECORD_DIR / 'SUPPORT_EVENT_PROGRESS_UI_VALIDATION.json'
REPORT_MD = RECORD_DIR / 'SUPPORT_EVENT_PROGRESS_UI_VALIDATION.md'
PENDING_SHOT = RECORD_DIR / 'taiwan-support-event-progress-pending.png'
EVENT_SHOT = RECORD_DIR / 'east-turkestan-event-success.png'
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
    setup = post_json('/test/setup-taiwan-support-proof', {
        'support_name': '臺灣奧援',
        'tier': 2,
        'event_name': '東突厥集中營',
        'player_name': '見證者',
        'enemy_name': '紅軍',
    })
    if not setup.get('success'):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    initial = setup['state']
    initial_event = initial.get('current_event') or {}
    record(
        'fixture_uses_canonical_east_turkestan_mission',
        initial_event.get('name') == '東突厥集中營'
        and initial_event.get('trigger', {}).get('type') == 'play_card_with_propaganda',
        initial_event,
    )
    record(
        'fixture_starts_with_zero_event_progress',
        initial_event.get('progress', {}).get('count') == 0
        and initial_event.get('progress', {}).get('required') == 1,
        initial_event.get('progress'),
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
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.includes('臺灣奧援')",
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
        action_button = page.locator(
            "button.hand-card-action-btn[data-card-name='臺灣奧援'][data-card-mode='action']"
        ).first
        action_button.wait_for(state='visible', timeout=10000)
        action_button.click()

        page.wait_for_function(
            """(id) => {
              const state = window.lastGameState;
              const event = state?.current_event;
              const player = state?.players?.find(entry => entry.id === id);
              return event?.name === '東突厥集中營'
                && event?.progress?.count === 1
                && event?.progress?.succeeded === true
                && state?.pending_choice?.choice_key === 'support_interaction'
                && player?.hand?.length === 0
                && player?.discard_pile?.includes('臺灣奧援');
            }""",
            arg=setup['player_id'],
            timeout=15000,
        )
        state = page.evaluate('window.lastGameState')
        event = state['current_event']
        pending = state['pending_choice']
        actor = next(player for player in state['players'] if player['id'] == setup['player_id'])
        record(
            'formal_hand_action_commits_taiwan_support_before_target_resolution',
            pending.get('choice_key') == 'support_interaction'
            and pending.get('source_name') == '臺灣奧援'
            and actor.get('hand') == []
            and '臺灣奧援' in actor.get('discard_pile', []),
            {'pending_choice': pending, 'hand': actor.get('hand'), 'discard': actor.get('discard_pile')},
        )
        record(
            'authoritative_event_progress_is_success_while_support_target_is_pending',
            event.get('progress', {}).get('count') == 1
            and event.get('progress', {}).get('required') == 1
            and event.get('progress', {}).get('succeeded') is True
            and event.get('progress', {}).get('status') == 'success_pending',
            event.get('progress'),
        )

        page.wait_for_function(
            "document.querySelector('#choiceModal') && getComputedStyle(document.querySelector('#choiceModal')).display !== 'none'"
        )
        choice_text = page.locator('#choiceModal').inner_text()
        pinned_panel = page.locator('#eventCardPanel')
        pinned_text = page.locator('#eventCardContent').inner_text()
        pinned_label = pinned_panel.get_attribute('aria-label') or ''
        record(
            'formal_ui_shows_taiwan_support_pending_choice',
            '臺灣奧援' in choice_text and ('瓦解' in choice_text or '選擇' in choice_text),
            choice_text,
        )
        record(
            'formal_pinned_event_ui_shows_completed_progress',
            '東突厥集中營' in pinned_label and ('1/1' in pinned_text or '任務成功' in pinned_text),
            {'aria_label': pinned_label, 'visible_text': pinned_text},
        )
        page.screenshot(path=str(PENDING_SHOT), full_page=True)

        page.evaluate("""() => {
          const choice = document.getElementById('choiceModal');
          if (choice) choice.style.display = 'none';
          openCurrentEventReveal();
        }""")
        page.locator('#eventRevealModal').wait_for(state='visible', timeout=5000)
        reveal_text = page.locator('#eventRevealCard').inner_text()
        image = page.locator('#eventRevealCard img[alt="東突厥集中營完整卡面"]')
        image.wait_for(state='visible', timeout=10000)
        page.wait_for_function(
            """() => {
              const image = document.querySelector('#eventRevealCard img[alt="東突厥集中營完整卡面"]');
              return image?.complete && image.naturalWidth > 0;
            }""",
            timeout=10000,
        )
        record(
            'formal_event_reveal_shows_success_and_one_of_one',
            ('1/1' in reveal_text or '任務成功' in reveal_text),
            reveal_text,
        )
        page.screenshot(path=str(EVENT_SHOT), full_page=True)
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
        'screenshots': [str(PENDING_SHOT.relative_to(ROOT)), str(EVENT_SHOT.relative_to(ROOT))],
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 東突厥集中營 × 臺灣奧援 UI Validation', '',
        f"- 結果：**{passed}/{len(checks)} passed**",
        '- 正式流程：從手牌按下臺灣奧援「使用行動」，在瓦解目標仍待選時檢查事件進度。',
        '- 預期：臺灣奧援印刷購買費用含 2 宣傳，因此事件進度立即達成 1/1。', '',
        '## Checks',
    ]
    lines.extend(f"- {'PASS' if check['ok'] else 'FAIL'} `{check['name']}`" for check in checks)
    lines.extend([
        '', '## Screenshots',
        f'- `{PENDING_SHOT.relative_to(ROOT)}`',
        f'- `{EVENT_SHOT.relative_to(ROOT)}`', '',
    ])
    REPORT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': passed, 'checks_total': len(checks)}, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
