"""Test-only route for the bait exhaustion (誘導虛耗) UI proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class BaitExhaustionUiTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-bait-exhaustion-ui",
            self.test_setup_bait_exhaustion_ui,
            methods=["POST"],
        )

    def test_setup_bait_exhaustion_ui(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        viewer = game.players[0]
        red = game.players[1]

        viewer.faction_id = payload.get("faction_id", "red_army")
        viewer.base = payload.get("base", "北京")
        viewer.organizations = payload.get("orgs") or {viewer.base: 1}
        viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
        viewer.hand = [
            Card("誘導虛耗", "command", {"propaganda": 1}),
            Card("可移除手牌", "command", {}),
        ]
        top_card_name = payload.get("draw_top_card", "宣傳家")
        viewer.deck.draw_pile = [Card(top_card_name, "propaganda", {"propaganda": 1})]
        viewer.deck.discard_pile = []

        red.faction_id = "hong_kong"
        red.base = "香港城"
        red.organizations = {"香港城": 1}
        red.hand = [Card("對手被棄牌", "command", {})]
        red.deck.draw_pile = [Card("對手抽牌A", "command", {})]
        red.deck.discard_pile = []

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
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {
            viewer.id: viewer.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "state": game.state(),
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
        }
