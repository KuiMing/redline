"""導覽列「遊戲選單」按鈕（取代舊的「Joy-Con 說明」按鈕）的 Browser（Playwright／Chromium）regression，1280×720。

伺服器與 Joy-Con 都沿用 test_propagandist_joycon_browser 的 harness：真的 uvicorn（ENABLE_TEST_ROUTES=true，隨機埠），
Joy-Con 是 mock bridge WebSocket（synthetic frame，不是實體 Joy-Con 驗證）。

驗證：
  1. 六個區段分頁不變；導覽列按鈕是「遊戲選單」（不是第七個遊戲頁面）；舊的 joyconHelpBtn／「Joy-Con 說明」導覽列按鈕不存在。
  2. R 依序經過區段後停在「遊戲選單」按鈕（只放焦點、不開選單），A 開啟 gameMenuModal（與長按搖桿同一個），B 關閉並回焦；
     SR 反向可到達；左 Joy-Con 的 L／SL 行為與右手 R／SR 相同；SL 全域聚焦選單仍可從該按鈕開啟。
  3. 未連接 Joy-Con 時滑鼠點按鈕也能開啟；Esc／返回遊戲關閉並回焦；Enter 鍵可開啟。
  4. Joy-Con 說明圖仍可由遊戲選單的「Joy-Con 功能表」開啟（滑鼠與 Joy-Con），圖片 1280×960 不裁切、B／Esc／× 關閉。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    MOCK_BRIDGE, app_url, browser, dismiss_modals, pad, settle, wait_until,
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


def open_game(browser, app_url, bridge=MOCK_BRIDGE, with_pad=True, extra_init=None):
    for _ in range(6):
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx.add_init_script(bridge if with_pad else "window.__noPad = true;")
        for script in extra_init or []:
            ctx.add_init_script(script)
        page = ctx.new_page()
        page.goto(app_url + "/?display=desktop")
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json={"faction_id": "aomen"}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        if with_pad:
            page.wait_for_function("window.RedlineController.getState().status === 'connected'")
        time.sleep(0.8)
        if page.evaluate("window.lastGameState.pending_choice") is None:
            return page
        ctx.close()
    raise AssertionError("could not get a test game without an unrelated pending choice")


STOP_JS = """() => {
  const s = window.RedlineController.getState();
  if (s.focusKind === 'menuEntry') return 'menuEntry';
  if (s.scope === 'eventRevealModal') return 'event';
  if (s.scope === 'eraAchievementModal') return 'era';
  if (s.scope !== 'page' && s.scope !== 'map') return 'modal:' + s.scope;
  return 'view:' + (document.querySelector('.game-tab.active[data-view]') || {dataset: {}}).dataset.view;
}"""


def stop(page):
    return page.evaluate(STOP_JS)


def shown(page, element_id):
    return page.evaluate(f"(() => {{ const e = document.getElementById('{element_id}'); return !!e && getComputedStyle(e).display !== 'none'; }})()")


def menu_open(page):
    return shown(page, "gameMenuModal")


def help_modal_open(page):
    return shown(page, "joyconHelpModal")


def menu_button_focused(page):
    return page.evaluate("""() => {
      const b = document.getElementById('gameMenuBtn');
      return window.RedlineController.getState().focusKind === 'menuEntry' && b.classList.contains('rl-pad-focus')
        && document.activeElement === b;
    }""")


NAV = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}  # y>0＝畫面向下（controller_core.stickDirection）


def stick(page, direction, hold=0.15, after=0.4):
    x, y = NAV[direction]
    page.evaluate(f"window.__padSend({x}, {y}, 0, 0)")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def dismiss_modals_by_click(page):
    """沒有 Joy-Con 時收掉隨機事件揭示等 modal：點該 modal scope 既有的取消／關閉控制（與 B 相同的目標）。"""
    for _ in range(6):
        closed = page.evaluate("""() => { for (const d of window.RedlineControllerCore.MODAL_SCOPES) {
          const el = document.getElementById(d.id);
          if (!el || getComputedStyle(el).display === 'none') continue;
          for (const sel of d.cancel) { const t = sel === 'self' ? el : el.querySelector(sel); if (t) { t.click(); return d.id; } }
        } return null; }""")
        if closed is None:
            return
        time.sleep(0.4)


def activate_pad(page):
    dismiss_modals(page)
    settle(page, "desktop")
    if not pad(page)["padActive"]:
        stick(page, "up")  # 第一下只放焦點
    settle(page, "desktop")
    assert pad(page)["padActive"], pad(page)


def ring_to_menu(page, key="R", limit=12):
    visited = [stop(page)]
    for _ in range(limit):
        press(page, key)
        settle(page, "desktop")
        visited.append(stop(page))
        if visited[-1] == "menuEntry":
            return visited
    raise AssertionError(visited)


def test_nav_has_six_sections_plus_game_menu_button_and_no_old_help_button(browser, app_url):
    page = open_game(browser, app_url)
    try:
        tabs = page.evaluate("[...document.querySelectorAll('#gameTabs > .game-tab')].map(t => t.textContent.trim())")
        assert tabs == SIX_TABS, tabs  # 時代關卡分頁在 #activeEraTabs 內
        btn = page.evaluate("""() => { const b = document.getElementById('gameMenuBtn'); const r = b.getBoundingClientRect();
          return { cls: b.className, name: b.getAttribute('aria-label'), text: b.textContent.trim(), w: r.width, h: r.height,
                   inTabs: !!b.closest('#gameTabs'), visible: getComputedStyle(b).display !== 'none',
                   controls: b.getAttribute('aria-controls') }; }""")
        assert btn["name"] == "遊戲選單" and btn["text"] == "遊戲選單", btn
        assert btn["controls"] == "gameMenuModal", btn
        assert "game-tab" not in btn["cls"], btn  # 不是第七個遊戲頁面
        assert btn["inTabs"] and btn["visible"] and btn["w"] > 40 and btn["h"] > 20, btn
        # 舊的導覽列說明入口完全移除（不只是改文字）
        gone = page.evaluate("""() => ({ btn: !!document.getElementById('joyconHelpBtn'),
          navText: document.getElementById('gameTabs').textContent.includes('Joy-Con 說明'),
          openHelpInline: !!document.querySelector('#gameTabs [onclick*="openJoyconHelp"]') })""")
        assert gone == {"btn": False, "navText": False, "openHelpInline": False}, gone
        # Joy-Con 說明圖資產仍存在且是原檔
        r = requests.get(app_url + IMAGE_PATH, timeout=10)
        assert r.status_code == 200 and r.headers["content-type"].startswith("image/jpeg") and len(r.content) > 100_000
        # 配樂資產：同源、AAC/mp4 容器
        a = requests.get(app_url + "/static/audio/redline-theme.m4a", timeout=10)
        assert a.status_code == 200 and a.headers["content-type"].startswith("audio/mp4"), a.headers
    finally:
        page.context.close()


def test_ring_focuses_menu_button_without_opening_then_a_opens_menu_b_closes_and_restores(browser, app_url):
    page = open_game(browser, app_url)
    try:
        activate_pad(page)
        assert stop(page) == "view:command", stop(page)
        visited = ring_to_menu(page, "R")
        sections = [v for v in visited if v.startswith("view:")]
        assert sections[:4] == ["view:command", "view:map", "view:log", "view:myFaction"], visited
        assert visited[-1] == "menuEntry" and visited.count("menuEntry") == 1, visited
        # R 只聚焦按鈕：不開選單、不開說明圖，也不切頁
        assert menu_button_focused(page), pad(page)
        assert not menu_open(page) and not help_modal_open(page)
        assert "遊戲選單" in page.evaluate("document.getElementById('padHint').textContent")

        # B 在按鈕上不作用
        press(page, "B")
        assert not menu_open(page) and menu_button_focused(page)

        # A 開啟與長按搖桿相同的 gameMenuModal；音量控制在裡面
        press(page, "A")
        assert wait_until(lambda: menu_open(page)), pad(page)
        settle(page, "desktop")
        assert pad(page)["scope"] == "gameMenuModal", pad(page)
        assert shown(page, "gameMenuVolume")
        assert not help_modal_open(page)

        # scope lock：R／SR、SL 不穿透
        view_before = page.evaluate("document.querySelector('.game-tab.active[data-view]').dataset.view")
        for key in ("R", "SR", "SL"):
            press(page, key)
            assert menu_open(page), key
            assert pad(page)["scope"] == "gameMenuModal", (key, pad(page))
        assert page.evaluate("document.querySelector('.game-tab.active[data-view]').dataset.view") == view_before

        # B 關閉並回焦到按鈕
        press(page, "B")
        assert wait_until(lambda: not menu_open(page))
        settle(page, "desktop")
        assert wait_until(lambda: menu_button_focused(page)), pad(page)

        # R 離開並繼續循環 → 指揮中心；SR 從指揮中心回到按鈕（仍不開選單）
        press(page, "R")
        settle(page, "desktop")
        assert stop(page) == "view:command", stop(page)
        assert not menu_button_focused(page)
        press(page, "SR")
        settle(page, "desktop")
        assert stop(page) == "menuEntry" and not menu_open(page), pad(page)
        press(page, "SR")
        settle(page, "desktop")
        assert stop(page) != "menuEntry"
    finally:
        page.context.close()


def test_joycon_function_menu_item_opens_help_image_and_b_returns(browser, app_url):
    page = open_game(browser, app_url)
    try:
        activate_pad(page)
        ring_to_menu(page, "R")
        press(page, "A")
        assert wait_until(lambda: menu_open(page))
        settle(page, "desktop")
        # 遊戲選單：返回遊戲 → Joy-Con 功能表（下一項）
        press(page, "B")  # 先確認 B 關閉
        assert wait_until(lambda: not menu_open(page))
        settle(page, "desktop")
        press(page, "A")
        assert wait_until(lambda: menu_open(page)), pad(page)
        settle(page, "desktop")
        stick(page, "down")
        settle(page, "desktop")
        assert pad(page)["focusSig"] == "#gameMenuSettingsBtn", pad(page)
        press(page, "A")
        assert wait_until(lambda: help_modal_open(page)), pad(page)
        assert not menu_open(page)
        settle(page, "desktop")
        assert pad(page)["scope"] == "joyconHelpModal"
        page.wait_for_function("document.getElementById('joyconHelpImage').complete && document.getElementById('joyconHelpImage').naturalWidth > 0")
        img = page.evaluate("""() => { const i = document.getElementById('joyconHelpImage'); const r = i.getBoundingClientRect();
          return { src: new URL(i.currentSrc || i.src).pathname, nw: i.naturalWidth, nh: i.naturalHeight, w: r.width, h: r.height,
                   alt: i.alt }; }""")
        assert img["src"] == IMAGE_PATH and (img["nw"], img["nh"]) == (1280, 960), img
        assert img["w"] > 300 and abs(img["w"] / img["h"] - 4 / 3) < 0.01, img
        assert "按住搖桿 2 秒，開啟遊戲選單" in img["alt"], img
        page.screenshot(path=str(SHOT_DIR / "joycon_help_modal_1280x720.png"))
        for key in ("R", "SR", "SL"):
            press(page, key)
            assert help_modal_open(page), key
        press(page, "B")
        assert wait_until(lambda: not help_modal_open(page))
        assert not menu_open(page)
    finally:
        page.context.close()


def test_mouse_opens_menu_without_joycon_and_keyboard_works(browser, app_url):
    page = open_game(browser, app_url, with_pad=False)
    try:
        # 沒有任何 Joy-Con 配對／擁有：長按入口的資格不成立，但滑鼠入口不受影響
        state = pad(page)
        assert state["enabled"] is False and state["padActive"] is False, state  # 沒有收到任何 Joy-Con 輸入
        dismiss_modals_by_click(page)
        page.click("#gameMenuBtn")
        assert wait_until(lambda: menu_open(page))
        assert page.evaluate("document.activeElement.id") == "gameMenuResumeBtn"
        assert not help_modal_open(page)
        # Esc 關閉並回焦
        page.keyboard.press("Escape")
        assert wait_until(lambda: not menu_open(page))
        assert page.evaluate("document.activeElement.id") == "gameMenuBtn"
        # 鍵盤 Enter 開啟；Tab 只在選單內循環；返回遊戲關閉
        page.keyboard.press("Enter")
        assert wait_until(lambda: menu_open(page))
        seen = []
        for _ in range(7):
            page.keyboard.press("Tab")
            seen.append(page.evaluate("document.activeElement.id"))
        assert set(seen) == {"gameMenuResumeBtn", "gameMenuSettingsBtn", "gameMenuVolumeDownBtn", "gameMenuVolumeUpBtn", "gameMenuRestartBtn"}, seen
        page.click("#gameMenuResumeBtn")
        assert wait_until(lambda: not menu_open(page))
        # 背景點擊＝返回遊戲
        page.click("#gameMenuBtn")
        assert wait_until(lambda: menu_open(page))
        page.mouse.click(10, 10)
        assert wait_until(lambda: not menu_open(page))
        # Joy-Con 功能表 → 說明圖 → Esc；焦點回到導覽列按鈕
        page.click("#gameMenuBtn")
        assert wait_until(lambda: menu_open(page))
        page.click("#gameMenuSettingsBtn")
        assert wait_until(lambda: help_modal_open(page) and not menu_open(page))
        page.keyboard.press("Escape")
        assert wait_until(lambda: not help_modal_open(page))
        assert page.evaluate("document.activeElement && document.activeElement.id") == "gameMenuBtn"
        # 重新開始仍先經過確認（不直接離開）
        page.click("#gameMenuBtn")
        assert wait_until(lambda: menu_open(page))
        page.click("#gameMenuRestartBtn")
        assert wait_until(lambda: shown(page, "gameMenuConfirmModal") and not menu_open(page))
        page.keyboard.press("Escape")
        assert wait_until(lambda: menu_open(page) and not shown(page, "gameMenuConfirmModal"))
        stage = page.evaluate("""() => { const r = document.getElementById('designStage').getBoundingClientRect();
          return [Math.round(r.width), Math.round(r.height)]; }""")
        assert stage == [1280, 720], stage
        page.screenshot(path=str(SHOT_DIR / "game_menu_with_volume_1280x720.png"))
    finally:
        page.context.close()


def test_small_viewport_image_is_scrollable_not_cropped(browser, app_url):
    page = open_game(browser, app_url, with_pad=False)
    try:
        dismiss_modals_by_click(page)
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


def test_left_joycon_l_and_sl_reach_the_menu_button_like_r_and_sr(browser, app_url):
    page = open_game(browser, app_url, MOCK_BRIDGE_LEFT)
    try:
        assert wait_until(lambda: pad(page)["controller"]["side"] == "left"), pad(page)["controller"]
        activate_pad(page)
        # 左手 L → 邏輯 R
        visited = ring_to_menu(page, "R")
        assert visited[-1] == "menuEntry" and not menu_open(page), visited
        press(page, "A")  # 左手 →＝A
        assert wait_until(lambda: menu_open(page))
        press(page, "SR")  # 左手 SL → 邏輯 SR：modal 中不穿透
        assert menu_open(page)
        press(page, "B")  # 左手 ↓＝B
        assert wait_until(lambda: not menu_open(page))
        settle(page, "desktop")
        assert wait_until(lambda: menu_button_focused(page)), pad(page)
        # 左手 SL（邏輯 SR）從按鈕往回一站
        press(page, "SR")
        settle(page, "desktop")
        assert stop(page) != "menuEntry"
    finally:
        page.context.close()


def test_global_sl_focus_menu_still_opens_from_menu_button(browser, app_url):
    page = open_game(browser, app_url)
    try:
        activate_pad(page)
        ring_to_menu(page, "R")
        press(page, "SL")
        opened = wait_until(lambda: page.evaluate(
            "(() => { const m = document.getElementById('lrFocusMenu'); return !!m && !m.hidden && getComputedStyle(m).display !== 'none'; })()"),
            timeout=10)
        assert opened, pad(page)
        assert not menu_open(page)
    finally:
        page.context.close()
