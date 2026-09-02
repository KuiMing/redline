import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.ccdi_choice import CcdiChoiceTestRoutes
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
    routes = CcdiChoiceTestRoutes(provider)
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


def test_ccdi_choice_default_state_and_lobby_registration():
    runtime = _runtime()
    result = CcdiChoiceTestRoutes(lambda: runtime).test_setup_ccdi_choice({})

    assert set(result) == {"success", "game_id", "player_id", "url", "state"}
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    red, opp = game.players

    assert result["success"] is True
    assert result["player_id"] == red.id
    assert result["url"] == f"/?game_id={game_id}&player_id={red.id}"

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == ["手牌甲", "手牌乙", "手牌丙"]
    assert (opp.faction_id, opp.base, opp.organizations) == (
        "liberals",
        "臺北",
        {"臺北": 1},
    )

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.pending_choice is not None
    assert game.pending_choice["type"] == "multi_card_choice"
    assert game.pending_choice["choice_key"] == "red_army_ccdi_discard_draw"
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == red.id
    assert runtime.lobby_factions[game_id] == {red.id: "red_army", opp.id: "liberals"}
    assert runtime.lobby_bases[game_id] == {red.id: "北京", opp.id: "臺北"}
    assert runtime.lobby_ready[game_id] == {red.id: True, opp.id: True}


def test_main_ccdi_choice_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-ccdi-choice", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_ccdi_choice({})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_ccdi_choice)


def test_ccdi_choice_first_two_uuids_are_the_players_and_game_id_set():
    runtime = _runtime()
    result = CcdiChoiceTestRoutes(lambda: runtime).test_setup_ccdi_choice({})
    game = runtime.manager.games[result["game_id"]]

    assert result["player_id"] == game.players[0].id
    assert game.id == result["game_id"]


def test_ccdi_choice_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-ccdi-choice", json={})
    assert response.status_code == 200
    assert set(response.json()) == {"success", "game_id", "player_id", "url", "state"}
    assert client.post("/test/setup-ccdi-choice").status_code == 422
    list_response = client.post("/test/setup-ccdi-choice", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-ccdi-choice"]["post"]
    assert operation["summary"] == "Test Setup Ccdi Choice"
    assert operation["operationId"].startswith("test_setup_ccdi_choice_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-ccdi-choice"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-ccdi-choice")
    assert paths[index - 1] == "/test/setup-discard-topdeck-choice"
    assert paths[index + 1] == "/test/setup-elite-defection-event-proof"
