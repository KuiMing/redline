"""Test-only route for the India support-card purchase proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class IndiaSupportPurchaseTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-india-support-purchase",
            self.test_setup_india_support_purchase,
            methods=["POST"],
        )

    def test_setup_india_support_purchase(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "tibet"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        tibet = game.players[0]
        red = game.players[1]

        tibet.faction_id = "tibet_dehradun"
        tibet.base = payload.get("base", "德拉敦")
        tibet.organizations = {tibet.base: 1}
        tibet.resources = {"money": 5, "propaganda": 5}
        tibet.hand = []

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}

        support_name = payload.get("support_name", "印度奧援")
        game.purchase_area = [game._make_support_card(support_name)]
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
        runtime.lobby_hosts[game_id] = tibet.id
        runtime.lobby_factions[game_id] = {
            tibet.id: tibet.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {tibet.id: tibet.base, red.id: red.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": tibet.id,
            "support_name": support_name,
            "turn_phase": game.turn_phase,
            "game_phase": game.game_phase,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
