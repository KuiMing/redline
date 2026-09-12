"""End-to-end smoke: drive a REAL REDLINE server (subprocess, isolated port,
/test/* routes NOT enabled) through the MCP tool implementations, exactly as
an MCP client would call them. This is the "did we actually wire the real
HTTP+WebSocket boundary correctly" test — everything else in this file's
siblings is a fast unit test against fabricated data.

The stdio *protocol* itself (JSON-RPC framing, tools/list, tools/call) is
covered separately by scripts/validate/mcp_stdio_smoke.py, which spawns
`python -m mcp_server` as a subprocess and talks MCP over stdio for real.
"""

from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.context import AppContext
from mcp_server.redline_client import RedlineClient
from mcp_server.rules_data import RulesCatalog
from mcp_server.tools import gameplay, lobby, rules


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def redline_server():
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {k: v for k, v in __import__("os").environ.items() if k != "ENABLE_TEST_ROUTES"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 20
        import urllib.request

        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{base_url}/factions", timeout=1)
                break
            except Exception:
                time.sleep(0.3)
        else:
            proc.terminate()
            raise RuntimeError("REDLINE test server did not become ready in time")
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def ctx(redline_server):
    client = RedlineClient(base_url=redline_server)
    return AppContext(client=client, rules=RulesCatalog(client))


async def _resolve_any_pending_choice(ctx, game_id, player_ids, max_iterations=5):
    """The first event drawn each game is random and occasionally forces an
    immediate pending_choice (e.g. a discard) before anyone can act. Drain
    any such choice(s) with the safe default index 0 — this also doubles as
    a live exercise of resolve_pending_choice, not just the unit tests in
    test_mcp_privacy_and_legal_actions.py."""
    for _ in range(max_iterations):
        resolved_one = False
        for player_id in player_ids:
            legal = await gameplay.get_legal_actions(ctx, game_id, player_id)
            entry = next((a for a in legal["actions"] if a["kind"] == "resolve_pending_choice"), None)
            if entry is None:
                continue
            if entry.get("use_indices_param"):
                pick = list(range(entry.get("min_count") or entry.get("count") or 0))
                result = await gameplay.resolve_pending_choice(ctx, game_id, player_id, indices=pick)
            else:
                result = await gameplay.resolve_pending_choice(ctx, game_id, player_id, index=0)
            assert result["ok"] is True, result
            resolved_one = True
        if not resolved_one:
            return
    raise AssertionError("pending choice never cleared after max_iterations")


@pytest.mark.anyio
async def test_full_lobby_to_first_action_flow(ctx):
    host = await lobby.create_room(ctx, "Host")
    assert host["ok"] is True
    game_id, host_id = host["game_id"], host["player_id"]

    guest = await lobby.join_room(ctx, game_id, "Guest")
    assert guest["ok"] is True
    guest_id = guest["player_id"]

    factions = await lobby.list_factions(ctx)
    assert any(f["faction_id"] == "red_army" for f in factions["factions"])

    assert (await lobby.choose_faction(ctx, game_id, host_id, "red_army"))["ok"]
    assert (await lobby.choose_faction(ctx, game_id, guest_id, "taiwan_green", "臺北"))["ok"]
    assert (await lobby.set_ready(ctx, game_id, host_id))["ok"]
    assert (await lobby.set_ready(ctx, game_id, guest_id))["ok"]

    status = await lobby.get_room_status(ctx, game_id)
    assert status["started"] is False
    assert status["ready"] == {host_id: True, guest_id: True}

    started = await lobby.start_game(ctx, game_id, host_id)
    assert started["ok"] is True
    await _resolve_any_pending_choice(ctx, game_id, [host_id, guest_id])

    known = await lobby.list_known_rooms(ctx)
    assert game_id in {room["game_id"] for room in known["rooms"]}

    host_state = await gameplay.get_state(ctx, game_id, host_id)
    guest_state = await gameplay.get_state(ctx, game_id, guest_id)
    assert host_state["ok"] and guest_state["ok"]
    # A random opening event can force a discard/draw before this point, so
    # only the shape (non-negative int) is guaranteed, not an exact count.
    assert isinstance(host_state["state"]["my_hand_size"], int) and host_state["state"]["my_hand_size"] >= 0
    assert isinstance(guest_state["state"]["my_hand_size"], int) and guest_state["state"]["my_hand_size"] >= 0

    # Privacy: neither seat's raw player rows expose the other's hand contents.
    host_players = await gameplay.get_state_detail(ctx, game_id, host_id, "players")
    other_row = next(p for p in host_players["value"] if p["id"] == guest_id)
    assert all(card == "未知手牌" for card in other_row["hand"])

    current_name = guest_state["state"]["current_player_name"]
    assert current_name in {"Host", "Guest"}
    first_id, second_id = (guest_id, host_id) if current_name == "Guest" else (host_id, guest_id)

    out_of_turn = await gameplay.play_card(ctx, game_id, second_id, 0, "resource")
    assert out_of_turn["ok"] is False
    assert "turn" in out_of_turn["error"].lower()

    legal = await gameplay.get_legal_actions(ctx, game_id, first_id)
    assert legal["ok"] is True
    pre_play_hand_size = sum(1 for a in legal["actions"] if a["kind"] == "play_card")
    assert pre_play_hand_size > 0
    assert any(a["kind"] == "advance_turn" for a in legal["actions"])

    played = await gameplay.play_card(ctx, game_id, first_id, 0, "resource")
    assert played["ok"] is True
    assert played["state"]["my_hand_size"] == pre_play_hand_size - 1

    bad_index = await gameplay.play_card(ctx, game_id, first_id, 99, "resource")
    assert bad_index["ok"] is False

    advanced = await gameplay.advance_turn(ctx, game_id, first_id)
    assert advanced["ok"] is True
    assert advanced["state"]["current_player_name"] != current_name or advanced["state"]["turn_phase"] != "action"

    await gameplay.disconnect_session(ctx, game_id, first_id)
    reconnected = await gameplay.get_state(ctx, game_id, first_id)
    assert reconnected["ok"] is True


@pytest.mark.anyio
async def test_rules_and_card_reference_tools(ctx):
    rulebook = await rules.get_rules_text(ctx)
    assert "勝利條件" in rulebook["rules_markdown"]

    cards = await rules.list_cards(ctx)
    names = {c["name"] for c in cards["cards"]}
    assert "追隨者" in names

    detail = await rules.get_card_detail(ctx, "追隨者")
    assert detail["ok"] is True
    assert detail["card"]["name"] == "追隨者"

    missing = await rules.get_card_detail(ctx, "不存在的卡牌")
    assert missing["ok"] is False

    faction = await rules.get_faction_detail(ctx, "red_army")
    assert faction["ok"] is True
    assert any("統戰部" == a.get("name") for a in faction["abilities"])


@pytest.mark.anyio
async def test_short_multi_turn_round_loop(ctx):
    """Play resource-mode cards and advance the turn a handful of times
    across both seats, proving the connection/session stays usable across
    several consecutive actions and turn handoffs (not just one)."""
    host = await lobby.create_room(ctx, "Host2")
    game_id, host_id = host["game_id"], host["player_id"]
    guest = await lobby.join_room(ctx, game_id, "Guest2")
    guest_id = guest["player_id"]
    await lobby.choose_faction(ctx, game_id, host_id, "red_army")
    await lobby.choose_faction(ctx, game_id, guest_id, "taiwan_green", "臺北")
    await lobby.set_ready(ctx, game_id, host_id)
    await lobby.set_ready(ctx, game_id, guest_id)
    await lobby.start_game(ctx, game_id, host_id)
    await _resolve_any_pending_choice(ctx, game_id, [host_id, guest_id])

    seats = {"Host2": host_id, "Guest2": guest_id}
    state = await gameplay.get_state(ctx, game_id, host_id)
    assert state["ok"]

    for _ in range(4):
        await _resolve_any_pending_choice(ctx, game_id, [host_id, guest_id])
        current_name = state["state"]["current_player_name"]
        actor_id = seats[current_name]
        legal = await gameplay.get_legal_actions(ctx, game_id, actor_id)
        assert legal["ok"] is True
        if legal["waiting_on"]:
            # Still waiting after draining pending choices (e.g. it is
            # genuinely the other seat's turn to act) — just resync state
            # and retry next iteration rather than failing the smoke.
            state = await gameplay.get_state(ctx, game_id, host_id)
            continue
        play_entry = next((a for a in legal["actions"] if a["kind"] == "play_card"), None)
        if play_entry:
            result = await gameplay.play_card(ctx, game_id, actor_id, play_entry["index"], "resource")
            assert result["ok"] is True
            state = result
        advanced = await gameplay.advance_turn(ctx, game_id, actor_id)
        assert advanced["ok"] is True, advanced
        state = advanced

    assert state["state"]["turn"] >= 1
    assert state["state"]["game_over"] is False
