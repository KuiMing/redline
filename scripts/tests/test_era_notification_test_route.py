import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.era_notification import EraNotificationTestRoutes
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
    routes = EraNotificationTestRoutes(provider)
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


def test_era_notification_default_mongolia_state_and_lobby_registration():
    runtime = _runtime()
    result = EraNotificationTestRoutes(
        lambda: runtime
    ).test_setup_era_notification_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "era_id",
        "era_name",
        "via_lifecycle",
        "viewer_organizations",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["red_player_id"] == red.id
    assert result["era_id"] == "mongolia"
    assert result["via_lifecycle"] is False
    assert result["viewer_organizations"] == {"烏蘭巴托": 1}
    assert result["url"] == f"/?game_id={game_id}&player_id={viewer.id}"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "mongol",
        "烏蘭巴托",
        {"烏蘭巴托": 1},
    )
    assert [card.name for card in viewer.hand] == ["追隨者"]
    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.era_notification is not None
    assert game.era_notification["id"] == "mongolia"
    assert "runtime_effects" in game.era_notification

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "mongol", red.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "烏蘭巴托", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {viewer.id: True, red.id: True}


def test_era_notification_unknown_era_returns_error_without_side_effects():
    runtime = _runtime()
    result = EraNotificationTestRoutes(
        lambda: runtime
    ).test_setup_era_notification_proof({"era_id": "no-such-era"})

    assert result == {"success": False, "error": "Unknown era: no-such-era"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_era_notification_via_lifecycle_activates_hong_kong_era():
    runtime = _runtime()
    result = EraNotificationTestRoutes(
        lambda: runtime
    ).test_setup_era_notification_proof(
        {"era_id": "hong_kong", "via_lifecycle": True}
    )

    assert result["success"] is True
    assert result["via_lifecycle"] is True
    assert result["era_id"] == "hong_kong"
    game = runtime.manager.games[result["game_id"]]
    assert "hong_kong" in game.era_engine.get_active_eras()
    # The idle placeholder event/progress this branch sets before advancing the
    # turn phase may be immediately overwritten by whatever advance_turn_phase()
    # draws next, so only the era-activation and organizations outcomes are a
    # stable route-level guarantee.
    assert result["viewer_organizations"] == dict(game.players[0].organizations)


def test_main_era_notification_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-era-notification-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_era_notification_proof({"era_id": "no-such"})
    assert direct["success"] is False
    assert callable(main.test_setup_era_notification_proof)


def test_era_notification_first_two_uuids_are_the_players():
    runtime = _runtime()
    result = EraNotificationTestRoutes(
        lambda: runtime
    ).test_setup_era_notification_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["player_id"] == game.players[0].id
    assert result["red_player_id"] == game.players[1].id
    assert result["game_id"] != game.players[0].id
    assert result["game_id"] != game.players[1].id


def test_era_notification_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-era-notification-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "era_id",
        "era_name",
        "via_lifecycle",
        "viewer_organizations",
        "url",
        "state",
    }
    assert client.post("/test/setup-era-notification-proof").status_code == 422
    list_response = client.post("/test/setup-era-notification-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-era-notification-proof"]["post"]
    assert operation["summary"] == "Test Setup Era Notification Proof"
    assert operation["operationId"].startswith("test_setup_era_notification_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-era-notification-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-era-notification-proof")
    assert paths[index - 1] == "/test/setup-era-event-layout-proof"
    assert paths[index + 1] == "/test/setup-hong-kong-era-red-discard-proof"
