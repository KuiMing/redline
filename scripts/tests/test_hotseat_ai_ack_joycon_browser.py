"""客廳輪流「AI 紅軍回合結束」摘要的 Joy-Con A 確認（Browser／Playwright＋真的 bridge app）。

Playtest bug：摘要寫「按『知道了』或 A 後才會輪到下一位」，但下一位玩家按自己的 Joy-Con A 沒反應，只能等約 10 秒逾時。
根因：等待中（waiting 遮罩）主連線不 claim 任何席位，只留著上一個畫面席位那一支；bridge v2 一條連線只收得到自己擁有那一支的
frame，所以下一位接手席位的 A 根本到不了頁面。

伺服器是同一個 process 內的真 uvicorn（可直接讀權威 Game 狀態；AI 節奏縮短、逾時拉長到 60 秒，A 生效不可能是逾時）。
Joy-Con **不是實體硬體**：真的 tools.joycon_bridge ControllerRegistry＋bridge app，由 FakeJoyCons 送 fixture S2B1 封包，
驗證的是 bridge v2 協定與瀏覽器路徑，不是實機藍牙行為。
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

playwright_sync = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")
from websockets.sync.client import connect as ws_connect  # noqa: E402

from server import main as server_main  # noqa: E402
import server.red_army_ai_runtime as ai_runtime  # noqa: E402
from test_start_flow_browser import FakeJoyCons, free_port  # noqa: E402

PORTS = (24801, 24800, 24803)  # P1 左、P2 右、P3 左
A_BITS = {24800: (8, 0x08), 24801: (10, 0x04), 24802: (8, 0x08), 24803: (10, 0x04)}  # fixture：右 A／左 Right＝A
HUMAN_FACTIONS = ("hong_kong", "taiwan_green", "tibet_family")


def choice_index(choice):
    """待決選擇的第一個合法答案：多張選擇（例如事件棄牌）要剛好 count 張。"""
    if choice.get("type") == "multi_card_choice":
        return list(range(int(choice.get("count") or 1)))
    return 0


class Seat:
    """真人席位的 WebSocket：只用來推進該席位的回合（畫面由瀏覽器分頁顯示）。"""

    def __init__(self, base, game_id, player_id, token, name):
        self.player_id, self.name, self.state = player_id, name, {}
        self.ws = ws_connect(base.replace("http", "ws", 1) + f"/ws/{game_id}/{player_id}", subprotocols=[token], open_timeout=10,
                             ping_interval=None)
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
        self.drain(0.5)

    def step(self):
        """base_selection／自己的 pending_choice／自己的回合 → 送一個合法動作。"""
        self.drain()
        s = self.state
        if s.get("game_phase") == "base_selection":
            choice = (s.get("pending_base_choices") or {}).get(self.player_id)
            if choice:
                label = choice["labels"][0]
                town = ((choice.get("resolved") or {}).get(label) or [label])[0]
                self.send({"action": "set_base", "town": town, "label": label})
        elif (s.get("pending_choice") or {}).get("player_id") == self.player_id:
            self.send({"action": "resolve_choice", "choice_id": s["pending_choice"].get("choice_id"), "index": choice_index(s["pending_choice"])})
        elif s.get("current_player") == self.name and not s.get("pending_choice"):
            self.send({"action": "advance"})


@pytest.fixture(scope="module")
def server_url():
    saved = (ai_runtime.AI_ACTION_DELAY_SECONDS, ai_runtime.AI_ACK_TIMEOUT_SECONDS)
    ai_runtime.AI_ACTION_DELAY_SECONDS = 0.4
    ai_runtime.AI_ACK_TIMEOUT_SECONDS = 60.0
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(server_main.app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    ai_runtime.AI_ACTION_DELAY_SECONDS, ai_runtime.AI_ACK_TIMEOUT_SECONDS = saved


@pytest.fixture(scope="module")
def joycons(server_url):
    fake = FakeJoyCons(server_url)
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


def hold_a(fake, port):
    fake.held[port] = [A_BITS[port]]
    time.sleep(0.15)


def release_a(fake, port):
    fake.held.pop(port, None)
    time.sleep(0.15)


def press_a(fake, port):
    hold_a(fake, port)
    time.sleep(0.15)
    release_a(fake, port)


def wait_until(fn, timeout=10.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(interval)
    return fn()


class Table:
    """三位本機真人席位（各綁一支 Joy-Con）＋AI 紅軍；一個客廳輪流瀏覽器分頁。"""

    def __init__(self, base, browser, fake):
        self.base, self.fake = base, fake
        post = lambda path, body: requests.post(base + path, json=body, timeout=20).json()
        created = post("/create", {"name": "P1", "device_id": "ai-ack-p1"})
        gid = created["game_id"]
        humans = [{"player_id": created["host_id"], "token": created["resume_token"], "name": "P1"}]
        for n in (2, 3):
            joined = post("/join", {"game_id": gid, "name": f"P{n}", "device_id": f"ai-ack-p{n}"})
            humans.append({"player_id": joined["player_id"], "token": joined["resume_token"], "name": f"P{n}"})
        assert post("/ai-red-army", {"game_id": gid, "player_id": humans[0]["player_id"], "resume_token": humans[0]["token"], "enabled": True}).get("success")
        for seat, faction, port in zip(humans, HUMAN_FACTIONS, PORTS):
            seat["port"], seat["controller"] = port, fake.controller_id(port)
            assert post("/choose-faction", {"game_id": gid, "player_id": seat["player_id"], "resume_token": seat["token"], "faction_id": faction}).get("success")
            assert post("/ready", {"game_id": gid, "player_id": seat["player_id"], "resume_token": seat["token"], "ready": True}).get("success")
        assert post("/start", {"game_id": gid, "player_id": humans[0]["player_id"], "resume_token": humans[0]["token"]}).get("success")
        self.gid, self.humans = gid, {s["player_id"]: s for s in humans}
        self.game = server_main.manager.get_game(gid)
        self.red_id = self.game.ai_red_army_player_id
        self.socks = {s["player_id"]: Seat(base, gid, s["player_id"], s["token"], s["name"]) for s in humans}
        store = {"v": 1, "enabled": True, "games": {gid: {"seats": [
            {"player_id": s["player_id"], "resume_token": s["token"], "name": s["name"], "controller": s["controller"], "auto_name": False}
            for s in humans]}}}
        session = {"gameId": gid, "active": humans[0]["player_id"], "unlocked": False}
        self.ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        self.ctx.add_init_script(
            f"localStorage.setItem('redline.controller.v1', JSON.stringify({{enabled: true, url: '{fake.url}'}}));"
            f"localStorage.setItem('redline.hotseat.v1', {json.dumps(json.dumps(store))});"
            f"if (!sessionStorage.getItem('redline.hotseat.session.v1')) sessionStorage.setItem('redline.hotseat.session.v1', {json.dumps(json.dumps(session))});")
        self.page = self.ctx.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.goto(base + "/")
        self.page.wait_for_function("() => window.lastGameState && window.RedlineHotSeat", timeout=20000)

    def hs(self):
        return self.page.evaluate("() => window.RedlineHotSeat.getState()")

    def awaiting(self):
        ack = self.game.ai_red_army_ack
        return bool(ack and not ack.get("released"))

    def authority_actor(self):
        pending = getattr(self.game, "pending_choice", None) or {}
        return pending.get("player_id") or self.game.current_player().id

    def released_to_next(self):
        """伺服器已放行且權威行動者不再是紅軍。整輪結算若先產生真人的必要 pending_choice，Game.current_player()
        會暫留紅軍，但權威行動者已是該 choice 的擁有者（與 validate_hotseat_ai_red_army_public_browser 相同判定）。"""
        return not self.awaiting() and self.authority_actor() != self.red_id

    def page_step(self, seat):
        """畫面上的席位以分頁自己的遊戲 WebSocket（app.js sendAction）行動，與真人玩家同一條連線。"""
        seat.drain()
        s = seat.state
        if s.get("game_phase") == "base_selection":
            choice = (s.get("pending_base_choices") or {}).get(seat.player_id)
            if choice:
                label = choice["labels"][0]
                town = ((choice.get("resolved") or {}).get(label) or [label])[0]
                self.page.evaluate("([town, label]) => sendAction('set_base', { town, label })", [town, label])
        elif (s.get("pending_choice") or {}).get("player_id") == seat.player_id:
            self.page.evaluate("([id, index]) => sendAction('resolve_choice', { choice_id: id, index })",
                               [s["pending_choice"].get("choice_id"), choice_index(s["pending_choice"])])
        elif s.get("current_player") == seat.name and not s.get("pending_choice"):
            self.page.evaluate("() => sendAction('advance')")
        seat.drain(0.5)

    def play_until(self, stop, limit=90.0, via_page=False):
        """以 Joy-Con A 確認每次交接、以各席位 WebSocket 推進回合，直到 stop(hs) 成立。
        via_page：畫面上的席位改由分頁自己的連線行動（結束回合與之後的確認走同一條連線）。"""
        deadline = time.time() + limit
        while time.time() < deadline:
            st = self.hs()
            if stop(st):
                return st
            if st["view"] == "handoff" and st["handoffSeat"] in self.humans and not st["aiPublic"]["open"]:
                press_a(self.fake, self.humans[st["handoffSeat"]]["port"])
                time.sleep(0.6)
                continue
            for sock in self.socks.values():
                sock.drain()  # 每一席的 state 都保持最新（閒置席位的連線也持續讀取）
            if st["view"] == "open" and st["displayedSeat"] in self.socks:
                seat = self.socks[st["displayedSeat"]]
                if via_page:
                    self.page_step(seat)
                else:
                    seat.step()
            time.sleep(0.2)
        raise AssertionError(f"沒有到達預期狀態：{self.hs()}")

    def next_human_after_red(self):
        ids = [p.id for p in self.game.players]
        at = ids.index(self.red_id)
        return next(ids[(at + i) % len(ids)] for i in range(1, len(ids)) if ids[(at + i) % len(ids)] in self.humans)

    def close(self):
        for sock in self.socks.values():
            try:
                sock.ws.close()
            except Exception:
                pass
        self.ctx.close()


def test_next_player_joycon_a_acks_ai_turn_summary_like_the_button(server_url, browser, joycons):
    table = Table(server_url, browser, joycons)
    try:
        fake, game = joycons, table.game
        # 紅軍行動中（摘要尚未 ended）：下一位先按住 A 不放。
        st = table.play_until(lambda s: s["aiPublic"]["open"] and not s["aiPublic"]["ended"])
        nxt = table.humans[table.next_human_after_red()]
        prev = table.humans[st["displayedSeat"]]
        other = next(s for s in table.humans.values() if s["player_id"] not in (nxt["player_id"], prev["player_id"]))
        assert game.current_player().id == table.red_id and not table.awaiting()
        hold_a(fake, nxt["port"])
        st = table.play_until(lambda s: s["aiPublic"]["open"] and s["aiPublic"]["ended"], limit=60)
        assert table.awaiting() and game.current_player().id == table.red_id
        assert "按「知道了」或 A 後才會輪到下一位" in st["aiPublic"]["text"]
        # 控制權：主連線仍是上一個畫面席位那一支；下一位那一支由本分頁的監聽連線擁有（等待中不 claim）。
        assert st["view"] == "waiting" and st["controllerOwner"]["controller"] == prev["controller"]
        assert wait_until(lambda: any(l["controller"] == nxt["controller"] and l["owned"] == nxt["controller"]
                                      for l in table.hs()["lobby"]["listeners"]), timeout=8)
        # 行動中就按住、一路按到 ended 的 A 不是新的按下：不確認。
        time.sleep(1.0)
        assert table.awaiting() and table.hs()["aiPublic"]["ended"], "按住的 A 不可在摘要結束時自動確認"
        release_a(fake, nxt["port"])
        # 錯誤玩家（既不是上一席也不是下一位）的 A：不作用，背景也不受影響。
        press_a(fake, other["port"])
        time.sleep(1.0)
        assert table.awaiting() and game.current_player().id == table.red_id and table.hs()["aiPublic"]["open"]

        # 下一位的 A（按下後一直按住）：伺服器權威放行，摘要關閉並換到下一位——遠早於 60 秒逾時。
        started = time.time()
        hold_a(fake, nxt["port"])
        assert wait_until(lambda: table.released_to_next(), timeout=4), "A 沒有確認"
        elapsed = time.time() - started
        assert elapsed < 4 and game.ai_red_army_ack["acknowledged"] is True
        expected = table.authority_actor()
        if not getattr(game, "pending_choice", None):
            assert expected == nxt["player_id"], "沒有回合邊界待決選擇時，紅軍之後就是下一位"
        st = wait_until(lambda: (lambda s: s if s["view"] == "handoff" and not s["aiPublic"]["open"] else None)(table.hs()), timeout=5)
        assert st and st["handoffSeat"] == expected and st["actor"]["playerId"] == expected
        assert table.page.evaluate("() => document.getElementById('hotseatMask').dataset.aiPublic") == "off"
        assert table.page.evaluate("() => window.lastGameState.ai_red_army.awaiting_ack") is None
        # 監聽連線釋放，主連線改擁有接手席位那一支（交接焦點正確）。
        handoff_port = table.humans[expected]["port"]
        assert wait_until(lambda: table.hs()["controllerOwner"]["seat"] == expected, timeout=8), table.hs()
        assert wait_until(lambda: not table.hs()["lobby"]["listeners"], timeout=5)
        # 確認摘要的那一下 A 仍按住：不可連帶確認交接（不 reload、仍是 handoff）。
        time.sleep(1.2)
        st = table.hs()
        assert st["view"] == "handoff" and st["displayedSeat"] == prev["player_id"] and st["session"]["unlocked"] is False
        release_a(fake, nxt["port"])
        assert table.hs()["view"] == "handoff"
        # 放開後接手席位再按一次 A：才交接，整頁以該席位重新連線並顯示。
        press_a(fake, handoff_port)
        assert wait_until(lambda: (lambda s: s["view"] == "open" and s["displayedSeat"] == expected)(table.hs()), timeout=20), table.hs()
        assert not table.errors, table.errors
    finally:
        table.close()


def test_previous_seat_joycon_and_mouse_button_still_ack(server_url, browser, joycons):
    table = Table(server_url, browser, joycons)
    try:
        fake, game = joycons, table.game
        # 上一個畫面席位（主連線擁有）那一支的 A：維持可確認。
        st = table.play_until(lambda s: s["aiPublic"]["open"] and s["aiPublic"]["ended"])
        prev = table.humans[st["displayedSeat"]]
        assert st["controllerOwner"]["controller"] == prev["controller"] and table.awaiting()
        press_a(fake, prev["port"])
        assert wait_until(lambda: table.released_to_next(), timeout=4), "上一席的 A 沒有確認"
        assert wait_until(lambda: table.hs()["view"] == "handoff" and not table.hs()["aiPublic"]["open"], timeout=5)
        # 下一輪的摘要用滑鼠「知道了」：同一條伺服器確認路徑。
        table.play_until(lambda s: s["aiPublic"]["open"] and s["aiPublic"]["ended"] and s["view"] == "waiting", limit=120)
        assert table.awaiting()
        table.page.click("#hotseatAiDismiss")
        assert wait_until(lambda: table.released_to_next(), timeout=4), "知道了沒有確認"
        assert wait_until(lambda: table.hs()["view"] == "handoff" and not table.hs()["aiPublic"]["open"], timeout=5)
        assert not table.errors, table.errors
    finally:
        table.close()


def test_turn_ended_on_the_page_socket_then_a_and_button_ack(server_url, browser, joycons):
    """實際路徑：真人用分頁自己的遊戲連線結束回合（伺服器在同一個 handler 裡跑 AI 並等確認），之後的 A／知道了也走這條連線。
    修正前：handler 卡在等待確認，同一條連線的 ack 要到逾時才被讀到——按 A 沒有反應。Joy-Con 為 fake UDP＋真 bridge app。"""
    table = Table(server_url, browser, joycons)
    proof = os.environ.get("REDLINE_AI_ACK_PROOF_DIR")
    try:
        fake, game = joycons, table.game
        st = table.play_until(lambda s: s["aiPublic"]["open"] and s["aiPublic"]["ended"], limit=120, via_page=True)
        nxt = table.humans[table.next_human_after_red()]
        prev = table.humans[st["displayedSeat"]]
        assert table.awaiting() and game.current_player().id == table.red_id
        assert st["view"] == "waiting" and st["controllerOwner"]["controller"] == prev["controller"]
        assert table.page.evaluate("() => window.lastGameState.ai_red_army.awaiting_ack.turn") == game.turn
        assert wait_until(lambda: any(l["controller"] == nxt["controller"] and l["owned"] == nxt["controller"]
                                      for l in table.hs()["lobby"]["listeners"]), timeout=8)
        if proof:
            Path(proof).mkdir(parents=True, exist_ok=True)
            table.page.screenshot(path=str(Path(proof) / "1_summary_before_a.png"))
        table.page.evaluate("() => { window.__ackSent = 0; const orig = window.sendAction; window.sendAction = function (a, p) {"
                            " if (a === 'ack_ai_red_army') window.__ackSent += 1; return orig.apply(this, arguments); }; }")
        # 下一位的 A（一次按下後按住）：遠早於 60 秒逾時就放行，並只送出一次 ack。
        started = time.time()
        hold_a(fake, nxt["port"])
        assert wait_until(lambda: table.released_to_next(), timeout=4), f"A 沒有確認（{time.time() - started:.1f}s）"
        assert game.ai_red_army_ack["acknowledged"] is True
        expected = table.authority_actor()
        st = wait_until(lambda: (lambda s: s if s["view"] == "handoff" and not s["aiPublic"]["open"] else None)(table.hs()), timeout=5)
        assert st and st["handoffSeat"] == expected
        assert table.page.evaluate("() => window.__ackSent") == 1
        assert wait_until(lambda: table.hs()["controllerOwner"]["seat"] == expected, timeout=8), table.hs()
        assert wait_until(lambda: "按 A 確認接手" in table.page.inner_text("#hotseatStatus"), timeout=5)
        if proof:
            table.page.screenshot(path=str(Path(proof) / "2_handoff_after_a.png"))
        # 按住的 A 不穿透交接；放開後接手席位的下一次 A 才交接。
        time.sleep(1.2)
        st = table.hs()
        assert st["view"] == "handoff" and st["displayedSeat"] == prev["player_id"] and st["session"]["unlocked"] is False
        release_a(fake, nxt["port"])
        press_a(fake, table.humans[expected]["port"])
        assert wait_until(lambda: (lambda s: s["view"] == "open" and s["displayedSeat"] == expected)(table.hs()), timeout=20), table.hs()
        if proof:
            table.page.screenshot(path=str(Path(proof) / "3_next_player_open.png"))

        # 下一輪：同樣由分頁連線結束回合，滑鼠「知道了」也立即生效。
        table.play_until(lambda s: s["aiPublic"]["open"] and s["aiPublic"]["ended"] and s["view"] == "waiting", limit=120, via_page=True)
        assert table.awaiting()
        table.page.click("#hotseatAiDismiss")
        assert wait_until(lambda: table.released_to_next(), timeout=4), "知道了沒有確認"
        assert game.ai_red_army_ack["acknowledged"] is True
        assert not table.errors, table.errors
    finally:
        table.close()
