#!/usr/bin/env python3
"""Formal UI proof for TODO P2「多張建立組織卡可累積後在地圖一次結算」的鏡頭保留規則
（2026-08-02 使用者回報：連續建立組織時，每成功建立一個就 zoom out 一次）。

規則：進入一段 `card_build_organization` 連續建立 session 時，第一次應該自動聚焦
（fitBounds／setView）；但同一個 session 內每次成功建立後，只應更新組織 marker、
合法候選與剩餘建立數，不能重新 fitBounds／setView 把玩家手動調整過的鏡頭沖掉。

根因與修法：`static/leaflet_game_map_logic.js` 的 `applySupportChoiceHighlight()` 用
`supportChoiceHighlightKey()` 判斷「這是不是同一個 session」來決定要不要重新聚焦；
舊版把 towns／prompt 也算進這把 key，而 `card_build_organization` 每次成功建立後
`prompt` 都會改成「尚可建立 N 個」、towns 也會重新投影，導致每次都被誤判成新
session、每次都重新聚焦。修法只保留 mode/actionKind/choiceKey/sourceName 這幾個
session 內不變的欄位做 key。

這裡直接呼叫 `selectTownForCurrentMapAction(town, {autoFocus: false})`
（而非既有 `validate_build_entitlement_queue_browser.py` 為了測試方便使用的
`{autoFocus: true}`）——`autoFocus: false` 才是正式地圖上點擊建立候選 marker 時
真正會走的路徑（見 `renderSupportChoiceHighlights()` 的 outerMarker/innerMarker
click handler），藉此如實驗證使用者實際會遇到的行為。
"""
import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards' / 'build-queue-viewport'
OUT_JSON = RECORD_DIR / 'BUILD_QUEUE_PRESERVES_MAP_VIEWPORT_VALIDATION.json'
OUT_MD = RECORD_DIR / 'BUILD_QUEUE_PRESERVES_MAP_VIEWPORT_VALIDATION.md'
SHOT_BEFORE_PAN = RECORD_DIR / 'viewport_before_manual_pan.png'
SHOT_AFTER_PAN = RECORD_DIR / 'viewport_after_manual_pan.png'
SHOT_AFTER_BUILD = RECORD_DIR / 'viewport_preserved_after_build.png'
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json('/test/setup-build-queue-proof', {})
    if not setup.get('success'):
        raise RuntimeError(setup)

    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={'width': 1280, 'height': 900}).new_page()
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until='networkidle')
        page.wait_for_selector('#gameShell', state='visible', timeout=10000)
        page.wait_for_timeout(900)
        page.evaluate(
            "() => { if (typeof closeEventReveal === 'function') closeEventReveal(); "
            "const b=document.getElementById('closeFactionActionModal'); if(b) b.click(); }"
        )
        page.wait_for_timeout(200)

        page.click("button.hand-card-action-btn[data-card-name='組織經驗丙'][data-card-mode='action']")
        page.wait_for_timeout(500)
        page.click("button.hand-card-action-btn[data-card-name='組織經驗乙'][data-card-mode='action']")
        page.wait_for_function(
            "() => window.lastGameState?.pending_choice?.choice_key === 'card_build_organization' "
            "&& window.lastGameState.pending_choice.remaining_builds === 3",
            timeout=10000,
        )
        page.wait_for_timeout(500)

        frame = page.frame_locator('#strategicMapFrame')
        frame.locator('#map').wait_for(state='visible', timeout=15000)
        map_frame = page.frames[-1]

        initial_view = map_frame.evaluate(
            "() => ({ zoom: window.__redlinePlayableMap.getZoom(), "
            "center: (() => { const c = window.__redlinePlayableMap.getCenter(); return { lat: c.lat, lng: c.lng }; })() })"
        )
        record(
            'entering_build_session_auto_focuses_once',
            isinstance(initial_view.get('zoom'), (int, float)),
            initial_view,
        )
        page.screenshot(path=str(SHOT_BEFORE_PAN))

        # Simulate the player manually panning/zooming away from the auto-focused view —
        # this is the viewport the fix must NOT clobber on the next successful build.
        manual_view = {'lat': 5.0, 'lng': 100.0, 'zoom': 4}
        map_frame.evaluate(
            "(v) => { window.__redlinePlayableMap.setView([v.lat, v.lng], v.zoom, { animate: false }); }",
            manual_view,
        )
        page.wait_for_timeout(200)
        confirmed_manual_view = map_frame.evaluate(
            "() => ({ zoom: window.__redlinePlayableMap.getZoom(), "
            "center: (() => { const c = window.__redlinePlayableMap.getCenter(); return { lat: c.lat, lng: c.lng }; })() })"
        )
        record(
            'manual_pan_applied_before_next_build',
            abs(confirmed_manual_view['zoom'] - manual_view['zoom']) < 0.01,
            confirmed_manual_view,
        )
        page.screenshot(path=str(SHOT_AFTER_PAN))

        remaining_after_each_build = []
        preserved_view_checks = []
        for expected_remaining in (2, 1, 0):
            state = page.evaluate('window.lastGameState')
            pending = state.get('pending_choice') or {}
            town = pending['towns'][0]['town']

            before_view = map_frame.evaluate(
                "() => ({ zoom: window.__redlinePlayableMap.getZoom(), "
                "center: (() => { const c = window.__redlinePlayableMap.getCenter(); return { lat: c.lat, lng: c.lng }; })() })"
            )

            map_frame.evaluate(
                "(t) => window.selectTownForCurrentMapAction(t, { autoFocus: false })",
                town,
            )
            page.wait_for_function(
                """() => {
                  const frame = document.getElementById('strategicMapFrame');
                  const button = frame?.contentDocument?.getElementById('directBuildBtn');
                  return button && !button.disabled && button.textContent.includes('效果');
                }""",
                timeout=10000,
            )
            frame.locator('#directBuildBtn').click()
            if expected_remaining:
                page.wait_for_function(
                    "expected => window.lastGameState?.pending_choice?.remaining_builds === expected",
                    arg=expected_remaining,
                    timeout=10000,
                )
            else:
                page.wait_for_function("() => !window.lastGameState?.pending_choice", timeout=10000)
            page.wait_for_timeout(250)
            remaining_after_each_build.append(expected_remaining)

            after_view = map_frame.evaluate(
                "() => ({ zoom: window.__redlinePlayableMap.getZoom(), "
                "center: (() => { const c = window.__redlinePlayableMap.getCenter(); return { lat: c.lat, lng: c.lng }; })() })"
            )
            preserved = (
                abs(after_view['zoom'] - before_view['zoom']) < 0.01
                and abs(after_view['center']['lat'] - before_view['center']['lat']) < 0.01
                and abs(after_view['center']['lng'] - before_view['center']['lng']) < 0.01
            )
            preserved_view_checks.append({
                'expected_remaining_after': expected_remaining,
                'before': before_view,
                'after': after_view,
                'preserved': preserved,
            })

        record(
            'three_builds_resolve_in_sequence',
            remaining_after_each_build == [2, 1, 0],
            remaining_after_each_build,
        )
        record(
            'map_viewport_never_resets_across_any_of_the_three_builds',
            all(entry['preserved'] for entry in preserved_view_checks),
            preserved_view_checks,
        )
        record(
            'viewport_after_all_builds_still_matches_the_manual_pan_not_the_original_auto_focus',
            abs(preserved_view_checks[-1]['after']['zoom'] - manual_view['zoom']) < 0.01,
            {'final_view': preserved_view_checks[-1]['after'], 'manual_view': manual_view},
        )
        page.screenshot(path=str(SHOT_AFTER_BUILD))

        browser.close()

    payload = {
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshots': [str(SHOT_BEFORE_PAN), str(SHOT_AFTER_PAN), str(SHOT_AFTER_BUILD)],
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 連續建立組織：地圖鏡頭保留驗證',
        '',
        '可重跑指令：`python3 scripts/validate_build_queue_preserves_map_viewport.py`',
        '',
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
        f"- screenshots: {', '.join(payload['screenshots'])}",
        '',
        '## Results',
    ]
    for r in payload['results']:
        lines.append(f"- {'✅' if r['ok'] else '❌'} `{r['name']}` — {json.dumps(r['detail'], ensure_ascii=False)}")
    lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
