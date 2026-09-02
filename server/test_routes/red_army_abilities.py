"""Test-only route for the red army abilities proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class RedArmyAbilitiesTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-red-army-abilities-proof",
            self.test_setup_red_army_abilities_proof,
            methods=["POST"],
        )

    def test_setup_red_army_abilities_proof(self, payload: dict | None = None):
        runtime = self._runtime_provider()
        payload = payload or {}
        empty_actions = bool(payload.get("empty_actions"))
        game_id = str(uuid.uuid4())
        players = [("red-proof", "紅軍"), ("lib-proof", "自由派"), ("hk-proof", "香港")]
        game = Game(players, market_mode="all_cards")
        red, liberals, hong_kong = game.players

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        red.hand = [Card("手牌甲", "test", {}), Card("手牌乙", "test", {})]
        red.deck.draw_pile = [
            Card("補牌甲", "test", {}),
            Card("補牌乙", "test", {}),
            Card("補牌丙", "test", {}),
        ]
        red.deck.discard_pile = []

        liberals.faction_id = "liberals"
        liberals.base = "香港城"
        liberals.organizations = {"天津": 1}
        liberals.deck.draw_pile = []
        liberals.deck.discard_pile = []

        hong_kong.faction_id = "hong_kong"
        hong_kong.base = "香港城"
        hong_kong.organizations = {"上海": 1}

        if empty_actions:
            red.hand = []
            red.deck.draw_pile = []
            red.deck.discard_pile = []
            liberals.hand = []
            liberals.organizations = {}
            hong_kong.hand = []
            hong_kong.organizations = {}
            game.static_purchase_supply["內鬥"] = 0
            game.static_purchase_supply["分神"] = 0

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.turn_log = game._new_turn_log()
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = red.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": red.id,
            "target_player_id": liberals.id,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
