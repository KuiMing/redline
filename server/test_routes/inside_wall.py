"""Test-only route for constructing the inside-wall proof state."""

from collections.abc import Callable
import uuid

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class InsideWallTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-inside-wall-proof",
            self.test_setup_inside_wall_proof,
            methods=["POST"],
        )

    def test_setup_inside_wall_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "Taiwan"), (str(uuid.uuid4()), "Red")]
        game = Game(players)
        taiwan, red = game.players
        taiwan.faction_id = "taiwan_green"
        red.faction_id = "red_army"

        inside_count = max(0, int(payload.get("inside_count", 0) or 0))
        outside_count = max(0, int(payload.get("outside_count", 8) or 0))
        inside_towns = [
            town
            for town in game._towns_for_region_alias("china")
            if game.can_faction_develop_in_town(taiwan.faction_id, town)
        ]
        outside_towns = [
            town
            for town in game._towns_for_region_alias("taiwan")
            if game.can_faction_develop_in_town(taiwan.faction_id, town)
        ]
        if len(inside_towns) < inside_count or len(outside_towns) < outside_count:
            return {"error": "Not enough canonical towns for inside-wall proof"}

        taiwan.base = outside_towns[0]
        red.base = "北京"
        taiwan.organizations = {
            town: 1
            for town in inside_towns[:inside_count] + outside_towns[:outside_count]
        }
        red.organizations = {}
        for player in game.players:
            player.hand = []
            player.deck.discard_pile = []
            player.resources = {"money": 0, "propaganda": 0}

        game.current_player_index = 0
        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.ACTION
        game.pending_base_choices = {}
        game.pending_choice = None
        noop_event = game._event_by_name("歲月靜好")
        game.current_event = dict(noop_event or {})
        game.event_progress = {
            "count": 0,
            "required": 0,
            "succeeded": True,
            "settled": True,
            "status": "idle",
        }
        game.event_notification = game._event_display_payload()
        game.event_modifiers = []
        game.id = game_id
        game._check_era_trigger()

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(
            game_id, {}
        )
        runtime.lobby[game_id] = [
            (player.id, player.name) for player in game.players
        ]
        runtime.lobby_hosts[game_id] = taiwan.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id for player in game.players
        }
        runtime.lobby_bases[game_id] = {}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": taiwan.id,
            "inside_count": inside_count,
            "outside_count": outside_count,
            "state": game.state(taiwan.id),
        }
