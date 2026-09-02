"""Test-only route for forcing the base-selection proof state."""

from collections.abc import Callable
import uuid

from fastapi import APIRouter

from server.game import Game, GamePhase
from server.test_routes.runtime import GameSetupRuntime


class ForceBaseSelectionTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/force-base-selection",
            self.test_force_base_selection,
            methods=["POST"],
        )

    def test_force_base_selection(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = payload.get("game_id")
        faction_ids = payload.get("faction_ids", [])
        player_names = payload.get("player_names") or [
            f"player{i+1}" for i in range(len(faction_ids))
        ]
        chosen_bases = payload.get("chosen_bases") or {}

        if len(faction_ids) < 2:
            return {"error": "Need at least 2 faction ids"}

        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), name) for name in player_names]
        game = Game(players)
        for player, faction_id in zip(game.players, faction_ids):
            player.faction_id = faction_id

        game.pending_base_choices = game._compute_pending_base_choices()
        for player in game.players:
            base_name = chosen_bases.get(player.name) or chosen_bases.get(player.id)
            if not base_name:
                continue
            result = getattr(game, "choose_base")(player.id, base_name)
            if result.get("error"):
                return {
                    "error": result["error"],
                    "player": player.name,
                    "base_name": base_name,
                }

        if game.pending_base_choices:
            game.game_phase = GamePhase.BASE_SELECTION
        else:
            game.game_phase = GamePhase.MAIN
            first_non_red = next(
                (
                    idx
                    for idx, player in enumerate(game.players)
                    if player.faction_id != "red_army"
                ),
                0,
            )
            game.current_player_index = first_non_red

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(
            game_id, {}
        )
        runtime.lobby[game_id] = list(
            zip(
                [player.id for player in game.players],
                [player.name for player in game.players],
            )
        )
        runtime.lobby_hosts[game_id] = game.players[0].id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id for player in game.players
        }
        runtime.lobby_bases[game_id] = {
            player.id: player.base for player in game.players if player.base
        }

        return {
            "success": True,
            "game_id": game_id,
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "faction": player.faction_id,
                    "base": player.base,
                }
                for player in game.players
            ],
            "pending_base_choices": game.pending_base_choices,
            "game_phase": game.game_phase,
        }
