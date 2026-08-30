import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.safehouse_range import SafehouseRangeTestRoutes


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
    routes = SafehouseRangeTestRoutes(provider)
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


def test_safehouse_range_default_state_and_lobby_registration():
    runtime = _runtime()
    result = SafehouseRangeTestRoutes(
        lambda: runtime
    ).test_setup_safehouse_range_proof({})

    assert set(result) == {"success", "game_id", "player_id", "state"}
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, opponent = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "hong_kong",
        "臺北",
        {"臺北": 1},
    )
    assert viewer.hand == []
    assert viewer.deck.draw_pile == []
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
    assert game.current_event["name"] == "歲月靜好"
    assert game.event_progress == {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    assert game.event_modifiers == []
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "hong_kong", opponent.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "臺北", opponent.id: "北京"}


def test_safehouse_range_custom_base_and_card():
    runtime = _runtime()
    result = SafehouseRangeTestRoutes(
        lambda: runtime
    ).test_setup_safehouse_range_proof({"base": "香港城", "card": "組織經驗丙"})
    game = runtime.manager.games[result["game_id"]]
    viewer, _opponent = game.players

    assert (viewer.base, viewer.organizations) == ("香港城", {"香港城": 1})
    assert [card.name for card in viewer.hand] == ["組織經驗丙"]


def test_safehouse_range_unknown_card_returns_error_without_side_effects():
    runtime = _runtime()
    result = SafehouseRangeTestRoutes(
        lambda: runtime
    ).test_setup_safehouse_range_proof({"card": "no-such-card"})

    assert result == {"error": "找不到卡牌：no-such-card"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_main_safehouse_range_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-safehouse-range-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_safehouse_range_proof({"base": "香港城"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_safehouse_range_proof)


def test_safehouse_range_uuid_order_is_stable(monkeypatch):
    from server.test_routes import safehouse_range

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(safehouse_range.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = SafehouseRangeTestRoutes(
        lambda: runtime
    ).test_setup_safehouse_range_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_safehouse_range_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-safehouse-range-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {"success", "game_id", "player_id", "state"}
    assert client.post("/test/setup-safehouse-range-proof").status_code == 422
    list_response = client.post("/test/setup-safehouse-range-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-safehouse-range-proof"]["post"]
    assert operation["summary"] == "Test Setup Safehouse Range Proof"
    assert operation["operationId"].startswith("test_setup_safehouse_range_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-safehouse-range-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-safehouse-range-proof")
    assert paths[index - 1] == "/test/setup-peer-choice-notice-proof"
    assert paths[index + 1] == "/test/setup-era-restrict-ignore-distance-proof"
