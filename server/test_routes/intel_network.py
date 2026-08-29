"""Test-only route for the information-network proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class IntelNetworkTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-intel-network-proof",
            self.test_setup_intel_network_proof,
            methods=["POST"],
        )

    def test_setup_intel_network_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [
            (str(uuid.uuid4()), "viewer"),
            (str(uuid.uuid4()), "enemyA"),
            (str(uuid.uuid4()), "enemyB"),
            (str(uuid.uuid4()), "enemyC"),
        ]
        game = Game(players)

        viewer, enemy_a, enemy_b, enemy_c = game.players

        viewer.faction_id = payload.get("viewer_faction", "red_army")
        viewer.base = payload.get("viewer_base", "北京")
        viewer.organizations = dict(
            payload.get("viewer_organizations") or {"北京": 1}
        )
        intel_card_count = max(1, int(payload.get("intel_card_count", 1) or 1))
        viewer.hand = [
            Card("情報網", "command", {}) for _ in range(intel_card_count)
        ]

        enemy_a.faction_id = payload.get("enemy_a_faction", "hong_kong")
        enemy_a.base = payload.get("enemy_a_base", "香港城")
        enemy_a_organizations = payload.get("enemy_a_organizations") or {
            "天津": 1,
            "香港城": 1,
            "廣州": 1,
        }
        enemy_a.organizations = dict(enemy_a_organizations)
        enemy_a.hand = [
            Card("敵方手牌A1", "command", {}),
            Card("敵方手牌A2", "command", {}),
        ]

        enemy_b.faction_id = payload.get("enemy_b_faction", "taiwan_green")
        enemy_b.base = payload.get("enemy_b_base", "臺北")
        enemy_b.organizations = dict(
            payload.get("enemy_b_organizations") or {"臺北": 1}
        )
        enemy_b.hand = [
            Card("敵方手牌B1", "command", {}),
            Card("敵方手牌B2", "command", {}),
        ]

        enemy_c.faction_id = payload.get("enemy_c_faction", "minyun")
        enemy_c.base = payload.get("enemy_c_base", "巴黎")
        enemy_c.organizations = dict(
            payload.get("enemy_c_organizations") or {"巴黎": 1, "上海": 1}
        )
        enemy_c.hand = [
            Card("敵方手牌C1", "command", {}),
            Card("敵方手牌C2", "command", {}),
        ]

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.id = game_id

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
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id for player in game.players
        }
        runtime.lobby_bases[game_id] = {
            player.id: player.base for player in game.players
        }

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "faction": player.faction_id,
                }
                for player in game.players
            ],
            "state": game.state(),
        }
