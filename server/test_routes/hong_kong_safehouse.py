"""Test-only route for the Hong Kong safehouse setup proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class HongKongSafehouseTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-hong-kong-safehouse",
            self.test_setup_hong_kong_safehouse,
            methods=["POST"],
        )

    def test_setup_hong_kong_safehouse(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "hk"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        hk = game.players[0]
        red = game.players[1]

        hk.faction_id = "hong_kong"
        hk.base = payload.get("base", "香港城")
        hk.organizations = {hk.base: 1}
        hk.hand = []

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}

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
        runtime.lobby_hosts[game_id] = hk.id
        runtime.lobby_factions[game_id] = {hk.id: "hong_kong", red.id: "red_army"}
        runtime.lobby_bases[game_id] = {hk.id: hk.base, red.id: red.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": hk.id,
            "base": hk.base,
            "turn_phase": game.turn_phase,
            "game_phase": game.game_phase,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
