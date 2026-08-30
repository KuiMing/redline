import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.urumqi_event import UrumqiEventTestRoutes


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
    routes = UrumqiEventTestRoutes(provider)
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


def test_urumqi_event_default_state_settles_and_lobby_registration():
    runtime = _runtime()
    result = UrumqiEventTestRoutes(lambda: runtime).test_setup_urumqi_event_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "event_name",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["red_player_id"] == red.id
    assert result["event_name"] == "烏魯木齊七五事件"
    assert result["url"] == f"/?game_id={game_id}&player_id={viewer.id}"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "taiwan_green",
        "臺北",
        {"北京": 1},
    )
    assert viewer.resources == {"money": 0, "propaganda": 0}
    # advance_turn_phase() (triggered by the default settle=True) draws the
    # deck's remaining card straight into hand.
    assert [card.name for card in viewer.hand] == ["保留手牌", "牌庫保留"]
    assert viewer.deck.draw_pile == []
    assert viewer.deck.discard_pile == []
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.ACTION
    assert game.current_event["name"] == "烏魯木齊七五事件"
    assert game.event_progress["status"] == "active"
    assert game.event_progress["settlement_target_player_id"] == viewer.id
    assert game.event_notification is not None
    assert game.event_deck.draw_pile == []
    assert game.event_deck.discard_pile == []

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "taiwan_green",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {viewer.id: "臺北", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {viewer.id: True, red.id: True}


def test_urumqi_event_settle_false_leaves_progress_without_settlement_target():
    runtime = _runtime()
    result = UrumqiEventTestRoutes(lambda: runtime).test_setup_urumqi_event_proof(
        {"settle": False}
    )
    game = runtime.manager.games[result["game_id"]]

    assert "settlement_target_player_id" not in game.event_progress
    assert game.event_progress == {
        "count": 0,
        "required": 1,
        "succeeded": False,
        "settled": False,
        "status": "active",
    }


def test_main_urumqi_event_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-urumqi-event-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_urumqi_event_proof({"settle": False})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_urumqi_event_proof)


def test_urumqi_event_first_two_uuids_are_the_players():
    runtime = _runtime()
    result = UrumqiEventTestRoutes(lambda: runtime).test_setup_urumqi_event_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["player_id"] == game.players[0].id
    assert result["red_player_id"] == game.players[1].id
    assert result["game_id"] != game.players[0].id
    assert result["game_id"] != game.players[1].id


def test_urumqi_event_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-urumqi-event-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "event_name",
        "url",
        "state",
    }
    assert client.post("/test/setup-urumqi-event-proof").status_code == 422
    list_response = client.post("/test/setup-urumqi-event-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-urumqi-event-proof"]["post"]
    assert operation["summary"] == "Test Setup Urumqi Event Proof"
    assert operation["operationId"].startswith("test_setup_urumqi_event_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-urumqi-event-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-urumqi-event-proof")
    assert paths[index - 1] == "/test/setup-uyghur-era-red-dissolve-proof"
    assert paths[index + 1] == "/test/setup-faction-action-used-proof"
