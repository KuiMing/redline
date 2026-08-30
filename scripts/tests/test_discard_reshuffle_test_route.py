import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.discard_reshuffle import DiscardReshuffleTestRoutes
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
    routes = DiscardReshuffleTestRoutes(provider)
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


def test_discard_reshuffle_default_sufficient_scenario():
    runtime = _runtime()
    result = DiscardReshuffleTestRoutes(
        lambda: runtime
    ).test_setup_discard_reshuffle_proof({})

    assert set(result) == {
        "success",
        "scenario",
        "game_id",
        "player_id",
        "opponent_id",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    red, opponent = game.players

    assert result["success"] is True
    assert result["scenario"] == "sufficient"
    assert result["player_id"] == red.id
    assert result["opponent_id"] == opponent.id

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == [
        "保留手牌1",
        "保留手牌2",
        "保留手牌3",
        "保留手牌4",
    ]
    assert [card.name for card in red.deck.draw_pile] == ["牌庫保留牌"]
    assert [card.name for card in red.deck.discard_pile] == ["棄牌唯一一張"]
    assert red.resources == {"money": 0, "propaganda": 0}
    assert red.moves_left == 0

    assert (opponent.faction_id, opponent.base, opponent.organizations) == (
        "taiwan_green",
        "臺北",
        {"臺北": 1},
    )

    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.END
    assert game.current_player_index == 0
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game._deferred_auto_event is False
    assert game.current_event["name"] == "歲月靜好"
    assert game.event_progress == {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    assert game.event_modifiers == []
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(red.id, red.name), (opponent.id, opponent.name)]
    assert runtime.lobby_hosts[game_id] == red.id
    assert runtime.lobby_factions[game_id] == {
        red.id: "red_army",
        opponent.id: "taiwan_green",
    }
    assert runtime.lobby_bases[game_id] == {red.id: "北京", opponent.id: "臺北"}
    assert runtime.lobby_ready[game_id] == {red.id: True, opponent.id: True}


def test_discard_reshuffle_exhausted_scenario_empties_draw_pile():
    runtime = _runtime()
    result = DiscardReshuffleTestRoutes(
        lambda: runtime
    ).test_setup_discard_reshuffle_proof({"scenario": "exhausted"})
    game = runtime.manager.games[result["game_id"]]
    red, _opponent = game.players

    assert result["scenario"] == "exhausted"
    assert red.deck.draw_pile == []
    assert [card.name for card in red.deck.discard_pile] == ["棄牌唯一一張"]


def test_discard_reshuffle_invalid_scenario_returns_error_without_side_effects():
    runtime = _runtime()
    result = DiscardReshuffleTestRoutes(
        lambda: runtime
    ).test_setup_discard_reshuffle_proof({"scenario": "bogus"})

    assert result == {"error": "scenario must be sufficient or exhausted"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_main_discard_reshuffle_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-discard-reshuffle-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_discard_reshuffle_proof({"scenario": "exhausted"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_discard_reshuffle_proof)


def test_discard_reshuffle_uuid_order_is_stable(monkeypatch):
    from server.test_routes import discard_reshuffle

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(discard_reshuffle.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = DiscardReshuffleTestRoutes(
        lambda: runtime
    ).test_setup_discard_reshuffle_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_discard_reshuffle_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-discard-reshuffle-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "scenario",
        "game_id",
        "player_id",
        "opponent_id",
        "state",
    }
    assert client.post("/test/setup-discard-reshuffle-proof").status_code == 422
    list_response = client.post("/test/setup-discard-reshuffle-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-discard-reshuffle-proof"]["post"]
    assert operation["summary"] == "Test Setup Discard Reshuffle Proof"
    assert operation["operationId"].startswith("test_setup_discard_reshuffle_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-discard-reshuffle-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-discard-reshuffle-proof")
    assert paths[index - 1] == "/test/setup-elite-defection-discard-proof"
    assert paths[index + 1] == "/test/setup-support-proof"
