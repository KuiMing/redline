"""Test-only route for the destroyed red base marker proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class DestroyedRedBaseMarkerTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-destroyed-red-base-marker-proof",
            self.test_setup_destroyed_red_base_marker_proof,
            methods=["POST"],
        )

    def test_setup_destroyed_red_base_marker_proof(self, payload: dict):
        """Create a Mongol move state before or after Beijing's Red Army base organization is destroyed."""
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "mongol"), (str(uuid.uuid4()), "red")]
        game = Game(players, market_mode="all_cards")
        mongol, red = game.players

        destroyed = bool(payload.get("destroyed", True))
        mongol.faction_id = "mongol"
        mongol.base = "烏蘭巴托"
        mongol.organizations = {"烏蘭巴托": 1, "張家口": 1}
        mongol.moves_left = 3

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {} if destroyed else {"北京": 1}

        game.current_player_index = 0
        game.round_start_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.pending_choice = None
        game.id = game_id
        if destroyed:
            game.turn_log["red_army_base_build_blocks"] = ["北京"]

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = mongol.id
        runtime.lobby_factions[game_id] = {
            mongol.id: mongol.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {mongol.id: mongol.base, red.id: red.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "destroyed": destroyed,
            "game_id": game_id,
            "player_id": mongol.id,
            "url": f"/?game_id={game_id}&player_id={mongol.id}",
            "state": game.state(),
        }
