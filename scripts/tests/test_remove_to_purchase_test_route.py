import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.remove_to_purchase import RemoveToPurchaseTestRoutes
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
    routes = RemoveToPurchaseTestRoutes(provider)
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


def test_remove_to_purchase_default_state_and_lobby_registration():
    runtime = _runtime()
    result = RemoveToPurchaseTestRoutes(
        lambda: runtime
    ).test_setup_remove_to_purchase({})

    assert set(result) == {
        "game_id",
        "player_id",
        "card_name",
        "purchase_area",
        "hand",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["player_id"] == viewer.id
    assert result["card_name"] == "宣傳家"
    assert result["hand"] == ["宣傳家"]
    assert len(result["purchase_area"]) == 11
    assert result["purchase_area"][:6] == [
        "宣傳家",
        "思想家",
        "資助者",
        "資本家",
        "分神",
        "內鬥",
    ]

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "tibet_dehradun",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert viewer.resources == {"money": 4, "propaganda": 3}
    assert [card.name for card in viewer.hand] == ["宣傳家"]
    assert (red.faction_id, red.base, red.organizations, red.hand) == (
        "red_army",
        "北京",
        {"北京": 1},
        [],
    )
    assert game.current_player_index == 0
    assert game.pending_base_choices == {}
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "tibet_dehradun",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {viewer.id: "德拉敦", red.id: "北京"}


def test_remove_to_purchase_unknown_card_name_falls_back_to_command_type():
    runtime = _runtime()
    result = RemoveToPurchaseTestRoutes(
        lambda: runtime
    ).test_setup_remove_to_purchase({"card_name": "不存在的牌"})
    game = runtime.manager.games[result["game_id"]]
    viewer, _red = game.players

    assert result["card_name"] == "不存在的牌"
    assert result["hand"] == ["不存在的牌"]
    assert viewer.hand[0].name == "不存在的牌"
    assert viewer.hand[0].card_type == "command"


def test_remove_to_purchase_custom_orgs_and_resources_overrides():
    runtime = _runtime()
    custom_orgs = {"上海": 2}
    custom_resources = {"money": 1, "propaganda": 9}
    result = RemoveToPurchaseTestRoutes(
        lambda: runtime
    ).test_setup_remove_to_purchase(
        {
            "faction_id": "liberals",
            "base": "上海",
            "orgs": custom_orgs,
            "resources": custom_resources,
        }
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, _red = game.players

    assert viewer.faction_id == "liberals"
    assert viewer.organizations == {"上海": 2}
    assert viewer.resources == {"money": 1, "propaganda": 9}


def test_main_remove_to_purchase_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-remove-to-purchase", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_remove_to_purchase({"card_name": "思想家"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_remove_to_purchase)


def test_remove_to_purchase_uuid_order_is_stable(monkeypatch):
    from server.test_routes import remove_to_purchase

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(remove_to_purchase.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = RemoveToPurchaseTestRoutes(
        lambda: runtime
    ).test_setup_remove_to_purchase({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_remove_to_purchase_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-remove-to-purchase", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "game_id",
        "player_id",
        "card_name",
        "purchase_area",
        "hand",
    }
    assert client.post("/test/setup-remove-to-purchase").status_code == 422
    list_response = client.post("/test/setup-remove-to-purchase", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-remove-to-purchase"]["post"]
    assert operation["summary"] == "Test Setup Remove To Purchase"
    assert operation["operationId"].startswith("test_setup_remove_to_purchase_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-remove-to-purchase"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-remove-to-purchase")
    assert paths[index - 1] == "/test/setup-india-support-purchase"
    assert paths[index + 1] == "/test/setup-underground-party"
