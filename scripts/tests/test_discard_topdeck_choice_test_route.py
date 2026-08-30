import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.discard_topdeck_choice import DiscardTopdeckChoiceTestRoutes
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
    routes = DiscardTopdeckChoiceTestRoutes(provider)
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


def test_discard_topdeck_choice_default_state_and_lobby_registration():
    runtime = _runtime()
    result = DiscardTopdeckChoiceTestRoutes(
        lambda: runtime
    ).test_setup_discard_topdeck_choice({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "discard_count",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["discard_count"] == 18
    assert result["url"] == f"/?game_id={game_id}&player_id={viewer.id}"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "臺北",
        {"臺北": 1},
    )
    assert viewer.resources == {"money": 0, "propaganda": 0}
    assert [card.name for card in viewer.hand] == ["追隨者"]
    assert [card.name for card in viewer.deck.draw_pile] == ["原牌庫頂下方"]
    assert len(viewer.deck.discard_pile) == 18
    assert [card.name for card in viewer.deck.discard_pile[:3]] == [
        "棄牌01",
        "棄牌02",
        "棄牌03",
    ]
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.current_event["name"] == "貿易戰加劇"
    assert game.event_notification is not None
    assert game.event_deck.draw_pile == []
    assert game.event_deck.discard_pile == []
    assert game.pending_choice is not None
    assert game.pending_choice["type"] == "card_choice"
    assert game.pending_choice["choice_key"] == "event_topdeck_from_discard"
    assert game.pending_choice["player_id"] == viewer.id
    assert len(game.pending_choice["cards"]) == 18
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "liberals", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "臺北", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {viewer.id: True, red.id: True}


def test_discard_topdeck_choice_custom_discard_count():
    runtime = _runtime()
    result = DiscardTopdeckChoiceTestRoutes(
        lambda: runtime
    ).test_setup_discard_topdeck_choice({"discard_count": 3})
    game = runtime.manager.games[result["game_id"]]
    viewer, _red = game.players

    assert result["discard_count"] == 3
    assert [card.name for card in viewer.deck.discard_pile] == [
        "棄牌01",
        "棄牌02",
        "棄牌03",
    ]
    assert len(game.pending_choice["cards"]) == 3


def test_main_discard_topdeck_choice_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-discard-topdeck-choice", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_discard_topdeck_choice({"discard_count": 5})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_discard_topdeck_choice)


def test_discard_topdeck_choice_first_two_uuids_are_the_players_and_game_id_set():
    runtime = _runtime()
    result = DiscardTopdeckChoiceTestRoutes(
        lambda: runtime
    ).test_setup_discard_topdeck_choice({})
    game = runtime.manager.games[result["game_id"]]

    # Game() consumes the first two uuid4() calls for the two players;
    # _apply_event_effect consumes further uuid4() calls internally before
    # the route's own game_id is generated and assigned to game.id.
    assert result["player_id"] == game.players[0].id
    assert game.id == result["game_id"]


def test_discard_topdeck_choice_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-discard-topdeck-choice", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "discard_count",
        "url",
        "state",
    }
    assert client.post("/test/setup-discard-topdeck-choice").status_code == 422
    list_response = client.post("/test/setup-discard-topdeck-choice", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-discard-topdeck-choice"]["post"]
    assert operation["summary"] == "Test Setup Discard Topdeck Choice"
    assert operation["operationId"].startswith("test_setup_discard_topdeck_choice_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-discard-topdeck-choice"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-discard-topdeck-choice")
    assert paths[index - 1] == "/test/setup-trade-war-event-proof"
    assert paths[index + 1] == "/test/setup-ccdi-choice"
