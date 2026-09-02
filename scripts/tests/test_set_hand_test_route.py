from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.cards import Card
from server.game import TurnPhase
from server.test_routes.set_hand import SetHandTestRoutes


class FakePlayer:
    def __init__(self, player_id, name):
        self.id = player_id
        self.name = name
        self.hand = [Card("舊卡", "test")]


class FakeGame:
    def __init__(self):
        self.players = [FakePlayer("p1", "甲"), FakePlayer("p2", "乙")]
        self.structured_cards = [
            {
                "name": "結構卡",
                "type": "action",
                "resources": {"money": 1, "propaganda": 2},
            }
        ]
        self.turn_phase = TurnPhase.ACTION
        self.event_modifiers = [
            {"type": "restrict_build", "remaining_turns": 2},
            {"type": "other"},
        ]
        self.current_player_index = 0

    def _starter_card(self, name):
        return Card(name, "starter", {"money": 0, "propaganda": 0})

    def current_player(self):
        if not self.players:
            return None
        return self.players[self.current_player_index]


class FakeManager:
    def __init__(self, game=None):
        self.game = game
        self.game_ids = []

    def get_game(self, game_id):
        self.game_ids.append(game_id)
        return self.game


def _make_app(manager_provider):
    routes = SetHandTestRoutes(manager_provider)
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


def test_set_hand_route_replaces_cards_and_turn_setup():
    game = FakeGame()
    manager = FakeManager(game)
    client = TestClient(_make_app(lambda: manager))

    response = client.post(
        "/test/set-hand",
        json={
            "game_id": "g1",
            "player_id": "p2",
            "cards": ["結構卡", "起始卡"],
            "turn_phase": "end",
            "set_current_player": True,
            "restrict_build": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "hand": ["結構卡", "起始卡"],
        "turn_phase": "end",
        "current_player": "乙",
        "current_player_id": "p2",
    }
    assert manager.game_ids == ["g1"]
    assert [card.card_type for card in game.players[1].hand] == ["action", "starter"]
    assert game.players[1].hand[0].resources == {"money": 1, "propaganda": 2}
    assert game.turn_phase == TurnPhase.END
    assert game.current_player_index == 1
    assert game.event_modifiers == [
        {"type": "restrict_build", "remaining_turns": 1}
    ]


def test_set_hand_route_removes_only_restrict_build_modifier():
    game = FakeGame()
    client = TestClient(_make_app(lambda: FakeManager(game)))

    response = client.post(
        "/test/set-hand",
        json={"game_id": "g1", "player_id": "p1", "turn_phase": "unknown"},
    )

    assert response.status_code == 200
    assert response.json()["hand"] == []
    assert game.turn_phase == TurnPhase.ACTION
    assert game.event_modifiers == [{"type": "other"}]
    assert game.current_player_index == 0


def test_set_hand_route_maps_action_and_event_turn_phases():
    for phase, expected in [
        ("action", TurnPhase.ACTION),
        ("event", TurnPhase.EVENT),
    ]:
        game = FakeGame()
        game.turn_phase = TurnPhase.END
        response = TestClient(_make_app(lambda: FakeManager(game))).post(
            "/test/set-hand",
            json={"game_id": "g1", "player_id": "p1", "turn_phase": phase},
        )

        assert response.status_code == 200
        assert game.turn_phase == expected
        assert response.json()["turn_phase"] == phase


def test_set_hand_route_preserves_existing_error_contracts():
    missing_game = TestClient(_make_app(lambda: FakeManager())).post(
        "/test/set-hand",
        json={"game_id": "missing", "player_id": "p1"},
    )
    missing_player = TestClient(_make_app(lambda: FakeManager(FakeGame()))).post(
        "/test/set-hand",
        json={"game_id": "g1", "player_id": "missing"},
    )

    assert missing_game.status_code == 200
    assert missing_game.json() == {"error": "Game not found"}
    assert missing_player.status_code == 200
    assert missing_player.json() == {"error": "Player not found"}


def test_main_set_hand_route_uses_rebound_manager(monkeypatch):
    game = FakeGame()
    manager = FakeManager(game)
    monkeypatch.setattr(main, "manager", manager)

    response = TestClient(main.app).post(
        "/test/set-hand",
        json={"game_id": "g2", "player_id": "p1", "cards": ["起始卡"]},
    )

    assert response.status_code == 200
    assert response.json()["hand"] == ["起始卡"]
    assert callable(main.test_set_hand)
    assert manager.game_ids == ["g2"]


def test_set_hand_request_and_openapi_contracts_are_stable():
    client = TestClient(_make_app(lambda: FakeManager()))

    assert client.post("/test/set-hand").status_code == 422
    assert client.post("/test/set-hand", json=[]).status_code == 422
    empty = client.post("/test/set-hand", json={})
    assert empty.status_code == 200
    assert empty.json() == {"error": "Game not found"}

    operation = main.app.openapi()["paths"]["/test/set-hand"]["post"]
    assert operation["summary"] == "Test Set Hand"
    assert operation["operationId"] == "test_set_hand_test_set_hand_post"
    assert operation["requestBody"]["required"] is True
    assert set(operation["responses"]) == {"200", "422"}


def test_main_registers_set_hand_route_once():
    routes = [
        route
        for route in _effective_app_routes()
        if getattr(route, "path", None) == "/test/set-hand"
    ]

    assert len(routes) == 1
    assert getattr(routes[0], "methods", None) == {"POST"}
