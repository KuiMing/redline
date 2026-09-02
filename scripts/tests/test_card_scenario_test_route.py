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
    holder = {"manager": FakeManager()}
    routes = CardScenarioTestRoutes(lambda: holder["manager"])
    app = FastAPI()
    app.include_router(routes.router)
    holder["manager"] = FakeManager(first_game)

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
    app = FastAPI()
    app.include_router(routes.router)

    response = TestClient(app).post(
        "/test/setup-card-scenario",
        json={"game_id": "missing"},
    )

    assert response.status_code == 200
    assert response.json() == {"error": "Game not found"}


def test_main_http_route_uses_rebound_manager(monkeypatch):
    game = FakeGame()
    manager = FakeManager(game)
    monkeypatch.setattr(main, "manager", manager)

    response = TestClient(main.app).post(
        "/test/setup-card-scenario",
        json={"game_id": "g2", "player_id": "p2", "card_name": "另一張卡"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert callable(main.test_setup_card_scenario)
    assert manager.game_ids == ["g2"]
    assert game.calls == [("p2", "另一張卡")]


def _effective_app_routes():
    for route in main.app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from original_router.routes
        else:
            yield route


def test_main_registers_card_scenario_route_once():
    routes = [
        route
        for route in _effective_app_routes()
        if getattr(route, "path", None) == "/test/setup-card-scenario"
    ]

    assert len(routes) == 1
    assert getattr(routes[0], "methods", None) == {"POST"}


def test_card_scenario_request_parsing_contract():
    routes = CardScenarioTestRoutes(lambda: FakeManager())
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)

    assert client.post("/test/setup-card-scenario").status_code == 422
    assert client.post("/test/setup-card-scenario", json=[]).status_code == 422
    response = client.post("/test/setup-card-scenario", json={})
    assert response.status_code == 200
    assert response.json() == {"error": "Game not found"}


def test_card_scenario_openapi_contract_is_stable():
    operation = main.app.openapi()["paths"]["/test/setup-card-scenario"]["post"]

    assert operation["summary"] == "Test Setup Card Scenario"
    assert operation["operationId"] == (
        "test_setup_card_scenario_test_setup_card_scenario_post"
    )
    assert operation["requestBody"]["required"] is True
    assert set(operation["responses"]) == {"200", "422"}
