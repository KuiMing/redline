import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.uyghur_era_red_dissolve import UyghurEraRedDissolveTestRoutes


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
    routes = UyghurEraRedDissolveTestRoutes(provider)
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


def test_uyghur_era_red_dissolve_default_state_and_lobby_registration():
    runtime = _runtime()
    result = UyghurEraRedDissolveTestRoutes(
        lambda: runtime
    ).test_setup_uyghur_era_red_dissolve_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "actor_player_id",
        "play_result",
        "discard_choice",
        "discard_result",
        "pending_choice",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    actor, red = game.players

    assert result["success"] is True
    assert result["player_id"] == red.id
    assert result["actor_player_id"] == actor.id
    assert result["url"] == f"/?game_id={game_id}&player_id={red.id}"

    assert (actor.faction_id, actor.base, actor.organizations) == (
        "uyghur_istanbul",
        "烏魯木齊",
        {"天津": 1},
    )
    # The resolved armed_target_discard choice moves the hand card into discard.
    assert [card.name for card in actor.deck.discard_pile] == ["維吾爾棄牌 UI proof"]
    assert actor.hand == []
    assert actor.resources == {"money": 0, "propaganda": 0}
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert red.resources == {"money": 0, "propaganda": 0}

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 1
    assert game.turn_phase == TurnPhase.ACTION

    assert result["play_result"] == {"success": True, "pending_choice": True}
    assert result["discard_choice"]["choice_key"] == "armed_target_discard"
    assert result["discard_result"]["success"] is True
    assert result["discard_result"]["discarded_card"] == "維吾爾棄牌 UI proof"
    assert result["discard_result"]["choice_key"] == "armed_target_discard"

    assert result["pending_choice"] is not None
    assert result["pending_choice"]["type"] == "target_choice"
    assert result["pending_choice"]["choice_key"] == "era_red_bonus_dissolve_target"
    assert result["pending_choice"]["player_id"] == red.id
    assert game.pending_choice == result["pending_choice"]

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {
        actor.id: "uyghur_istanbul",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {actor.id: "烏魯木齊", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {actor.id: True, red.id: True}


def test_main_uyghur_era_red_dissolve_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-uyghur-era-red-dissolve-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_uyghur_era_red_dissolve_proof({})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_uyghur_era_red_dissolve_proof)


def test_uyghur_era_red_dissolve_first_two_uuids_are_the_players():
    runtime = _runtime()
    result = UyghurEraRedDissolveTestRoutes(
        lambda: runtime
    ).test_setup_uyghur_era_red_dissolve_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["actor_player_id"] == game.players[0].id
    assert result["player_id"] == game.players[1].id
    assert result["game_id"] != game.players[0].id
    assert result["game_id"] != game.players[1].id


def test_uyghur_era_red_dissolve_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-uyghur-era-red-dissolve-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "actor_player_id",
        "play_result",
        "discard_choice",
        "discard_result",
        "pending_choice",
        "url",
        "state",
    }
    assert client.post("/test/setup-uyghur-era-red-dissolve-proof").status_code == 422
    list_response = client.post("/test/setup-uyghur-era-red-dissolve-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-uyghur-era-red-dissolve-proof"][
        "post"
    ]
    assert operation["summary"] == "Test Setup Uyghur Era Red Dissolve Proof"
    assert operation["operationId"].startswith(
        "test_setup_uyghur_era_red_dissolve_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-uyghur-era-red-dissolve-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-uyghur-era-red-dissolve-proof")
    assert paths[index - 1] == "/test/setup-hong-kong-era-red-discard-proof"
    assert paths[index + 1] == "/test/setup-urumqi-event-proof"
