"""Test-only route for canonical scope-audit proof states."""

from collections.abc import Callable
import uuid

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class ScopeAuditTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-scope-audit-proof",
            self.test_setup_scope_audit_proof,
            methods=["POST"],
        )

    def test_setup_scope_audit_proof(self, payload: dict):
        runtime = self._runtime_provider()
        scenario = str(payload.get("scenario") or "")
        include_taiwan = scenario == "red_taiwan_with_taiwan"
        players = [(str(uuid.uuid4()), "Actor"), (str(uuid.uuid4()), "Opponent")]
        if include_taiwan:
            players.append((str(uuid.uuid4()), "Taiwan"))
        game = Game(players)
        actor, opponent = game.players[:2]
        actor.id, actor.name = players[0]
        opponent.id, opponent.name = players[1]
        actor.organizations = {}
        opponent.organizations = {}

        inside = [
            town
            for town in game.map.get("towns", {})
            if game._is_inside_wall_town(town)
        ]
        outside = [
            town
            for town in game.map.get("towns", {})
            if not game._is_inside_wall_town(town)
        ]
        mongolia_outside = [
            town
            for town in game._towns_for_region_alias("mongolian_plateau")
            if not game._is_inside_wall_town(town)
        ]
        taiwan_towns = list(game._towns_for_region_alias("taiwan"))

        if scenario in {"mongolia_outside", "mongolia_inside"}:
            actor.faction_id = "mongol"
            opponent.faction_id = "red_army"
            selected = (
                mongolia_outside[:4]
                if scenario == "mongolia_outside"
                else inside[:4]
            )
            if len(selected) < 4:
                return {"error": "Not enough canonical towns for Mongolia scope proof"}
            actor.organizations = {town: 1 for town in selected}
        elif scenario in {
            "hong_kong_outside_victory",
            "hong_kong_inside_victory",
        }:
            actor.faction_id = "hong_kong"
            opponent.faction_id = "red_army"
            selected = (
                outside[:14]
                if scenario == "hong_kong_outside_victory"
                else inside[:14]
            )
            actor.organizations = {town: 1 for town in selected}
        elif scenario in {
            "red_taiwan_without_taiwan",
            "red_taiwan_with_taiwan",
        }:
            actor.faction_id = "red_army"
            opponent.faction_id = "liberals"
            if len(taiwan_towns) < 14:
                return {
                    "error": "Not enough canonical Taiwan towns for Red Army victory proof"
                }
            actor.organizations = {town: 1 for town in taiwan_towns[:14]}
            if include_taiwan:
                taiwan = game.players[2]
                taiwan.id, taiwan.name = players[2]
                taiwan.faction_id = "taiwan_green"
                taiwan.organizations = {}
        else:
            return {"error": f"Unknown scope audit scenario: {scenario}"}

        for player in game.players:
            player.hand = []
            player.deck.discard_pile = []
            player.resources = {"money": 0, "propaganda": 0}
        actor.base = (
            "北京"
            if actor.faction_id == "red_army"
            else next(iter(actor.organizations), None)
        )
        opponent.base = (
            "北京"
            if opponent.faction_id == "red_army"
            else next(iter(opponent.organizations), None)
        )
        game.current_player_index = 0
        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.ACTION
        game.pending_base_choices = {}
        game.pending_choice = None
        game.current_event = dict(game._event_by_name("歲月靜好") or {})
        game.event_progress = {
            "count": 0,
            "required": 0,
            "succeeded": True,
            "settled": True,
            "status": "idle",
        }
        game.event_notification = game._event_display_payload()
        game.event_modifiers = []
        game._check_era_trigger()
        game._check_victory()

        game_id = str(uuid.uuid4())
        game.id = game_id
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(
            game_id, {}
        )
        runtime.lobby[game_id] = [
            (player.id, player.name) for player in game.players
        ]
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id for player in game.players
        }
        runtime.lobby_bases[game_id] = {}
        return {
            "success": True,
            "scenario": scenario,
            "game_id": game_id,
            "player_id": actor.id,
            "state": game.state(actor.id),
        }
