import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.draw_privacy import DrawPrivacyTestRoutes
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
    routes = DrawPrivacyTestRoutes(runtime_provider, broadcaster_provider)
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
async def test_setup_then_trigger_draw_privacy_proof_broadcasts_and_draws():
    runtime = _runtime()
    broadcasts = []

    async def fake_broadcast(game_id, game):
        broadcasts.append((game_id, game))

    routes = DrawPrivacyTestRoutes(lambda: runtime, lambda: fake_broadcast)

    setup_result = routes.test_setup_draw_privacy_proof()
    assert set(setup_result) == {
        "success",
        "game_id",
        "red_player_id",
        "kazakh_player_id",
        "observer_player_id",
    }
    game_id = setup_result["game_id"]
    game = runtime.manager.games[game_id]
    red, kazakh, observer = game.players

    assert setup_result["success"] is True
    assert setup_result["red_player_id"] == red.id
    assert setup_result["kazakh_player_id"] == kazakh.id
    assert setup_result["observer_player_id"] == observer.id

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert (kazakh.faction_id, kazakh.base, kazakh.organizations) == (
        "kazakh",
        "阿拉木圖",
        {"阿拉木圖": 1},
    )
    assert (observer.faction_id, observer.base, observer.organizations) == (
        "hong_kong",
        "香港城",
        {"香港城": 1},
    )
    assert all(player.hand == [] for player in game.players)
    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.ACTION
    assert game.current_player_index == game.players.index(kazakh)
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.action_log == []
    assert game._action_log_visibility == []
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == red.id
    assert runtime.lobby_factions[game_id] == {
        red.id: "red_army",
        kazakh.id: "kazakh",
        observer.id: "hong_kong",
    }
    assert runtime.lobby_bases[game_id] == {
        red.id: "北京",
        kazakh.id: "阿拉木圖",
        observer.id: "香港城",
    }
    assert runtime.lobby_ready[game_id] == {p.id: True for p in game.players}

    trigger_result = await routes.test_trigger_draw_privacy_proof({"game_id": game_id})
    assert trigger_result == {"success": True, "draw_count": 2}
    assert [card.name for card in kazakh.hand] == ["追隨者", "樂捐者"]
    assert kazakh.deck.draw_pile == []
    assert len(broadcasts) == 1
    assert broadcasts[0] == (game_id, game)


@pytest.mark.anyio
async def test_trigger_draw_privacy_proof_missing_game_returns_error():
    runtime = _runtime()
    routes = DrawPrivacyTestRoutes(lambda: runtime, lambda: (lambda *a: None))

    result = await routes.test_trigger_draw_privacy_proof({"game_id": "does-not-exist"})
    assert result == {"error": "Game not found"}


@pytest.mark.anyio
async def test_trigger_draw_privacy_proof_missing_kazakh_returns_error():
    runtime = _runtime()
    routes = DrawPrivacyTestRoutes(lambda: runtime, lambda: (lambda *a: None))

    setup_result = routes.test_setup_draw_privacy_proof()
    game_id = setup_result["game_id"]
    game = runtime.manager.games[game_id]
    for player in game.players:
        player.faction_id = "red_army"

    result = await routes.test_trigger_draw_privacy_proof({"game_id": game_id})
    assert result == {"error": "Kazakh player not found"}


def test_main_draw_privacy_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-draw-privacy-proof")
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_draw_privacy_proof()
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_draw_privacy_proof)
    assert callable(main.test_trigger_draw_privacy_proof)


def test_draw_privacy_uuid_order_is_stable(monkeypatch):
    from server.test_routes import draw_privacy

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(draw_privacy.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    routes = DrawPrivacyTestRoutes(lambda: runtime, lambda: (lambda *a: None))
    result = routes.test_setup_draw_privacy_proof()
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:4]]


def test_draw_privacy_http_openapi_and_route_order():
    runtime = _runtime()

    async def fake_broadcast(game_id, game):
        return None

    app = _make_app(lambda: runtime, lambda: fake_broadcast)
    client = TestClient(app)
    response = client.post("/test/setup-draw-privacy-proof")
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "red_player_id",
        "kazakh_player_id",
        "observer_player_id",
    }

    trigger_response = client.post(
        "/test/trigger-draw-privacy-proof", json={"game_id": response.json()["game_id"]}
    )
    assert trigger_response.status_code == 200
    assert trigger_response.json() == {"success": True, "draw_count": 2}

    routes = list(_effective_app_routes())
    matching_setup = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-draw-privacy-proof"
    ]
    matching_trigger = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/trigger-draw-privacy-proof"
    ]
    assert len(matching_setup) == 1
    assert len(matching_trigger) == 1
    assert getattr(matching_setup[0], "methods", None) == {"POST"}
    assert getattr(matching_trigger[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-draw-privacy-proof")
    assert paths[index + 1] == "/test/trigger-draw-privacy-proof"
    assert paths[index - 1] == "/test/setup-victory-proof"
    assert paths[index + 2] == "/test/setup-elite-defection-discard-proof"
