"""思想家（無視距離建立 1 個組織，再進行 3 次組織遷移）pending choice 經 SL 全域聚焦到「天方 › 利雅德」之後，
Joy-Con 必須維持與「直接用 Joy-Con 導航到利雅德」一致的可操作狀態。Browser（Playwright／Chromium）regression。

伺服器是真的 uvicorn（server.main:app，ENABLE_TEST_ROUTES=true，隨機埠，測試結束即關閉；harness 與
test_propagandist_joycon_browser 共用）。牌局由 /test/setup-remove-to-purchase 準備：維吾爾（伊斯坦堡）陣營、
手牌只有思想家、行動階段。Joy-Con 是 mock bridge WebSocket（舊版 frame 協定，不是實體硬體）：每個按鍵都是
「按下 frame → 按住期間 bridge 每 33ms 重送 → 放開 frame」，SL 聚焦選單內也只用搖桿與 A 移動、選定（不呼叫 focusElement、
不點任何按鈕）。遊戲 WebSocket（parent 與戰略地圖 iframe）的 send 全部記錄下來，用來證明 SL 不送任何遊戲 mutation。

根因：思想家的候選遍布全圖（沒有陣營標籤的北美城鎮對所有非紅軍陣營都合法），SL 當時把地圖精確置中利雅德並放大到 zoom 10 後，
溫哥華等目標的 iframe container 座標約 −12 萬 px，超過 parent sanitizeMapSnapshot 舊的 ±10 萬上限 → 整份 snapshot 作廢、
之後每一份推送也一樣（相機一直停在 zoom 10）→ parent 沒有任何地圖目標：桌面焦點 town:利雅德 對不到項目、客廳清單變空，
A／Y／搖桿全部 no-op。直接導航不改層級（座標小），所以不會卡。不是 race：同一路徑必定重現。
SL 的固定層級現在是 zoom 9（北美目標約 −6 萬 px）；SL 之後再按 ZR 放大到循環最大層級 10 仍會到 −12 萬 px，
所以另有一個 SL → ZR（zoom 10）的 regression 保住目標座標上限的修正。
"""
from __future__ import annotations

import json
import time

import pytest
import requests

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    BITS, MOCK_BRIDGE, app_url, browser, dismiss_modals, focused_choice_town, me, org_counts, pad, pending, settle, wait_until,
)

KEYS = {**BITS, "SL": (0, 0x20), "ZR": (0, 0x80)}
# controller_core.stickDirection：y > 0 是畫面向下。
NAV = {"right": (1, 0), "left": (-1, 0), "down": (0, 1), "up": (0, -1)}
DECK = ["追隨者", "追隨者", "追隨者", "樂捐者", "樂捐者"]
FIXTURE = {"card_name": "思想家", "faction_id": "uyghur_istanbul", "base": "伊斯坦堡", "deck": DECK}
TARGET = "利雅德"
NON_TARGET = "伊斯坦堡"  # 天方的城鎮，但已有自己的根據地組織：不是建立目標
FAR_TARGET = "溫哥華"  # 沒有陣營標籤：思想家對所有非紅軍陣營都合法
GROUP_ID = "lrFocusOpt-ruler-天方"
SL_CYCLES = 5
FOCUS_ZOOM = 9  # controller_core MAP_FOCUS_ZOOM（SL 固定層級）
ZR_MAX_ZOOM = 10  # controller_core MAP_ZOOM_CYCLE.max

SEND_SPY = """
(() => {
  window.__gameSends = [];
  const send = WebSocket.prototype.send;
  WebSocket.prototype.send = function (data) { window.__gameSends.push(String(data)); return send.call(this, data); };
})();
"""


# ------------------------------------------------------------------ controller input（只送 bridge frame）

def press(page, name, hold=0.12, after=0.4):
    index, mask = KEYS[name]
    buttons = [0, 0]
    buttons[index] = mask
    page.evaluate(f"window.__padSend(0, 0, {buttons[0]}, {buttons[1]})")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def stick(page, direction, hold=0.15, after=0.3):
    x, y = NAV[direction]
    page.evaluate(f"window.__padSend({x}, {y}, 0, 0)")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def assert_released(page):
    held = pad(page)["held"]
    assert not any(held.values()), held


# ------------------------------------------------------------------ state probes

def frame(page):
    return page.query_selector("#strategicMapFrame").content_frame()


def game_sends(page):
    return page.evaluate("window.__gameSends.length") + frame(page).evaluate("window.__gameSends.length")


def server_view(page):
    """伺服器權威 state（client 端最新一份）：choice、組織、遷移次數、手牌、資源。"""
    p = me(page)
    c = pending(page)
    return {
        "choice": c and (c["choice_id"], c["choice_key"], sorted(t["town"] for t in c["towns"])),
        "orgs": org_counts(p), "moves": p.get("moves_left"), "hand": list(p["hand"]), "resources": p.get("resources"),
    }


def iframe_view(page, town):
    """戰略地圖 iframe：層級、town 是否精確置中、iframe 自己的焦點城鎮與選取（只讀）。"""
    return frame(page).evaluate("""(town) => {
      const p = map.latLngToContainerPoint(townDisplayLatLng(byName.get(town)));
      const s = map.getSize();
      const snap = window.__redlineControllerAdapter.snapshot();
      return { zoom: map.getZoom(), centered: Math.abs(p.x - s.x / 2) <= 1 && Math.abs(p.y - s.y / 2) <= 1,
               focusTown: snap.focusTown, selected: snap.selected, targets: snap.targets.map(t => t.town) };
    }""", town)


def hint_text(page, display):
    return page.evaluate("document.getElementById('lrLegend')?.textContent || ''" if display == "living-room"
                         else "document.getElementById('padHint')?.textContent || ''")


def action_state(page, display):
    """SL 結束後與直接導航必須一致的部分：controller scope／焦點、採用中的 snapshot（目標集合簽章）、可用的 A／Y 命令與提示。"""
    s = pad(page)
    m = s["map"]
    out = {
        "scope": s["scope"],
        "map": m and {k: m[k] for k in ("scope", "targets", "sig", "selected", "focusTown")},
        "hint": hint_text(page, display),
    }
    if display == "living-room":
        lr = s["livingRoom"]
        out.update({k: lr[k] for k in ("zone", "layer", "itemKey", "mapStage", "mapRows", "mapActs", "mapSelected", "mapPending", "browseTown")})
        out["hints"] = [(h["id"], h["key"], h["label"]) for h in lr["hints"]]
    else:
        out.update({k: s[k] for k in ("focusKind", "focusSig", "focusTown")})
    return out


def focused_town(page, display):
    s = pad(page)
    if display == "living-room":
        key = s["livingRoom"]["itemKey"] or ""
        return key[len("town:"):] if s["livingRoom"]["layer"] == "item" and key.startswith("town:") else None
    return s["focusTown"] if s["focusKind"] == "map" else None


def menu_open(page):
    return page.evaluate("(() => { const m = document.getElementById('lrFocusMenu'); return !!m && m.style.display !== 'none'; })()")


def menu_focus(page):
    return page.evaluate("document.querySelector('#lrFocusMenu .rl-pad-focus')?.id || null")


def last_ack(page, display):
    gate = pad(page)["livingRoom"] if display == "living-room" else pad(page)["shortcuts"]
    return gate.get("lastMapAck")


# ------------------------------------------------------------------ flows

def open_thinker_game(browser, app_url, display):
    # 測試牌局的開局事件是隨機的，少數事件會先開一個別的 pending choice：換一局，讓情境固定從思想家開始。
    for _ in range(6):
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx.add_init_script(SEND_SPY)  # 先於 mock bridge：真正的 WebSocket.prototype.send
        ctx.add_init_script(MOCK_BRIDGE)
        page = ctx.new_page()
        page.goto(app_url + f"/?display={display}")
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json=FIXTURE, timeout=10).json()
        assert setup.get("game_id") and setup.get("hand") == ["思想家"], setup
        page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        page.wait_for_function("window.RedlineController.getState().status === 'connected'")
        time.sleep(0.8)
        if pending(page) is None and me(page)["hand"] == ["思想家"]:
            return page
        ctx.close()
    pytest.fail("could not get a test game without an unrelated pending choice")


def play_thinker(page, display):
    """只用 controller：手牌思想家 → Y（既有「行動」）→ 思想家的必選地圖目標，控制器焦點落在地圖目標上。"""
    dismiss_modals(page)
    settle(page, display)
    if not pad(page)["padActive"]:
        press(page, "A")  # 第一下只放焦點
    if display == "living-room":
        if pad(page)["livingRoom"]["layer"] == "zone":
            press(page, "A")
        assert pad(page)["livingRoom"]["itemKey"].startswith("hand:0:思想家"), pad(page)["livingRoom"]
    else:
        assert pad(page)["focusSig"].startswith("DIV||hand|思想家"), pad(page)
    settle(page, display)
    press(page, "Y", after=0.2)
    choice = wait_until(lambda: pending(page))
    assert choice and choice["choice_key"] == "card_build_organization", choice
    towns = [t["town"] for t in choice["towns"]]
    assert TARGET in towns and FAR_TARGET in towns and NON_TARGET not in towns, towns
    assert wait_until(lambda: focused_choice_town(page, display) and (pad(page)["map"] or {}).get("scope") == "choice"), pad(page)
    settle(page, display)
    return choice


def menu_nav_to(page, element_id):
    """SL 聚焦選單內：依選項的畫面位置用搖桿移到 element_id（只送方向 frame）。"""
    for _ in range(40):
        current = menu_focus(page)
        if current == element_id:
            return
        delta = page.evaluate("""([a, b]) => {
          const r = id => { const e = document.getElementById(id).getBoundingClientRect(); return [(e.left + e.right) / 2, (e.top + e.bottom) / 2]; };
          const [ax, ay] = r(a); const [bx, by] = r(b); return [bx - ax, by - ay];
        }""", [current, element_id])
        dx, dy = delta
        primary = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
        stick(page, primary)
        if menu_focus(page) == current:  # 該方向沒有候選：改走另一軸
            stick(page, ("down" if dy > 0 else "up") if abs(dx) >= abs(dy) else ("right" if dx > 0 else "left"))
    pytest.fail(f"menu focus never reached {element_id}: {menu_focus(page)}")


def sl_focus(page, display, town):
    """SL → 天方 → town：開選單、搖桿移到分組、A、搖桿移到城鎮、A；回傳 focusTown 的 ack。"""
    settle(page, display)
    press(page, "SL")
    assert wait_until(lambda: menu_open(page) and menu_focus(page), timeout=4), pad(page)
    settle(page, display)
    menu_nav_to(page, GROUP_ID)
    press(page, "A")
    assert wait_until(lambda: page.evaluate("!!document.getElementById('lrFocusMenuBack')"), timeout=3), "天方 group did not open"
    settle(page, display)
    menu_nav_to(page, f"lrFocusTown-{town}")
    before = (last_ack(page, display) or {}).get("req") or 0
    press(page, "A")
    ack = wait_until(lambda: (lambda a: a if a and a["cmd"] == "focusTown" and a["req"] > before else None)(last_ack(page, display)), timeout=3)
    assert ack and ack["outcome"] == "success", (ack, pad(page))
    assert not menu_open(page)
    return ack


def wait_focus_snapshot(page, town, sig):
    """focusTown 的 ok:true 之後：iframe 精確置中 zoom 9，parent 採用了放大後的 snapshot（目標集合不變）。"""
    return wait_zoomed_snapshot(page, town, sig, FOCUS_ZOOM)


def wait_zoomed_snapshot(page, town, sig, zoom):
    def ready():
        m = pad(page)["map"]
        view = iframe_view(page, town)
        return m and view["zoom"] == zoom and view["centered"] and m["sig"] == sig and m
    m = wait_until(ready, timeout=3)
    assert m, {"map": pad(page)["map"], "iframe": iframe_view(page, town), "pad": pad(page)}
    assert m["scope"] == "choice"
    return m


def direct_to(page, display, town):
    """不開 SL：只用搖桿把地圖目標焦點移到 town（客廳＝清單上下；桌面＝依 iframe 目標座標的方向導航）。"""
    for _ in range(60):
        current = focused_town(page, display)
        if current == town:
            return
        if display == "living-room":
            rows = pad(page)["livingRoom"]["mapRows"]
            stick(page, "down" if rows.index(town) > rows.index(current) else "up")
            continue
        dx, dy = frame(page).evaluate("""([a, b]) => {
          const t = window.__redlineControllerAdapter.snapshot().targets;
          const p = t.find(x => x.town === a); const q = t.find(x => x.town === b); return [q.x - p.x, q.y - p.y];
        }""", [current, town])
        primary = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
        stick(page, primary)
        if focused_town(page, display) == current:
            stick(page, ("down" if dy > 0 else "up") if abs(dx) >= abs(dy) else ("right" if dx > 0 else "left"))
    pytest.fail(f"direct navigation never reached {town}: {pad(page)}")


def move_away(page, display):
    """搖桿離開目前的地圖目標（下一次 SL 才是一次完整的「從別處聚焦」）。"""
    start = focused_town(page, display)
    for direction in ("down", "up", "right", "left"):
        stick(page, direction)
        now = focused_town(page, display)
        if now and now != start:
            return now
    pytest.fail(f"could not move away from {start}: {pad(page)}")


def select_and_execute(page, display, town):
    """既有按鍵：A 選取（marker click）→ Y 建立組織（iframe 重驗後點既有按鈕）→ 思想家的下一段：3 次組織遷移。"""
    before = org_counts(me(page))
    settle(page, display)
    press(page, "A")
    assert wait_until(lambda: (pad(page)["map"] or {}).get("selected") == town, timeout=3), pad(page)
    assert pending(page) and pending(page)["choice_key"] == "card_build_organization", "A only selects"
    settle(page, display)
    press(page, "Y", after=0.2)
    assert wait_until(lambda: pending(page) is None and me(page)["moves_left"] == 3, timeout=6), (pending(page), me(page), pad(page))
    after = org_counts(me(page))
    assert after.get(town, 0) == before.get(town, 0) + 1, (town, before, after)
    assert "思想家" not in me(page)["hand"], me(page)["hand"]
    # 下一段（遷移）：地圖回到 move scope，控制器仍在地圖目標上可操作。
    assert wait_until(lambda: (pad(page)["map"] or {}).get("scope") == "move", timeout=4), pad(page)
    if display == "living-room":
        assert wait_until(lambda: pad(page)["livingRoom"]["mapStage"] in ("source", "destination")
                          and pad(page)["livingRoom"]["mapRows"]), pad(page)["livingRoom"]
    else:
        assert wait_until(lambda: pad(page)["focusKind"] == "map"), pad(page)
    assert page.evaluate("window.__trustedPointer") == 0, "game was operated with the mouse"


# ------------------------------------------------------------------ tests

@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_direct_joycon_riyadh_control(browser, app_url, display):
    """對照組：思想家 pending choice 後不開 SL，直接用 Joy-Con 選利雅德，之後選取與執行都正常。"""
    page = open_thinker_game(browser, app_url, display)
    try:
        play_thinker(page, display)
        direct_to(page, display, TARGET)
        settle(page, display)
        state = action_state(page, display)
        assert state["map"] and state["map"]["scope"] == "choice" and state["map"]["focusTown"] == TARGET, state
        if display == "living-room":
            assert (state["zone"], state["layer"], state["itemKey"], state["mapStage"]) == ("maplist", "item", f"town:{TARGET}", "choice"), state
            assert ("mapAct", "Y", f"建立組織 {TARGET}") in state["hints"], state
        else:
            assert (state["focusKind"], state["focusSig"]) == ("map", f"town:{TARGET}"), state
            assert f"Y 建立組織 {TARGET}" in state["hint"], state
        select_and_execute(page, display, TARGET)
    finally:
        page.context.close()


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_sl_riyadh_matches_direct_navigation_and_executes(browser, app_url, display):
    """pending choice → SL → 天方 → 利雅德 → focusTown ok:true＋放大後的 snapshot → 放開按鍵 → 與直接導航同一個可操作狀態；
    SL 不送任何遊戲 mutation。整條 SL 路徑重複 5 次（使用者回報「重複同一路徑必定卡住」），最後一次之後直接選取並執行。"""
    page = open_thinker_game(browser, app_url, display)
    try:
        play_thinker(page, display)
        sig = pad(page)["map"]["sig"]
        sends = game_sends(page)
        server = server_view(page)
        reference = None
        for cycle in range(SL_CYCLES):
            if cycle:
                move_away(page, display)
            sl_focus(page, display, TARGET)
            wait_focus_snapshot(page, TARGET, sig)
            assert_released(page)
            settle(page, display)
            state = action_state(page, display)
            assert focused_town(page, display) == TARGET, (cycle, state)
            assert iframe_view(page, TARGET)["focusTown"] == TARGET, "the ring stays on the focused target"
            # SL 只改地圖相機與焦點：沒有任何遊戲 WebSocket 訊息，伺服器權威 state（choice／組織／遷移／手牌／資源）不變。
            assert game_sends(page) == sends, (cycle, page.evaluate("window.__gameSends"), frame(page).evaluate("window.__gameSends"))
            assert server_view(page) == server, cycle
            assert state["map"]["selected"] is None, "focusing never selects"
            if cycle == 0:
                # 同一份 fixture、同一個 pending choice 的對照：離開後直接用搖桿導航回利雅德。
                move_away(page, display)
                direct_to(page, display, TARGET)
                settle(page, display)
                reference = action_state(page, display)
                assert reference["map"]["focusTown"] == TARGET, reference
            assert state == reference, (cycle, state, reference)
        select_and_execute(page, display, TARGET)
    finally:
        page.context.close()


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_sl_non_target_town_is_browse_only(browser, app_url, display):
    """同一個思想家 choice 下 SL 聚焦到不是目標的城鎮（伊斯坦堡已有組織）：只建立瀏覽焦點，不成為 action target；
    放大後的 snapshot 仍被採用（瀏覽焦點不會因 snapshot 作廢而被放掉），A／Y 不選取、不送任何遊戲 mutation。"""
    page = open_thinker_game(browser, app_url, display)
    try:
        play_thinker(page, display)
        sig = pad(page)["map"]["sig"]
        sends = game_sends(page)
        server = server_view(page)
        sl_focus(page, display, NON_TARGET)
        wait_focus_snapshot(page, NON_TARGET, sig)
        assert_released(page)
        time.sleep(0.5)  # 80ms reconcile／50ms render 都跑過：瀏覽焦點仍在
        s = pad(page)
        assert s["map"]["focusTown"] != NON_TARGET and NON_TARGET not in iframe_view(page, NON_TARGET)["targets"]
        assert iframe_view(page, NON_TARGET)["focusTown"] != NON_TARGET, "a browse town is never the action focus"
        if display == "living-room":
            lr = s["livingRoom"]
            assert (lr["zone"], lr["layer"], lr["browseTown"]) == ("maplist", "zone", NON_TARGET), lr
            assert NON_TARGET not in lr["mapRows"] and lr["mapStage"] == "choice", lr
        else:
            assert (s["focusKind"], s["focusSig"], s["focusTown"]) == ("browse", f"browse:{NON_TARGET}", NON_TARGET), s
        settle(page, display)
        for key in ("Y", "A"):
            press(page, key, after=0.6)
            assert_released(page)
            assert (pad(page)["map"] or {}).get("selected") is None, (key, pad(page))
            assert iframe_view(page, NON_TARGET)["selected"] is None, key
            assert game_sends(page) == sends, (key, page.evaluate("window.__gameSends"), frame(page).evaluate("window.__gameSends"))
            assert server_view(page) == server, key
            settle(page, display)
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()


def target_x(page, town):
    return frame(page).evaluate("(t) => window.__redlineControllerAdapter.snapshot().targets.find(x => x.town === t).x", town)


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_sl_riyadh_then_zr_to_max_zoom_keeps_snapshot_and_executes(browser, app_url, display):
    """SL → 天方 → 利雅德（zoom 9）→ ZR 放大到循環最大層級 10（中心仍是利雅德）：北美目標超過舊的 ±10 萬 px 上限，
    parent 仍採用 snapshot（目標集合不變、焦點仍在利雅德）；ZR 與 SL 都不送遊戲 mutation，之後 A 選取、Y 建立照常。"""
    page = open_thinker_game(browser, app_url, display)
    try:
        play_thinker(page, display)
        sig = pad(page)["map"]["sig"]
        sends = game_sends(page)
        server = server_view(page)
        sl_focus(page, display, TARGET)
        wait_focus_snapshot(page, TARGET, sig)
        far9 = target_x(page, FAR_TARGET)
        assert 50000 < abs(far9) < 100000, f"{FAR_TARGET} at the SL focus zoom: {far9}"
        settle(page, display)
        press(page, "ZR")
        m = wait_zoomed_snapshot(page, TARGET, sig, ZR_MAX_ZOOM)
        assert_released(page)
        far10 = target_x(page, FAR_TARGET)
        assert abs(far10) >= 100000, f"the regression needs a target beyond the old 100000px bound: {far10}"
        assert m["focusTown"] == TARGET and m["selected"] is None, m
        settle(page, display)
        assert focused_town(page, display) == TARGET, pad(page)
        assert game_sends(page) == sends, (page.evaluate("window.__gameSends"), frame(page).evaluate("window.__gameSends"))
        assert server_view(page) == server
        select_and_execute(page, display, TARGET)
    finally:
        page.context.close()
