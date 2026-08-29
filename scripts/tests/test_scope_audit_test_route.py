import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pydantic
import pytest

from server import main
from server.game import Game, GamePhase, TurnPhase
from server.test_routes import scope_audit
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.scope_audit import ScopeAuditTestRoutes


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
    routes = ScopeAuditTestRoutes(runtime_provider)
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


CANONICAL_PREFIXES = {
    "mongolia_outside": ["亞巴坎", "伊爾庫次克", "克孜勒", "喬巴山"],
    "mongolia_inside": ["延邊", "丹東", "牡丹江", "佳木斯"],
    "hong_kong_outside_victory": [
        "臺北", "新北", "基隆", "桃園", "新竹", "苗栗", "彰化",
        "臺中", "南投", "雲林", "嘉義", "臺南", "高雄", "屏東",
    ],
    "hong_kong_inside_victory": [
        "延邊", "丹東", "牡丹江", "佳木斯", "赤峰", "承德", "朝陽",
        "阜新", "北京", "天津", "張家口", "烏蘭察布", "錫林郭勒", "呼和浩特",
    ],
    "red_taiwan_without_taiwan": [
        "南投", "嘉義", "基隆", "宜蘭", "屏東", "彰化", "新北",
        "新竹", "東沙", "桃園", "澎湖", "臺中", "臺北", "臺南",
    ],
    "red_taiwan_with_taiwan": [
        "南投", "嘉義", "基隆", "宜蘭", "屏東", "彰化", "新北",
        "新竹", "東沙", "桃園", "澎湖", "臺中", "臺北", "臺南",
    ],
}


SCENARIOS = [
    ("mongolia_outside", 2, "mongol", "red_army", 4, 0, 4, False, None),
    ("mongolia_inside", 2, "mongol", "red_army", 4, 4, 0, True, None),
    (
        "hong_kong_outside_victory",
        2,
        "hong_kong",
        "red_army",
        14,
        0,
        14,
        False,
        None,
    ),
    (
        "hong_kong_inside_victory",
        2,
        "hong_kong",
        "red_army",
        14,
        14,
        0,
        True,
        "Actor",
    ),
    (
        "red_taiwan_without_taiwan",
        2,
        "red_army",
        "liberals",
        14,
        0,
        14,
        None,
        None,
    ),
    (
        "red_taiwan_with_taiwan",
        3,
        "red_army",
        "liberals",
        14,
        0,
        14,
        None,
        "red_army",
    ),
]


@pytest.mark.parametrize(
    (
        "scenario",
        "player_count",
        "actor_faction",
        "opponent_faction",
        "total",
        "inside_count",
        "outside_count",
        "era_achieved",
        "winner",
    ),
    SCENARIOS,
)
def test_scope_audit_scenarios_preserve_canonical_state_and_results(
    scenario,
    player_count,
    actor_faction,
    opponent_faction,
    total,
    inside_count,
    outside_count,
    era_achieved,
    winner,
):
    runtime = _runtime()
    result = ScopeAuditTestRoutes(lambda: runtime).test_setup_scope_audit_proof(
        {"scenario": scenario}
    )

    assert set(result) == {"success", "scenario", "game_id", "player_id", "state"}
    assert result["success"] is True
    assert result["scenario"] == scenario
    game = runtime.manager.games[result["game_id"]]
    assert len(game.players) == player_count
    actor, opponent = game.players[:2]
    assert result["player_id"] == actor.id
    assert [actor.name, opponent.name] == ["Actor", "Opponent"]
    assert [actor.faction_id, opponent.faction_id] == [
        actor_faction,
        opponent_faction,
    ]
    assert game.current_player_index == 0
    expected_phase = GamePhase.FINISHED if winner else GamePhase.MAIN
    assert game.game_phase == expected_phase
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
    assert game.event_modifiers == []
    assert all(player.hand == [] for player in game.players)
    assert all(
        player.resources == {"money": 0, "propaganda": 0}
        for player in game.players
    )

    counts = result["state"]["players"][0]["organization_counts"]
    assert counts == {
        "total": total,
        "inside_wall": inside_count,
        "outside_wall": outside_count,
    }
    stage = result["state"].get("my_era_stage")
    assert (stage.get("achieved") if stage else None) is era_achieved
    assert result["state"].get("winner") == winner

    expected_towns = CANONICAL_PREFIXES[scenario]
    assert list(actor.organizations) == expected_towns
    assert actor.organizations == {town: 1 for town in expected_towns}
    assert actor.base == (
        "北京" if actor_faction == "red_army" else expected_towns[0]
    )
    assert opponent.base == ("北京" if opponent_faction == "red_army" else None)

    if scenario == "red_taiwan_with_taiwan":
        taiwan = game.players[2]
        assert (taiwan.name, taiwan.faction_id, taiwan.organizations) == (
            "Taiwan",
            "taiwan_green",
            {},
        )

    game_id = result["game_id"]
    assert game.id == game_id
    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [
        (player.id, player.name) for player in game.players
    ]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {
        player.id: player.faction_id for player in game.players
    }
    assert runtime.lobby_bases[game_id] == {}


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({}, {"error": "Unknown scope audit scenario: "}),
        ({"scenario": None}, {"error": "Unknown scope audit scenario: "}),
        (
            {"scenario": 123},
            {"error": "Unknown scope audit scenario: 123"},
        ),
        (
            {"scenario": "unknown"},
            {"error": "Unknown scope audit scenario: unknown"},
        ),
    ],
)
def test_scope_audit_unknown_scenario_preserves_coercion_and_no_store_writes(
    payload,
    expected,
):
    runtime = _runtime()

    assert (
        ScopeAuditTestRoutes(lambda: runtime).test_setup_scope_audit_proof(payload)
        == expected
    )
    assert runtime.manager.games == {}
    assert runtime.manager.connections == {}
    assert runtime.lobby == {}
    assert runtime.lobby_hosts == {}
    assert runtime.lobby_factions == {}
    assert runtime.lobby_bases == {}


def test_scope_audit_preserves_insufficient_mongolia_and_taiwan_errors(monkeypatch):
    class InsufficientGame(Game):
        def _towns_for_region_alias(self, region):
            if region in {"mongolian_plateau", "taiwan"}:
                return ["臺北"]
            return super()._towns_for_region_alias(region)

    monkeypatch.setattr(scope_audit, "Game", InsufficientGame)

    for scenario, message in [
        (
            "mongolia_outside",
            "Not enough canonical towns for Mongolia scope proof",
        ),
        (
            "red_taiwan_with_taiwan",
            "Not enough canonical Taiwan towns for Red Army victory proof",
        ),
    ]:
        runtime = _runtime()
        result = ScopeAuditTestRoutes(
            lambda: runtime
        ).test_setup_scope_audit_proof({"scenario": scenario})
        assert result == {"error": message}
        assert runtime.manager.games == {}
        assert runtime.manager.connections == {}
        assert runtime.lobby == {}
        assert runtime.lobby_hosts == {}
        assert runtime.lobby_factions == {}
        assert runtime.lobby_bases == {}


def test_scope_audit_preserves_hook_and_store_order(monkeypatch):
    events = []

    class RecordingDict(dict):
        def __init__(self, label):
            super().__init__()
            self.label = label

        def __setitem__(self, key, value):
            events.append(("store", self.label, key))
            super().__setitem__(key, value)

    class OrderedManager(FakeManager):
        def __init__(self):
            self.games = RecordingDict("games")
            self.connections = RecordingDict("connections")

    class OrderedGame(Game):
        def _check_era_trigger(self):
            events.append(("era", self.id, self.game_phase, self.turn_phase))
            return super()._check_era_trigger()

        def _check_victory(self):
            events.append(("victory", self.id, self.game_phase, self.turn_phase))
            return super()._check_victory()

        def state(self, viewer_player_id=None):
            events.append(("state", self.id, viewer_player_id))
            return super().state(viewer_player_id)

    monkeypatch.setattr(scope_audit, "Game", OrderedGame)
    runtime = GameSetupRuntime(
        manager=OrderedManager(),
        lobby=RecordingDict("lobby"),
        lobby_hosts=RecordingDict("lobby_hosts"),
        lobby_factions=RecordingDict("lobby_factions"),
        lobby_bases=RecordingDict("lobby_bases"),
    )
    result = ScopeAuditTestRoutes(lambda: runtime).test_setup_scope_audit_proof(
        {"scenario": "mongolia_outside"}
    )
    game = runtime.manager.games[result["game_id"]]

    relevant = [
        event for event in events if event[0] in {"era", "victory", "store", "state"}
    ]
    initial_hook_id = relevant[-9][1]
    assert initial_hook_id
    assert initial_hook_id != result["game_id"]
    assert relevant[-9:] == [
        ("era", initial_hook_id, GamePhase.MAIN, TurnPhase.ACTION),
        ("victory", initial_hook_id, GamePhase.MAIN, TurnPhase.ACTION),
        ("store", "games", result["game_id"]),
        ("store", "connections", result["game_id"]),
        ("store", "lobby", result["game_id"]),
        ("store", "lobby_hosts", result["game_id"]),
        ("store", "lobby_factions", result["game_id"]),
        ("store", "lobby_bases", result["game_id"]),
        ("state", result["game_id"], game.players[0].id),
    ]


def test_scope_audit_http_contract_and_openapi():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)

    response = client.post(
        "/test/setup-scope-audit-proof",
        json={"scenario": "mongolia_outside"},
    )
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "scenario",
        "game_id",
        "player_id",
        "state",
    }

    missing = client.post("/test/setup-scope-audit-proof")
    assert missing.status_code == 422
    non_object = client.post("/test/setup-scope-audit-proof", json=[])
    expected_non_object_status = 422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    assert non_object.status_code == expected_non_object_status

    operation = app.openapi()["paths"]["/test/setup-scope-audit-proof"]["post"]
    assert operation["summary"] == "Test Setup Scope Audit Proof"
    assert operation["operationId"].startswith("test_setup_scope_audit_proof_")
    assert operation["requestBody"]["required"] is True


def test_main_scope_audit_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-scope-audit-proof",
        json={"scenario": "mongolia_outside"},
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in lobby_hosts
    assert game_id in lobby_factions
    assert game_id in lobby_bases

    direct = main.test_setup_scope_audit_proof(
        {"scenario": "mongolia_inside"}
    )
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_scope_audit_proof)


def test_scope_audit_route_is_registered_once_at_original_position():
    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-scope-audit-proof"
    ]
    assert len(matching) == 1
    assert matching[0].methods == {"POST"}

    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-scope-audit-proof")
    assert paths[index - 1] == "/test/setup-negotiation-proof"
    assert paths[index + 1] == "/test/setup-inside-wall-proof"


@pytest.mark.parametrize(
    ("scenario", "expected_player_indexes", "expected_game_index"),
    [
        ("mongolia_outside", [0, 1], 5),
        ("red_taiwan_with_taiwan", [0, 1, 2], 7),
    ],
)
def test_scope_audit_uuid_order_is_stable(
    monkeypatch,
    scenario,
    expected_player_indexes,
    expected_game_index,
):
    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(scope_audit.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()

    result = ScopeAuditTestRoutes(lambda: runtime).test_setup_scope_audit_proof(
        {"scenario": scenario}
    )
    game = runtime.manager.games[result["game_id"]]

    assert [player.id for player in game.players] == [
        str(ids[index]) for index in expected_player_indexes
    ]
    assert result["game_id"] == str(ids[expected_game_index])
