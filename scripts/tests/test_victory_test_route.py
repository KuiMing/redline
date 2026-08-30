import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.victory import VictoryTestRoutes


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
    routes = VictoryTestRoutes(provider)
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


def test_victory_default_state_and_lobby_registration():
    runtime = _runtime()
    result = VictoryTestRoutes(lambda: runtime).test_setup_victory_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "winner",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    green, red = game.players

    assert result["success"] is True
    assert result["player_id"] == green.id
    assert result["red_player_id"] == red.id
    assert result["winner"] == "GREEN"

    assert green.name == "GREEN"
    assert (green.faction_id, green.base, green.organizations) == (
        "taiwan_green",
        "臺北",
        {"臺北": 3, "桃園": 2},
    )
    assert green.resources == {"money": 2, "propaganda": 4}
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 5, "天津": 2},
    )
    assert red.resources == {"money": 1, "propaganda": 0}

    assert game.game_phase == GamePhase.FINISHED
    assert game.turn == 21
    assert game.winner == "GREEN"
    assert game.co_winners == []
    assert game.pending_base_choices == {}
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == green.id
    assert runtime.lobby_factions[game_id] == {
        green.id: "taiwan_green",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {green.id: "臺北", red.id: "北京"}


def test_victory_custom_winner_turn_and_co_winners():
    runtime = _runtime()
    result = VictoryTestRoutes(lambda: runtime).test_setup_victory_proof(
        {
            "winner_name": "自由臺灣",
            "winner": "red_army",
            "turn": 15,
            "co_winners": ["盟友甲"],
        }
    )
    game = runtime.manager.games[result["game_id"]]
    green, _red = game.players

    assert green.name == "自由臺灣"
    assert result["winner"] == "red_army"
    assert game.winner == "red_army"
    assert game.turn == 15
    assert game.co_winners == ["盟友甲"]


def test_main_victory_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-victory-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_victory_proof({"winner": "red_army"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_victory_proof)


def test_victory_uuid_order_is_stable(monkeypatch):
    from server.test_routes import victory

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(victory.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = VictoryTestRoutes(lambda: runtime).test_setup_victory_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_victory_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-victory-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "winner",
        "state",
    }
    assert client.post("/test/setup-victory-proof").status_code == 422
    list_response = client.post("/test/setup-victory-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-victory-proof"]["post"]
    assert operation["summary"] == "Test Setup Victory Proof"
    assert operation["operationId"].startswith("test_setup_victory_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-victory-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-victory-proof")
    assert paths[index - 1] == "/test/setup-spy-proof"
    assert paths[index + 1] == "/test/setup-draw-privacy-proof"
