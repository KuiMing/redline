import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.support_card_play import SupportCardPlayTestRoutes


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
    routes = SupportCardPlayTestRoutes(provider)
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


def test_support_card_play_default_state_and_lobby_registration():
    runtime = _runtime()
    result = SupportCardPlayTestRoutes(
        lambda: runtime
    ).test_setup_support_card_play({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "support_name",
        "turn_phase",
        "game_phase",
        "players",
        "support_tier",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    player, red = game.players

    assert result["success"] is True
    assert result["player_id"] == player.id
    assert result["red_player_id"] == red.id
    assert result["support_name"] == "印度奧援"
    assert result["turn_phase"] == TurnPhase.ACTION
    assert result["game_phase"] == GamePhase.MAIN
    assert result["support_tier"] == 3

    assert (player.faction_id, player.base, player.organizations) == (
        "tibet_dehradun",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert player.resources == {"money": 0, "propaganda": 0}
    assert len(player.hand) == 1
    assert [card.name for card in player.deck.draw_pile] == ["補牌A", "補牌B"]
    assert player.deck.discard_pile == []

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert red.hand == []
    assert [card.name for card in red.deck.draw_pile] == ["紅軍抽牌A"]
    assert red.deck.discard_pile == []

    assert game.purchase_area == []
    assert game.current_player_index == 0
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert result["players"] == [
        {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
    ]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == player.id
    assert runtime.lobby_factions[game_id] == {
        player.id: "tibet_dehradun",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {player.id: "德拉敦", red.id: "北京"}


def test_support_card_play_enemy_hand_names_and_distraction_supply():
    runtime = _runtime()
    result = SupportCardPlayTestRoutes(
        lambda: runtime
    ).test_setup_support_card_play(
        {
            "enemy_hand_names": ["反制A", "反制B"],
            "distraction_supply": 2,
        }
    )
    game = runtime.manager.games[result["game_id"]]
    _player, red = game.players

    assert [card.name for card in red.hand] == ["反制A", "反制B"]
    assert all(card.card_type == "reaction" for card in red.hand)
    assert game.static_purchase_supply["分神"] == 2


def test_support_card_play_unknown_mission_returns_error_without_side_effects():
    runtime = _runtime()
    result = SupportCardPlayTestRoutes(
        lambda: runtime
    ).test_setup_support_card_play({"mission_name": "no-such-mission"})

    assert result == {"error": "Unknown mission event: no-such-mission"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_support_card_play_known_mission_sets_event_state():
    runtime = _runtime()
    result = SupportCardPlayTestRoutes(
        lambda: runtime
    ).test_setup_support_card_play({"mission_name": "全國人大召開"})
    game = runtime.manager.games[result["game_id"]]

    assert game.current_event["name"] == "全國人大召開"
    assert game.event_progress == {
        "count": 0,
        "required": 1,
        "succeeded": False,
        "settled": False,
        "status": "active",
    }
    assert game.event_notification is not None


def test_main_support_card_play_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-support-card-play", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_support_card_play({"variant_index": 0})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_support_card_play)


def test_support_card_play_uuid_order_is_stable(monkeypatch):
    from server.test_routes import support_card_play

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(support_card_play.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = SupportCardPlayTestRoutes(
        lambda: runtime
    ).test_setup_support_card_play({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_support_card_play_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-support-card-play", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "support_name",
        "turn_phase",
        "game_phase",
        "players",
        "support_tier",
        "state",
    }
    assert client.post("/test/setup-support-card-play").status_code == 422
    list_response = client.post("/test/setup-support-card-play", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-support-card-play"]["post"]
    assert operation["summary"] == "Test Setup Support Card Play"
    assert operation["operationId"].startswith("test_setup_support_card_play_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-support-card-play"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-support-card-play")
    assert paths[index - 1] == "/test/setup-recruit-talent-proof"
    assert paths[index + 1] == "/test/setup-purchase-deck-ui"
