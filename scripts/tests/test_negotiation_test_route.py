import ast
import inspect
import random
import re
import subprocess
import sys
import uuid
from types import SimpleNamespace

import pydantic
import pytest
from fastapi.testclient import TestClient

from server import main
from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.negotiation import NegotiationTestRoutes


ROUTE_PATH = "/test/setup-negotiation-proof"
BASELINE_MAIN_REF = "e6a7104070afe8b0fa94219f68cbb46677ed909d:server/main.py"
EXPECTED_EVENT = {
    "id": "quiet_times",
    "name": "歲月靜好",
    "type": "idle",
}
EXPECTED_PROGRESS = {
    "count": 0,
    "required": 0,
    "succeeded": True,
    "settled": True,
    "status": "idle",
}


class FakeManager:
    def __init__(self, games=None, connections=None):
        self.games = games if games is not None else {}
        self.connections = connections if connections is not None else {}


def _production_module():
    return sys.modules[main.test_setup_negotiation_proof.__module__]


def _effective_app_routes(app=main.app):
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from original_router.routes
        else:
            yield route


def _install_runtime(monkeypatch, manager=None, **stores):
    manager = manager or FakeManager()
    runtime_stores = {
        "lobby": stores.get("lobby", {}),
        "lobby_hosts": stores.get("lobby_hosts", {}),
        "lobby_factions": stores.get("lobby_factions", {}),
        "lobby_bases": stores.get("lobby_bases", {}),
    }
    monkeypatch.setattr(main, "manager", manager)
    for name, store in runtime_stores.items():
        monkeypatch.setattr(main, name, store)
    return SimpleNamespace(manager=manager, **runtime_stores)


def _assert_fixture(runtime, result):
    assert list(result) == [
        "success",
        "game_id",
        "player_id",
        "enemy_player_id",
        "state",
    ]
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    actor, ally, enemy, observer = game.players

    assert result["success"] is True
    assert result["game_id"] == game.id
    assert result["player_id"] == actor.id
    assert result["enemy_player_id"] == enemy.id
    assert [(player.name, player.faction_id) for player in game.players] == [
        ("Actor", "liberals"),
        ("Ally", "hong_kong"),
        ("Enemy", "red_army"),
        ("Observer", "taiwan_green"),
    ]
    assert [[card.name for card in player.hand] for player in game.players] == [
        ["合作談判"],
        [],
        [],
        [],
    ]
    assert [[card.name for card in player.deck.draw_pile] for player in game.players] == [
        ["ActorDraw"],
        ["AllyDraw"],
        ["EnemyDraw"],
        ["ObserverDraw"],
    ]
    assert [player.deck.discard_pile for player in game.players] == [[], [], [], []]
    assert [player.resources for player in game.players] == [
        {"money": 0, "propaganda": 0},
    ] * 4
    negotiation = actor.hand[0]
    card_def = next(card for card in game.structured_cards if card.get("name") == "合作談判")
    assert negotiation.card_type == card_def.get("type", "command")
    assert negotiation.resources == card_def.get("resources", {})

    assert game.current_player_index == 0
    assert game.game_phase == GamePhase.MAIN
    assert game.turn_phase == TurnPhase.ACTION
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.current_event == EXPECTED_EVENT
    assert game.event_progress == EXPECTED_PROGRESS
    assert game.event_notification == {
        "id": "quiet_times",
        "name": "歲月靜好",
        "type": "idle",
        "trigger": {},
        "success": {},
        "failure": {},
        "effect": {},
        "progress": EXPECTED_PROGRESS,
        "status": "idle",
        "result_text": "本次事件無效果",
        "trigger_text": "無",
        "success_text": "無",
        "failure_text": "無",
        "effect_text": "無",
    }
    assert game.event_modifiers == []

    state = result["state"]
    assert state == game.state(actor.id)
    assert state["game_phase"] == GamePhase.MAIN
    assert state["turn_phase"] == TurnPhase.ACTION
    assert state["pending_base_choices"] == {}
    assert state["pending_choice"] is None
    assert state["current_event"] == game.event_notification
    assert state["event_modifiers"] == []
    assert [entry["name"] for entry in state["players"]] == [
        "Actor",
        "Ally",
        "Enemy",
        "Observer",
    ]
    assert [entry["faction"] for entry in state["players"]] == [
        "liberals",
        "hong_kong",
        "red_army",
        "taiwan_green",
    ]
    assert [entry["hand"] for entry in state["players"]] == [["合作談判"], [], [], []]
    assert [entry["deck_count"] for entry in state["players"]] == [1, 1, 1, 1]
    assert [entry["discard_count"] for entry in state["players"]] == [0, 0, 0, 0]
    assert [entry["discard_pile"] for entry in state["players"]] == [[], [], [], []]
    assert [entry["resources"] for entry in state["players"]] == [
        {"money": 0, "propaganda": 0},
    ] * 4

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {
        player.id: player.faction_id for player in game.players
    }
    assert runtime.lobby_bases[game_id] == {}
    return game


def test_negotiation_default_fixture_response_state_and_lobby_stores(monkeypatch):
    runtime = _install_runtime(monkeypatch)
    result = main.test_setup_negotiation_proof({})
    _assert_fixture(runtime, result)


def test_negotiation_extra_payload_is_ignored(monkeypatch):
    runtime = _install_runtime(monkeypatch)
    result = main.test_setup_negotiation_proof({"unused": {"nested": True}})
    _assert_fixture(runtime, result)


class TrackingStore(dict):
    def __init__(self, label, events, initial=None):
        super().__init__(initial or {})
        self.label = label
        self.events = events

    def get(self, key, default=None):
        self.events.append(f"{self.label}.get")
        return super().get(key, default)

    def __setitem__(self, key, value):
        self.events.append(f"{self.label}.set")
        super().__setitem__(key, value)


def test_negotiation_connections_identity_and_complete_store_write_order(monkeypatch):
    fixed_game_id = str(uuid.UUID(int=101))
    ids = iter(uuid.UUID(int=value) for value in range(101, 111))
    monkeypatch.setattr(_production_module().uuid, "uuid4", ids.__next__)
    events = []
    existing_connections = {"actor": [object()]}
    games = TrackingStore("games", events)
    connections = TrackingStore(
        "connections", events, {fixed_game_id: existing_connections}
    )
    runtime = _install_runtime(
        monkeypatch,
        FakeManager(games, connections),
        lobby=TrackingStore("lobby", events),
        lobby_hosts=TrackingStore("hosts", events),
        lobby_factions=TrackingStore("factions", events),
        lobby_bases=TrackingStore("bases", events),
    )

    result = main.test_setup_negotiation_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert events == [
        "games.set",
        "connections.get",
        "connections.set",
        "lobby.set",
        "hosts.set",
        "factions.set",
        "bases.set",
    ]
    assert runtime.manager.connections[fixed_game_id] is existing_connections
    assert runtime.lobby[fixed_game_id] == [
        (player.id, player.name) for player in game.players
    ]
    assert runtime.lobby_hosts[fixed_game_id] == game.players[0].id
    assert runtime.lobby_factions[fixed_game_id] == {
        player.id: player.faction_id for player in game.players
    }
    assert runtime.lobby_bases[fixed_game_id] == {}


def test_negotiation_complete_uuid_ledger(monkeypatch):
    values = [uuid.UUID(int=value) for value in range(201, 211)]
    iterator = iter(values)
    ledger = []

    def tracked_uuid4():
        current_frame = inspect.currentframe()
        assert current_frame is not None
        caller = current_frame.f_back
        assert caller is not None
        qualname = caller.f_code.co_qualname
        if qualname == "Game.__init__":
            label = "Game.__init__.temporary_id"
        elif qualname == "Player.__init__":
            label = f"Player.__init__.temporary_id:{caller.f_locals['name']}"
        else:
            context = inspect.getframeinfo(caller).code_context
            assert context is not None
            source = context[0]
            if "game_id =" in source:
                label = "route.game_id"
            else:
                names = re.findall(r'"([A-Za-z]+)"', source)
                assert len(names) == 1
                label = f"route.player_id:{names[0]}"
        value = next(iterator)
        ledger.append((label, value))
        return value

    monkeypatch.setattr(_production_module().uuid, "uuid4", tracked_uuid4)
    runtime = _install_runtime(monkeypatch)
    result = main.test_setup_negotiation_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert ledger == [
        ("route.game_id", values[0]),
        ("route.player_id:Actor", values[1]),
        ("route.player_id:Ally", values[2]),
        ("route.player_id:Enemy", values[3]),
        ("route.player_id:Observer", values[4]),
        ("Game.__init__.temporary_id", values[5]),
        ("Player.__init__.temporary_id:Actor", values[6]),
        ("Player.__init__.temporary_id:Ally", values[7]),
        ("Player.__init__.temporary_id:Enemy", values[8]),
        ("Player.__init__.temporary_id:Observer", values[9]),
    ]
    assert result["game_id"] == str(values[0])
    assert [player.id for player in game.players] == [str(value) for value in values[1:5]]
    with pytest.raises(StopIteration):
        next(iterator)


def test_negotiation_rng_call_order_and_argument_sizes(monkeypatch):
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
    main.test_setup_negotiation_proof({})

    assert ledger == [
        ("shuffle", 59),
        ("shuffle", 4),
        ("shuffle", 11),
        ("shuffle", 10),
        ("shuffle", 10),
        ("shuffle", 10),
        ("shuffle", 12),
        ("shuffle", 64),
        ("shuffle", 181),
        ("shuffle", 53),
        ("shuffle", 53),
        ("sample", 25, 20),
        ("shuffle", 20),
    ]


class PrivacyProbeGame(Game):
    def state(self, viewer_player_id=None):
        self.players[1].hand = [Card("AllySecret", "command", {})]
        self.players[2].hand = [Card("EnemySecret", "command", {})]
        self.players[3].hand = [Card("ObserverSecret", "command", {})]
        return super().state(viewer_player_id)


def test_negotiation_response_is_viewer_scoped_and_masks_non_viewer_hands(monkeypatch):
    monkeypatch.setattr(_production_module(), "Game", PrivacyProbeGame)
    runtime = _install_runtime(monkeypatch)
    result = main.test_setup_negotiation_proof({})
    game = runtime.manager.games[result["game_id"]]

    scoped_players = result["state"]["players"]
    assert scoped_players[0]["hand"] == ["合作談判"]
    assert scoped_players[1]["hand"] == ["未知手牌"]
    assert scoped_players[2]["hand"] == ["未知手牌"]
    assert scoped_players[3]["hand"] == ["未知手牌"]
    assert scoped_players[1]["hand_variants"] == [None]
    assert scoped_players[1]["hand_action_legality"] == [None]

    unscoped_players = game.state()["players"]
    assert [player["hand"] for player in unscoped_players] == [
        ["合作談判"],
        ["AllySecret"],
        ["EnemySecret"],
        ["ObserverSecret"],
    ]


def _validation_detail(value):
    pydantic_major = int(pydantic.VERSION.split(".")[0])
    if pydantic_major >= 2:
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
def test_negotiation_http_root_body_matrix(monkeypatch, label, raw, value):
    runtime = _install_runtime(monkeypatch)
    response = TestClient(main.app).post(
        ROUTE_PATH,
        content=raw,
        headers={"content-type": "application/json"},
    )
    pydantic_major = int(pydantic.VERSION.split(".")[0])
    pydantic_one_coerces_to_empty_dict = pydantic_major == 1 and value in ("", [])

    if pydantic_one_coerces_to_empty_dict:
        assert response.status_code == 200, label
        _assert_fixture(runtime, response.json())
    else:
        assert response.status_code == 422, label
        assert response.json() == _validation_detail(value)
        assert runtime.manager.games == {}


def test_negotiation_http_missing_empty_extra_openapi_and_route_adjacency(monkeypatch):
    runtime = _install_runtime(monkeypatch)
    client = TestClient(main.app)

    missing = client.post(ROUTE_PATH)
    assert missing.status_code == 422
    assert missing.json() == _validation_detail(None)

    empty = client.post(ROUTE_PATH, json={})
    assert empty.status_code == 200
    _assert_fixture(runtime, empty.json())
    extra = client.post(ROUTE_PATH, json={"extra": [1, 2, 3]})
    assert extra.status_code == 200
    _assert_fixture(runtime, extra.json())

    operation = main.app.openapi()["paths"][ROUTE_PATH]["post"]
    assert operation["summary"] == "Test Setup Negotiation Proof"
    assert (
        operation["operationId"]
        == "test_setup_negotiation_proof_test_setup_negotiation_proof_post"
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
    assert operation["responses"] == {
        "200": {
            "description": "Successful Response",
            "content": {"application/json": {"schema": {}}},
        },
        "422": {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                }
            },
        },
    }

    routes = list(_effective_app_routes())
    matching = [route for route in routes if getattr(route, "path", None) == ROUTE_PATH]
    assert len(matching) == 1
    assert matching[0].methods == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index(ROUTE_PATH)
    assert paths[index - 1] == "/test/setup-build-queue-proof"
    assert paths[index + 1] == "/test/setup-scope-audit-proof"


def test_negotiation_main_http_and_callable_use_late_bound_replacements(monkeypatch):
    first = _install_runtime(monkeypatch)
    first_response = TestClient(main.app).post(ROUTE_PATH, json={})
    assert first_response.status_code == 200
    first_game_id = first_response.json()["game_id"]
    assert first_game_id in first.manager.games

    second = _install_runtime(monkeypatch)
    second_response = TestClient(main.app).post(ROUTE_PATH, json={})
    assert second_response.status_code == 200
    second_game_id = second_response.json()["game_id"]
    assert second_game_id in second.manager.games
    assert second_game_id not in first.manager.games

    direct = main.test_setup_negotiation_proof({})
    assert direct["game_id"] in second.manager.games
    assert direct["game_id"] not in first.manager.games
    assert callable(main.test_setup_negotiation_proof)
    assert main.test_setup_negotiation_proof.__self__ is main._negotiation_test_routes
    assert (
        main.test_setup_negotiation_proof.__func__
        is NegotiationTestRoutes.test_setup_negotiation_proof
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
            and node.name == "test_setup_negotiation_proof"
        ),
        None,
    )
    assert function is not None, (
        f"test_setup_negotiation_proof missing from reviewed base {BASELINE_MAIN_REF}"
    )
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, BASELINE_MAIN_REF, "exec"), namespace)
    return namespace["test_setup_negotiation_proof"]


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
                "hand": [card.name for card in player.hand],
                "draw": [card.name for card in player.deck.draw_pile],
                "discard": [card.name for card in player.deck.discard_pile],
                "resources": player.resources,
            }
            for player in game.players
        ],
        "purchase_deck": [card.name for card in game.purchase_deck.draw_pile],
        "purchase_area": [card.name for card in game.purchase_area],
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


def test_negotiation_seeded_reviewed_base_deterministic_differential(monkeypatch):
    original_uuid4 = uuid.uuid4

    def run(handler, runtime, seed):
        values = iter(uuid.UUID(int=value) for value in range(301, 311))
        monkeypatch.setattr(uuid, "uuid4", values.__next__)
        random.seed(seed)
        result = handler({})
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
    namespace = {
        "uuid": uuid,
        "Game": Game,
        "Card": Card,
        "GamePhase": GamePhase,
        "TurnPhase": TurnPhase,
        **vars(old_runtime),
    }
    old_handler = _load_baseline_handler(namespace)
    old_snapshot, old_random_state = run(old_handler, old_runtime, 97531)

    monkeypatch.setattr(uuid, "uuid4", original_uuid4)
    new_runtime = _install_runtime(monkeypatch)
    new_snapshot, new_random_state = run(
        main.test_setup_negotiation_proof, new_runtime, 97531
    )

    assert new_snapshot == old_snapshot
    assert new_random_state == old_random_state
