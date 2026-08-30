import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.spy import SpyTestRoutes


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
    routes = SpyTestRoutes(provider)
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


def test_spy_default_card_default_state_and_lobby_registration():
    runtime = _runtime()
    result = SpyTestRoutes(lambda: runtime).test_setup_spy_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "enemy_id",
        "card_name",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    player, enemy = game.players

    assert result["success"] is True
    assert result["player_id"] == player.id
    assert result["enemy_id"] == enemy.id
    assert result["card_name"] == "派遣間諜"

    assert (player.faction_id, player.base, player.organizations) == (
        "red_army",
        "北京",
        {"北京": 1, "上海": 1},
    )
    assert player.resources == {"money": 0, "propaganda": 0}
    assert len(player.hand) == 1
    assert player.hand[0].name == "派遣間諜"
    assert player.hand[0].resources == {"propaganda": 1}
    assert player.deck.draw_pile == []
    assert player.deck.discard_pile == []

    assert (enemy.faction_id, enemy.base, enemy.organizations) == (
        "taiwan_green",
        "臺北",
        {"天津": 1, "杭州": 1, "香港城": 1},
    )
    assert enemy.resources == {"money": 0, "propaganda": 0}
    assert [card.name for card in enemy.hand] == ["對手手牌1", "對手手牌2"]
    assert enemy.deck.draw_pile == []
    assert enemy.deck.discard_pile == []

    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert result["players"] == [
        {"id": p.id, "name": p.name, "faction": p.faction_id, "base": p.base}
        for p in game.players
    ]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == player.id
    assert runtime.lobby_factions[game_id] == {
        player.id: "red_army",
        enemy.id: "taiwan_green",
    }
    assert runtime.lobby_bases[game_id] == {player.id: "北京", enemy.id: "臺北"}


def test_spy_inner_response_card_uses_its_own_defaults():
    runtime = _runtime()
    result = SpyTestRoutes(lambda: runtime).test_setup_spy_proof(
        {"card_name": "內應間諜"}
    )
    game = runtime.manager.games[result["game_id"]]
    player, enemy = game.players

    assert result["card_name"] == "內應間諜"
    assert player.organizations == {"北京": 1}
    assert enemy.organizations == {"天津": 1, "香港城": 1}
    assert player.hand[0].resources == {"propaganda": 2}


def test_spy_unsupported_card_name_returns_error_without_side_effects():
    runtime = _runtime()
    result = SpyTestRoutes(lambda: runtime).test_setup_spy_proof(
        {"card_name": "不支援的牌"}
    )

    assert result == {"error": "Unsupported spy card"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_spy_custom_payload_overrides():
    runtime = _runtime()
    result = SpyTestRoutes(lambda: runtime).test_setup_spy_proof(
        {
            "player_name": "我方",
            "enemy_name": "對手",
            "faction_id": "liberals",
            "base": "上海",
            "enemy_faction_id": "hong_kong",
            "enemy_base": "香港城",
            "orgs": {"上海": 2},
            "enemy_orgs": {"香港城": 3},
        }
    )
    game = runtime.manager.games[result["game_id"]]
    player, enemy = game.players

    assert (player.name, enemy.name) == ("我方", "對手")
    assert (player.faction_id, player.base, player.organizations) == (
        "liberals",
        "上海",
        {"上海": 2},
    )
    assert (enemy.faction_id, enemy.base, enemy.organizations) == (
        "hong_kong",
        "香港城",
        {"香港城": 3},
    )


def test_main_spy_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-spy-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_spy_proof({"card_name": "內應間諜"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_spy_proof)


def test_spy_uuid_order_is_stable(monkeypatch):
    from server.test_routes import spy

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(spy.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = SpyTestRoutes(lambda: runtime).test_setup_spy_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_spy_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-spy-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "enemy_id",
        "card_name",
        "players",
        "state",
    }
    assert client.post("/test/setup-spy-proof").status_code == 422
    list_response = client.post("/test/setup-spy-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-spy-proof"]["post"]
    assert operation["summary"] == "Test Setup Spy Proof"
    assert operation["operationId"].startswith("test_setup_spy_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-spy-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-spy-proof")
    assert paths[index - 1] == "/test/setup-red-army-abilities-proof"
    assert paths[index + 1] == "/test/setup-victory-proof"
