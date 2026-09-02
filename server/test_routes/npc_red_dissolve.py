"""Test-only route for the 全國人大召開 failed-event red-dissolve proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class NpcRedDissolveTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-national-people-congress-red-dissolve-proof",
            self.test_setup_national_people_congress_red_dissolve_proof,
            methods=["POST"],
        )

    def test_setup_national_people_congress_red_dissolve_proof(self, payload: dict):
        runtime = self._runtime_provider()
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players, market_mode="all_cards")
        viewer = game.players[0]
        red = game.players[1]
        viewer.faction_id = "liberals"
        red.faction_id = "red_army"
        viewer.base = "臺北"
        red.base = "北京"
        viewer.organizations = {"北京": 1}
        red.organizations = {"臺北": 1}
        viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        event = game._event_by_name("全國人大召開")
        game.current_event = event
        game.event_progress = {
            "count": 0,
            "required": int((event or {}).get("trigger", {}).get("count", 1) or 1),
            "succeeded": False,
            "settled": True,
            "status": "failure",
        }
        if event:
            game._apply_event_effect(event.get("failure"), viewer, outcome="failure")
        game.event_notification = game._event_display_payload()
        game.event_deck.draw_pile = []
        game.event_deck.discard_pile = [event] if event else []

        game_id = str(uuid.uuid4())
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
            "red_player_id": red.id,
            "event_name": event.get("name") if event else None,
            "url": f"/?game_id={game_id}&player_id={red.id}",
            "state": game.state(),
        }
