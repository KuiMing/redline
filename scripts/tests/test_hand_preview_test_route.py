from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.hand_preview import HandPreviewRuntime, HandPreviewTestRoutes


class FakeManager:
    def __init__(self):
        self.games = {}
        self.connections = {}


def _runtime(manager=None):
    return HandPreviewRuntime(
        manager=manager or FakeManager(),
        lobby={},
        lobby_hosts={},
        lobby_factions={},
        lobby_bases={},
    )


def _make_app(runtime_provider):
    routes = HandPreviewTestRoutes(runtime_provider)
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


def test_hand_preview_route_builds_default_runtime_state():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/setup-hand-preview",
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["hand_names"] == ["宣傳家", "印度奧援", "東洋奧援"]
    assert payload["turn_phase"] == "action"
    assert payload["game_phase"] == "main"

    game_id = payload["game_id"]
    viewer_id = payload["player_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players
    assert game.id == game_id
    assert viewer.id == viewer_id
    assert viewer.faction_id == "tibet_dehradun"
    assert viewer.base == "德拉敦"
    assert viewer.organizations == {"德拉敦": 1}
    assert viewer.resources == {"money": 4, "propaganda": 3}
    assert [card.name for card in viewer.hand] == payload["hand_names"]
    assert red.faction_id == "red_army"
    assert red.base == "北京"
    assert red.organizations == {"北京": 1}
    assert len(game.purchase_area) == 11
    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [
        (viewer.id, "viewer"),
        (red.id, "red"),
    ]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "tibet_dehradun",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {
        viewer.id: "德拉敦",
        red.id: "北京",
    }


def test_hand_preview_route_preserves_custom_card_and_log_setup():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/setup-hand-preview",
        json={
            "faction_id": "taiwan",
            "base": "臺北",
            "orgs": {"臺北": 2},
            "resources": {"money": 8, "propaganda": 6},
            "hand_names": ["宣傳家", "印度奧援", "未知牌"],
            "viewer_discard_names": ["東洋奧援"],
            "red_discard_names": ["未知紅軍牌"],
            "action_log": [1, "記錄"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    game = runtime.manager.games[payload["game_id"]]
    viewer, red = game.players
    assert viewer.faction_id == "taiwan"
    assert viewer.base == "臺北"
    assert viewer.organizations == {"臺北": 2}
    assert viewer.resources == {"money": 8, "propaganda": 6}
    assert [card.name for card in viewer.hand] == ["宣傳家", "印度奧援", "未知牌"]
    assert [card.name for card in viewer.deck.discard_pile] == ["東洋奧援"]
    assert [card.name for card in red.deck.discard_pile] == ["未知紅軍牌"]
    assert game.action_log == ["1", "記錄"]
    assert game._action_log_visibility == [None, None]


def test_main_hand_preview_route_uses_rebound_runtime(monkeypatch):
    manager = FakeManager()
    lobby = {}
    lobby_hosts = {}
    lobby_factions = {}
    lobby_bases = {}
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "lobby", lobby)
    monkeypatch.setattr(main, "lobby_hosts", lobby_hosts)
    monkeypatch.setattr(main, "lobby_factions", lobby_factions)
    monkeypatch.setattr(main, "lobby_bases", lobby_bases)

    response = TestClient(main.app).post("/test/setup-hand-preview", json={})

    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in lobby_hosts
    assert game_id in lobby_factions
    assert game_id in lobby_bases
    assert callable(main.test_setup_hand_preview)


def test_hand_preview_request_and_openapi_contracts_are_stable():
    client = TestClient(_make_app(lambda: _runtime()))

    assert client.post("/test/setup-hand-preview").status_code == 422
    assert client.post("/test/setup-hand-preview", json=[]).status_code == 422

    operation = main.app.openapi()["paths"]["/test/setup-hand-preview"]["post"]
    assert operation["summary"] == "Test Setup Hand Preview"
    assert operation["operationId"] == (
        "test_setup_hand_preview_test_setup_hand_preview_post"
    )
    assert operation["requestBody"]["required"] is True
    assert set(operation["responses"]) == {"200", "422"}


def test_main_registers_hand_preview_route_once():
    routes = [
        route
        for route in _effective_app_routes()
        if getattr(route, "path", None) == "/test/setup-hand-preview"
    ]

    assert len(routes) == 1
    assert getattr(routes[0], "methods", None) == {"POST"}
