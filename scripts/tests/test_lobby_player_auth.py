"""/choose-faction and /ready are seat mutations: they must prove ownership of
the seat with its own resume_token. player_ids are public via /lobby."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from server import main

AUTH_ERROR = {"error": "Invalid player credentials"}


def _room(client, tag):
    created = client.post("/create", json={"name": "Host", "device_id": f"auth-{tag}-host"}).json()
    joined = client.post("/join", json={
        "game_id": created["game_id"], "name": "Guest", "device_id": f"auth-{tag}-guest",
    }).json()
    return {
        "game_id": created["game_id"],
        "p1": created["host_id"], "t1": created["resume_token"],
        "p2": joined["player_id"], "t2": joined["resume_token"],
    }


def _snapshot(client, game_id):
    lobby = client.get(f"/lobby/{game_id}").json()
    return {k: lobby.get(k) for k in ("factions", "bases", "ready")}


def _choose(client, room, player, token, faction="liberals", base="北京"):
    body = {"game_id": room["game_id"], "player_id": room[player], "faction_id": faction, "base_name": base}
    if token is not None:
        body["resume_token"] = token
    return client.post("/choose-faction", json=body).json()


def _ready(client, room, player, token, ready=True):
    body = {"game_id": room["game_id"], "player_id": room[player], "ready": ready}
    if token is not None:
        body["resume_token"] = token
    return client.post("/ready", json=body).json()


BAD_TOKENS = {
    "missing": lambda room: None,
    "empty": lambda room: "",
    "wrong": lambda room: "not-the-token",
    "non_ascii": lambda room: "令牌密碼-é",
    "other_seat": lambda room: room["t2"],  # P2's token used on P1's seat
    "non_string": lambda room: 12345,
}


@pytest.mark.parametrize("kind", list(BAD_TOKENS))
def test_choose_faction_rejects_bad_credentials_without_changing_lobby(kind):
    client = TestClient(main.app)
    room = _room(client, f"choose-{kind}")
    before = _snapshot(client, room["game_id"])

    result = _choose(client, room, "p1", BAD_TOKENS[kind](room))

    assert result == AUTH_ERROR
    assert _snapshot(client, room["game_id"]) == before


@pytest.mark.parametrize("kind", list(BAD_TOKENS))
@pytest.mark.parametrize("ready", [True, False])
def test_ready_rejects_bad_credentials_without_changing_lobby(kind, ready):
    client = TestClient(main.app)
    room = _room(client, f"ready-{kind}-{ready}")
    assert _choose(client, room, "p1", room["t1"]).get("success") is True
    assert _ready(client, room, "p1", room["t1"], ready=not ready).get("success") is True
    before = _snapshot(client, room["game_id"])

    result = _ready(client, room, "p1", BAD_TOKENS[kind](room), ready=ready)

    assert result == AUTH_ERROR
    assert _snapshot(client, room["game_id"]) == before


def test_correct_token_can_choose_and_ready_own_seat_only():
    client = TestClient(main.app)
    room = _room(client, "ok")

    chosen = _choose(client, room, "p1", room["t1"])
    assert chosen["success"] is True
    assert chosen["factions"][room["p1"]] == "liberals"
    assert _ready(client, room, "p1", room["t1"])["ready"][room["p1"]] is True
    assert _ready(client, room, "p1", room["t1"], ready=False)["ready"][room["p1"]] is False

    assert _choose(client, room, "p2", room["t2"], faction="taiwan_green", base="臺北").get("success") is True
    assert _ready(client, room, "p2", room["t2"]).get("success") is True
    lobby = _snapshot(client, room["game_id"])
    assert lobby["factions"] == {room["p1"]: "liberals", room["p2"]: "taiwan_green"}


def test_seat_without_stored_credential_fails_closed():
    client = TestClient(main.app)
    room = _room(client, "nocred")
    main.lobby_player_credentials[room["game_id"]].pop(room["p1"])
    before = _snapshot(client, room["game_id"])

    assert _choose(client, room, "p1", room["t1"]) == AUTH_ERROR
    assert _ready(client, room, "p1", room["t1"]) == AUTH_ERROR
    assert _snapshot(client, room["game_id"]) == before
