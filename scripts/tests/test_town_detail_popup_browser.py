"""戰略地圖「選取城鎮 → 打開該城鎮標準說明 popup」的 Browser（Playwright／Chromium＋真 Leaflet）regression。

使用者回報：以前選擇任一城鎮都會顯示 Leaflet 城鎮說明（座標、陣營、控制者、共享、道路、鐵路）；現在只有移動流程會顯示。
根因：marker click 的選取路徑（selectTownForCurrentMapAction）在同一個 click 內呼叫 renderMap()，重建全部 marker——
Leaflet 先為被點的 marker 開了 popup，接著該 marker 被移除，popup 隨之關閉；只有「點合法移動目的地」那條分支不重繪，
所以只剩移動流程看得到說明。Joy-Con A 走同一條 marker click，SL 全域聚焦從未開說明；每份 state 的 bindPopup 也會
留下內容過期的舊 popup。修正後所有選取都走 leaflet_game_map_logic.js 的 showTownDetail（canonical），重繪後在新的
marker 上以最新內容重新開啟；Joy-Con B 的第一下只關閉說明（controller_map_adapter cancel → via 'popup'）。

伺服器是真的 uvicorn（ENABLE_TEST_ROUTES=true，harness 與 test_propagandist_joycon_browser 共用）；Leaflet 是頁面
原本載入的真 Leaflet 1.9.4。Joy-Con 是 mock bridge WebSocket（舊版 frame 協定，不是實體硬體）。
"""
from __future__ import annotations

import json
import time

import pytest
import requests

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    BITS, MOCK_BRIDGE, app_url, browser, dismiss_modals, focused_choice_town, me, pad, pending, settle, wait_until,
)
from test_thinker_sl_focus_joycon_browser import open_thinker_game, play_thinker

KEYS = {**BITS, "SL": (0, 0x20), "ZR": (0, 0x80)}
NAV = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}
# /test/setup-move-confirmation-proof：臺灣綠線（根據地臺北）唯一的組織在臺中（不是根據地，可遷移）、5 次遷移；紅軍根據地北京。
BASE = "臺中"
RED_BASE = "北京"
FOCUS_ZOOM = 9  # controller_core MAP_FOCUS_ZOOM（SL）
ZR_MAX_ZOOM = 10  # controller_core MAP_ZOOM_CYCLE.max


def press(page, name, hold=0.12, after=0.45):
    index, mask = KEYS[name]
    buttons = [0, 0]
    buttons[index] = mask
    page.evaluate(f"window.__padSend(0, 0, {buttons[0]}, {buttons[1]})")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def stick(page, direction, hold=0.15, after=0.35):
    x, y = NAV[direction]
    page.evaluate(f"window.__padSend({x}, {y}, 0, 0)")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def open_move_game(browser, app_url, display):
    """行動階段、自己的回合、根據地有組織且有遷移次數；開局隨機事件若先開了別的 pending choice 就換一局。"""
    for _ in range(6):
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx.add_init_script(MOCK_BRIDGE)
        page = ctx.new_page()
        page.goto(app_url + f"/?display={display}")
        setup = requests.post(app_url + "/test/setup-move-confirmation-proof", json={"mover_town": BASE}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        page.wait_for_function("window.RedlineController.getState().status === 'connected'")
        time.sleep(0.8)
        if pending(page) is None:
            return page
        ctx.close()
    pytest.fail("could not get a test game without an unrelated pending choice")


def frame(page):
    return page.query_selector("#strategicMapFrame").content_frame()


def detail(page):
    """iframe 內真正開著的 Leaflet popup：數量、標題城鎮、內容（只讀）。"""
    return frame(page).evaluate("window.__townDetailForTest()")


def detail_box(page):
    """實際 Leaflet popup 內容尺寸；城鎮切換／重繪後不得退化成狹長直欄。"""
    return frame(page).evaluate("""() => {
      const el = document.querySelector('.leaflet-popup-content');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { width: r.width, height: r.height };
    }""")


def map_state(page):
    return frame(page).evaluate("window.__mapDebugStateForTest()")


def view(page):
    return page.evaluate("document.querySelector('.game-tab.active')?.dataset.view || null")


def open_map(page):
    page.click('.game-tab[data-view="map"]')
    frame_el = wait_until(lambda: page.query_selector("#strategicMapFrame"))
    assert frame_el
    wait_until(lambda: frame(page) and frame(page).evaluate(
        "typeof window.__townDetailForTest === 'function' && typeof currentMarkers !== 'undefined' && currentMarkers.size > 0"
        " && !!lastGameState"), timeout=20)
    time.sleep(0.6)


def town_point(page, town, zoom=7):
    """把 town 置中於 zoom（真 Leaflet setView），回傳它在 parent 頁面上的螢幕座標（考慮 #designStage 縮放）。"""
    local = frame(page).evaluate("""([town, zoom]) => {
      map.setView(townDisplayLatLng(byName.get(town)), zoom, { animate: false });
      const p = map.latLngToContainerPoint(townDisplayLatLng(byName.get(town)));
      const r = document.getElementById('map').getBoundingClientRect();
      return { x: r.left + p.x, y: r.top + p.y, w: document.documentElement.clientWidth };
    }""", [town, zoom])
    time.sleep(0.3)
    box = page.query_selector("#strategicMapFrame").bounding_box()
    scale = box["width"] / local["w"]
    return box["x"] + local["x"] * scale, box["y"] + local["y"] * scale


def mouse_click_town(page, town):
    x, y = town_point(page, town)
    page.mouse.click(x, y)
    time.sleep(0.5)


def assert_only_detail(page, town):
    d = wait_until(lambda: (lambda v: v if v["town"] == town and v["popups"] == 1 else None)(detail(page)), timeout=4) or detail(page)
    assert d["town"] == town and d["popups"] == 1 and d["names"] == [town], d
    text = d["text"][0]
    for label in ("座標", "靜態統治者", "陣營", "城鎮類型", "當前控制者", "可共享陣營", "一般道路", "鐵路"):
        assert label in text, (label, text)
    return d


def move_target_of(page):
    snap = frame(page).evaluate("window.__redlineControllerAdapter.snapshot()")
    return [t["town"] for t in snap["targets"] if t["role"] == "move"]


# ------------------------------------------------------------------ mouse／一般瀏覽

def test_mouse_browse_selection_opens_detail_and_the_latest_town_wins_across_redraws(browser, app_url):
    page = open_move_game(browser, app_url, "desktop")
    dismiss_modals(page)
    open_map(page)
    assert detail(page)["popups"] == 0

    # 一般瀏覽：不是自己組織的城鎮也一樣打開完整說明（真的滑鼠點擊）。
    mouse_click_town(page, "曼谷")
    assert map_state(page)["selectedTown"] == "曼谷"
    assert_only_detail(page, "曼谷")
    assert frame(page).evaluate("document.querySelector('#info .name')?.textContent.trim()") == "曼谷"
    first_box = detail_box(page)
    assert first_box["width"] >= 279, first_box

    # town A → town B：最後只顯示 B（舊 popup 不殘留、不覆蓋）。
    mouse_click_town(page, "河內")
    assert map_state(page)["selectedTown"] == "河內"
    assert_only_detail(page, "河內")
    second_box = detail_box(page)
    assert second_box["width"] >= 279, second_box

    # A → B → A：回點原城鎮時尺寸保持穩定；首次顯示也不能先變成狹長直欄。
    mouse_click_town(page, "曼谷")
    assert_only_detail(page, "曼谷")
    reopened_box = detail_box(page)
    assert reopened_box["width"] >= 279, reopened_box
    assert abs(reopened_box["width"] - first_box["width"]) < 1, (first_box, reopened_box)
    mouse_click_town(page, "河內")
    assert_only_detail(page, "河內")

    # Leaflet 重繪與 state render（每份 state 都會重新 bindPopup）之後仍是最新選取的 B，內容是最新的。
    frame(page).evaluate("renderMap(); applyGameStateToMap(lastGameState); applyGameStateToMap(lastGameState);")
    time.sleep(0.3)
    assert_only_detail(page, "河內")
    # 滑鼠滾輪縮放（zoomend → renderMap）也不讓說明消失或換回曼谷。
    x, y = town_point(page, "河內")
    page.mouse.move(x, y)
    page.mouse.wheel(0, -300)
    time.sleep(1.0)
    assert_only_detail(page, "河內")

    # 根據地（🏕 疊在城鎮圓圈正中央）：點圖示也是選取該城鎮並顯示說明（不會被圖示吃掉）。
    x, y = town_point(page, RED_BASE)
    assert page.evaluate("([x, y]) => document.elementFromPoint(x, y)?.tagName", [x, y]) == "IFRAME"
    hit = frame(page).evaluate("""(t) => { const b = document.querySelector(`.base-badge[data-base-town="${t}"]`); if (!b) return null;
      const r = b.getBoundingClientRect(); return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)?.closest('.base-badge') === b; }""", RED_BASE)
    assert hit, "the 🏕 badge is what the mouse hits at the town centre"
    page.mouse.click(x, y)
    time.sleep(0.5)
    assert map_state(page)["selectedTown"] == RED_BASE
    assert_only_detail(page, RED_BASE)

    # 自己的組織城鎮：選取來源。
    mouse_click_town(page, BASE)
    assert map_state(page)["selectedTown"] == BASE
    assert_only_detail(page, BASE)

    # 合法移動目的地（既有的移動流程）：預備移動並顯示目的地說明。
    dest = move_target_of(page)
    assert dest, "base has legal movement destinations"
    frame(page).evaluate("(t) => window.__clickMoveTargetForTest(t)", dest[0])
    time.sleep(0.3)
    assert map_state(page)["pendingMoveTarget"]["to"] == dest[0]
    assert_only_detail(page, dest[0])

    # 使用者自己關閉（×）：說明關閉，之後的重繪不會再打開它。
    frame(page).evaluate("document.querySelector('.leaflet-popup-close-button').click()")
    time.sleep(0.2)
    frame(page).evaluate("renderMap(); applyGameStateToMap(lastGameState);")
    time.sleep(0.2)
    assert detail(page)["popups"] == 0
    assert map_state(page)["pendingMoveTarget"]["to"] == dest[0], "closing the popup keeps the pending move"


# ------------------------------------------------------------------ Joy-Con：A 選取、B 先關說明

def joycon_select_base(page):
    open_map(page)
    if not pad(page)["padActive"]:
        press(page, "A")  # 第一下只放焦點
    settle(page, "desktop")
    assert pad(page)["scope"] == "map", pad(page)
    for _ in range(12):
        if pad(page)["focusTown"] == BASE:
            break
        stick(page, "right")
    assert pad(page)["focusTown"] == BASE, pad(page)
    press(page, "A")
    assert wait_until(lambda: map_state(page)["selectedTown"] == BASE)
    assert_only_detail(page, BASE)


def test_joycon_a_selects_with_detail_first_b_only_closes_it_second_b_runs_the_original_cancel(browser, app_url):
    page = open_move_game(browser, app_url, "desktop")
    dismiss_modals(page)
    joycon_select_base(page)

    # 搖桿移到合法目的地，A 預備移動：說明換成目的地（只有一個 popup）。
    dests = move_target_of(page)
    assert dests
    for direction in ["right", "down", "left", "up"] * 4:
        if pad(page)["focusTown"] in dests:
            break
        stick(page, direction)
    target = pad(page)["focusTown"]
    assert target in dests, pad(page)
    settle(page, "desktop")
    press(page, "A")
    assert wait_until(lambda: (map_state(page)["pendingMoveTarget"] or {}).get("to") == target), map_state(page)
    assert_only_detail(page, target)
    wait_until(lambda: (pad(page)["map"] or {}).get("detail") == target)
    assert "B 關閉城鎮說明" in page.evaluate("document.getElementById('padHint')?.textContent || ''")

    # 第一下 B：只關閉說明；選取、預備移動、地圖分頁、控制器焦點都保留。
    before_focus = (pad(page)["focusKind"], pad(page)["focusTown"])
    settle(page, "desktop")
    press(page, "B")
    assert wait_until(lambda: detail(page)["popups"] == 0), detail(page)
    st = map_state(page)
    assert st["selectedTown"] == BASE and (st["pendingMoveTarget"] or {}).get("to") == target, st
    assert view(page) == "map"
    assert (pad(page)["focusKind"], pad(page)["focusTown"]) == before_focus
    assert me(page)["orgs"] == {BASE: 1}, "no move was sent"

    # 第二下 B：原本的取消（取消目前選取＋預備移動）。
    settle(page, "desktop")
    press(page, "B")
    assert wait_until(lambda: map_state(page)["selectedTown"] is None), map_state(page)
    assert map_state(page)["pendingMoveTarget"] is None
    assert view(page) == "map"

    # A 仍能選取並確認移動（Y＝既有確認移動）：說明不擋住既有操作。
    for _ in range(12):
        if pad(page)["focusTown"] == BASE:
            break
        stick(page, "right")
    settle(page, "desktop")
    press(page, "A")
    assert wait_until(lambda: map_state(page)["selectedTown"] == BASE)
    assert_only_detail(page, BASE)


# ------------------------------------------------------------------ 動作目標（pending choice）

def test_action_target_selection_opens_detail_and_b_keeps_the_pending_choice(browser, app_url):
    page = open_thinker_game(browser, app_url, "desktop")
    choice = play_thinker(page, "desktop")
    target = focused_choice_town(page, "desktop")
    assert target, pad(page)
    settle(page, "desktop")
    press(page, "A")  # A＝選取合法目標（既有 marker click）
    assert wait_until(lambda: map_state(page)["selectedTown"] == target), map_state(page)
    assert_only_detail(page, target)

    settle(page, "desktop")
    press(page, "B")
    assert wait_until(lambda: detail(page)["popups"] == 0), detail(page)
    assert map_state(page)["selectedTown"] == target, "first B keeps the selected target"
    assert (pending(page) or {}).get("choice_id") == choice["choice_id"], "pending choice untouched"
    assert view(page) == "map"

    settle(page, "desktop")
    press(page, "B")  # 原本的規則：取消目前選取（pending choice 仍在，必選）
    assert wait_until(lambda: map_state(page)["selectedTown"] is None), map_state(page)
    assert (pending(page) or {}).get("choice_id") == choice["choice_id"]

    # 選取後 Y 仍走既有建立流程（說明 popup 不擋）。
    for _ in range(12):
        if focused_choice_town(page, "desktop") == target:
            break
        stick(page, "right")
    settle(page, "desktop")
    press(page, "A")
    assert wait_until(lambda: map_state(page)["selectedTown"] == target)
    assert_only_detail(page, target)


# ------------------------------------------------------------------ SL 全域聚焦（iframe 指令路徑）＋ZR

def test_sl_focus_opens_detail_read_only_keeps_zoom_9_center_and_survives_zr_zoom_10(browser, app_url):
    page = open_move_game(browser, app_url, "desktop")
    dismiss_modals(page)
    open_map(page)
    sends_before = map_state(page)
    # parent 送出與 SL 選單相同的 focusTown 指令（帶 req；iframe 驗證 source＝parent）。
    page.evaluate("""() => document.getElementById('strategicMapFrame').contentWindow.postMessage(
      { type: 'redline-controller-command', v: 1, cmd: 'focusTown', town: '曼谷', req: 4242 }, location.origin)""")
    time.sleep(0.6)
    assert_only_detail(page, "曼谷")
    cam = frame(page).evaluate("""() => {
      const p = map.latLngToContainerPoint(townDisplayLatLng(byName.get('曼谷'))); const s = map.getSize();
      return { zoom: map.getZoom(), dx: p.x - s.x / 2, dy: p.y - s.y / 2 };
    }""")
    assert cam["zoom"] == FOCUS_ZOOM and abs(cam["dx"]) <= 1 and abs(cam["dy"]) <= 1, cam
    st = map_state(page)
    assert st["selectedTown"] == sends_before["selectedTown"] and st["pendingMoveTarget"] is None, "read-only"

    # ZR（第一下也執行，不需要焦點）：zoom 9 → 10，中心不變，說明仍是曼谷。
    press(page, "ZR")
    cam = frame(page).evaluate("""() => {
      const p = map.latLngToContainerPoint(townDisplayLatLng(byName.get('曼谷'))); const s = map.getSize();
      return { zoom: map.getZoom(), dx: p.x - s.x / 2, dy: p.y - s.y / 2 };
    }""")
    assert cam["zoom"] == ZR_MAX_ZOOM and abs(cam["dx"]) <= 1 and abs(cam["dy"]) <= 1, cam
    assert_only_detail(page, "曼谷")

    # B（第一下放焦點之後）：第一下只關閉說明，相機不動。
    if not pad(page)["padActive"]:
        press(page, "A")  # 第一下只放焦點（不執行）
    assert_only_detail(page, "曼谷")
    settle(page, "desktop")
    press(page, "B")
    assert wait_until(lambda: detail(page)["popups"] == 0), detail(page)
    assert frame(page).evaluate("map.getZoom()") == ZR_MAX_ZOOM
    assert view(page) == "map"
