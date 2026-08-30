import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.bait_exhaustion_ui import BaitExhaustionUiTestRoutes
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
    routes = BaitExhaustionUiTestRoutes(provider)
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


def test_bait_exhaustion_ui_default_state_and_lobby_registration():
    runtime = _runtime()
    result = BaitExhaustionUiTestRoutes(
        lambda: runtime
    ).test_setup_bait_exhaustion_ui({})

    assert set(result) == {"success", "game_id", "player_id", "state", "players"}
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["players"] == [
        {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
    ]

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert viewer.resources == {"money": 0, "propaganda": 0}
    assert [card.name for card in viewer.hand] == ["誘導虛耗", "可移除手牌"]
    assert [card.name for card in viewer.deck.draw_pile] == ["宣傳家"]
    assert viewer.deck.draw_pile[0].card_type == "propaganda"
    assert viewer.deck.discard_pile == []

    assert (red.faction_id, red.base, red.organizations) == (
        "hong_kong",
        "香港城",
        {"香港城": 1},
    )
    assert [card.name for card in red.hand] == ["對手被棄牌"]
    assert [card.name for card in red.deck.draw_pile] == ["對手抽牌A"]
    assert red.deck.discard_pile == []

    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "red_army", red.id: "hong_kong"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "北京", red.id: "香港城"}


def test_bait_exhaustion_ui_custom_payload_overrides():
    runtime = _runtime()
    result = BaitExhaustionUiTestRoutes(
        lambda: runtime
    ).test_setup_bait_exhaustion_ui(
        {
            "faction_id": "liberals",
            "base": "上海",
            "orgs": {"上海": 2},
            "resources": {"money": 3, "propaganda": 1},
            "draw_top_card": "思想家",
        }
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, _red = game.players

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "上海",
        {"上海": 2},
    )
    assert viewer.resources == {"money": 3, "propaganda": 1}
    assert [card.name for card in viewer.deck.draw_pile] == ["思想家"]


def test_main_bait_exhaustion_ui_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-bait-exhaustion-ui", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_bait_exhaustion_ui({"draw_top_card": "思想家"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_bait_exhaustion_ui)


def test_bait_exhaustion_ui_uuid_order_is_stable(monkeypatch):
    from server.test_routes import bait_exhaustion_ui

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(bait_exhaustion_ui.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = BaitExhaustionUiTestRoutes(
        lambda: runtime
    ).test_setup_bait_exhaustion_ui({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_bait_exhaustion_ui_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-bait-exhaustion-ui", json={})
    assert response.status_code == 200
    assert set(response.json()) == {"success", "game_id", "player_id", "state", "players"}
    assert client.post("/test/setup-bait-exhaustion-ui").status_code == 422
    list_response = client.post("/test/setup-bait-exhaustion-ui", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-bait-exhaustion-ui"]["post"]
    assert operation["summary"] == "Test Setup Bait Exhaustion Ui"
    assert operation["operationId"].startswith("test_setup_bait_exhaustion_ui_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-bait-exhaustion-ui"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-bait-exhaustion-ui")
    assert paths[index - 1] == "/test/setup-taiwan-support-proof"
    assert paths[index + 1] == "/test/setup-manchuria-era-reorder-proof"
