"""遊戲選單（遊戲中按住搖桿按鈕 2 秒）的 Browser（Playwright／Chromium）regression。

伺服器是真的 uvicorn（ENABLE_TEST_ROUTES=true，隨機埠；沿用 test_propagandist_joycon_browser 的 fixture），真實的
index.html／app.js／controller_*.js。Joy-Con 是 mock bridge WebSocket，用 bridge 的真實訊息格式送 synthetic frame
（右 Joy-Con＝舊版 {x, y, buttons}；左 Joy-Con＝v2 roster＋frame，左手按下搖桿已由 bridge 正規化成邏輯 STICK）。
這不是實體 Joy-Con 驗證。

mock bridge 每 33ms 重送目前的按鍵狀態（與 bridge 30Hz 相同），所以「按住」就是連續的 frame。遊戲 WebSocket 的 send
全部記錄（SEND_SPY），證明開啟、導覽、取消都不送任何遊戲 mutation；伺服器 state 前後不變。`/new-game` 由 Playwright
route 攔截（不打到伺服器、不建立或破壞任何房間），只證明確認後導向既有正式入口。

驗證：
  1. 不到 2 秒放開不開；搖桿離開中央立即取消（回中也不恢復）；滿 2 秒開啟置中的「遊戲選單」。
  2. 開啟時 STICK 仍按住：放開前 A 不作用（held-button 不穿透）。
  3. 搖桿上下導覽（不循環）、左右與其他鍵不作用；B 返回遊戲並還原開啟前的焦點。
  4. Joy-Con 功能表＝既有 Joy-Con 說明圖；重新開始＝第二層確認（明確顯示離開目前遊戲）；按住的 A／B 不連續觸發兩層；
     確認層 B 回到遊戲選單（焦點在重新開始），選單 B 返回遊戲；選重新開始的 A 一直按住不會確認，放開後新的 A
     才點「確認重新開始」導向 /new-game。
  5. 左 Joy-Con（v2）同樣可開啟；其他 Joy-Con 的 frame 不能開啟；其他 overlay／交接遮罩期間不開啟。
  6. 滑鼠也能操作每一項（背景點擊＝返回）。

--redline-evidence-dir（或 REDLINE_EVIDENCE_DIR）有設定時，另存 1280×720 截圖與機器可讀 state proof（JSON）。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from test_joycon_help_button_browser import LEFT_ID, MOCK_BRIDGE_LEFT
from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    MOCK_BRIDGE, app_url, browser, dismiss_modals, hint, me, pad, pending, settle, wait_until,
)
from test_thinker_sl_focus_joycon_browser import SEND_SPY

KEYS = {"A": (0, 0x08), "B": (0, 0x04), "X": (0, 0x02), "Y": (0, 0x01), "SL": (0, 0x20), "SR": (0, 0x10), "R": (0, 0x40),
        "ZR": (0, 0x80), "PLUS": (1, 0x02), "CAPTURE": (1, 0x40), "STICK": (1, 0x04)}
NAV = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}  # y>0＝畫面向下（controller_core.stickDirection）
STICK_B1 = KEYS["STICK"][1]
OTHER_LEFT = "L24802-0a1b2c3d"
NEW_GAME_STUB = "<!doctype html><html><body>new-game route intercepted by test</body></html>"


# ------------------------------------------------------------------ controller input（只送 bridge frame）

def send(page, x=0.0, y=0.0, *names):
    b = [0, 0]
    for name in names:
        index, mask = KEYS[name]
        b[index] |= mask
    page.evaluate(f"window.__padSend({x}, {y}, {b[0]}, {b[1]})")


def press(page, name, hold=0.12, after=0.4):
    send(page, 0, 0, name)
    time.sleep(hold)
    send(page)
    time.sleep(after)


def stick(page, direction, hold=0.15, after=0.35):
    x, y = NAV[direction]
    send(page, x, y)
    time.sleep(hold)
    send(page)
    time.sleep(after)


def hold_stick(page, seconds):
    """按住搖桿按鈕（搖桿在中央）seconds 秒，不放開。"""
    send(page, 0, 0, "STICK")
    time.sleep(seconds)


def release(page, after=0.4):
    send(page)
    time.sleep(after)


def open_menu(page):
    settle(page, "desktop")
    hold_stick(page, 2.4)
    assert wait_until(lambda: menu(page)["level"] == "menu", timeout=2), menu(page)
    release(page)
    assert wait_until(lambda: menu(page)["gate"] == [], timeout=2), menu(page)
    settle(page, "desktop")


# ------------------------------------------------------------------ state probes

def menu(page):
    return pad(page)["gameMenu"]


def focus_id(page):
    return page.evaluate("""() => { const s = window.RedlineController.getState();
      const el = document.activeElement; return { sig: s.focusSig, active: el && el.id || null,
      ring: !!(el && el.classList.contains('rl-pad-focus')) }; }""")


def shown(page, element_id):
    return page.evaluate(f"(() => {{ const el = document.getElementById({json.dumps(element_id)});"
                         " return !!el && getComputedStyle(el).display !== 'none'; })()")


def game_sends(page):
    return page.evaluate("window.__gameSends.length")


def wait_new_game(page, hits):
    """等到導向 /new-game。route handler 只會在 Playwright（sync API）呼叫等待中執行：time.sleep 的輪詢（wait_until
    搭配只讀 hits 的 predicate）永遠不會派送 route 事件，所以 hits 會一直是 []。wait_for_url 會派送事件並等導覽完成。"""
    page.wait_for_url("**/new-game", timeout=5000)
    assert len(hits) == 1 and hits[0].endswith("/new-game"), (hits, page.url)


def pump(page, seconds):
    """等待 seconds 秒並讓 Playwright 派送事件（被攔截的 /new-game 會在這段時間記進 hits）。"""
    page.wait_for_timeout(int(seconds * 1000))


def authoritative(page):
    """不可被開啟／導覽／取消改變：伺服器 state 中自己的資源、手牌、組織、行動，以及行動者與 pending choice。"""
    p = me(page)
    s = page.evaluate("(() => { const s = window.lastGameState; return { current: s.current_player ?? null,"
                      " turn: s.turn ?? null, round: s.round ?? null, log: (s.log || []).length }; })()")
    keys = ("hand", "resources", "orgs", "actions_left", "moves_left", "deck_count", "discard_count")
    return {"player": {k: p.get(k) for k in keys}, "pending": pending(page), **s}


def view(page):
    return page.evaluate("document.querySelector('.game-tab.active[data-view]')?.dataset.view || null")


def menu_layout(page):
    return page.evaluate("""() => {
      const box = el => { const b = el.getBoundingClientRect(); return { cx: b.left + b.width / 2, cy: b.top + b.height / 2, w: b.width, h: b.height }; };
      return { glass: box(document.querySelector('#gameMenuModal .game-menu-glass')), stage: box(document.getElementById('designStage')),
        options: [...document.querySelectorAll('#gameMenuModal .game-menu-option')].map(b => b.textContent.trim()) };
    }""")


# ------------------------------------------------------------------ harness

def open_game(browser, app_url, bridge=MOCK_BRIDGE):
    """回傳 (page, new_game_hits)：/new-game 一律由 route 攔截（hits 記下 URL），不打到伺服器。"""
    for _ in range(6):
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx.add_init_script(SEND_SPY)  # 先於 mock bridge：記錄真正的 WebSocket.prototype.send
        ctx.add_init_script(bridge)
        hits: list[str] = []

        def intercept(route, _request, hits=hits):
            hits.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=NEW_GAME_STUB)

        ctx.route("**/new-game", intercept)
        page = ctx.new_page()
        page.goto(app_url + "/?display=desktop")
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json={"faction_id": "aomen"}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        page.wait_for_function("window.RedlineController.getState().status === 'connected'")
        time.sleep(0.8)
        if pending(page) is None:
            return page, hits
        ctx.close()
    raise AssertionError("could not get a test game without an unrelated pending choice")


def activate_pad(page):
    dismiss_modals(page)
    settle(page, "desktop")
    if not pad(page)["padActive"]:
        stick(page, "right")  # 第一下只放焦點（不執行）
    settle(page, "desktop")
    assert pad(page)["padActive"] and pad(page)["scope"] in ("page", "map"), pad(page)


class Evidence:
    def __init__(self, request, name):
        root = request.config.getoption("--redline-evidence-dir") or os.environ.get("REDLINE_EVIDENCE_DIR")
        self.dir = Path(root) if root else None
        self.name = name
        self.steps = []
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def record(self, page, hits, step, shot=None):
        entry = {"step": step, "gameMenu": menu(page), "scope": pad(page)["scope"], "focus": focus_id(page), "hint": hint(page),
                 "gameSends": game_sends(page), "newGameHits": list(hits), "view": view(page)}
        if self.dir and shot:
            path = self.dir / f"{self.name}_{shot}_1280x720.png"
            page.screenshot(path=str(path))
            entry["screenshot"] = str(path)
            entry["viewport"] = page.viewport_size
        self.steps.append(entry)

    def write(self, extra=None):
        if self.dir:
            (self.dir / f"{self.name}_state.json").write_text(
                json.dumps({"test": self.name, "steps": self.steps, **(extra or {})}, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ tests

def test_hold_threshold_neutral_cancel_navigation_settings_and_two_level_back(browser, app_url, request):
    ev = Evidence(request, "right_joycon_menu")
    page, hits = open_game(browser, app_url)
    try:
        activate_pad(page)
        sends = game_sends(page)
        before = authoritative(page)
        view_before = view(page)
        ev.record(page, hits, "game-ready", "00_game")

        # 1a. 不到 2 秒：累積中顯示提示；放開不開。
        hold_stick(page, 0.9)
        assert menu(page)["holding"] is True, menu(page)
        assert "繼續按住搖桿按鈕" in hint(page), hint(page)
        ev.record(page, hits, "holding-0.9s", "01_holding_hint")
        hold_stick(page, 0.5)
        release(page)
        assert menu(page)["level"] is None and menu(page)["holding"] is False, menu(page)
        # 1b. 按住中推離中央：立即取消；回中繼續按住也不恢復。
        hold_stick(page, 1.0)
        send(page, 0.9, 0, "STICK")
        time.sleep(0.15)
        assert menu(page)["holding"] is False and menu(page)["latched"] is True, menu(page)
        hold_stick(page, 2.2)
        assert menu(page)["level"] is None, menu(page)
        release(page)
        settle(page, "desktop")
        page_focus = pad(page)["focusSig"]  # 推離中央是一般方向輸入（只移焦點）
        assert page_focus, pad(page)
        # 1c. 滿 2 秒：開啟；STICK 仍按住時任何按鍵不作用（同時按 A 不會觸發「返回遊戲」）。
        hold_stick(page, 2.4)
        assert wait_until(lambda: menu(page)["level"] == "menu", timeout=2), menu(page)
        assert menu(page)["gate"] == ["STICK"], menu(page)
        assert "放開搖桿按鈕後操作" in hint(page), hint(page)
        send(page, 0, 0, "STICK", "A")
        time.sleep(0.3)
        send(page, 0, 0, "STICK")
        time.sleep(0.2)
        assert menu(page)["level"] == "menu", "held stick click must block A"
        release(page)
        assert wait_until(lambda: menu(page)["gate"] == [], timeout=2), menu(page)
        settle(page, "desktop")
        f = focus_id(page)
        assert f["sig"] == "#gameMenuResumeBtn" and f["active"] == "gameMenuResumeBtn" and f["ring"], f
        layout = menu_layout(page)
        assert layout["options"] == ["返回遊戲", "Joy-Con 功能表", "重新開始…"], layout
        assert abs(layout["glass"]["cx"] - layout["stage"]["cx"]) < 8 and abs(layout["glass"]["cy"] - layout["stage"]["cy"]) < 8, layout
        assert "遊戲選單" in hint(page) and "B 返回遊戲" in hint(page), hint(page)
        ev.record(page, hits, "menu-open", "02_menu_open")

        # 3. 上下導覽（不循環）；左右與其他鍵不作用。
        stick(page, "down")
        assert focus_id(page)["sig"] == "#gameMenuSettingsBtn"
        stick(page, "down")
        assert focus_id(page)["sig"] == "#gameMenuRestartBtn"
        ev.record(page, hits, "nav-restart", "03_menu_nav_restart")
        stick(page, "down")
        assert focus_id(page)["sig"] == "#gameMenuRestartBtn"
        for direction in ("left", "right"):
            stick(page, direction)
            assert focus_id(page)["sig"] == "#gameMenuRestartBtn", direction
        for key in ("X", "Y", "R", "SR", "SL", "ZR", "PLUS", "CAPTURE"):
            press(page, key)
            assert menu(page)["level"] == "menu" and pad(page)["scope"] == "gameMenuModal", key
            assert focus_id(page)["sig"] == "#gameMenuRestartBtn", key
        assert not shown(page, "lrConfirmModal") and not shown(page, "lrFocusMenu")
        assert view(page) == view_before
        stick(page, "up")
        stick(page, "up")
        assert focus_id(page)["sig"] == "#gameMenuResumeBtn"
        stick(page, "up")
        assert focus_id(page)["sig"] == "#gameMenuResumeBtn"
        # B＝返回遊戲：選單關閉、焦點回到開啟前的位置。
        press(page, "B")
        assert wait_until(lambda: menu(page)["level"] is None)
        settle(page, "desktop")
        assert pad(page)["scope"] in ("page", "map") and pad(page)["focusSig"] == page_focus, (pad(page), page_focus)
        ev.record(page, hits, "b-returned-to-game")

        # 4a. Joy-Con 功能表＝既有 Joy-Con 說明圖（B 照既有流程關閉）。
        open_menu(page)
        stick(page, "down")
        press(page, "A")
        assert wait_until(lambda: shown(page, "joyconHelpModal")), pad(page)
        assert menu(page)["level"] is None
        settle(page, "desktop")
        assert pad(page)["scope"] == "joyconHelpModal"
        ev.record(page, hits, "settings-opened-help", "04_settings_help")
        press(page, "B")
        assert wait_until(lambda: not shown(page, "joyconHelpModal"))
        settle(page, "desktop")
        assert pad(page)["scope"] in ("page", "map"), pad(page)

        # 4b. 重新開始 → 第二層確認；選這一項的 A 按住 1 秒也不會直接確認。
        open_menu(page)
        stick(page, "down")
        stick(page, "down")
        press(page, "A", hold=1.0)
        assert wait_until(lambda: menu(page)["level"] == "confirm"), menu(page)
        settle(page, "desktop")
        assert hits == []
        f = focus_id(page)
        assert f["sig"] == "#gameMenuConfirmOkBtn" and f["ring"], f
        body = page.evaluate("document.getElementById('gameMenuConfirmModal').innerText")
        assert "離開目前遊戲" in body and "確認重新開始" in body and "返回選單" in body, body
        assert "A 確認重新開始" in hint(page) and "B 返回遊戲選單" in hint(page), hint(page)
        ev.record(page, hits, "restart-confirm", "05_restart_confirm")
        # 確認層 B（按住 1 秒）：回到遊戲選單、焦點在「重新開始」；同一個按住的 B 不會接著關閉選單。
        press(page, "B", hold=1.0)
        assert wait_until(lambda: menu(page)["level"] == "menu"), menu(page)
        time.sleep(0.3)
        assert menu(page)["level"] == "menu", menu(page)
        settle(page, "desktop")
        assert focus_id(page)["sig"] == "#gameMenuRestartBtn", focus_id(page)
        ev.record(page, hits, "confirm-b-back-to-menu", "06_confirm_back_to_menu")
        # 選單 B：返回遊戲（兩層返回）。
        press(page, "B")
        assert wait_until(lambda: menu(page)["level"] is None)
        settle(page, "desktop")
        assert pad(page)["scope"] in ("page", "map"), pad(page)

        # 開啟、導覽、取消、設定都沒有遊戲 mutation，伺服器 state 不變。
        assert game_sends(page) == sends, page.evaluate("window.__gameSends")
        assert authoritative(page) == before
        assert hits == []
        ev.record(page, hits, "after-cancel-no-mutation")

        # 4c. 選「重新開始」的 A 一直按住：確認層出現但 A 被 release gate 擋住，持續按住不會重新開始。
        open_menu(page)
        stick(page, "down")
        stick(page, "down")
        assert focus_id(page)["sig"] == "#gameMenuRestartBtn", focus_id(page)
        send(page, 0, 0, "A")
        assert wait_until(lambda: menu(page)["level"] == "confirm"), menu(page)
        assert menu(page)["gate"] == ["A"], menu(page)
        pump(page, 1.2)  # 仍按住 A（mock bridge 每 33ms 重送）；期間有導覽的話 route 會記進 hits
        assert hits == [] and not page.url.endswith("/new-game"), (hits, page.url)
        assert menu(page)["level"] == "confirm" and menu(page)["gate"] == ["A"], menu(page)
        # 放開 A：gate 清空，焦點在「確認重新開始」；仍沒有任何遊戲 mutation 或導覽。
        release(page)
        assert wait_until(lambda: menu(page)["gate"] == [], timeout=2), menu(page)
        settle(page, "desktop")
        f = focus_id(page)
        assert f["sig"] == "#gameMenuConfirmOkBtn" and f["active"] == "gameMenuConfirmOkBtn" and f["ring"], f
        pump(page, 0.2)
        assert menu(page)["level"] == "confirm" and hits == [], (menu(page), hits)
        assert game_sends(page) == sends
        ev.record(page, hits, "confirm-before-a")
        # 新的 A 按下：點焦點中的「確認重新開始」→ 既有 /new-game（route 攔截，不打到伺服器）。
        send(page, 0, 0, "A")
        wait_new_game(page, hits)
        ev.steps.append({"step": "confirm-a-navigated", "newGameHits": list(hits), "url": page.url})
        ev.write({"before": before, "pageFocus": page_focus, "layout": layout,
                  "note": "synthetic mock bridge frames (real bridge message format), not a physical Joy-Con"})
    finally:
        page.context.close()


def test_left_joycon_opens_and_other_controllers_and_overlays_cannot(browser, app_url, request):
    ev = Evidence(request, "left_joycon_menu")
    page, hits = open_game(browser, app_url, MOCK_BRIDGE_LEFT)
    try:
        assert wait_until(lambda: pad(page)["controller"]["side"] == "left"), pad(page)["controller"]
        activate_pad(page)
        sends = game_sends(page)
        # 其他 Joy-Con（不是本分頁綁定的那一支）按住搖桿 2.5 秒：frame 被丟棄，不開啟。
        page.evaluate(f"""() => {{
          const live = window.__mockBridges.filter(b => b.readyState === 1).pop();
          window.__otherTimer = setInterval(() => live.onmessage({{ data: JSON.stringify({{ type: 'frame', v: 2,
            controller: {json.dumps(OTHER_LEFT)}, side: 'left', epoch: 1, x: 0, y: 0, buttons: [0, {STICK_B1}] }}) }}), 33);
        }}""")
        time.sleep(2.5)
        page.evaluate("clearInterval(window.__otherTimer)")
        assert menu(page)["level"] is None and menu(page)["holding"] is False, menu(page)
        assert pad(page)["controller"]["owned"] == LEFT_ID

        # 其他 overlay 開著（既有 Joy-Con 說明圖）：不開啟。
        page.evaluate("openJoyconHelp()")
        settle(page, "desktop")
        assert menu(page)["blocker"] == "overlay", menu(page)
        hold_stick(page, 2.5)
        assert menu(page)["level"] is None, menu(page)
        release(page)
        press(page, "B")
        assert wait_until(lambda: not shown(page, "joyconHelpModal"))
        settle(page, "desktop")

        # 客廳輪流交接遮罩：不開啟。
        page.evaluate("document.documentElement.dataset.hotseat = 'masked'")
        assert menu(page)["blocker"] == "handoff", menu(page)
        hold_stick(page, 2.5)
        assert menu(page)["level"] is None, menu(page)
        release(page)
        page.evaluate("delete document.documentElement.dataset.hotseat")
        settle(page, "desktop")

        # 左 Joy-Con 按下搖桿（bridge 正規化成邏輯 STICK）：滿 2 秒開啟；B 返回遊戲。
        assert menu(page)["blocker"] is None, menu(page)
        open_menu(page)
        assert focus_id(page)["sig"] == "#gameMenuResumeBtn"
        ev.record(page, hits, "left-menu-open", "01_left_menu_open")
        press(page, "B")
        assert wait_until(lambda: menu(page)["level"] is None)
        assert game_sends(page) == sends and hits == []
        ev.write({"note": "synthetic mock bridge v2 frames, not a physical Joy-Con"})
    finally:
        page.context.close()


def test_mouse_operates_every_menu_item(browser, app_url, request):
    ev = Evidence(request, "mouse_menu")
    page, hits = open_game(browser, app_url)
    try:
        activate_pad(page)
        sends = game_sends(page)
        open_menu(page)
        page.click("#gameMenuRestartBtn")
        assert wait_until(lambda: menu(page)["level"] == "confirm")
        page.click("#gameMenuConfirmCancelBtn")
        assert wait_until(lambda: menu(page)["level"] == "menu")
        page.click("#gameMenuRestartBtn")
        assert wait_until(lambda: menu(page)["level"] == "confirm")
        page.mouse.click(30, 690)  # 確認層背景＝返回遊戲選單（不會重新開始）
        assert wait_until(lambda: menu(page)["level"] == "menu")
        page.mouse.click(30, 690)  # 選單背景＝返回遊戲
        assert wait_until(lambda: menu(page)["level"] is None)
        open_menu(page)
        page.click("#gameMenuSettingsBtn")
        assert wait_until(lambda: shown(page, "joyconHelpModal")) and menu(page)["level"] is None
        page.click("#joyconHelpCloseBtn")
        assert wait_until(lambda: not shown(page, "joyconHelpModal"))
        open_menu(page)
        page.click("#gameMenuResumeBtn")
        assert wait_until(lambda: menu(page)["level"] is None)
        assert game_sends(page) == sends and hits == []
        open_menu(page)
        page.click("#gameMenuRestartBtn")
        assert wait_until(lambda: menu(page)["level"] == "confirm")
        page.click("#gameMenuConfirmOkBtn")
        wait_new_game(page, hits)
        ev.steps.append({"step": "mouse-confirm-navigated", "newGameHits": list(hits)})
        ev.write()
    finally:
        page.context.close()
