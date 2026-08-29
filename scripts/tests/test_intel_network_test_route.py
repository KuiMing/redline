import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.intel_network import IntelNetworkTestRoutes
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


def _make_app(provider):
    routes = IntelNetworkTestRoutes(provider)
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


def test_intel_network_default_state_and_unscoped_hands():
    runtime = _runtime()
    result = IntelNetworkTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_proof({})

    assert set(result) == {"success", "game_id", "player_id", "players", "state"}
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, enemy_a, enemy_b, enemy_c = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert [(player.name, player.faction_id, player.base) for player in game.players] == [
        ("viewer", "red_army", "北京"),
        ("enemyA", "hong_kong", "香港城"),
        ("enemyB", "taiwan_green", "臺北"),
        ("enemyC", "minyun", "巴黎"),
    ]
    assert viewer.organizations == {"北京": 1}
    assert enemy_a.organizations == {"天津": 1, "香港城": 1, "廣州": 1}
    assert enemy_b.organizations == {"臺北": 1}
    assert enemy_c.organizations == {"巴黎": 1, "上海": 1}
    assert [card.name for card in viewer.hand] == ["情報網"]
    assert [card.name for card in enemy_a.hand] == ["敵方手牌A1", "敵方手牌A2"]
    assert [card.name for card in enemy_b.hand] == ["敵方手牌B1", "敵方手牌B2"]
    assert [card.name for card in enemy_c.hand] == ["敵方手牌C1", "敵方手牌C2"]
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.id == game_id

    state_players = result["state"]["players"]
    assert state_players[0]["hand"] == ["情報網"]
    assert state_players[1]["hand"] == ["敵方手牌A1", "敵方手牌A2"]
    assert state_players[2]["hand"] == ["敵方手牌B1", "敵方手牌B2"]
    assert state_players[3]["hand"] == ["敵方手牌C1", "敵方手牌C2"]
    assert result["players"] == [
        {"id": player.id, "name": player.name, "faction": player.faction_id}
        for player in game.players
    ]
    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(player.id, player.name) for player in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        player.id: player.faction_id for player in game.players
    }
    assert runtime.lobby_bases[game_id] == {
        player.id: player.base for player in game.players
    }


def test_intel_network_custom_payload_and_mapping_copies():
    runtime = _runtime()
    viewer_orgs = {"承德": 1}
    enemy_a_orgs = {"上海": 1}
    enemy_b_orgs = {"臺南": 1}
    enemy_c_orgs = {"倫敦": 1}
    result = IntelNetworkTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_proof(
        {
            "viewer_faction": "liberals",
            "viewer_base": "香港城",
            "viewer_organizations": viewer_orgs,
            "intel_card_count": "3",
            "enemy_a_faction": "rebel",
            "enemy_a_base": "上海",
            "enemy_a_organizations": enemy_a_orgs,
            "enemy_b_faction": "mongol",
            "enemy_b_base": "烏蘭巴托",
            "enemy_b_organizations": enemy_b_orgs,
            "enemy_c_faction": "kazakh",
            "enemy_c_base": "阿拉木圖",
            "enemy_c_organizations": enemy_c_orgs,
        }
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, enemy_a, enemy_b, enemy_c = game.players

    assert [card.name for card in viewer.hand] == ["情報網"] * 3
    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "香港城",
        {"承德": 1},
    )
    assert (enemy_a.faction_id, enemy_a.base, enemy_a.organizations) == (
        "rebel",
        "上海",
        {"上海": 1},
    )
    assert (enemy_b.faction_id, enemy_b.base, enemy_b.organizations) == (
        "mongol",
        "烏蘭巴托",
        {"臺南": 1},
    )
    assert (enemy_c.faction_id, enemy_c.base, enemy_c.organizations) == (
        "kazakh",
        "阿拉木圖",
        {"倫敦": 1},
    )
    viewer_orgs["北京"] = 9
    enemy_a_orgs["天津"] = 9
    enemy_b_orgs["臺北"] = 9
    enemy_c_orgs["巴黎"] = 9
    assert viewer.organizations == {"承德": 1}
    assert enemy_a.organizations == {"上海": 1}
    assert enemy_b.organizations == {"臺南": 1}
    assert enemy_c.organizations == {"倫敦": 1}


@pytest.mark.parametrize(
    ("value", "expected_count"),
    [(None, 1), (0, 1), (False, 1), (-2, 1), (2.9, 2), ("4", 4)],
)
def test_intel_network_card_count_coercion(value, expected_count):
    runtime = _runtime()
    result = IntelNetworkTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_proof({"intel_card_count": value})
    game = runtime.manager.games[result["game_id"]]
    assert len(game.players[0].hand) == expected_count


@pytest.mark.parametrize("value", ["bad", [1], {"value": 1}])
def test_intel_network_invalid_card_count_raises_before_store_writes(value):
    runtime = _runtime()
    with pytest.raises((TypeError, ValueError)):
        IntelNetworkTestRoutes(lambda: runtime).test_setup_intel_network_proof(
            {"intel_card_count": value}
        )
    assert runtime.manager.games == {}
    assert runtime.manager.connections == {}
    assert runtime.lobby == {}
    assert runtime.lobby_hosts == {}
    assert runtime.lobby_factions == {}
    assert runtime.lobby_bases == {}


def test_main_intel_network_uses_rebound_runtime_and_callable(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-intel-network-proof", json={})
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_intel_network_proof({"intel_card_count": 2})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_intel_network_proof)


def test_intel_network_uuid_order_is_stable(monkeypatch):
    from server.test_routes import intel_network

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(intel_network.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = IntelNetworkTestRoutes(
        lambda: runtime
    ).test_setup_intel_network_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:5]]


def test_intel_network_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-intel-network-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {"success", "game_id", "player_id", "players", "state"}
    assert client.post("/test/setup-intel-network-proof").status_code == 422
    list_response = client.post("/test/setup-intel-network-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-intel-network-proof"]["post"]
    assert operation["summary"] == "Test Setup Intel Network Proof"
    assert operation["operationId"].startswith("test_setup_intel_network_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-intel-network-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-intel-network-proof")
    assert paths[index - 1] == "/test/force-base-selection"
    assert paths[index + 1] == "/test/setup-press-advantage-proof"
