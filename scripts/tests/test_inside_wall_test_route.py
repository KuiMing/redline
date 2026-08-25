import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pydantic
import pytest

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes import inside_wall
from server.test_routes.build_queue import BuildQueueRuntime
from server.test_routes.hand_preview import HandPreviewRuntime
from server.test_routes.inside_wall import InsideWallTestRoutes
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
    )


def _make_app(runtime_provider):
    routes = InsideWallTestRoutes(runtime_provider)
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


def test_inside_wall_route_constructs_default_proof_state():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/setup-inside-wall-proof",
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "success",
        "game_id",
        "player_id",
        "inside_count",
        "outside_count",
        "state",
    }
    assert payload["success"] is True
    assert payload["inside_count"] == 0
    assert payload["outside_count"] == 8
    game_id = payload["game_id"]
    game = runtime.manager.games[game_id]
    taiwan, red = game.players
    assert payload["player_id"] == taiwan.id
    assert game.id == game_id
    assert taiwan.faction_id == "taiwan_green"
    assert red.faction_id == "red_army"
    assert taiwan.base in game._towns_for_region_alias("taiwan")
    assert red.base == "北京"
    assert len(taiwan.organizations) == 8
    assert all(
        town in game._towns_for_region_alias("taiwan")
        for town in taiwan.organizations
    )
    assert red.organizations == {}
    for player in game.players:
        assert player.hand == []
        assert player.deck.discard_pile == []
        assert player.resources == {"money": 0, "propaganda": 0}
    assert game.current_player_index == 0
    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.ACTION
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.current_event.get("name") == "歲月靜好"
    assert game.event_progress == {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    assert game.event_notification == game._event_display_payload()
    assert game.event_modifiers == []
    assert payload["state"] == game.state(taiwan.id)
    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(taiwan.id, "Taiwan"), (red.id, "Red")]
    assert runtime.lobby_hosts[game_id] == taiwan.id
    assert runtime.lobby_factions[game_id] == {
        taiwan.id: "taiwan_green",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {}


def test_inside_wall_route_uses_canonical_inside_and_outside_towns():
    runtime = _runtime()
    result = InsideWallTestRoutes(lambda: runtime).test_setup_inside_wall_proof(
        {"inside_count": 2, "outside_count": 3}
    )
    game = runtime.manager.games[result["game_id"]]
    taiwan = game.players[0]
    eligible_inside = [
        town
        for town in game._towns_for_region_alias("china")
        if game.can_faction_develop_in_town(taiwan.faction_id, town)
    ]
    eligible_outside = [
        town
        for town in game._towns_for_region_alias("taiwan")
        if game.can_faction_develop_in_town(taiwan.faction_id, town)
    ]

    assert result["inside_count"] == 2
    assert result["outside_count"] == 3
    assert list(taiwan.organizations) == eligible_inside[:2] + eligible_outside[:3]
    assert taiwan.organizations == {
        town: 1 for town in eligible_inside[:2] + eligible_outside[:3]
    }
    assert taiwan.base == eligible_outside[0]


def test_inside_wall_route_clamps_negative_counts():
    runtime = _runtime()
    result = InsideWallTestRoutes(lambda: runtime).test_setup_inside_wall_proof(
        {"inside_count": -4, "outside_count": -2}
    )
    game = runtime.manager.games[result["game_id"]]

    assert result["inside_count"] == 0
    assert result["outside_count"] == 0
    assert game.players[0].organizations == {}


@pytest.mark.parametrize(
    ("payload", "expected_inside", "expected_outside"),
    [
        ({"inside_count": "2", "outside_count": "3"}, 2, 3),
        ({"inside_count": 2.9, "outside_count": 3.9}, 2, 3),
        ({"inside_count": None, "outside_count": None}, 0, 0),
        ({"inside_count": True, "outside_count": False}, 1, 0),
    ],
)
def test_inside_wall_route_preserves_count_coercion(
    payload, expected_inside, expected_outside
):
    runtime = _runtime()
    result = InsideWallTestRoutes(lambda: runtime).test_setup_inside_wall_proof(
        payload
    )

    assert result["inside_count"] == expected_inside
    assert result["outside_count"] == expected_outside


def test_inside_wall_route_preserves_invalid_count_exception():
    runtime = _runtime()

    with pytest.raises(ValueError, match="invalid literal for int"):
        InsideWallTestRoutes(lambda: runtime).test_setup_inside_wall_proof(
            {"inside_count": "not-an-integer"}
        )

    assert runtime.manager.games == {}


def test_inside_wall_sets_game_id_before_era_check_and_stores_after(
    monkeypatch,
):
    runtime = _runtime()
    observations = []
    original_game = inside_wall.Game

    class EraOrderGame(original_game):
        def _check_era_trigger(self):
            observations.append(
                {
                    "game_id": self.id,
                    "games": dict(runtime.manager.games),
                    "lobby": dict(runtime.lobby),
                    "hosts": dict(runtime.lobby_hosts),
                    "factions": dict(runtime.lobby_factions),
                    "bases": dict(runtime.lobby_bases),
                }
            )
            return super()._check_era_trigger()

    monkeypatch.setattr(inside_wall, "Game", EraOrderGame)

    result = InsideWallTestRoutes(lambda: runtime).test_setup_inside_wall_proof(
        {"inside_count": 7, "outside_count": 0}
    )

    assert observations == [
        {
            "game_id": result["game_id"],
            "games": {},
            "lobby": {},
            "hosts": {},
            "factions": {},
            "bases": {},
        }
    ]
    assert result["game_id"] in runtime.manager.games


def test_inside_wall_route_preserves_insufficient_towns_error():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/setup-inside-wall-proof",
        json={"inside_count": 999, "outside_count": 999},
    )

    assert response.status_code == 200
    assert response.json() == {
        "error": "Not enough canonical towns for inside-wall proof"
    }
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_main_inside_wall_route_uses_rebound_runtime(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-inside-wall-proof", json={})

    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in lobby_hosts
    assert game_id in lobby_factions
    assert lobby_bases[game_id] == {}
    assert callable(main.test_setup_inside_wall_proof)


def test_inside_wall_uuid_order_is_stable(monkeypatch):
    ids = [uuid.UUID(int=value) for value in range(1, 101)]
    monkeypatch.setattr(inside_wall.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()

    result = InsideWallTestRoutes(lambda: runtime).test_setup_inside_wall_proof({})

    assert result["game_id"] == str(ids[0])
    assert result["player_id"] == str(ids[1])
    assert [player.id for player in runtime.manager.games[result["game_id"]].players] == [
        str(ids[1]),
        str(ids[2]),
    ]


def test_shared_game_setup_runtime_preserves_compatibility_aliases():
    assert HandPreviewRuntime is GameSetupRuntime
    assert BuildQueueRuntime is GameSetupRuntime


def test_inside_wall_request_and_openapi_contracts_are_stable():
    client = TestClient(_make_app(lambda: _runtime()))
    path = "/test/setup-inside-wall-proof"

    assert client.post(path).status_code == 422
    list_response = client.post(path, json=[])
    if int(pydantic.VERSION.split(".", 1)[0]) == 1:
        assert list_response.status_code == 200
    else:
        assert list_response.status_code == 422

    operation = main.app.openapi()["paths"][path]["post"]
    assert operation["summary"] == "Test Setup Inside Wall Proof"
    assert operation["operationId"] == (
        "test_setup_inside_wall_proof_test_setup_inside_wall_proof_post"
    )
    assert operation["requestBody"]["required"] is True
    assert set(operation["responses"]) == {"200", "422"}


def test_main_registers_inside_wall_route_once_and_in_original_order():
    effective_routes = list(_effective_app_routes())
    paths = [getattr(route, "path", None) for route in effective_routes]
    path = "/test/setup-inside-wall-proof"
    routes = [route for route in effective_routes if getattr(route, "path", None) == path]
    route_index = paths.index(path)

    assert len(routes) == 1
    assert getattr(routes[0], "methods", None) == {"POST"}
    assert paths[route_index - 1] == "/test/setup-scope-audit-proof"
    assert paths[route_index + 1] == "/test/setup-card-scenario"
