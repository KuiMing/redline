import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.faction_action_used import FactionActionUsedTestRoutes
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
    routes = FactionActionUsedTestRoutes(provider)
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


def test_faction_action_used_default_state_and_lobby_registration():
    runtime = _runtime()
    result = FactionActionUsedTestRoutes(
        lambda: runtime
    ).test_setup_faction_action_used_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "resource_card_name",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, opponent = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["resource_card_name"] == "領導"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "aomen",
        "澳門城",
        {"澳門城": 1},
    )
    assert viewer.resources == {"money": 0, "propaganda": 0}
    assert [card.name for card in viewer.hand] == ["領導"]
    assert [card.name for card in viewer.deck.draw_pile] == ["補牌1", "補牌2"]
    assert viewer.deck.discard_pile == []

    assert (opponent.faction_id, opponent.base, opponent.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert opponent.hand == []

    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.current_event["name"] == "歲月靜好"
    assert game.event_progress == {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    assert game.event_modifiers == []
    assert game.turn_log["faction_action_used"] is True
    assert game.id == game_id
    assert (
        "UI proof setup: viewer already used this turn's faction action (aomen)."
        in game.action_log[-1]
    )

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "aomen", opponent.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "澳門城", opponent.id: "北京"}


def test_faction_action_used_custom_payload_overrides():
    runtime = _runtime()
    result = FactionActionUsedTestRoutes(
        lambda: runtime
    ).test_setup_faction_action_used_proof(
        {
            "faction_id": "gambler",
            "base": "拉斯維加斯",
            "resource_card_name": "宣傳家",
            "faction_action_used": False,
            "draw_pile": ["自訂補牌"],
        }
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, _opponent = game.players

    assert result["resource_card_name"] == "宣傳家"
    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "gambler",
        "拉斯維加斯",
        {"拉斯維加斯": 1},
    )
    assert [card.name for card in viewer.hand] == ["宣傳家"]
    assert [card.name for card in viewer.deck.draw_pile] == ["自訂補牌"]
    assert game.turn_log["faction_action_used"] is False
    assert "(gambler)" in game.action_log[-1]


def test_main_faction_action_used_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-faction-action-used-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_faction_action_used_proof({"faction_action_used": False})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_faction_action_used_proof)


def test_faction_action_used_uuid_order_is_stable(monkeypatch):
    from server.test_routes import faction_action_used

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(faction_action_used.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = FactionActionUsedTestRoutes(
        lambda: runtime
    ).test_setup_faction_action_used_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_faction_action_used_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-faction-action-used-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "resource_card_name",
        "state",
    }
    assert client.post("/test/setup-faction-action-used-proof").status_code == 422
    list_response = client.post("/test/setup-faction-action-used-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-faction-action-used-proof"]["post"]
    assert operation["summary"] == "Test Setup Faction Action Used Proof"
    assert operation["operationId"].startswith("test_setup_faction_action_used_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-faction-action-used-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-faction-action-used-proof")
    assert paths[index - 1] == "/test/setup-urumqi-event-proof"
    assert paths[index + 1] == "/test/setup-show-strength-choice-proof"
