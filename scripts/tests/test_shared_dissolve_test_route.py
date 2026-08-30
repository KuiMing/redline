import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.shared_dissolve import SharedDissolveTestRoutes


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
    routes = SharedDissolveTestRoutes(provider)
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


def test_shared_dissolve_default_state_and_lobby_registration():
    runtime = _runtime()
    result = SharedDissolveTestRoutes(
        lambda: runtime
    ).test_setup_shared_dissolve({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "shared_town",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    attacker, hu, tw = game.players

    assert result["success"] is True
    assert result["player_id"] == attacker.id
    assert result["shared_town"] == "上海"
    assert result["turn_phase"] == TurnPhase.ACTION
    assert result["game_phase"] == GamePhase.MAIN

    assert (attacker.faction_id, attacker.base, attacker.organizations) == (
        "red_army",
        "南京",
        {"南京": 1},
    )
    assert [card.name for card in attacker.hand] == ["測試手牌"]
    assert (hu.faction_id, hu.base, hu.organizations, hu.hand) == (
        "hu",
        "紐約",
        {"紐約": 1},
        [],
    )
    assert (tw.faction_id, tw.base, tw.organizations, tw.hand) == (
        "taiwan_green",
        "臺北",
        {"上海": 1, "臺北": 1},
        [],
    )
    assert [card.name for card in tw.deck.draw_pile] == ["補牌A"]
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
    assert runtime.lobby_hosts[game_id] == attacker.id
    assert runtime.lobby_factions[game_id] == {
        attacker.id: "red_army",
        hu.id: "hu",
        tw.id: "taiwan_green",
    }
    assert runtime.lobby_bases[game_id] == {
        attacker.id: "南京",
        hu.id: "紐約",
        tw.id: "臺北",
    }


def test_shared_dissolve_attacker_no_hand_and_custom_payload():
    runtime = _runtime()
    result = SharedDissolveTestRoutes(
        lambda: runtime
    ).test_setup_shared_dissolve(
        {
            "attacker_no_hand": True,
            "attacker_faction": "liberals",
            "attacker_base": "上海",
            "tw_faction": "taiwan_blue",
            "shared_town": "廣州",
        }
    )
    game = runtime.manager.games[result["game_id"]]
    attacker, _hu, tw = game.players

    assert result["shared_town"] == "廣州"
    assert attacker.hand == []
    assert (attacker.faction_id, attacker.base, attacker.organizations) == (
        "liberals",
        "上海",
        {"上海": 1},
    )
    assert tw.faction_id == "taiwan_blue"
    assert tw.organizations == {"廣州": 1, "臺北": 1}


def test_main_shared_dissolve_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-shared-dissolve", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_shared_dissolve({"attacker_no_hand": True})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_shared_dissolve)


def test_shared_dissolve_uuid_order_is_stable(monkeypatch):
    from server.test_routes import shared_dissolve

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(shared_dissolve.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = SharedDissolveTestRoutes(
        lambda: runtime
    ).test_setup_shared_dissolve({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:4]]


def test_shared_dissolve_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-shared-dissolve", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "shared_town",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    assert client.post("/test/setup-shared-dissolve").status_code == 422
    list_response = client.post("/test/setup-shared-dissolve", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-shared-dissolve"]["post"]
    assert operation["summary"] == "Test Setup Shared Dissolve"
    assert operation["operationId"].startswith("test_setup_shared_dissolve_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-shared-dissolve"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-shared-dissolve")
    assert paths[index - 1] == "/test/setup-hu-taiwan-shared"
    assert paths[index + 1] == "/test/setup-india-support-purchase"
