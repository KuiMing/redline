import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.red_support import RedSupportTestRoutes
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
    routes = RedSupportTestRoutes(provider)
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


def test_red_support_default_state_and_lobby_registration():
    runtime = _runtime()
    result = RedSupportTestRoutes(
        lambda: runtime
    ).test_setup_red_support_proof({})

    assert set(result) == {"success", "game_id", "player_id", "mode", "players", "state"}
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, target = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["mode"] == "resource"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert viewer.resources == {"money": 0, "propaganda": 0}
    assert len(viewer.hand) == 1
    assert viewer.deck.draw_pile == []
    assert viewer.deck.discard_pile == []

    assert (target.faction_id, target.base, target.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert target.resources == {"money": 0, "propaganda": 0}
    assert target.hand == []
    assert target.deck.draw_pile == []
    assert target.deck.discard_pile == []

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
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "liberals", target.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "德拉敦", target.id: "北京"}


def test_red_support_action_mode_populates_discard_pile():
    runtime = _runtime()
    result = RedSupportTestRoutes(
        lambda: runtime
    ).test_setup_red_support_proof({"mode": "action"})
    game = runtime.manager.games[result["game_id"]]
    viewer, _target = game.players

    assert result["mode"] == "action"
    assert [card.name for card in viewer.deck.discard_pile] == ["抽到展示牌"]


def test_red_support_actor_faction_red_army_swaps_bases_and_opponent():
    runtime = _runtime()
    result = RedSupportTestRoutes(
        lambda: runtime
    ).test_setup_red_support_proof({"actor_faction": "red_army"})
    game = runtime.manager.games[result["game_id"]]
    viewer, target = game.players

    assert (viewer.faction_id, viewer.base) == ("red_army", "北京")
    assert (target.faction_id, target.base) == ("liberals", "香港城")


def test_red_support_explicit_opponent_faction_override():
    runtime = _runtime()
    result = RedSupportTestRoutes(
        lambda: runtime
    ).test_setup_red_support_proof(
        {"actor_faction": "hong_kong", "opponent_faction": "mongol"}
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, target = game.players

    assert viewer.faction_id == "hong_kong"
    assert target.faction_id == "mongol"
    assert target.base == "香港城"


def test_main_red_support_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-red-support-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_red_support_proof({"mode": "action"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_red_support_proof)


def test_red_support_uuid_order_is_stable(monkeypatch):
    from server.test_routes import red_support

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(red_support.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = RedSupportTestRoutes(
        lambda: runtime
    ).test_setup_red_support_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_red_support_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-red-support-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "mode",
        "players",
        "state",
    }
    assert client.post("/test/setup-red-support-proof").status_code == 422
    list_response = client.post("/test/setup-red-support-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-red-support-proof"]["post"]
    assert operation["summary"] == "Test Setup Red Support Proof"
    assert operation["operationId"].startswith("test_setup_red_support_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-red-support-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-red-support-proof")
    assert paths[index - 1] == "/test/setup-trash-choice-ui"
    assert paths[index + 1] == "/test/setup-red-army-abilities-proof"
