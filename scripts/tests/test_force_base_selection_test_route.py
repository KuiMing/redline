import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from server import main
from server.game import Game, GamePhase
from server.test_routes import force_base_selection
from server.test_routes.force_base_selection import ForceBaseSelectionTestRoutes
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
    routes = ForceBaseSelectionTestRoutes(runtime_provider)
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


def test_force_base_selection_requires_at_least_two_factions():
    runtime = _runtime()
    route = ForceBaseSelectionTestRoutes(lambda: runtime)

    assert route.test_force_base_selection({}) == {
        "error": "Need at least 2 faction ids"
    }
    assert route.test_force_base_selection({"faction_ids": ["red_army"]}) == {
        "error": "Need at least 2 faction ids"
    }
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_force_base_selection_constructs_default_state():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/force-base-selection",
        json={"faction_ids": ["red_army", "hong_kong"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "success",
        "game_id",
        "players",
        "pending_base_choices",
        "game_phase",
    }
    assert payload["success"] is True
    game_id = payload["game_id"]
    game = runtime.manager.games[game_id]
    first, second = game.players
    assert [player.name for player in game.players] == ["player1", "player2"]
    assert [player.faction_id for player in game.players] == [
        "red_army",
        "hong_kong",
    ]
    assert payload["players"] == [
        {
            "id": player.id,
            "name": player.name,
            "faction": player.faction_id,
            "base": player.base,
        }
        for player in game.players
    ]
    assert payload["pending_base_choices"] == game.pending_base_choices
    expected_phase = (
        GamePhase.BASE_SELECTION
        if game.pending_base_choices
        else GamePhase.MAIN
    )
    assert payload["game_phase"] == expected_phase
    assert game.game_phase == expected_phase
    if not game.pending_base_choices:
        assert game.current_player_index == 1
    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [
        (first.id, "player1"),
        (second.id, "player2"),
    ]
    assert runtime.lobby_hosts[game_id] == first.id
    assert runtime.lobby_factions[game_id] == {
        first.id: "red_army",
        second.id: "hong_kong",
    }
    assert runtime.lobby_bases[game_id] == {
        player.id: player.base for player in game.players if player.base
    }


def test_force_base_selection_sets_base_selection_phase_when_choices_remain(
    monkeypatch,
):
    class PendingGame(Game):
        def __init__(self, players):
            super().__init__(players)
            self.current_player_index = 7

        def _compute_pending_base_choices(self):
            return {self.players[0].id: {"labels": ["北京"]}}

    monkeypatch.setattr(force_base_selection, "Game", PendingGame)
    runtime = _runtime()

    result = ForceBaseSelectionTestRoutes(
        lambda: runtime
    ).test_force_base_selection(
        {"faction_ids": ["red_army", "hong_kong"]}
    )
    game = runtime.manager.games[result["game_id"]]

    assert result["pending_base_choices"] == {
        game.players[0].id: {"labels": ["北京"]}
    }
    assert result["game_phase"] == GamePhase.BASE_SELECTION
    assert game.game_phase == GamePhase.BASE_SELECTION
    assert game.current_player_index == 7


def test_force_base_selection_sets_first_non_red_player_when_no_choices(
    monkeypatch,
):
    class NoPendingGame(Game):
        def _compute_pending_base_choices(self):
            return {}

    monkeypatch.setattr(force_base_selection, "Game", NoPendingGame)
    runtime = _runtime()

    result = ForceBaseSelectionTestRoutes(
        lambda: runtime
    ).test_force_base_selection(
        {
            "faction_ids": ["red_army", "hong_kong", "taiwan_green"],
            "player_names": ["Red", "HK", "Taiwan"],
        }
    )
    game = runtime.manager.games[result["game_id"]]

    assert result["pending_base_choices"] == {}
    assert result["game_phase"] == GamePhase.MAIN
    assert game.current_player_index == 1


def test_force_base_selection_preserves_mismatched_name_and_faction_lengths(
    monkeypatch,
):
    class NoPendingGame(Game):
        def __init__(self, players):
            super().__init__(players)
            self.initial_faction_ids = [
                player.faction_id for player in self.players
            ]

        def _compute_pending_base_choices(self):
            return {}

    monkeypatch.setattr(force_base_selection, "Game", NoPendingGame)

    short_runtime = _runtime()
    short_result = ForceBaseSelectionTestRoutes(
        lambda: short_runtime
    ).test_force_base_selection(
        {
            "faction_ids": ["red_army", "hong_kong", "taiwan_green"],
            "player_names": ["Red", "HK"],
        }
    )
    short_game = short_runtime.manager.games[short_result["game_id"]]
    assert [player.name for player in short_game.players] == ["Red", "HK"]
    assert [player.faction_id for player in short_game.players] == [
        "red_army",
        "hong_kong",
    ]

    long_runtime = _runtime()
    long_result = ForceBaseSelectionTestRoutes(
        lambda: long_runtime
    ).test_force_base_selection(
        {
            "faction_ids": ["red_army", "hong_kong"],
            "player_names": ["Red", "HK", "Unassigned"],
        }
    )
    long_game = long_runtime.manager.games[long_result["game_id"]]
    assert [player.name for player in long_game.players] == [
        "Red",
        "HK",
        "Unassigned",
    ]
    assert [player.faction_id for player in long_game.players[:2]] == [
        "red_army",
        "hong_kong",
    ]
    assert long_game.players[2].faction_id == long_game.initial_faction_ids[2]


def test_force_base_selection_preserves_chosen_base_success_path(monkeypatch):
    class SelectableGame(Game):
        def _compute_pending_base_choices(self):
            return {player.id: {"labels": [player.name]} for player in self.players}

        def choose_base(self, player_id, base_name):
            player = next(player for player in self.players if player.id == player_id)
            player.base = base_name
            self.pending_base_choices.pop(player_id, None)
            return {"success": True}

    monkeypatch.setattr(force_base_selection, "Game", SelectableGame)
    runtime = _runtime()

    result = ForceBaseSelectionTestRoutes(
        lambda: runtime
    ).test_force_base_selection(
        {
            "faction_ids": ["red_army", "hong_kong"],
            "player_names": ["Red", "HK"],
            "chosen_bases": {"Red": "北京", "HK": "香港城"},
        }
    )
    game = runtime.manager.games[result["game_id"]]

    assert [player.base for player in game.players] == ["北京", "香港城"]
    assert result["pending_base_choices"] == {}
    assert result["game_phase"] == GamePhase.MAIN
    assert game.current_player_index == 1
    assert runtime.lobby_bases[result["game_id"]] == {
        game.players[0].id: "北京",
        game.players[1].id: "香港城",
    }


def test_force_base_selection_preserves_name_then_id_base_precedence(
    monkeypatch,
):
    selections = []

    class SelectableGame(Game):
        def _compute_pending_base_choices(self):
            return {player.id: {} for player in self.players}

        def choose_base(self, player_id, base_name):
            selections.append((player_id, base_name))
            self.pending_base_choices.pop(player_id, None)
            return {"success": True}

    ids = [uuid.UUID(int=value) for value in range(1, 101)]
    monkeypatch.setattr(force_base_selection, "Game", SelectableGame)
    monkeypatch.setattr(force_base_selection.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()

    ForceBaseSelectionTestRoutes(lambda: runtime).test_force_base_selection(
        {
            "faction_ids": ["red_army", "hong_kong"],
            "player_names": ["Red", "HK"],
            "chosen_bases": {
                "Red": "名稱優先基地",
                str(ids[1]): "ID 不應勝出",
                "HK": "",
                str(ids[2]): "ID fallback 基地",
            },
        }
    )

    assert selections == [
        (str(ids[1]), "名稱優先基地"),
        (str(ids[2]), "ID fallback 基地"),
    ]


def test_force_base_selection_preserves_choose_base_error_and_store_order(
    monkeypatch,
):
    class RejectingGame(Game):
        def _compute_pending_base_choices(self):
            return {player.id: {} for player in self.players}

        def choose_base(self, player_id, base_name):
            return {"error": "invalid base"}

    monkeypatch.setattr(force_base_selection, "Game", RejectingGame)
    runtime = _runtime()

    result = ForceBaseSelectionTestRoutes(
        lambda: runtime
    ).test_force_base_selection(
        {
            "faction_ids": ["red_army", "hong_kong"],
            "player_names": ["Red", "HK"],
            "chosen_bases": {"Red": "錯誤基地"},
        }
    )

    assert result == {
        "error": "invalid base",
        "player": "Red",
        "base_name": "錯誤基地",
    }
    assert runtime.manager.games == {}
    assert runtime.manager.connections == {}
    assert runtime.lobby == {}
    assert runtime.lobby_hosts == {}
    assert runtime.lobby_factions == {}
    assert runtime.lobby_bases == {}


def test_force_base_selection_preserves_missing_choose_base_failure():
    runtime = _runtime()

    with pytest.raises(AttributeError, match="choose_base"):
        ForceBaseSelectionTestRoutes(
            lambda: runtime
        ).test_force_base_selection(
            {
                "faction_ids": ["red_army", "hong_kong"],
                "player_names": ["Red", "HK"],
                "chosen_bases": {"Red": "北京"},
            }
        )

    assert runtime.manager.games == {}
    assert runtime.manager.connections == {}
    assert runtime.lobby == {}
    assert runtime.lobby_hosts == {}
    assert runtime.lobby_factions == {}
    assert runtime.lobby_bases == {}


def test_main_force_base_selection_uses_rebound_runtime(monkeypatch):
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

    response = TestClient(main.app).post(
        "/test/force-base-selection",
        json={"faction_ids": ["red_army", "hong_kong"]},
    )

    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in lobby_hosts
    assert game_id in lobby_factions
    assert game_id in lobby_bases
    assert callable(main.test_force_base_selection)

    direct_result = main.test_force_base_selection(
        {"faction_ids": ["red_army", "hong_kong"]}
    )
    direct_game_id = direct_result["game_id"]
    assert direct_game_id != game_id
    assert direct_game_id in manager.games
    assert direct_game_id in lobby
    assert direct_game_id in lobby_hosts
    assert direct_game_id in lobby_factions
    assert direct_game_id in lobby_bases


def test_force_base_selection_uuid_order_is_stable(monkeypatch):
    ids = [uuid.UUID(int=value) for value in range(1, 101)]
    monkeypatch.setattr(force_base_selection.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()

    result = ForceBaseSelectionTestRoutes(
        lambda: runtime
    ).test_force_base_selection(
        {
            "game_id": "caller-supplied-id",
            "faction_ids": ["red_army", "hong_kong"],
        }
    )

    assert result["game_id"] == str(ids[0])
    assert result["game_id"] != "caller-supplied-id"
    assert [player.id for player in runtime.manager.games[result["game_id"]].players] == [
        str(ids[1]),
        str(ids[2]),
    ]


@pytest.mark.parametrize(
    "payload_overrides",
    [
        {},
        {"player_names": None, "chosen_bases": None},
        {"player_names": [], "chosen_bases": {}},
    ],
)
def test_force_base_selection_preserves_empty_payload_fallbacks(
    payload_overrides,
):
    runtime = _runtime()
    payload = {"faction_ids": ["red_army", "hong_kong"], **payload_overrides}

    result = ForceBaseSelectionTestRoutes(
        lambda: runtime
    ).test_force_base_selection(payload)
    game = runtime.manager.games[result["game_id"]]

    assert [player.name for player in game.players] == ["player1", "player2"]


def test_force_base_selection_preserves_null_faction_ids_exception():
    runtime = _runtime()

    with pytest.raises(TypeError, match="has no len"):
        ForceBaseSelectionTestRoutes(
            lambda: runtime
        ).test_force_base_selection({"faction_ids": None})

    assert runtime.manager.games == {}


def test_force_base_selection_request_and_openapi_contracts_are_stable():
    client = TestClient(_make_app(lambda: _runtime()))
    path = "/test/force-base-selection"

    assert client.post(path).status_code == 422
    empty_payload_response = client.post(path, json={})
    assert empty_payload_response.status_code == 200
    assert empty_payload_response.json() == {
        "error": "Need at least 2 faction ids"
    }

    operation = main.app.openapi()["paths"][path]["post"]
    assert operation["summary"] == "Test Force Base Selection"
    assert operation["operationId"] == (
        "test_force_base_selection_test_force_base_selection_post"
    )
    assert operation["requestBody"]["required"] is True
    assert set(operation["responses"]) == {"200", "422"}


def test_main_registers_force_base_selection_once_and_in_original_order():
    effective_routes = list(_effective_app_routes())
    paths = [getattr(route, "path", None) for route in effective_routes]
    path = "/test/force-base-selection"
    routes = [route for route in effective_routes if getattr(route, "path", None) == path]
    route_index = paths.index(path)

    assert len(routes) == 1
    assert getattr(routes[0], "methods", None) == {"POST"}
    assert paths[route_index - 1] == "/test/setup-card-scenario"
    assert paths[route_index + 1] == "/test/setup-intel-network-proof"
