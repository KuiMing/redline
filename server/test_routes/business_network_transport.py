"""Test-only route for the business network (企業人脈) transport proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class BusinessNetworkTransportTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-business-network-transport-proof",
            self.test_setup_business_network_transport_proof,
            methods=["POST"],
        )

    def test_setup_business_network_transport_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        viewer = game.players[0]
        red = game.players[1]

        viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
        viewer.base = payload.get("base", "德拉敦")
        viewer.organizations = payload.get("orgs") or {viewer.base: 1}
        viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
        viewer.moves_left = 4
        viewer.hand = []

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        red.hand = []

        game.purchase_area = game._static_purchase_cards() + [
            Card("合作談判", "command", {"propaganda": 1}),
            Card("交通經驗乙", "transport", {"money": 2}),
            Card("模仿戰術", "command", {"propaganda": 2}),
            Card("資本家", "money", {"money": 3}),
            Card("填充D", "command", {}),
        ]
        game.pending_choice = {
            "type": "card_choice",
            "choice_key": "use_purchase_area_card",
            "player_id": viewer.id,
            "cards": [
                {
                    "card": game.purchase_area[6],
                    "name": getattr(
                        game.purchase_area[6], "name", str(game.purchase_area[6])
                    ),
                    "zone": "purchase_area",
                    "zone_label": "購買區槽位 1",
                    "purchase_index": 6,
                },
                {
                    "card": game.purchase_area[7],
                    "name": getattr(
                        game.purchase_area[7], "name", str(game.purchase_area[7])
                    ),
                    "zone": "purchase_area",
                    "zone_label": "購買區槽位 2",
                    "purchase_index": 7,
                },
                {
                    "card": game.purchase_area[8],
                    "name": getattr(
                        game.purchase_area[8], "name", str(game.purchase_area[8])
                    ),
                    "zone": "purchase_area",
                    "zone_label": "購買區槽位 3",
                    "purchase_index": 8,
                },
                {
                    "card": game.purchase_area[9],
                    "name": getattr(
                        game.purchase_area[9], "name", str(game.purchase_area[9])
                    ),
                    "zone": "purchase_area",
                    "zone_label": "購買區槽位 4",
                    "purchase_index": 9,
                },
                {
                    "card": game.purchase_area[10],
                    "name": getattr(
                        game.purchase_area[10], "name", str(game.purchase_area[10])
                    ),
                    "zone": "purchase_area",
                    "zone_label": "購買區槽位 5",
                    "purchase_index": 10,
                },
            ],
            "prompt": "企業人脈：選擇購買區正面朝上的 1 張牌，視同打出該牌。",
            "source_name": "企業人脈",
        }

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
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {
            viewer.id: viewer.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "turn_phase": game.turn_phase,
            "game_phase": game.game_phase,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
