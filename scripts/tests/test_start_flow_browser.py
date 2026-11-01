"""開始遊戲前流程的 Browser（Playwright／Chromium）驗證。

伺服器是真的 uvicorn（server.main:app）。Joy-Con 部分 **沒有實體硬體**：使用真的 tools.joycon_bridge 的
ControllerRegistry＋WebSocket bridge app，由測試執行緒以 fixture 的 FTCW S2B1／S2N1 封包模擬四支手把
（物理 SL／SR 位元取自 fixtures/joycon_dual_layout.json）。因此這裡驗證的是 bridge v2 協定、瀏覽器配對邏輯與
伺服器狀態，不是真實 Joy-Con 的藍牙／FTCW 行為（見 TODO.md 的實機驗證項目）。

設定環境變數 START_FLOW_PROOF_DIR 時，會把正式 Browser UI 截圖寫到該目錄（docs/records/start-flow/）。
"""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

playwright_sync = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")

from tools.joycon_bridge import bridge as B  # noqa: E402

PROOF_DIR = os.environ.get("START_FLOW_PROOF_DIR")
PORTS = (24800, 24801, 24802, 24803)
NAMES = {24800: "Joy-Con 2 (R)", 24801: "Joy-Con 2 (L)", 24802: "Joy-Con 2 (R)", 24803: "Joy-Con 2 (L)"}
# 物理 SL＋SR 位元（fixtures/joycon_dual_layout.json）：右 offset 8 的 0x20／0x10；左 offset 10 的 0x20／0x10。
LEFT_PHYSICAL = {"A": (10, 0x04), "B": (10, 0x01)}
CHORD_OFFSET = {"R": (8, 0x30), "L": (10, 0x30)}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def s2b1(offset: int | None = None, value: int = 0) -> bytes:
    data = bytearray(b"S2B1" + struct.pack("<I", 1) + b"\0" * 4 + struct.pack("<4f", 0, 0, 0, 0) + b"\0" * 16)
    if offset is not None:
        data[offset] |= value
    return bytes(data)


class FakeJoyCons:
    """真的 ControllerRegistry＋bridge app；4 支 fixture 手把（不是實體硬體）。"""

    def __init__(self, page_origin: str, present=PORTS):
        self.registry = B.ControllerRegistry(PORTS, primary_port=24800)
        self.port = free_port()
        self.chord: set[int] = set()
        self.held: dict[int, list[tuple[int, int]]] = {}  # port -> [(packet offset, mask)] 目前按住的實體鍵
        self.stick: dict[int, tuple[float, float]] = {}  # port -> 左搖桿 (x, y)；FTCW 向上為正
        self.present = set(present)  # 目前送封包的埠；拿掉＝手把訊號消失（bridge 1 秒後標成 stale）
        self._stop = threading.Event()
        app = B.create_app(self.registry, allowed_origins=[page_origin])
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error"))
        self.threads = [threading.Thread(target=self.server.run, daemon=True), threading.Thread(target=self._feed, daemon=True)]
        for t in self.threads:
            t.start()
        deadline = time.time() + 10
        while not self.server.started and time.time() < deadline:
            time.sleep(0.05)

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/ws"

    def _feed(self):
        while not self._stop.is_set():
            for port in PORTS:
                if port not in self.present:
                    continue
                self.registry.observe(port, b"S2N1" + NAMES[port].encode())
                side = "L" if "(L)" in NAMES[port] else "R"
                offset, value = CHORD_OFFSET[side]
                data = bytearray(s2b1(offset, value) if port in self.chord else s2b1())
                for off, mask in list(self.held.get(port, ())):
                    data[off] |= mask
                # 只讀一次：測試執行緒可能剛好 pop 掉（先 in 再取值會 KeyError，feed 執行緒就此停掉）。
                stick = self.stick.get(port)
                if stick is not None:
                    data[12:20] = struct.pack("<2f", *stick)
                self.registry.observe(port, bytes(data))
            time.sleep(0.03)

    def controller_id(self, port: int) -> str:
        return B.controller_id(B.detect_side(NAMES[port]), port, NAMES[port])

    def press_chord(self, port: int, hold: float = 0.35):
        self.chord.add(port)
        time.sleep(hold)
        self.chord.discard(port)
        time.sleep(0.2)

    def press(self, port: int, logical: str, hold: float = 0.25):
        """按一下左 Joy-Con 的實體鍵：A＝Right、B＝Down（fixture）。"""
        offset, mask = LEFT_PHYSICAL[logical]
        self.held[port] = [(offset, mask)]
        time.sleep(hold)
        self.held.pop(port, None)
        time.sleep(0.2)

    def _wait_bridge_button(self, port: int, logical: str, pressed: bool, timeout: float = 3.0):
        """等 bridge registry 最新的 frame 真的是「按住／放開」：feed 執行緒每 30ms 才送一次，和瀏覽器沒有先後保證。"""
        cid = self.controller_id(port)
        index, bit = B.LOGICAL_BITS[logical]
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = (self.registry.snapshot().get(cid) or {}).get("frame")
            if frame is not None and bool((frame.b0, frame.b1)[index] & bit) is pressed:
                return
            time.sleep(0.005)
        raise AssertionError(f"bridge 在 {timeout}s 內沒有收到 {port} 的 {logical}{'按住' if pressed else '放開'}")

    def hold(self, port: int, logical: str):
        """按住左 Joy-Con 的實體鍵不放，並等 bridge 已收到：之後才建立的連線，第一筆 frame 一定已經按著。"""
        self.held[port] = [LEFT_PHYSICAL[logical]]
        self._wait_bridge_button(port, logical, True)

    def release(self, port: int, logical: str):
        self.held.pop(port, None)
        self._wait_bridge_button(port, logical, False)

    def nav(self, port: int, direction: str, hold: float = 0.25):
        """左搖桿推一下（回中後才算下一次）：這是 Joy-Con 的方向導覽輸入。"""
        x, y = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}[direction]
        self.stick[port] = (float(x), float(y))
        time.sleep(hold)
        self.stick.pop(port, None)
        time.sleep(0.2)

    def close(self):
        self._stop.set()
        self.server.should_exit = True


@pytest.fixture(scope="module")
def app_url():
    port = free_port()
    env = {**os.environ, "ENABLE_TEST_ROUTES": "false"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
                            cwd=ROOT, env=env)
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
def joycons(app_url):
    fake = FakeJoyCons(app_url)
    yield fake
    fake.close()


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment without Chromium
            pytest.skip(f"chromium unavailable: {exc}")
        yield b
        b.close()


def new_page(browser, app_url, joycons=None, display=None, init_script=None):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    if joycons is not None:
        ctx.add_init_script(
            "if (!localStorage.getItem('redline.controller.v1')) localStorage.setItem('redline.controller.v1', "
            f"JSON.stringify({{enabled: false, url: '{joycons.url}'}}));"
        )
    if init_script:
        ctx.add_init_script(init_script)
    page = ctx.new_page()
    page.goto(app_url + ("/?display=" + display if display else "/"))
    page.wait_for_selector("#startFlow:not([hidden])")
    return page


def shot(page, name):
    if PROOF_DIR:
        Path(PROOF_DIR).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(PROOF_DIR) / name))


def lobby_of(app_url, page):
    game_id = page.evaluate("window.RedlineSession.current().gameId")
    return game_id, requests.get(f"{app_url}/lobby/{game_id}").json()


def create_via_flow(page, ai=False, market=None, control="computer"):
    page.click("#sfCreateAi" if ai else "#sfCreateHuman")
    if market:
        page.click(f'[data-sf-market="{market}"]')
    page.click(f'[data-sf-control="{control}"]')


def test_joycon_connection_guide_only_appears_for_joycon(browser, app_url):
    page = new_page(browser, app_url)
    page.click("#sfCreateHuman")
    guide = page.locator("#sfJoyconConnectGuide")
    assert not guide.is_visible()
    page.click('[data-sf-control="joycon"]')
    assert guide.is_visible()
    guide_box = guide.bounding_box()
    assert guide_box and guide_box["x"] > 720 and guide_box["y"] < 60
    assert page.locator('#sfJoyconConnectGuide img[src="/static/help/joycon-connect-guide.jpg"]').count() == 1
    assert page.locator("#sfJoyconConnectGuide img").is_visible()
    page.click('[data-sf-control="computer"]')
    assert not guide.is_visible()


def finish_and_create(page, name="Tester", proof=None):
    page.click("#sfContinueBtn")
    page.wait_for_selector("#startFlow", state="hidden")
    page.fill("#playerName", name)
    if proof:
        shot(page, proof)
    page.click("#createRoomBtn")
    page.wait_for_function("window.RedlineSession.current().gameId")


def finish_joycon(page):
    """Joy-Con：完成配對後自動建房；不填代號、不點建立鈕，等陣營選擇自動開啟。"""
    page.click("#sfContinueBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)


def pad_finish_pairing(page, joycons, port=24801):
    """P1 的 Joy-Con 以方向鍵＋A 完成配對（手把因此已啟用，之後焦點由流程明確指定）。"""
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % joycons.controller_id(port), timeout=15000)
    for _ in range(6):
        if focus_id(page) == "sfContinueBtn":
            break
        joycons.nav(port, "down")
    assert focus_id(page) == "sfContinueBtn"
    joycons.press(port, "A")


def test_entry_offers_three_paths_and_no_player_count(browser, app_url):
    page = new_page(browser, app_url)
    assert page.inner_text("#sfCreateHuman").startswith("真人紅軍")
    assert page.inner_text("#sfCreateAi").startswith("AI 紅軍")
    assert page.is_visible("#sfRoomCode") and page.is_visible("#sfJoinBtn")
    text = page.inner_text("#startFlow")
    assert "人數" not in text and "幾人" not in text
    assert page.locator("#startFlow select").count() == 0
    # 入口只有三條路：隱藏的作戰準備室不在畫面（Joy-Con 焦點集合因此不含它）。
    assert not page.locator("#lobby .lobby-card").is_visible()
    # 入口直接疊在 1280×720 主視覺下方，不得再以大型面板遮住「逆統戰」標題。
    human = page.locator("#sfCreateHuman").bounding_box()
    ai = page.locator("#sfCreateAi").bounding_box()
    panel = page.locator("#startFlow").bounding_box()
    assert panel == {"x": 0, "y": 0, "width": 1280, "height": 720}
    join = page.locator(".sf-path-join").bounding_box()
    assert human == {"x": 170, "y": 606, "width": 294, "height": 64}
    assert ai == {"x": 493, "y": 606, "width": 294, "height": 64}
    assert join == {"x": 816, "y": 606, "width": 294, "height": 64}
    shot(page, "01_entry_three_paths.png")
    page.context.close()


@pytest.mark.parametrize("ai,market,label", [(False, "sample_53", "真人紅軍"), (False, "all_cards", "真人紅軍"),
                                              (True, "sample_53", "AI 紅軍"), (True, "all_cards", "AI 紅軍")])
def test_create_both_red_army_types_and_difficulties(browser, app_url, ai, market, label):
    page = new_page(browser, app_url)
    create_via_flow(page, ai=ai, market=market, control="computer")
    assert label in page.inner_text("#sfSetupTitle")
    assert page.is_enabled("#sfContinueBtn")  # 電腦操作不需配對
    if not ai and market == "sample_53":
        shot(page, "02_setup_computer.png")
    finish_and_create(page, proof="09_host_name_and_faction_screen.png" if (not ai and market == "all_cards") else None)
    # 同一個既有「行動代號／陣營」畫面：陣營選擇視窗打開，行動代號欄在作戰室內。
    page.wait_for_selector("#factionPicker", state="visible")
    _, state = lobby_of(app_url, page)
    assert (state["ai_red_army"], state["market_mode"], state["control_mode"], state["joycon_count"]) == (ai, market, "computer", None)
    assert label in page.inner_text("#roomSettingsSummary")
    for selector in ("#difficultyField", "#marketModeSelect", "[data-market-mode]", "#aiRedArmyField", "#aiRedArmySelect", "[data-ai-red-army]"):
        assert page.locator(selector).count() == 0, selector
    page.context.close()


def test_guest_joins_by_code_skips_setup_and_cannot_change_settings(browser, app_url):
    host = new_page(browser, app_url)
    create_via_flow(host, ai=True, market="all_cards", control="computer")
    finish_and_create(host, "房主")
    game_id, _ = lobby_of(app_url, host)

    guest = new_page(browser, app_url)
    guest.fill("#sfRoomCode", "no-such-room")
    guest.click("#sfJoinBtn")
    guest.wait_for_function("document.getElementById('sfJoinError').textContent.includes('找不到')")
    guest.fill("#sfRoomCode", game_id)
    guest.click("#sfJoinBtn")
    guest.wait_for_selector("#startFlow", state="hidden")
    # 沒有經過紅軍類型／難度／操作方式／配對步驟；直接是既有的行動代號畫面並沿用房主設定。
    assert guest.get_attribute("#lobby", "data-flow") == "join"
    assert not guest.is_visible("#sfSetup")
    assert guest.input_value("#roomId") == game_id
    assert "AI 紅軍｜一般模式｜操作：電腦" in guest.inner_text("#roomSettingsSummary")
    assert guest.is_visible("#playerName") and guest.is_visible("#joinRoomBtn") and not guest.is_visible("#createRoomBtn")
    # 加入者的代號欄不能預設成現有房主（「host」是房主欄位的預設值），而且焦點在代號欄等著輸入。
    assert guest.input_value("#playerName") == ""
    assert guest.evaluate("document.activeElement.id") == "playerName"
    for selector in ("#difficultyField", "#marketModeSelect", "[data-market-mode]", "#aiRedArmyField", "#aiRedArmySelect", "[data-ai-red-army]"):
        assert guest.locator(selector).count() == 0, selector
    shot(guest, "05_guest_join_readonly_settings.png")
    guest.fill("#playerName", "訪客")
    guest.click("#joinRoomBtn")
    guest.wait_for_selector("#factionPicker", state="visible")
    guest_id = guest.evaluate("window.RedlineSession.current().playerId")
    # 伺服器拒絕訪客改設定，且設定沒變。
    assert requests.post(f"{app_url}/market-mode", json={"game_id": game_id, "player_id": guest_id, "market_mode": "sample_53"}).json()["error"]
    assert requests.post(f"{app_url}/ai-red-army", json={"game_id": game_id, "player_id": guest_id, "enabled": False}).json()["error"]
    state = requests.get(f"{app_url}/lobby/{game_id}").json()
    assert (state["ai_red_army"], state["market_mode"]) == (True, "all_cards")
    # 訪客從公開 /lobby 看得到 host_id，但沒有房主 resume_token 就不能冒充房主。
    host_id = state["host_id"]
    for route, body in (("/market-mode", {"market_mode": "sample_53"}), ("/ai-red-army", {"enabled": False}), ("/start", {})):
        res = requests.post(f"{app_url}{route}", json={"game_id": game_id, "player_id": host_id, **body}).json()
        assert res == {"error": "Host authentication failed"}, (route, res)
    state = requests.get(f"{app_url}/lobby/{game_id}").json()
    assert (state["ai_red_army"], state["market_mode"], state["started"]) == (True, "all_cards", False)
    host.context.close()
    guest.context.close()


def test_toggles_expose_aria_pressed_and_focus_follows_step_changes(browser, app_url):
    page = new_page(browser, app_url)
    pressed = lambda attr: page.evaluate(
        f"[...document.querySelectorAll('[data-sf-{attr}]')].map(b => [b.dataset.sf{attr.capitalize()}, b.getAttribute('aria-pressed')])")
    page.click("#sfCreateHuman")
    assert page.evaluate("document.activeElement.id") == "sfSetupTitle"
    assert pressed("market") == [["sample_53", "true"], ["all_cards", "false"]]
    assert pressed("control") == [["joycon", "false"], ["computer", "true"]]
    assert page.locator('[data-sf-mode-guide="sample_53"]').get_attribute("data-selected") == "true"
    assert page.locator('[data-sf-mode-guide="all_cards"]').get_attribute("data-selected") == "false"
    guide_text = page.inner_text(".sf-mode-guide")
    assert "53 張精簡牌組" in guide_text and "245 張完整牌組" in guide_text
    assert "客廳輪流" not in guide_text and "同一台電腦，多位玩家" not in guide_text
    setup_box = page.locator("#sfSetup").bounding_box()
    guide_box = page.locator(".sf-mode-guide").bounding_box()
    assert setup_box and guide_box
    assert guide_box["y"] + guide_box["height"] <= setup_box["y"] + setup_box["height"]
    page.click('[data-sf-market="all_cards"]')
    assert pressed("market") == [["sample_53", "false"], ["all_cards", "true"]]
    assert page.locator('[data-sf-mode-guide="sample_53"]').get_attribute("data-selected") == "false"
    assert page.locator('[data-sf-mode-guide="all_cards"]').get_attribute("data-selected") == "true"
    page.click('[data-sf-control="joycon"]')
    assert pressed("control") == [["joycon", "true"], ["computer", "false"]]
    page.click('[data-sf-control="computer"]')
    assert pressed("control") == [["joycon", "false"], ["computer", "true"]]
    page.click("#sfBackToEntry")
    assert page.evaluate("document.activeElement.id") == "sfTitle"
    page.click("#sfCreateAi")
    assert page.evaluate("document.activeElement.id") == "sfSetupTitle"
    page.click("#sfContinueBtn")
    page.wait_for_selector("#startFlow", state="hidden")
    assert page.evaluate("document.activeElement.id") == "playerName"
    page.context.close()


def test_joycon_seat_provisioning_failure_keeps_pairing_and_retry_creates_no_duplicates(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, control="joycon")
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    order = [24801, 24800]
    for n, port in enumerate(order, start=1):
        joycons.press_chord(port)
        page.wait_for_function(f"window.RedlineStartFlow.getState().paired.length === {n}", timeout=8000)
    paired = page.evaluate("window.RedlineStartFlow.getState().paired")

    page.route("**/join", lambda route: route.fulfill(json={"error": "Room full"}))
    pad_finish_pairing(page, joycons)
    page.wait_for_selector("#sfAutoRetryBtn", state="visible", timeout=20000)
    game_id = page.evaluate("window.RedlineSession.current().gameId")
    assert game_id
    assert page.is_hidden("#factionPicker"), "席位未配置成功不可進入陣營畫面"
    assert page.is_hidden("#createRoomBtn") and page.is_hidden("#sfAutoBackBtn"), "已建房不可退回配對，也不顯示建立鈕"
    state = page.evaluate("window.RedlineStartFlow.getState()")
    assert state["pending"] and state["pending"]["controllers"] == paired and state["paired"] == paired
    assert len(requests.get(f"{app_url}/lobby/{game_id}").json()["players"]) == 1
    # 重試鈕可由 Joy-Con 操作：焦點在重試鈕，A 觸發。
    page.wait_for_function("document.activeElement && document.activeElement.id === 'sfAutoRetryBtn'", timeout=5000)

    # 網路恢復後用 Joy-Con A 重試：同一個房間，只補缺的席位。
    page.unroute("**/join")
    joycons.press(24801, "A")
    page.wait_for_selector("#factionPicker", state="visible", timeout=20000)
    assert page.evaluate("window.RedlineSession.current().gameId") == game_id
    players = requests.get(f"{app_url}/lobby/{game_id}").json()["players"]
    assert len(players) == 2
    page.wait_for_function("window.RedlineHotSeat.getState().seats.length === 2 && window.RedlineHotSeat.getState().seats.every(s => s.controller)", timeout=20000)
    assert [s["controller"] for s in page.evaluate("window.RedlineHotSeat.getState().seats")] == paired
    assert page.evaluate("window.RedlineStartFlow.getState().pending") is None
    assert page.is_hidden("#sfAutoSetup")
    page.context.close()


def test_joycon_create_failure_can_go_back_to_pairing_then_retry_creates_one_room(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, control="joycon")
    pair_one_left(page, joycons)
    page.route("**/create", lambda route: route.fulfill(json={"error": "boom"}))
    page.click("#sfContinueBtn")
    page.wait_for_selector("#sfAutoRetryBtn", state="visible", timeout=20000)
    assert page.evaluate("window.RedlineSession.current().gameId") in (None, "")
    assert page.is_visible("#sfAutoBackBtn")
    page.unroute("**/create")
    page.click("#sfAutoRetryBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=20000)
    game_id, state = lobby_of(app_url, page)
    assert state["control_mode"] == "joycon" and [p[1] for p in state["players"]] == ["P1"]
    page.context.close()


def test_joycon_create_response_lost_retries_same_room(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, control="joycon")
    pair_one_left(page, joycons)
    lost = []

    def lose_first_create_response(route):
        if lost:
            route.continue_()
            return
        lost.append(route.fetch().json())
        route.abort("connectionreset")

    page.route("**/create", lose_first_create_response)
    page.click("#sfContinueBtn")
    page.wait_for_selector("#sfAutoRetryBtn", state="visible", timeout=20000)
    created_game_id = lost[0]["game_id"]
    assert requests.get(f"{app_url}/lobby/{created_game_id}").json()["players"][0][1] == "P1"

    page.click("#sfAutoRetryBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=20000)
    assert page.evaluate("window.RedlineSession.current().gameId") == created_game_id
    assert requests.get(f"{app_url}/lobby/{created_game_id}").json()["players"] == [
        [lost[0]["host_id"], "P1"]
    ]
    page.context.close()


def test_hiding_start_flow_ignores_late_create_response(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, control="joycon")
    pair_one_left(page, joycons)
    page.evaluate("""() => {
      const originalFetch = window.fetch.bind(window);
      window.__releaseCreateResponse = null;
      window.fetch = (input, init) => {
        const response = originalFetch(input, init);
        const url = typeof input === 'string' ? input : input.url;
        if (!url.endsWith('/create')) return response;
        return response.then(value => new Promise(resolve => {
          window.__releaseCreateResponse = () => resolve(value);
        }));
      };
    }""")
    page.click("#sfContinueBtn")
    page.wait_for_function("typeof window.__releaseCreateResponse === 'function'", timeout=20000)
    page.evaluate("window.RedlineStartFlow.hide()")
    page.evaluate("window.__releaseCreateResponse()")
    time.sleep(0.5)
    assert page.evaluate("window.RedlineSession.current().gameId") in (None, "")
    assert page.is_hidden("#factionPicker") and page.is_hidden("#sfAutoSetup")
    assert page.evaluate("window.RedlineStartFlow.getState().pending") is None
    page.context.close()


def test_joycon_join_response_lost_after_server_created_seat_retry_recovers_same_seat(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, control="joycon")
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    for n, port in enumerate([24801, 24800, 24802], start=1):
        joycons.press_chord(port)
        page.wait_for_function(f"window.RedlineStartFlow.getState().paired.length === {n}", timeout=8000)
    paired = page.evaluate("window.RedlineStartFlow.getState().paired")

    # 第一個 /join：伺服器真的建立了 P2 席位，但回應在客戶端遺失（連線中斷）。
    lost = []

    def lose_first_join_response(route):
        if lost:
            route.continue_()
            return
        lost.append(route.fetch().json())
        route.abort("connectionreset")

    page.route("**/join", lose_first_join_response)
    page.click("#sfContinueBtn")
    page.wait_for_selector("#sfAutoRetryBtn", state="visible", timeout=20000)
    game_id = page.evaluate("window.RedlineSession.current().gameId")
    assert page.is_hidden("#factionPicker")
    orphan_id = lost[0]["player_id"]
    before = requests.get(f"{app_url}/lobby/{game_id}").json()["players"]
    assert [p[1] for p in before] == ["P1", "P2"] and before[1][0] == orphan_id
    assert page.evaluate("window.RedlineHotSeat.getState().seats.length") == 1  # 本機不知道有這一席

    # 重試：取回同一個 P2（不是跳到 P3 留下孤兒），再補 P3；房間、席位 ID、配對順序不變。
    page.click("#sfAutoRetryBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=20000)
    assert page.evaluate("window.RedlineSession.current().gameId") == game_id
    after = requests.get(f"{app_url}/lobby/{game_id}").json()["players"]
    assert [p[1] for p in after]== ["P1", "P2", "P3"]
    assert [p[0] for p in after[:2]] == [p[0] for p in before], "P2 必須是同一個席位 ID，不可重複建立"
    assert len({p[0] for p in after}) == 3
    page.wait_for_function("window.RedlineHotSeat.getState().seats.length === 3 && window.RedlineHotSeat.getState().seats.every(s => s.controller)", timeout=20000)
    seats = page.evaluate("window.RedlineHotSeat.getState().seats")
    assert [s["player_id"] for s in seats] == [p[0] for p in after]
    assert [s["controller"] for s in seats] == paired
    page.context.close()


def test_joycon_pairing_order_and_finish_threshold(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, market="all_cards", control="joycon")
    page.wait_for_selector('#sfPairing:not([hidden])')
    assert "SL + SR" in page.inner_text("#sfPairingPrompt")
    assert page.is_disabled("#sfContinueBtn"), "尚未配對任何手把時不可完成"
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    shot(page, "03_pairing_waiting.png")

    # 單按 SR 之類不算；SL＋SR 同時按才配對。依成功順序：先 24802，再 24801，再 24803。
    order = [24802, 24801, 24803]
    for port in order:
        joycons.press_chord(port)
        page.wait_for_function(f"window.RedlineStartFlow.getState().paired.length === {order.index(port) + 1}", timeout=8000)
        if port == order[0]:
            assert page.is_enabled("#sfContinueBtn"), "至少一支配對成功就可以完成配對"
            shot(page, "04_pairing_first_paired.png")
    paired = page.evaluate("window.RedlineStartFlow.getState().paired")
    assert paired == [joycons.controller_id(p) for p in order]
    assert [page.inner_text(f'[data-slot="P{i}"] strong') for i in (1, 2, 3)] == ["P1", "P2", "P3"]
    # 已配對的同一支再按不會重複；第四支還能配（真人紅軍最多四支）。
    joycons.press_chord(24802)
    assert len(page.evaluate("window.RedlineStartFlow.getState().paired")) == 3
    joycons.press_chord(24800)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 4", timeout=8000)
    shot(page, "06_pairing_four_paired.png")

    finish_joycon(page)  # 不填行動代號、不點建立鈕：自動以 P1 建房並開啟陣營選擇
    game_id, state = lobby_of(app_url, page)
    assert (state["control_mode"], state["joycon_count"], state["market_mode"], state["ai_red_army"]) == ("joycon", 4, "all_cards", False)
    # 客廳輪流席位：依配對順序 P1～P4 各綁一支。
    page.wait_for_function("window.RedlineHotSeat.getState().seats.length === 4 && window.RedlineHotSeat.getState().seats.every(s => s.controller)", timeout=20000)
    seats = page.evaluate("window.RedlineHotSeat.getState().seats")
    assert [s["controller"] for s in seats] == [joycons.controller_id(p) for p in order + [24800]]
    page.wait_for_function("(window.RedlineSession.current().lobby.players || []).map(p => p[1]).join() === 'P1,P2,P3,P4'", timeout=20000)
    page.context.close()


def test_ai_red_army_limits_pairing_to_three_and_computer_needs_no_pairing(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=True, control="joycon")
    page.wait_for_selector('#sfPairing:not([hidden])')
    assert page.locator(".sf-slot").count() == 3
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    for port in (24800, 24801, 24802, 24803):
        joycons.press_chord(port)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 3", timeout=8000)
    time.sleep(0.5)
    assert page.evaluate("window.RedlineStartFlow.getState().paired.length") == 3
    page.click('[data-sf-control="computer"]')
    assert page.is_hidden("#sfPairing") and page.is_enabled("#sfContinueBtn")
    assert page.evaluate("window.RedlineStartFlow.getState().listeners.length") == 0
    page.context.close()


def test_removed_living_room_display_falls_back_to_desktop(browser, app_url):
    """客廳大螢幕顯示模式已移除：舊的 ?display=living-room 書籤與已儲存的 'living-room' 都回到桌面並遷移儲存值，
    設定面板沒有顯示模式選單，RedlineDisplayMode.set('living-room') 也只會得到桌面。"""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script("if (!sessionStorage.getItem('seeded')) { localStorage.setItem('redline.display.v1', 'living-room'); sessionStorage.setItem('seeded', '1'); }")
    page = ctx.new_page()
    page.goto(app_url + "/?display=living-room")
    page.wait_for_selector("#startFlow:not([hidden])")
    assert page.evaluate("document.documentElement.dataset.display") is None
    assert page.evaluate("window.RedlineDisplayMode.get()") == "desktop"
    assert page.evaluate("localStorage.getItem('redline.display.v1')") == "desktop"
    assert page.evaluate("document.getElementById('padDisplaySelect')") is None
    assert "客廳" not in page.evaluate("document.getElementById('padPanel')?.textContent || ''")
    box = page.evaluate("(() => { const s = document.getElementById('designStage'); return [s.offsetWidth, s.offsetHeight]; })()")
    assert box == [1280, 720]
    zoom = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--stage-scale')")
    assert abs(float(zoom) - 1.0) < 1e-6
    page.evaluate("window.RedlineDisplayMode.set('living-room')")
    assert page.evaluate("[window.RedlineDisplayMode.get(), document.documentElement.dataset.display ?? null]") == ["desktop", None]
    assert page.evaluate("localStorage.getItem('redline.display.v1')") == "desktop"
    page.reload()
    page.wait_for_selector("#startFlow:not([hidden])")
    assert page.evaluate("[window.RedlineDisplayMode.get(), document.documentElement.dataset.display ?? null]") == ["desktop", None]
    shot(page, "07_desktop_after_living_room_removed.png")
    page.context.close()


def test_joycon_room_enables_controller_for_guest_but_computer_room_does_not(browser, app_url, joycons):
    host = new_page(browser, app_url, joycons)
    create_via_flow(host, control="joycon")
    host.wait_for_function("window.RedlineStartFlow.getState().listeners.some(l => l.owned)", timeout=20000)
    joycons.press_chord(24800)
    host.wait_for_function("window.RedlineStartFlow.getState().paired.length === 1", timeout=8000)
    finish_joycon(host)
    game_id, state = lobby_of(app_url, host)
    assert (state["control_mode"], state["joycon_count"]) == ("joycon", 1)
    assert host.evaluate("window.RedlineController.getState().enabled") is True

    guest = new_page(browser, app_url, joycons)
    guest.fill("#sfRoomCode", game_id)
    guest.click("#sfJoinBtn")
    guest.wait_for_selector("#startFlow", state="hidden")
    assert "Joy-Con ×1" in guest.inner_text("#roomSettingsSummary")
    guest.fill("#playerName", "訪客")
    guest.click("#joinRoomBtn")
    guest.wait_for_selector("#factionPicker", state="visible")
    guest.wait_for_function("window.RedlineController.getState().enabled === true", timeout=10000)

    plain_host = new_page(browser, app_url, joycons)
    create_via_flow(plain_host, control="computer")
    finish_and_create(plain_host)
    plain_id, _ = lobby_of(app_url, plain_host)
    plain_guest = new_page(browser, app_url, joycons)
    plain_guest.fill("#sfRoomCode", plain_id)
    plain_guest.click("#sfJoinBtn")
    plain_guest.wait_for_selector("#startFlow", state="hidden")
    plain_guest.fill("#playerName", "訪客")
    plain_guest.click("#joinRoomBtn")
    plain_guest.wait_for_selector("#factionPicker", state="visible")
    assert plain_guest.evaluate("window.RedlineController.getState().enabled") is False
    for p in (host, guest, plain_host, plain_guest):
        p.context.close()


def test_reload_resumes_room_without_showing_start_flow(browser, app_url):
    page = new_page(browser, app_url)
    create_via_flow(page)
    finish_and_create(page, "重整")
    page.reload()
    page.wait_for_function("window.RedlineSession.current().gameId")
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "done"
    page.context.close()


# ---------------------------------------------------------------- Joy-Con 配對後的作戰準備畫面
def pair_one_left(page, joycons):
    """AI／真人皆可：只配對左 Joy-Con（24801）→ P1。"""
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    joycons.press_chord(24801)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 1", timeout=8000)


def visible(page, sel):
    return page.evaluate("(s) => { const e = document.querySelector(s); if (!e) return false; const r = e.getBoundingClientRect(); return getComputedStyle(e).display !== 'none' && r.width > 0 && r.height > 0; }", sel)


def focus_id(page):
    return page.evaluate("document.activeElement && (document.activeElement.id || document.activeElement.className)")


def test_joycon_two_pairs_ai_auto_creates_room_and_opens_faction_picker(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=True, market="all_cards", control="joycon")
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    order = [24801, 24800]
    joycons.press_chord(24801)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 1", timeout=8000)
    controller_id = joycons.controller_id(24801)
    # P1 在配對畫面就交給主控制連線：Joy-Con 本身能完成流程。
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % controller_id, timeout=15000)
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "setup"
    assert page.evaluate("window.RedlineStartFlow.getState().listeners.some(l => l.controller === '%s')" % controller_id) is False
    joycons.press_chord(24800)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 2", timeout=8000)
    paired = page.evaluate("window.RedlineStartFlow.getState().paired")
    assert paired == [joycons.controller_id(p) for p in order]
    # 真實 bridge frame：方向鍵移到「完成配對」，A 觸發既有 click handler。
    for _ in range(4):
        if focus_id(page) == "sfContinueBtn":
            break
        joycons.nav(24801, "down")
    assert focus_id(page) == "sfContinueBtn"
    joycons.press(24801, "A")
    # 不填 playerName、不點 createRoomBtn：陣營選擇自動開啟。
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    assert page.evaluate("window.RedlineStartFlow.getState().listeners.length") == 0
    for sel in ("#playerName", "#createRoomBtn", "#hotseatEnableChk", "#hotseatAddSeatBtn", "#roomSettingsSummary", "#roomId", "#lanUrl",
                "#copyLanUrlBtn", "#copyRoomBtn", "#marketModeSelect", '[data-market-mode="all_cards"]', '[data-ai-red-army="on"]', "#sfAutoSetup"):
        assert not visible(page, sel), sel
    game_id, state = lobby_of(app_url, page)
    assert (state["control_mode"], state["joycon_count"], state["market_mode"], state["ai_red_army"]) == ("joycon", 2, "all_cards", True)
    page.wait_for_function("window.RedlineHotSeat.getState().seats.length === 2 && window.RedlineHotSeat.getState().seats.every(s => s.controller)", timeout=20000)
    page.wait_for_function("(window.RedlineSession.current().lobby.players || []).map(p => p[1]).join() === 'P1,P2'", timeout=20000)
    # 真人席位數＝配對手把數（server lobby 只有 P1、P2），AI 紅軍另有且只有一個 AI 席位。
    assert [p[1] for p in requests.get(f"{app_url}/lobby/{game_id}").json()["players"]] == ["P1", "P2"]
    page.wait_for_function("document.querySelectorAll('#lobbyRoster .ai-seat').length === 1")
    assert page.locator("#lobbyRoster .ai-seat[data-preroom]").count() == 0
    # 配對順序＝本機席位綁定順序。
    seats = page.evaluate("window.RedlineHotSeat.getState().seats")
    assert [s["controller"] for s in seats] == paired
    assert [p[0] for p in requests.get(f"{app_url}/lobby/{game_id}").json()["players"]] == [s["player_id"] for s in seats]
    # 焦點在合法的陣營選項（不是關閉鈕、代號欄或隱藏鈕）。
    page.wait_for_function("(() => { const a = document.activeElement; return !!a && !!a.closest('#factionList') && a.classList.contains('faction-choice-btn') && !a.disabled; })()", timeout=5000)
    assert page.evaluate("window.RedlineController.getState().controller.owned") == controller_id
    shot(page, "10_joycon_direct_faction.png")
    page.context.close()


ROSTER_LAYOUT_JS = """() => {
  const box = (s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, cx: (r.left + r.right) / 2 }; };
  const buttons = [...document.querySelectorAll('#lobby .lobby-actions .lobby-action-btn')]
    .filter(b => getComputedStyle(b).display !== 'none' && b.getClientRects().length).map(b => b.getBoundingClientRect());
  return {
    column: box('#lobby .lobby-roster-column'), roster: box('#lobbyRoster'), hint: box('#lobbyStatusHint'),
    actions: buttons.length ? { left: Math.min(...buttons.map(r => r.left)), right: Math.max(...buttons.map(r => r.right)), top: Math.min(...buttons.map(r => r.top)) } : null,
    buttonCount: buttons.length,
  };
}"""


def test_joycon_lobby_centers_roster_without_duplicate_hotseat_controls(browser, app_url, joycons):
    """Synthetic bridge（非實體 Joy-Con）：Joy-Con 建立／準備畫面只留席位卡片、狀態提示與底部操作鈕，席位以畫面中線置中。"""
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=True, control="joycon")
    pair_in_order(page, joycons, [24801, 24800])
    page.click("#sfContinueBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    page.wait_for_function("window.RedlineHotSeat.getState().seats.length === 2 && window.RedlineHotSeat.getState().seats.every(s => s.controller)", timeout=20000)
    page.wait_for_function("(window.RedlineSession.current().lobby.players || []).length === 2 && document.querySelectorAll('#lobbyRoster .ai-seat:not([data-preroom])').length === 1", timeout=20000)
    page.click("#closeFactionPickerBtn")
    page.wait_for_selector("#factionPicker", state="hidden")
    for sel in ("#hotseatLobby", "#hotseatEnableChk", "#hotseatAddSeatBtn", "#hotseatSeatList", "#hotseatLobbyHint"):
        assert page.locator(sel).count() == 0, sel
    # 席位卡片、狀態提示、底部操作鈕仍可見。
    for sel in ("#lobbyRoster", "#lobbyStatusHint", "#openFactionPickerBtn", "#toggleReadyBtn", "#startGameBtn"):
        assert visible(page, sel), sel
    assert page.locator("#lobbyRoster .lobby-player-card").count() == 4
    layout = page.evaluate(ROSTER_LAYOUT_JS)
    assert layout["buttonCount"] == 3, layout
    actions_cx = (layout["actions"]["left"] + layout["actions"]["right"]) / 2
    for key in ("column", "roster", "hint"):
        assert abs(layout[key]["cx"] - 640) <= 2, (key, layout)
    assert abs(actions_cx - 640) <= 2, layout
    # 席位區不遮住底部按鈕。
    assert max(layout["roster"]["bottom"], layout["hint"]["bottom"]) <= layout["actions"]["top"], layout
    proof = os.environ.get("REDLINE_CENTER_ROSTER_PROOF")
    if proof:
        page.screenshot(path=proof)
    page.context.close()


def test_switching_back_to_computer_cancels_pairing_claim_lifecycle(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, control="joycon")
    pair_one_left(page, joycons)
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % joycons.controller_id(24801), timeout=15000)
    page.click('[data-sf-control="computer"]')
    page.wait_for_function("!window.RedlineController.getState().enabled && window.RedlineController.getState().controller.owned === null")
    assert page.evaluate("window.RedlineStartFlow.getState().listeners.length") == 0
    assert page.evaluate("window.RedlineStartFlow.getState().claimPending") is False
    page.wait_for_timeout(1500)
    assert page.evaluate("window.RedlineController.getState().controller.owned") is None
    page.context.close()


def test_joycon_p1_claim_retries_beyond_reconnect_backoff_and_cancels_in_flight(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, control="joycon")
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    # 模擬主 controller socket 重連／claim 暫時不可送出。舊實作約 7.2 秒後會永久停止。
    page.evaluate("""() => {
      window.__realSelectController = window.RedlineController.selectController;
      window.RedlineController.selectController = () => false;
    }""")
    joycons.press_chord(24801)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 1", timeout=8000)
    page.wait_for_timeout(8500)
    assert page.evaluate("window.RedlineStartFlow.getState().claimPending") is True
    assert page.evaluate("window.RedlineController.getState().controller.owned") is None
    page.evaluate("""() => {
      window.RedlineController.selectController = window.__realSelectController;
      delete window.__realSelectController;
    }""")
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % joycons.controller_id(24801), timeout=15000)
    page.wait_for_function("!window.RedlineStartFlow.getState().claimPending", timeout=2000)
    page.context.close()

    # claim 尚未成功時直接切回電腦模式，handoff retry 必須停止且不可延遲重搶。
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, control="joycon")
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    page.evaluate("""() => {
      window.__realSelectController = window.RedlineController.selectController;
      window.RedlineController.selectController = () => false;
    }""")
    joycons.press_chord(24801)
    page.wait_for_function("window.RedlineStartFlow.getState().claimPending", timeout=8000)
    page.click('[data-sf-control="computer"]')
    assert page.evaluate("window.RedlineStartFlow.getState().claimPending") is False
    page.evaluate("""() => {
      window.RedlineController.selectController = window.__realSelectController;
      delete window.__realSelectController;
    }""")
    page.wait_for_timeout(1500)
    assert page.evaluate("window.RedlineController.getState().controller.owned") is None
    page.context.close()


def test_joycon_faction_picker_navigation_a_and_b(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, control="joycon")
    pair_one_left(page, joycons)
    finish_joycon(page)
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % joycons.controller_id(24801), timeout=15000)
    in_picker = "(() => { const a = document.activeElement; return a && a.closest('#factionPicker') ? (a.dataset.faction || a.id || a.textContent.trim().slice(0, 16)) : null; })()"
    # 陣營 modal：第一下只放焦點，之後方向在 modal 內可聚焦項目間移動。
    # 自動開啟時焦點已在第一個陣營；是否已啟用手把取決於時序，故以「起點＋三次導覽」整體判斷焦點確實移動過。
    page.wait_for_function(in_picker, timeout=5000)
    seen = [page.evaluate(in_picker)]
    for _ in range(3):
        joycons.nav(24801, "down")
        seen.append(page.evaluate(in_picker))
    assert all(seen) and len(set(seen)) > 1, seen
    # A＝既有預覽／確認：選定一個陣營後出現確認列或詳情。
    joycons.press(24801, "A")
    page.wait_for_function("document.getElementById('factionDetailPanel').style.display !== 'none' || document.getElementById('factionConfirmBar').style.display !== 'none'", timeout=5000)
    # B＝既有取消：最後可關閉 modal 回到 lobby（可能先退一層選擇）。
    for _ in range(4):
        if not visible(page, "#factionPicker"):
            break
        joycons.press(24801, "B")
    assert not visible(page, "#factionPicker")
    joycons.nav(24801, "down")
    assert page.evaluate("!!document.activeElement && !!document.activeElement.closest('#lobby')")
    page.context.close()


# ---------------------------------------------------------------- 配對畫面 P1 的 A／B（synthetic bridge，不等於實機）
# ---------------------------------------------------------------- 陣營選擇的 Joy-Con 階段：陣營 →（具體陣營）→ 根據地 → 閱讀 → A 確認
# Synthetic bridge（fixture 封包，非實體 Joy-Con）。AI 紅軍房間：唯一真人席位不會被限制只能選紅軍。
PICKER_JS = """() => {
  const a = document.activeElement;
  const panel = document.getElementById('factionDetailPanel');
  const hint = document.getElementById('padHint');
  const ring = document.querySelector('#factionPicker .rl-pad-focus');
  return {
    open: getComputedStyle(document.getElementById('factionPicker')).display !== 'none',
    phase: document.getElementById('factionPicker').dataset.padPhase || null,
    focus: a && a.closest('#factionPicker') ? (a.id || a.textContent.trim()) : null,
    focusIn: a && a.parentElement ? a.parentElement.id : null,
    ring: ring ? (ring.id || ring.textContent.trim()) : null,
    faction: pendingFactionChoice, base: pendingFactionBaseChoice,
    category: pendingFactionCategory ? pendingFactionCategory.id : null,
    scrollTop: panel.scrollTop, maxScroll: panel.scrollHeight - panel.clientHeight,
    hint: hint && !hint.hidden ? hint.textContent : null,
    outer: [document.scrollingElement.scrollTop, document.getElementById('lobby').scrollTop,
      document.getElementById('designStage').scrollTop, document.getElementById('factionPicker').scrollTop,
      document.querySelector('.faction-picker-dialog').scrollTop],
  };
}"""

NAV_TOWARD_JS = """([sel, text]) => {
  const t = [...document.querySelectorAll(sel)].find(b => b.textContent.trim() === text);
  const a = document.activeElement;
  if (!t || !a) return null;
  if (a === t) return 'done';
  const r1 = a.getBoundingClientRect(), r2 = t.getBoundingClientRect();
  const dx = (r2.left + r2.right) / 2 - (r1.left + r1.right) / 2, dy = (r2.top + r2.bottom) / 2 - (r1.top + r1.bottom) / 2;
  if (Math.abs(dy) > Math.max(8, r1.height / 2)) return dy > 0 ? 'down' : 'up';
  return dx > 0 ? 'right' : 'left';
}"""

# 最後內容（時代關卡卡片或最後一段）完整落在右側面板可視範圍內，且不被底欄（footer）或 Joy-Con 提示遮住。
LAST_CONTENT_JS = """() => {
  const panel = document.getElementById('factionDetailPanel');
  const kids = [...panel.querySelectorAll('#factionDetailEra > *')];
  const last = kids[kids.length - 1] || panel.lastElementChild;
  const lr = last.getBoundingClientRect(), pr = panel.getBoundingClientRect();
  const footer = document.querySelector('.faction-picker-footer').getBoundingClientRect();
  const hint = document.getElementById('padHint');
  const hr = hint && !hint.hidden ? hint.getBoundingClientRect() : null;
  const overlapsHint = !!hr && hr.left < lr.right && hr.right > lr.left && hr.top < lr.bottom && hr.bottom > lr.top;
  return { lastBottom: lr.bottom, lastTop: lr.top, panelTop: pr.top, panelBottom: pr.bottom, footerTop: footer.top,
    clientBottom: pr.top + panel.clientTop + panel.clientHeight, overlapsHint };
}"""


def picker(page):
    return page.evaluate(PICKER_JS)


def pad_nav_to(page, joycons, port, selector, text, limit=20):
    """以搖桿把焦點移到 selector 內文字為 text 的按鈕（每次朝目標方向推一下）。"""
    for _ in range(limit):
        step = page.evaluate(NAV_TOWARD_JS, [selector, text])
        if step == "done":
            return
        assert step, (selector, text, picker(page))
        joycons.nav(port, step)
    assert page.evaluate(NAV_TOWARD_JS, [selector, text]) == "done", picker(page)


def wait_phase(page, phase, timeout=8000):
    page.wait_for_function("document.getElementById('factionPicker').dataset.padPhase === '%s'" % phase, timeout=timeout)
    page.wait_for_timeout(150)  # 讓 80ms reconcile 跑完，確認焦點穩定
    return picker(page)


def open_picker_with_pad(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=True, control="joycon")
    pair_one_left(page, joycons)
    pad_finish_pairing(page, joycons)
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    page.wait_for_function("(() => { const a = document.activeElement; return !!a && !!a.closest('#factionList') && a.classList.contains('faction-choice-btn') && !a.disabled; })()", timeout=15000)
    page.wait_for_function("window.RedlineController.getState().padActive", timeout=5000)
    return page


def test_joycon_faction_picker_direct_faction_base_read_scroll_and_confirm(browser, app_url, joycons):
    """一般陣營：A 選陣營 → 焦點自動進根據地 → A 選根據地 → 閱讀（上下只捲右側資訊、到底可見最後內容）→ B／B 退回 → A 最終確認。"""
    page = open_picker_with_pad(browser, app_url, joycons)
    port = 24801
    s = picker(page)
    assert s["phase"] == "faction" and s["hint"] and s["hint"].endswith("搖桿 選擇陣營　A 選定　B 返回作戰室"), s
    pad_nav_to(page, joycons, port, "#factionList .faction-choice-btn", "蒙古")

    # 陣營 A → 自動進入根據地選擇（焦點在根據地清單，不需要再移動）。
    joycons.press(port, "A")
    s = wait_phase(page, "base")
    assert s["faction"] == "mongol" and s["base"] is None and s["focusIn"] == "factionBaseList" and s["ring"] == s["focus"], s
    assert s["hint"].endswith("搖桿 選擇根據地　A 選定　B 返回陣營"), s
    # 根據地階段：搖桿只在根據地之間移動，往上不會跳回陣營清單或關閉鈕。
    first = s["focus"]
    joycons.nav(port, "right")
    s = picker(page)
    assert s["focusIn"] == "factionBaseList" and s["focus"] != first and s["phase"] == "base", s
    for _ in range(3):
        joycons.nav(port, "up")
    s = picker(page)
    assert s["focusIn"] == "factionBaseList" and s["faction"] == "mongol", s
    pad_nav_to(page, joycons, port, "#factionBaseList .base-choice-btn", "東京")

    # 根據地 A → 閱讀陣營資訊：焦點在既有確認鈕，右側資訊從頂端開始。
    joycons.press(port, "A")
    s = wait_phase(page, "read")
    assert (s["faction"], s["base"], s["focus"], s["scrollTop"]) == ("mongol", "東京", "confirmFactionBtn", 0), s
    assert s["hint"].endswith("搖桿上下 捲動　A 確認　B 取消根據地／返回"), s
    assert s["maxScroll"] > 40, "右側資訊必須超出可視高度，捲動才有意義"
    outer = s["outer"]

    # 上下只捲動右側面板；陣營、根據地、焦點、整頁與背景都不變；捲到底有邊界。
    tops = [0]
    for _ in range(12):
        joycons.nav(port, "down")
        s = picker(page)
        assert (s["phase"], s["faction"], s["base"], s["focus"], s["outer"]) == ("read", "mongol", "東京", "confirmFactionBtn", outer), s
        tops.append(s["scrollTop"])
        if s["scrollTop"] >= s["maxScroll"] - 1:
            break
    assert tops == sorted(tops) and tops[-1] >= s["maxScroll"] - 1, tops
    joycons.nav(port, "down")
    s = picker(page)
    assert abs(s["scrollTop"] - tops[-1]) <= 1 and s["outer"] == outer, s
    last = page.evaluate(LAST_CONTENT_JS)
    assert last["lastBottom"] <= last["clientBottom"] + 1 and last["lastBottom"] <= last["footerTop"] and not last["overlapsHint"], last
    # 左右在閱讀階段不作用。
    joycons.nav(port, "left")
    s = picker(page)
    assert (s["focus"], s["base"], s["phase"]) == ("confirmFactionBtn", "東京", "read"), s
    proof = os.environ.get("REDLINE_FACTION_PICKER_READ_PROOF")
    if proof:
        page.screenshot(path=proof)
    joycons.nav(port, "up")
    assert picker(page)["scrollTop"] < tops[-1]

    # B：取消已選根據地，回到根據地選擇（焦點回到剛才的根據地）；再按 B 回到陣營選擇；選擇視窗仍開著、伺服器沒有變更。
    joycons.press(port, "B")
    s = wait_phase(page, "base")
    assert (s["faction"], s["base"], s["focus"], s["focusIn"]) == ("mongol", None, "東京", "factionBaseList"), s
    assert s["scrollTop"] == 0, "根據地改變後右側資訊回到頂端"
    joycons.press(port, "B")
    s = wait_phase(page, "faction")
    assert s["open"] and s["focus"] == "蒙古" and s["focusIn"] == "factionList", s
    assert s["hint"].endswith("搖桿 選擇陣營　A 選定　B 返回作戰室"), s
    game_id, lobby = lobby_of(app_url, page)
    pid = page.evaluate("window.RedlineSession.current().playerId")
    assert pid not in (lobby.get("factions") or {}), lobby

    # 重新走一次，閱讀階段 A 才是最終確認。
    joycons.press(port, "A")
    wait_phase(page, "base")
    pad_nav_to(page, joycons, port, "#factionBaseList .base-choice-btn", "紐約")
    joycons.press(port, "A")
    s = wait_phase(page, "read")
    assert (s["base"], s["scrollTop"]) == ("紐約", 0), s
    assert pid not in (requests.get(f"{app_url}/lobby/{game_id}").json().get("factions") or {})
    joycons.press(port, "A")
    page.wait_for_selector("#factionPicker", state="hidden", timeout=10000)
    lobby = requests.get(f"{app_url}/lobby/{game_id}").json()
    assert (lobby["factions"][pid], lobby["bases"][pid]) == ("mongol", "紐約"), lobby
    assert page.evaluate("document.getElementById('factionPicker').dataset.padPhase") == "faction"
    page.context.close()


def test_joycon_faction_picker_rebel_variant_then_base_and_b_chain_back_out(browser, app_url, joycons):
    """反賊：A 進入既有具體陣營選擇 → A 選定具體陣營後自動進根據地 → 閱讀；B 依序退回根據地、具體陣營、陣營，最後返回作戰室。"""
    page = open_picker_with_pad(browser, app_url, joycons)
    port = 24801
    pad_nav_to(page, joycons, port, "#factionList .faction-choice-btn", "反賊")
    joycons.press(port, "A")
    s = wait_phase(page, "variant")
    assert (s["category"], s["faction"], s["focusIn"]) == ("rebel", None, "factionVariantList"), s
    assert s["hint"].endswith("搖桿 選擇具體陣營　A 選定　B 返回陣營"), s
    # 具體陣營階段：搖桿不會離開具體陣營清單。
    joycons.nav(port, "up")
    joycons.nav(port, "right")
    s = picker(page)
    assert s["focusIn"] == "factionVariantList" and s["phase"] == "variant", s
    variant_text = s["focus"]
    expected_id = page.evaluate("(t) => availableFactionCategories.find(c => c.id === 'rebel').options.find(o => (o.variant || o.name || o.id) === t).id", variant_text)

    joycons.press(port, "A")
    s = wait_phase(page, "base")
    assert (s["category"], s["faction"], s["base"], s["focusIn"]) == ("rebel", expected_id, None, "factionBaseList"), s
    assert s["hint"].endswith("搖桿 選擇根據地　A 選定　B 返回具體陣營"), s
    town = page.evaluate("document.activeElement.dataset.baseTown")
    joycons.press(port, "A")
    s = wait_phase(page, "read")
    assert (s["faction"], s["base"], s["focus"]) == (expected_id, town, "confirmFactionBtn"), s

    joycons.press(port, "B")
    s = wait_phase(page, "base")
    assert (s["faction"], s["base"]) == (expected_id, None) and page.evaluate("document.activeElement.dataset.baseTown") == town, s
    joycons.press(port, "B")
    s = wait_phase(page, "variant")
    assert s["focus"] == variant_text and s["focusIn"] == "factionVariantList", s
    joycons.press(port, "B")
    s = wait_phase(page, "faction")
    assert s["focus"] == "反賊" and s["open"], s
    # 陣營階段的 B＝既有「返回作戰室」；沒有送出任何陣營選擇。
    joycons.press(port, "B")
    page.wait_for_selector("#factionPicker", state="hidden", timeout=5000)
    game_id, lobby = lobby_of(app_url, page)
    pid = page.evaluate("window.RedlineSession.current().playerId")
    assert pid not in (lobby.get("factions") or {}), lobby
    page.context.close()


# 陣營選擇清單（陣營／具體陣營／根據地）的 Joy-Con 焦點框：量 computed outline、按鈕 bounding box 是否因焦點改變，
# 以及整個黃框是否落在清單捲動容器的可視範圍內（清單是 overflow:auto，框畫到按鈕外面就會被裁掉）。
PICKER_RING_JS = """() => {
  const el = document.querySelector('#factionPicker .rl-pad-focus');
  if (!el) return null;
  const list = el.parentElement;
  const cs = getComputedStyle(el);
  const width = parseFloat(cs.outlineWidth), offset = parseFloat(cs.outlineOffset);
  const box = r => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height });
  const focused = box(el.getBoundingClientRect());
  el.classList.remove('rl-pad-focus');
  const plain = box(el.getBoundingClientRect());
  el.classList.add('rl-pad-focus');
  const out = Math.max(0, width + offset);  // 黃框超出按鈕框線的距離（offset 為負＝畫在按鈕內）
  const lr = list.getBoundingClientRect();
  const clip = { left: lr.left + list.clientLeft, top: lr.top + list.clientTop };
  clip.right = clip.left + list.clientWidth; clip.bottom = clip.top + list.clientHeight;
  const ring = { left: focused.left - out, top: focused.top - out, right: focused.right + out, bottom: focused.bottom + out };
  return {
    text: el.textContent.trim(), list: list.id, width, offset, style: cs.outlineStyle, color: cs.outlineColor,
    shadow: cs.boxShadow, focused, plain, ring, clip,
    ringInside: ring.left >= clip.left - 0.5 && ring.top >= clip.top - 0.5 && ring.right <= clip.right + 0.5 && ring.bottom <= clip.bottom + 0.5,
  };
}"""

# 在正式 Browser 截圖上取黃框四邊中點的像素（瀏覽器 canvas 解碼 PNG），確認四邊都真的畫出黃色。
RING_PIXELS_JS = """async ([png, m]) => {
  const img = new Image();
  img.src = 'data:image/png;base64,' + png;
  await img.decode();
  const c = document.createElement('canvas');
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext('2d');
  g.drawImage(img, 0, 0);
  const d = m.offset + m.width / 2;  // 黃框中線距按鈕框線的距離（負＝在按鈕內）
  const f = m.focused, cx = (f.left + f.right) / 2, cy = (f.top + f.bottom) / 2;
  const at = (x, y) => Array.from(g.getImageData(Math.floor(x), Math.floor(y), 1, 1).data.slice(0, 3));
  return { top: at(cx, f.top - d), bottom: at(cx, f.bottom + d - 1), left: at(f.left - d, cy), right: at(f.right + d - 1, cy), size: [c.width, c.height] };
}"""

GLOBAL_RING_JS = """() => {
  const b = document.createElement('button');
  b.className = 'rl-pad-focus';
  document.getElementById('designStage').appendChild(b);
  const cs = getComputedStyle(b);
  const r = { width: parseFloat(cs.outlineWidth), offset: parseFloat(cs.outlineOffset), shadow: cs.boxShadow };
  b.remove();
  return r;
}"""


def assert_picker_ring(page, list_id, proof_name=None):
    m = page.evaluate(PICKER_RING_JS)
    assert m and m["list"] == list_id, m
    # 縮小後的焦點框：3px 黃框畫在按鈕框線內（outline-offset -3px），只剩內側 inset 黑圈，沒有外圈光暈。
    assert (m["width"], m["offset"], m["style"]) == (3, -3, "solid"), m
    assert m["color"] == "rgb(255, 225, 77)", m
    assert m["shadow"].startswith("rgb(0, 0, 0)") and m["shadow"].endswith("inset") and m["shadow"].count("rgb") == 1, m
    # 焦點不改按鈕尺寸與位置（hit area 不變）。
    assert m["focused"] == m["plain"], m
    # 按鈕完整在清單可視範圍內，黃框四邊都沒有被清單捲動容器裁掉。
    assert m["ringInside"], m
    png = page.screenshot()
    px = page.evaluate(RING_PIXELS_JS, [base64.b64encode(png).decode(), m])
    assert px["size"] == [1280, 720], px
    for side in ("top", "bottom", "left", "right"):
        r, g, b = px[side]
        assert r >= 200 and g >= 180 and b <= 140, (side, px, m)
    proof_dir = os.environ.get("REDLINE_FACTION_FOCUS_PROOF_DIR")
    if proof_dir and proof_name:
        Path(proof_dir).mkdir(parents=True, exist_ok=True)
        Path(proof_dir, proof_name).write_bytes(png)
    return m


def test_joycon_faction_picker_focus_ring_is_compact_and_unclipped(browser, app_url, joycons):
    """陣營／具體陣營／根據地的 Joy-Con 焦點框畫在按鈕內，清單邊緣（第一列、捲動後的最後一列）四邊完整；全域焦點框同樣內縮。
    synthetic bridge（fixture 封包），不取代實體 Joy-Con 驗證。"""
    page = open_picker_with_pad(browser, app_url, joycons)
    port = 24801
    g = page.evaluate(GLOBAL_RING_JS)
    assert (g["width"], g["offset"]) == (3, -3) and g["shadow"].endswith("inset") and g["shadow"].count("rgb") == 1, g

    # 陣營：初始焦點在 #factionList 第一個（清單沒有 padding，框若畫在外面會被頂邊／左邊裁掉）。
    wait_phase(page, "faction")
    assert_picker_ring(page, "factionList", "faction_first.png")
    pad_nav_to(page, joycons, port, "#factionList .faction-choice-btn", "反賊")
    assert_picker_ring(page, "factionList", "faction_rebel.png")

    # 具體陣營（反賊）：第一個，以及捲到清單最後一列的最後一個。
    joycons.press(port, "A")
    s = wait_phase(page, "variant")
    assert s["focusIn"] == "factionVariantList", s
    assert_picker_ring(page, "factionVariantList", "variant_first.png")
    last_variant = page.evaluate("[...document.querySelectorAll('#factionVariantList .faction-choice-btn')].pop().textContent.trim()")
    pad_nav_to(page, joycons, port, "#factionVariantList .faction-choice-btn", last_variant, limit=40)
    assert page.evaluate("document.getElementById('factionVariantList').scrollTop") > 0, "最後一列需要捲動才看得到"
    assert_picker_ring(page, "factionVariantList", "variant_last.png")

    # 根據地：第一個與最後一個。
    joycons.press(port, "A")
    s = wait_phase(page, "base")
    assert s["focusIn"] == "factionBaseList", s
    assert_picker_ring(page, "factionBaseList", "base_first.png")
    last_base = page.evaluate("[...document.querySelectorAll('#factionBaseList .base-choice-btn:not(:disabled)')].pop().textContent.trim()")
    pad_nav_to(page, joycons, port, "#factionBaseList .base-choice-btn", last_base, limit=40)
    assert_picker_ring(page, "factionBaseList", "base_last.png")
    page.context.close()


def test_mouse_faction_picker_flow_unchanged_and_detail_scroll_is_bounded(browser, app_url):
    """滑鼠流程不回歸：點陣營／根據地不移動焦點、不進入 Joy-Con 階段；右側資訊在陣營／根據地改變時回到頂端，滾輪不捲背景。"""
    page = new_page(browser, app_url)
    create_via_flow(page, ai=True)
    finish_and_create(page)
    page.wait_for_selector("#factionPicker", state="visible")
    page.locator("#factionList .faction-choice-btn", has_text="蒙古").click()
    page.wait_for_selector("#factionBaseList .base-choice-btn")
    s = picker(page)
    assert s["phase"] == "faction" and s["focusIn"] != "factionBaseList" and s["ring"] is None, s
    page.locator("#factionBaseList .base-choice-btn", has_text="東京").click()
    page.wait_for_function("document.querySelector('#factionBaseList .base-choice-btn.active')?.dataset.baseTown === '東京'")
    s = picker(page)
    assert s["phase"] == "faction" and s["scrollTop"] == 0 and s["maxScroll"] > 40, s
    outer = s["outer"]
    box = page.locator("#factionDetailPanel").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(12):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(60)
    s = picker(page)
    assert s["scrollTop"] >= s["maxScroll"] - 1 and s["outer"] == outer, s
    last = page.evaluate(LAST_CONTENT_JS)
    assert last["lastBottom"] <= last["clientBottom"] + 1 and last["lastBottom"] <= last["footerTop"], last
    # 同一個選擇的重繪保留位置；換根據地回到頂端。
    page.evaluate("renderFactionPicker()")
    page.wait_for_timeout(300)
    assert picker(page)["scrollTop"] >= s["maxScroll"] - 1
    page.locator("#factionBaseList .base-choice-btn", has_text="紐約").click()
    page.wait_for_function("document.querySelector('#factionBaseList .base-choice-btn.active')?.dataset.baseTown === '紐約'")
    assert picker(page)["scrollTop"] == 0
    page.click("#confirmFactionBtn")
    page.wait_for_selector("#factionPicker", state="hidden")
    game_id, lobby = lobby_of(app_url, page)
    pid = page.evaluate("window.RedlineSession.current().playerId")
    assert (lobby["factions"][pid], lobby["bases"][pid]) == ("mongol", "紐約"), lobby
    # 重新開啟（變更陣營與根據地）：右側資訊從頂端開始，滑鼠仍可操作。
    page.click("#openFactionPickerBtn")
    page.wait_for_selector("#factionPicker", state="visible")
    s = picker(page)
    assert s["scrollTop"] == 0 and s["phase"] == "faction", s
    page.click("#closeFactionPickerBtn")
    page.wait_for_selector("#factionPicker", state="hidden")
    page.context.close()


def wait_listener_owns(page, controller_id, timeout=15000):
    page.wait_for_function(
        "window.RedlineStartFlow.getState().listeners.some(l => l.controller === '%s' && l.owned === '%s')"
        % (controller_id, controller_id), timeout=timeout)


def test_joycon_pairing_p1_a_finishes_without_moving_focus(browser, app_url, joycons):
    """Synthetic bridge（fixture 封包，不是實體 Joy-Con）：配對後 P1 不用方向鍵移焦點，直接按 A＝「完成配對」。"""
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, control="joycon")
    cid = joycons.controller_id(24801)
    pair_in_order(page, joycons, [24801])
    sent = track_mutations(page)
    page.wait_for_timeout(400)
    assert focus_id(page) != "sfContinueBtn", "前提：焦點不在「完成配對」"
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "setup"
    assert sent == [], "配對完成前不可送出任何 server mutation"
    joycons.press(24801, "A")
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    game_id, state = lobby_of(app_url, page)
    assert (state["control_mode"], state["joycon_count"]) == ("joycon", 1)
    assert [p[1] for p in state["players"]] == ["P1"]
    assert page.evaluate("window.RedlineController.getState().controller.owned") == cid
    page.context.close()


def test_joycon_pairing_b_cancels_then_second_b_returns_to_entry(browser, app_url, joycons):
    """Synthetic bridge（不等於實機）：第一次 B 清空配對並留在配對畫面；P1 交還配對 listener、沒有晚到 claim 奪回；再按 B 回開始選擇。"""
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, control="joycon")
    cid = joycons.controller_id(24801)
    pair_in_order(page, joycons, [24801, 24800])
    sent = track_mutations(page)

    joycons.press(24801, "B")
    page.wait_for_function("window.RedlineStartFlow.getState().cancelled && window.RedlineStartFlow.getState().paired.length === 0", timeout=5000)
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "setup"
    assert page.is_visible("#sfPairing") and page.get_attribute("#sfPairing", "data-cancelled") == "true"
    assert "已取消" in page.inner_text("#sfPairingStatus")
    assert "已取消" in page.inner_text("#sfContinueHint")
    assert page.is_disabled("#sfContinueBtn")
    assert page.evaluate("[...document.querySelectorAll('.sf-slot')].every(s => s.dataset.paired === 'false')")
    # 主連線釋放 P1、交接 claim 重試停止；P1 回到配對 listener（之後才能 SL＋SR 或 B）。
    wait_listener_owns(page, cid)
    page.wait_for_timeout(1500)
    assert page.evaluate("window.RedlineController.getState().controller.owned") is None, "晚到的 claim 不可奪回 P1"
    assert page.evaluate("window.RedlineStartFlow.getState().claimPending") is False
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "setup"

    joycons.press(24801, "B")
    page.wait_for_function("window.RedlineStartFlow.getState().step === 'entry'", timeout=5000)
    sf = page.evaluate("window.RedlineStartFlow.getState()")
    assert sf["cancelled"] is False and sf["paired"] == [] and sf["listeners"] == []
    assert page.is_visible("#sfCreateHuman") and page.is_visible("#sfCreateAi")
    assert page.is_hidden("#sfSetup")
    assert sent == [], sent
    page.context.close()


def test_joycon_pairing_second_b_only_from_cancelling_controller(browser, app_url, joycons):
    """Synthetic bridge（fixture 封包，不等於實體 Joy-Con）：原 P1 取消後，仍由配對 listener 持有的 P2 按 B
    不可返回、不可送 mutation、不可改變取消狀態；只有剛才取消的原 P1 再按 B 才回到開始選擇。"""
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=False, control="joycon")
    p1, p2 = joycons.controller_id(24801), joycons.controller_id(24803)
    pair_in_order(page, joycons, [24801, 24803])
    sent = track_mutations(page)

    joycons.press(24801, "B")
    page.wait_for_function("window.RedlineStartFlow.getState().cancelled && window.RedlineStartFlow.getState().paired.length === 0", timeout=5000)
    assert page.evaluate("window.RedlineStartFlow.getState().cancelledBy") == p1
    wait_listener_owns(page, p1)
    wait_listener_owns(page, p2)  # 前提：P2 仍由配對 listener 持有，它的 B 會送進配對 listener

    for _ in range(2):
        joycons.press(24803, "B")
    page.wait_for_timeout(800)
    sf = page.evaluate("window.RedlineStartFlow.getState()")
    assert sf["step"] == "setup", "P2 的 B 不可觸發「← 重新選擇」"
    assert sf["cancelled"] is True and sf["cancelledBy"] == p1 and sf["paired"] == [], sf
    assert page.get_attribute("#sfPairing", "data-cancelled") == "true"
    assert page.is_hidden("#sfEntry") and page.is_visible("#sfSetup")
    assert sent == [], sent

    joycons.press(24801, "B")
    page.wait_for_function("window.RedlineStartFlow.getState().step === 'entry'", timeout=5000)
    sf = page.evaluate("window.RedlineStartFlow.getState()")
    assert sf["cancelled"] is False and sf["cancelledBy"] is None and sf["paired"] == [] and sf["listeners"] == [], sf
    assert page.is_visible("#sfCreateHuman") and page.is_visible("#sfCreateAi")
    assert sent == [], sent
    page.context.close()


def test_joycon_pairing_b_cancel_then_sl_sr_repairs_and_a_finishes(browser, app_url, joycons):
    """Synthetic bridge（不等於實機）：第一次 B 後不再按 B，同一支重新 SL＋SR 成為 P1（ownership 回到主連線），之後 A 完成。"""
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=True, control="joycon")
    p1, p2 = joycons.controller_id(24801), joycons.controller_id(24803)
    pair_in_order(page, joycons, [24801])
    joycons.press(24801, "B")
    page.wait_for_function("window.RedlineStartFlow.getState().cancelled && window.RedlineStartFlow.getState().paired.length === 0", timeout=5000)
    wait_listener_owns(page, p1)

    joycons.press_chord(24801)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 1", timeout=8000)
    assert page.evaluate("window.RedlineStartFlow.getState().paired") == [p1]
    assert page.evaluate("window.RedlineStartFlow.getState().cancelled") is False
    assert page.evaluate("window.RedlineStartFlow.getState().cancelledBy") is None
    assert page.get_attribute("#sfPairing", "data-cancelled") is None
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % p1, timeout=15000)
    page.wait_for_function("!window.RedlineStartFlow.getState().claimPending", timeout=5000)
    joycons.press_chord(24803)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 2", timeout=8000)
    assert page.evaluate("window.RedlineStartFlow.getState().paired") == [p1, p2]
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "setup"
    assert page.is_enabled("#sfContinueBtn")

    joycons.press(24801, "A")
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    page.wait_for_function("window.RedlineHotSeat.getState().seats.length === 2 && window.RedlineHotSeat.getState().seats.every(s => s.controller)", timeout=20000)
    assert [s["controller"] for s in page.evaluate("window.RedlineHotSeat.getState().seats")] == [p1, p2]
    _, state = lobby_of(app_url, page)
    assert [p[1] for p in state["players"]] == ["P1", "P2"]
    page.context.close()


@pytest.mark.parametrize("ai", [True, False])
def test_computer_mode_keeps_room_settings_and_preroom_ai_seat_matches_entry(browser, app_url, ai):
    page = new_page(browser, app_url)
    create_via_flow(page, ai=ai, control="computer")
    page.click("#sfContinueBtn")
    page.wait_for_selector("#startFlow", state="hidden")
    for sel in ("#roomSettingsSummary", "#roomId", "#lanUrl", "#playerName", "#createRoomBtn"):
        assert visible(page, sel), sel
    assert page.locator("#lobbyRoster .ai-seat").count() == (1 if ai else 0)
    page.fill("#playerName", "Tester")
    page.click("#createRoomBtn")
    page.wait_for_selector("#factionPicker", state="visible")
    _, state = lobby_of(app_url, page)
    assert state["ai_red_army"] is ai
    page.wait_for_function(f"document.querySelectorAll('#lobbyRoster .ai-seat').length === {1 if ai else 0}")
    # 非 Joy-Con：維持左右兩欄，但不顯示重複的客廳輪流設定區。
    page.click("#closeFactionPickerBtn")
    page.wait_for_selector("#factionPicker", state="hidden")
    for sel in ("#hotseatLobby", "#hotseatEnableChk", "#hotseatAddSeatBtn", "#hotseatSeatList", "#hotseatLobbyHint"):
        assert page.locator(sel).count() == 0, sel
    assert page.evaluate(ROSTER_LAYOUT_JS)["column"]["left"] > 640
    page.context.close()


# ---------------------------------------------------------------- Joy-Con 逐棒交接（P1→P2→…→回房主 P1 啟動）
FACTION_PICKS = [("hong_kong", None), ("taiwan_green", None), ("tibet_family", None), ("red_army", "北京")]


def local_seats(page):
    gid = page.evaluate("window.RedlineSession.current().gameId")
    store = page.evaluate("JSON.parse(localStorage.getItem('redline.hotseat.v1'))")
    return gid, store["games"][gid]["seats"]


def pair_in_order(page, joycons, ports):
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.filter(l => l.owned).length === 4", timeout=20000)
    for n, port in enumerate(ports, start=1):
        joycons.press_chord(port)
        page.wait_for_function(f"window.RedlineStartFlow.getState().paired.length === {n}", timeout=8000)
        if n == 1:
            page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % joycons.controller_id(port), timeout=15000)
    return page.evaluate("window.RedlineStartFlow.getState().paired")


def wait_turn(page, joycons, player_id, port, picker=True):
    """這一棒：整頁已切到該席位、bridge 擁有權在它的手把、陣營選擇開啟且焦點在陣營選項。"""
    page.wait_for_function("window.RedlineSession.current().playerId === '%s'" % player_id, timeout=30000)
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % joycons.controller_id(port), timeout=30000)
    if picker:
        page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
        page.wait_for_function("(() => { const a = document.activeElement; return !!a && !!a.closest('#factionList') && a.classList.contains('faction-choice-btn') && !a.disabled; })()", timeout=30000)


def finish_turn(app_url, gid, seat, pick):
    player_id, token = seat["player_id"], seat["resume_token"]
    faction, base = pick
    body = {"game_id": gid, "player_id": player_id, "resume_token": token, "faction_id": faction}
    if base:
        body["base_name"] = base
    assert "error" not in requests.post(f"{app_url}/choose-faction", json=body).json()
    assert requests.post(f"{app_url}/ready", json={"game_id": gid, "player_id": player_id, "resume_token": token, "ready": True}).json().get("success")


def start_focused(page):
    page.wait_for_function("document.activeElement && document.activeElement.id === 'startGameBtn'", timeout=30000)


def test_joycon_two_players_hand_off_p1_to_p2_then_back_to_host_who_starts(browser, app_url, joycons):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=True, control="joycon")
    ports = [24801, 24800]  # P1＝左（A 鍵有 fixture 對應）、P2＝右
    pair_in_order(page, joycons, ports)
    page.click("#sfContinueBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    gid, seats = local_seats(page)
    lobby = requests.get(f"{app_url}/lobby/{gid}").json()
    # 兩支 → server lobby、本機 seat store 都是 P1、P2（AI 紅軍另占一席，不算真人）。
    assert [p[1] for p in lobby["players"]] == ["P1", "P2"]
    assert [s["player_id"] for s in seats] == [p[0] for p in lobby["players"]]
    assert [s["name"] for s in seats] == ["P1", "P2"], "本機 P1 席位也必須是 P1，不是輸入欄預設的 host"
    p1, p2 = seats[0], seats[1]
    wait_turn(page, joycons, p1["player_id"], 24801)
    assert page.evaluate("window.RedlineSession.current().playerId") == p1["player_id"]

    # P1 完成選擇並 ready → 自動把整個 session、bridge 擁有權、焦點交給 P2，並直接開啟 P2 的陣營選擇。
    finish_turn(app_url, gid, p1, FACTION_PICKS[0])
    wait_turn(page, joycons, p2["player_id"], 24800)
    assert page.evaluate("window.RedlineHotSeat.getState().controllerOwner.seat") == p2["player_id"]
    for sel in ("#playerName", "#createRoomBtn", "#roomSettingsSummary", "#roomId", "#lanUrl", "#marketModeSelect", '[data-ai-red-army="on"]'):
        assert not visible(page, sel), sel
    # 這一棒 reload：仍是 P2、不新增房間或席位。
    page.reload()
    page.wait_for_function("window.RedlineSession.current().playerId === '%s'" % p2["player_id"], timeout=30000)
    assert [p[0] for p in requests.get(f"{app_url}/lobby/{gid}").json()["players"]] == [p1["player_id"], p2["player_id"]]
    # P2 不能啟動：伺服器只認房主憑證，P2 自己的 token 也不行；公開 host_id 不是憑證。
    denied = requests.post(f"{app_url}/start", json={"game_id": gid, "player_id": p2["player_id"], "resume_token": p2["resume_token"]}).json()
    assert "error" in denied
    assert "error" in requests.post(f"{app_url}/start", json={"game_id": gid, "player_id": p1["player_id"]}).json()

    # P2 完成並 ready → 最後一棒自動交回 P1：P1 的 Joy-Con 取得 ownership，焦點在「啟動行動」，尚未啟動。
    finish_turn(app_url, gid, p2, FACTION_PICKS[1])
    wait_turn(page, joycons, p1["player_id"], 24801, picker=False)
    start_focused(page)
    assert requests.get(f"{app_url}/lobby/{gid}").json()["started"] is False
    assert not visible(page, "#factionPicker")
    assert page.evaluate("window.RedlineHotSeat.getState().controllerOwner.seat") == p1["player_id"]
    # P2 的 Joy-Con（右）按 A 不會啟動；房主 P1 的 Joy-Con 按 A 才啟動。
    joycons.press(24800, "A")
    page.wait_for_timeout(600)
    assert requests.get(f"{app_url}/lobby/{gid}").json()["started"] is False
    joycons.press(24801, "A")
    page.wait_for_function("window.RedlineSession.current().started", timeout=30000)
    assert requests.get(f"{app_url}/lobby/{gid}").json()["started"] is True
    page.context.close()


@pytest.mark.parametrize("ai,ports", [(True, [24801, 24800, 24802]), (False, [24801, 24800, 24802, 24803])])
def test_joycon_three_and_four_players_hand_off_in_order_then_return_to_host(browser, app_url, joycons, ai, ports):
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=ai, control="joycon")
    pair_in_order(page, joycons, ports)
    page.click("#sfContinueBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    gid, seats = local_seats(page)
    lobby = requests.get(f"{app_url}/lobby/{gid}").json()
    n = len(ports)
    assert [p[1] for p in lobby["players"]] == [f"P{i + 1}" for i in range(n)]
    assert [s["player_id"] for s in seats] == [p[0] for p in lobby["players"]]
    wait_turn(page, joycons, seats[0]["player_id"], ports[0])
    visited = [page.evaluate("window.RedlineSession.current().playerId")]
    picks = FACTION_PICKS[:n - 1] + ([FACTION_PICKS[2]] if ai else [FACTION_PICKS[3]])
    for i in range(n):
        # 前一棒完成前，lobby 仍只輪到第 i 棒：後面的席位沒有 faction／ready。
        current = requests.get(f"{app_url}/lobby/{gid}").json()
        assert all(seats[j]["player_id"] not in current["ready"] or not current["ready"][seats[j]["player_id"]] for j in range(i, n))
        finish_turn(app_url, gid, seats[i], picks[i])
        if i + 1 < n:
            wait_turn(page, joycons, seats[i + 1]["player_id"], ports[i + 1])
            visited.append(page.evaluate("window.RedlineSession.current().playerId"))
    wait_turn(page, joycons, seats[0]["player_id"], ports[0], picker=False)
    start_focused(page)
    assert visited == [s["player_id"] for s in seats]
    assert page.evaluate("window.RedlineSession.current().playerId") == seats[0]["player_id"]
    assert requests.get(f"{app_url}/lobby/{gid}").json()["started"] is False
    assert page.is_enabled("#startGameBtn")
    page.context.close()


def test_joycon_provisioning_survives_lobby_refresh_failures_and_creates_exactly_p1_p2(browser, app_url, joycons):
    """實機 P2 失敗的根因：席位已建立後的 /lobby 刷新失敗（或配置期間被 claim／改名插隊）會讓整個配置被誤判失敗。"""
    page = new_page(browser, app_url, joycons)
    create_via_flow(page, ai=True, control="joycon")
    pair_in_order(page, joycons, [24801, 24800])
    seen = []

    def flaky_lobby(route):
        seen.append(1)
        if len(seen) % 2 == 0:
            route.abort("connectionreset")
        else:
            route.continue_()

    page.route("**/lobby/*", flaky_lobby)
    page.click("#sfContinueBtn")
    page.wait_for_selector("#factionPicker", state="visible", timeout=40000)
    page.unroute("**/lobby/*", flaky_lobby)
    gid, seats = local_seats(page)
    lobby = requests.get(f"{app_url}/lobby/{gid}").json()
    assert [p[1] for p in lobby["players"]] == ["P1", "P2"]
    assert [s["player_id"] for s in seats] == [p[0] for p in lobby["players"]]
    assert page.is_hidden("#sfAutoSetup")
    page.context.close()


# ---------------------------------------------------------------- 起始畫面：單一 Joy-Con 不用 SL＋SR 直接導覽
@pytest.fixture
def single_joycon(app_url):
    """bridge 上只有一支左 Joy-Con（24801）有訊號；其他埠不送封包（不在 roster）。"""
    fake = FakeJoyCons(app_url, present={24801})
    yield fake
    fake.close()


def nav_state(page):
    return page.evaluate("window.RedlineController.getState()")


def wait_nav_claim(page, controller_id, timeout=15000):
    page.wait_for_function(
        "(() => { const s = window.RedlineController.getState(); return s.controller.owned === '%s' && s.status === 'connected'"
        " && s.startNav.claim === '%s'; })()" % (controller_id, controller_id), timeout=timeout)


def track_mutations(page):
    """記下所有非 GET 的 HTTP 請求（/create、/join、ready、start 等 server mutation）。"""
    sent = []
    page.on("request", lambda r: sent.append(f"{r.method} {r.url}") if r.method != "GET" else None)
    return sent


def nav_to(page, joycons, port, selector, limit=12):
    """以真實 bridge frame 的方向鍵把焦點移到 selector（依畫面位置選方向）；第一下只放焦點。回傳是否到達。"""
    for _ in range(limit):
        delta = page.evaluate("""(sel) => {
          const t = document.querySelector(sel), a = document.activeElement;
          if (!t) return null;
          if (a === t) return 'done';
          if (!a || a === document.body || !a.classList.contains('rl-pad-focus')) return 'none';
          const r = t.getBoundingClientRect(), q = a.getBoundingClientRect();
          const dy = (r.top + r.bottom - q.top - q.bottom) / 2;
          // 遊戲選單是依列導覽（上下走列、左右只在配樂音量的 −/+ 之間）：目標在別列就用垂直方向。
          const menu = document.getElementById('gameMenuModal');
          if (menu && menu.contains(t) && menu.contains(a) && Math.abs(dy) > 8) return [0, dy];
          return [(r.left + r.right - q.left - q.right) / 2, dy];
        }""", selector)
        if delta == "done":
            return True
        if delta is None:
            return False
        if delta == "none":
            joycons.nav(port, "down")  # 第一下只放焦點
            continue
        dx, dy = delta
        joycons.nav(port, ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up"))
    return page.evaluate("(sel) => document.activeElement === document.querySelector(sel)", selector)


@pytest.mark.parametrize("ai", [False, True], ids=["human", "ai"])
def test_single_joycon_drives_start_screen_without_sl_sr_and_creates_no_seat(browser, app_url, single_joycon, ai):
    fake = single_joycon
    cid = fake.controller_id(24801)
    page = new_page(browser, app_url, fake)
    sent = track_mutations(page)
    # 搖桿控制未啟用（預設）：起始畫面只為導覽開暫時連線，恰好一支 → 自動 claim，沒有按 SL＋SR。
    wait_nav_claim(page, cid)
    s = nav_state(page)
    assert s["enabled"] is False and s["startNav"]["on"] is True and s["startNav"]["live"] is True
    assert page.evaluate("localStorage.getItem('redline.controller.v1')").find('"enabled":false') >= 0, "不寫入啟用設定"
    assert page.evaluate("sessionStorage.getItem('redline.controller.claim.v1')") is None, "導覽手把不存成手把偏好"
    sf = page.evaluate("window.RedlineStartFlow.getState()")
    assert sf["step"] == "entry" and sf["paired"] == [] and sf["listeners"] == [] and sf["startNav"] is True
    # 第一個 frame 是 baseline；第一下方向只放焦點（不執行），之後方向鍵移動、A 觸發既有按鈕。
    target = "sfCreateAi" if ai else "sfCreateHuman"
    assert nav_to(page, fake, 24801, "#" + target), focus_id(page)
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
    fake.press(24801, "A")
    page.wait_for_function("window.RedlineStartFlow.getState().step === 'setup'", timeout=5000)
    assert page.evaluate("window.RedlineStartFlow.getState().draft.aiRedArmy") is ai
    assert page.inner_text("#sfSetupTitle") == ("建立 AI 紅軍遊戲" if ai else "建立真人紅軍遊戲")
    # 起始設定（難度）也由同一支操作；仍是導覽，不是 P1。
    assert nav_to(page, fake, 24801, '[data-sf-market="all_cards"]'), focus_id(page)
    fake.press(24801, "A")
    page.wait_for_function("window.RedlineStartFlow.getState().draft.marketMode === 'all_cards'", timeout=5000)
    # 沒有建立／綁定任何席位、沒有 server mutation、沒有 session。
    sf = page.evaluate("window.RedlineStartFlow.getState()")
    assert sf["paired"] == [] and sf["pending"] is None
    assert page.evaluate("window.RedlineSession.current().gameId") in (None, "")
    assert page.evaluate("window.RedlineHotSeat.getState().seats.length") == 0
    assert sent == [], sent
    assert nav_state(page)["controller"]["owned"] == cid
    page.context.close()


def test_single_joycon_nav_then_formal_pairing_still_needs_sl_sr(browser, app_url, single_joycon):
    fake = single_joycon
    cid = fake.controller_id(24801)
    page = new_page(browser, app_url, fake)
    sent = track_mutations(page)
    wait_nav_claim(page, cid)
    assert nav_to(page, fake, 24801, "#sfCreateHuman")
    fake.press(24801, "A")
    page.wait_for_function("window.RedlineStartFlow.getState().step === 'setup'", timeout=5000)
    assert nav_to(page, fake, 24801, '[data-sf-control="joycon"]'), focus_id(page)
    fake.press(24801, "A")
    # 進入正式配對：導覽權撤銷，主連線不擁有；手把交給配對 listener，仍要 SL＋SR 才成為 P1。
    page.wait_for_function("window.RedlineStartFlow.getState().listeners.some(l => l.owned === '%s')" % cid, timeout=15000)
    s = nav_state(page)
    assert s["startNav"]["on"] is False and s["startNav"]["claim"] is None and s["controller"]["owned"] is None
    page.wait_for_timeout(800)
    assert page.evaluate("window.RedlineStartFlow.getState().paired") == [], "沒有按 SL＋SR 不會自動成為 P1"
    fake.press_chord(24801)
    page.wait_for_function("window.RedlineStartFlow.getState().paired.length === 1", timeout=8000)
    assert page.evaluate("window.RedlineStartFlow.getState().paired") == [cid]
    page.wait_for_function("window.RedlineController.getState().controller.owned === '%s'" % cid, timeout=15000)
    assert sent == [], sent
    page.context.close()


def test_start_nav_fail_closed_for_zero_multiple_and_other_tab(browser, app_url):
    # 0 支：bridge 沒有任何手把。
    empty = FakeJoyCons(app_url, present=set())
    two = FakeJoyCons(app_url, present={24800, 24801})
    one = FakeJoyCons(app_url, present={24801})
    try:
        page = new_page(browser, app_url, empty)
        page.wait_for_function("(() => { const s = window.RedlineController.getState(); return s.controller.mode === 'v2' && Array.isArray(s.controller.roster); })()", timeout=15000)
        page.wait_for_timeout(800)
        s = nav_state(page)
        assert s["controller"]["owned"] is None and s["startNav"]["claim"] is None
        assert page.is_hidden("#padHint"), "沒拿到手把時不顯示暫時連線狀態"
        page.context.close()
        # 多支：兩支都有訊號 → 不猜，誰都不拿；按鍵完全不作用。
        page = new_page(browser, app_url, two)
        page.wait_for_function("(window.RedlineController.getState().controller.roster || []).filter(c => c.status === 'active').length === 2", timeout=15000)
        page.wait_for_timeout(800)
        assert nav_state(page)["controller"]["owned"] is None
        two.nav(24801, "right")
        two.press(24801, "A")
        assert nav_state(page)["padActive"] is False
        assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
        page.context.close()
        # other-tab：第一個分頁已拿到唯一一支；第二個分頁看到 owner=other，不搶。
        first = new_page(browser, app_url, one)
        wait_nav_claim(first, one.controller_id(24801))
        second = new_page(browser, app_url, one)
        second.wait_for_function("(window.RedlineController.getState().controller.roster || []).some(c => c.owner === 'other')", timeout=15000)
        second.wait_for_timeout(1000)
        assert nav_state(second)["controller"]["owned"] is None
        assert nav_state(first)["controller"]["owned"] == one.controller_id(24801)
        second.context.close()
        first.context.close()
    finally:
        for fake in (empty, two, one):
            fake.close()


def test_start_nav_revoked_when_second_controller_appears_or_pad_goes_stale(browser, app_url, single_joycon):
    fake = single_joycon
    cid = fake.controller_id(24801)
    page = new_page(browser, app_url, fake)
    wait_nav_claim(page, cid)
    assert nav_to(page, fake, 24801, "#sfCreateAi")
    # 第二支連上：恰好一支 → 多支，撤銷導覽（不留幽靈 controller），舊手把的 A 不作用。
    fake.present.add(24800)
    page.wait_for_function("window.RedlineController.getState().controller.owned === null", timeout=8000)
    s = nav_state(page)
    assert s["startNav"]["claim"] is None and s["status"] == "unbound" and s["padActive"] is False
    fake.press(24801, "A")
    fake.press(24800, "A")
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
    # 第二支訊號消失（stale）：又只剩一支有訊號 → 重新取得導覽（第一下仍只放焦點）。
    fake.present.discard(24800)
    wait_nav_claim(page, cid)
    # 唯一那支訊號消失：撤銷。
    fake.present.discard(24801)
    page.wait_for_function("window.RedlineController.getState().controller.owned === null", timeout=8000)
    assert nav_state(page)["startNav"]["claim"] is None
    fake.present.add(24801)
    wait_nav_claim(page, cid)
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
    page.context.close()


# 記下這個文件每一條 WebSocket 收到的第一筆 bridge frame（buttons）：證明新連線建立時 bridge 已經是「按住」。
FIRST_FRAME_PROBE = """
(() => {
  const Base = window.WebSocket;
  window.__padSockets = [];
  window.WebSocket = class FirstFrameProbe extends Base {
    constructor(...args) {
      super(...args);
      const rec = { first: null };
      window.__padSockets.push(rec);
      this.addEventListener('message', (e) => {
        if (rec.first || typeof e.data !== 'string') return;
        try { const m = JSON.parse(e.data); if (m && m.type === 'frame') rec.first = m.buttons; } catch {}
      });
    }
  };
})();
"""


def first_frames(page, since=0):
    return page.evaluate("(n) => window.__padSockets.slice(n).filter(s => s.first).map(s => s.first)", since)


def wait_pad_held(page, button, held, timeout=8000):
    """等這個分頁的 reducer 真的處理到該 frame（getState().held）；取代固定等待。"""
    page.wait_for_function("([b, v]) => window.RedlineController.getState().held[b] === v", arg=[button, held], timeout=timeout)


def test_start_nav_held_a_on_reload_and_bridge_reconnect_is_baseline_only(browser, app_url, single_joycon):
    """產品不變式：連線建立前就按住的 A，在新連線上只是 baseline（不放焦點、不觸發）；放開也不算操作。

    前提必須先成立：fake.hold 等到 bridge 已收到按住 A 才重新整理／重連。直接寫 fake.held 再 reload 時，
    feed 執行緒（每 30ms）和新連線沒有先後保證；若新連線的第一筆仍是放開，之後的按住就是一次真的按下，
    頁面把它當第一下放焦點（padActive=true）是正確行為，那是 fixture 競態，不是 baseline 失效。
    """
    fake = single_joycon
    cid = fake.controller_id(24801)
    page = new_page(browser, app_url, fake, init_script=FIRST_FRAME_PROBE)
    wait_nav_claim(page, cid)
    assert nav_to(page, fake, 24801, "#sfCreateHuman")
    # 按住 A 重新整理（舊文件看到的是一次真的按下，可能點了「建立真人」；重新整理後的新頁面不受影響）。
    fake.hold(24801, "A")
    page.reload()
    page.wait_for_selector("#startFlow:not([hidden])")
    wait_nav_claim(page, cid)
    wait_pad_held(page, "A", True)
    frames = first_frames(page)
    assert frames and all(f[0] & 0x08 for f in frames), f"新連線第一筆 frame 必須已按住 A：{frames}"
    s = nav_state(page)
    assert s["padActive"] is False, f"按住 A 重新整理：新連線第一筆只當 baseline：{s}"
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
    fake.release(24801, "A")
    wait_pad_held(page, "A", False)
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
    assert nav_state(page)["padActive"] is False, "放開 A 也不算一次操作"
    # bridge 重連時仍按著 A。目前連線把這次按下當第一下（只放焦點），再把焦點移到「建立真人」：
    # 重連後若把按住的 A 當成新的按下，就會點下去進入 setup。
    fake.hold(24801, "A")
    page.wait_for_function("window.RedlineController.getState().padActive === true", timeout=5000)
    assert nav_to(page, fake, 24801, "#sfCreateHuman"), focus_id(page)
    sockets = page.evaluate("window.__padSockets.length")
    page.evaluate("window.RedlineController.setEnabled(false)")  # 未啟用：起始畫面導覽改用新的暫時連線
    wait_nav_claim(page, cid)
    wait_pad_held(page, "A", True)
    frames = first_frames(page, sockets)
    assert frames and all(f[0] & 0x08 for f in frames), f"重連後第一筆 frame 必須已按住 A：{frames}"
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
    assert nav_state(page)["focusSig"] == "#sfCreateHuman"
    fake.release(24801, "A")
    wait_pad_held(page, "A", False)
    assert page.evaluate("window.RedlineStartFlow.getState().step") == "entry"
    # 對照：放開後再按一次 A，同一個焦點立即作用（證明上面的「沒有作用」不是焦點或連線失效）。
    fake.press(24801, "A")
    page.wait_for_function("window.RedlineStartFlow.getState().step === 'setup'", timeout=5000)
    page.context.close()


def test_start_nav_leaves_desktop_mode_only(browser, app_url, single_joycon):
    page = new_page(browser, app_url, single_joycon, display="living-room")
    wait_nav_claim(page, single_joycon.controller_id(24801))
    assert nav_state(page)["livingRoom"] is None
    assert page.evaluate("[window.RedlineDisplayMode.get(), document.documentElement.dataset.display ?? null]") == ["desktop", None]
    page.context.close()


def test_browser_tests_never_reach_resident_bridge_on_8000(browser, app_url):
    """預設 bridge 位址（常駐服務的 8000）在測試中一律被 conftest 換成沉默的 mock：沒有 roster、沒有 claim。"""
    page = new_page(browser, app_url)
    page.wait_for_timeout(1500)
    s = nav_state(page)
    assert s["url"] == "ws://127.0.0.1:8000/ws" and s["startNav"]["on"] is True
    # 沉默的 mock 沒有 v2 roster：沒有任何 bridge 手把；未啟用時舊版（無身份）frame 也一律不收。
    assert s["controller"]["roster"] is None and s["controller"]["mode"] != "v2" and s["startNav"]["claim"] is None
    page.evaluate("window.RedlineController.feed({x: 1, y: 0, buttons: [0, 8]})")
    assert nav_state(page)["padActive"] is False
    assert page.is_hidden("#padHint")
    page.context.close()


def test_start_nav_exit_releases_claim_still_in_flight_when_controller_is_enabled(browser, app_url, single_joycon):
    """離開起始頁時，晚到的導覽 claim 不得變成一般 ownership、保存偏好或留下幽靈控制權。"""
    fake = single_joycon
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script(
        f"""
        localStorage.setItem('redline.controller.v1', JSON.stringify({{enabled: true, url: '{fake.url}'}}));
        const NativeWebSocket = window.WebSocket;
        window.WebSocket = class DelayedClaimWebSocket extends NativeWebSocket {{
          send(data) {{
            let message = null;
            try {{ message = JSON.parse(data); }} catch {{}}
            if (message && message.type === 'claim' && !window.__delayedStartNavClaim) {{
              window.__delayedStartNavClaim = true;
              setTimeout(() => super.send(data), 600);
              return;
            }}
            if (message && message.type === 'release' && window.__delayedStartNavClaim) {{
              setTimeout(() => super.send(data), 650);
              return;
            }}
            return super.send(data);
          }}
        }};
        """
    )
    page = ctx.new_page()
    page.goto(app_url + "/")
    page.wait_for_selector("#startFlow:not([hidden])")
    page.wait_for_function("window.__delayedStartNavClaim === true", timeout=15000)

    page.evaluate("window.RedlineStartFlow.hide()")
    page.wait_for_timeout(1800)

    state = nav_state(page)
    assert state["startNav"]["on"] is False
    assert state["startNav"]["claim"] is None
    assert state["controller"]["owned"] is None
    assert page.evaluate("sessionStorage.getItem('redline.controller.claim.v1')") is None
    ctx.close()
