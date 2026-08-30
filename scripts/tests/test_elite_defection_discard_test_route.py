import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.elite_defection_discard import EliteDefectionDiscardTestRoutes
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
    routes = EliteDefectionDiscardTestRoutes(provider)
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


def test_elite_defection_discard_default_state_and_lobby_registration():
    runtime = _runtime()
    result = EliteDefectionDiscardTestRoutes(
        lambda: runtime
    ).test_setup_elite_defection_discard_proof({})

    assert set(result) == {"success", "game_id", "player_id", "red_player_id", "state"}
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    host, red = game.players

    assert result["success"] is True
    assert result["player_id"] == host.id
    assert result["red_player_id"] == red.id

    assert (host.faction_id, host.base, host.organizations) == (
        "taiwan_green",
        "臺北",
        {"臺北": 2},
    )
    assert host.hand == []
    assert [card.name for card in host.deck.draw_pile] == ["牌庫甲", "牌庫乙", "樂捐者"]
    assert len(host.deck.discard_pile) == 10
    assert host.deck.discard_pile[0].name == "樂捐者"

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == [
        "天方奧援",
        "紅軍手牌0",
        "紅軍手牌1",
        "紅軍手牌2",
        "紅軍手牌3",
    ]

    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.END
    assert game.current_player_index == 0
    assert game.round_start_player_index == 0
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.current_event["name"] == "紅軍權貴出逃"
    assert game.event_progress == {
        "count": 0,
        "required": 3,
        "succeeded": False,
        "settled": False,
        "status": "active",
        "last_actor_id": host.id,
    }
    assert [event["name"] for event in game.event_deck.draw_pile] == ["上海合作組織"]
    assert game.event_deck.discard_pile == []
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(host.id, host.name), (red.id, red.name)]
    assert runtime.lobby_hosts[game_id] == host.id
    assert runtime.lobby_factions[game_id] == {host.id: "taiwan_green", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {host.id: "臺北", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {host.id: True, red.id: True}


def test_main_elite_defection_discard_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-elite-defection-discard-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_elite_defection_discard_proof({})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_elite_defection_discard_proof)


def test_elite_defection_discard_uuid_order_is_stable(monkeypatch):
    from server.test_routes import elite_defection_discard

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(elite_defection_discard.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = EliteDefectionDiscardTestRoutes(
        lambda: runtime
    ).test_setup_elite_defection_discard_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_elite_defection_discard_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-elite-defection-discard-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "state",
    }
    assert client.post("/test/setup-elite-defection-discard-proof").status_code == 422
    list_response = client.post(
        "/test/setup-elite-defection-discard-proof", json=[]
    )
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"][
        "/test/setup-elite-defection-discard-proof"
    ]["post"]
    assert operation["summary"] == "Test Setup Elite Defection Discard Proof"
    assert operation["operationId"].startswith(
        "test_setup_elite_defection_discard_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-elite-defection-discard-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-elite-defection-discard-proof")
    assert paths[index - 1] == "/test/trigger-draw-privacy-proof"
    assert paths[index + 1] == "/test/setup-discard-reshuffle-proof"
