import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.red_army_abilities import RedArmyAbilitiesTestRoutes
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
    routes = RedArmyAbilitiesTestRoutes(provider)
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


def test_red_army_abilities_default_state_and_lobby_registration():
    runtime = _runtime()
    result = RedArmyAbilitiesTestRoutes(
        lambda: runtime
    ).test_setup_red_army_abilities_proof()

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "target_player_id",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    red, liberals, hong_kong = game.players

    assert result["success"] is True
    assert (red.id, red.name) == ("red-proof", "紅軍")
    assert result["player_id"] == "red-proof"
    assert result["target_player_id"] == "lib-proof"

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == ["手牌甲", "手牌乙"]
    assert [card.name for card in red.deck.draw_pile] == ["補牌甲", "補牌乙", "補牌丙"]
    assert red.deck.discard_pile == []

    assert (liberals.id, liberals.faction_id, liberals.base, liberals.organizations) == (
        "lib-proof",
        "liberals",
        "香港城",
        {"天津": 1},
    )
    assert liberals.deck.draw_pile == []
    assert liberals.deck.discard_pile == []

    assert (hong_kong.id, hong_kong.faction_id, hong_kong.base, hong_kong.organizations) == (
        "hk-proof",
        "hong_kong",
        "香港城",
        {"上海": 1},
    )

    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id
    assert result["players"] == [
        {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
    ]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == "red-proof"
    assert runtime.lobby_factions[game_id] == {
        "red-proof": "red_army",
        "lib-proof": "liberals",
        "hk-proof": "hong_kong",
    }
    assert runtime.lobby_bases[game_id] == {
        "red-proof": "北京",
        "lib-proof": "香港城",
        "hk-proof": "香港城",
    }


def test_red_army_abilities_none_payload_behaves_like_empty_dict():
    runtime = _runtime()
    result = RedArmyAbilitiesTestRoutes(
        lambda: runtime
    ).test_setup_red_army_abilities_proof(None)
    game = runtime.manager.games[result["game_id"]]
    red, _liberals, _hk = game.players

    assert [card.name for card in red.hand] == ["手牌甲", "手牌乙"]


def test_red_army_abilities_empty_actions_clears_hands_and_supply():
    runtime = _runtime()
    result = RedArmyAbilitiesTestRoutes(
        lambda: runtime
    ).test_setup_red_army_abilities_proof({"empty_actions": True})
    game = runtime.manager.games[result["game_id"]]
    red, liberals, hong_kong = game.players

    assert red.hand == []
    assert red.deck.draw_pile == []
    assert red.deck.discard_pile == []
    assert liberals.hand == []
    assert liberals.organizations == {}
    assert hong_kong.hand == []
    assert hong_kong.organizations == {}
    assert game.static_purchase_supply["內鬥"] == 0
    assert game.static_purchase_supply["分神"] == 0


def test_main_red_army_abilities_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-red-army-abilities-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_red_army_abilities_proof({"empty_actions": True})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_red_army_abilities_proof)


def test_red_army_abilities_uuid_order_is_stable(monkeypatch):
    from server.test_routes import red_army_abilities

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(red_army_abilities.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = RedArmyAbilitiesTestRoutes(
        lambda: runtime
    ).test_setup_red_army_abilities_proof()

    assert result["game_id"] == str(ids[0])


def test_red_army_abilities_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-red-army-abilities-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "target_player_id",
        "players",
        "state",
    }
    no_body_response = client.post("/test/setup-red-army-abilities-proof")
    assert no_body_response.status_code == 200
    list_response = client.post("/test/setup-red-army-abilities-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-red-army-abilities-proof"]["post"]
    assert operation["summary"] == "Test Setup Red Army Abilities Proof"
    assert operation["operationId"].startswith("test_setup_red_army_abilities_proof_")

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-red-army-abilities-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-red-army-abilities-proof")
    assert paths[index - 1] == "/test/setup-red-support-proof"
    assert paths[index + 1] == "/test/setup-spy-proof"
