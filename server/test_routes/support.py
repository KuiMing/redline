"""Test-only route for the region support-card (臺灣奧援/北國奧援) proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class SupportTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-support-proof",
            self.test_setup_support_proof,
            methods=["POST"],
        )

    def test_setup_support_proof(self, payload: dict):
        runtime = self._runtime_provider()
        support_name = payload.get("support_name", "臺灣奧援")
        tier = int(payload.get("tier", 2) or 2)
        game_id = str(uuid.uuid4())
        players = [
            (str(uuid.uuid4()), payload.get("player_name", "player")),
            (str(uuid.uuid4()), payload.get("enemy_name", "red")),
        ]
        game = Game(players)

        player = game.players[0]
        enemy = game.players[1]

        default_player_faction = {
            "臺灣奧援": "taiwan_green",
            "北國奧援": "liberals",
        }
        default_player_base = {
            "臺灣奧援": "臺北",
            "北國奧援": "海參崴",
        }
        default_orgs_by_card = {
            "臺灣奧援": {
                3: {"臺北": 1, "屏東": 1, "佬沃": 1, "馬祖": 1},
                2: {"臺北": 1, "屏東": 1, "佬沃": 1, "馬祖": 1},
                1: {"東京": 1},
            },
            "北國奧援": {
                3: {"海參崴": 1},
                2: {"巴黎": 1, "沖繩": 1},
                1: {"巴黎": 1, "日內瓦": 1},
            },
        }
        default_regions_by_card = {
            "臺灣奧援": {
                3: ["臺灣"],
                2: ["東洋", "南洋"],
                1: ["東洋"],
            },
            "北國奧援": {
                3: ["北國"],
                2: ["歐洲", "東洋"],
                1: ["歐洲"],
            },
        }
        default_enemy_orgs_by_card = {
            "臺灣奧援": {
                3: {"北京": 1, "福州": 1},
                2: {"北京": 1, "福州": 1},
                1: {"北京": 1},
            },
            "北國奧援": {
                3: {"北京": 1, "伯力": 1},
                2: {"北京": 1, "福州": 1},
                1: {"慕尼黑": 1},
            },
        }
        default_enemy_base = {
            "臺灣奧援": "北京",
            "北國奧援": "北京",
        }
        default_enemy_faction = {
            "臺灣奧援": "red_army",
            "北國奧援": "red_army",
        }

        player.faction_id = payload.get(
            "faction_id", default_player_faction.get(support_name, "taiwan_green")
        )
        player.base = payload.get(
            "base", default_player_base.get(support_name, "臺北")
        )
        player.organizations = payload.get("orgs") or default_orgs_by_card.get(
            support_name, {}
        ).get(tier, {})
        player.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
        player.hand = [game._make_support_card(support_name)]
        player.deck.draw_pile = [
            Card(str(name), "command", {}) for name in (payload.get("draw_pile") or [])
        ]
        player.deck.discard_pile = []

        enemy.faction_id = payload.get(
            "enemy_faction_id", default_enemy_faction.get(support_name, "red_army")
        )
        enemy.base = payload.get(
            "enemy_base", default_enemy_base.get(support_name, "北京")
        )
        enemy.organizations = payload.get(
            "enemy_orgs"
        ) or default_enemy_orgs_by_card.get(support_name, {}).get(tier, {})
        enemy.resources = {"money": 0, "propaganda": 0}
        enemy_hand_names = payload.get("enemy_hand") or []
        enemy.hand = [Card(name, "command", {}) for name in enemy_hand_names]
        enemy.deck.draw_pile = []
        enemy.deck.discard_pile = []

        original_resolver = game._support_card_tier

        def forced_tier(target_player, card):
            card_name = getattr(card, "name", str(card))
            if (
                getattr(target_player, "id", None) == player.id
                and card_name == support_name
            ):
                matched = payload.get("matched_regions")
                if matched is None:
                    matched = default_regions_by_card.get(support_name, {}).get(
                        tier, []
                    )
                return tier, 0, list(matched)
            return original_resolver(target_player, card)

        game._support_card_tier = forced_tier

        game.current_player_index = 0
        requested_phase = str(payload.get("turn_phase", "action") or "action").lower()
        game.turn_phase = (
            TurnPhase.EVENT if requested_phase == "event" else TurnPhase.ACTION
        )
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.pending_choice = None
        game._deferred_auto_event = False
        event_name = payload.get("event_name")
        if event_name:
            selected_event = game._event_by_name(event_name)
            if selected_event is None:
                return {"error": f"Unknown event: {event_name}"}
            game.current_event = dict(selected_event)
            required = int((game.current_event.get("trigger") or {}).get("count", 1) or 1)
            game.event_progress = {
                "count": 0,
                "required": required,
                "succeeded": False,
                "settled": False,
                "status": "active",
            }
        else:
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

        auto_resolve_target_index = payload.get("auto_resolve_target_index")
        if auto_resolve_target_index is not None:
            played = game.play_card(0, mode="action")
            if played.get("pending_choice"):
                game.resolve_pending_choice(player.id, int(auto_resolve_target_index))

        return {
            "success": True,
            "game_id": game_id,
            "player_id": player.id,
            "tier": tier,
            "support_name": support_name,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
