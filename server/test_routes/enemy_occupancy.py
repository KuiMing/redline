"""Test-only route for the enemy occupancy proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class EnemyOccupancyTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-enemy-occupancy-proof",
            self.test_setup_enemy_occupancy_proof,
            methods=["POST"],
        )

    def test_setup_enemy_occupancy_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "f"), (str(uuid.uuid4()), "紅軍")]
        game = Game(players, market_mode="all_cards")
        actor = game.players[0]
        red = game.players[1]

        actor.faction_id = payload.get("actor_faction", "taiwan_green")
        actor.base = payload.get("actor_base", "臺北")
        actor.organizations = {payload.get("actor_town", "桃園"): 1}
        actor.hand = [Card("宣傳家", "propaganda", {"propaganda": 2})]
        actor.moves_left = int(payload.get("moves_left", 1) or 1)
        actor.resources = {"money": 0, "propaganda": 0}

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {payload.get("red_town", "新竹"): 1}
        red.hand = []

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
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {
            actor.id: actor.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {actor.id: actor.base, red.id: red.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "red_player_id": red.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "state": game.state(),
            "move_to_enemy_result": (
                game.move_organization("桃園", "新竹", "rail")
                if payload.get("probe_move", False)
                else None
            ),
            "card_build_choices": game._card_build_town_choices(
                actor, {"type": "build", "range": 1}
            ),
        }
