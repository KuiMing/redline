"""Test-only route for replacing a player's hand and turn setup."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from server.cards import Card
from server.game import TurnPhase


class SetHandTestRoutes:
    def __init__(self, manager_provider: Callable[[], Any]):
        self._manager_provider = manager_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/set-hand",
            self.test_set_hand,
            methods=["POST"],
        )

    def test_set_hand(self, payload: dict):
        game_id = payload.get("game_id")
        player_id = payload.get("player_id")
        cards = payload.get("cards", [])
        turn_phase = payload.get("turn_phase")
        set_current_player = bool(payload.get("set_current_player"))
        restrict_build = bool(payload.get("restrict_build"))

        game = self._manager_provider().get_game(game_id)
        if not game:
            return {"error": "Game not found"}

        player = next((p for p in game.players if p.id == player_id), None)
        if not player:
            return {"error": "Player not found"}

        player.hand = []
        for name in cards:
            card_def = next(
                (c for c in game.structured_cards if c.get("name") == name),
                None,
            )
            if card_def:
                player.hand.append(
                    Card(
                        card_def["name"],
                        card_def.get("type", "test"),
                        card_def.get("resources", {}),
                    )
                )
            else:
                player.hand.append(game._starter_card(name))

        if turn_phase == "action":
            game.turn_phase = TurnPhase.ACTION
        elif turn_phase == "event":
            game.turn_phase = TurnPhase.EVENT
        elif turn_phase == "end":
            game.turn_phase = TurnPhase.END

        if restrict_build:
            game.event_modifiers = [{"type": "restrict_build", "remaining_turns": 1}]
        else:
            game.event_modifiers = [
                modifier
                for modifier in (game.event_modifiers or [])
                if (modifier or {}).get("type") != "restrict_build"
            ]

        if set_current_player:
            for idx, candidate in enumerate(game.players):
                if candidate.id == player_id:
                    game.current_player_index = idx
                    break

        return {
            "success": True,
            "hand": [c.name for c in player.hand],
            "turn_phase": game.turn_phase,
            "current_player": game.current_player().name if game.current_player() else None,
            "current_player_id": game.current_player().id if game.current_player() else None,
        }
