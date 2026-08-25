from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.card_scenario import CardScenarioTestRoutes


class FakeGame:
    def __init__(self):
        self.calls = []

    def setup_test_card_scenario(self, player_id, card_name):
        self.calls.append((player_id, card_name))
        return {"success": True, "player_id": player_id, "card_name": card_name}


class FakeManager:
    def __init__(self, game=None):
        self.game = game
        self.game_ids = []

    def get_game(self, game_id):
        self.game_ids.append(game_id)
        return self.game


def test_card_scenario_route_delegates_to_current_manager():
    first_game = FakeGame()
    holder = {"manager": FakeManager(first_game)}
    routes = CardScenarioTestRoutes(lambda: holder["manager"])
    app = FastAPI()
    app.include_router(routes.router)

    response = TestClient(app).post(
        "/test/setup-card-scenario",
        json={"game_id": "g1", "player_id": "p1", "card_name": "測試卡"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "player_id": "p1",
        "card_name": "測試卡",
    }
    assert holder["manager"].game_ids == ["g1"]
    assert first_game.calls == [("p1", "測試卡")]


def test_card_scenario_route_returns_existing_missing_game_error():
    routes = CardScenarioTestRoutes(lambda: FakeManager())

    assert routes.test_setup_card_scenario({"game_id": "missing"}) == {
        "error": "Game not found"
    }


def test_main_compatibility_export_uses_rebound_manager(monkeypatch):
    game = FakeGame()
    manager = FakeManager(game)
    monkeypatch.setattr(main, "manager", manager)

    result = main.test_setup_card_scenario(
        {"game_id": "g2", "player_id": "p2", "card_name": "另一張卡"}
    )

    assert result["success"] is True
    assert manager.game_ids == ["g2"]
    assert game.calls == [("p2", "另一張卡")]


def test_main_registers_card_scenario_router_once():
    included = [
        route
        for route in main.app.routes
        if getattr(route, "original_router", None)
        is main._card_scenario_test_routes.router
    ]

    assert len(included) == 1
    route = main._card_scenario_test_routes.router.routes[0]
    assert getattr(route, "path", None) == "/test/setup-card-scenario"
    assert getattr(route, "methods", None) == {"POST"}
