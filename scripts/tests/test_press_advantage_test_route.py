import random
import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.press_advantage import PressAdvantageTestRoutes
from server.test_routes.runtime import GameSetupRuntime

PROOF_LOG = (
    "[Turn 1] UI proof setup: viewer has 乘勝追擊; discard pile contains "
    "宣傳家 / 合作談判 / 走漏風聲."
)


class FakeManager:
    def __init__(self, games=None, connections=None):
        self.games = games if games is not None else {}
        self.connections = connections if connections is not None else {}


def _runtime(manager=None, **stores):
    return GameSetupRuntime(
        manager=manager or FakeManager(),
        lobby=stores.get("lobby", {}),
        lobby_hosts=stores.get("lobby_hosts", {}),
        lobby_factions=stores.get("lobby_factions", {}),
        lobby_bases=stores.get("lobby_bases", {}),
    )


def _make_app(provider):
    routes = PressAdvantageTestRoutes(provider)
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


def _card_definition(game, name):
    return next(card for card in game.structured_cards if card.get("name") == name)


def test_press_advantage_default_payload_state_and_unscoped_hands():
    runtime = _runtime()
    result = PressAdvantageTestRoutes(
        lambda: runtime
    ).test_setup_press_advantage_proof({})

    assert set(result) == {"success", "game_id", "player_id", "players", "state"}
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, enemy = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert [(player.name, player.faction_id, player.base) for player in game.players] == [
        ("viewer", "red_army", "北京"),
        ("enemy", "hong_kong", "香港城"),
    ]
    assert viewer.organizations == {"北京": 1}
    assert enemy.organizations == {"香港城": 1}
    assert [card.name for card in viewer.hand] == ["乘勝追擊"]
    assert [card.name for card in viewer.deck.draw_pile] == ["抽牌A", "抽牌B"]
    assert [card.name for card in viewer.deck.discard_pile] == [
        "宣傳家",
        "合作談判",
        "走漏風聲",
    ]
    assert [card.name for card in enemy.hand] == ["對手手牌A"]
    assert [card.name for card in enemy.deck.draw_pile] == ["對手抽牌A"]
    assert enemy.deck.discard_pile == []
    assert viewer.resources == enemy.resources == {"money": 0, "propaganda": 0}
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id
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
    state = result["state"]
    assert state["game_phase"] == GamePhase.MAIN
    assert state["turn_phase"] == TurnPhase.ACTION
    assert state["pending_base_choices"] == {}
    assert state["action_log"][-1] == PROOF_LOG
    assert state["players"][0]["hand"] == ["乘勝追擊"]
    assert state["players"][1]["hand"] == ["對手手牌A"]
    assert state["players"][0]["resources"] == {"money": 0, "propaganda": 0}
    assert state["players"][1]["resources"] == {"money": 0, "propaganda": 0}
    assert state["players"][0]["deck_count"] == 2
    assert state["players"][0]["discard_pile"] == [
        "宣傳家",
        "合作談判",
        "走漏風聲",
    ]


def test_press_advantage_custom_payload_card_metadata_and_input_copies():
    runtime = _runtime()
    draw_names = ["合作談判", "自訂抽牌"]
    discard_names = ["走漏風聲", "自訂棄牌"]
    result = PressAdvantageTestRoutes(
        lambda: runtime
    ).test_setup_press_advantage_proof(
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
    assert [card.name for card in viewer.deck.draw_pile] == draw_names
    assert [card.name for card in viewer.deck.discard_pile] == discard_names

    for card in [viewer.hand[0], viewer.deck.draw_pile[0], viewer.deck.discard_pile[0]]:
        definition = _card_definition(game, card.name)
        assert card.card_type == definition["type"]
        assert card.resources == definition["resources"]
        assert card.resources is not definition["resources"]

    for card in [viewer.deck.draw_pile[1], viewer.deck.discard_pile[1]]:
        assert card.card_type == "command"
        assert card.resources == {"money": 0, "propaganda": 0}

    press_advantage = viewer.hand[0]
    definition = _card_definition(game, "乘勝追擊")
    original_resources = dict(press_advantage.resources)
    definition["resources"]["money"] = 999
    draw_names.append("稍後加入抽牌")
    discard_names.append("稍後加入棄牌")
    assert press_advantage.resources == original_resources
    assert [card.name for card in viewer.deck.draw_pile] == ["合作談判", "自訂抽牌"]
    assert [card.name for card in viewer.deck.discard_pile] == ["走漏風聲", "自訂棄牌"]


@pytest.mark.parametrize("discard_value", [None, [], (), ""])
def test_press_advantage_falsy_discard_uses_default_fallback(discard_value):
    runtime = _runtime()
    result = PressAdvantageTestRoutes(
        lambda: runtime
    ).test_setup_press_advantage_proof({"discard_pile": discard_value})
    viewer = runtime.manager.games[result["game_id"]].players[0]
    assert [card.name for card in viewer.deck.discard_pile] == [
        "宣傳家",
        "合作談判",
        "走漏風聲",
    ]


def test_press_advantage_empty_draw_does_not_use_default_fallback():
    runtime = _runtime()
    result = PressAdvantageTestRoutes(
        lambda: runtime
    ).test_setup_press_advantage_proof({"draw_pile": []})
    viewer = runtime.manager.games[result["game_id"]].players[0]
    assert viewer.deck.draw_pile == []


class TrackingStore(dict):
    def __init__(self, label, events, initial=None):
        super().__init__(initial or {})
        self.label = label
        self.events = events

    def get(self, key, default=None):
        self.events.append(f"{self.label}.get")
        return super().get(key, default)

    def __setitem__(self, key, value):
        if self.label == "games":
            assert value.action_log[-1] == PROOF_LOG
        self.events.append(f"{self.label}.set")
        super().__setitem__(key, value)


def test_press_advantage_store_values_and_side_effect_order(monkeypatch):
    from server.test_routes import press_advantage

    fixed_game_id = uuid.UUID(int=101)
    ids = iter(uuid.UUID(int=value) for value in range(101, 1000))
    monkeypatch.setattr(press_advantage.uuid, "uuid4", ids.__next__)
    events = []
    existing_connections = {"socket": object()}
    games = TrackingStore("games", events)
    connections = TrackingStore(
        "connections", events, {str(fixed_game_id): existing_connections}
    )
    lobby = TrackingStore("lobby", events)
    hosts = TrackingStore("hosts", events)
    factions = TrackingStore("factions", events)
    bases = TrackingStore("bases", events)
    runtime = _runtime(
        FakeManager(games, connections),
        lobby=lobby,
        lobby_hosts=hosts,
        lobby_factions=factions,
        lobby_bases=bases,
    )

    result = PressAdvantageTestRoutes(
        lambda: runtime
    ).test_setup_press_advantage_proof({})
    game_id = result["game_id"]
    game = games[game_id]
    viewer, enemy = game.players

    assert events == [
        "games.set",
        "connections.get",
        "connections.set",
        "lobby.set",
        "hosts.set",
        "factions.set",
        "bases.set",
    ]
    assert connections[game_id] is existing_connections
    assert lobby[game_id] == [(viewer.id, "viewer"), (enemy.id, "enemy")]
    assert hosts[game_id] == viewer.id
    assert factions[game_id] == {
        viewer.id: viewer.faction_id,
        enemy.id: enemy.faction_id,
    }
    assert bases[game_id] == {viewer.id: viewer.base, enemy.id: enemy.base}


def test_main_press_advantage_uses_rebound_runtime_and_callable(monkeypatch):
    manager = FakeManager()
    lobby = {}
    hosts = {}
    factions = {}
    bases = {}
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "lobby", lobby)
    monkeypatch.setattr(main, "lobby_hosts", hosts)
    monkeypatch.setattr(main, "lobby_factions", factions)
    monkeypatch.setattr(main, "lobby_bases", bases)

    response = TestClient(main.app).post(
        "/test/setup-press-advantage-proof",
        json={"viewer_base": "上海"},
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert manager.games[game_id].players[0].base == "上海"
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_press_advantage_proof({"enemy_base": "臺北"})
    assert direct["game_id"] != game_id
    assert manager.games[direct["game_id"]].players[1].base == "臺北"
    assert callable(main.test_setup_press_advantage_proof)
    assert (
        main.test_setup_press_advantage_proof.__self__
        is main._press_advantage_test_routes
    )
    assert (
        main.test_setup_press_advantage_proof.__func__
        is PressAdvantageTestRoutes.test_setup_press_advantage_proof
    )


def test_press_advantage_uuid_prefix_and_rng_consumption_are_stable(monkeypatch):
    from server.test_routes import press_advantage

    ids = [uuid.UUID(int=value) for value in range(201, 1000)]
    monkeypatch.setattr(press_advantage.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()

    random.seed(24680)
    result = PressAdvantageTestRoutes(
        lambda: runtime
    ).test_setup_press_advantage_proof({})
    actual_random_state = random.getstate()
    game = runtime.manager.games[result["game_id"]]

    random.seed(24680)
    Game([("baseline-viewer", "viewer"), ("baseline-enemy", "enemy")])
    expected_random_state = random.getstate()

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(ids[1]), str(ids[2])]
    assert actual_random_state == expected_random_state


def test_press_advantage_http_body_coercion_openapi_and_route_adjacency():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)

    response = client.post(
        "/test/setup-press-advantage-proof",
        json={"draw_pile": [], "discard_pile": ["走漏風聲"]},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"success", "game_id", "player_id", "players", "state"}
    assert client.post("/test/setup-press-advantage-proof").status_code == 422
    list_response = client.post("/test/setup-press-advantage-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-press-advantage-proof"]["post"]
    assert operation["summary"] == "Test Setup Press Advantage Proof"
    assert operation["operationId"].startswith("test_setup_press_advantage_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-press-advantage-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-press-advantage-proof")
    assert paths[index - 1] == "/test/setup-intel-network-proof"
    assert paths[index + 1] == "/test/setup-expand-results-proof"
