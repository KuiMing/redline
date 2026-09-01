#!/usr/bin/env python3
"""Browser proof: 宣傳家立即切到地圖並聚焦合法建立範圍。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards' / 'propagandist-build-focus'
REPORT = RECORD_DIR / 'PROPAGANDIST_BUILD_FOCUS_BROWSER_VALIDATION.json'
SCREENSHOT = RECORD_DIR / 'propagandist-build-focus.png'


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json('/test/setup-build-queue-proof', {
        'cards': ['宣傳家', '組織經驗丙'],
        'base': '香港城',
        'organizations': {'香港城': 1},
    })
    if not setup.get('success'):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({'name': name, 'passed': bool(ok), 'detail': detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
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
          setActiveGameView('command');
        }""")

        action = page.locator(
            "button.hand-card-action-btn[data-card-name='宣傳家'][data-card-mode='action']"
        ).first
        action.wait_for(state='visible', timeout=10000)
        action.click()
        page.wait_for_function(
            """() => window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'
              && window.lastGameState.pending_choice.source_name === '宣傳家'
              && window.lastGameState.pending_choice.queueable_card_names?.includes('組織經驗丙')""",
            timeout=10000,
        )
        page.wait_for_function(
            "document.querySelector(\".game-tab[data-view='map']\")?.classList.contains('active')",
            timeout=10000,
        )
        record(
            'propagandist_switches_directly_from_command_center_to_map',
            'active' in (page.locator(".game-tab[data-view='map']").get_attribute('class') or '').split(),
        )

        frame_locator = page.frame_locator('#strategicMapFrame')
        frame_locator.locator('#map').wait_for(state='visible', timeout=15000)
        frame_locator.locator('#interactionHint').wait_for(state='visible', timeout=10000)
        map_frame = page.frames[-1]
        map_frame.wait_for_function(
            """() => supportChoiceHighlight?.sourceName === '宣傳家'
              && map?.getZoom() >= 8""",
            timeout=10000,
        )
        focus = map_frame.evaluate("""() => {
          const candidates = (supportChoiceHighlight?.towns || []).map(entry => entry.town);
          const center = map.getCenter();
          const target = candidates.length === 1 ? byName.get(candidates[0]) : null;
          return {
            candidates,
            zoom: map.getZoom(),
            center: {lat: center.lat, lon: center.lng},
            target: target ? {lat: target.lat, lon: target.lon} : null,
            hint: document.getElementById('interactionHint')?.textContent || '',
          };
        }""")
        centered = bool(
            focus['target']
            and abs(focus['center']['lat'] - focus['target']['lat']) < 0.001
            and abs(focus['center']['lon'] - focus['target']['lon']) < 0.001
        )
        record(
            'map_focuses_the_actual_legal_build_range',
            focus['zoom'] >= 8 and centered,
            focus,
        )
        record(
            'map_explains_propagandist_build_candidates',
            '宣傳家' in focus['hint'] and '可建立城鎮' in focus['hint'],
            focus['hint'],
        )

        page.screenshot(path=str(SCREENSHOT), full_page=True)

        page.locator(".game-tab[data-view='command']").click()
        queued_action = page.locator(
            "button.hand-card-action-btn[data-card-name='組織經驗丙'][data-card-mode='action']"
        ).first
        record(
            'build_card_queue_remains_available_after_auto_focus',
            queued_action.is_visible() and queued_action.is_enabled(),
            {'visible': queued_action.is_visible(), 'enabled': queued_action.is_enabled()},
        )

        # 重現使用者的「新遊戲第一次開地圖」時序：choice 先抵達，/map-data 與座標資料
        # 晚 700ms 才完成。舊版會先把 choice 標成已聚焦，資料到齊後又被 focusAsia 沖回
        # 亞洲全圖。這個獨立頁面證明初始化完成後會重試並停在合法城鎮。
        race_page = context.new_page()
        race_page.add_init_script("""() => {
          const nativeFetch = window.fetch.bind(window);
          window.fetch = (input, init) => {
            const url = String(input || '');
            if (url.includes('/map-data') || url.includes('/map-geo-coordinates')) {
              return new Promise((resolve, reject) => {
                setTimeout(() => nativeFetch(input, init).then(resolve, reject), 700);
              });
            }
            return nativeFetch(input, init);
          };
        }""")
        race_page.goto(
            f"{BASE_URL}/static/leaflet_game_map.html?v=propagandist-focus-race-proof",
            wait_until='domcontentloaded',
        )
        race_page.evaluate("""() => window.postMessage({
          type: 'redline-choice-highlight',
          payload: {
            mode: 'support-targets',
            actionKind: 'build',
            choiceKey: 'card_build_organization',
            sourceName: '宣傳家',
            prompt: '宣傳家：選擇要建立組織的城鎮。',
            towns: [{town: '澳門', label: '澳門', index: 0}],
          },
        }, window.location.origin)""")
        race_page.wait_for_function("() => window.__redlineMapDataReady != null", timeout=5000)
        race_page.evaluate("() => window.__redlineMapDataReady")
        race_page.wait_for_timeout(350)
        race_focus = race_page.evaluate("""() => {
          const center = map.getCenter();
          const target = byName.get('澳門');
          return {
            zoom: map.getZoom(),
            center: {lat: center.lat, lon: center.lng},
            target: target ? {lat: target.lat, lon: target.lon} : null,
            sourceName: supportChoiceHighlight?.sourceName || null,
          };
        }""")
        race_centered = bool(
            race_focus['target']
            and abs(race_focus['center']['lat'] - race_focus['target']['lat']) < 0.001
            and abs(race_focus['center']['lon'] - race_focus['target']['lon']) < 0.001
        )
        record(
            'first_map_load_retries_focus_after_delayed_map_data',
            race_focus['zoom'] >= 8 and race_centered and race_focus['sourceName'] == '宣傳家',
            race_focus,
        )
        race_page.close()

        record('browser_console_has_no_errors', not console_errors, console_errors)
        context.close()
        browser.close()

    passed = sum(1 for check in checks if check['passed'])
    payload = {
        'status': 'passed' if passed == len(checks) else 'failed',
        'checks_passed': passed,
        'checks_total': len(checks),
        'base_url': BASE_URL,
        'screenshot': str(SCREENSHOT.relative_to(ROOT)),
        'checks': checks,
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if payload['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
