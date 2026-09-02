"""Test-only route for the 貿易戰加劇 topdeck-from-discard choice proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class DiscardTopdeckChoiceTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-discard-topdeck-choice",
            self.test_setup_discard_topdeck_choice,
            methods=["POST"],
        )

    def test_setup_discard_topdeck_choice(self, payload: dict):
        """Put the viewer straight into a 貿易戰加劇 topdeck-from-discard card choice over a
        large discard pile, to exercise the scrollable choice grid."""
        runtime = self._runtime_provider()
        discard_count = int(payload.get("discard_count", 18) or 18)
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players, market_mode="all_cards")
        viewer = game.players[0]
        red = game.players[1]
        viewer.faction_id = "liberals"
        red.faction_id = "red_army"
        viewer.base = "臺北"
        red.base = "北京"
        viewer.organizations = {"臺北": 1}
        red.organizations = {"北京": 1}
        viewer.resources = {"money": 0, "propaganda": 0}
        viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        viewer.deck.draw_pile = [Card("原牌庫頂下方", "command", {})]
        viewer.deck.discard_pile = [
            Card(f"棄牌{i + 1:02d}", "command", {}) for i in range(discard_count)
        ]

        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        event = game._event_by_name("貿易戰加劇")
        game.current_event = event
        game.event_notification = game._event_display_payload()
        game.event_deck.draw_pile = []
        game.event_deck.discard_pile = []

        # Trigger the success effect directly so the topdeck-from-discard card
        # choice is pending.
        game._apply_event_effect({"type": "topdeck_from_discard", "count": 1}, viewer)

        game_id = str(uuid.uuid4())
        game.id = game_id
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "discard_count": discard_count,
            "url": f"/?game_id={game_id}&player_id={viewer.id}",
            "state": game.state(),
        }
