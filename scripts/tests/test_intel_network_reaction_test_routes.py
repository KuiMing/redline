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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.intel_network_reaction import IntelNetworkReactionTestRoutes
from server.test_routes.runtime import GameSetupRuntime


SETUP_PATH = "/test/setup-intel-network-cancel-reaction-proof"
RESOLVE_PATH = "/test/resolve-intel-network-cancel-reaction-proof"
BASELINE_MAIN_REF = "95f1a810fc21627596395aba09e3e30f086ab067:server/main.py"
DEFAULT_LOG = (
    "[Turn 1] 情報網取消反應測試：actor 準備打出 領導；"
    "reactor 手牌有 情報網 可取消。"
)


class FakeManager:
    def __init__(self, games=None, connections=None):
        self.games = games if games is not None else {}
        self.connections = connections if connections is not None else {}

    def get_game(self, game_id):
        return self.games.get(game_id)


def _runtime(manager=None, **stores):
    return GameSetupRuntime(
        manager=manager or FakeManager(),
        lobby=stores.get("lobby", {}),
        lobby_hosts=stores.get("lobby_hosts", {}),
        lobby_factions=stores.get("lobby_factions", {}),
        lobby_bases=stores.get("lobby_bases", {}),
    )


def _install_runtime(monkeypatch, runtime=None):
    runtime = runtime or _runtime()
    monkeypatch.setattr(main, "manager", runtime.manager)
    for name in ("lobby", "lobby_hosts", "lobby_factions", "lobby_bases"):
        monkeypatch.setattr(main, name, getattr(runtime, name))
    return runtime


def _make_app(runtime_provider):
    routes = IntelNetworkReactionTestRoutes(runtime_provider)
    app = FastAPI()
    app.include_router(routes.router)
    return app


def _effective_app_routes(app=main.app):
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from original_router.routes
        else:
            yield route


def _card_names(cards):
    return [card.name for card in cards]


def _assert_default_setup(runtime, result):
    assert list(result) == [
        "success", "game_id", "actor_id", "reactor_id", "players", "state"
    ]
    assert result["success"] is True
    game = runtime.manager.games[result["game_id"]]
    actor, reactor = game.players
    assert game.id == result["game_id"]
    assert result["actor_id"] == actor.id
    assert result["reactor_id"] == reactor.id
    assert [(p.name, p.faction_id, p.base) for p in game.players] == [
        ("actor", "hong_kong", "香港城"),
        ("reactor", "red_army", "北京"),
    ]
    assert actor.organizations == {"香港城": 1}
    assert reactor.organizations == {"北京": 1}
    assert _card_names(actor.hand) == ["領導"]
    assert _card_names(actor.deck.draw_pile) == ["ShouldNotDraw"]
    assert _card_names(reactor.hand) == ["情報網"]
    assert _card_names(reactor.deck.draw_pile) == ["IntelShouldNotDrawBonus"]
    for player in game.players:
        assert player.deck.discard_pile == []
        assert player.resources == {"money": 0, "propaganda": 0}
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.pending_choice is None
    assert game.action_log[-1] == DEFAULT_LOG
    assert result["players"] == [
        {"id": p.id, "name": p.name, "faction": p.faction_id}
        for p in game.players
    ]
    assert result["state"] == game.state()
    assert [p["hand"] for p in result["state"]["players"]] == [["領導"], ["情報網"]]
    assert game.state(actor.id)["players"][1]["hand"] == ["未知手牌"]
    return game


def test_setup_default_fixture_unscoped_state_and_stores():
    runtime = _runtime()
    result = IntelNetworkReactionTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_cancel_reaction_proof({})
    game = _assert_default_setup(runtime, result)
    actor, reactor = game.players
    game_id = game.id
    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(actor.id, "actor"), (reactor.id, "reactor")]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {
        actor.id: "hong_kong", reactor.id: "red_army"
    }
    assert runtime.lobby_bases[game_id] == {actor.id: "香港城", reactor.id: "北京"}


def test_setup_custom_fixture_and_proof_card_metadata_are_copied():
    runtime = _runtime()
    payload = {
        "actor_card": "合作談判",
        "reaction_card": "走漏風聲",
        "actor_faction": "liberals",
        "actor_base": "上海",
        "actor_draw_top": "宣傳家",
        "reactor_faction": "taiwan_green",
        "reactor_base": "臺北",
        "reactor_draw_top": "自訂反應抽牌",
    }
    result = IntelNetworkReactionTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_cancel_reaction_proof(payload)
    game = runtime.manager.games[result["game_id"]]
    actor, reactor = game.players
    assert (actor.faction_id, actor.base, actor.organizations) == (
        "liberals", "上海", {"上海": 1}
    )
    assert (reactor.faction_id, reactor.base, reactor.organizations) == (
        "taiwan_green", "臺北", {"臺北": 1}
    )
    cards = [actor.hand[0], actor.deck.draw_pile[0], reactor.hand[0]]
    for card in cards:
        definition = next(c for c in game.structured_cards if c.get("name") == card.name)
        assert card.card_type == definition.get("type", "command")
        assert card.resources == dict(definition.get("resources", {}) or {})
        assert card.resources is not definition.get("resources")
    fallback = reactor.deck.draw_pile[0]
    assert (fallback.name, fallback.card_type, fallback.resources) == (
        "自訂反應抽牌", "command", {"money": 0, "propaganda": 0}
    )
    copied = dict(cards[0].resources)
    definition = next(c for c in game.structured_cards if c.get("name") == cards[0].name)
    definition["resources"]["money"] = 999
    assert cards[0].resources == copied
    assert game.action_log[-1] == (
        "[Turn 1] 走漏風聲取消反應測試：actor 準備打出 合作談判；"
        "reactor 手牌有 走漏風聲 可取消。"
    )


@pytest.mark.parametrize(
    ("field", "player_index", "attribute"),
    [
        ("actor_faction", 0, "faction_id"),
        ("actor_base", 0, "base"),
        ("reactor_faction", 1, "faction_id"),
        ("reactor_base", 1, "base"),
    ],
)
@pytest.mark.parametrize("value", [None, False, 0, "", "truthy"])
def test_setup_payload_faction_and_base_get_semantics(field, player_index, attribute, value):
    runtime = _runtime()
    result = IntelNetworkReactionTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_cancel_reaction_proof({field: value})
    player = runtime.manager.games[result["game_id"]].players[player_index]
    assert getattr(player, attribute) == value
    if attribute == "base":
        assert player.organizations == {value: 1}


@pytest.mark.parametrize(
    ("field", "player_index", "zone"),
    [
        ("actor_card", 0, "hand"),
        ("reaction_card", 1, "hand"),
        ("actor_draw_top", 0, "draw"),
        ("reactor_draw_top", 1, "draw"),
    ],
)
@pytest.mark.parametrize("value", [None, False, 0, "", "truthy", 7])
def test_setup_payload_card_name_get_semantics(field, player_index, zone, value):
    runtime = _runtime()
    result = IntelNetworkReactionTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_cancel_reaction_proof({field: value})
    player = runtime.manager.games[result["game_id"]].players[player_index]
    cards = player.hand if zone == "hand" else player.deck.draw_pile
    assert cards[0].name == value


class RecordingStore(dict):
    def __init__(self, label, events, initial=None):
        super().__init__(initial or {})
        self.label = label
        self.events = events

    def get(self, key, default=None):
        self.events.append((self.label, "get", key))
        return super().get(key, default)

    def __setitem__(self, key, value):
        self.events.append((self.label, "set", key))
        super().__setitem__(key, value)


def test_setup_store_and_response_order_and_connection_identity(monkeypatch):
    events = []
    game_id = str(uuid.UUID(int=1))
    existing = {"socket": object()}
    manager = FakeManager(
        RecordingStore("games", events),
        RecordingStore("connections", events, {game_id: existing}),
    )
    runtime = _runtime(
        manager,
        lobby=RecordingStore("lobby", events),
        lobby_hosts=RecordingStore("hosts", events),
        lobby_factions=RecordingStore("factions", events),
        lobby_bases=RecordingStore("bases", events),
    )
    values = iter(uuid.UUID(int=i) for i in range(1, 7))
    import server.test_routes.intel_network_reaction as production
    monkeypatch.setattr(production.uuid, "uuid4", values.__next__)
    result = IntelNetworkReactionTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_cancel_reaction_proof({})
    assert [(label, action) for label, action, _ in events] == [
        ("games", "set"), ("connections", "get"), ("connections", "set"),
        ("lobby", "set"), ("hosts", "set"), ("factions", "set"), ("bases", "set"),
    ]
    assert runtime.manager.connections[game_id] is existing
    assert list(result) == [
        "success", "game_id", "actor_id", "reactor_id", "players", "state"
    ]


def test_setup_complete_six_uuid_and_rng_ledgers(monkeypatch):
    import server.test_routes.intel_network_reaction as production
    ids = [uuid.UUID(int=i) for i in range(11, 17)]
    iterator = iter(ids)
    uuid_ledger = []

    def tracked_uuid4():
        caller = inspect.currentframe().f_back
        qualname = caller.f_code.co_qualname
        if qualname == "Game.__init__":
            label = "Game.__init__.temporary_id"
        elif qualname == "Player.__init__":
            label = f"Player.__init__.temporary_id:{caller.f_locals['name']}"
        else:
            line = inspect.getframeinfo(caller).code_context[0]
            label = "route.game_id" if "game_id =" in line else (
                "route.actor_id" if '"actor"' in line else "route.reactor_id"
            )
        value = next(iterator)
        uuid_ledger.append((label, value))
        return value

    rng_ledger = []
    original_shuffle, original_sample = random.shuffle, random.sample
    monkeypatch.setattr(production.uuid, "uuid4", tracked_uuid4)
    monkeypatch.setattr(random, "shuffle", lambda seq: (rng_ledger.append(("shuffle", len(seq))), original_shuffle(seq))[1])
    monkeypatch.setattr(random, "sample", lambda pop, count: (rng_ledger.append(("sample", len(pop), count)), original_sample(pop, count))[1])
    runtime = _runtime()
    random.seed(24680)
    result = IntelNetworkReactionTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_cancel_reaction_proof({})
    assert uuid_ledger == [
        ("route.game_id", ids[0]),
        ("route.actor_id", ids[1]),
        ("route.reactor_id", ids[2]),
        ("Game.__init__.temporary_id", ids[3]),
        ("Player.__init__.temporary_id:actor", ids[4]),
        ("Player.__init__.temporary_id:reactor", ids[5]),
    ]
    assert result["game_id"] == str(ids[0])
    assert [p.id for p in runtime.manager.games[result["game_id"]].players] == [str(ids[1]), str(ids[2])]
    with pytest.raises(StopIteration):
        next(iterator)
    assert rng_ledger == [
        ("shuffle", 59), ("shuffle", 2), ("shuffle", 11), ("shuffle", 10),
        ("shuffle", 64), ("shuffle", 181), ("shuffle", 53), ("shuffle", 53),
        ("sample", 25, 20), ("shuffle", 20),
    ]


class ResolveGame:
    def __init__(self, players, result):
        self.players = players
        self.current_player_index = 0
        self._result = result
        self.events = []
        self.authoritative_state = {"marker": "authoritative"}

    def current_player(self):
        self.events.append(("current_player", self.current_player_index))
        return self.players[self.current_player_index]

    def play_card(self, *args, **kwargs):
        self.events.append(("play_card", args, kwargs, self.current_player_index))
        self.authoritative_state["played"] = True
        return self._result

    def state(self):
        self.events.append(("state", self.current_player_index))
        return dict(self.authoritative_state)


def _player(name, id):
    return SimpleNamespace(name=name, id=id)


def test_resolve_missing_game_and_manager_is_late_bound(monkeypatch):
    first = FakeManager()
    runtime = _install_runtime(monkeypatch, _runtime(first))
    assert main.test_resolve_intel_network_cancel_reaction_proof({}) == {"error": "Game not found"}
    second = FakeManager()
    monkeypatch.setattr(main, "manager", second)
    response = TestClient(main.app).post(RESOLVE_PATH, json={"game_id": "missing"})
    assert response.status_code == 200
    assert response.json() == {"error": "Game not found"}
    assert runtime.manager is first


@pytest.mark.parametrize(
    ("payload", "players", "expected_index", "expect_error"),
    [
        ({}, [_player("actor", "a"), _player("reactor", "r")], 0, False),
        ({"actor_name": "missing"}, [_player("first", "f"), _player("reactor", "r")], 0, False),
        ({"actor_name": "actor", "reactor_name": "missing"}, [_player("actor", "a")], 0, True),
        ({"actor_name": None}, [_player("actor", "a"), _player("reactor", "r")], 0, False),
    ],
)
def test_resolve_actor_reactor_lookup_fallback_and_errors(payload, players, expected_index, expect_error):
    game = ResolveGame(players, {"ok": True})
    manager = FakeManager({"g": game})
    result = IntelNetworkReactionTestRoutes(
        lambda: _runtime(manager)
    ).test_resolve_intel_network_cancel_reaction_proof({"game_id": "g", **payload})
    if expect_error:
        assert result == {"error": "Proof players not found"}
        assert not any(event[0] == "play_card" for event in game.events)
    else:
        assert result["success"] is True
        assert game.current_player_index == expected_index


def test_resolve_switches_actor_then_calls_play_card_and_state_in_order():
    players = [_player("other", "o"), _player("actor", "a"), _player("reactor", "r")]
    game = ResolveGame(players, {"value": 1})
    result = IntelNetworkReactionTestRoutes(
        lambda: _runtime(FakeManager({"g": game}))
    ).test_resolve_intel_network_cancel_reaction_proof({"game_id": "g"})
    assert game.events == [
        ("current_player", 0),
        ("play_card", (0,), {"mode": "action", "reaction": {"player_id": "r", "card_index": 0}}, 1),
        ("state", 1),
    ]
    assert game.current_player_index == 1
    assert result == {
        "success": True,
        "result": {"value": 1},
        "state": {"marker": "authoritative", "played": True, "last_action_result": {"value": 1}},
    }
    assert game.authoritative_state == {"marker": "authoritative", "played": True}


@pytest.mark.parametrize(
    ("play_result", "success"),
    [({}, True), ({"error": ""}, True), ({"error": 0}, True), ({"error": "bad"}, False),
     (None, True), (False, True), (0, True), ("bad", True), (["error"], True)],
)
def test_resolve_dict_and_non_dict_success_semantics_and_response_only_injection(play_result, success):
    game = ResolveGame([_player("actor", "a"), _player("reactor", "r")], play_result)
    result = IntelNetworkReactionTestRoutes(
        lambda: _runtime(FakeManager({"g": game}))
    ).test_resolve_intel_network_cancel_reaction_proof({"game_id": "g"})
    assert result["success"] is success
    assert result["result"] is play_result
    assert result["state"]["last_action_result"] is play_result
    assert "last_action_result" not in game.authoritative_state


def _validation_detail(value):
    if int(pydantic.VERSION.split(".")[0]) >= 2:
        if value is None:
            return {"detail": [{"type": "missing", "loc": ["body"], "msg": "Field required", "input": None}]}
        return {"detail": [{"type": "dict_type", "loc": ["body"], "msg": "Input should be a valid dictionary", "input": value}]}
    if value is None:
        return {"detail": [{"loc": ["body"], "msg": "field required", "type": "value_error.missing"}]}
    return {"detail": [{"loc": ["body"], "msg": "value is not a valid dict", "type": "type_error.dict"}]}


@pytest.mark.parametrize("path", [SETUP_PATH, RESOLVE_PATH])
@pytest.mark.parametrize(
    ("label", "raw", "value"),
    [("null", "null", None), ("false", "false", False), ("zero", "0", 0),
     ("empty-string", '\"\"', ""), ("empty-list", "[]", []),
     ("truthy-string", '\"truthy\"', "truthy"), ("truthy-number", "7", 7)],
)
def test_http_root_body_matrix(monkeypatch, path, label, raw, value):
    runtime = _install_runtime(monkeypatch)
    response = TestClient(main.app).post(path, content=raw, headers={"content-type": "application/json"})
    pydantic_one_success = int(pydantic.VERSION.split(".")[0]) == 1 and value in ("", [])
    if pydantic_one_success:
        assert response.status_code == 200, label
        if path == SETUP_PATH:
            _assert_default_setup(runtime, response.json())
        else:
            assert response.json() == {"error": "Game not found"}
    else:
        assert response.status_code == 422, label
        assert response.json() == _validation_detail(value)


def test_http_missing_empty_extra_openapi_routes_order_and_sync(monkeypatch):
    runtime = _install_runtime(monkeypatch)
    client = TestClient(main.app)
    for path in (SETUP_PATH, RESOLVE_PATH):
        missing = client.post(path)
        assert missing.status_code == 422
        assert missing.json() == _validation_detail(None)
    for body in ({}, {"extra": [1, 2, 3]}):
        setup = client.post(SETUP_PATH, json=body)
        assert setup.status_code == 200
        _assert_default_setup(runtime, setup.json())
        resolve = client.post(RESOLVE_PATH, json=body)
        assert resolve.status_code == 200
        assert resolve.json() == {"error": "Game not found"}

    expected = [
        (SETUP_PATH, "Test Setup Intel Network Cancel Reaction Proof",
         "test_setup_intel_network_cancel_reaction_proof_test_setup_intel_network_cancel_reaction_proof_post"),
        (RESOLVE_PATH, "Test Resolve Intel Network Cancel Reaction Proof",
         "test_resolve_intel_network_cancel_reaction_proof_test_resolve_intel_network_cancel_reaction_proof_post"),
    ]
    routes = list(_effective_app_routes())
    paths = [getattr(route, "path", None) for route in routes]
    for path, summary, operation_id in expected:
        matching = [route for route in routes if getattr(route, "path", None) == path]
        assert len(matching) == 1
        assert matching[0].methods == {"POST"}
        assert not inspect.iscoroutinefunction(matching[0].endpoint)
        operation = main.app.openapi()["paths"][path]["post"]
        assert operation["summary"] == summary
        assert operation["operationId"] == operation_id
        assert operation["requestBody"]["required"] is True
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert schema["type"] == "object"
        assert set(operation["responses"]) == {"200", "422"}
    setup_index = paths.index(SETUP_PATH)
    assert paths[setup_index - 1] == "/test/setup-expand-results-proof"
    assert paths[setup_index + 1] == RESOLVE_PATH
    assert paths[setup_index + 2] == "/test/setup-hong-kong-safehouse"


def test_main_preserves_two_bound_callables_and_late_bound_runtime(monkeypatch):
    first = _install_runtime(monkeypatch)
    first_result = main.test_setup_intel_network_cancel_reaction_proof({})
    second = _install_runtime(monkeypatch)
    second_result = main.test_setup_intel_network_cancel_reaction_proof({"actor_base": "上海"})
    assert first_result["game_id"] in first.manager.games
    assert second_result["game_id"] in second.manager.games
    assert second_result["game_id"] not in first.manager.games
    assert second.manager.games[second_result["game_id"]].players[0].base == "上海"
    for name in (
        "test_setup_intel_network_cancel_reaction_proof",
        "test_resolve_intel_network_cancel_reaction_proof",
    ):
        callable_ = getattr(main, name)
        assert callable(callable_)
        assert not inspect.iscoroutinefunction(callable_)
        assert callable_.__self__ is main._intel_network_reaction_test_routes


def _baseline_functions(*names):
    source = subprocess.run(["git", "show", BASELINE_MAIN_REF], check=True, capture_output=True, text=True).stdout
    tree = ast.parse(source)
    found = {
        node.name: node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    }
    assert set(found) == set(names), f"historical handlers {names} missing from reviewed base {BASELINE_MAIN_REF}"
    return found


def test_extracted_bodies_are_structurally_identical_to_immutable_base():
    names = (
        "test_setup_intel_network_cancel_reaction_proof",
        "test_resolve_intel_network_cancel_reaction_proof",
    )
    baseline = _baseline_functions(*names)
    import server.test_routes.intel_network_reaction as production
    tree = ast.parse(Path(production.__file__).read_text())
    extracted = {
        node.name: node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in names
    }

    class NormalizeRuntime(ast.NodeTransformer):
        def visit_Attribute(self, node):
            node = self.generic_visit(node)
            if isinstance(node.value, ast.Name) and node.value.id == "runtime":
                return ast.copy_location(ast.Name(id=node.attr, ctx=node.ctx), node)
            return node

    for name in names:
        assert isinstance(extracted[name].body[0], ast.Assign)
        normalized = NormalizeRuntime().visit(ast.Module(body=extracted[name].body[1:], type_ignores=[]))
        expected = ast.Module(body=baseline[name].body, type_ignores=[])
        ast.fix_missing_locations(normalized)
        ast.fix_missing_locations(expected)
        assert ast.dump(normalized, include_attributes=False) == ast.dump(expected, include_attributes=False)


def _load_baseline_setup(namespace):
    function = _baseline_functions("test_setup_intel_network_cancel_reaction_proof")[
        "test_setup_intel_network_cancel_reaction_proof"
    ]
    function.decorator_list = []
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, BASELINE_MAIN_REF, "exec"), namespace)
    return namespace[function.name]


def _snapshot(result, runtime):
    game = runtime.manager.games[result["game_id"]]
    return {
        "result": result,
        "state": game.state(),
        "players": [
            {"id": p.id, "name": p.name, "faction": p.faction_id, "base": p.base,
             "organizations": p.organizations, "hand": _card_names(p.hand),
             "draw": _card_names(p.deck.draw_pile), "discard": _card_names(p.deck.discard_pile),
             "resources": p.resources}
            for p in game.players
        ],
        "purchase_deck": _card_names(game.purchase_deck.draw_pile),
        "purchase_area": _card_names(game.purchase_area),
        "event_draw": [e.get("name") for e in game.event_deck.draw_pile],
        "event_discard": [e.get("name") for e in game.event_deck.discard_pile],
        "stores": {"connections": runtime.manager.connections, "lobby": runtime.lobby,
                   "hosts": runtime.lobby_hosts, "factions": runtime.lobby_factions,
                   "bases": runtime.lobby_bases},
    }


def test_setup_seeded_immutable_base_differential(monkeypatch):
    original_uuid4 = uuid.uuid4
    payload = {"actor_card": "合作談判", "reaction_card": "走漏風聲",
               "actor_faction": "liberals", "actor_base": "上海",
               "actor_draw_top": "宣傳家", "reactor_faction": "taiwan_green",
               "reactor_base": "臺北", "reactor_draw_top": "自訂牌"}

    def run(handler, runtime):
        values = iter(uuid.UUID(int=i) for i in range(101, 107))
        monkeypatch.setattr(uuid, "uuid4", values.__next__)
        random.seed(97531)
        result = handler(payload)
        snapshot = _snapshot(result, runtime)
        rng_state = random.getstate()
        with pytest.raises(StopIteration):
            next(values)
        return snapshot, rng_state

    old_runtime = _runtime()
    old_handler = _load_baseline_setup({
        "uuid": uuid, "Game": Game, "Card": Card, "GamePhase": GamePhase,
        "TurnPhase": TurnPhase, **vars(old_runtime),
    })
    old = run(old_handler, old_runtime)
    monkeypatch.setattr(uuid, "uuid4", original_uuid4)
    new_runtime = _runtime()
    new = run(
        IntelNetworkReactionTestRoutes(lambda: new_runtime).test_setup_intel_network_cancel_reaction_proof,
        new_runtime,
    )
    assert new == old
