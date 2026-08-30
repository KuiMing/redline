import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.game import GamePhase, TurnPhase
from server.test_routes.manchuria_era_reorder import ManchuriaEraReorderTestRoutes
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
        lobby_ready={},
    )


def _make_app(provider):
    routes = ManchuriaEraReorderTestRoutes(provider)
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


def test_manchuria_era_reorder_default_state_and_lobby_registration():
    runtime = _runtime()
    result = ManchuriaEraReorderTestRoutes(
        lambda: runtime
    ).test_setup_manchuria_era_reorder_proof({})

    assert set(result) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "era_name",
        "runtime_effects",
        "url",
        "state",
    }
    game_id = result["game_id"]
    game = runtime.manager.games[game_id]
    viewer, red = game.players

    assert result["success"] is True
    assert result["player_id"] == viewer.id
    assert result["red_player_id"] == red.id
    assert result["era_name"] == "[滿洲]滿洲地方派系凝聚"
    assert result["url"] == f"/?game_id={game_id}&player_id={viewer.id}"

    assert (viewer.faction_id, viewer.base, viewer.organizations) == (
        "manchuria",
        "瀋陽",
        {"瀋陽": 1},
    )
    assert [card.name for card in viewer.hand] == ["追隨者"]
    assert [card.name for card in viewer.deck.draw_pile] == [
        "底牌0",
        "底牌1",
        "底牌2",
        "第七張",
        "第六張",
        "第五張",
        "第四張",
        "第三張",
        "第二張",
        "第一張",
    ]
    # Manchuria era activation's red_suppression runtime effect adds 5 分神
    # cards straight to the viewer's discard pile.
    assert [card.name for card in viewer.deck.discard_pile] == ["分神"] * 5

    assert (red.faction_id, red.base, red.organizations) == (
        "red_army",
        "北京",
        {"北京": 1},
    )
    assert [card.name for card in red.hand] == ["追隨者"]

    assert game.pending_base_choices == []
    assert game.game_phase == GamePhase.MAIN
    assert game.current_player_index == 0
    assert game.turn_phase == TurnPhase.ACTION
    assert game.era_notification["id"] == "manchuria"
    assert game.era_notification["name"] == "[滿洲]滿洲地方派系凝聚"
    assert game.era_notification["runtime_effects"] == result["runtime_effects"]
    runtime_effects = result["runtime_effects"]
    assert runtime_effects["red_suppression"]["type"] == "add_static_cards_to_discard"
    assert runtime_effects["red_suppression"]["added"] == {viewer.id: 5}
    assert runtime_effects["revolution_counterattack"] == {
        "type": "inspect_deck_top_and_reorder",
        "status": "pending_reorder_choice",
        "player_id": viewer.id,
        "inspected_count": 7,
        "top_count": 2,
    }
    # This route never assigns game.id; Game()'s own auto-generated id is left as-is.
    assert game.id != game_id

    assert runtime.manager.connections[game_id] == {}
    assert runtime.lobby[game_id] == [(p.id, p.name) for p in game.players]
    assert runtime.lobby_hosts[game_id] == viewer.id
    assert runtime.lobby_factions[game_id] == {
        viewer.id: "manchuria",
        red.id: "red_army",
    }
    assert runtime.lobby_bases[game_id] == {viewer.id: "瀋陽", red.id: "北京"}
    assert runtime.lobby_ready[game_id] == {viewer.id: True, red.id: True}


def test_main_manchuria_era_reorder_uses_rebound_runtime_and_callable(monkeypatch):
    manager = FakeManager()
    lobby = {}
    hosts = {}
    factions = {}
    bases = {}
    ready = {}
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "lobby", lobby)
    monkeypatch.setattr(main, "lobby_hosts", hosts)
    monkeypatch.setattr(main, "lobby_factions", factions)
    monkeypatch.setattr(main, "lobby_bases", bases)
    monkeypatch.setattr(main, "lobby_ready", ready)

    response = TestClient(main.app).post(
        "/test/setup-manchuria-era-reorder-proof", json={}
    )
    assert response.status_code == 200
    game_id = response.json()["game_id"]
    assert game_id in manager.games
    assert game_id in lobby
    assert game_id in hosts
    assert game_id in factions
    assert game_id in bases
    assert game_id in ready

    direct = main.test_setup_manchuria_era_reorder_proof({})
    assert direct["game_id"] != game_id
    assert direct["game_id"] in manager.games
    assert callable(main.test_setup_manchuria_era_reorder_proof)


def test_manchuria_era_reorder_first_two_uuids_are_the_players():
    runtime = _runtime()
    result = ManchuriaEraReorderTestRoutes(
        lambda: runtime
    ).test_setup_manchuria_era_reorder_proof({})
    game = runtime.manager.games[result["game_id"]]

    # Game() consumes the first two uuid4() calls for the two players; the
    # route's own game_id (and any uuids era activation consumes in between)
    # come after, so only the player-id ordering is a stable route contract.
    assert result["player_id"] == game.players[0].id
    assert result["red_player_id"] == game.players[1].id


def test_manchuria_era_reorder_http_openapi_and_route_order():
    runtime = _runtime()
    app = _make_app(lambda: runtime)
    client = TestClient(app)
    response = client.post("/test/setup-manchuria-era-reorder-proof", json={})
    assert response.status_code == 200
    assert set(response.json()) == {
        "success",
        "game_id",
        "player_id",
        "red_player_id",
        "era_name",
        "runtime_effects",
        "url",
        "state",
    }
    assert client.post("/test/setup-manchuria-era-reorder-proof").status_code == 422
    list_response = client.post(
        "/test/setup-manchuria-era-reorder-proof", json=[]
    )
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"][
        "/test/setup-manchuria-era-reorder-proof"
    ]["post"]
    assert operation["summary"] == "Test Setup Manchuria Era Reorder Proof"
    assert operation["operationId"].startswith(
        "test_setup_manchuria_era_reorder_proof_"
    )
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-manchuria-era-reorder-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-manchuria-era-reorder-proof")
    assert paths[index - 1] == "/test/setup-bait-exhaustion-ui"
    assert paths[index + 1] == "/"
