"""導覽列「Joy-Con 說明」按鈕的 Browser（Playwright／Chromium）regression。

伺服器是真的 uvicorn（ENABLE_TEST_ROUTES=true，隨機埠；沿用 test_propagandist_joycon_browser 的 fixture），
真實的 index.html／app.js／controller_*.js。Joy-Con 是 mock bridge WebSocket（synthetic frame，不是實體 Joy-Con）：
右 Joy-Con 用舊版 frame 協定；左 Joy-Con 用 bridge v2 roster＋frame（bridge 已把左手 L／SL 正規化成邏輯 R／SR）。

驗證：
  1. 六個區段分頁不變；R 依序經過區段後停在 Joy-Con 說明按鈕（只放焦點、不開圖），再按 R 回到指揮中心；SR 反向可到達。
  2. A 開啟說明圖：圖片 src 正確、已載入 1280×960、可見且保持 4:3；modal 開著時 R／SR、SL 不穿透。
  3. B 關閉並把焦點（搖桿焦點與原生 focus）還回說明按鈕。
  4. 滑鼠點按鈕開啟、點 × 關閉；Esc 也關閉。
  5. 左 Joy-Con：L＝R、SL＝SR 行為相同。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    MOCK_BRIDGE, app_url, browser, dismiss_modals, pad, settle, stick, wait_until,
)

KEYS = {"A": (0, 0x08), "B": (0, 0x04), "Y": (0, 0x01), "SL": (0, 0x20), "SR": (0, 0x10), "R": (0, 0x40)}
SIX_TABS = ["指揮中心", "戰略地圖", "戰況紀錄", "我的陣營", "事件卡"]
IMAGE_PATH = "/static/help/joycon-function-table.jpg"
LEFT_ID = "L24801-0a1b2c3d"
# 實頁截圖（UI 證據）；預設寫到系統暫存目錄。
SHOT_DIR = Path(os.environ.get("REDLINE_SHOT_DIR", "/tmp"))

# 左 Joy-Con：bridge v2。連上後送 roster（本分頁擁有這支左手），之後的 frame 帶 v2 身份。
MOCK_BRIDGE_LEFT = MOCK_BRIDGE.replace(
    "live.onmessage({ data: JSON.stringify({ x, y, buttons: [b0, b1] }) });",
    "if (!live.__roster) { live.__roster = true; live.onmessage({ data: JSON.stringify({ type: 'roster', v: 2, owned: '__ID__', "
    "controllers: [{ id: '__ID__', side: 'left', status: 'active', owner: 'you' }] }) }); }\n"
    "    live.onmessage({ data: JSON.stringify({ type: 'frame', v: 2, controller: '__ID__', side: 'left', epoch: 1, x, y, buttons: [b0, b1] }) });",
).replace("__ID__", LEFT_ID)
assert MOCK_BRIDGE_LEFT != MOCK_BRIDGE


def press(page, name, hold=0.12, after=0.45):
    index, mask = KEYS[name]
    buttons = [0, 0]
    buttons[index] = mask
    page.evaluate(f"window.__padSend(0, 0, {buttons[0]}, {buttons[1]})")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def open_game(browser, app_url, bridge=MOCK_BRIDGE):
    for _ in range(6):
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx.add_init_script(bridge)
        page = ctx.new_page()
        page.goto(app_url + "/?display=desktop")
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json={"faction_id": "aomen"}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        page.wait_for_function("window.RedlineController.getState().status === 'connected'")
        time.sleep(0.8)
        if page.evaluate("window.lastGameState.pending_choice") is None:
            return page
        ctx.close()
    raise AssertionError("could not get a test game without an unrelated pending choice")


STOP_JS = """() => {
  const s = window.RedlineController.getState();
  if (s.focusKind === 'help') return 'help';
  if (s.scope === 'eventRevealModal') return 'event';
  if (s.scope === 'eraAchievementModal') return 'era';
  if (s.scope !== 'page' && s.scope !== 'map') return 'modal:' + s.scope;
  return 'view:' + (document.querySelector('.game-tab.active[data-view]') || {dataset: {}}).dataset.view;
}"""


def stop(page):
    return page.evaluate(STOP_JS)


def help_modal_open(page):
    return page.evaluate("getComputedStyle(document.getElementById('joyconHelpModal')).display !== 'none'")


def help_button_focused(page):
    return page.evaluate("""() => {
      const b = document.getElementById('joyconHelpBtn');
      return window.RedlineController.getState().focusKind === 'help' && b.classList.contains('rl-pad-focus')
        && document.activeElement === b;
    }""")


def activate_pad(page):
    dismiss_modals(page)
    settle(page, "desktop")
    if not pad(page)["padActive"]:
        stick(page, "up")  # 第一下只放焦點
    settle(page, "desktop")
    assert pad(page)["padActive"], pad(page)


def ring_to_help(page, key="R", limit=12):
    visited = [stop(page)]
    for _ in range(limit):
        press(page, key)
        settle(page, "desktop")
        visited.append(stop(page))
        if visited[-1] == "help":
            return visited
    raise AssertionError(visited)


def test_nav_has_six_sections_plus_help_button(browser, app_url):
    page = open_game(browser, app_url)
    try:
        tabs = page.evaluate("[...document.querySelectorAll('#gameTabs > .game-tab')].map(t => t.textContent.trim())")
        assert tabs == SIX_TABS, tabs  # 時代關卡分頁在 #activeEraTabs 內
        btn = page.evaluate("""() => { const b = document.getElementById('joyconHelpBtn'); const r = b.getBoundingClientRect();
          return { cls: b.className, name: b.getAttribute('aria-label'), text: b.textContent.trim(), w: r.width, h: r.height,
                   inTabs: !!b.closest('#gameTabs'), visible: getComputedStyle(b).display !== 'none' }; }""")
        assert btn["name"] == "Joy-Con 說明" and "Joy-Con 說明" in btn["text"], btn
        assert "game-tab" not in btn["cls"], btn  # 不是第七個遊戲頁面
        assert btn["inTabs"] and btn["visible"] and btn["w"] > 40 and btn["h"] > 20, btn
        # 圖片資產存在且是原檔
        r = requests.get(app_url + IMAGE_PATH, timeout=10)
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/jpeg") and len(r.content) > 100_000
    finally:
        page.context.close()


def test_ring_focuses_help_without_opening_then_a_opens_b_closes_and_restores(browser, app_url):
    page = open_game(browser, app_url)
    try:
        activate_pad(page)
        start = stop(page)
        assert start == "view:command", start
        visited = ring_to_help(page, "R")
        sections = [v for v in visited if v.startswith("view:")]
        assert sections[:4] == ["view:command", "view:map", "view:log", "view:myFaction"], visited
        assert visited[-1] == "help" and visited.count("help") == 1, visited
        # 1/2. R 只聚焦按鈕，不開圖，也不切頁（留在最後一個區段的畫面）
        assert help_button_focused(page), pad(page)
        assert not help_modal_open(page)
        assert "Joy-Con 說明" in page.evaluate("document.getElementById('padHint').textContent")

        # A 開圖
        press(page, "A")
        assert wait_until(lambda: help_modal_open(page)), pad(page)
        settle(page, "desktop")
        assert pad(page)["scope"] == "joyconHelpModal"
        page.wait_for_function("document.getElementById('joyconHelpImage').complete && document.getElementById('joyconHelpImage').naturalWidth > 0")
        img = page.evaluate("""() => { const i = document.getElementById('joyconHelpImage'); const r = i.getBoundingClientRect();
          return { src: new URL(i.currentSrc || i.src).pathname, nw: i.naturalWidth, nh: i.naturalHeight, w: r.width, h: r.height,
                   alt: i.alt, top: r.top, left: r.left }; }""")
        assert img["src"] == IMAGE_PATH and (img["nw"], img["nh"]) == (1280, 960), img
        assert img["w"] > 300 and abs(img["w"] / img["h"] - 4 / 3) < 0.01, img
        assert "Joy-Con 功能表" in img["alt"], img
        page.screenshot(path=str(SHOT_DIR / "joycon_help_modal_1280x720.png"))

        # 5. scope lock：R／SR、SL 不穿透（不切頁、不開聚焦選單、modal 不關）
        view_before = page.evaluate("document.querySelector('.game-tab.active[data-view]').dataset.view")
        for key in ("R", "SR", "SL"):
            press(page, key)
            assert help_modal_open(page), key
            assert pad(page)["scope"] == "joyconHelpModal", (key, pad(page))
        assert page.evaluate("document.querySelector('.game-tab.active[data-view]').dataset.view") == view_before
        assert not page.evaluate("(() => { const m = document.getElementById('lrFocusMenu'); return !!m && !m.hidden && getComputedStyle(m).display !== 'none'; })()")

        # 3. B 關閉並回焦
        press(page, "B")
        assert wait_until(lambda: not help_modal_open(page))
        settle(page, "desktop")
        assert wait_until(lambda: help_button_focused(page)), pad(page)

        # R 離開並繼續循環 → 指揮中心；SR 從指揮中心回到說明按鈕（仍不開圖）
        press(page, "R")
        settle(page, "desktop")
        assert stop(page) == "view:command", stop(page)
        assert not help_button_focused(page)
        press(page, "SR")
        settle(page, "desktop")
        assert stop(page) == "help" and not help_modal_open(page), pad(page)
        press(page, "SR")
        settle(page, "desktop")
        assert stop(page) != "help"
    finally:
        page.context.close()


def test_mouse_click_opens_and_close_control_and_escape_close(browser, app_url):
    page = open_game(browser, app_url)
    try:
        dismiss_modals(page)
        page.click("#joyconHelpBtn")
        assert wait_until(lambda: help_modal_open(page))
        page.click("#joyconHelpCloseBtn")
        assert wait_until(lambda: not help_modal_open(page))
        assert page.evaluate("document.activeElement && document.activeElement.id") == "joyconHelpBtn"
        page.click("#joyconHelpBtn")
        assert wait_until(lambda: help_modal_open(page))
        page.keyboard.press("Escape")
        assert wait_until(lambda: not help_modal_open(page))
    finally:
        page.context.close()


def test_small_viewport_image_is_scrollable_not_cropped(browser, app_url):
    page = open_game(browser, app_url)
    try:
        dismiss_modals(page)
        page.set_viewport_size({"width": 480, "height": 360})
        page.evaluate("openJoyconHelp()")
        page.wait_for_function("document.getElementById('joyconHelpImage').complete && document.getElementById('joyconHelpImage').naturalWidth > 0")
        m = page.evaluate("""() => { const s = document.getElementById('joyconHelpScroll'); const i = document.getElementById('joyconHelpImage');
          const r = i.getBoundingClientRect();
          return { sw: s.scrollWidth, cw: s.clientWidth, sh: s.scrollHeight, ch: s.clientHeight, w: r.width, h: r.height,
                   close: document.getElementById('joyconHelpCloseBtn').getBoundingClientRect().right <= innerWidth }; }""")
        assert abs(m["w"] / m["h"] - 4 / 3) < 0.01, m
        assert m["sh"] > m["ch"] and m["sw"] >= m["w"] - 1, m  # 整張圖都在捲動範圍內（可捲動，不裁切）
        assert m["close"], m
        page.screenshot(path=str(SHOT_DIR / "joycon_help_modal_480x360.png"))
    finally:
        page.context.close()


def test_left_joycon_l_and_sl_reach_the_help_button_like_r_and_sr(browser, app_url):
    page = open_game(browser, app_url, MOCK_BRIDGE_LEFT)
    try:
        assert wait_until(lambda: pad(page)["controller"]["side"] == "left"), pad(page)["controller"]
        activate_pad(page)
        # 左手 L → 邏輯 R
        visited = ring_to_help(page, "R")
        assert visited[-1] == "help" and not help_modal_open(page), visited
        press(page, "A")  # 左手 →＝A
        assert wait_until(lambda: help_modal_open(page))
        press(page, "SR")  # 左手 SL → 邏輯 SR：modal 中不穿透
        assert help_modal_open(page)
        press(page, "B")  # 左手 ↓＝B
        assert wait_until(lambda: not help_modal_open(page))
        settle(page, "desktop")
        assert wait_until(lambda: help_button_focused(page)), pad(page)
        # 左手 SL（邏輯 SR）從說明按鈕往回一站
        press(page, "SR")
        settle(page, "desktop")
        assert stop(page) != "help"
    finally:
        page.context.close()


def test_global_sl_focus_menu_still_opens_from_help_button(browser, app_url):
    page = open_game(browser, app_url)
    try:
        activate_pad(page)
        ring_to_help(page, "R")
        press(page, "SL")
        opened = wait_until(lambda: page.evaluate(
            "(() => { const m = document.getElementById('lrFocusMenu'); return !!m && !m.hidden && getComputedStyle(m).display !== 'none'; })()"),
            timeout=10)
        assert opened, pad(page)
        assert not help_modal_open(page)
    finally:
        page.context.close()
