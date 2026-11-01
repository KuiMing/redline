"""Start-flow room settings are server-authoritative lobby state.

The creator picks 紅軍類型 / 難度 / 操作方式 (+ paired Joy-Con count) before the
room exists; /create validates and stores them, /lobby/{id} exposes them to
everyone, and guests cannot change any of them.
"""
from __future__ import annotations

import sys
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from server import lobby_routes, main


def _client() -> TestClient:
    return TestClient(main.app)


def _create(client, **settings):
    return client.post("/create", json={"name": "Host", "device_id": "start-flow-host", **settings}).json()


def test_plain_create_keeps_legacy_defaults():
    client = _client()
    game_id = _create(client)["game_id"]
    state = client.get(f"/lobby/{game_id}").json()
    assert state["ai_red_army"] is False
    assert state["market_mode"] == "sample_53"
    assert state["control_mode"] == "computer"
    assert state["joycon_count"] is None


def test_create_request_id_replays_one_room_and_rejects_changed_payload():
    client = _client()
    request_id = "browser-create-retry-000001"
    payload = {
        "name": "玩家一號",
        "device_id": "joycon-host",
        "control_mode": "joycon",
        "joycon_count": 2,
        "create_request_id": request_id,
    }
    before = set(main.lobby)
    first = client.post("/create", json=payload).json()
    replay = client.post("/create", json=payload).json()
    assert replay == first
    assert set(main.lobby) - before == {first["game_id"]}

    conflict = client.post("/create", json={**payload, "joycon_count": 3}).json()
    assert conflict == {"error": "Create request payload conflict"}
    assert set(main.lobby) - before == {first["game_id"]}


def test_create_request_replay_cache_expires_and_stays_bounded(monkeypatch):
    now = time.monotonic()
    cache = OrderedDict({
        "expired-request-000001": (now - 61, "expired", {"resume_token": "expired-secret"}),
        "recent-request-000002": (now, "recent-2", {"resume_token": "recent-secret-2"}),
        "recent-request-000003": (now, "recent-3", {"resume_token": "recent-secret-3"}),
    })
    monkeypatch.setattr(lobby_routes, "lobby_create_requests", cache)
    monkeypatch.setattr(lobby_routes, "CREATE_REQUEST_TTL_SECONDS", 60)
    monkeypatch.setattr(lobby_routes, "CREATE_REQUEST_CACHE_MAX", 2)

    result = _create(_client(), create_request_id="new-request-key-000004")
    assert result.get("game_id")
    assert list(cache) == ["recent-request-000003", "new-request-key-000004"]
    assert len(cache) <= lobby_routes.CREATE_REQUEST_CACHE_MAX


def test_create_request_replay_wins_before_capacity_eviction(monkeypatch):
    cache = OrderedDict()
    monkeypatch.setattr(lobby_routes, "lobby_create_requests", cache)
    monkeypatch.setattr(lobby_routes, "CREATE_REQUEST_CACHE_MAX", 2)

    client = _client()
    oldest = _create(client, create_request_id="oldest-request-key-0001")
    _create(client, create_request_id="second-request-key-0002")
    assert len(cache) == 2

    replay = _create(client, create_request_id="oldest-request-key-0001")
    assert replay == oldest
    assert list(cache) == ["oldest-request-key-0001", "second-request-key-0002"]


@pytest.mark.parametrize("request_id", ["short", 123, True])
def test_create_request_id_requires_high_entropy_string(request_id):
    before = set(main.lobby)
    result = _create(_client(), create_request_id=request_id)
    assert result == {"error": "Invalid create request id"}
    assert set(main.lobby) == before


def test_create_stores_all_settings_authoritatively():
    client = _client()
    created = _create(client, ai_red_army=True, market_mode="all_cards", control_mode="joycon", joycon_count=3)
    assert "error" not in created
    state = client.get(f"/lobby/{created['game_id']}").json()
    assert state["ai_red_army"] is True
    assert state["market_mode"] == "all_cards"
    assert state["control_mode"] == "joycon"
    assert state["joycon_count"] == 3


@pytest.mark.parametrize("settings", [
    {"ai_red_army": "yes"},
    {"market_mode": "hard"},
    {"control_mode": "gamepad"},
    {"control_mode": "joycon"},                      # count required
    {"control_mode": "joycon", "joycon_count": 0},   # at least one controller
    {"control_mode": "joycon", "joycon_count": 5},   # at most four
    {"control_mode": "joycon", "joycon_count": "2"},
    {"control_mode": "joycon", "joycon_count": True},
    {"control_mode": "computer", "joycon_count": 2},  # count only with Joy-Con
    {"ai_red_army": True, "control_mode": "joycon", "joycon_count": 4},  # AI takes the 4th seat
])
def test_invalid_settings_are_rejected_without_creating_a_room(settings):
    client = _client()
    before = set(main.lobby)
    result = _create(client, **settings)
    assert "error" in result and "game_id" not in result
    assert set(main.lobby) == before


def test_guest_sees_settings_but_cannot_change_them():
    client = _client()
    created = _create(client, ai_red_army=True, market_mode="all_cards", control_mode="joycon", joycon_count=2)
    game_id = created["game_id"]
    guest = client.post("/join", json={"game_id": game_id, "name": "Guest", "device_id": "g"}).json()
    guest_id = guest["player_id"]

    assert client.post("/market-mode", json={"game_id": game_id, "player_id": guest_id, "market_mode": "sample_53"}).json()["error"]
    assert client.post("/ai-red-army", json={"game_id": game_id, "player_id": guest_id, "enabled": False}).json()["error"]
    state = client.get(f"/lobby/{game_id}").json()
    assert (state["ai_red_army"], state["market_mode"], state["control_mode"], state["joycon_count"]) == (True, "all_cards", "joycon", 2)


def test_guest_join_does_not_need_or_accept_settings():
    client = _client()
    game_id = _create(client, control_mode="joycon", joycon_count=1)["game_id"]
    joined = client.post("/join", json={
        "game_id": game_id, "name": "Guest", "device_id": "g2",
        "control_mode": "computer", "market_mode": "all_cards", "ai_red_army": True,
    }).json()
    assert joined.get("player_id")
    state = client.get(f"/lobby/{game_id}").json()
    assert (state["control_mode"], state["market_mode"], state["ai_red_army"]) == ("joycon", "sample_53", False)


def test_unknown_room_lobby_preview_is_an_error_for_join_by_code():
    assert _client().get("/lobby/does-not-exist").json() == {"error": "Game not found"}


def _ready_two_player_room(client, **settings):
    created = _create(client, **settings)
    game_id, host_id = created["game_id"], created["host_id"]
    guest_id = client.post("/join", json={"game_id": game_id, "name": "Guest", "device_id": "tok-g"}).json()["player_id"]
    main.lobby_factions[game_id] = {host_id: "red_army", guest_id: "liberals"}
    main.lobby_bases[game_id] = {host_id: "北京", guest_id: "臺北"}
    main.lobby_ready[game_id] = {host_id: True, guest_id: True}
    return created, guest_id


@pytest.mark.parametrize("route,body", [
    ("/market-mode", {"market_mode": "all_cards"}),
    ("/ai-red-army", {"enabled": True}),
    ("/start", {}),
])
def test_host_mutations_reject_visitor_who_only_knows_public_host_id(route, body):
    client = _client()
    created, _ = _ready_two_player_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    before = (main.lobby_market_mode[game_id], main.lobby_ai_red_army[game_id])
    for token in (None, "", "guessed-token"):
        payload = {"game_id": game_id, "player_id": host_id, **body}
        if token is not None:
            payload["resume_token"] = token
        assert client.post(route, json=payload).json() == {"error": "Host authentication failed"}
    assert (main.lobby_market_mode[game_id], main.lobby_ai_red_army[game_id]) == before
    assert main.manager.games.get(game_id) is None


@pytest.mark.parametrize("route,body", [
    ("/market-mode", {"market_mode": "all_cards"}),
    ("/ai-red-army", {"enabled": True}),
    ("/start", {}),
])
def test_host_mutations_reject_room_with_missing_stored_host_credential(route, body):
    client = _client()
    created, _ = _ready_two_player_room(client)
    game_id, host_id = created["game_id"], created["host_id"]
    del main.lobby_player_credentials[game_id][host_id]
    payload = {
        "game_id": game_id,
        "player_id": host_id,
        "resume_token": created["resume_token"],
        **body,
    }
    assert client.post(route, json=payload).json() == {"error": "Host authentication failed"}
    assert main.manager.games.get(game_id) is None


def test_host_mutations_accept_the_real_resume_token():
    client = _client()
    created, _ = _ready_two_player_room(client)
    game_id, host_id, token = created["game_id"], created["host_id"], created["resume_token"]
    auth = {"game_id": game_id, "player_id": host_id, "resume_token": token}
    assert client.post("/market-mode", json={**auth, "market_mode": "all_cards"}).json()["success"] is True
    assert client.post("/ai-red-army", json={**auth, "enabled": False}).json()["success"] is True
    assert client.post("/start", json=auth).json()["success"] is True


def test_guest_token_cannot_act_as_host():
    client = _client()
    created, guest_id = _ready_two_player_room(client)
    guest_token = main.lobby_player_credentials[created["game_id"]][guest_id]["resume_token"]
    result = client.post("/start", json={"game_id": created["game_id"], "player_id": guest_id, "resume_token": guest_token}).json()
    assert result["error"] == "Only host can start"


def test_start_ignores_client_market_mode_and_keeps_stored_difficulty():
    client = _client()
    created, _ = _ready_two_player_room(client, market_mode="all_cards")
    game_id = created["game_id"]
    started = client.post("/start", json={
        "game_id": game_id, "player_id": created["host_id"], "resume_token": created["resume_token"],
        "market_mode": "sample_53",  # stale client value must not overwrite the stored difficulty
    }).json()
    assert started["success"] is True
    assert started["market_mode"] == "all_cards"
    assert main.lobby_market_mode[game_id] == "all_cards"
    assert client.get(f"/lobby/{game_id}").json()["market_mode"] == "all_cards"
