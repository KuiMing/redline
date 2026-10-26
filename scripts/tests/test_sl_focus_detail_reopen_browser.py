"""SL 全域聚焦城鎮 → B 關閉城鎮說明 → A 重新開啟同一城鎮說明的 Browser（Playwright／Chromium＋真 Leaflet）regression。

使用者回報：Joy-Con SL 選屏東或宜蘭後，地圖聚焦 zoom 9 並顯示城鎮說明；B 關閉說明後地圖焦點仍停在該城鎮（正確），
但再按 A 無法重新開啟該城鎮說明。根因：SL 聚焦的非目標城鎮是只看的 'browse' 焦點，刻意不在 action 焦點集合內，
controller_core.routeAction 的 A 在沒有 action 焦點時回傳 null；城鎮說明只在 focusTown 的副作用中打開，
沒有任何唯讀指令能重新打開它。修正後 A 在 browse 焦點上路由為 townDetail → iframe 'detail' 指令（adapter 重驗
town＝目前的 map focus 後只呼叫 canonical showTownDetail；不 marker click、不選取、不動相機）。

伺服器是真的 uvicorn（ENABLE_TEST_ROUTES=true，harness 與 test_propagandist_joycon_browser 共用）。Joy-Con 是 mock
bridge WebSocket（舊版 frame 協定，不是實體硬體）：每個按鍵都是「按下 frame → 按住期間每 33ms 重送 → 放開 frame」，
SL 選單內也只用搖桿與 A（不呼叫 focusElement、不點任何按鈕）。遊戲 WebSocket（parent 與 iframe）的 send 全部記錄下來，
證明 SL／B／A／ZR 都不送任何遊戲 mutation。

--redline-evidence-dir（或 REDLINE_EVIDENCE_DIR）有設定時，另存 1280×720 截圖與機器可讀 state proof（JSON）。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    app_url, browser, dismiss_modals, hint, me, org_counts, pad, pending, settle, wait_until,
)
from test_thinker_sl_focus_joycon_browser import SEND_SPY, assert_released, game_sends, last_ack, menu_focus, menu_nav_to, menu_open
from test_town_detail_popup_browser import (
    FOCUS_ZOOM, ZR_MAX_ZOOM, assert_only_detail, detail, frame, map_state, open_map, open_move_game, press, view,
)

GROUP_ID = "lrFocusOpt-ruler-臺灣"  # 屏東、宜蘭的靜態統治者都是臺灣


def camera(page, town):
    return frame(page).evaluate("""(town) => {
      const p = map.latLngToContainerPoint(townDisplayLatLng(byName.get(town))); const s = map.getSize();
      return { zoom: map.getZoom(), centered: Math.abs(p.x - s.x / 2) <= 1 && Math.abs(p.y - s.y / 2) <= 1 };
    }""", town)


def ring_label(page):
    """iframe 的 Joy-Con focus ring 標籤（map focus 停在哪個城鎮）。"""
    return frame(page).evaluate("document.querySelector('.pad-focus-label')?.textContent.trim() || null")


def authoritative(page):
    """不可被 SL／B／A／ZR 改變的部分：伺服器 state（組織、遷移次數、pending choice）＋iframe 的選取／預備移動。"""
    st = map_state(page)
    p = me(page)
    return {
        "orgs": org_counts(p), "moves": p.get("moves_left"), "pending": pending(page),
        "selectedTown": st["selectedTown"], "pendingMoveTarget": st["pendingMoveTarget"],
    }


def focus_state(page):
    s = pad(page)
    return {"scope": s["scope"], "focusKind": s["focusKind"], "focusTown": s["focusTown"], "ring": ring_label(page)}


def sl_focus(page, town):
    """SL → 臺灣 → town：只用 bridge frame（搖桿＋A）；回傳 focusTown 的 ack。"""
    settle(page, "desktop")
    press(page, "SL")
    assert wait_until(lambda: menu_open(page) and menu_focus(page), timeout=4), pad(page)
    settle(page, "desktop")
    menu_nav_to(page, GROUP_ID)
    press(page, "A")
    assert wait_until(lambda: page.evaluate("!!document.getElementById('lrFocusMenuBack')"), timeout=3), "臺灣 group did not open"
    settle(page, "desktop")
    menu_nav_to(page, f"lrFocusTown-{town}")
    before = (last_ack(page, "desktop") or {}).get("req") or 0
    press(page, "A")
    ack = wait_until(lambda: (lambda a: a if a and a["cmd"] == "focusTown" and a["req"] > before else None)(last_ack(page, "desktop")), timeout=3)
    assert ack and ack["outcome"] == "success", (ack, pad(page))
    assert not menu_open(page)
    return ack


def open_spied_move_game(browser, app_url):
    """open_move_game 同一份 fixture（自己的回合、可遷移），先掛 send spy（真正的 WebSocket.prototype.send）。"""
    original = browser.new_context

    def new_context(**kwargs):
        ctx = original(**kwargs)
        ctx.add_init_script(SEND_SPY)
        return ctx

    browser.new_context = new_context
    try:
        return open_move_game(browser, app_url, "desktop")
    finally:
        browser.new_context = original


@pytest.mark.parametrize("town", ["屏東", "宜蘭"])
def test_sl_focused_town_detail_closed_by_b_reopens_with_a_read_only(browser, app_url, town, request):
    evidence = request.config.getoption("--redline-evidence-dir") or os.environ.get("REDLINE_EVIDENCE_DIR")
    page = open_spied_move_game(browser, app_url)
    try:
        dismiss_modals(page)
        open_map(page)
        if not pad(page)["padActive"]:
            press(page, "A")  # 第一下只放焦點（不執行）
        settle(page, "desktop")
        assert pad(page)["scope"] == "map", pad(page)
        sends = game_sends(page)
        pointer = page.evaluate("window.__trustedPointer")  # open_map 的分頁 click 是測試準備；之後只用 Joy-Con frame
        before = authoritative(page)
        assert before["pending"] is None and before["pendingMoveTarget"] is None, before

        # 1. SL 選城 → zoom 9 精確置中＋城鎮說明（只看的 browse 焦點）。
        sl_focus(page, town)
        assert wait_until(lambda: camera(page, town)["zoom"] == FOCUS_ZOOM and camera(page, town)["centered"], timeout=3), camera(page, town)
        assert_only_detail(page, town)
        assert_released(page)
        focused = {"scope": "map", "focusKind": "browse", "focusTown": town, "ring": town}
        assert wait_until(lambda: focus_state(page) == focused, timeout=3), focus_state(page)
        assert town not in [t["town"] for t in frame(page).evaluate("window.__redlineControllerAdapter.snapshot()")["targets"]]
        proof = {"town": town, "steps": []}

        def record(step):
            proof["steps"].append({"step": step, "detail": detail(page), "camera": camera(page, town), "focus": focus_state(page),
                                   "authoritative": authoritative(page), "gameSends": game_sends(page) - sends, "view": view(page),
                                   "hint": hint(page)})

        record("sl-selected")

        # 2. B → 說明關閉；地圖焦點（browse＋ring）、相機都保留。
        settle(page, "desktop")
        press(page, "B")
        assert wait_until(lambda: detail(page)["popups"] == 0), detail(page)
        assert wait_until(lambda: (pad(page)["map"] or {}).get("detail") is None), pad(page)["map"]
        time.sleep(0.4)  # reconcile／render 都跑過：瀏覽焦點仍在
        assert focus_state(page) == focused, focus_state(page)
        assert camera(page, town) == {"zoom": FOCUS_ZOOM, "centered": True}
        assert "A 城鎮說明" in hint(page), hint(page)
        record("b-closed")

        # 3. A → 同一城鎮說明重新開啟；唯讀（不選取、不預備移動、不送遊戲訊息），焦點與相機不變。
        settle(page, "desktop")
        press(page, "A")
        assert_only_detail(page, town)
        assert focus_state(page) == focused, focus_state(page)
        assert camera(page, town) == {"zoom": FOCUS_ZOOM, "centered": True}
        assert view(page) == "map"
        record("a-reopened")
        if evidence:
            out = Path(evidence)
            out.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out / f"sl-focus-reopen-{town}-1280x720.png"))

        # 4. ZR → zoom 10（說明仍開著）；B 關閉、A 在 zoom 10 重新開啟（不跳回 zoom 9）。
        press(page, "ZR")
        assert wait_until(lambda: camera(page, town)["zoom"] == ZR_MAX_ZOOM, timeout=3), camera(page, town)
        assert camera(page, town)["centered"]
        assert_only_detail(page, town)
        settle(page, "desktop")
        press(page, "B")
        assert wait_until(lambda: detail(page)["popups"] == 0), detail(page)
        settle(page, "desktop")
        press(page, "A")
        assert_only_detail(page, town)
        assert camera(page, town) == {"zoom": ZR_MAX_ZOOM, "centered": True}
        assert focus_state(page) == focused, focus_state(page)
        record("zr-b-a-reopened")

        # 沒有 mutation：沒有任何遊戲 WebSocket 訊息，伺服器 state、選取、預備移動、pending choice 都不變；沒有滑鼠。
        assert game_sends(page) == sends, (page.evaluate("window.__gameSends"), frame(page).evaluate("window.__gameSends"))
        assert authoritative(page) == before
        assert page.evaluate("window.__trustedPointer") == pointer, "game was operated with the mouse"
        if evidence:
            proof["mutation"] = {"gameSends": game_sends(page) - sends, "before": before, "after": authoritative(page),
                                 "trustedPointerAfterSetup": page.evaluate("window.__trustedPointer") - pointer}
            (Path(evidence) / f"sl-focus-reopen-{town}-state.json").write_text(
                json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        page.context.close()
