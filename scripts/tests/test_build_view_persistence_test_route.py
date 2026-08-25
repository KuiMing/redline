from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.cards import Card
from server.game import GamePhase, TurnPhase
from server.test_routes.build_view_persistence import BuildViewPersistenceTestRoutes


class FakePlayer:
    def __init__(self, player_id, faction_id):
        self.id = player_id
        self.faction_id = faction_id
        self.base = "舊基地"
        self.organizations = {"舊基地": 2}
        self.hand = [Card("舊手牌", "test")]
        self.deck = SimpleNamespace(discard_pile=[Card("舊棄牌", "test")])


class FakeGame:
    def __init__(self):
        self.players = [
            FakePlayer("viewer", "other"),
            FakePlayer("red", "red_army"),
            FakePlayer("ally", "ally"),
        ]
        self.structured_cards = [
            {"name": "組織經驗丙", "type": "action", "resources": {"money": 1}},
            {"name": "組織經驗乙", "type": "action", "resources": {"money": 2}},
        ]
        self.current_player_index = 2
        self.game_phase = "stale"
        self.turn_phase = TurnPhase.END
        self.pending_base_choices = {"stale": True}
        self.pending_choice: dict | None = {"type": "stale"}
        self.turn_log = {"stale": True}
        self.action_log = ["stale"]
        self._action_log_visibility = ["viewer"]
        self.current_event = {"name": "stale"}
        self.event_progress = {"stale": True}
        self.event_notification = {"stale": True}
        self.event_modifiers = [{"type": "stale"}]

    def _new_turn_log(self):
        return {"new": True}


class FakeManager:
    def __init__(self, game=None):
        self.game = game
        self.game_ids = []

    def get_game(self, game_id):
        self.game_ids.append(game_id)
        return self.game


class BroadcastSpy:
    def __init__(self):
        self.calls = []

    async def __call__(self, game_id, game):
        self.calls.append((game_id, game))


def _make_app(manager_provider, broadcaster_provider):
    routes = BuildViewPersistenceTestRoutes(
        manager_provider,
        broadcaster_provider,
    )
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


def test_first_build_view_stage_resets_proof_state():
    game = FakeGame()
    manager = FakeManager(game)
    broadcast = BroadcastSpy()
    response = TestClient(_make_app(lambda: manager, lambda: broadcast)).post(
        "/test/setup-build-view-persistence-proof",
        json={"game_id": "g1", "player_id": "viewer"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "stage": "first",
        "hand": ["組織經驗丙"],
        "organizations": {"香港城": 1, "舊金山": 1},
        "turn_phase": "action",
    }
    viewer, red, ally = game.players
    assert manager.game_ids == ["g1"]
    assert viewer.faction_id == "liberals"
    assert viewer.base == "香港城"
    assert viewer.deck.discard_pile == []
    assert isinstance(viewer.hand[0], Card)
    assert viewer.hand[0].card_type == "action"
    assert viewer.hand[0].resources == {"money": 1}
    assert viewer.hand[0].resources is game.structured_cards[0]["resources"]
    assert viewer.hand[0].effect is None
    assert red.hand == []
    assert red.base == "北京"
    assert red.organizations == {"北京": 1}
    assert ally.hand == []
    assert ally.base == "舊基地"
    assert ally.organizations == {"舊基地": 2}
    assert game.current_player_index == 0
    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.ACTION
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.turn_log == {"new": True}
    assert game.action_log == []
    assert game._action_log_visibility == []
    assert game.current_event is None
    assert game.event_progress == {}
    assert game.event_notification is None
    assert game.event_modifiers == []
    assert broadcast.calls == []


def test_second_build_view_stage_broadcasts_without_resetting_board():
    game = FakeGame()
    game.pending_choice = None
    manager = FakeManager(game)
    broadcast = BroadcastSpy()
    response = TestClient(_make_app(lambda: manager, lambda: broadcast)).post(
        "/test/setup-build-view-persistence-proof",
        json={"game_id": "g2", "player_id": "viewer", "stage": "second"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "stage": "second",
        "hand": ["組織經驗乙"],
        "organizations": {"舊基地": 2},
        "turn_phase": "end",
    }
    assert isinstance(game.players[0].hand[0], Card)
    assert game.players[0].hand[0].resources == {"money": 2}
    assert game.players[0].hand[0].resources is game.structured_cards[1]["resources"]
    assert game.players[0].hand[0].effect is None
    assert game.players[0].faction_id == "other"
    assert game.players[0].base == "舊基地"
    assert [card.name for card in game.players[0].deck.discard_pile] == ["舊棄牌"]
    assert [card.name for card in game.players[1].hand] == ["舊手牌"]
    assert [card.name for card in game.players[2].hand] == ["舊手牌"]
    assert game.game_phase == "stale"
    assert game.current_player_index == 2
    assert game.pending_base_choices == {"stale": True}
    assert game.pending_choice is None
    assert game.turn_log == {"stale": True}
    assert game.action_log == ["stale"]
    assert game._action_log_visibility == ["viewer"]
    assert game.current_event == {"name": "stale"}
    assert game.event_progress == {"stale": True}
    assert game.event_notification == {"stale": True}
    assert game.event_modifiers == [{"type": "stale"}]
    assert broadcast.calls == [("g2", game)]


def test_build_view_route_preserves_error_contracts():
    cases = [
        (FakeManager(), {"game_id": "missing"}, "Game not found"),
        (
            FakeManager(FakeGame()),
            {"game_id": "g1", "player_id": "missing"},
            "Player not found",
        ),
        (
            FakeManager(FakeGame()),
            {"game_id": "g1", "player_id": "viewer", "stage": "other"},
            "Unknown build-view proof stage",
        ),
        (
            FakeManager(FakeGame()),
            {"game_id": "g1", "player_id": "viewer", "stage": "second"},
            "First build session is still pending",
        ),
    ]

    for manager, payload, error in cases:
        response = TestClient(
            _make_app(lambda manager=manager: manager, lambda: BroadcastSpy())
        ).post("/test/setup-build-view-persistence-proof", json=payload)
        assert response.status_code == 200
        assert response.json() == {"error": error}


def test_build_view_route_preserves_competing_error_priority():
    pending_without_cards = FakeGame()
    pending_without_cards.structured_cards = []
    cases = [
        (
            FakeManager(),
            {"game_id": "missing", "player_id": "missing", "stage": "other"},
            "Game not found",
        ),
        (
            FakeManager(FakeGame()),
            {"game_id": "g1", "player_id": "missing", "stage": "other"},
            "Player not found",
        ),
        (
            FakeManager(FakeGame()),
            {"game_id": "g1", "player_id": "viewer", "stage": "other"},
            "Unknown build-view proof stage",
        ),
        (
            FakeManager(pending_without_cards),
            {"game_id": "g1", "player_id": "viewer", "stage": "second"},
            "First build session is still pending",
        ),
    ]

    for manager, payload, error in cases:
        response = TestClient(
            _make_app(lambda manager=manager: manager, lambda: BroadcastSpy())
        ).post("/test/setup-build-view-persistence-proof", json=payload)
        assert response.json() == {"error": error}


def test_build_view_route_reports_missing_action_card():
    game = FakeGame()
    game.structured_cards = []
    response = TestClient(
        _make_app(lambda: FakeManager(game), lambda: BroadcastSpy())
    ).post(
        "/test/setup-build-view-persistence-proof",
        json={"game_id": "g1", "player_id": "viewer"},
    )

    assert response.status_code == 200
    assert response.json() == {"error": "Unknown action card: 組織經驗丙"}


def test_main_build_view_route_uses_rebound_dependencies(monkeypatch):
    game = FakeGame()
    game.pending_choice = None
    manager = FakeManager(game)
    broadcast = BroadcastSpy()
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "broadcast_game_state", broadcast)

    response = TestClient(main.app).post(
        "/test/setup-build-view-persistence-proof",
        json={"game_id": "g3", "player_id": "viewer", "stage": "second"},
    )

    assert response.status_code == 200
    assert broadcast.calls == [("g3", game)]
    assert callable(main.test_setup_build_view_persistence_proof)


def test_build_view_request_and_openapi_contracts_are_stable():
    client = TestClient(_make_app(lambda: FakeManager(), lambda: BroadcastSpy()))
    path = "/test/setup-build-view-persistence-proof"

    assert client.post(path).status_code == 422
    assert client.post(path, json=[]).status_code == 422
    assert client.post(path, json={}).json() == {"error": "Game not found"}

    operation = main.app.openapi()["paths"][path]["post"]
    assert operation["summary"] == "Test Setup Build View Persistence Proof"
    assert operation["operationId"] == (
        "test_setup_build_view_persistence_proof_"
        "test_setup_build_view_persistence_proof_post"
    )
    assert operation["requestBody"]["required"] is True
    assert set(operation["responses"]) == {"200", "422"}


def test_main_registers_build_view_route_once_and_in_original_order():
    effective_routes = list(_effective_app_routes())
    paths = [getattr(route, "path", None) for route in effective_routes]
    path = "/test/setup-build-view-persistence-proof"
    routes = [route for route in effective_routes if getattr(route, "path", None) == path]
    route_index = paths.index(path)

    assert len(routes) == 1
    assert getattr(routes[0], "methods", None) == {"POST"}
    assert paths[route_index - 1] == "/test/set-hand"
    assert paths[route_index + 1] == "/test/setup-build-queue-proof"
