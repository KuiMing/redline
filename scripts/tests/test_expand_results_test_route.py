import ast
import inspect
import random
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pydantic
import pytest
from fastapi.testclient import TestClient

from server import main
from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.expand_results import ExpandResultsTestRoutes


ROUTE_PATH = "/test/setup-expand-results-proof"
BASELINE_MAIN_REF = "43762fe4580f7214d629565b88e2e95a040588ba:server/main.py"
PROOF_LOG = (
    "[Turn 1] UI proof setup: viewer has 擴大戰果; discard pile contains "
    "宣傳家 / 合作談判 / 走漏風聲."
)
DEFAULT_DRAW = ["抽牌A", "抽牌B"]
DEFAULT_DISCARD = ["宣傳家", "合作談判", "走漏風聲"]


class FakeManager:
    def __init__(self, games=None, connections=None):
        self.games = games if games is not None else {}
        self.connections = connections if connections is not None else {}


def _production_module():
    return sys.modules[main.test_setup_expand_results_proof.__module__]


def _effective_app_routes(app=main.app):
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from original_router.routes
        else:
            yield route


def _install_runtime(monkeypatch, manager=None, **stores):
    manager = manager or FakeManager()
    values = {
        "lobby": stores.get("lobby", {}),
        "lobby_hosts": stores.get("lobby_hosts", {}),
        "lobby_factions": stores.get("lobby_factions", {}),
        "lobby_bases": stores.get("lobby_bases", {}),
    }
    monkeypatch.setattr(main, "manager", manager)
    for name, store in values.items():
        monkeypatch.setattr(main, name, store)
    return SimpleNamespace(manager=manager, **values)


def _card_names(cards):
    return [card.name for card in cards]


def _assert_default_fixture(runtime, result):
    assert list(result) == ["success", "game_id", "player_id", "players", "state"]
    assert result["success"] is True
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, enemy = game.players

    assert game.id == game_id
    assert result["player_id"] == viewer.id
    assert [(player.name, player.faction_id, player.base) for player in game.players] == [
        ("viewer", "red_army", "北京"),
        ("enemy", "hong_kong", "香港城"),
    ]
    assert viewer.organizations == {"北京": 1}
    assert enemy.organizations == {"香港城": 1}
    assert _card_names(viewer.hand) == ["擴大戰果"]
    assert _card_names(viewer.deck.draw_pile) == DEFAULT_DRAW
    assert _card_names(viewer.deck.discard_pile) == DEFAULT_DISCARD
    assert _card_names(enemy.hand) == ["對手手牌A"]
    assert _card_names(enemy.deck.draw_pile) == ["對手抽牌A"]
    assert enemy.deck.discard_pile == []
    assert viewer.resources == enemy.resources == {"money": 0, "propaganda": 0}
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.action_log[-1] == PROOF_LOG

    assert result["players"] == [
        {
            "id": player.id,
            "name": player.name,
            "faction": player.faction_id,
            "base": player.base,
        }
        for player in game.players
    ]
    assert result["state"] == game.state()
    state_players = result["state"]["players"]
    assert state_players[0]["hand"] == ["擴大戰果"]
    assert state_players[1]["hand"] == ["對手手牌A"]
    assert state_players[0]["deck_count"] == 2
    assert state_players[0]["discard_pile"] == DEFAULT_DISCARD
    assert result["state"]["game_phase"] == GamePhase.MAIN
    assert result["state"]["turn_phase"] == TurnPhase.ACTION
    assert result["state"]["pending_base_choices"] == {}
    assert result["state"]["action_log"][-1] == PROOF_LOG
    return game


def test_expand_results_default_fixture_response_and_unscoped_state(monkeypatch):
    runtime = _install_runtime(monkeypatch)
    result = main.test_setup_expand_results_proof({})
    game = _assert_default_fixture(runtime, result)

    # The legacy route deliberately calls state() without a viewer scope.  Both
    # private hands are therefore visible in its proof response.
    assert [player["hand"] for player in result["state"]["players"]] == [
        ["擴大戰果"],
        ["對手手牌A"],
    ]
    assert game.state(game.players[0].id)["players"][1]["hand"] == ["未知手牌"]


def test_expand_results_custom_fields_and_proof_card_metadata_are_copied(monkeypatch):
    runtime = _install_runtime(monkeypatch)
    draw_names = ["合作談判", "自訂抽牌"]
    discard_names = ["走漏風聲", "自訂棄牌"]
    result = main.test_setup_expand_results_proof(
        {
            "viewer_faction": "liberals",
            "viewer_base": "上海",
            "enemy_faction": "taiwan_green",
            "enemy_base": "臺北",
            "draw_pile": draw_names,
            "discard_pile": discard_names,
        }
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, enemy = game.players

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "上海",
        {"上海": 1},
    )
    assert (enemy.faction_id, enemy.base, enemy.organizations) == (
        "taiwan_green",
        "臺北",
        {"臺北": 1},
    )
    assert _card_names(viewer.deck.draw_pile) == draw_names
    assert _card_names(viewer.deck.discard_pile) == discard_names

    for card in (viewer.hand[0], viewer.deck.draw_pile[0], viewer.deck.discard_pile[0]):
        definition = next(
            item for item in game.structured_cards if item.get("name") == card.name
        )
        assert card.card_type == definition["type"]
        assert card.resources == definition["resources"]
        assert card.resources is not definition["resources"]

    for card in (viewer.deck.draw_pile[1], viewer.deck.discard_pile[1]):
        assert (card.card_type, card.resources) == (
            "command",
            {"money": 0, "propaganda": 0},
        )

    copied_resources = dict(viewer.hand[0].resources)
    definition = next(
        item for item in game.structured_cards if item.get("name") == "擴大戰果"
    )
    definition["resources"]["money"] = 999
    draw_names.append("late draw")
    discard_names.append("late discard")
    assert viewer.hand[0].resources == copied_resources
    assert _card_names(viewer.deck.draw_pile) == ["合作談判", "自訂抽牌"]
    assert _card_names(viewer.deck.discard_pile) == ["走漏風聲", "自訂棄牌"]


@pytest.mark.parametrize(
    ("field", "player_index", "attribute", "response_key"),
    [
        ("viewer_faction", 0, "faction_id", "faction"),
        ("viewer_base", 0, "base", "base"),
        ("enemy_faction", 1, "faction_id", "faction"),
        ("enemy_base", 1, "base", "base"),
    ],
)
@pytest.mark.parametrize("value", [None, False, 0, ""])
def test_expand_results_http_preserves_falsy_faction_and_base_fields(
    monkeypatch, field, player_index, attribute, response_key, value
):
    runtime = _install_runtime(monkeypatch)
    response = TestClient(main.app).post(ROUTE_PATH, json={field: value})
    assert response.status_code == 200
    result = response.json()
    player = runtime.manager.games[result["game_id"]].players[player_index]
    assert getattr(player, attribute) == value
    assert result["players"][player_index][response_key] == value
    if attribute == "base":
        assert player.organizations == {value: 1}


@pytest.mark.parametrize(
    ("field", "value", "status", "names"),
    [
        ("draw_pile", None, 500, None),
        ("draw_pile", [], 200, []),
        ("draw_pile", {}, 200, []),
        ("draw_pile", False, 500, None),
        ("draw_pile", 0, 500, None),
        ("draw_pile", 7, 500, None),
        ("draw_pile", "", 200, []),
        ("draw_pile", "AB", 200, ["A", "B"]),
        ("draw_pile", {"A": 1}, 200, ["A"]),
        ("discard_pile", None, 200, DEFAULT_DISCARD),
        ("discard_pile", [], 200, DEFAULT_DISCARD),
        ("discard_pile", {}, 200, DEFAULT_DISCARD),
        ("discard_pile", False, 200, DEFAULT_DISCARD),
        ("discard_pile", 0, 200, DEFAULT_DISCARD),
        ("discard_pile", 7, 500, None),
        ("discard_pile", "", 200, DEFAULT_DISCARD),
        ("discard_pile", "AB", 200, ["A", "B"]),
        ("discard_pile", {"A": 1}, 200, ["A"]),
    ],
)
def test_expand_results_http_pile_field_real_coercion(
    monkeypatch, field, value, status, names
):
    runtime = _install_runtime(monkeypatch)
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.post(ROUTE_PATH, json={field: value})
    assert response.status_code == status
    if status == 500:
        assert response.text == "Internal Server Error"
        assert runtime.manager.games == {}
    else:
        game = runtime.manager.games[response.json()["game_id"]]
        assert _card_names(getattr(game.players[0].deck, field)) == names


class RecordingStore(dict):
    def __init__(self, label, events, initial=None, fail=False):
        super().__init__(initial or {})
        self.label = label
        self.events = events
        self.fail = fail

    def get(self, key, default=None):
        self.events.append((self.label, "get", key))
        return super().get(key, default)

    def __setitem__(self, key, value):
        self.events.append((self.label, "set", key))
        if self.fail:
            raise RuntimeError(f"fail:{self.label}")
        super().__setitem__(key, value)


def _recording_runtime(monkeypatch, failing=None, existing_connections=None):
    events = []
    game_id = str(uuid.UUID(int=101))
    games = RecordingStore("games", events, fail=failing == "games")
    connections = RecordingStore(
        "connections",
        events,
        {game_id: existing_connections} if existing_connections is not None else None,
        fail=failing == "connections",
    )
    stores = {
        "lobby": RecordingStore("lobby", events, fail=failing == "lobby"),
        "lobby_hosts": RecordingStore(
            "lobby_hosts", events, fail=failing == "lobby_hosts"
        ),
        "lobby_factions": RecordingStore(
            "lobby_factions", events, fail=failing == "lobby_factions"
        ),
        "lobby_bases": RecordingStore(
            "lobby_bases", events, fail=failing == "lobby_bases"
        ),
    }
    runtime = _install_runtime(
        monkeypatch, FakeManager(games, connections), **stores
    )
    return runtime, events


def test_expand_results_store_values_order_and_connection_collision_identity(monkeypatch):
    existing_connections = {"socket": object()}
    runtime, events = _recording_runtime(
        monkeypatch, existing_connections=existing_connections
    )
    ids = iter(uuid.UUID(int=value) for value in range(101, 107))
    monkeypatch.setattr(_production_module().uuid, "uuid4", ids.__next__)

    result = main.test_setup_expand_results_proof({})
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, enemy = game.players

    assert [(label, action) for label, action, _ in events] == [
        ("games", "set"),
        ("connections", "get"),
        ("connections", "set"),
        ("lobby", "set"),
        ("lobby_hosts", "set"),
        ("lobby_factions", "set"),
        ("lobby_bases", "set"),
    ]
    assert runtime.manager.connections[game_id] is existing_connections
    assert runtime.lobby[game_id] == [(viewer.id, "viewer"), (enemy.id, "enemy")]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: viewer.faction_id,
        enemy.id: enemy.faction_id,
    }
    assert runtime.lobby_bases[game_id] == {
        viewer.id: viewer.base,
        enemy.id: enemy.base,
    }


@pytest.mark.parametrize(
    ("failing", "completed"),
    [
        ("games", []),
        ("connections", ["games"]),
        ("lobby", ["games", "connections"]),
        ("lobby_hosts", ["games", "connections", "lobby"]),
        (
            "lobby_factions",
            ["games", "connections", "lobby", "lobby_hosts"],
        ),
        (
            "lobby_bases",
            ["games", "connections", "lobby", "lobby_hosts", "lobby_factions"],
        ),
    ],
)
def test_expand_results_store_failures_preserve_partial_write_order(
    monkeypatch, failing, completed
):
    runtime, events = _recording_runtime(monkeypatch, failing=failing)
    with pytest.raises(RuntimeError, match=f"fail:{failing}"):
        main.test_setup_expand_results_proof({})
    successful_sets = []
    for label, action, key in events:
        if action == "set" and label != failing:
            successful_sets.append(label)
    assert successful_sets == completed
    assert list(runtime.manager.games) == ([next(iter(runtime.manager.games))] if "games" in completed else [])


def test_expand_results_complete_six_uuid_ledger(monkeypatch):
    values = [uuid.UUID(int=value) for value in range(201, 207)]
    iterator = iter(values)
    ledger = []

    def tracked_uuid4():
        caller = inspect.currentframe().f_back
        assert caller is not None
        qualname = caller.f_code.co_qualname
        if qualname == "Game.__init__":
            label = "Game.__init__.temporary_id"
        elif qualname == "Player.__init__":
            label = f"Player.__init__.temporary_id:{caller.f_locals['name']}"
        else:
            line = inspect.getframeinfo(caller).code_context[0]
            if "game_id =" in line:
                label = "route.game_id"
            elif '"viewer"' in line:
                label = "route.viewer_id"
            elif '"enemy"' in line:
                label = "route.enemy_id"
            else:
                label = f"unexpected:{qualname}:{line.strip()}"
        value = next(iterator)
        ledger.append((label, value))
        return value

    monkeypatch.setattr(_production_module().uuid, "uuid4", tracked_uuid4)
    runtime = _install_runtime(monkeypatch)
    result = main.test_setup_expand_results_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert ledger == [
        ("route.game_id", values[0]),
        ("route.viewer_id", values[1]),
        ("route.enemy_id", values[2]),
        ("Game.__init__.temporary_id", values[3]),
        ("Player.__init__.temporary_id:viewer", values[4]),
        ("Player.__init__.temporary_id:enemy", values[5]),
    ]
    assert result["game_id"] == str(values[0])
    assert [player.id for player in game.players] == [str(values[1]), str(values[2])]
    with pytest.raises(StopIteration):
        next(iterator)


def test_expand_results_rng_ledger(monkeypatch):
    ledger = []
    original_shuffle = random.shuffle
    original_sample = random.sample

    def tracked_shuffle(sequence):
        ledger.append(("shuffle", len(sequence)))
        return original_shuffle(sequence)

    def tracked_sample(population, count):
        ledger.append(("sample", len(population), count))
        return original_sample(population, count)

    monkeypatch.setattr(random, "shuffle", tracked_shuffle)
    monkeypatch.setattr(random, "sample", tracked_sample)
    _install_runtime(monkeypatch)
    random.seed(24680)
    main.test_setup_expand_results_proof({})

    assert ledger == [
        ("shuffle", 59),
        ("shuffle", 2),
        ("shuffle", 11),
        ("shuffle", 10),
        ("shuffle", 64),
        ("shuffle", 181),
        ("shuffle", 53),
        ("shuffle", 53),
        ("sample", 25, 20),
        ("shuffle", 20),
    ]


def _validation_detail(value):
    major = int(pydantic.VERSION.split(".")[0])
    if major >= 2:
        if value is None:
            return {
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["body"],
                        "msg": "Field required",
                        "input": None,
                    }
                ]
            }
        return {
            "detail": [
                {
                    "type": "dict_type",
                    "loc": ["body"],
                    "msg": "Input should be a valid dictionary",
                    "input": value,
                }
            ]
        }
    if value is None:
        return {
            "detail": [
                {
                    "loc": ["body"],
                    "msg": "field required",
                    "type": "value_error.missing",
                }
            ]
        }
    return {
        "detail": [
            {
                "loc": ["body"],
                "msg": "value is not a valid dict",
                "type": "type_error.dict",
            }
        ]
    }


@pytest.mark.parametrize(
    ("label", "raw", "value"),
    [
        ("null", "null", None),
        ("false", "false", False),
        ("zero", "0", 0),
        ("empty-string", '\"\"', ""),
        ("empty-list", "[]", []),
        ("truthy-string", '\"truthy\"', "truthy"),
        ("truthy-number", "7", 7),
    ],
)
def test_expand_results_http_root_body_matrix(monkeypatch, label, raw, value):
    runtime = _install_runtime(monkeypatch)
    response = TestClient(main.app).post(
        ROUTE_PATH,
        content=raw,
        headers={"content-type": "application/json"},
    )
    pydantic_one_success = int(pydantic.VERSION.split(".")[0]) == 1 and value in (
        "",
        [],
    )
    if pydantic_one_success:
        assert response.status_code == 200, label
        _assert_default_fixture(runtime, response.json())
    else:
        assert response.status_code == 422, label
        assert response.json() == _validation_detail(value)
        assert runtime.manager.games == {}


def test_expand_results_http_missing_empty_extra_openapi_and_adjacency(monkeypatch):
    runtime = _install_runtime(monkeypatch)
    client = TestClient(main.app)
    missing = client.post(ROUTE_PATH)
    assert missing.status_code == 422
    assert missing.json() == _validation_detail(None)

    for body in ({}, {"extra": [1, 2, 3]}):
        response = client.post(ROUTE_PATH, json=body)
        assert response.status_code == 200
        _assert_default_fixture(runtime, response.json())

    operation = main.app.openapi()["paths"][ROUTE_PATH]["post"]
    assert operation["summary"] == "Test Setup Expand Results Proof"
    assert (
        operation["operationId"]
        == "test_setup_expand_results_proof_test_setup_expand_results_proof_post"
    )
    assert operation["requestBody"]["required"] is True
    body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    if int(pydantic.VERSION.split(".")[0]) >= 2:
        assert body_schema == {
            "additionalProperties": True,
            "type": "object",
            "title": "Payload",
        }
    else:
        assert body_schema == {"title": "Payload", "type": "object"}
    assert set(operation["responses"]) == {"200", "422"}

    routes = list(_effective_app_routes())
    matching = [route for route in routes if getattr(route, "path", None) == ROUTE_PATH]
    assert len(matching) == 1
    assert matching[0].methods == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index(ROUTE_PATH)
    assert paths[index - 1] == "/test/setup-press-advantage-proof"
    assert paths[index + 1] == "/test/setup-intel-network-cancel-reaction-proof"


def test_expand_results_main_http_and_callable_use_late_bound_replacements(monkeypatch):
    first = _install_runtime(monkeypatch)
    first_response = TestClient(main.app).post(ROUTE_PATH, json={})
    assert first_response.status_code == 200
    first_id = first_response.json()["game_id"]
    assert first_id in first.manager.games

    second = _install_runtime(monkeypatch)
    second_response = TestClient(main.app).post(ROUTE_PATH, json={"viewer_base": "上海"})
    assert second_response.status_code == 200
    second_id = second_response.json()["game_id"]
    assert second_id in second.manager.games
    assert second_id not in first.manager.games
    assert second.manager.games[second_id].players[0].base == "上海"

    direct = main.test_setup_expand_results_proof({"enemy_base": "臺北"})
    assert direct["game_id"] in second.manager.games
    assert direct["game_id"] not in first.manager.games
    assert second.manager.games[direct["game_id"]].players[1].base == "臺北"
    assert callable(main.test_setup_expand_results_proof)
    assert not inspect.iscoroutinefunction(main.test_setup_expand_results_proof)
    assert isinstance(main.test_setup_expand_results_proof.__self__, ExpandResultsTestRoutes)
    assert (
        main.test_setup_expand_results_proof.__func__
        is ExpandResultsTestRoutes.test_setup_expand_results_proof
    )


def test_expand_results_body_is_structurally_identical_to_immutable_base():
    baseline_source = subprocess.run(
        ["git", "show", BASELINE_MAIN_REF],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    baseline_tree = ast.parse(baseline_source)
    baseline = next(
        (
            node
            for node in baseline_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_setup_expand_results_proof"
        ),
        None,
    )
    assert baseline is not None, (
        f"test_setup_expand_results_proof missing from reviewed base {BASELINE_MAIN_REF}"
    )

    extracted_tree = ast.parse(Path(_production_module().__file__).read_text())
    extracted = next(
        (
            node
            for node in ast.walk(extracted_tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_setup_expand_results_proof"
        ),
        None,
    )
    assert extracted is not None
    assert isinstance(extracted.body[0], ast.Assign)

    class NormalizeRuntime(ast.NodeTransformer):
        def visit_Attribute(self, node):
            node = self.generic_visit(node)
            if isinstance(node.value, ast.Name) and node.value.id == "runtime":
                return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
            return node

    normalized = NormalizeRuntime().visit(
        ast.Module(body=extracted.body[1:], type_ignores=[])
    )
    expected = ast.Module(body=baseline.body, type_ignores=[])
    ast.fix_missing_locations(normalized)
    ast.fix_missing_locations(expected)
    assert ast.dump(normalized, include_attributes=False) == ast.dump(
        expected, include_attributes=False
    )


def _load_baseline_handler(namespace):
    source = subprocess.run(
        ["git", "show", BASELINE_MAIN_REF],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    tree = ast.parse(source)
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "test_setup_expand_results_proof"
        ),
        None,
    )
    assert function is not None, (
        f"test_setup_expand_results_proof missing from reviewed base {BASELINE_MAIN_REF}"
    )
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, BASELINE_MAIN_REF, "exec"), namespace)
    return namespace["test_setup_expand_results_proof"]


def _snapshot(result, runtime):
    game = runtime.manager.games[result["game_id"]]
    return {
        "result": result,
        "unscoped_state": game.state(),
        "players": [
            {
                "id": player.id,
                "name": player.name,
                "faction": player.faction_id,
                "base": player.base,
                "organizations": player.organizations,
                "hand": _card_names(player.hand),
                "draw": _card_names(player.deck.draw_pile),
                "discard": _card_names(player.deck.discard_pile),
                "resources": player.resources,
            }
            for player in game.players
        ],
        "purchase_deck": _card_names(game.purchase_deck.draw_pile),
        "purchase_area": _card_names(game.purchase_area),
        "event_draw": [event.get("name") for event in game.event_deck.draw_pile],
        "event_discard": [event.get("name") for event in game.event_deck.discard_pile],
        "stores": {
            "connections": runtime.manager.connections,
            "lobby": runtime.lobby,
            "hosts": runtime.lobby_hosts,
            "factions": runtime.lobby_factions,
            "bases": runtime.lobby_bases,
        },
    }


def test_expand_results_seeded_immutable_base_differential(monkeypatch):
    original_uuid4 = uuid.uuid4

    def run(handler, runtime):
        values = iter(uuid.UUID(int=value) for value in range(301, 307))
        monkeypatch.setattr(uuid, "uuid4", values.__next__)
        random.seed(97531)
        result = handler(
            {
                "viewer_faction": "liberals",
                "viewer_base": "上海",
                "enemy_faction": "taiwan_green",
                "enemy_base": "臺北",
                "draw_pile": ["合作談判", "自訂抽牌"],
                "discard_pile": ["走漏風聲", "自訂棄牌"],
            }
        )
        snapshot = _snapshot(result, runtime)
        random_state = random.getstate()
        with pytest.raises(StopIteration):
            next(values)
        return snapshot, random_state

    old_runtime = SimpleNamespace(
        manager=FakeManager(),
        lobby={},
        lobby_hosts={},
        lobby_factions={},
        lobby_bases={},
    )
    old_handler = _load_baseline_handler(
        {
            "uuid": uuid,
            "Game": Game,
            "Card": Card,
            "GamePhase": GamePhase,
            "TurnPhase": TurnPhase,
            **vars(old_runtime),
        }
    )
    old_snapshot, old_random_state = run(old_handler, old_runtime)

    monkeypatch.setattr(uuid, "uuid4", original_uuid4)
    new_runtime = _install_runtime(monkeypatch)
    new_snapshot, new_random_state = run(
        main.test_setup_expand_results_proof, new_runtime
    )
    assert new_snapshot == old_snapshot
    assert new_random_state == old_random_state
