import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.underground_party import UndergroundPartyTestRoutes


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
    routes = UndergroundPartyTestRoutes(provider)
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


def test_underground_party_default_state_and_lobby_registration():
    runtime = _runtime()
    result = UndergroundPartyTestRoutes(
        lambda: runtime
    ).test_setup_underground_party({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "purchase_draw_pile",
        "expected_reveal_order",
        "hand",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["hand"] == ["地下黨"]
    assert result["expected_reveal_order"] == ["宣傳家", "合作談判", "走漏風聲"]
    assert result["purchase_draw_pile"] == ["走漏風聲", "合作談判", "宣傳家"]

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "tibet_dehradun",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert viewer.resources == {"money": 4, "propaganda": 4}
    assert [card.name for card in viewer.hand] == ["地下黨"]
    assert [card.name for card in viewer.deck.draw_pile] == ["抽牌A", "抽牌B"]
    assert viewer.deck.discard_pile == []
    assert (red.faction_id, red.base, red.organizations, red.hand) == (
        "red_army",
        "北京",
        {"北京": 1},
        [],
    )
    assert [card.name for card in game.purchase_deck.draw_pile] == [
        "走漏風聲",
        "合作談判",
        "宣傳家",
    ]
    assert game.purchase_deck.discard_pile == []
    assert len(game.purchase_area) == 11
    assert [card.name for card in game.purchase_area[-5:]] == [
        "批鬥",
        "組織經驗甲",
        "組織經驗丙",
        "北國奧援",
        "模仿戰術",
    ]
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert (
        "UI proof setup: viewer has 地下黨; purchase deck top reveals 宣傳家 / 合作談判 / 走漏風聲."
        in game.action_log[-1]
    )

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "tibet_dehradun",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {viewer.id: "德拉敦", red.id: "北京"}


def test_underground_party_custom_candidate_order_and_unknown_card_fallback():
    runtime = _runtime()
    result = UndergroundPartyTestRoutes(
        lambda: runtime
    ).test_setup_underground_party(
        {"candidate_names": ["不存在的牌", "思想家"], "purchase_area_random": ["批鬥"]}
    )
    game = runtime.manager.games[result["game_id"]]

    assert result["expected_reveal_order"] == ["不存在的牌", "思想家"]
    assert result["purchase_draw_pile"] == ["思想家", "不存在的牌"]
    assert game.purchase_deck.draw_pile[-1].name == "不存在的牌"
    assert game.purchase_deck.draw_pile[-1].card_type == "command"
    assert len(game.purchase_area) == 7
    assert game.purchase_area[-1].name == "批鬥"


def test_main_underground_party_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-underground-party", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_underground_party({"candidate_names": ["思想家"]})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_underground_party)


def test_underground_party_uuid_order_is_stable(monkeypatch):
    from server.test_routes import underground_party

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(underground_party.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = UndergroundPartyTestRoutes(
        lambda: runtime
    ).test_setup_underground_party({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_underground_party_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-underground-party", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "purchase_draw_pile",
        "expected_reveal_order",
        "hand",
        "state",
    }
    assert client.post("/test/setup-underground-party").status_code == 422
    list_response = client.post("/test/setup-underground-party", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-underground-party"]["post"]
    assert operation["summary"] == "Test Setup Underground Party"
    assert operation["operationId"].startswith("test_setup_underground_party_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-underground-party"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-underground-party")
    assert paths[index - 1] == "/test/setup-remove-to-purchase"
    assert paths[index + 1] == "/test/setup-recruit-talent-proof"
