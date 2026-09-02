import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.move_confirmation import MoveConfirmationTestRoutes
from server.test_routes.runtime import GameSetupRuntime


class FakeManager:
    def __init__(self):
        self.games = {}
        self.connections = {}


def _runtime(manager=None):
    return GameSetupRuntime(
        manager=manager or FakeManager(),
        lobby={},
        lobby_hosts={},
        lobby_factions={},
        lobby_bases={},
        lobby_ready={},
    )


def _make_app(provider):
    routes = MoveConfirmationTestRoutes(provider)
    app = FastAPI()
    app.include_router(routes.router)
    return app


def _effective_app_routes():
    for route in main.app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from original_router.routes
        else:
            yield route


def test_move_confirmation_default_state_and_lobby_registration():
    runtime = _runtime()
    result = MoveConfirmationTestRoutes(
        lambda: runtime
    ).test_setup_move_confirmation_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "opponent_player_id",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    mover, opponent = game.players

    assert result["success"] is True
    assert result["player_id"] == mover.id
    assert result["opponent_player_id"] == opponent.id
    assert result["url"] == f"/?game_id={game_id}&player_id={mover.id}"

    assert (mover.faction_id, mover.base, mover.organizations, mover.moves_left) == (
        "taiwan_green",
        "臺北",
        {"臺北": 1},
        5,
    )
    assert (opponent.faction_id, opponent.base, opponent.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert game.current_player_index == 0
    assert game.round_start_player_index == 0
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == mover.id
    assert runtime.lobby_factions[game_id] == {
        mover.id: "taiwan_green",
        opponent.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {mover.id: "臺北", opponent.id: "北京"}
    assert runtime.lobby_ready[game_id] == {mover.id: True, opponent.id: True}


def test_move_confirmation_custom_payload_overrides():
    runtime = _runtime()
    result = MoveConfirmationTestRoutes(
        lambda: runtime
    ).test_setup_move_confirmation_proof(
        {
            "mover_faction": "liberals",
            "mover_base": "香港城",
            "mover_town": "新北",
            "moves_left": "9",
        }
    )
    game = runtime.manager.games[result["game_id"]]
    mover, _opponent = game.players

    assert (mover.faction_id, mover.base, mover.organizations, mover.moves_left) == (
        "liberals",
        "香港城",
        {"新北": 1},
        9,
    )


def test_main_move_confirmation_uses_rebound_runtime_and_callable(monkeypatch):
    manager = FakeManager()
    lobby = {}
    hosts = {}
    factions = {}
    bases = {}
    ready = {}
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "lobby", lobby)
    monkeypatch.setattr(main, "lobby_hosts", hosts)
    monkeypatch.setattr(main, "lobby_factions", factions)
    monkeypatch.setattr(main, "lobby_bases", bases)
    monkeypatch.setattr(main, "lobby_ready", ready)

    response = TestClient(main.app).post("/test/setup-move-confirmation-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_move_confirmation_proof({"moves_left": 2})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_move_confirmation_proof)


def test_move_confirmation_uuid_order_is_stable(monkeypatch):
    from server.test_routes import move_confirmation

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(move_confirmation.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = MoveConfirmationTestRoutes(
        lambda: runtime
    ).test_setup_move_confirmation_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_move_confirmation_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-move-confirmation-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "opponent_player_id",
        "url",
        "state",
    }
    assert client.post("/test/setup-move-confirmation-proof").status_code == 422
    list_response = client.post("/test/setup-move-confirmation-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-move-confirmation-proof"]["post"]
    assert operation["summary"] == "Test Setup Move Confirmation Proof"
    assert operation["operationId"].startswith("test_setup_move_confirmation_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-move-confirmation-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-move-confirmation-proof")
    assert paths[index - 1] == "/test/setup-enemy-occupancy-proof"
    assert paths[index + 1] == "/test/setup-destroyed-red-base-marker-proof"
