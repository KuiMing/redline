"""Test-only route for the 中紀委 (red_army_ccdi_discard_draw) choice proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class CcdiChoiceTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-ccdi-choice",
            self.test_setup_ccdi_choice,
            methods=["POST"],
        )

    def test_setup_ccdi_choice(self, payload: dict):
        """Put a Red Army player straight into the 中紀委 (red_army_ccdi_discard_draw) choice,
        to exercise the cancellable-choice close/cancel behaviour."""
        runtime = self._runtime_provider()
        players = [(str(uuid.uuid4()), "red"), (str(uuid.uuid4()), "opp")]
        game = Game(players, market_mode="all_cards")
        red = game.players[0]
        opp = game.players[1]
        red.faction_id = "red_army"
        opp.faction_id = "liberals"
        red.base = "北京"
        red.organizations = {"北京": 1}
        opp.base = "臺北"
        opp.organizations = {"臺北": 1}
        red.hand = [
            Card("手牌甲", "command", {}),
            Card("手牌乙", "command", {}),
            Card("手牌丙", "command", {}),
        ]
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.turn_log = game._new_turn_log()

        game._activated_faction_action(red, "中紀委")

        game_id = str(uuid.uuid4())
        game.id = game_id
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = red.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": red.id,
            "url": f"/?game_id={game_id}&player_id={red.id}",
            "state": game.state(),
        }
