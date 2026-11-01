"""宣傳家（打出可移除本牌；若移除，於己方組織 1 格內建立 1 個組織，並進行 1 次組織遷移）全程只用 Joy-Con 完成的
Browser（Playwright／Chromium）regression。

伺服器是真的 uvicorn（server.main:app，ENABLE_TEST_ROUTES=true，隨機埠，測試結束即關閉）；牌局由
/test/setup-remove-to-purchase＋/test/set-hand 準備（宣傳家在手牌、行動階段）。Joy-Con 是 mock bridge WebSocket
（舊版 frame 協定，不是實體硬體）。遊戲操作只透過 controller frame：不呼叫 page.click、不點任何按鈕，
並以 trusted pointer 事件計數證明沒有滑鼠輸入。

根因情境：手上還有另一張可排入地圖互動的建立卡（例如第二張宣傳家）時，pending choice 帶 queueable_card_names，
既有流程刻意不自動切到戰略地圖（滑鼠可繼續排入）；但必選地圖目標會鎖住其他分頁的所有焦點，戰略地圖 iframe 也從未掛載，
控制器因此完全不能操作。修正後控制器以既有分頁切換回到戰略地圖，iframe 載入後第一份有目標的 snapshot 一到就聚焦目標。
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

playwright_sync = pytest.importorskip("playwright.sync_api")
pytest.importorskip("uvicorn")

ROOT = Path(__file__).resolve().parents[2]
BRIDGE_URL = "ws://127.0.0.1:9/redline-test-pad"
BITS = {"A": (0, 0x08), "B": (0, 0x04), "Y": (0, 0x01)}
STICK = {"right": (1, 0), "left": (-1, 0), "up": (0, 1), "down": (0, -1)}
# 固定起始牌庫（不含宣傳家）：測試牌局以隨機陣營建局，開局能力可能把宣傳家洗入牌庫，而德拉敦在牆內（例如阿里）
# 建立會觸發游擊隊抽 1 張——抽到宣傳家會讓「打出的宣傳家已離開手牌」無法以手牌張數驗證。
DECK = ["追隨者", "追隨者", "追隨者", "樂捐者", "樂捐者"]

MOCK_BRIDGE = """
(() => {
  const RealWS = window.WebSocket;
  window.__mockBridges = [];
  class MockBridge {
    constructor(url) {
      this.url = url; this.readyState = 0; this.onopen = this.onmessage = this.onclose = this.onerror = null;
      window.__mockBridges.push(this);
      setTimeout(() => { if (this.readyState === 0) { this.readyState = 1; this.onopen && this.onopen({}); } }, 20);
    }
    send() {}
    close() { this.readyState = 3; }
  }
  window.WebSocket = function (url, protocols) {
    if (String(url) === '__BRIDGE__') return new MockBridge(url);
    return protocols === undefined ? new RealWS(url) : new RealWS(url, protocols);
  };
  Object.assign(window.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
  window.__padLast = [0, 0, 0, 0];
  const emit = () => {
    const live = window.__mockBridges.filter(b => b.readyState === 1).pop();
    if (!live || !live.onmessage) return false;
    const [x, y, b0, b1] = window.__padLast;
    live.onmessage({ data: JSON.stringify({ x, y, buttons: [b0, b1] }) });
    return true;
  };
  window.__padSend = (x, y, b0, b1) => { window.__padLast = [x, y, b0, b1]; return emit(); };
  setInterval(emit, 33);
  window.__trustedPointer = 0;
  for (const type of ['pointerdown', 'mousedown', 'click']) {
    document.addEventListener(type, (e) => { if (e.isTrusted) window.__trustedPointer += 1; }, true);
  }
  localStorage.setItem('redline.controller.v1', JSON.stringify({ enabled: true, url: '__BRIDGE__' }));
})();
""".replace("__BRIDGE__", BRIDGE_URL)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app_url():
    port = free_port()
    env = {**os.environ, "ENABLE_TEST_ROUTES": "true"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port),
                             "--log-level", "error"], cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if requests.get(url + "/", timeout=1).ok:
                break
        except requests.RequestException:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment without Chromium
            pytest.skip(f"chromium unavailable: {exc}")
        yield b
        b.close()


# ------------------------------------------------------------------ controller input（只送 bridge frame）

def press(page, name, hold=0.12, after=0.4):
    index, mask = BITS[name]
    buttons = [0, 0]
    buttons[index] = mask
    page.evaluate(f"window.__padSend(0, 0, {buttons[0]}, {buttons[1]})")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def stick(page, direction, hold=0.15, after=0.4):
    x, y = STICK[direction]
    page.evaluate(f"window.__padSend({x}, {y}, 0, 0)")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def pad(page):
    return page.evaluate("window.RedlineController.getState()")


def me(page):
    return page.evaluate("(window.lastGameState.players || []).find(p => p.id === playerId)")


def pending(page):
    return page.evaluate("window.lastGameState.pending_choice || null")


def view(page):
    return page.evaluate("document.querySelector('.game-tab.active')?.dataset.view || null")


def hint(page):
    return page.evaluate("document.getElementById('padHint')?.textContent || ''")


def org_counts(player):
    orgs = player.get("orgs") or {}
    return {town: int(count) for town, count in orgs.items()} if isinstance(orgs, dict) else {}


def open_game(browser, app_url, display, hand):
    # 測試牌局的開局事件是隨機的，少數事件會先開一個別的 pending choice（例如事件建立組織）：換一局，讓情境固定從宣傳家開始。
    for _ in range(6):
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        ctx.add_init_script(MOCK_BRIDGE)
        page = ctx.new_page()
        page.goto(app_url + ("/?display=living-room" if display == "living-room" else "/?display=desktop"))
        setup = requests.post(app_url + "/test/setup-remove-to-purchase", json={"deck": DECK}, timeout=10).json()
        assert setup.get("game_id") and setup.get("player_id"), setup
        res = requests.post(app_url + "/test/set-hand", json={"game_id": setup["game_id"], "player_id": setup["player_id"], "cards": hand},
                            timeout=10).json()
        assert res.get("hand") == hand, res
        page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
        page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
        page.wait_for_function("window.RedlineController.getState().status === 'connected'")
        time.sleep(0.8)
        if pending(page) is None and me(page)["hand"] == hand:
            return page
        ctx.close()
    pytest.fail("could not get a test game without an unrelated pending choice")


def dismiss_modals(page):
    """隨機事件揭示等 modal：只用 controller（第一下放焦點，B 以既有關閉收起）。"""
    for _ in range(6):
        if pad(page)["scope"] in ("page", "map"):
            return
        press(page, "B")
    assert pad(page)["scope"] in ("page", "map"), pad(page)


def play_propagandist_action(page, display):
    dismiss_modals(page)
    settle(page, display)
    if not pad(page)["padActive"]:
        press(page, "A")  # 第一下只放焦點（手牌／客廳模式的手牌區）；用 B 收過 modal 時焦點已回到頁面預設的手牌
    if display == "living-room":
        assert pad(page)["livingRoom"]["zone"] == "hand", pad(page)["livingRoom"]
        if pad(page)["livingRoom"]["layer"] == "zone":
            press(page, "A")  # 進入手牌區（已在內容層時不再按：內容層的 A＝查看）
        assert pad(page)["livingRoom"]["itemKey"].startswith("hand:0:宣傳家"), pad(page)["livingRoom"]
    else:
        assert pad(page)["focusSig"].startswith("DIV||hand|宣傳家"), pad(page)
    settle(page, display)
    press(page, "Y", after=0.2)  # 既有「行動」按鈕


def focused_choice_town(page, display):
    s = pad(page)
    if s["scope"] != "map":
        return None
    if display == "living-room":
        lr = s["livingRoom"]
        if lr["mapStage"] != "choice" or not (lr["itemKey"] or "").startswith("town:"):
            return None
        return lr["itemKey"][len("town:"):]
    if s["focusKind"] != "map" or not (s["focusSig"] or "").startswith("town:"):
        return None
    return s["focusTown"]


def wait_until(predicate, timeout=8.0, step=0.1):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return predicate()


def settle(page, display):
    """等控制器把焦點穩定下來：reconcile／重繪冷卻（300ms 內忽略 A／B／X／Y）、地圖確認與處理中鎖都結束。
    不送任何輸入；只是避免測試在合法的防誤觸冷卻內按鍵（那一下會被既有閘門吞掉）。"""
    def ready():
        s = pad(page)
        if s["reconcilePending"]:
            return False
        gate = s["livingRoom"] if display == "living-room" else s["shortcuts"]
        if not gate:
            return True
        if gate.get("reconcilePending") or gate.get("mapRequest") or gate.get("processing"):
            return False
        now = page.evaluate("performance.now()")
        return now - (gate.get("redrawAt") or -1e9) > 400 and now - (gate.get("activatedAt") or -1e9) > 400
    assert wait_until(ready, timeout=6), pad(page)


def build_with_controller(page, display, expected_propagandists):
    town = wait_until(lambda: focused_choice_town(page, display))
    assert town, {"pad": pad(page), "view": view(page), "hint": hint(page)}
    settle(page, display)
    town = focused_choice_town(page, display)
    assert town, {"pad": pad(page), "view": view(page), "hint": hint(page)}
    choice = pending(page)
    assert choice and choice["choice_key"] == "card_build_organization", choice
    assert town in [t["town"] for t in choice["towns"]], (town, choice["towns"])
    before = org_counts(me(page))
    press(page, "Y", after=0.2)  # 既有「建立組織」（iframe 以權威資料重驗後點擊）
    assert wait_until(lambda: pending(page) is None and me(page)["moves_left"] == 1), (pending(page), me(page), pad(page))
    player = me(page)
    after = org_counts(player)
    assert after.get(town, 0) == before.get(town, 0) + 1, (town, before, after)
    # 打出的宣傳家已移除（回到購買區），不在手牌；建立後的陣營效果（游擊隊）可能另外抽牌，但只會抽到固定牌庫裡的牌。
    assert player["hand"].count("宣傳家") == expected_propagandists, player["hand"]
    assert all(card == "宣傳家" or card in DECK for card in player["hand"]), player["hand"]
    return town


def move_with_controller(page, display):
    """遷移：只用搖桿／A 選來源與目的地，Y 走既有「確認移動」。回傳 (from, to)。"""
    before = org_counts(me(page))
    directions = ["right", "down", "left", "up"]
    for step in range(16):
        if display == "living-room":
            lr = pad(page)["livingRoom"]
            row = (lr["itemKey"] or "")[len("town:"):]
            acts = dict(zip(lr["mapRows"], lr["mapActs"]))
            if lr["mapStage"] == "destination" and acts.get(row) == "move" and lr["mapSelected"]:
                origin = lr["mapSelected"]
                settle(page, display)
                press(page, "Y", after=0.2)
                move = (origin, row)
                break
            if lr["mapStage"] == "source" and row:
                settle(page, display)
                press(page, "A")  # 選來源（既有 marker click）
                continue
            stick(page, "down")
            continue
        match = re.search(r"Y 移動 (\S+)→(\S+)", hint(page))
        if match:
            settle(page, display)
            match = re.search(r"Y 移動 (\S+)→(\S+)", hint(page))
            assert match, hint(page)
            press(page, "Y", after=0.2)
            move = (match.group(1), match.group(2))
            break
        s = pad(page)
        if s["focusKind"] == "map" and "A 選取" in hint(page) and step % 4 == 3:
            press(page, "A")
        stick(page, directions[step % 4])
    else:
        pytest.fail(f"could not reach a move target: {pad(page)} {hint(page)}")
    assert wait_until(lambda: me(page)["moves_left"] == 0), me(page)
    after = org_counts(me(page))
    origin, dest = move
    assert after.get(dest, 0) == before.get(dest, 0) + 1, (move, before, after)
    assert after.get(origin, 0) == before.get(origin, 0) - 1, (move, before, after)
    return move


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
@pytest.mark.parametrize("hand", [["宣傳家", "宣傳家"], ["宣傳家"]], ids=["queueable-build-card-in-hand", "single-card"])
def test_propagandist_build_and_move_with_controller_only(browser, app_url, display, hand):
    page = open_game(browser, app_url, display, hand)
    try:
        assert page.evaluate("document.getElementById('strategicMapFrame').getAttribute('src')") in (None, "", "about:blank")
        play_propagandist_action(page, display)
        choice = wait_until(lambda: pending(page))
        assert choice and choice["choice_key"] == "card_build_organization", choice
        if len(hand) > 1:
            # 根因情境的前提：既有流程因可排入的建立卡不自動切到戰略地圖。
            assert choice["queueable_card_names"], choice
        build_with_controller(page, display, expected_propagandists=len(hand) - 1)
        move_with_controller(page, display)
        assert page.evaluate("window.__trustedPointer") == 0, "game was operated with the mouse"
    finally:
        page.context.close()


def test_input_after_mouse_leaves_map_returns_to_map_without_executing(browser, app_url):
    page = open_game(browser, app_url, "desktop", ["宣傳家", "宣傳家"])
    try:
        play_propagandist_action(page, "desktop")
        assert wait_until(lambda: focused_choice_town(page, "desktop"))
        choice_id = pending(page)["choice_id"]
        # 滑鼠（既有分頁 handler）離開戰略地圖：同一個 choice 不再自動拉回。
        page.evaluate("document.querySelector('.game-tab[data-view=command]').click()")
        time.sleep(1.0)
        assert view(page) == "command"
        assert pad(page)["scope"] == "page"
        # ZR 在其他分頁維持完全不作用（不切分頁、不改焦點）。
        before_zr = pad(page)["focusSig"]
        page.evaluate("window.__padSend(0, 0, 128, 0)")
        time.sleep(0.12)
        page.evaluate("window.__padSend(0, 0, 0, 0)")
        time.sleep(0.6)
        assert view(page) == "command" and pad(page)["focusSig"] == before_zr, (view(page), pad(page))
        # 方向／按鍵輸入：先回到戰略地圖並聚焦目標，該輸入本身不執行（choice 仍在）。
        stick(page, "right")
        assert wait_until(lambda: view(page) == "map" and focused_choice_town(page, "desktop")), (view(page), pad(page))
        assert pending(page) and pending(page)["choice_id"] == choice_id
        assert me(page)["moves_left"] == 0
        build_with_controller(page, "desktop", expected_propagandists=1)
    finally:
        page.context.close()


def test_slow_map_iframe_load_recovers_without_mouse(browser, app_url):
    """iframe 掛載後 /map-data 晚到：早送的 snapshot 指令落空也不能形成永久鎖死。"""
    page = open_game(browser, app_url, "desktop", ["宣傳家", "宣傳家"])
    delayed = []

    def slow_map_data(route):
        delayed.append(route.request.url)
        time.sleep(2.0)
        route.continue_()

    page.route("**/map-data*", slow_map_data)
    try:
        play_propagandist_action(page, "desktop")
        assert wait_until(lambda: view(page) == "map", timeout=4)
        assert wait_until(lambda: focused_choice_town(page, "desktop"), timeout=12), pad(page)
        assert delayed, "map data request was not delayed"
        build_with_controller(page, "desktop", expected_propagandists=1)
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_choice_opened_before_controller_use_recovers_with_one_input(browser, app_url, display):
    """宣傳家由既有「行動」按鈕打出（控制器尚未操作過），手上另一張宣傳家讓既有流程留在指揮中心、戰略地圖 iframe 從未載入。
    第一個控制器輸入就以既有分頁切換到地圖並載入；之後只用控制器完成建立與遷移。"""
    page = open_game(browser, app_url, display, ["宣傳家", "宣傳家"])
    try:
        for _ in range(6):  # 隨機事件揭示：以既有背景關閉收起（不經過控制器，控制器維持未啟用）
            if pad(page)["scope"] in ("page", "map"):
                break
            page.evaluate("document.getElementById('eventRevealModal')?.click()")
            time.sleep(0.4)
        assert pad(page)["scope"] == "page" and not pad(page)["padActive"], pad(page)
        page.evaluate("document.querySelector('#hand button[data-card-index=\"0\"][data-card-mode=\"action\"]').click()")
        choice = wait_until(lambda: pending(page))
        assert choice and choice["choice_key"] == "card_build_organization" and choice["queueable_card_names"], choice
        time.sleep(0.8)
        assert view(page) == "command", view(page)
        assert page.evaluate("document.getElementById('strategicMapFrame').getAttribute('src')") in (None, "", "about:blank")
        stick(page, "down")
        assert wait_until(lambda: view(page) == "map" and focused_choice_town(page, display), timeout=12), (view(page), pad(page))
        assert pending(page) and pending(page)["choice_id"] == choice["choice_id"], "the redirecting input must not execute"
        build_with_controller(page, display, expected_propagandists=1)
        move_with_controller(page, display)
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()
