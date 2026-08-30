import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.npc_inner_build import NpcInnerBuildTestRoutes
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
    routes = NpcInnerBuildTestRoutes(provider)
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


def test_npc_inner_build_default_state_and_lobby_registration():
    runtime = _runtime()
    result = NpcInnerBuildTestRoutes(
        lambda: runtime
    ).test_setup_national_people_congress_inner_build_proof({})

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
    assert result["event_name"] == "全國人大召開"
    assert result["url"] == f"/?game_id={game_id}&player_id={viewer.id}"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "taiwan_green",
        "臺北",
        {"臺北": 1, "南寧": 1, "廣州": 1},
    )
    assert [card.name for card in viewer.hand] == ["追隨者"]
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == ["追隨者"]

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.END
    assert game.turn_log["built_towns"] == ["南寧", "廣州"]
    assert game.current_event["name"] == "全國人大召開"
    assert game.event_progress == {
        "count": 0,
        "required": 1,
        "succeeded": False,
        "settled": False,
        "status": "active",
    }
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


def test_main_npc_inner_build_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-national-people-congress-inner-build-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_national_people_congress_inner_build_proof({})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_national_people_congress_inner_build_proof)


def test_npc_inner_build_first_two_uuids_are_the_players():
    runtime = _runtime()
    result = NpcInnerBuildTestRoutes(
        lambda: runtime
    ).test_setup_national_people_congress_inner_build_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["player_id"] == game.players[0].id
    assert result["red_player_id"] == game.players[1].id
    assert result["game_id"] != game.players[0].id
    assert result["game_id"] != game.players[1].id


def test_npc_inner_build_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post(
        "/test/setup-national-people-congress-inner-build-proof", json={}
    )
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
    assert (
        client.post(
            "/test/setup-national-people-congress-inner-build-proof"
        ).status_code
        == 422
    )
    list_response = client.post(
        "/test/setup-national-people-congress-inner-build-proof", json=[]
    )
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"][
        "/test/setup-national-people-congress-inner-build-proof"
    ]["post"]
    assert (
        operation["summary"]
        == "Test Setup National People Congress Inner Build Proof"
    )
    assert operation["operationId"].startswith(
        "test_setup_national_people_congress_inner_build_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None)
        == "/test/setup-national-people-congress-inner-build-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index(
        "/test/setup-national-people-congress-inner-build-proof"
    )
    assert (
        paths[index - 1]
        == "/test/setup-national-people-congress-red-dissolve-proof"
    )
    assert paths[index + 1] == "/test/setup-trade-war-event-proof"
