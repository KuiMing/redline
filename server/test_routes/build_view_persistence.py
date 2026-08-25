"""Test-only route for the two-stage build-view persistence proof."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from server.cards import Card
from server.game import GamePhase, TurnPhase


class BuildViewPersistenceTestRoutes:
    def __init__(
        self,
        manager_provider: Callable[[], Any],
        broadcaster_provider: Callable[[], Any],
    ):
        self._manager_provider = manager_provider
        self._broadcaster_provider = broadcaster_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-build-view-persistence-proof",
            self.test_setup_build_view_persistence_proof,
            methods=["POST"],
        )

    async def test_setup_build_view_persistence_proof(self, payload: dict):
        game_id = payload.get("game_id")
        player_id = payload.get("player_id")
        stage = payload.get("stage", "first")
        game = self._manager_provider().get_game(game_id)
        if not game:
            return {"error": "Game not found"}
        player = next(
            (candidate for candidate in game.players if candidate.id == player_id),
            None,
        )
        if not player:
            return {"error": "Player not found"}
        if stage not in {"first", "second"}:
            return {"error": "Unknown build-view proof stage"}
        if stage == "second" and game.pending_choice:
            return {"error": "First build session is still pending"}

        card_names = ["組織經驗丙"] if stage == "first" else ["組織經驗乙"]
        cards = []
        for name in card_names:
            card_def = next(
                (card for card in game.structured_cards if card.get("name") == name),
                None,
            )
            if card_def is None:
                return {"error": f"Unknown action card: {name}"}
            cards.append(
                Card(
                    card_def["name"],
                    card_def.get("type", "test"),
                    card_def.get("resources", {}),
                )
            )

        player.hand = cards
        if stage == "first":
            player.faction_id = "liberals"
            player.base = "香港城"
            player.organizations = {"香港城": 1, "舊金山": 1}
            player.deck.discard_pile = []
            for other in game.players:
                if other is player:
                    continue
                other.hand = []
                if other.faction_id == "red_army":
                    other.base = "北京"
                    other.organizations = {"北京": 1}

            game.current_player_index = game.players.index(player)
            game.game_phase = GamePhase.MAIN
            game.turn_phase = TurnPhase.ACTION
            game.pending_base_choices = {}
            game.pending_choice = None
            game.turn_log = game._new_turn_log()
            game.action_log = []
            game._action_log_visibility = []
            game.current_event = None
            game.event_progress = {}
            game.event_notification = None
            game.event_modifiers = []
        else:
            await self._broadcaster_provider()(game_id, game)

        return {
            "success": True,
            "stage": stage,
            "hand": [card.name for card in player.hand],
            "organizations": dict(player.organizations),
            "turn_phase": game.turn_phase,
        }
