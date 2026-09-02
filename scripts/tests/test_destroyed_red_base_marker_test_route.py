import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.destroyed_red_base_marker import DestroyedRedBaseMarkerTestRoutes
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
    routes = DestroyedRedBaseMarkerTestRoutes(provider)
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


def test_destroyed_red_base_marker_default_destroyed_state():
    runtime = _runtime()
    result = DestroyedRedBaseMarkerTestRoutes(
        lambda: runtime
    ).test_setup_destroyed_red_base_marker_proof({})

    assert set(result) == {
        "success",
        "destroyed",
        "game_id",
        "player_id",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    mongol, red = game.players

    assert result["success"] is True
    assert result["destroyed"] is True
    assert result["player_id"] == mongol.id
    assert result["url"] == f"/?game_id={game_id}&player_id={mongol.id}"

    assert (mongol.faction_id, mongol.base, mongol.organizations, mongol.moves_left) == (
        "mongol",
        "烏蘭巴托",
        {"烏蘭巴托": 1, "張家口": 1},
        3,
    )
    assert (red.faction_id, red.base, red.organizations) == ("red_army", "北京", {})
    assert game.current_player_index == 0
    assert game.round_start_player_index == 0
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.id == game_id
    assert game.turn_log["red_army_base_build_blocks"] == ["北京"]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == mongol.id
    assert runtime.lobby_factions[game_id] == {mongol.id: "mongol", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {mongol.id: "烏蘭巴托", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {mongol.id: True, red.id: True}


def test_destroyed_red_base_marker_not_destroyed_state():
    runtime = _runtime()
    result = DestroyedRedBaseMarkerTestRoutes(
        lambda: runtime
    ).test_setup_destroyed_red_base_marker_proof({"destroyed": False})

    game = runtime.manager.games[result["game_id"]]
    _mongol, red = game.players

    assert result["destroyed"] is False
    assert red.organizations == {"北京": 1}
    assert game.turn_log.get("red_army_base_build_blocks") == []


def test_main_destroyed_red_base_marker_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post(
        "/test/setup-destroyed-red-base-marker-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_destroyed_red_base_marker_proof({"destroyed": False})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_destroyed_red_base_marker_proof)


def test_destroyed_red_base_marker_uuid_order_is_stable(monkeypatch):
    from server.test_routes import destroyed_red_base_marker

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(destroyed_red_base_marker.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = DestroyedRedBaseMarkerTestRoutes(
        lambda: runtime
    ).test_setup_destroyed_red_base_marker_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_destroyed_red_base_marker_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-destroyed-red-base-marker-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "destroyed",
        "game_id",
        "player_id",
        "url",
        "state",
    }
    assert client.post("/test/setup-destroyed-red-base-marker-proof").status_code == 422
    list_response = client.post("/test/setup-destroyed-red-base-marker-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-destroyed-red-base-marker-proof"]["post"]
    assert operation["summary"] == "Test Setup Destroyed Red Base Marker Proof"
    assert operation["operationId"].startswith(
        "test_setup_destroyed_red_base_marker_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-destroyed-red-base-marker-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-destroyed-red-base-marker-proof")
    assert paths[index - 1] == "/test/setup-move-confirmation-proof"
    assert paths[index + 1] == "/test/setup-hu-taiwan-shared"
