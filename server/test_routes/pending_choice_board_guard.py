"""Test-only route for the pending-choice board guard proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class PendingChoiceBoardGuardTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-pending-choice-board-guard",
            self.test_setup_pending_choice_board_guard,
            methods=["POST"],
        )

    def test_setup_pending_choice_board_guard(self):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "player"), (str(uuid.uuid4()), "red")]
        game = Game(players, market_mode="all_cards")
        actor, red = game.players

        actor.faction_id = "taiwan_green"
        actor.base = "臺北"
        actor.organizations = {"臺北": 1, "桃園": 1}
        actor.moves_left = 3
        actor.resources = {"money": 0, "propaganda": 0}
        actor.hand = []

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1, "上海": 1}
        red.hand = []

        game.current_player_index = 0
        game.round_start_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        legal_moves = game._legal_organization_moves()
        move_origin = next(town for town in legal_moves if town != actor.base)
        move_mode, move_options = next(
            (mode, options) for mode, options in legal_moves[move_origin].items() if options
        )
        game.pending_choice = {
            "type": "card_choice",
            "choice_key": "recruit_talent",
            "player_id": actor.id,
            "cards": [Card("候選牌", "command", {})],
            "prompt": "網羅人才：請選擇一張牌。",
        }
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {
            actor.id: actor.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {actor.id: actor.base, red.id: red.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "red_player_id": red.id,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
            "move": {
                "from": move_origin,
                "to": move_options[0]["town"],
                "mode": move_mode,
            },
            "state": game.state(actor.id),
        }
