"""AI 紅軍回合結束確認（ack_ai_red_army）必須能從「結束回合的那一條 WebSocket」送達。

Playtest bug：客廳輪流只有一個瀏覽器分頁、一條遊戲 WebSocket。真人在這條連線上結束回合後，伺服器在同一個 handler 裡
（broadcast_game_state → drive_red_army_turns）跑 AI 紅軍並等待公開視窗確認；handler 卡在等待迴圈，同一條連線送來的
「知道了」／Joy-Con A 確認要到約 10 秒逾時後才被讀到，所以按 A 沒有反應。

真 uvicorn＋真 WebSocket（同一個 process，可讀權威 Game 狀態）；不需要瀏覽器或 Joy-Con。
"""
from __future__ import annotations

import json
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
import server.red_army_ai_runtime as ai_runtime  # noqa: E402

HUMAN_FACTIONS = ("hong_kong", "taiwan_green")


class Seat:
    """一位真人席位的唯一一條遊戲 WebSocket（等同客廳輪流分頁的主連線）。"""

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
        self.drain(0.3)

    def step(self):
        """base_selection／自己的 pending_choice／自己的回合 → 送一個合法動作；回傳是否送出結束回合的 advance。"""
        self.drain()
        s = self.state
        if s.get("game_phase") == "base_selection":
            choice = (s.get("pending_base_choices") or {}).get(self.player_id)
            if choice:
                label = choice["labels"][0]
                town = ((choice.get("resolved") or {}).get(label) or [label])[0]
                self.send({"action": "set_base", "town": town, "label": label})
        elif (s.get("pending_choice") or {}).get("player_id") == self.player_id:
            self.send({"action": "resolve_choice", "choice_id": s["pending_choice"].get("choice_id"), "index": 0})
        elif s.get("current_player") == self.name and not s.get("pending_choice"):
            self.send({"action": "advance"})
            return True
        return False

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


@pytest.fixture(scope="module")
def server_url():
    saved = (ai_runtime.AI_ACTION_DELAY_SECONDS, ai_runtime.AI_ACK_TIMEOUT_SECONDS)
    ai_runtime.AI_ACTION_DELAY_SECONDS = 0.2
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(server_main.app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    ai_runtime.AI_ACTION_DELAY_SECONDS, ai_runtime.AI_ACK_TIMEOUT_SECONDS = saved


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_game(base):
    post = lambda path, body: requests.post(base + path, json=body, timeout=20).json()
    created = post("/create", {"name": "P1", "device_id": "same-sock-p1"})
    gid = created["game_id"]
    humans = [{"player_id": created["host_id"], "token": created["resume_token"], "name": "P1"}]
    joined = post("/join", {"game_id": gid, "name": "P2", "device_id": "same-sock-p2"})
    humans.append({"player_id": joined["player_id"], "token": joined["resume_token"], "name": "P2"})
    assert post("/ai-red-army", {"game_id": gid, "player_id": humans[0]["player_id"], "resume_token": humans[0]["token"], "enabled": True}).get("success")
    for seat, faction in zip(humans, HUMAN_FACTIONS):
        assert post("/choose-faction", {"game_id": gid, "player_id": seat["player_id"], "resume_token": seat["token"], "faction_id": faction}).get("success")
        assert post("/ready", {"game_id": gid, "player_id": seat["player_id"], "resume_token": seat["token"], "ready": True}).get("success")
    assert post("/start", {"game_id": gid, "player_id": humans[0]["player_id"], "resume_token": humans[0]["token"]}).get("success")
    game = server_main.manager.get_game(gid)
    socks = [Seat(base, gid, s["player_id"], s["token"], s["name"]) for s in humans]
    for sock in socks:
        sock.send({"action": "ai_public_hold", "enabled": True})  # 每一條都是客廳輪流顯示端
    return game, socks


def _awaiting(game):
    ack = game.ai_red_army_ack
    return bool(ack and not ack.get("released"))


def _play_until_ai_awaits_ack(game, socks, limit=60.0):
    """以各席位自己的連線推進；回傳最後送出結束回合 advance 的那一條（AI 紅軍緊接在它之後）。"""
    last = None
    deadline = time.time() + limit
    while time.time() < deadline:
        if _awaiting(game):
            return last
        for sock in socks:
            if sock.step():
                last = sock
        time.sleep(0.05)
    raise AssertionError("AI 紅軍沒有進入回合結束等待確認")


def _released_within(game, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        ack = game.ai_red_army_ack
        if not ack or ack.get("released"):
            return True
        time.sleep(0.05)
    return False


def test_ack_on_the_socket_that_ended_the_turn_releases_immediately(server_url):
    ai_runtime.AI_ACK_TIMEOUT_SECONDS = 30.0
    game, socks = _start_game(server_url)
    try:
        ender = _play_until_ai_awaits_ack(game, socks)
        assert ender is not None and game.current_player().id == game.ai_red_army_player_id
        # 公開視窗看到的「回合結束」：同一條連線收得到 awaiting_ack 廣播。
        ender.drain(1.0)
        assert (ender.state.get("ai_red_army") or {}).get("awaiting_ack"), "結束回合的連線沒有收到等待確認的 state"
        started = time.time()
        ender.ws.send(json.dumps({"action": "ack_ai_red_army"}))
        assert _released_within(game, 3.0), f"同一條連線的確認在 {time.time() - started:.1f}s 內沒有生效（逾時 30s）"
        assert game.ai_red_army_ack["acknowledged"] is True
        # 放行後換人並廣播：同一條連線收到 awaiting_ack 清除後的 state。
        deadline = time.time() + 5
        while time.time() < deadline and (ender.state.get("ai_red_army") or {}).get("awaiting_ack"):
            ender.drain(0.2)
        assert not (ender.state.get("ai_red_army") or {}).get("awaiting_ack")
    finally:
        for sock in socks:
            sock.close()


def test_unacknowledged_wait_still_times_out_and_advances(server_url):
    ai_runtime.AI_ACK_TIMEOUT_SECONDS = 1.5
    game, socks = _start_game(server_url)
    try:
        ender = _play_until_ai_awaits_ack(game, socks)
        assert ender is not None
        started = time.time()
        assert not _released_within(game, 1.0), "沒有確認時不可提早放行"
        assert _released_within(game, 4.0), "逾時後必須自動放行"
        assert game.ai_red_army_ack["acknowledged"] is False
        assert time.time() - started >= 1.0
        deadline = time.time() + 5
        while time.time() < deadline and game.current_player().id == game.ai_red_army_player_id and not getattr(game, "pending_choice", None):
            time.sleep(0.05)
        assert game.current_player().id != game.ai_red_army_player_id or getattr(game, "pending_choice", None)
    finally:
        for sock in socks:
            sock.close()
