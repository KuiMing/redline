import uuid

import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.peer_choice_notice import PeerChoiceNoticeTestRoutes
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
    routes = PeerChoiceNoticeTestRoutes(provider)
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


def test_peer_choice_notice_default_state_and_lobby_registration():
    runtime = _runtime()
    result = PeerChoiceNoticeTestRoutes(
        lambda: runtime
    ).test_setup_peer_choice_notice_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "actor_player_id",
        "viewer_player_id",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    actor, viewer = game.players

    assert result["success"] is True
    assert result["actor_player_id"] == actor.id
    assert result["viewer_player_id"] == viewer.id

    assert (actor.faction_id, actor.base, actor.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert actor.hand == []
    assert actor.deck.discard_pile == []

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "liberals",
        "德拉敦",
        {"德拉敦": 1},
    )
    assert [card.name for card in viewer.hand] == ["情報網", "領導", "謀劃"]
    assert [card.name for card in viewer.deck.draw_pile] == ["補牌"]
    assert viewer.deck.discard_pile == []

    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.game_phase == GamePhase.MAIN
    assert game.pending_base_choices == {}
    assert game.current_event["name"] == "歲月靜好"
    assert game.event_progress == {
        "count": 0,
        "required": 0,
        "succeeded": True,
        "settled": True,
        "status": "idle",
    }
    assert game.event_modifiers == []
    assert game.id == game_id

    assert game.pending_choice is not None
    assert game.pending_choice["type"] == "card_choice"
    assert game.pending_choice["choice_key"] == "armed_target_discard"
    assert game.pending_choice["player_id"] == viewer.id
    assert game.pending_choice["source_name"] == "武裝小隊"
    assert game.pending_choice["prompt"] == "武裝小隊：從所有手牌中棄掉任 1 張牌。"
    assert game.pending_choice["initiator_player_id"] == actor.id
    assert game.pending_choice["initiator_player_name"] == actor.name
    assert game.pending_choice["target_player_name"] == viewer.name
    assert (
        f"{actor.name} used 武裝小隊 to ask {viewer.name} to choose 1 discard(s)"
        in game.action_log[-1]
    )

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == actor.id
    assert runtime.lobby_factions[game_id] == {actor.id: "red_army", viewer.id: "liberals"}
    assert runtime.lobby_bases[game_id] == {actor.id: "北京", viewer.id: "德拉敦"}


def test_peer_choice_notice_custom_payload_overrides():
    runtime = _runtime()
    result = PeerChoiceNoticeTestRoutes(
        lambda: runtime
    ).test_setup_peer_choice_notice_proof(
        {
            "source_name": "自訂事件",
            "viewer_hand": ["不存在的牌"],
            "actor_faction_id": "liberals",
            "viewer_faction_id": "hong_kong",
            "viewer_base": "香港城",
        }
    )
    game = runtime.manager.games[result["game_id"]]
    actor, viewer = game.players

    assert actor.faction_id == "liberals"
    assert (viewer.faction_id, viewer.base) == ("hong_kong", "香港城")
    assert [card.name for card in viewer.hand] == ["不存在的牌"]
    assert viewer.hand[0].card_type == "command"
    assert game.pending_choice["source_name"] == "自訂事件"
    assert game.pending_choice["prompt"] == "自訂事件：從所有手牌中棄掉任 1 張牌。"


def test_main_peer_choice_notice_uses_rebound_runtime_and_callable(monkeypatch):
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
        "/test/setup-peer-choice-notice-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases

    direct = main.test_setup_peer_choice_notice_proof({"source_name": "自訂事件"})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_peer_choice_notice_proof)


def test_peer_choice_notice_uuid_order_is_stable(monkeypatch):
    from server.test_routes import peer_choice_notice

    ids = [uuid.UUID(int=value) for value in range(1, 1000)]
    monkeypatch.setattr(peer_choice_notice.uuid, "uuid4", iter(ids).__next__)
    runtime = _runtime()
    result = PeerChoiceNoticeTestRoutes(
        lambda: runtime
    ).test_setup_peer_choice_notice_proof({})
    game = runtime.manager.games[result["game_id"]]

    assert result["game_id"] == str(ids[0])
    assert [player.id for player in game.players] == [str(item) for item in ids[1:3]]


def test_peer_choice_notice_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-peer-choice-notice-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "actor_player_id",
        "viewer_player_id",
        "state",
    }
    assert client.post("/test/setup-peer-choice-notice-proof").status_code == 422
    list_response = client.post("/test/setup-peer-choice-notice-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-peer-choice-notice-proof"]["post"]
    assert operation["summary"] == "Test Setup Peer Choice Notice Proof"
    assert operation["operationId"].startswith("test_setup_peer_choice_notice_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-peer-choice-notice-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-peer-choice-notice-proof")
    assert paths[index - 1] == "/test/setup-show-strength-choice-proof"
    assert paths[index + 1] == "/test/setup-safehouse-range-proof"
