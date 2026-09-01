import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'map-ui'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'MOVE_CONFIRMATION_VALIDATION.json'
OUT_MD = RECORD_DIR / 'MOVE_CONFIRMATION_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'move_confirmation_validation.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def map_debug(page):
    return page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__mapDebugStateForTest()")


def last_move_request(page):
    return page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__lastMoveRequest || null")


def check_flow(page):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    setup = post_json('/test/setup-move-confirmation-proof', {
        'mover_faction': 'taiwan_green',
        'mover_base': '新竹',  # base ≠ moving town so the org isn't a non-movable base anchor
        'mover_town': '臺北',
        'moves_left': 5,
    })
    record('setup_succeeded', setup.get('success') is True, setup)
    game_id = setup['game_id']

    page.goto(BASE_URL + setup['url'], wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
    page.click('button.game-tab[data-view="map"]')
    page.wait_for_timeout(2000)

    page.evaluate("() => { document.getElementById('strategicMapFrame').contentWindow.__selectTownForTest('臺北'); }")
    page.wait_for_timeout(300)

    before_click = map_debug(page)
    record(
        'no_pending_move_before_clicking_a_target',
        before_click['pendingMoveTarget'] is None and last_move_request(page) is None and '基隆' in before_click['reachableFromSelected'],
        before_click,
    )

    click_result = page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__clickMoveTargetForTest('基隆')")
    after_click = map_debug(page)
    record(
        'clicking_a_reachable_town_shows_pending_confirmation_without_sending_move',
        click_result.get('ok')
        and after_click['pendingMoveTarget'] == {'from': '臺北', 'to': '基隆', 'mode': 'rail', 'cost': 1}
        and last_move_request(page) is None,
        {'click_result': click_result, 'after_click': after_click},
    )

    button_state = page.evaluate(
        """() => {
          const doc = document.getElementById('strategicMapFrame').contentDocument;
          const confirmBtn = doc.getElementById('confirmMoveBtn');
          const hint = doc.getElementById('confirmMoveHint');
          return { confirmDisabled: confirmBtn.disabled, hintText: hint.textContent };
        }"""
    )
    record(
        'confirm_button_enabled_with_explanatory_hint',
        not button_state['confirmDisabled']
        and '臺北' in button_state['hintText'] and '基隆' in button_state['hintText'],
        button_state,
    )

    # 2026-08-05 使用者需求：「取消目的地（保留起點）」按鈕已移除，改為「點地圖其他地方
    # 直接取消整個選擇」。點擊一個不相關、玩家也無法從該城鎮行動、也不是本次移動合法目的
    # 地的城鎮（臺中）現在會取消整個選擇（含起點），不再只是清空目的地。
    cancel_result = page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__clickMoveTargetForTest('臺中')")
    after_cancel = map_debug(page)
    record(
        'clicking_an_unrelated_town_cancels_the_whole_selection_and_sends_nothing',
        cancel_result.get('ok') and after_cancel['pendingMoveTarget'] is None and last_move_request(page) is None
        and after_cancel['selectedTown'] is None and after_cancel['reachableFromSelected'] == [],
        {'cancel_result': cancel_result, 'after_cancel': after_cancel},
    )

    button_state_after_cancel = page.evaluate(
        """() => {
          const doc = document.getElementById('strategicMapFrame').contentDocument;
          return { confirmDisabled: doc.getElementById('confirmMoveBtn').disabled };
        }"""
    )
    record(
        'confirm_button_disabled_again_after_cancel',
        button_state_after_cancel['confirmDisabled'],
        button_state_after_cancel,
    )

    page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__selectTownForTest('臺北')")
    page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__clickMoveTargetForTest('基隆')")
    page.wait_for_timeout(200)
    confirm_result = page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__confirmPendingMoveForTest()")
    page.wait_for_timeout(800)
    after_confirm = map_debug(page)
    move_request = last_move_request(page)
    record(
        'confirm_sends_the_move_with_correct_payload_and_clears_pending',
        confirm_result.get('ok') and after_confirm['pendingMoveTarget'] is None
        and move_request == {'from': '臺北', 'to': '基隆', 'mode': 'rail', 'ok': True},
        {'confirm_result': confirm_result, 'after_confirm': after_confirm, 'move_request': move_request},
    )

    final_state = page.evaluate(
        "() => { const towns = document.getElementById('strategicMapFrame').contentWindow.lastGameState?.map?.towns || {}; return { taipei: towns['臺北'] || [], keelung: towns['基隆'] || [] }; }"
    )
    record(
        'server_state_reflects_the_confirmed_move',
        any(e.get('player') == 'mover' and (e.get('count') or 0) > 0 for e in final_state.get('keelung', [])),
        final_state,
    )

    page.screenshot(path=str(SCREENSHOT))
    return {
        'game_id': game_id,
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshot': str(SCREENSHOT),
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
        payload = check_flow(page)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Move confirmation dialog validation',
        '',
        f"- game_id: {payload['game_id']}",
        f"- total: {payload['summary']['total']}",
        f"- passed: {payload['summary']['passed']}",
        f"- failed: {payload['summary']['failed']}",
        f"- screenshot: {payload['screenshot']}",
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
