import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes import build_queue
from server.test_routes.build_queue import BuildQueueRuntime, BuildQueueTestRoutes


class FakeManager:
    def __init__(self):
        self.games = {}
        self.connections = {}


def _runtime(manager=None):
    return BuildQueueRuntime(
        manager=manager or FakeManager(),
        lobby={},
        lobby_hosts={},
        lobby_factions={},
        lobby_bases={},
    )


def _make_app(runtime_provider):
    routes = BuildQueueTestRoutes(runtime_provider)
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


def test_build_queue_route_constructs_default_proof_state():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/setup-build-queue-proof",
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"success", "game_id", "player_id", "state"}
    assert payload["success"] is True
    game_id = payload["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players
    assert payload["player_id"] == viewer.id
    assert game.id == game_id
    assert viewer.faction_id == "liberals"
    assert viewer.base == "香港城"
    assert viewer.organizations == {"香港城": 1}
    assert [card.name for card in viewer.hand] == ["組織經驗丙", "組織經驗乙"]
    assert viewer.deck.discard_pile == []
    assert red.faction_id == "red_army"
    assert red.base == "北京"
    assert red.organizations == {"北京": 1}
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
    assert payload["state"] == game.state(viewer.id)
    scoped_players = {
        player_state["id"]: player_state for player_state in payload["state"]["players"]
    }
    unscoped_players = {
        player_state["id"]: player_state for player_state in game.state()["players"]
    }
    assert scoped_players[viewer.id]["hand"] == ["組織經驗丙", "組織經驗乙"]
    assert scoped_players[red.id]["hand"] == ["未知手牌"] * len(red.hand)
    assert unscoped_players[red.id]["hand"] == [card.name for card in red.hand]
    assert scoped_players[red.id]["hand"] != unscoped_players[red.id]["hand"]
    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(viewer.id, "viewer"), (red.id, "red")]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "liberals",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {
        viewer.id: "香港城",
        red.id: "北京",
    }


def test_build_queue_route_preserves_custom_cards_and_forced_support_tier():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/setup-build-queue-proof",
        json={
            "faction_id": "hong_kong",
            "base": "香港城",
            "organizations": {"香港城": 2, "九龍": 1},
            "enemy_base": "廣州",
            "enemy_organizations": {"廣州": 2},
            "cards": ["印度奧援", "東洋奧援", "組織經驗丙"],
            "support_tiers": {"印度奧援": "3"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    game = runtime.manager.games[payload["game_id"]]
    viewer, red = game.players
    support_card, fallback_support_card, action_card = viewer.hand
    assert viewer.faction_id == "hong_kong"
    assert viewer.organizations == {"香港城": 2, "九龍": 1}
    assert red.base == "廣州"
    assert red.organizations == {"廣州": 2}
    assert support_card.name == "印度奧援"
    assert support_card.card_type == "support"
    assert support_card.effect["support_taxonomy"]["support_region"] == "印度"
    assert fallback_support_card.name == "東洋奧援"
    assert fallback_support_card.card_type == "support"
    assert action_card.name == "組織經驗丙"
    assert action_card.card_type == "organization"
    canonical_action = next(
        card for card in game.structured_cards if card.get("name") == "組織經驗丙"
    )
    assert action_card.resources == canonical_action.get("resources", {})
    assert action_card.resources is canonical_action["resources"]
    assert game._support_card_tier(viewer, support_card) == (
        3,
        int(getattr(support_card, "variant_index", 0) or 0),
        [],
    )

    control_runtime = _runtime()
    control_result = BuildQueueTestRoutes(
        lambda: control_runtime
    ).test_setup_build_queue_proof(
        {
            "faction_id": "hong_kong",
            "base": "香港城",
            "organizations": {"香港城": 2, "九龍": 1},
            "cards": ["東洋奧援"],
        }
    )
    control_game = control_runtime.manager.games[control_result["game_id"]]
    control_viewer = control_game.players[0]
    assert "_support_card_tier" in game.__dict__
    assert "_support_card_tier" not in control_game.__dict__
    assert game._support_card_tier(viewer, fallback_support_card) == (
        control_game._support_card_tier(control_viewer, control_viewer.hand[0])
    )


def test_build_queue_route_copies_organization_mappings():
    organizations = {"香港城": 2}
    enemy_organizations = {"北京": 2}
    runtime = _runtime()
    result = BuildQueueTestRoutes(lambda: runtime).test_setup_build_queue_proof(
        {
            "organizations": organizations,
            "enemy_organizations": enemy_organizations,
        }
    )
    game = runtime.manager.games[result["game_id"]]

    organizations["香港城"] = 99
    enemy_organizations["北京"] = 99

    assert game.players[0].organizations == {"香港城": 2}
    assert game.players[1].organizations == {"北京": 2}
    assert game.players[0].organizations is not organizations
    assert game.players[1].organizations is not enemy_organizations


def test_build_queue_route_preserves_unknown_card_error():
    runtime = _runtime()
    response = TestClient(_make_app(lambda: runtime)).post(
        "/test/setup-build-queue-proof",
        json={"cards": ["不存在卡牌"]},
    )

    assert response.status_code == 200
    assert response.json() == {"error": "Unknown action card: 不存在卡牌"}
    assert runtime.manager.games == {}
    assert runtime.lobby == {}


def test_main_build_queue_route_uses_rebound_runtime(monkeypatch):
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

    response = TestClient(main.app).post("/test/setup-build-queue-proof", json={})

    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in lobby_hosts
    assert game_id in lobby_factions
    assert game_id in lobby_bases
    assert callable(main.test_setup_build_queue_proof)

    direct_result = main.test_setup_build_queue_proof({})
    direct_game_id = direct_result["game_id"]
    assert direct_game_id != game_id
    assert direct_game_id in manager.games
    assert direct_game_id in lobby
    assert direct_game_id in lobby_hosts
    assert direct_game_id in lobby_factions
    assert direct_game_id in lobby_bases


def test_build_queue_uuid_order_is_stable(monkeypatch):
    ids = [uuid.UUID(int=value) for value in range(1, 101)]
    monkeypatch.setattr(build_queue.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()

    result = BuildQueueTestRoutes(lambda: runtime).test_setup_build_queue_proof({})

    assert result["game_id"] == str(ids[0])
    assert result["player_id"] == str(ids[1])
    assert [player.id for player in runtime.manager.games[result["game_id"]].players] == [
        str(ids[1]),
        str(ids[2]),
    ]


def test_build_queue_request_and_openapi_contracts_are_stable():
    client = TestClient(_make_app(lambda: _runtime()))
    path = "/test/setup-build-queue-proof"

    assert client.post(path).status_code == 422
    assert client.post(path, json=[]).status_code == 422

    operation = main.app.openapi()["paths"][path]["post"]
    assert operation["summary"] == "Test Setup Build Queue Proof"
    assert operation["operationId"] == (
        "test_setup_build_queue_proof_test_setup_build_queue_proof_post"
    )
    assert operation["requestBody"]["required"] is True
    assert set(operation["responses"]) == {"200", "422"}


def test_main_registers_build_queue_route_once_and_in_original_order():
    effective_routes = list(_effective_app_routes())
    paths = [getattr(route, "path", None) for route in effective_routes]
    path = "/test/setup-build-queue-proof"
    routes = [route for route in effective_routes if getattr(route, "path", None) == path]
    route_index = paths.index(path)

    assert len(routes) == 1
    assert getattr(routes[0], "methods", None) == {"POST"}
    assert paths[route_index - 1] == "/test/setup-build-view-persistence-proof"
    assert paths[route_index + 1] == "/test/setup-negotiation-proof"
