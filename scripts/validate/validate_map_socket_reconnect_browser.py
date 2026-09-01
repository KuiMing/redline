#!/usr/bin/env python3
"""正式 UI proof：戰略地圖連線中斷後仍能用組織經驗丙在廈門建立組織。

2026-08-08 playtest 回報：打出組織經驗丙、在地圖上點選廈門，左側「在目前城鎮建立組織
（效果）」按鈕確實亮起，但按下去完全沒有建立組織、也沒有任何錯誤訊息。

根因是戰略地圖 iframe 那條 WebSocket 斷過一次之後永遠不會重連（父頁 app.js 自己有
scheduleReconnect，所以指揮中心看起來完全正常，選擇提示也照樣 postMessage 進地圖，
候選城鎮與按鈕都還亮著），而 sendDirectBuildAction() 在 socket 未開時只是靜默 return。

這支 proof 走完整瀏覽器流程：打出組織經驗丙 → 讓兩條 WebSocket 同時斷線（等同伺服器
重啟／睡眠喚醒／網路閃斷）→ 確認地圖自動重連 → 在地圖點選廈門 → 按建立組織按鈕 →
權威盤面確實在廈門長出組織。
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'map-ui' / 'socket-reconnect'
REPORT_JSON = RECORD_DIR / 'MAP_SOCKET_RECONNECT_VALIDATION.json'
REPORT_MD = RECORD_DIR / 'MAP_SOCKET_RECONNECT_VALIDATION.md'
ARMED_SHOT = RECORD_DIR / 'map-socket-reconnect-xiamen-armed.png'
BUILT_SHOT = RECORD_DIR / 'map-socket-reconnect-xiamen-built.png'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')

TARGET_TOWN = '廈門'


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
    setup = post_json('/test/setup-build-queue-proof', {
        'faction_id': 'min',
        'base': '福州',
        'organizations': {'福州': 1},
        'cards': ['組織經驗丙'],
    })
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
        context = browser.new_context(viewport={'width': 1600, 'height': 1100}, device_scale_factor=1)
        page = context.new_page()
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.on('pageerror', lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until='domcontentloaded',
        )
        page.locator('#gameShell').wait_for(state='visible', timeout=15000)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.length === 1",
            arg=setup['player_id'],
            timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          document.getElementById('closeFactionActionModal')?.click();
          const modal = document.getElementById('factionActionModal');
          if (modal) { modal.classList.add('hidden'); modal.style.display = 'none'; }
          setActiveGameView('command');
        }""")

        play_button = page.locator(
            "button.hand-card-action-btn[data-card-name='組織經驗丙'][data-card-mode='action']"
        ).first
        play_button.wait_for(state='visible', timeout=10000)
        play_button.click()
        page.wait_for_function(
            "() => window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'",
            timeout=10000,
        )
        candidates = [entry['town'] for entry in page.evaluate('window.lastGameState.pending_choice.towns')]
        record('xiamen_is_a_legal_card_build_candidate', TARGET_TOWN in candidates, candidates)

        page.wait_for_function(
            "document.querySelector(\".game-tab[data-view='map']\")?.classList.contains('active')",
            timeout=10000,
        )
        frame = page.frame_locator('#strategicMapFrame')
        frame.locator('#map').wait_for(state='visible', timeout=15000)
        page.wait_for_timeout(1000)

        # === 模擬連線中斷：父頁與地圖 iframe 的 WebSocket 同時被切斷 ===
        page.evaluate("() => { try { ws.close(); } catch (err) {} }")
        page.frames[-1].evaluate("() => { try { mapWs.close(); } catch (err) {} }")
        page.wait_for_timeout(500)
        map_frame = page.frames[-1]
        try:
            page.wait_for_function(
                "() => document.getElementById('strategicMapFrame')?.contentWindow?.mapWs?.readyState === 1",
                timeout=15000,
            )
        except PlaywrightTimeoutError:
            # 修好前地圖 socket 沒有 onclose／重連，會永遠停在 CLOSED(3)。
            pass
        map_socket_state = map_frame.evaluate('() => mapWs ? mapWs.readyState : null')
        record(
            'strategic_map_socket_reconnects_after_a_drop',
            map_socket_state == 1,
            {'readyState': map_socket_state, 'legend': '0=CONNECTING 1=OPEN 2=CLOSING 3=CLOSED, null=已被清成 null 且未重連'},
        )
        page.wait_for_timeout(500)

        # === 在正式 Leaflet 地圖上點選廈門 ===
        map_frame.evaluate("""(town) => {
          const entry = byName.get(town);
          const marker = currentMarkers.get(town);
          marker.fire('click', {latlng: L.latLng(entry.lat, entry.lon), sourceTarget: marker, propagatedFrom: marker});
        }""", TARGET_TOWN)
        page.wait_for_timeout(400)
        armed = map_frame.evaluate("""() => {
          const button = document.getElementById('directBuildBtn');
          return {
            selected: selectedTown,
            text: button.textContent,
            disabled: button.disabled,
            hint: document.getElementById('directBuildHint').textContent,
          };
        }""")
        record(
            'build_button_arms_for_xiamen_after_reconnect',
            armed['selected'] == TARGET_TOWN and not armed['disabled'] and '效果' in armed['text'],
            armed,
        )
        page.locator('#strategicMapFrame').screenshot(path=str(ARMED_SHOT))

        if not armed['disabled']:
            frame.locator('#directBuildBtn').click()
            try:
                page.wait_for_function("() => !window.lastGameState?.pending_choice", timeout=10000)
            except PlaywrightTimeoutError:
                # 修好前這裡就是使用者回報的症狀：按鈕亮著、按下去卻靜默失效。
                pass
        page.wait_for_timeout(500)

        final_state = page.evaluate('window.lastGameState')
        actor = next(player for player in final_state['players'] if player['id'] == setup['player_id'])
        record(
            'authoritative_state_shows_the_organization_in_xiamen',
            actor['orgs'].get(TARGET_TOWN) == 1,
            actor['orgs'],
        )
        record(
            'card_is_committed_to_discard_and_choice_clears',
            actor['hand'] == [] and final_state.get('pending_choice') is None,
            {'hand': actor['hand'], 'pending': final_state.get('pending_choice')},
        )
        map_state = map_frame.evaluate('() => window.lastGameState')
        map_actor = next(player for player in map_state['players'] if player['id'] == setup['player_id'])
        record(
            'reconnected_map_iframe_also_sees_the_new_organization',
            map_actor['orgs'].get(TARGET_TOWN) == 1,
            map_actor['orgs'],
        )
        page.screenshot(path=str(BUILT_SHOT), full_page=True)
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
            str(ARMED_SHOT.relative_to(ROOT)),
            str(BUILT_SHOT.relative_to(ROOT)),
        ],
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 戰略地圖連線中斷後重連 UI Validation', '',
        f"- 結果：**{passed}/{len(checks)} passed**",
        '- 情境：打出組織經驗丙 → 兩條 WebSocket 同時斷線 → 地圖自動重連 → 點選廈門 → 按建立組織。',
        '- 回歸重點：修好前地圖 socket 斷線後永不重連，按鈕仍亮著但按下去靜默失效。', '',
        '## Checks',
    ]
    lines.extend(f"- {'PASS' if check['ok'] else 'FAIL'} `{check['name']}`" for check in checks)
    lines.extend([
        '', '## Screenshots',
        f'- `{ARMED_SHOT.relative_to(ROOT)}`',
        f'- `{BUILT_SHOT.relative_to(ROOT)}`', '',
    ])
    REPORT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'status': payload['status'], 'checks_passed': passed, 'checks_total': len(checks)}, ensure_ascii=False))
    if payload['status'] != 'passed':
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
