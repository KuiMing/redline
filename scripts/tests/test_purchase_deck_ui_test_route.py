import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.purchase_deck_ui import PurchaseDeckUiTestRoutes
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
    routes = PurchaseDeckUiTestRoutes(provider)
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


def test_purchase_deck_ui_default_state_and_lobby_registration():
    runtime = _runtime()
    result = PurchaseDeckUiTestRoutes(
        lambda: runtime
    ).test_setup_purchase_deck_ui({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["turn_phase"] == TurnPhase.ACTION
    assert result["game_phase"] == GamePhase.MAIN

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "tibet_dehradun",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert viewer.resources == {"money": 5, "propaganda": 5}
    assert viewer.hand == []
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert len(game.purchase_area) == 11
    assert [card.name for card in game.purchase_area[:6]] == [
        "宣傳家",
        "思想家",
        "資助者",
        "資本家",
        "分神",
        "內鬥",
    ]
    assert game.current_player_index == 0
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert result["players"] == [
        {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
    ]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "tibet_dehradun",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {viewer.id: "德拉敦", red.id: "北京"}


def test_purchase_deck_ui_pinned_random_slots_support_and_card_and_unknown():
    runtime = _runtime()
    result = PurchaseDeckUiTestRoutes(
        lambda: runtime
    ).test_setup_purchase_deck_ui(
        {"purchase_area_random": ["印度奧援", "思想家", "不存在的牌"]}
    )
    game = runtime.manager.games[result["game_id"]]

    assert len(game.purchase_area) == 11
    assert [card.name for card in game.purchase_area[:6]] == [
        "宣傳家",
        "思想家",
        "資助者",
        "資本家",
        "分神",
        "內鬥",
    ]
    pinned = game.purchase_area[6:9]
    assert [card.name for card in pinned] == ["印度奧援", "思想家", "不存在的牌"]
    assert pinned[2].card_type == "command"


def test_purchase_deck_ui_pinned_random_caps_at_five_slots():
    runtime = _runtime()
    result = PurchaseDeckUiTestRoutes(
        lambda: runtime
    ).test_setup_purchase_deck_ui(
        {"purchase_area_random": ["A", "B", "C", "D", "E", "F"]}
    )
    game = runtime.manager.games[result["game_id"]]

    assert [card.name for card in game.purchase_area[6:11]] == [
        "A",
        "B",
        "C",
        "D",
        "E",
    ]
    assert len(game.purchase_area) == 11


def test_main_purchase_deck_ui_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-purchase-deck-ui", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_purchase_deck_ui({"purchase_area_random": ["思想家"]})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_purchase_deck_ui)


def test_purchase_deck_ui_uuid_order_is_stable(monkeypatch):
    from server.test_routes import purchase_deck_ui

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(purchase_deck_ui.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = PurchaseDeckUiTestRoutes(
        lambda: runtime
    ).test_setup_purchase_deck_ui({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_purchase_deck_ui_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-purchase-deck-ui", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    assert client.post("/test/setup-purchase-deck-ui").status_code == 422
    list_response = client.post("/test/setup-purchase-deck-ui", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-purchase-deck-ui"]["post"]
    assert operation["summary"] == "Test Setup Purchase Deck Ui"
    assert operation["operationId"].startswith("test_setup_purchase_deck_ui_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-purchase-deck-ui"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-purchase-deck-ui")
    assert paths[index - 1] == "/test/setup-support-card-play"
    assert paths[index + 1] == "/test/setup-hand-preview"
