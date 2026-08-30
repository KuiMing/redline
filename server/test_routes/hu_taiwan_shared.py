"""Test-only route for the HU/Taiwan shared organization proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class HuTaiwanSharedTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-hu-taiwan-shared",
            self.test_setup_hu_taiwan_shared,
            methods=["POST"],
        )

    def test_setup_hu_taiwan_shared(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "hu"), (str(uuid.uuid4()), "taiwan")]
        game = Game(players)

        hu = game.players[0]
        tw = game.players[1]

        hu.faction_id = "hu"
        hu.base = payload.get("hu_base", "紐約")
        hu.organizations = {hu.base: 1}
        hu.hand = []
        hu.moves_left = 0

        tw.faction_id = "taiwan_green"
        tw.base = payload.get("tw_base", "臺北")
        tw.organizations = {
            payload.get("shared_town", "上海"): 1,
            tw.base: 1,
        }
        tw.hand = []

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = hu.id
        runtime.lobby_factions[game_id] = {hu.id: "hu", tw.id: "taiwan_green"}
        runtime.lobby_bases[game_id] = {hu.id: hu.base, tw.id: tw.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": hu.id,
            "shared_town": payload.get("shared_town", "上海"),
            "turn_phase": game.turn_phase,
            "game_phase": game.game_phase,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
