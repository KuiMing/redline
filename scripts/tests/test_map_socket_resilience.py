"""戰略地圖 WebSocket 斷線韌性回歸測試。

2026-08-08 playtest 回報：打出組織經驗丙、在地圖上選好廈門，「在目前城鎮建立組織（效果）」
按鈕確實亮起，但按下去完全沒有建立組織、也沒有任何錯誤訊息。根因是戰略地圖 iframe 的
WebSocket 斷線後永遠不會重連（父頁 app.js 有自己的重連，所以指揮中心看起來完全正常），
而按鈕的送出路徑在 socket 未開時只是靜默 return。

這裡涵蓋伺服器端「會讓地圖那條 socket 被關掉／被踢掉登記」的兩個成因：
1. broadcast 時某位玩家的連線已死，例外會冒到「正在送出動作那位玩家」的 handler，
   把對方的 socket 一起關掉。
2. 舊連線收尾時無條件 pop 掉該玩家的登記，會把同一位玩家後來建立的新連線一起踢掉；
   以及滿桌 4 人時任何重連都會被 register_connection 拒絕。
"""
from pathlib import Path
import asyncio
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.game_manager import GameManager
from server.main import broadcast_game_state, manager


class _FakeSocket:
    def __init__(self, alive=True):
        self.alive = alive
        self.sent = []

    async def send_json(self, payload):
        if not self.alive:
            raise RuntimeError("connection closed")
        self.sent.append(payload)


def _make_game():
    return Game([("p1", "甲"), ("p2", "乙")])


def test_register_connection_allows_same_player_to_reconnect_when_table_is_full():
    gm = GameManager()
    game_id = gm.create_room()
    sockets = {f"player{i}": _FakeSocket() for i in range(4)}
    for pid, ws in sockets.items():
        assert gm.register_connection(game_id, pid, ws) is True

    reconnected = _FakeSocket()
    assert gm.register_connection(game_id, "player0", reconnected) is True
    assert gm.connections[game_id]["player0"] is reconnected
    assert len(gm.connections[game_id]) == 4

    # 第 5 位「不同」玩家仍然要被擋下來。
    assert gm.register_connection(game_id, "player4", _FakeSocket()) is False


def test_remove_connection_does_not_evict_a_newer_socket_for_the_same_player():
    gm = GameManager()
    game_id = gm.create_room()
    old_socket = _FakeSocket()
    new_socket = _FakeSocket()
    gm.register_connection(game_id, "player0", old_socket)
    gm.register_connection(game_id, "player0", new_socket)

    # 舊連線的 handler 收尾：不可以把後來登記的新連線一起移除。
    gm.remove_connection(game_id, "player0", old_socket)
    assert gm.connections[game_id].get("player0") is new_socket

    gm.remove_connection(game_id, "player0", new_socket)
    assert "player0" not in gm.connections[game_id]


def test_broadcast_survives_a_dead_peer_and_still_reaches_the_live_socket():
    game = _make_game()
    game_id = "broadcast-resilience"
    live = _FakeSocket()
    dead = _FakeSocket(alive=False)
    manager.connections[game_id] = {
        game.players[0].id: live,
        game.players[1].id: dead,
    }
    try:
        asyncio.run(broadcast_game_state(game_id, game))
        assert len(live.sent) == 1, "存活的連線仍必須收到完整盤面"
        assert game.players[1].id not in manager.connections[game_id], "已死的連線要被清掉"
        assert manager.connections[game_id][game.players[0].id] is live, "存活的連線不可被連帶移除"
    finally:
        manager.connections.pop(game_id, None)


def test_map_logic_reconnects_and_reports_disconnected_socket_to_the_player():
    """前端守門：地圖 socket 必須有 onclose 重連，且送出動作前不再靜默失敗。"""
    source = (ROOT / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")

    assert "socket.onclose" in source, "地圖 WebSocket 必須有 onclose 才能偵測斷線"
    assert "scheduleMapSocketReconnect" in source, "斷線後必須排程自動重連"
    assert "function requireOpenMapSocket" in source, "送出動作前必須有連線守門"
    assert "MAP_SOCKET_DISCONNECTED_MESSAGE" in source, "斷線時必須有給玩家看的繁中訊息"

    # 三個會改變盤面的送出路徑都必須經過守門，不可以再直接靜默 return。
    for sender in ("function sendDirectBuildAction", "function sendDissolveAction", "function sendMoveAction"):
        start = source.index(sender)
        body = source[start:start + 400]
        assert "requireOpenMapSocket()" in body, f"{sender} 仍會在連線中斷時靜默失敗"
        assert "mapWs.readyState !== WebSocket.OPEN" not in body, f"{sender} 仍保留舊的靜默檢查"
