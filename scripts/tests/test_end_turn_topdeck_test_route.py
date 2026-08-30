import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.end_turn_topdeck import EndTurnTopdeckTestRoutes
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
    routes = EndTurnTopdeckTestRoutes(provider)
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


def test_end_turn_topdeck_default_state_and_lobby_registration():
    runtime = _runtime()
    result = EndTurnTopdeckTestRoutes(
        lambda: runtime
    ).test_setup_end_turn_topdeck_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "card_name",
        "bought_cards",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["card_name"] == "行動預告"
    assert result["bought_cards"] == ["本回合購得牌"]

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "tibet_dehradun",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert viewer.resources == {"money": 0, "propaganda": 1}
    assert [card.name for card in viewer.hand] == ["Filler"]
    assert [card.name for card in viewer.deck.draw_pile] == [
        "補牌1",
        "補牌2",
        "補牌3",
        "補牌4",
        "補牌5",
    ]
    assert [card.name for card in viewer.deck.discard_pile] == ["本回合購得牌"]
    assert (red.faction_id, red.base, red.organizations, red.hand) == (
        "red_army",
        "北京",
        {"北京": 1},
        [],
    )
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert [card.name for card in game.turn_log["purchased_cards_this_turn"]] == [
        "本回合購得牌"
    ]
    assert game.turn_log["pending_topdeck_uses"] == 1
    assert (
        "UI proof setup: viewer already played 行動預告 (1 banked right); bought cards "
        "['本回合購得牌'] are in discard." in game.action_log[-1]
    )

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "tibet_dehradun",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {viewer.id: "德拉敦", red.id: "北京"}


def test_end_turn_topdeck_money_card_and_end_phase():
    runtime = _runtime()
    result = EndTurnTopdeckTestRoutes(
        lambda: runtime
    ).test_setup_end_turn_topdeck_proof(
        {"card_name": "行動募資", "phase": "end", "pending_topdeck_uses": 2}
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, _red = game.players

    assert game.turn_phase == TurnPhase.END
    assert viewer.resources == {"money": 2, "propaganda": 0}
    assert game.turn_log["pending_topdeck_uses"] == 2


def test_end_turn_topdeck_bought_cards_and_resources_overrides():
    runtime = _runtime()
    result = EndTurnTopdeckTestRoutes(
        lambda: runtime
    ).test_setup_end_turn_topdeck_proof(
        {
            "bought_cards": ["牌A", "牌B"],
            "resources": {"money": 5, "propaganda": 5},
            "extra_hand": ["手牌X"],
            "draw_pile": ["自訂補牌"],
        }
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, _red = game.players

    assert result["bought_cards"] == ["牌A", "牌B"]
    assert [card.name for card in viewer.deck.discard_pile] == ["牌A", "牌B"]
    assert viewer.resources == {"money": 5, "propaganda": 5}
    assert [card.name for card in viewer.hand] == ["手牌X"]
    assert [card.name for card in viewer.deck.draw_pile] == ["自訂補牌"]


def test_main_end_turn_topdeck_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-end-turn-topdeck-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_end_turn_topdeck_proof({"phase": "end"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_end_turn_topdeck_proof)


def test_end_turn_topdeck_uuid_order_is_stable(monkeypatch):
    from server.test_routes import end_turn_topdeck

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(end_turn_topdeck.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = EndTurnTopdeckTestRoutes(
        lambda: runtime
    ).test_setup_end_turn_topdeck_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_end_turn_topdeck_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-end-turn-topdeck-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "card_name",
        "bought_cards",
        "state",
    }
    assert client.post("/test/setup-end-turn-topdeck-proof").status_code == 422
    list_response = client.post("/test/setup-end-turn-topdeck-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-end-turn-topdeck-proof"]["post"]
    assert operation["summary"] == "Test Setup End Turn Topdeck Proof"
    assert operation["operationId"].startswith("test_setup_end_turn_topdeck_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-end-turn-topdeck-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-end-turn-topdeck-proof")
    assert paths[index - 1] == "/test/setup-hand-preview"
    assert paths[index + 1] == "/test/setup-business-network-transport-proof"
