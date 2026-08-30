"""Test-only route for the 一帶一路 red-turn handoff proof state."""

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class BeltRoadRedTurnTestRoutes:
    def __init__(
        self,
        runtime_provider: Callable[[], GameSetupRuntime],
        broadcaster_provider: Callable[[], Any],
    ):
        self._runtime_provider = runtime_provider
        self._broadcaster_provider = broadcaster_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-belt-road-red-turn-proof",
            self.test_setup_belt_road_red_turn_proof,
            methods=["POST"],
        )

    async def test_setup_belt_road_red_turn_proof(self, payload: dict):
        runtime = self._runtime_provider()
        requested_game_id = str(payload.get("game_id") or "")
        game = runtime.manager.games.get(requested_game_id) if requested_game_id else None
        if game:
            viewer_id = str(payload.get("player_id") or "")
            red_id = str(payload.get("red_player_id") or "")
            viewer = next(
                (player for player in game.players if player.id == viewer_id), None
            )
            red = next((player for player in game.players if player.id == red_id), None)
            if not viewer or not red or viewer is red:
                return {"success": False, "error": "Formal proof players not found"}
            if game.players.index(viewer) != 0 or game.players.index(red) != 1:
                return {
                    "success": False,
                    "error": "Formal proof requires viewer seat 0 and red seat 1",
                }
            game_id = requested_game_id
        else:
            players = [(str(uuid.uuid4()), "BEN"), (str(uuid.uuid4()), "紅軍")]
            game = Game(players, market_mode="all_cards")
            viewer = game.players[0]
            red = game.players[1]
            game_id = str(uuid.uuid4())
        viewer.faction_id = payload.get("viewer_faction", "liberals")
        red.faction_id = "red_army"
        viewer.base = payload.get("viewer_base", "臺北")
        red.base = "北京"
        viewer.organizations = {viewer.base: 1}
        red.organizations = {"北京": 1}
        viewer.hand = [Card("BEN 保留手牌", "money", {"money": 1})]
        red.hand = [Card("紅軍保留手牌", "propaganda", {"propaganda": 1})]
        game.pending_base_choices = {}
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.round_start_player_index = 0
        game.turn_phase = TurnPhase.EVENT
        event_name = payload.get("event_name", "一帶一路 南洋")
        event = game._event_by_name(event_name)
        game.event_deck.draw_pile = [event] if event else []
        game.event_deck.discard_pile = []
        game.current_event = None
        game.event_progress = None
        game.event_notification = None
        game.pending_choice = None
        draw_result = game.advance_turn_phase()
        initial_state = game.state()
        advance_results = []
        if payload.get("advance_to_red", False):
            # EVENT -> ACTION，再一次「結束行動階段」就把席位交給紅軍（合併後不再需要第三次）。
            for _ in range(2):
                advance_results.append(game.advance_turn_phase())
                if game.current_player_index == 1 and game.turn_phase == TurnPhase.EVENT:
                    break
        if payload.get("stale_visual_build", False):
            stale_town = payload.get("stale_town", "曼谷")
            if (
                game.pending_choice
                and game.pending_choice.get("choice_key") == "event_build_organization"
            ):
                red.organizations[stale_town] = max(1, red.organizations.get(stale_town, 0))

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        if requested_game_id:
            await self._broadcaster_provider()(game_id, game)
        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "red_player_id": red.id,
            "event_name": event_name,
            "draw_result": draw_result,
            "advance_results": advance_results,
            "initial_state": initial_state,
            "url": f"/?game_id={game_id}&player_id={red.id}",
            "state": game.state(),
        }
