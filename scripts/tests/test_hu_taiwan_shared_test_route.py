import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.hu_taiwan_shared import HuTaiwanSharedTestRoutes
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
    routes = HuTaiwanSharedTestRoutes(provider)
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


def test_hu_taiwan_shared_default_state_and_lobby_registration():
    runtime = _runtime()
    result = HuTaiwanSharedTestRoutes(
        lambda: runtime
    ).test_setup_hu_taiwan_shared({})

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
    hu, tw = game.players

    assert result["success"] is True
    assert result["player_id"] == hu.id
    assert result["shared_town"] == "上海"
    assert result["turn_phase"] == TurnPhase.ACTION
    assert result["game_phase"] == GamePhase.MAIN

    assert (hu.faction_id, hu.base, hu.organizations, hu.hand, hu.moves_left) == (
        "hu",
        "紐約",
        {"紐約": 1},
        [],
        0,
    )
    assert (tw.faction_id, tw.base, tw.organizations, tw.hand) == (
        "taiwan_green",
        "臺北",
        {"上海": 1, "臺北": 1},
        [],
    )
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
    assert runtime.lobby_hosts[game_id] == hu.id
    assert runtime.lobby_factions[game_id] == {hu.id: "hu", tw.id: "taiwan_green"}
    assert runtime.lobby_bases[game_id] == {hu.id: "紐約", tw.id: "臺北"}


def test_hu_taiwan_shared_custom_payload_overrides():
    runtime = _runtime()
    result = HuTaiwanSharedTestRoutes(
        lambda: runtime
    ).test_setup_hu_taiwan_shared(
        {"hu_base": "倫敦", "tw_base": "高雄", "shared_town": "廣州"}
    )
    game = runtime.manager.games[result["game_id"]]
    hu, tw = game.players

    assert result["shared_town"] == "廣州"
    assert (hu.base, hu.organizations) == ("倫敦", {"倫敦": 1})
    assert (tw.base, tw.organizations) == ("高雄", {"廣州": 1, "高雄": 1})


def test_main_hu_taiwan_shared_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-hu-taiwan-shared", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_hu_taiwan_shared({"hu_base": "倫敦"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_hu_taiwan_shared)


def test_hu_taiwan_shared_uuid_order_is_stable(monkeypatch):
    from server.test_routes import hu_taiwan_shared

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(hu_taiwan_shared.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = HuTaiwanSharedTestRoutes(
        lambda: runtime
    ).test_setup_hu_taiwan_shared({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_hu_taiwan_shared_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-hu-taiwan-shared", json={})
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
    assert client.post("/test/setup-hu-taiwan-shared").status_code == 422
    list_response = client.post("/test/setup-hu-taiwan-shared", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-hu-taiwan-shared"]["post"]
    assert operation["summary"] == "Test Setup Hu Taiwan Shared"
    assert operation["operationId"].startswith("test_setup_hu_taiwan_shared_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-hu-taiwan-shared"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-hu-taiwan-shared")
    assert paths[index - 1] == "/test/setup-destroyed-red-base-marker-proof"
    assert paths[index + 1] == "/test/setup-shared-dissolve"
