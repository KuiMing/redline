"""Test-only route for the move confirmation proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class MoveConfirmationTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-move-confirmation-proof",
            self.test_setup_move_confirmation_proof,
            methods=["POST"],
        )

    def test_setup_move_confirmation_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "mover"), (str(uuid.uuid4()), "opponent")]
        game = Game(players, market_mode="all_cards")
        mover = game.players[0]
        opponent = game.players[1]

        mover.faction_id = payload.get("mover_faction", "taiwan_green")
        mover.base = payload.get("mover_base", "臺北")
        mover.organizations = {payload.get("mover_town", "臺北"): 1}
        mover.moves_left = int(payload.get("moves_left", 5) or 5)

        opponent.faction_id = "red_army"
        opponent.base = "北京"
        opponent.organizations = {"北京": 1}

        game.current_player_index = 0
        game.round_start_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.pending_choice = None
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = mover.id
        runtime.lobby_factions[game_id] = {
            mover.id: mover.faction_id,
            opponent.id: opponent.faction_id,
        }
        runtime.lobby_bases[game_id] = {mover.id: mover.base, opponent.id: opponent.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": mover.id,
            "opponent_player_id": opponent.id,
            "url": f"/?game_id={game_id}&player_id={mover.id}",
            "state": game.state(),
        }
