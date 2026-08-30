import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.india_support_purchase import IndiaSupportPurchaseTestRoutes
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
    routes = IndiaSupportPurchaseTestRoutes(provider)
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


def test_india_support_purchase_default_state_and_lobby_registration():
    runtime = _runtime()
    result = IndiaSupportPurchaseTestRoutes(
        lambda: runtime
    ).test_setup_india_support_purchase({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "support_name",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    tibet, red = game.players

    assert result["success"] is True
    assert result["player_id"] == tibet.id
    assert result["support_name"] == "印度奧援"
    assert result["turn_phase"] == TurnPhase.ACTION
    assert result["game_phase"] == GamePhase.MAIN

    assert (tibet.faction_id, tibet.base, tibet.organizations, tibet.hand) == (
        "tibet_dehradun",
        "德拉敦",
        {"德拉敦": 1},
        [],
    )
    assert tibet.resources == {"money": 5, "propaganda": 5}
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in game.purchase_area] == ["印度奧援"]
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert result["players"] == [
        {"id": player.id, "name": player.name, "faction": player.faction_id}
        for player in game.players
    ]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == tibet.id
    assert runtime.lobby_factions[game_id] == {tibet.id: "tibet_dehradun", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {tibet.id: "德拉敦", red.id: "北京"}


def test_india_support_purchase_custom_payload_overrides():
    runtime = _runtime()
    result = IndiaSupportPurchaseTestRoutes(
        lambda: runtime
    ).test_setup_india_support_purchase(
        {"base": "達蘭薩拉", "support_name": "西藏奧援"}
    )
    game = runtime.manager.games[result["game_id"]]
    tibet, _red = game.players

    assert result["support_name"] == "西藏奧援"
    assert (tibet.base, tibet.organizations) == ("達蘭薩拉", {"達蘭薩拉": 1})
    assert [card.name for card in game.purchase_area] == ["西藏奧援"]


def test_main_india_support_purchase_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-india-support-purchase", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_india_support_purchase({"support_name": "西藏奧援"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_india_support_purchase)


def test_india_support_purchase_uuid_order_is_stable(monkeypatch):
    from server.test_routes import india_support_purchase

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(india_support_purchase.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = IndiaSupportPurchaseTestRoutes(
        lambda: runtime
    ).test_setup_india_support_purchase({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_india_support_purchase_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-india-support-purchase", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "support_name",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    assert client.post("/test/setup-india-support-purchase").status_code == 422
    list_response = client.post("/test/setup-india-support-purchase", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-india-support-purchase"]["post"]
    assert operation["summary"] == "Test Setup India Support Purchase"
    assert operation["operationId"].startswith("test_setup_india_support_purchase_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-india-support-purchase"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-india-support-purchase")
    assert paths[index - 1] == "/test/setup-shared-dissolve"
    assert paths[index + 1] == "/test/setup-remove-to-purchase"
