"""TDD coverage for the lobby "AI 紅軍" toggle (server-owned, not a
client-only flag — see /ai-red-army, choose_faction(), and start_game() in
server/lobby_routes.py).

Contract under test:
- defaults to off for a brand-new room
- only the host may change it; a guest's attempt is rejected server-side
- an invalid (non-boolean) value is rejected
- it is immutable once the game has actually started
- every /lobby/{game_id} GET reflects the current server value (no stale
  client cache)
- with it on, a room can start with zero human Red Army players, and a
  human cannot simultaneously choose Red Army while it is on
- with it off, every existing seat/start rule is completely unchanged
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from server import main


def _client() -> TestClient:
    return TestClient(main.app)


def _create_room(client: TestClient, name: str = "Host", device_id: str = "ai-toggle-host") -> dict:
    return client.post("/create", json={"name": name, "device_id": device_id}).json()


def _join(client: TestClient, game_id: str, name: str, device_id: str) -> dict:
    return client.post("/join", json={"game_id": game_id, "name": name, "device_id": device_id}).json()


# ---------- default is off ----------

def test_ai_red_army_defaults_to_off_for_a_new_room():
    client = _client()
    created = _create_room(client)
    game_id = created["game_id"]

    lobby_state = client.get(f"/lobby/{game_id}").json()

    assert lobby_state["ai_red_army"] is False


# ---------- host can set it ----------

def test_host_can_enable_ai_red_army():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]

    result = client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True}).json()

    assert result == {"success": True, "ai_red_army": True}
    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is True


def test_host_can_turn_it_back_off():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True})

    result = client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": False}).json()

    assert result == {"success": True, "ai_red_army": False}
    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is False


# ---------- guest is rejected ----------

def test_guest_cannot_enable_ai_red_army():
    client = _client()
    created = _create_room(client)
    game_id = created["game_id"]
    guest = _join(client, game_id, "Guest", "ai-toggle-guest")
    guest_id = guest["player_id"]

    result = client.post("/ai-red-army", json={"game_id": game_id, "player_id": guest_id, "enabled": True}).json()

    assert result == {"error": "Only host can change AI Red Army setting"}
    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is False


# ---------- invalid value is rejected ----------

def test_non_boolean_value_is_rejected():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]

    for bad_value in ["yes", 1, None, "true", [], {}]:
        result = client.post(
            "/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": bad_value}
        ).json()
        assert result == {"error": "Invalid value"}, f"expected rejection for {bad_value!r}, got {result}"

    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is False


# ---------- immutable after start ----------

def test_cannot_change_after_game_started():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    guest = _join(client, game_id, "Guest", "ai-toggle-start-guest")
    guest_id = guest["player_id"]

    main.lobby_factions[game_id] = {host_id: "liberals", guest_id: "red_army"}
    main.lobby_ready[game_id] = {host_id: True, guest_id: True}
    started = client.post("/start", json={"game_id": game_id, "player_id": host_id}).json()
    assert started.get("success") is True

    result = client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True}).json()

    assert result == {"error": "Game already started"}


# ---------- every lobby GET reflects the current server value ----------

def test_lobby_get_always_reflects_current_server_value_not_a_stale_cache():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]

    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is False
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True})
    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is True
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": False})
    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is False


# ---------- enabling is rejected if a human already chose red_army ----------

def test_enabling_is_rejected_while_a_human_already_chose_red_army():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    main.lobby_factions[game_id] = {host_id: "red_army"}

    result = client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True}).json()

    assert result == {"error": "請先取消已選擇紅軍的玩家，才能開啟 AI 紅軍"}
    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is False


# ---------- seat/start semantics: AI on ----------

def test_game_can_start_with_ai_red_army_on_and_zero_human_red_army_players():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    guest = _join(client, game_id, "Guest", "ai-toggle-seat-guest")
    guest_id = guest["player_id"]

    enabled = client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True}).json()
    assert enabled["success"] is True

    main.lobby_factions[game_id] = {host_id: "liberals", guest_id: "hong_kong"}
    main.lobby_ready[game_id] = {host_id: True, guest_id: True}
    result = client.post("/start", json={"game_id": game_id, "player_id": host_id}).json()

    assert result.get("success") is True
    assert result.get("ai_red_army") is True
    game = main.manager.games.get(game_id)
    assert game is not None
    assert game.ai_red_army_player_id is not None
    ai_player = next(p for p in game.players if p.id == game.ai_red_army_player_id)
    assert ai_player.faction_id == "red_army"
    # The virtual AI seat is never a human join — it must never appear in
    # the human lobby roster/ready/credentials bookkeeping.
    assert game.ai_red_army_player_id not in [pid for pid, _ in main.lobby[game_id]]


def test_single_human_plus_ai_is_enough_players_to_start():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True})

    main.lobby_factions[game_id] = {host_id: "liberals"}
    main.lobby_ready[game_id] = {host_id: True}
    result = client.post("/start", json={"game_id": game_id, "player_id": host_id}).json()

    assert result.get("success") is True
    assert main.manager.games.get(game_id) is not None


# ---------- virtual seat is not websocket-connectable (security) ----------

def test_virtual_ai_seat_cannot_be_connected_to_over_websocket():
    """The virtual AI seat's id is fully deterministic (f"ai-red-army-{game_id}")
    and game_id is public (it's in the room URL), yet the seat is deliberately
    never added to lobby_player_credentials (see start_game()'s comment). The
    websocket endpoint's credential check only runs `if credential:` — with no
    credential entry at all, the check used to be skipped entirely rather than
    rejected, so anyone who knew the public game_id could connect as this id
    with zero token and receive Red Army's real, un-redacted hand. This test
    reproduces that exact attack and asserts the connection is now refused
    before any state is ever sent."""
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    guest = _join(client, game_id, "Guest", "ai-toggle-seat-security-guest")
    guest_id = guest["player_id"]
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True})
    main.lobby_factions[game_id] = {host_id: "liberals", guest_id: "hong_kong"}
    main.lobby_ready[game_id] = {host_id: True, guest_id: True}
    client.post("/start", json={"game_id": game_id, "player_id": host_id})

    game = main.manager.games[game_id]
    ai_player_id = game.ai_red_army_player_id
    assert ai_player_id == f"ai-red-army-{game_id}"  # confirms it is guessable from game_id alone

    with client.websocket_connect(f"/ws/{game_id}/{ai_player_id}") as ws:
        payload = ws.receive_json()
        assert payload.get("error") == "This seat is AI-controlled and cannot be connected to"
        with pytest.raises(Exception):
            ws.receive_json()  # the server must have closed the connection, not kept it open


def test_human_cannot_choose_red_army_while_ai_is_enabled():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True})

    result = client.post(
        "/choose-faction",
        json={"game_id": game_id, "player_id": host_id, "faction_id": "red_army", "base_name": "北京"},
    ).json()

    assert result == {"error": "AI 紅軍已啟用，紅軍席位由電腦控制，玩家不可選擇"}
    assert main.lobby_factions.get(game_id, {}).get(host_id) is None


def test_required_faction_rule_never_forces_red_army_on_a_human_when_ai_is_on():
    # With AI on, room capacity for humans is 3 (the 4th seat is the AI's —
    # see test_room_capacity_is_three_humans_when_ai_is_enabled), so this
    # fills the room completely (host + 2 guests) rather than 4 humans.
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True})
    player_ids = [host_id]
    for index in range(1, 3):
        joined = _join(client, game_id, f"Player {index + 1}", f"ai-toggle-forced-{index}")
        player_ids.append(joined["player_id"])

    lobby_state = client.get(f"/lobby/{game_id}").json()

    assert lobby_state["required_faction_by_player"] == {}


def test_room_capacity_is_three_humans_when_ai_is_enabled():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True})
    for index in range(2):
        joined = _join(client, game_id, f"Player {index + 1}", f"ai-toggle-capacity-{index}")
        assert joined.get("error") is None

    rejected = _join(client, game_id, "One Too Many", "ai-toggle-capacity-overflow")

    assert rejected == {"error": "Room full"}


def test_enabling_ai_is_rejected_when_room_already_has_four_humans():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    for index in range(3):
        _join(client, game_id, f"Player {index + 1}", f"ai-toggle-full-{index}")

    result = client.post("/ai-red-army", json={"game_id": game_id, "player_id": host_id, "enabled": True}).json()

    assert result == {"error": "房間人數已達上限，無法開啟 AI 紅軍"}
    assert client.get(f"/lobby/{game_id}").json()["ai_red_army"] is False


# ---------- seat/start semantics: AI off (existing behavior unchanged) ----------

def test_existing_seat_rules_are_completely_unchanged_when_ai_is_off():
    client = _client()
    created = _create_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    guest = _join(client, game_id, "Guest", "ai-toggle-off-guest")
    guest_id = guest["player_id"]

    main.lobby_factions[game_id] = {host_id: "liberals", guest_id: "hong_kong"}
    main.lobby_ready[game_id] = {host_id: True, guest_id: True}
    result = client.post("/start", json={"game_id": game_id, "player_id": host_id}).json()

    assert result == {"error": "必須有且只能有一名玩家選擇紅軍，才能啟動行動"}
    assert main.manager.games.get(game_id) is None


def test_room_capacity_is_still_four_humans_when_ai_is_off():
    client = _client()
    created = _create_room(client)
    game_id = created["game_id"]
    for index in range(3):
        joined = _join(client, game_id, f"Player {index + 1}", f"ai-toggle-off-capacity-{index}")
        assert joined.get("error") is None

    rejected = _join(client, game_id, "One Too Many", "ai-toggle-off-capacity-overflow")

    assert rejected == {"error": "Room full"}
