import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.business_network_transport import (
    BusinessNetworkTransportTestRoutes,
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
    )


def _make_app(provider):
    routes = BusinessNetworkTransportTestRoutes(provider)
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


def test_business_network_transport_default_state_and_lobby_registration():
    runtime = _runtime()
    result = BusinessNetworkTransportTestRoutes(
        lambda: runtime
    ).test_setup_business_network_transport_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["turn_phase"] == TurnPhase.ACTION
    assert result["game_phase"] == GamePhase.MAIN

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "tibet_dehradun",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert viewer.resources == {"money": 0, "propaganda": 0}
    assert viewer.moves_left == 4
    assert viewer.hand == []
    assert (red.faction_id, red.base, red.organizations, red.hand) == (
        "red_army",
        "北京",
        {"北京": 1},
        [],
    )

    assert len(game.purchase_area) == 11
    assert [card.name for card in game.purchase_area[6:]] == [
        "合作談判",
        "交通經驗乙",
        "模仿戰術",
        "資本家",
        "填充D",
    ]
    assert game.pending_choice["type"] == "card_choice"
    assert game.pending_choice["choice_key"] == "use_purchase_area_card"
    assert game.pending_choice["player_id"] == viewer.id
    assert game.pending_choice["prompt"] == "企業人脈：選擇購買區正面朝上的 1 張牌，視同打出該牌。"
    assert game.pending_choice["source_name"] == "企業人脈"
    assert [c["name"] for c in game.pending_choice["cards"]] == [
        "合作談判",
        "交通經驗乙",
        "模仿戰術",
        "資本家",
        "填充D",
    ]
    assert [c["zone"] for c in game.pending_choice["cards"]] == ["purchase_area"] * 5
    assert [c["purchase_index"] for c in game.pending_choice["cards"]] == [
        6,
        7,
        8,
        9,
        10,
    ]
    assert [c["zone_label"] for c in game.pending_choice["cards"]] == [
        "購買區槽位 1",
        "購買區槽位 2",
        "購買區槽位 3",
        "購買區槽位 4",
        "購買區槽位 5",
    ]

    assert game.current_player_index == 0
    assert game.pending_base_choices == {}
    assert game.id == game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "tibet_dehradun",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {viewer.id: "德拉敦", red.id: "北京"}


def test_business_network_transport_custom_payload_overrides():
    runtime = _runtime()
    custom_orgs = {"上海": 2}
    result = BusinessNetworkTransportTestRoutes(
        lambda: runtime
    ).test_setup_business_network_transport_proof(
        {
            "faction_id": "liberals",
            "base": "上海",
            "orgs": custom_orgs,
            "resources": {"money": 3, "propaganda": 2},
        }
    )
    game = runtime.manager.games[result["game_id"]]
    viewer, _red = game.players

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "上海",
        {"上海": 2},
    )
    assert viewer.resources == {"money": 3, "propaganda": 2}


def test_main_business_network_transport_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-business-network-transport-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_business_network_transport_proof({"base": "上海"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_business_network_transport_proof)


def test_business_network_transport_uuid_order_is_stable(monkeypatch):
    from server.test_routes import business_network_transport

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(business_network_transport.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = BusinessNetworkTransportTestRoutes(
        lambda: runtime
    ).test_setup_business_network_transport_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_business_network_transport_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-business-network-transport-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "turn_phase",
        "game_phase",
        "players",
        "state",
    }
    assert (
        client.post("/test/setup-business-network-transport-proof").status_code == 422
    )
    list_response = client.post(
        "/test/setup-business-network-transport-proof", json=[]
    )
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"][
        "/test/setup-business-network-transport-proof"
    ]["post"]
    assert operation["summary"] == "Test Setup Business Network Transport Proof"
    assert operation["operationId"].startswith(
        "test_setup_business_network_transport_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None)
        == "/test/setup-business-network-transport-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-business-network-transport-proof")
    assert paths[index - 1] == "/test/setup-end-turn-topdeck-proof"
    assert paths[index + 1] == "/test/setup-planning-lobby-ui"
