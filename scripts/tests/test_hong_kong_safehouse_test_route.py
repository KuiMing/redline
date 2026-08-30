import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.hong_kong_safehouse import HongKongSafehouseTestRoutes
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
    )


def _make_app(provider):
    routes = HongKongSafehouseTestRoutes(provider)
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


def test_hong_kong_safehouse_default_state_and_lobby_registration():
    runtime = _runtime()
    result = HongKongSafehouseTestRoutes(
        lambda: runtime
    ).test_setup_hong_kong_safehouse({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "base",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    hk, red = game.players

    assert result["success"] is True
    assert result["base"] == "香港城"
    assert result["player_id"] == hk.id
    assert (hk.name, hk.faction_id, hk.base, hk.organizations, hk.hand) == (
        "hk",
        "hong_kong",
        "香港城",
        {"香港城": 1},
        [],
    )
    assert (red.name, red.faction_id, red.base, red.organizations) == (
        "red",
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert result["turn_phase"] == TurnPhase.ACTION
    assert result["game_phase"] == GamePhase.MAIN
    assert result["players"] == [
        {"id": player.id, "name": player.name, "faction": player.faction_id}
        for player in game.players
    ]
    assert result["state"]["players"][0]["hand"] == []

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == hk.id
    assert runtime.lobby_factions[game_id] == {hk.id: "hong_kong", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {hk.id: "香港城", red.id: "北京"}


def test_hong_kong_safehouse_custom_base_overrides_organizations_key():
    runtime = _runtime()
    result = HongKongSafehouseTestRoutes(
        lambda: runtime
    ).test_setup_hong_kong_safehouse({"base": "九龍"})

    game = runtime.manager.games[result["game_id"]]
    hk, _red = game.players

    assert result["base"] == "九龍"
    assert hk.base == "九龍"
    assert hk.organizations == {"九龍": 1}
    assert runtime.lobby_bases[result["game_id"]][hk.id] == "九龍"


def test_main_hong_kong_safehouse_uses_rebound_runtime_and_callable(monkeypatch):
    manager = FakeManager()
    lobby = {}
    hosts = {}
    factions = {}
    bases = {}
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "lobby", lobby)
    monkeypatch.setattr(main, "lobby_hosts", hosts)
    monkeypatch.setattr(main, "lobby_factions", factions)
    monkeypatch.setattr(main, "lobby_bases", bases)

    response = TestClient(main.app).post("/test/setup-hong-kong-safehouse", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_hong_kong_safehouse({"base": "九龍"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_hong_kong_safehouse)


def test_hong_kong_safehouse_uuid_order_is_stable(monkeypatch):
    from server.test_routes import hong_kong_safehouse

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(hong_kong_safehouse.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = HongKongSafehouseTestRoutes(
        lambda: runtime
    ).test_setup_hong_kong_safehouse({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_hong_kong_safehouse_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-hong-kong-safehouse", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "base",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    assert client.post("/test/setup-hong-kong-safehouse").status_code == 422
    list_response = client.post("/test/setup-hong-kong-safehouse", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-hong-kong-safehouse"]["post"]
    assert operation["summary"] == "Test Setup Hong Kong Safehouse"
    assert operation["operationId"].startswith("test_setup_hong_kong_safehouse_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-hong-kong-safehouse"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-hong-kong-safehouse")
    assert paths[index - 1] == "/test/resolve-intel-network-cancel-reaction-proof"
    assert paths[index + 1] == "/test/setup-pending-choice-board-guard"
