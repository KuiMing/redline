import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.hong_kong_era_red_discard import HongKongEraRedDiscardTestRoutes
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
        lobby_ready={},
    )


def _make_app(provider):
    routes = HongKongEraRedDiscardTestRoutes(provider)
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


def test_hong_kong_era_red_discard_default_state_and_lobby_registration():
    runtime = _runtime()
    result = HongKongEraRedDiscardTestRoutes(
        lambda: runtime
    ).test_setup_hong_kong_era_red_discard_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "hong_kong_player_id",
        "target_town",
        "red_url",
        "hong_kong_url",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    actor, red = game.players

    assert result["success"] is True
    assert result["player_id"] == red.id
    assert result["red_player_id"] == red.id
    assert result["hong_kong_player_id"] == actor.id
    assert result["target_town"] == "天津"
    assert result["red_url"] == f"/?game_id={game_id}&player_id={red.id}"
    assert result["hong_kong_url"] == f"/?game_id={game_id}&player_id={actor.id}"
    assert result["url"] == result["red_url"]

    assert (actor.faction_id, actor.base, actor.organizations) == (
        "hong_kong",
        "香港城",
        {"天津": 1},
    )
    assert [card.name for card in actor.hand] == ["香港目標手牌", "香港保留手牌"]
    assert actor.deck.discard_pile == []
    assert actor.resources == {"money": 0, "propaganda": 0}

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == ["內應間諜"]
    assert red.deck.discard_pile == []
    assert red.resources == {"money": 0, "propaganda": 0}

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 1
    assert game.turn_phase == TurnPhase.ACTION
    assert game.era_notification is not None
    assert game.era_notification["id"] == "hong_kong"
    assert "runtime_effects" in game.era_notification

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {actor.id: "hong_kong", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {actor.id: "香港城", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {actor.id: True, red.id: True}


def test_main_hong_kong_era_red_discard_uses_rebound_runtime_and_callable(monkeypatch):
    manager = FakeManager()
    lobby = {}
    hosts = {}
    factions = {}
    bases = {}
    ready = {}
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "lobby", lobby)
    monkeypatch.setattr(main, "lobby_hosts", hosts)
    monkeypatch.setattr(main, "lobby_factions", factions)
    monkeypatch.setattr(main, "lobby_bases", bases)
    monkeypatch.setattr(main, "lobby_ready", ready)

    response = TestClient(main.app).post(
        "/test/setup-hong-kong-era-red-discard-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_hong_kong_era_red_discard_proof({})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_hong_kong_era_red_discard_proof)


def test_hong_kong_era_red_discard_first_two_uuids_are_the_players():
    runtime = _runtime()
    result = HongKongEraRedDiscardTestRoutes(
        lambda: runtime
    ).test_setup_hong_kong_era_red_discard_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["hong_kong_player_id"] == game.players[0].id
    assert result["red_player_id"] == game.players[1].id
    assert result["game_id"] != game.players[0].id
    assert result["game_id"] != game.players[1].id


def test_hong_kong_era_red_discard_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-hong-kong-era-red-discard-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "hong_kong_player_id",
        "target_town",
        "red_url",
        "hong_kong_url",
        "url",
        "state",
    }
    assert (
        client.post("/test/setup-hong-kong-era-red-discard-proof").status_code == 422
    )
    list_response = client.post(
        "/test/setup-hong-kong-era-red-discard-proof", json=[]
    )
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"][
        "/test/setup-hong-kong-era-red-discard-proof"
    ]["post"]
    assert operation["summary"] == "Test Setup Hong Kong Era Red Discard Proof"
    assert operation["operationId"].startswith(
        "test_setup_hong_kong_era_red_discard_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-hong-kong-era-red-discard-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-hong-kong-era-red-discard-proof")
    assert paths[index - 1] == "/test/setup-era-notification-proof"
    assert paths[index + 1] == "/test/setup-uyghur-era-red-dissolve-proof"
