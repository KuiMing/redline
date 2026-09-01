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

"""瓦解組織效果：地圖優先互動驗證（2026-08-02 playtest 建議）。

北國奧援、臺灣奧援、間諜卡瓦解互動、情報網、事件紅軍瓦解、時代加成瓦解、國安部等
瓦解選目標效果，建立 pending choice 後應自動切換到戰略地圖，只在後端判定合法的組織
marker 上以 💀 標示，玩家可直接點選完成瓦解，不必先在指揮中心或通用 choice modal
找目標。這支腳本補齊既有 `validate_beiguo_two_stage_dissolve.py`／
`validate_intel_network_map_close_browser.py`／`validate_base_dissolve_browser.py`
（敵我/base 保護）之外，跨來源 interaction_kind 一致性、距離過濾、與連續多次瓦解的
正式 UI 覆蓋。

2026-08-02 追加：點擊 💀 marker 現在只會「選取」該目標（啟用左側 #dissolveBtn 並顯示
確認提示），須再按一次 #dissolveBtn 才會真正送出瓦解動作——playtest 回饋指出單擊
立即瓦解對新手太危險，容易誤觸不可逆動作。本檔的斷言已相應改為「點 skull → 斷言已
選取待確認且尚未變動盤面 → 點確認按鈕 → 斷言真正完成瓦解」。
"""

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'DISSOLVE_MAP_FIRST_INTERACTION_VALIDATION.json'
OUT_MD = RECORD_DIR / 'DISSOLVE_MAP_FIRST_INTERACTION_VALIDATION.md'
SCREENSHOT_SPY = RECORD_DIR / 'dissolve_map_first_spy_card.png'
SCREENSHOT_MULTI = RECORD_DIR / 'dissolve_map_first_multi_target.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def close_startup_modals(page):
    page.evaluate(
        "() => { if (typeof closeEventReveal === 'function') closeEventReveal(); "
        "const b=document.getElementById('closeFactionActionModal'); if(b) b.click(); }"
    )
    page.wait_for_timeout(200)


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # --- 1. 間諜卡（內應間諜，choice_key='card_dissolve_interaction'，單步、無自我犧牲）：
    # interaction_kind 統一標記、自動切地圖、距離過濾正確反映在 💀 數量上 ---
    page = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
    setup = post_json('/test/setup-spy-proof', {'card_name': '內應間諜'})
    gid, pid = setup['game_id'], setup['player_id']
    page.goto(f'{BASE_URL}/?game_id={gid}&player_id={pid}', wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_timeout(900)
    close_startup_modals(page)
    page.click('button.hand-card-action-btn[data-card-name="內應間諜"][data-card-mode="action"]')
    page.wait_for_timeout(700)
    pc = page.evaluate("() => window.lastGameState?.pending_choice")
    active_view = page.evaluate("() => document.querySelector('.game-view.active')?.id")
    modal_visible = page.evaluate("() => document.getElementById('choiceModal')?.style.display !== 'none'")
    skull_count = page.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge').count()
    # 預設敵方組織有 3 座城鎮（天津/杭州/香港城），只有距離內的合法目標才會出現在
    # choice.targets（後端已排除距離外的），💀 數量應與後端投影的候選數一致——
    # 藉此連帶驗證「距離」過濾確實反映在地圖標示上。
    record(
        'spy_card_dissolve_interaction_gets_unified_interaction_kind_and_auto_switches_to_map',
        pc is not None
        and pc.get('choice_key') == 'card_dissolve_interaction'
        and pc.get('interaction_kind') == 'dissolve_organization'
        and not modal_visible
        and active_view == 'mapView',
        {'pending_choice': pc, 'modal_visible': modal_visible, 'active_view': active_view},
    )
    record(
        'skull_marker_count_matches_backend_projected_legal_targets_distance_filtered',
        skull_count == len(pc.get('targets') or []) and skull_count < 3,
        {'skull_count': skull_count, 'target_count': len(pc.get('targets') or []), 'enemy_total_orgs': 3},
    )
    page.screenshot(path=str(SCREENSHOT_SPY))

    before_hand = page.evaluate("(id) => window.lastGameState.players.find(p=>p.id===id).hand", pid)
    page.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge').first.click()
    page.wait_for_timeout(400)
    armed_count = page.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge-armed').count()
    still_pending_after_arm = page.evaluate("() => window.lastGameState?.pending_choice") is not None
    enemy_before_confirm = next(p for p in page.evaluate("() => window.lastGameState")['players'] if p['name'] == 'enemy')
    record(
        'clicking_the_skull_only_arms_the_target_without_dissolving',
        armed_count == 1 and still_pending_after_arm and enemy_before_confirm['orgs'].get('天津', 0) == 1,
        {'armed_count': armed_count, 'still_pending_after_arm': still_pending_after_arm, 'enemy_orgs_before_confirm': enemy_before_confirm['orgs']},
    )
    page.frame_locator('#strategicMapFrame').locator('#dissolveBtn').click()
    page.wait_for_timeout(700)
    final1 = page.evaluate("() => window.lastGameState")
    enemy1 = next(p for p in final1['players'] if p['name'] == 'enemy')
    record(
        'confirm_button_click_resolves_the_dissolve_and_returns_to_no_pending_state',
        final1.get('pending_choice') is None and enemy1['orgs'].get('天津', 0) == 0,
        {'before_hand': before_hand, 'enemy_orgs_after': enemy1['orgs']},
    )
    page.close()

    # --- 2. 北國奧援 III 級（choice_key='support_interaction'，可連續瓦解 2 個）：
    # 跨兩輪的地圖優先流程，每輪 💀 數量正確更新，結算後停留在地圖，直到全部結算完成 ---
    page2 = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
    setup2 = post_json('/test/setup-support-proof', {
        'support_name': '北國奧援', 'tier': 3,
        'orgs': {'基隆': 1, '新竹': 1},
        'matched_regions': ['北國'],
        'enemy_faction_id': 'taiwan_green',
        'enemy_base': '臺北',
        'enemy_orgs': {'新北': 1, '桃園': 1},
    })
    gid2, pid2 = setup2['game_id'], setup2['player_id']
    page2.goto(f'{BASE_URL}/?game_id={gid2}&player_id={pid2}', wait_until='networkidle')
    page2.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page2.wait_for_timeout(900)
    close_startup_modals(page2)
    page2.click('button.hand-card-action-btn[data-card-name="北國奧援"][data-card-mode="action"]')
    page2.wait_for_timeout(700)
    pc_r1 = page2.evaluate("() => window.lastGameState?.pending_choice")
    skulls_r1 = page2.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge')
    record(
        'support_interaction_multi_dissolve_round1_shows_both_legal_targets',
        pc_r1 is not None
        and pc_r1.get('interaction_kind') == 'dissolve_organization'
        and sorted(t['town'] for t in pc_r1['targets']) == ['新北', '桃園']
        and skulls_r1.count() == 2,
        {'pending_choice_round1': pc_r1, 'skull_count_round1': skulls_r1.count()},
    )
    page2.screenshot(path=str(SCREENSHOT_MULTI))
    skulls_r1.first.click()
    page2.wait_for_timeout(400)
    armed_count_r1 = page2.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge-armed').count()
    still_pending_r1 = page2.evaluate("() => window.lastGameState?.pending_choice") is not None
    enemy_before_confirm_r1 = next(p for p in page2.evaluate("() => window.lastGameState")['players'] if p['faction'] == 'taiwan_green')
    record(
        'round1_clicking_a_skull_only_arms_it_without_dissolving',
        armed_count_r1 == 1 and still_pending_r1 and len(enemy_before_confirm_r1['orgs']) == 2,
        {'armed_count_r1': armed_count_r1, 'still_pending_r1': still_pending_r1, 'enemy_orgs_before_confirm_r1': enemy_before_confirm_r1['orgs']},
    )
    page2.frame_locator('#strategicMapFrame').locator('#dissolveBtn').click()
    page2.wait_for_timeout(700)
    pc_r2 = page2.evaluate("() => window.lastGameState?.pending_choice")
    view_between_rounds = page2.evaluate("() => document.querySelector('.game-view.active')?.id")
    skulls_r2 = page2.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge')
    record(
        'confirming_round1_dissolves_one_target_and_round2_shows_only_the_remaining_legal_target',
        pc_r2 is not None
        and len(pc_r2.get('targets') or []) == 1
        and skulls_r2.count() == 1
        and view_between_rounds == 'mapView',
        {'pending_choice_round2': pc_r2, 'skull_count_round2': skulls_r2.count(), 'view_between_rounds': view_between_rounds},
    )
    skulls_r2.first.click()
    page2.wait_for_timeout(400)
    armed_count_r2 = page2.frame_locator('#strategicMapFrame').locator('.dissolve-target-badge-armed').count()
    record(
        'round2_clicking_the_last_skull_also_only_arms_it_first',
        armed_count_r2 == 1 and page2.evaluate("() => window.lastGameState?.pending_choice") is not None,
        {'armed_count_r2': armed_count_r2},
    )
    page2.frame_locator('#strategicMapFrame').locator('#dissolveBtn').click()
    page2.wait_for_timeout(700)
    final2 = page2.evaluate("() => window.lastGameState")
    enemy2 = next(p for p in final2['players'] if p['faction'] == 'taiwan_green')
    view_after_settlement = page2.evaluate("() => document.querySelector('.game-view.active')?.id")
    record(
        'both_sequential_dissolves_complete_after_explicit_confirms_and_view_stays_on_map',
        final2.get('pending_choice') is None
        and enemy2['orgs'] == {}
        and view_after_settlement == 'mapView',
        {'enemy_orgs_final': enemy2['orgs'], 'view_after_settlement': view_after_settlement},
    )
    page2.close()

    return {
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshots': [str(SCREENSHOT_SPY), str(SCREENSHOT_MULTI)],
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 瓦解組織效果：地圖優先互動（interaction_kind 統一／💀 標示／連續瓦解）驗證',
        '',
        '可重跑指令：`python3 scripts/validate/validate_dissolve_map_first_interaction.py`',
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
