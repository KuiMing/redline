"""Test-only route for the event card (預設香港抗暴之戰) proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class EventCardTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-event-card-proof",
            self.test_setup_event_card_proof,
            methods=["POST"],
        )

    def test_setup_event_card_proof(self, payload: dict):
        runtime = self._runtime_provider()
        event_name = payload.get("event_name") or "香港抗暴之戰"
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players, market_mode="all_cards")
        game.players[0].faction_id = payload.get("viewer_faction") or "liberals"
        game.players[1].faction_id = "red_army"
        game.players[0].base = (
            "香港城" if game.players[0].faction_id == "hong_kong" else "臺北"
        )
        game.players[1].base = "北京"
        game.players[0].organizations = dict(
            payload.get("viewer_orgs") or {game.players[0].base: 1}
        )
        game.players[1].organizations = dict(payload.get("red_orgs") or {"北京": 1})
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.EVENT
        game.players[0].hand = [
            Card("合作談判", "command", {}),
            Card("追隨者", "propaganda", {"propaganda": 1}),
        ]
        game.players[0].deck.discard_pile = []
        event = game._event_by_name(event_name) or game._event_by_name("香港抗暴之戰")
        if payload.get("hk_end_turn_relocation_timing") and event:
            game.current_event = event
            game.event_progress = {
                "count": 0,
                "required": int(event.get("trigger", {}).get("count", 1) or 1),
                "succeeded": False,
                "settled": False,
                "status": "active",
                "settlement_target_player_id": game.players[0].id,
            }
            game.event_notification = game._event_display_payload()
            game.event_deck.draw_pile = []
            game.event_deck.discard_pile = []
            game.turn_phase = TurnPhase.END
        elif payload.get("hk_failed_relocation") and event:
            game.current_event = event
            game.event_progress = {
                "count": 0,
                "required": int(event.get("trigger", {}).get("count", 1) or 1),
                "succeeded": False,
                "settled": False,
                "status": "active",
            }
            game._settle_current_event()
            game.event_deck.draw_pile = []
            game.event_deck.discard_pile = []
            game.turn_phase = TurnPhase.ACTION
        elif payload.get("hk_free_relocation") and event:
            game.current_event = event
            game.event_progress = {
                "count": int(event.get("trigger", {}).get("count", 1) or 1),
                "required": int(event.get("trigger", {}).get("count", 1) or 1),
                "succeeded": True,
                "settled": False,
                "status": "success_pending",
            }
            game._settle_current_event()
            game.event_deck.draw_pile = []
            game.event_deck.discard_pile = []
            game.turn_phase = TurnPhase.ACTION
        elif payload.get("current_event_active") and event:
            game.current_event = event
            forced_status = str(payload.get("event_status") or "active")
            game.event_progress = {
                "count": 0,
                "required": int(event.get("trigger", {}).get("count", 1) or 1),
                "succeeded": forced_status == "success",
                "settled": forced_status in {"idle", "success", "failure", "auto"},
                "status": forced_status,
            }
            game.event_notification = game._event_display_payload()
            game.turn_phase = TurnPhase.ACTION
            game.event_deck.draw_pile = []
            game.event_deck.discard_pile = []
        else:
            game.event_deck.draw_pile = [event] if event else []
            game.event_deck.discard_pile = []

        requested_current_player_index = int(
            payload.get("current_player_index", game.current_player_index) or 0
        )
        if 0 <= requested_current_player_index < len(game.players):
            game.current_player_index = requested_current_player_index

        game_id = str(uuid.uuid4())
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = game.players[0].id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": game.players[0].id,
            "red_player_id": game.players[1].id,
            "event_name": event.get("name") if event else None,
            "url": f"/?game_id={game_id}&player_id={game.players[0].id}",
            "state": game.state(),
        }
