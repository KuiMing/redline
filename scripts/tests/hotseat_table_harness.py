"""客廳輪流（hot-seat）Browser regression 共用的牌桌：真的 server.main（同一 process 的 uvicorn，可直接讀寫權威 Game）、
真的 tools.joycon_bridge（FakeJoyCons 送 fixture S2B1 封包——**不是實體 Joy-Con**）、一個保存所有本機席位的瀏覽器分頁。

席位順序＝建立順序（P1 房主、P2、P3…），與開始流程配對／hotseat 席位表的既有順序相同。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

uvicorn = pytest.importorskip("uvicorn")
from websockets.sync.client import connect as ws_connect  # noqa: E402

from server import main as server_main  # noqa: E402
from server.cards import Card  # noqa: E402
from server.game import GamePhase, TurnPhase  # noqa: E402
from test_start_flow_browser import free_port  # noqa: E402

# fixture 實體位元（scripts/tests/fixtures/joycon_dual_layout.json）：左 Joy-Con 的 Right＝A、Down＝B、搖桿按下＝STICK；
# 右 Joy-Con 的 A／B。方向一律用左搖桿（FakeJoyCons.stick 寫入左搖桿 offset）。
BITS = {"L": {"A": (10, 0x04), "B": (10, 0x01), "STICK": (9, 0x08)}, "R": {"A": (8, 0x08), "B": (8, 0x04)}}
SIDE = {24800: "R", 24801: "L", 24802: "R", 24803: "L"}


def evidence_dir(request):
    raw = request.config.getoption("--redline-evidence-dir") or os.environ.get("REDLINE_EVIDENCE_DIR")
    return Path(raw) if raw else None


def shot(request, page, name):
    target = evidence_dir(request)
    if target:
        target.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target / f"{name}.png"))


def wait_until(fn, timeout=10.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(interval)
    return fn()


def stays(fn, seconds=1.5, interval=0.1):
    """fn() 在整段期間都成立（不是只在某一瞬間）。"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not fn():
            return False
        time.sleep(interval)
    return bool(fn())


def hold(fake, port, button):
    fake.held[port] = [BITS[SIDE[port]][button]]
    time.sleep(0.15)


def release(fake, port):
    fake.held.pop(port, None)
    time.sleep(0.15)


def press(fake, port, button, after=0.35):
    hold(fake, port, button)
    time.sleep(0.1)
    release(fake, port)
    time.sleep(after)


def nav(fake, port, direction, after=0.3):
    assert SIDE[port] == "L", "方向導覽只用左 Joy-Con（左搖桿）"
    fake.nav(port, direction)
    time.sleep(after)


@pytest.fixture(scope="module")
def server_url():
    """同一 process 的真 uvicorn；取消反應的 10 秒逾時拉長，交接／重新載入期間不會被自動跳過（結果一定來自玩家輸入）。"""
    saved = server_main.REACTION_RESPONSE_TIMEOUT_SECONDS
    server_main.REACTION_RESPONSE_TIMEOUT_SECONDS = 180
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(server_main.app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    server_main.REACTION_RESPONSE_TIMEOUT_SECONDS = saved


class Seat:
    """真人席位自己的遊戲 WebSocket（以該席 resume token 授權）：用來讓「不在畫面上的玩家」行動。"""

    def __init__(self, base, game_id, player_id, token, name):
        self.player_id, self.name, self.state = player_id, name, {}
        self.ws = ws_connect(base.replace("http", "ws", 1) + f"/ws/{game_id}/{player_id}", subprotocols=[token],
                             open_timeout=10, ping_interval=None)
        self.drain(1.0)

    def drain(self, timeout=0.05):
        while True:
            try:
                data = json.loads(self.ws.recv(timeout=timeout))
            except Exception:
                return
            if isinstance(data, dict) and "players" in data:
                self.state = data
            timeout = 0.02

    def send(self, payload):
        self.ws.send(json.dumps(payload, ensure_ascii=False))
        self.drain(0.6)
        return self.state


class HotSeatTable:
    """N 位本機真人席位（各綁一支 fixture Joy-Con），一個客廳輪流瀏覽器分頁。factions 依席位順序（P1 起）。"""

    def __init__(self, base, browser, fake, factions, ports, device="hs", ai_red_army=False):
        self.base, self.fake, self.browser = base, fake, browser
        post = lambda path, body: requests.post(base + path, json=body, timeout=20).json()
        created = post("/create", {"name": "P1", "device_id": f"{device}-p1"})
        gid = created["game_id"]
        seats = [{"player_id": created["host_id"], "token": created["resume_token"], "name": "P1"}]
        for n in range(2, len(factions) + 1):
            joined = post("/join", {"game_id": gid, "name": f"P{n}", "device_id": f"{device}-p{n}"})
            seats.append({"player_id": joined["player_id"], "token": joined["resume_token"], "name": f"P{n}"})
        if ai_red_army:
            assert post("/ai-red-army", {"game_id": gid, "player_id": seats[0]["player_id"], "resume_token": seats[0]["token"], "enabled": True}).get("success")
        for seat, faction, port in zip(seats, factions, ports):
            seat["port"], seat["controller"], seat["faction"] = port, fake.controller_id(port), faction
            assert post("/choose-faction", {"game_id": gid, "player_id": seat["player_id"], "resume_token": seat["token"], "faction_id": faction}).get("success")
            assert post("/ready", {"game_id": gid, "player_id": seat["player_id"], "resume_token": seat["token"], "ready": True}).get("success")
        assert post("/start", {"game_id": gid, "player_id": seats[0]["player_id"], "resume_token": seats[0]["token"]}).get("success")
        self.gid, self.seats = gid, seats
        self.by_name = {s["name"]: s for s in seats}
        self.game = server_main.manager.get_game(gid)
        self._finish_base_selection()
        self.socks = {s["name"]: Seat(base, gid, s["player_id"], s["token"], s["name"]) for s in seats}
        self.ctx = None
        self.page = None
        self.errors = []

    # ------------------------------------------------------------ server-side setup（瀏覽器開啟前，直接寫權威 Game）
    def _finish_base_selection(self):
        game = self.game
        for _ in range(10):
            pending = dict(getattr(game, "pending_base_choices", None) or {})
            if not pending:
                break
            for pid, choice in pending.items():
                label = choice["labels"][0]
                town = ((choice.get("resolved") or {}).get(label) or [label])[0]
                game.set_base_choice(pid, town, label)
        assert str(game.game_phase).endswith("main") or game.game_phase == GamePhase.MAIN, game.game_phase

    def player(self, name):
        return next(p for p in self.game.players if p.id == self.by_name[name]["player_id"])

    def card(self, name):
        card_def = next((c for c in self.game.structured_cards if c.get("name") == name), None)
        assert card_def, name
        return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))

    def pin_noop_event(self):
        game = self.game
        game.current_event = dict(game._event_by_name("歲月靜好") or {})
        game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
        game.event_notification = game._event_display_payload()
        game.event_modifiers = []

    def set_turn(self, name):
        game = self.game
        game.pending_choice = None
        game.current_player_index = next(i for i, p in enumerate(game.players) if p.id == self.by_name[name]["player_id"])
        game.turn_phase = TurnPhase.ACTION
        game.turn_log = {}

    # ------------------------------------------------------------ browser
    def open(self, active):
        """分頁以 active 席位恢復（尚未解鎖＝交接遮罩，要該席自己的 Joy-Con 按 A）。"""
        store = {"v": 1, "enabled": True, "games": {self.gid: {"seats": [
            {"player_id": s["player_id"], "resume_token": s["token"], "name": s["name"], "controller": s["controller"], "auto_name": True}
            for s in self.seats]}}}
        session = {"gameId": self.gid, "active": self.by_name[active]["player_id"], "unlocked": False}
        self.ctx = self.browser.new_context(viewport={"width": 1280, "height": 720})
        # 只在分頁第一次載入時寫入（之後的整頁重新載入／重新開始要保留頁面自己寫的內容）。
        self.ctx.add_init_script(
            "if (!sessionStorage.getItem('__hsInit')) {"
            "sessionStorage.setItem('__hsInit', '1');"
            f"localStorage.setItem('redline.controller.v1', JSON.stringify({{enabled: true, url: '{self.fake.url}'}}));"
            f"localStorage.setItem('redline.hotseat.v1', {json.dumps(json.dumps(store))});"
            f"sessionStorage.setItem('redline.hotseat.session.v1', {json.dumps(json.dumps(session))});"
            "}")
        self.page = self.ctx.new_page()
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: self.errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        self.page.goto(self.base + "/")
        self.page.wait_for_function("() => window.lastGameState && window.RedlineHotSeat", timeout=20000)
        return self.page

    def hs(self):
        return self.page.evaluate("() => window.RedlineHotSeat.getState()")

    def ctl(self):
        return self.page.evaluate("() => window.RedlineController.getState()")

    def owned(self):
        return (self.ctl().get("controller") or {}).get("owned")

    def wait_handoff(self, name, timeout=15.0):
        pid = self.by_name[name]["player_id"]
        assert wait_until(lambda: (lambda st: st["view"] == "handoff" and st["handoffSeat"] == pid)(self.hs()), timeout), self.hs()
        assert wait_until(lambda: self.owned() == self.by_name[name]["controller"], timeout), self.ctl()

    def hand_to(self, name):
        """交接遮罩：由該席自己的 Joy-Con 按 A 確認 → 整頁以該席 token 重新載入 → open。"""
        self.wait_handoff(name)
        press(self.fake, self.by_name[name]["port"], "A")
        pid = self.by_name[name]["player_id"]
        assert wait_until(lambda: self._safe_hs_open(pid), 20.0), "handoff did not open"
        assert wait_until(lambda: self.owned() == self.by_name[name]["controller"], 15.0), self.ctl()

    def _safe_hs_open(self, pid):
        try:
            self.page.wait_for_function("() => window.lastGameState && window.RedlineHotSeat", timeout=2000)
            st = self.hs()
        except Exception:
            return False
        return st["view"] == "open" and st["displayedSeat"] == pid

    def shown(self, element_id):
        return self.page.evaluate(
            "(id) => { const el = document.getElementById(id); return !!el && getComputedStyle(el).display !== 'none'"
            " && getComputedStyle(el).visibility !== 'hidden' && el.getClientRects().length > 0; }", element_id)

    def close(self):
        for sock in self.socks.values():
            try:
                sock.ws.close()
            except Exception:
                pass
        if self.ctx:
            self.ctx.close()
