"""遊戲內 Joy-Con 操作說明列位置與設定面板入口的 Browser（Playwright／Chromium）regression，1280×720。

伺服器與 Joy-Con 都沿用 test_propagandist_joycon_browser 的 harness：真的 uvicorn（ENABLE_TEST_ROUTES=true，隨機埠），
Joy-Con 是 mock bridge WebSocket（synthetic frame，不是實體 Joy-Con 驗證）。牌局由 /test/setup-remove-to-purchase 準備
（行動階段＝可購買；澳門陣營讓右側「陣營能力」面板顯示）。

驗證：
  1. 說明列（#padHint）在主導覽列下方、隨機購買卡上方的中央，不與導覽、右上操作鈕、隨機購買區標題、購買操作鈕、
     陣營能力、任何購買卡重疊；選了卡之後的「已選 N 張」摘要也不重疊。
  2. 「請選擇要購買的卡牌」不再出現；「隨機購買區」標題、每張卡與「選擇卡牌」按鈕保留。
  3. 遊戲中 🎮 鈕不可見，點擊（滑鼠或程式）都不會開啟舊的設定／狀態面板；大廳仍可開啟（非遊戲流程不變）。
  4. Joy-Con 操作本身照常：方向移動焦點、B 選擇購買卡、R 切換區段，說明列跟著更新。
"""
from __future__ import annotations

import json
import os
import time

import requests

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    BITS, MOCK_BRIDGE, app_url, browser, dismiss_modals, pad, settle, stick, wait_until,
)

KEYS = {**BITS, "R": (0, 0x40)}
TOP_GAP_TARGETS = {
    "tabs": "#gameTabs .game-tab",
    "turnButtons": "#turnActionButtons button",
    "hud": "#hud",
    "marketTitle": "#randomMarketPanel > .panel-title",
    "purchaseButtons": "#purchaseSelectionControls button",
    "factionAbility": "#factionActionPanel",
    "randomCards": "#purchaseRandom .purchase-card-item",
}

GEOMETRY_JS = """(targets) => {
  const stage = document.getElementById('designStage');
  const sr = stage.getBoundingClientRect();
  const scale = sr.width / stage.offsetWidth;
  const shown = el => !!el && getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden' && el.getClientRects().length > 0;
  const box = r => ({ left: (r.left - sr.left) / scale, top: (r.top - sr.top) / scale, right: (r.right - sr.left) / scale, bottom: (r.bottom - sr.top) / scale });
  const hint = document.getElementById('padHint');
  const out = { hint: shown(hint) ? box(hint.getBoundingClientRect()) : null, hintText: hint ? hint.textContent : '', targets: {} };
  for (const [name, sel] of Object.entries(targets)) {
    // 標題是整列寬的 block：量實際文字範圍。
    const rectOf = e => { if (!e.matches('.panel-title')) return e.getBoundingClientRect(); const r = document.createRange(); r.selectNodeContents(e); return r.getBoundingClientRect(); };
    out.targets[name] = [...document.querySelectorAll(sel)].filter(shown).map(e => box(rectOf(e)));
  }
  const summary = document.getElementById('purchaseSelectionSummary');
  if (summary && shown(summary) && summary.textContent) {
    const range = document.createRange();
    range.selectNodeContents(summary);
    out.summaryText = box(range.getBoundingClientRect());
  }
  out.tabsBottom = box(document.getElementById('gameTabs').getBoundingClientRect()).bottom;
  return out;
}"""


def press(page, name, hold=0.12, after=0.4):
    index, mask = KEYS[name]
    buttons = [0, 0]
    buttons[index] = mask
    page.evaluate(f"window.__padSend(0, 0, {buttons[0]}, {buttons[1]})")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def screen_up(page, hold=0.15, after=0.45):
    """畫面向上一格（bridge frame y＝-1；harness 的 stick('up') 送 y＝+1，是畫面向下）。"""
    page.evaluate("window.__padSend(0, -1, 0, 0)")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def visible(page, sel):
    return page.evaluate(
        "(s) => { const e = document.querySelector(s); return !!e && getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0; }", sel)


def overlaps(a, b, slack=0.5):
    return a["left"] < b["right"] - slack and b["left"] < a["right"] - slack and a["top"] < b["bottom"] - slack and b["top"] < a["bottom"] - slack


def open_purchase(browser, app_url, faction_id="aomen"):
    for _ in range(6):
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx.add_init_script(MOCK_BRIDGE)
        page = ctx.new_page()
        page.goto(app_url + "/?display=desktop")
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json={"faction_id": faction_id}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        page.wait_for_function("window.RedlineController.getState().status === 'connected'")
        time.sleep(0.8)
        if page.evaluate("window.lastGameState.pending_choice") is None:
            return page
        ctx.close()
    raise AssertionError("could not get a purchase-phase test game without an unrelated pending choice")


def assert_hint_top_centre(page):
    g = page.evaluate(GEOMETRY_JS, TOP_GAP_TARGETS)
    hint = g["hint"]
    assert hint, g
    assert abs((hint["left"] + hint["right"]) / 2 - 640) <= 2, g
    assert hint["top"] >= g["tabsBottom"] - 0.5, g
    cards = g["targets"]["randomCards"]
    assert cards, g
    assert hint["bottom"] <= min(c["top"] for c in cards) + 0.5, g
    for name, rects in g["targets"].items():
        for rect in rects:
            assert not overlaps(hint, rect), (name, rect, hint)
    if "summaryText" in g:
        assert not overlaps(hint, g["summaryText"]), g
    return g


def focused_in(page, sel):
    return page.evaluate(f"!!document.querySelector('.rl-pad-focus')?.closest({json.dumps(sel)})")


def test_purchase_screen_help_bar_top_centre_and_no_settings_panel(browser, app_url):
    page = open_purchase(browser, app_url)
    try:
        dismiss_modals(page)
        settle(page, "desktop")
        # 第一下只放焦點；之後的說明列是完整按鍵說明。
        stick(page, "up")
        settle(page, "desktop")
        assert pad(page)["padActive"], pad(page)
        for _ in range(4):
            if focused_in(page, "#purchaseRandom"):
                break
            settle(page, "desktop")
            screen_up(page)
        assert focused_in(page, "#purchaseRandom"), pad(page)["focusSig"]
        assert visible(page, "#factionActionPanel")
        assert visible(page, "#purchaseSelectionControls")

        # 2. 舊的購買提示文字不存在；標題、卡、「選擇卡牌」保留。
        assert page.evaluate("document.getElementById('purchaseSelectionSummary').textContent") == ""
        assert "請選擇要購買的卡牌" not in page.evaluate("document.body.innerText")
        assert page.evaluate("document.querySelector('#randomMarketPanel > .panel-title').textContent.trim()") == "隨機購買區"
        cards = page.evaluate("document.querySelectorAll('#purchaseRandom .purchase-card-item').length")
        assert cards >= 1
        assert page.evaluate("[...document.querySelectorAll('#purchaseRandom .purchase-card-select-label')].filter(l => l.textContent.trim() === '選擇卡牌').length") == cards

        # 1. 說明列在上方中央、不遮擋。
        g = assert_hint_top_centre(page)
        assert "R/SR" in g["hintText"] and "Joy-Con" in g["hintText"], g["hintText"]

        # 3. 🎮 不可見，點擊不開面板（滑鼠點說明列位置、程式 click 都一樣）。
        assert not visible(page, "#padToggleBtn")
        hint = g["hint"]
        page.mouse.click((hint["left"] + hint["right"]) / 2, (hint["top"] + hint["bottom"]) / 2)
        page.evaluate("document.getElementById('padToggleBtn').click()")
        time.sleep(0.2)
        assert not visible(page, "#padPanel")
        assert page.evaluate("document.getElementById('padPanel').hidden") is True

        # 4. Joy-Con 照常：B 選擇聚焦的購買卡，摘要更新且仍不與說明列重疊。
        settle(page, "desktop")
        press(page, "B")
        assert wait_until(lambda: page.evaluate("document.getElementById('purchaseSelectionSummary').textContent").startswith("已選 1 張")), \
            page.evaluate("document.getElementById('purchaseSelectionSummary').textContent")
        g = assert_hint_top_centre(page)
        assert "Y" in g["hintText"], g["hintText"]

        proof = os.environ.get("REDLINE_JOYCON_HELP_TOP_PROOF")
        if proof:
            page.screenshot(path=proof)

        # R 切到下一個區段（戰略地圖）：說明列仍在導覽列下方中央、不遮右上操作鈕。
        settle(page, "desktop")
        press(page, "R", after=0.8)
        assert page.evaluate("document.querySelector('.game-tab.active')?.dataset.view") == "map"
        g = page.evaluate(GEOMETRY_JS, {"tabs": "#gameTabs .game-tab", "turnButtons": "#turnActionButtons button", "hud": "#hud"})
        assert g["hint"] and g["hint"]["top"] >= g["tabsBottom"] - 0.5, g
        assert abs((g["hint"]["left"] + g["hint"]["right"]) / 2 - 640) <= 2, g
        for name, rects in g["targets"].items():
            for rect in rects:
                assert not overlaps(g["hint"], rect), (name, rect, g["hint"])
        assert not visible(page, "#padPanel")
    finally:
        page.context.close()


def test_lobby_keeps_controller_settings_panel(browser, app_url):
    """非遊戲畫面（開始／大廳）不受影響：🎮 仍可開關設定面板。"""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script(MOCK_BRIDGE)
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        page.wait_for_selector("#padToggleBtn", state="attached")
        assert not page.evaluate("getComputedStyle(document.getElementById('gameShell')).display !== 'none'")
        page.evaluate("document.getElementById('padToggleBtn').click()")
        assert page.evaluate("document.getElementById('padPanel').hidden") is False
        page.evaluate("document.getElementById('padToggleBtn').click()")
        assert page.evaluate("document.getElementById('padPanel').hidden") is True
    finally:
        ctx.close()


def test_joycon_first_command_centre_opens_help_once(browser, app_url):
    """Joy-Con 牌局選完陣營後第一次進入指揮中心會自動顯示說明；同一玩家、同一局只顯示一次。"""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script(MOCK_BRIDGE)
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json={"faction_id": "aomen"}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        page.evaluate("""setup => {
          latestLobbyState = {control_mode: 'joycon'};
          gameId = setup.game_id;
          playerId = setup.player_id;
          connect();
        }""", setup)
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        page.wait_for_function("document.querySelector('#gameTabs .game-tab.active')?.dataset.view === 'command'")

        # 隨機事件等既有視窗優先；測試只保留本功能的說明視窗。
        page.evaluate("""() => {
          for (const modal of document.querySelectorAll('.modal-overlay')) {
            if (modal.id !== 'joyconHelpModal') modal.style.display = 'none';
          }
          scheduleJoyconFirstCommandHelp(window.lastGameState);
        }""")
        page.wait_for_selector("#joyconHelpModal", state="visible", timeout=5000)
        assert page.evaluate("document.getElementById('joyconHelpTitle').textContent.trim()") == "Joy-Con 說明"
        assert page.evaluate("document.body.classList.contains('joycon-help-open')") is True
        proof = os.environ.get("REDLINE_JOYCON_FIRST_HELP_PROOF")
        if proof:
            page.screenshot(path=proof)
        marker = page.evaluate("""() => localStorage.getItem(
          `redline.joycon-first-command-help.v1:${gameId}:${playerId}`
        )""")
        assert marker == "shown"

        page.click("#joyconHelpCloseBtn")
        page.wait_for_selector("#joyconHelpModal", state="hidden")
        page.evaluate("render(window.lastGameState)")
        time.sleep(0.8)
        assert not visible(page, "#joyconHelpModal"), "同一玩家、同一局重新繪製後不得再次自動顯示"
    finally:
        ctx.close()


def test_computer_game_does_not_auto_open_joycon_help(browser, app_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script(MOCK_BRIDGE)
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json={"faction_id": "aomen"}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        page.evaluate("""setup => {
          latestLobbyState = {control_mode: 'computer'};
          gameId = setup.game_id;
          playerId = setup.player_id;
          connect();
        }""", setup)
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        time.sleep(0.8)
        assert not visible(page, "#joyconHelpModal")
        marker = page.evaluate("""() => localStorage.getItem(
          `redline.joycon-first-command-help.v1:${gameId}:${playerId}`
        )""")
        assert marker is None
    finally:
        ctx.close()


def test_finished_joycon_game_does_not_poll_for_first_help(browser, app_url):
    """永久不符合資格的結束狀態只檢查一次，不建立無限輪詢。"""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script(MOCK_BRIDGE)
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        page.evaluate("""() => {
          gameId = 'finished-help-test';
          playerId = 'p1';
          latestLobbyState = {control_mode: 'joycon'};
          window.__helpPolls = 0;
          const nativeTimeout = window.setTimeout;
          window.setTimeout = (...args) => {
            window.__helpPolls += 1;
            return nativeTimeout(...args);
          };
          maybeOpenJoyconFirstCommandHelp({
            game_over: true,
            players: [{id: 'p1', faction: 'aomen', base: '澳門'}],
          });
        }""")
        time.sleep(0.6)
        assert page.evaluate("window.__helpPolls") == 0
        assert not visible(page, "#joyconHelpModal")
    finally:
        ctx.close()


def test_first_help_does_not_cover_controller_peer_notice(browser, app_url):
    """控制器 scope 中不具 modal-overlay class 的視窗也有優先權。"""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        page.evaluate("""() => {
          gameId = 'peer-notice-help-test';
          playerId = 'p1';
          latestLobbyState = {control_mode: 'joycon'};
          document.getElementById('gameShell').style.display = 'block';
          document.querySelectorAll('#gameTabs .game-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.view === 'command');
          });
          const peer = document.getElementById('peerActionNotice');
          peer.classList.remove('peer-action-notice-minimized');
          peer.style.display = 'block';
          window.lastGameState = {
            game_over: false,
            players: [{id: 'p1', faction: 'aomen', base: '澳門'}],
          };
          maybeOpenJoyconFirstCommandHelp(window.lastGameState);
        }""")
        time.sleep(0.3)
        assert not visible(page, "#joyconHelpModal")
        marker = page.evaluate("localStorage.getItem('redline.joycon-first-command-help.v1:peer-notice-help-test:p1')")
        assert marker is None

        # 關閉既有視窗後，屬性觀察器會重新檢查，不需等待下一次 server render。
        page.evaluate("document.getElementById('peerActionNotice').style.display = 'none'")
        page.wait_for_selector("#joyconHelpModal", state="visible", timeout=3000)
        marker = page.evaluate("localStorage.getItem('redline.joycon-first-command-help.v1:peer-notice-help-test:p1')")
        assert marker == "shown"
    finally:
        ctx.close()


def test_entering_command_tab_rechecks_first_help_without_render(browser, app_url):
    """首次從其他分頁進入指揮中心時立即顯示，不依賴下一次 server render。"""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        page.evaluate("""() => {
          gameId = 'command-tab-help-test';
          playerId = 'p1';
          latestLobbyState = {control_mode: 'joycon'};
          document.getElementById('gameShell').style.display = 'block';
          document.querySelectorAll('#gameTabs .game-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.view === 'map');
          });
          window.lastGameState = {
            game_over: false,
            players: [{id: 'p1', faction: 'aomen', base: '澳門'}],
          };
          maybeOpenJoyconFirstCommandHelp(window.lastGameState);
        }""")
        time.sleep(0.3)
        assert not visible(page, "#joyconHelpModal")

        page.evaluate("""() => {
          document.querySelectorAll('#gameTabs .game-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.view === 'command');
          });
        }""")
        page.wait_for_selector("#joyconHelpModal", state="visible", timeout=3000)
    finally:
        ctx.close()
