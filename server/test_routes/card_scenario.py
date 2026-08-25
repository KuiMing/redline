"""Test-only route for preparing a named card scenario."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


class CardScenarioTestRoutes:
    def __init__(self, manager_provider: Callable[[], Any]):
        self._manager_provider = manager_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-card-scenario",
            self.test_setup_card_scenario,
            methods=["POST"],
        )

    def test_setup_card_scenario(self, payload: dict):
        game_id = payload.get("game_id")
        player_id = payload.get("player_id")
        card_name = payload.get("card_name")

        game = self._manager_provider().get_game(game_id)
        if not game:
            return {"error": "Game not found"}

        return game.setup_test_card_scenario(player_id, card_name)
