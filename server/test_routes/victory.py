"""Test-only route for the victory screen proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase
from server.test_routes.runtime import GameSetupRuntime


class VictoryTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-victory-proof",
            self.test_setup_victory_proof,
            methods=["POST"],
        )

    def test_setup_victory_proof(self, payload: dict):
        """Test-only：建立一場已分出勝負的 2 人局，供勝利畫面 UI proof 使用。

        payload.winner：'red_army'（紅軍保底勝）或省略（預設綠線玩家名獲勝）。
        """
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        green_name = payload.get("winner_name", "GREEN")
        players = [(str(uuid.uuid4()), green_name), (str(uuid.uuid4()), "RED")]
        game = Game(players)
        green, red = game.players

        green.faction_id = "taiwan_green"
        green.base = "臺北"
        green.organizations = {"臺北": 3, "桃園": 2}
        green.resources = {"money": 2, "propaganda": 4}
        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 5, "天津": 2}
        red.resources = {"money": 1, "propaganda": 0}

        game.game_phase = GamePhase.FINISHED
        game.turn = int(payload.get("turn", 21) or 21)
        game.winner = payload.get("winner", green_name)
        game.co_winners = list(payload.get("co_winners", []) or [])
        game.pending_base_choices = {}
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = green.id
        runtime.lobby_factions[game_id] = {
            green.id: green.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {green.id: green.base, red.id: red.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": green.id,
            "red_player_id": red.id,
            "winner": game.winner,
            "state": game.state(),
        }
