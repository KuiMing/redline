import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import Game
from server.test_routes.era_event_layout import EraEventLayoutTestRoutes


class FakeManager:
    def __init__(self):
        self.games = {}
        self.connections = {}


def _make_app(provider):
    routes = EraEventLayoutTestRoutes(provider)
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


def _make_game(faction_a="taiwan_green", faction_b="hong_kong"):
    game = Game([(str(uuid.uuid4()), "a"), (str(uuid.uuid4()), "b")])
    game.players[0].faction_id = faction_a
    game.players[1].faction_id = faction_b
    return game


def test_era_event_layout_default_activates_hong_kong_era_and_idle_event():
    manager = FakeManager()
    game = _make_game()
    manager.games["g1"] = game

    result = EraEventLayoutTestRoutes(lambda: manager).test_setup_era_event_layout_proof(
        {"game_id": "g1"}
    )

    assert result == {
        "success": True,
        "game_id": "g1",
        "era_ids": ["hong_kong"],
        "event_name": "歲月靜好",
    }
    assert game.current_event["name"] == "歲月靜好"
    assert game.event_progress == {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    assert game.event_notification is not None
    assert game.event_deck.draw_pile == []
    assert game.event_deck.discard_pile == []
    runtime_effects = game.era_notification["runtime_effects"]
    assert runtime_effects["red_suppression"]["type"] == "bonus_discard_on_red_card"
    assert runtime_effects["red_suppression"]["target_camp"] == "hong_kong"
    assert runtime_effects["revolution_counterattack"]["type"] == "reduce_purchase_cost"
    assert runtime_effects["revolution_counterattack"]["target_camp"] == "hong_kong"


def test_era_event_layout_game_not_found_returns_error():
    manager = FakeManager()

    result = EraEventLayoutTestRoutes(lambda: manager).test_setup_era_event_layout_proof(
        {"game_id": "does-not-exist"}
    )

    assert result == {"success": False, "error": "Game not found"}


def test_era_event_layout_missing_faction_returns_error_with_details():
    manager = FakeManager()
    game = _make_game()
    manager.games["g1"] = game

    result = EraEventLayoutTestRoutes(lambda: manager).test_setup_era_event_layout_proof(
        {"game_id": "g1", "era_ids": ["no-such-faction"]}
    )

    assert result == {
        "success": False,
        "error": "Era layout proof requires one matching player faction per active era",
        "missing_factions": ["no-such-faction"],
        "player_count": 2,
    }


def test_era_event_layout_unknown_era_returns_error():
    manager = FakeManager()
    game = _make_game(faction_a="not_a_real_faction")
    manager.games["g1"] = game

    result = EraEventLayoutTestRoutes(lambda: manager).test_setup_era_event_layout_proof(
        {"game_id": "g1", "era_ids": ["not_a_real_faction"]}
    )

    assert result == {"success": False, "error": "Unknown era: not_a_real_faction"}


def test_era_event_layout_unknown_event_returns_error():
    manager = FakeManager()
    game = _make_game()
    manager.games["g1"] = game

    result = EraEventLayoutTestRoutes(lambda: manager).test_setup_era_event_layout_proof(
        {"game_id": "g1", "event_name": "no-such-event"}
    )

    assert result == {"success": False, "error": "Unknown event: no-such-event"}


def test_era_event_layout_custom_era_ids_list_takes_priority_over_era_id():
    manager = FakeManager()
    game = _make_game(faction_a="manchuria", faction_b="hong_kong")
    manager.games["g1"] = game

    result = EraEventLayoutTestRoutes(lambda: manager).test_setup_era_event_layout_proof(
        {"game_id": "g1", "era_id": "hong_kong", "era_ids": ["manchuria"]}
    )

    assert result["success"] is True
    assert result["era_ids"] == ["manchuria"]


def test_main_era_event_layout_uses_rebound_manager_and_callable(monkeypatch):
    manager = FakeManager()
    game = _make_game()
    manager.games["g1"] = game
    monkeypatch.setattr(main, "manager", manager)

    response = TestClient(main.app).post(
        "/test/setup-era-event-layout-proof", json={"game_id": "g1"}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    direct = main.test_setup_era_event_layout_proof({"game_id": "g1"})
    assert direct["success"] is True
    assert callable(main.test_setup_era_event_layout_proof)


def test_era_event_layout_http_openapi_and_route_order():
    manager = FakeManager()
    game = _make_game()
    manager.games["g1"] = game

    app = _make_app(lambda: manager)
    client = TestClient(app)
    response = client.post("/test/setup-era-event-layout-proof", json={"game_id": "g1"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert client.post("/test/setup-era-event-layout-proof").status_code == 422
    list_response = client.post("/test/setup-era-event-layout-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-era-event-layout-proof"]["post"]
    assert operation["summary"] == "Test Setup Era Event Layout Proof"
    assert operation["operationId"].startswith("test_setup_era_event_layout_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-era-event-layout-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-era-event-layout-proof")
    assert paths[index - 1] == "/test/setup-tibet-era-red-build-proof"
    assert paths[index + 1] == "/test/setup-era-notification-proof"
