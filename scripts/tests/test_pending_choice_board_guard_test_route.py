import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.pending_choice_board_guard import PendingChoiceBoardGuardTestRoutes
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
    routes = PendingChoiceBoardGuardTestRoutes(provider)
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


def test_pending_choice_board_guard_state_and_lobby_registration():
    runtime = _runtime()
    result = PendingChoiceBoardGuardTestRoutes(
        lambda: runtime
    ).test_setup_pending_choice_board_guard()

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "url",
        "move",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    actor, red = game.players

    assert result["success"] is True
    assert result["player_id"] == actor.id
    assert result["red_player_id"] == red.id
    assert result["url"] == f"/?game_id={game_id}&player_id={actor.id}"
    assert result["move"] == {"from": "桃園", "to": "宜蘭", "mode": "road"}

    assert (actor.faction_id, actor.base, actor.organizations, actor.moves_left) == (
        "taiwan_green",
        "臺北",
        {"臺北": 1, "桃園": 1},
        3,
    )
    assert actor.resources == {"money": 0, "propaganda": 0}
    assert actor.hand == []
    assert (red.faction_id, red.base, red.organizations, red.hand) == (
        "red_army",
        "北京",
        {"北京": 1, "上海": 1},
        [],
    )
    assert game.current_player_index == 0
    assert game.round_start_player_index == 0
    assert game.pending_base_choices == {}
    assert game.pending_choice["type"] == "card_choice"
    assert game.pending_choice["choice_key"] == "recruit_talent"
    assert game.pending_choice["player_id"] == actor.id
    assert [card.name for card in game.pending_choice["cards"]] == ["候選牌"]
    assert game.pending_choice["prompt"] == "網羅人才：請選擇一張牌。"
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {actor.id: "taiwan_green", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {actor.id: "臺北", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {actor.id: True, red.id: True}


def test_main_pending_choice_board_guard_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-pending-choice-board-guard")
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_pending_choice_board_guard()
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_pending_choice_board_guard)


def test_pending_choice_board_guard_uuid_order_is_stable(monkeypatch):
    from server.test_routes import pending_choice_board_guard

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(pending_choice_board_guard.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = PendingChoiceBoardGuardTestRoutes(
        lambda: runtime
    ).test_setup_pending_choice_board_guard()
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_pending_choice_board_guard_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-pending-choice-board-guard")
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "url",
        "move",
        "state",
    }

    operation = app.openapi()["paths"]["/test/setup-pending-choice-board-guard"]["post"]
    assert operation["summary"] == "Test Setup Pending Choice Board Guard"
    assert operation["operationId"].startswith("test_setup_pending_choice_board_guard_")

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-pending-choice-board-guard"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-pending-choice-board-guard")
    assert paths[index - 1] == "/test/setup-hong-kong-safehouse"
    assert paths[index + 1] == "/test/setup-enemy-occupancy-proof"
