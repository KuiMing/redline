"""Test-only route for the support card play proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class SupportCardPlayTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-support-card-play",
            self.test_setup_support_card_play,
            methods=["POST"],
        )

    def test_setup_support_card_play(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "player"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        player = game.players[0]
        red = game.players[1]

        player.faction_id = payload.get("faction_id", "tibet_dehradun")
        player.base = payload.get("base", "德拉敦")
        player.organizations = payload.get("orgs") or {player.base: 1}
        player.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
        player.hand = [
            game._make_support_card(
                payload.get("support_name", "印度奧援"),
                variant_index=int(payload.get("variant_index", 0) or 0),
            )
        ]
        player.deck.draw_pile = [Card("補牌A", "command", {}), Card("補牌B", "command", {})]
        player.deck.discard_pile = []

        red.faction_id = payload.get("enemy_faction_id", "red_army")
        red.base = payload.get("enemy_base", "北京")
        red.organizations = payload.get("enemy_orgs") or {"北京": 1}
        red.hand = [
            Card(name, "reaction", {}) for name in payload.get("enemy_hand_names", [])
        ]
        red.deck.draw_pile = [Card("紅軍抽牌A", "command", {})]
        red.deck.discard_pile = []

        if "distraction_supply" in payload:
            game.static_purchase_supply["分神"] = max(
                0, int(payload.get("distraction_supply", 0) or 0)
            )

        mission_name = payload.get("mission_name")
        if mission_name:
            mission = game._event_by_name(mission_name)
            if mission is None:
                return {"error": f"Unknown mission event: {mission_name}"}
            game.current_event = dict(mission)
            trigger = game.current_event.get("trigger") or {}
            required = int(trigger.get("count", 1) or 1)
            game.event_progress = {
                "count": 0,
                "required": required,
                "succeeded": False,
                "settled": False,
                "status": "active",
            }
            game.event_notification = game._event_display_payload()

        game.purchase_area = []
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
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {player.id: player.base, red.id: red.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": player.id,
            "red_player_id": red.id,
            "support_name": payload.get("support_name", "印度奧援"),
            "turn_phase": game.turn_phase,
            "game_phase": game.game_phase,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "support_tier": game._support_card_tier(player, player.hand[0])[0],
            "state": game.state(),
        }
