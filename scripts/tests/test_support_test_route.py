import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.support import SupportTestRoutes


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
    routes = SupportTestRoutes(provider)
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


def test_support_default_taiwan_card_state_and_lobby_registration():
    runtime = _runtime()
    result = SupportTestRoutes(lambda: runtime).test_setup_support_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "tier",
        "support_name",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    player, enemy = game.players

    assert result["success"] is True
    assert result["player_id"] == player.id
    assert result["tier"] == 2
    assert result["support_name"] == "臺灣奧援"

    assert (player.faction_id, player.base) == ("taiwan_green", "臺北")
    assert player.organizations == {"臺北": 1, "屏東": 1, "佬沃": 1, "馬祖": 1}
    assert player.resources == {"money": 0, "propaganda": 0}
    assert len(player.hand) == 1
    assert player.hand[0].name == "臺灣奧援"
    assert player.deck.draw_pile == []
    assert player.deck.discard_pile == []

    assert (enemy.faction_id, enemy.base) == ("red_army", "北京")
    assert enemy.organizations == {"北京": 1, "福州": 1}
    assert enemy.resources == {"money": 0, "propaganda": 0}
    assert enemy.hand == []

    assert game._support_card_tier(player, player.hand[0]) == (2, 0, ["東洋", "南洋"])

    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game._deferred_auto_event is False
    assert game.current_event["name"] == "歲月靜好"
    assert game.event_progress == {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    assert game.event_notification is not None
    assert game.event_modifiers == []
    assert game.id == game_id
    assert result["players"] == [
        {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
    ]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == player.id
    assert runtime.lobby_factions[game_id] == {
        player.id: "taiwan_green",
        enemy.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {player.id: "臺北", enemy.id: "北京"}


def test_support_northern_card_tier_1_and_custom_matched_regions():
    runtime = _runtime()
    result = SupportTestRoutes(lambda: runtime).test_setup_support_proof(
        {"support_name": "北國奧援", "tier": 1, "matched_regions": ["自訂區域"]}
    )
    game = runtime.manager.games[result["game_id"]]
    player, _enemy = game.players

    assert result["support_name"] == "北國奧援"
    assert result["tier"] == 1
    assert (player.faction_id, player.base) == ("liberals", "海參崴")
    assert player.organizations == {"巴黎": 1, "日內瓦": 1}
    assert game._support_card_tier(player, player.hand[0]) == (1, 0, ["自訂區域"])


def test_support_event_turn_phase_and_pending_choice_auto_resolve():
    runtime = _runtime()
    result = SupportTestRoutes(lambda: runtime).test_setup_support_proof(
        {"event_name": "全國人大召開", "turn_phase": "event"}
    )
    game = runtime.manager.games[result["game_id"]]

    assert game.turn_phase == TurnPhase.EVENT
    assert game.current_event["name"] == "全國人大召開"
    assert game.event_progress["status"] == "active"
    assert game.event_progress["required"] == 1


def test_support_unknown_event_returns_error_without_side_effects():
    runtime = _runtime()
    result = SupportTestRoutes(lambda: runtime).test_setup_support_proof(
        {"event_name": "no-such-event"}
    )

    assert result == {"error": "Unknown event: no-such-event"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_support_auto_resolve_target_index_plays_card():
    runtime = _runtime()
    result = SupportTestRoutes(lambda: runtime).test_setup_support_proof(
        {"auto_resolve_target_index": 0}
    )
    assert result["success"] is True
    game = runtime.manager.games[result["game_id"]]
    player, _enemy = game.players
    assert player.hand == []


def test_main_support_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-support-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_support_proof({"tier": 1})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_support_proof)


def test_support_uuid_order_is_stable(monkeypatch):
    from server.test_routes import support

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(support.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = SupportTestRoutes(lambda: runtime).test_setup_support_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_support_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-support-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "tier",
        "support_name",
        "players",
        "state",
    }
    assert client.post("/test/setup-support-proof").status_code == 422
    list_response = client.post("/test/setup-support-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-support-proof"]["post"]
    assert operation["summary"] == "Test Setup Support Proof"
    assert operation["operationId"].startswith("test_setup_support_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-support-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-support-proof")
    assert paths[index - 1] == "/test/setup-discard-reshuffle-proof"
    assert paths[index + 1] == "/test/setup-taiwan-support-proof"
