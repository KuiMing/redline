"""Test-only routes for the draw-privacy proof (setup + trigger)."""

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class DrawPrivacyTestRoutes:
    def __init__(
        self,
        runtime_provider: Callable[[], GameSetupRuntime],
        broadcaster_provider: Callable[[], Any],
    ):
        self._runtime_provider = runtime_provider
        self._broadcaster_provider = broadcaster_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-draw-privacy-proof",
            self.test_setup_draw_privacy_proof,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/trigger-draw-privacy-proof",
            self.test_trigger_draw_privacy_proof,
            methods=["POST"],
        )

    def test_setup_draw_privacy_proof(self):
        """建立三位玩家的抽牌隱私 Browser proof，初始狀態不含抽牌紀錄。"""
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        game = Game(
            [
                (str(uuid.uuid4()), "紅軍"),
                (str(uuid.uuid4()), "哈薩克"),
                (str(uuid.uuid4()), "旁觀玩家"),
            ]
        )
        red, kazakh, observer = game.players
        for player, faction_id, base in (
            (red, "red_army", "北京"),
            (kazakh, "kazakh", "阿拉木圖"),
            (observer, "hong_kong", "香港城"),
        ):
            player.faction_id = faction_id
            player.base = base
            player.organizations = {base: 1}
            player.hand = []
            player.deck.draw_pile = []
            player.deck.discard_pile = []

        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.ACTION
        game.current_player_index = game.players.index(kazakh)
        game.pending_base_choices = {}
        game.pending_choice = None
        game.action_log = []
        game._action_log_visibility = []
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = {}
        runtime.lobby[game_id] = [(player.id, player.name) for player in game.players]
        runtime.lobby_hosts[game_id] = red.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id for player in game.players
        }
        runtime.lobby_bases[game_id] = {player.id: player.base for player in game.players}
        runtime.lobby_ready[game_id] = {player.id: True for player in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "red_player_id": red.id,
            "kazakh_player_id": kazakh.id,
            "observer_player_id": observer.id,
        }

    async def test_trigger_draw_privacy_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(payload.get("game_id") or "")
        game = runtime.manager.games.get(game_id)
        if game is None:
            return {"error": "Game not found"}
        kazakh = next(
            (player for player in game.players if player.faction_id == "kazakh"), None
        )
        if kazakh is None:
            return {"error": "Kazakh player not found"}
        kazakh.deck.draw_pile = [Card("樂捐者", "starter", {}), Card("追隨者", "starter", {})]
        kazakh.deck.discard_pile = []
        game._draw_player_cards(kazakh, 2, source="era")
        await self._broadcaster_provider()(game_id, game)
        return {"success": True, "draw_count": 2}
