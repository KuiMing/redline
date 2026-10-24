"""開始遊戲前流程的 Browser（Playwright／Chromium）驗證。

伺服器是真的 uvicorn（server.main:app）。Joy-Con 部分 **沒有實體硬體**：使用真的 tools.joycon_bridge 的
ControllerRegistry＋WebSocket bridge app，由測試執行緒以 fixture 的 FTCW S2B1／S2N1 封包模擬四支手把
（物理 SL／SR 位元取自 fixtures/joycon_dual_layout.json）。因此這裡驗證的是 bridge v2 協定、瀏覽器配對邏輯與
伺服器狀態，不是真實 Joy-Con 的藍牙／FTCW 行為（見 TODO.md 的實機驗證項目）。

設定環境變數 START_FLOW_PROOF_DIR 時，會把正式 Browser UI 截圖寫到該目錄（docs/records/start-flow/）。
"""
from __future__ import annotations

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

    def __init__(self, page_origin: str):
        self.registry = B.ControllerRegistry(PORTS, primary_port=24800)
        self.port = free_port()
        self.chord: set[int] = set()
        self.present = set(PORTS)
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
                self.registry.observe(port, s2b1(offset, value) if port in self.chord else s2b1())
            time.sleep(0.03)

    def controller_id(self, port: int) -> str:
        return B.controller_id(B.detect_side(NAMES[port]), port, NAMES[port])

    def press_chord(self, port: int, hold: float = 0.35):
        self.chord.add(port)
        time.sleep(hold)
        self.chord.discard(port)
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


def new_page(browser, app_url, joycons=None, display=None):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    if joycons is not None:
        ctx.add_init_script(
            "if (!localStorage.getItem('redline.controller.v1')) localStorage.setItem('redline.controller.v1', "
            f"JSON.stringify({{enabled: false, url: '{joycons.url}'}}));"
        )
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


def finish_and_create(page, name="Tester", proof=None):
    page.click("#sfContinueBtn")
    page.wait_for_selector("#startFlow", state="hidden")
    page.fill("#playerName", name)
    if proof:
        shot(page, proof)
    page.click("#createRoomBtn")
    page.wait_for_function("window.RedlineSession.current().gameId")


def test_entry_offers_three_paths_and_no_player_count(browser, app_url):
    page = new_page(browser, app_url)
    assert page.inner_text("#sfCreateHuman").startswith("建立真人紅軍遊戲")
    assert page.inner_text("#sfCreateAi").startswith("建立 AI 紅軍遊戲")
    assert page.is_visible("#sfRoomCode") and page.is_visible("#sfJoinBtn")
    text = page.inner_text("#startFlow")
    assert "人數" not in text and "幾人" not in text
    assert page.locator("#startFlow select").count() == 0
    # 入口只有三條路：隱藏的作戰準備室不在畫面（Joy-Con 焦點集合因此不含它）。
    assert not page.locator("#lobby .lobby-card").is_visible()
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
    for sel in ("[data-market-mode]", "[data-ai-red-army]"):
        for i in range(guest.locator(sel).count()):
            assert guest.locator(sel).nth(i).is_disabled()
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
    page.click('[data-sf-market="all_cards"]')
    assert pressed("market") == [["sample_53", "false"], ["all_cards", "true"]]
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
    page.click("#sfContinueBtn")
    page.wait_for_selector("#startFlow", state="hidden")

    page.route("**/join", lambda route: route.fulfill(json={"error": "Room full"}))
    page.click("#createRoomBtn")
    page.wait_for_function("window.RedlineSession.current().gameId")
    game_id = page.evaluate("window.RedlineSession.current().gameId")
    page.wait_for_function("document.getElementById('lobbyStatusHint').textContent.includes('重試')", timeout=10000)
    assert page.is_hidden("#factionPicker"), "席位未配置成功不可進入陣營畫面"
    state = page.evaluate("window.RedlineStartFlow.getState()")
    assert state["pending"] and state["pending"]["controllers"] == paired and state["paired"] == paired
    assert len(requests.get(f"{app_url}/lobby/{game_id}").json()["players"]) == 1

    # 網路恢復後在同一個房間重試：只補缺的席位，不再建立新房間，也不重複建立席位。
    page.unroute("**/join")
    page.click("#createRoomBtn")
    page.wait_for_selector("#factionPicker", state="visible")
    assert page.evaluate("window.RedlineSession.current().gameId") == game_id
    players = requests.get(f"{app_url}/lobby/{game_id}").json()["players"]
    assert len(players) == 2
    page.wait_for_function("window.RedlineHotSeat.getState().seats.length === 2 && window.RedlineHotSeat.getState().seats.every(s => s.controller)", timeout=20000)
    assert [s["controller"] for s in page.evaluate("window.RedlineHotSeat.getState().seats")] == paired
    assert page.evaluate("window.RedlineStartFlow.getState().pending") is None
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

    page.click("#sfContinueBtn")
    page.wait_for_selector("#startFlow", state="hidden")
    page.click("#createRoomBtn")  # Joy-Con 玩家不必輸入行動代號：沿用預設，本機席位自動成為 P1～P4
    page.wait_for_selector("#factionPicker", state="visible")
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


def test_living_room_display_keeps_fixed_stage(browser, app_url):
    page = new_page(browser, app_url, display="living-room")
    assert page.evaluate("document.documentElement.dataset.display") == "living-room"
    box = page.evaluate("(() => { const s = document.getElementById('designStage'); return [s.offsetWidth, s.offsetHeight]; })()")
    assert box == [1280, 720]
    zoom = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--stage-scale')")
    assert abs(float(zoom) - 0.9) < 1e-6
    shot(page, "07_living_room_entry.png")
    page.click("#sfCreateHuman")
    shot(page, "08_living_room_setup.png")
    page.context.close()


def test_joycon_room_enables_controller_for_guest_but_computer_room_does_not(browser, app_url, joycons):
    host = new_page(browser, app_url, joycons)
    create_via_flow(host, control="joycon")
    host.wait_for_function("window.RedlineStartFlow.getState().listeners.some(l => l.owned)", timeout=20000)
    joycons.press_chord(24800)
    host.wait_for_function("window.RedlineStartFlow.getState().paired.length === 1", timeout=8000)
    finish_and_create(host)
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
