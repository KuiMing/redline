import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.era_restrict_ignore_distance import (
    EraRestrictIgnoreDistanceTestRoutes,
)
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
    routes = EraRestrictIgnoreDistanceTestRoutes(provider)
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


def test_era_restrict_ignore_distance_default_state_and_lobby_registration():
    runtime = _runtime()
    result = EraRestrictIgnoreDistanceTestRoutes(
        lambda: runtime
    ).test_setup_era_restrict_ignore_distance_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "opponent_player_id",
        "era_id",
        "era_name",
        "origin",
        "near_inner",
        "ideologue_inner",
        "ideologue_outer_count",
        "org_experience_a_inner",
        "east_asia_support_anywhere",
        "east_asia_support_near",
        "url",
        "opponent_url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, opponent = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["opponent_player_id"] == opponent.id
    assert result["era_id"] == "rebels"
    assert result["era_name"] == "[反賊]公知世代的終結"
    assert result["origin"] == "上海"
    assert result["near_inner"] == ["上海", "南京", "杭州"]
    assert result["ideologue_inner"] == ["南京", "杭州"]
    assert result["ideologue_outer_count"] == 36
    assert result["url"] == f"/?game_id={game_id}&player_id={viewer.id}"
    assert result["opponent_url"] == f"/?game_id={game_id}&player_id={opponent.id}"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "上海",
        {"上海": 1},
    )
    assert viewer.hand == []
    assert viewer.deck.draw_pile == []
    assert viewer.deck.discard_pile == []
    assert viewer.build_range_bonus == 0

    assert (opponent.faction_id, opponent.base, opponent.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert opponent.hand == []

    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
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
    assert "rebels" in game.era_engine.get_active_eras()
    assert game.era_notification is not None

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {viewer.id: "liberals", opponent.id: "red_army"}
    assert runtime.lobby_bases[game_id] == {viewer.id: "上海", opponent.id: "北京"}
    assert runtime.lobby_ready[game_id] == {viewer.id: True, opponent.id: True}


def test_era_restrict_ignore_distance_unknown_era_returns_error_without_side_effects():
    runtime = _runtime()
    result = EraRestrictIgnoreDistanceTestRoutes(
        lambda: runtime
    ).test_setup_era_restrict_ignore_distance_proof({"era": "no-such-era"})

    assert result == {"error": "時代關卡無法啟用：no-such-era"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_era_restrict_ignore_distance_unknown_card_returns_error():
    runtime = _runtime()
    result = EraRestrictIgnoreDistanceTestRoutes(
        lambda: runtime
    ).test_setup_era_restrict_ignore_distance_proof({"card": "no-such-card"})

    assert result == {"error": "找不到卡牌：no-such-card"}
    assert runtime.manager.games == {}


def test_era_restrict_ignore_distance_unknown_extra_era_returns_error():
    runtime = _runtime()
    result = EraRestrictIgnoreDistanceTestRoutes(
        lambda: runtime
    ).test_setup_era_restrict_ignore_distance_proof({"extra_eras": ["no-such-extra"]})

    assert result == {"error": "時代關卡無法啟用：no-such-extra"}
    # Game/lobby registration happens after both the primary era and the
    # extra_eras loop, so a failure in extra_eras still leaves no side effects.
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_era_restrict_ignore_distance_no_era_skips_activation():
    runtime = _runtime()
    result = EraRestrictIgnoreDistanceTestRoutes(
        lambda: runtime
    ).test_setup_era_restrict_ignore_distance_proof({"era": ""})

    assert result["success"] is True
    assert result["era_id"] == ""
    assert result["era_name"] is None
    game = runtime.manager.games[result["game_id"]]
    assert game.era_engine.get_active_eras() == []


def test_era_restrict_ignore_distance_custom_origin_and_card():
    runtime = _runtime()
    result = EraRestrictIgnoreDistanceTestRoutes(
        lambda: runtime
    ).test_setup_era_restrict_ignore_distance_proof(
        {"origin": "臺北", "card": "思想家", "build_range_bonus": 2}
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, _opponent = game.players

    assert result["origin"] == "臺北"
    assert (viewer.base, viewer.organizations) == ("臺北", {"臺北": 1})
    assert viewer.build_range_bonus == 2
    assert [card.name for card in viewer.hand] == ["思想家"]


def test_main_era_restrict_ignore_distance_uses_rebound_runtime_and_callable(
    monkeypatch,
):
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
        "/test/setup-era-restrict-ignore-distance-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_era_restrict_ignore_distance_proof({"era": "kazakh"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_era_restrict_ignore_distance_proof)


def test_era_restrict_ignore_distance_uuid_order_is_stable(monkeypatch):
    from server.test_routes import era_restrict_ignore_distance

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(
        era_restrict_ignore_distance.uuid, "uuid4", iter(ids).__next__
    )
    runtime = _runtime()
    result = EraRestrictIgnoreDistanceTestRoutes(
        lambda: runtime
    ).test_setup_era_restrict_ignore_distance_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_era_restrict_ignore_distance_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-era-restrict-ignore-distance-proof", json={})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert (
        client.post("/test/setup-era-restrict-ignore-distance-proof").status_code
        == 422
    )
    list_response = client.post(
        "/test/setup-era-restrict-ignore-distance-proof", json=[]
    )
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"][
        "/test/setup-era-restrict-ignore-distance-proof"
    ]["post"]
    assert operation["summary"] == "Test Setup Era Restrict Ignore Distance Proof"
    assert operation["operationId"].startswith(
        "test_setup_era_restrict_ignore_distance_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None)
        == "/test/setup-era-restrict-ignore-distance-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-era-restrict-ignore-distance-proof")
    assert paths[index - 1] == "/test/setup-safehouse-range-proof"
    assert index == len(paths) - 1
