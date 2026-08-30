"""Test-only route for the 展現實力 reward-choice proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class ShowStrengthChoiceTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-show-strength-choice-proof",
            self.test_setup_show_strength_choice_proof,
            methods=["POST"],
        )

    def test_setup_show_strength_choice_proof(self, payload: dict):
        """建立「展現實力」已達成且等待能力擁有者選擇獎勵的 Browser proof。"""
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "滿洲玩家"), (str(uuid.uuid4()), "紅軍玩家")]
        game = Game(players)
        player, red = game.players

        player.faction_id = "manchuria"
        player.base = "東京"
        player.organizations = {"東京": 1}
        player.resources = {"money": 0, "propaganda": 0}
        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        game.current_player_index = 0
        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.ACTION
        game.pending_base_choices = {}
        game.turn_log = game._new_turn_log()
        game.turn_log["played_nonstarter_names"] = ["甲", "乙", "丙"]
        game.current_event = None
        game.event_progress = {}
        game.event_modifiers = []
        game.id = game_id

        game._apply_card_play_faction_abilities(
            player, cost_has_money=False, cost_has_propaganda=False
        )

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(candidate.id, candidate.name) for candidate in game.players]
        runtime.lobby_hosts[game_id] = player.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {player.id: player.base, red.id: red.base}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": player.id,
            "pending_choice": game.pending_choice,
            "resources": dict(player.resources),
        }
