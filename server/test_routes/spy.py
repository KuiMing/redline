"""Test-only route for the spy card (派遣間諜/內應間諜) proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class SpyTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-spy-proof",
            self.test_setup_spy_proof,
            methods=["POST"],
        )

    def test_setup_spy_proof(self, payload: dict):
        runtime = self._runtime_provider()
        card_name = payload.get("card_name", "派遣間諜")
        if card_name not in {"派遣間諜", "內應間諜"}:
            return {"error": "Unsupported spy card"}

        game_id = str(uuid.uuid4())
        players = [
            (str(uuid.uuid4()), payload.get("player_name", "viewer")),
            (str(uuid.uuid4()), payload.get("enemy_name", "enemy")),
        ]
        game = Game(players)
        player = game.players[0]
        enemy = game.players[1]

        player.faction_id = payload.get("faction_id", "red_army")
        player.base = payload.get("base", "北京")
        enemy.faction_id = payload.get("enemy_faction_id", "taiwan_green")
        enemy.base = payload.get("enemy_base", "臺北")

        default_player_orgs = {
            "派遣間諜": {"北京": 1, "上海": 1},
            "內應間諜": {"北京": 1},
        }
        default_enemy_orgs = {
            "派遣間諜": {"天津": 1, "杭州": 1, "香港城": 1},
            "內應間諜": {"天津": 1, "香港城": 1},
        }
        player.organizations = payload.get("orgs") or default_player_orgs[card_name]
        enemy.organizations = payload.get("enemy_orgs") or default_enemy_orgs[card_name]
        player.resources = {"money": 0, "propaganda": 0}
        enemy.resources = {"money": 0, "propaganda": 0}
        resources = {"propaganda": 1} if card_name == "派遣間諜" else {"propaganda": 2}
        player.hand = [Card(card_name, "spy", resources)]
        enemy.hand = [Card("對手手牌1", "command", {}), Card("對手手牌2", "command", {})]
        player.deck.draw_pile = []
        player.deck.discard_pile = []
        enemy.deck.draw_pile = []
        enemy.deck.discard_pile = []

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = player.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id,
            enemy.id: enemy.faction_id,
        }
        runtime.lobby_bases[game_id] = {player.id: player.base, enemy.id: enemy.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": player.id,
            "enemy_id": enemy.id,
            "card_name": card_name,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id, "base": p.base}
                for p in game.players
            ],
            "state": game.state(),
        }
