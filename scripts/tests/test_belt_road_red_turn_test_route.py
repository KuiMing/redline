import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.belt_road_red_turn import BeltRoadRedTurnTestRoutes
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


def _make_app(runtime_provider, broadcaster_provider):
    routes = BeltRoadRedTurnTestRoutes(runtime_provider, broadcaster_provider)
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


@pytest.mark.anyio
async def test_belt_road_red_turn_creates_new_game_when_no_game_id():
    runtime = _runtime()
    broadcasts = []

    async def fake_broadcast(game_id, game):
        broadcasts.append((game_id, game))

    routes = BeltRoadRedTurnTestRoutes(lambda: runtime, lambda: fake_broadcast)
    result = await routes.test_setup_belt_road_red_turn_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "event_name",
        "draw_result",
        "advance_results",
        "initial_state",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["red_player_id"] == red.id
    assert result["event_name"] == "一帶一路 南洋"
    assert result["url"] == f"/?game_id={game_id}&player_id={red.id}"
    assert result["advance_results"] == []

    assert viewer.name == "BEN"
    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "臺北",
        {"臺北": 1},
    )
    assert [card.name for card in viewer.hand] == ["BEN 保留手牌"]
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == ["紅軍保留手牌"]

    assert game.pending_base_choices == {}
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 0
    assert game.round_start_player_index == 0
    assert [event["name"] for event in game.event_deck.draw_pile] == []
    assert game.current_event["name"] == "一帶一路 南洋"

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "liberals", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "臺北", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {viewer.id: True, red.id: True}

    # No broadcast fires when a fresh game is created (no requested game_id).
    assert broadcasts == []


@pytest.mark.anyio
async def test_belt_road_red_turn_advance_to_red_and_broadcasts_on_reuse():
    runtime = _runtime()
    broadcasts = []

    async def fake_broadcast(game_id, game):
        broadcasts.append((game_id, game))

    routes = BeltRoadRedTurnTestRoutes(lambda: runtime, lambda: fake_broadcast)
    first = await routes.test_setup_belt_road_red_turn_proof({})

    second = await routes.test_setup_belt_road_red_turn_proof(
        {
            "game_id": first["game_id"],
            "player_id": first["player_id"],
            "red_player_id": first["red_player_id"],
            "advance_to_red": True,
        }
    )

    assert second["success"] is True
    assert second["game_id"] == first["game_id"]
    assert len(second["advance_results"]) == 2
    assert len(broadcasts) == 1
    assert broadcasts[0][0] == first["game_id"]

    game = runtime.manager.games[first["game_id"]]
    assert game.current_player_index == 1
    assert game.turn_phase == TurnPhase.ACTION


@pytest.mark.anyio
async def test_belt_road_red_turn_players_not_found_returns_error():
    runtime = _runtime()

    async def fake_broadcast(game_id, game):
        return None

    routes = BeltRoadRedTurnTestRoutes(lambda: runtime, lambda: fake_broadcast)
    first = await routes.test_setup_belt_road_red_turn_proof({})

    result = await routes.test_setup_belt_road_red_turn_proof(
        {"game_id": first["game_id"], "player_id": "bad", "red_player_id": "also-bad"}
    )
    assert result == {"success": False, "error": "Formal proof players not found"}


@pytest.mark.anyio
async def test_belt_road_red_turn_wrong_seats_returns_error():
    runtime = _runtime()

    async def fake_broadcast(game_id, game):
        return None

    routes = BeltRoadRedTurnTestRoutes(lambda: runtime, lambda: fake_broadcast)
    first = await routes.test_setup_belt_road_red_turn_proof({})

    result = await routes.test_setup_belt_road_red_turn_proof(
        {
            "game_id": first["game_id"],
            "player_id": first["red_player_id"],
            "red_player_id": first["player_id"],
        }
    )
    assert result == {
        "success": False,
        "error": "Formal proof requires viewer seat 0 and red seat 1",
    }


def test_main_belt_road_red_turn_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-belt-road-red-turn-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    assert callable(main.test_setup_belt_road_red_turn_proof)


def test_belt_road_red_turn_http_openapi_and_route_order():
    runtime = _runtime()

    async def fake_broadcast(game_id, game):
        return None

    app = _make_app(lambda: runtime, lambda: fake_broadcast)
    client = TestClient(app)
    response = client.post("/test/setup-belt-road-red-turn-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "event_name",
        "draw_result",
        "advance_results",
        "initial_state",
        "url",
        "state",
    }
    assert client.post("/test/setup-belt-road-red-turn-proof").status_code == 422
    list_response = client.post("/test/setup-belt-road-red-turn-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-belt-road-red-turn-proof"]["post"]
    assert operation["summary"] == "Test Setup Belt Road Red Turn Proof"
    assert operation["operationId"].startswith("test_setup_belt_road_red_turn_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-belt-road-red-turn-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-belt-road-red-turn-proof")
    assert paths[index - 1] == "/test/setup-elite-defection-event-proof"
    assert paths[index + 1] == "/test/setup-tibet-era-red-build-proof"
