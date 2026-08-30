import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.show_strength_choice import ShowStrengthChoiceTestRoutes


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
    routes = ShowStrengthChoiceTestRoutes(provider)
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


def test_show_strength_choice_default_state_and_lobby_registration():
    runtime = _runtime()
    result = ShowStrengthChoiceTestRoutes(
        lambda: runtime
    ).test_setup_show_strength_choice_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "pending_choice",
        "resources",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    player, red = game.players

    assert result["success"] is True
    assert result["player_id"] == player.id
    assert result["resources"] == {"money": 0, "propaganda": 0}

    assert (player.faction_id, player.base, player.organizations) == (
        "manchuria",
        "東京",
        {"東京": 1},
    )
    assert player.resources == {"money": 0, "propaganda": 0}
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )

    assert game.current_player_index == 0
    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.ACTION
    assert game.pending_base_choices == {}
    assert game.turn_log["played_nonstarter_names"] == ["甲", "乙", "丙"]
    assert game.current_event is None
    assert game.event_progress == {}
    assert game.event_modifiers == []
    assert game.id == game_id

    assert result["pending_choice"] is not None
    assert result["pending_choice"]["type"] == "option_choice"
    assert result["pending_choice"]["choice_key"] == "show_strength_reward"
    assert result["pending_choice"]["player_id"] == player.id
    assert result["pending_choice"]["options"] == [
        {"label": "獲得 3 點宣傳"},
        {"label": "獲得 3 點資金"},
    ]
    assert game.pending_choice == result["pending_choice"]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == player.id
    assert runtime.lobby_factions[game_id] == {player.id: "manchuria", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {player.id: "東京", red.id: "北京"}


def test_main_show_strength_choice_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post(
        "/test/setup-show-strength-choice-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_show_strength_choice_proof({})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_show_strength_choice_proof)


def test_show_strength_choice_uuid_order_is_stable(monkeypatch):
    from server.test_routes import show_strength_choice

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(show_strength_choice.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = ShowStrengthChoiceTestRoutes(
        lambda: runtime
    ).test_setup_show_strength_choice_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_show_strength_choice_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-show-strength-choice-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "pending_choice",
        "resources",
    }
    assert client.post("/test/setup-show-strength-choice-proof").status_code == 422
    list_response = client.post("/test/setup-show-strength-choice-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-show-strength-choice-proof"][
        "post"
    ]
    assert operation["summary"] == "Test Setup Show Strength Choice Proof"
    assert operation["operationId"].startswith(
        "test_setup_show_strength_choice_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-show-strength-choice-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-show-strength-choice-proof")
    assert paths[index - 1] == "/test/setup-faction-action-used-proof"
    assert paths[index + 1] == "/test/setup-peer-choice-notice-proof"
