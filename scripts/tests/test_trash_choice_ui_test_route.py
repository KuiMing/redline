import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.trash_choice_ui import TrashChoiceUiTestRoutes


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
    routes = TrashChoiceUiTestRoutes(provider)
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


def test_trash_choice_ui_default_state_and_lobby_registration():
    runtime = _runtime()
    result = TrashChoiceUiTestRoutes(
        lambda: runtime
    ).test_setup_trash_choice_ui({})

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
    assert [card.name for card in viewer.hand] == ["思想家", "宣傳家"]
    assert [card.name for card in viewer.deck.discard_pile] == ["資本家", "樂捐者"]
    assert (red.faction_id, red.base, red.organizations) == (
        "hong_kong",
        "香港城",
        {"香港城": 1},
    )
    assert [card.name for card in red.hand] == ["追隨者"]
    assert red.deck.discard_pile == []
    assert len(game.purchase_area) == 11

    assert game.pending_choice["type"] == "card_choice"
    assert game.pending_choice["choice_key"] == "trash_from_hand_or_discard"
    assert game.pending_choice["player_id"] == viewer.id
    assert game.pending_choice["prompt"] == "批判：請從己方手牌或棄牌堆中移除 1 張牌。"
    assert game.pending_choice["source_name"] == "批判"
    assert game.pending_choice["count"] == 1
    assert [c["zone"] for c in game.pending_choice["cards"]] == [
        "hand",
        "hand",
        "discard",
        "discard",
    ]

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


def test_trash_choice_ui_count_above_one_uses_multi_card_choice():
    runtime = _runtime()
    result = TrashChoiceUiTestRoutes(
        lambda: runtime
    ).test_setup_trash_choice_ui({"count": 2, "source_name": "特別事件"})
    game = runtime.manager.games[result["game_id"]]

    assert game.pending_choice["type"] == "multi_card_choice"
    assert game.pending_choice["choice_key"] == "trash_from_hand_or_discard"
    assert game.pending_choice["count"] == 2
    assert game.pending_choice["source_name"] == "特別事件"
    assert game.pending_choice["prompt"] == "特別事件：請從己方手牌或棄牌堆中移除 2 張牌。"


def test_main_trash_choice_ui_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-trash-choice-ui", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_trash_choice_ui({"count": 2})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_trash_choice_ui)


def test_trash_choice_ui_uuid_order_is_stable(monkeypatch):
    from server.test_routes import trash_choice_ui

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(trash_choice_ui.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = TrashChoiceUiTestRoutes(
        lambda: runtime
    ).test_setup_trash_choice_ui({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_trash_choice_ui_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-trash-choice-ui", json={})
    assert response.status_code == 200
    assert set(response.json()) == {"success", "game_id", "player_id", "state", "players"}
    assert client.post("/test/setup-trash-choice-ui").status_code == 422
    list_response = client.post("/test/setup-trash-choice-ui", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-trash-choice-ui"]["post"]
    assert operation["summary"] == "Test Setup Trash Choice Ui"
    assert operation["operationId"].startswith("test_setup_trash_choice_ui_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-trash-choice-ui"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-trash-choice-ui")
    assert paths[index - 1] == "/test/setup-planning-lobby-ui"
    assert paths[index + 1] == "/test/setup-red-support-proof"
