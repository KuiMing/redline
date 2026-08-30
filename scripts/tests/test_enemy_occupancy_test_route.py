import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.enemy_occupancy import EnemyOccupancyTestRoutes
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
    routes = EnemyOccupancyTestRoutes(provider)
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


def test_enemy_occupancy_default_state_and_lobby_registration():
    runtime = _runtime()
    result = EnemyOccupancyTestRoutes(
        lambda: runtime
    ).test_setup_enemy_occupancy_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "url",
        "state",
        "move_to_enemy_result",
        "card_build_choices",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    actor, red = game.players

    assert result["success"] is True
    assert result["player_id"] == actor.id
    assert result["red_player_id"] == red.id
    assert result["url"] == f"/?game_id={game_id}&player_id={actor.id}"
    assert result["move_to_enemy_result"] is None
    assert result["card_build_choices"] == [
        {"town": "宜蘭"},
        {"town": "新北"},
        {"town": "臺北"},
    ]

    assert (actor.faction_id, actor.base, actor.organizations, actor.moves_left) == (
        "taiwan_green",
        "臺北",
        {"桃園": 1},
        1,
    )
    assert actor.resources == {"money": 0, "propaganda": 0}
    assert [card.name for card in actor.hand] == ["宣傳家"]
    assert (red.faction_id, red.base, red.organizations, red.hand) == (
        "red_army",
        "北京",
        {"新竹": 1},
        [],
    )
    assert game.current_player_index == 0
    assert game.round_start_player_index == 0
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {actor.id: "taiwan_green", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {actor.id: "臺北", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {actor.id: True, red.id: True}


def test_enemy_occupancy_probe_move_returns_blocked_error():
    runtime = _runtime()
    result = EnemyOccupancyTestRoutes(
        lambda: runtime
    ).test_setup_enemy_occupancy_proof({"probe_move": True})

    assert result["move_to_enemy_result"] == {"error": "Cannot move into occupied town"}


def test_enemy_occupancy_custom_payload_overrides():
    runtime = _runtime()
    result = EnemyOccupancyTestRoutes(
        lambda: runtime
    ).test_setup_enemy_occupancy_proof(
        {
            "actor_faction": "liberals",
            "actor_base": "香港城",
            "actor_town": "新北",
            "red_town": "宜蘭",
            "moves_left": "5",
        }
    )
    game = runtime.manager.games[result["game_id"]]
    actor, red = game.players

    assert (actor.faction_id, actor.base, actor.organizations, actor.moves_left) == (
        "liberals",
        "香港城",
        {"新北": 1},
        5,
    )
    assert red.organizations == {"宜蘭": 1}


def test_main_enemy_occupancy_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-enemy-occupancy-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_enemy_occupancy_proof({"moves_left": 2})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_enemy_occupancy_proof)


def test_enemy_occupancy_uuid_order_is_stable(monkeypatch):
    from server.test_routes import enemy_occupancy

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(enemy_occupancy.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = EnemyOccupancyTestRoutes(
        lambda: runtime
    ).test_setup_enemy_occupancy_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_enemy_occupancy_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-enemy-occupancy-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "url",
        "state",
        "move_to_enemy_result",
        "card_build_choices",
    }
    assert client.post("/test/setup-enemy-occupancy-proof").status_code == 422
    list_response = client.post("/test/setup-enemy-occupancy-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-enemy-occupancy-proof"]["post"]
    assert operation["summary"] == "Test Setup Enemy Occupancy Proof"
    assert operation["operationId"].startswith("test_setup_enemy_occupancy_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-enemy-occupancy-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-enemy-occupancy-proof")
    assert paths[index - 1] == "/test/setup-pending-choice-board-guard"
    assert paths[index + 1] == "/test/setup-move-confirmation-proof"
