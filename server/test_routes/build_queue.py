"""Test-only route for constructing the build-queue proof state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
import uuid

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


@dataclass(frozen=True)
class BuildQueueRuntime:
    manager: Any
    lobby: dict
    lobby_hosts: dict
    lobby_factions: dict
    lobby_bases: dict


class BuildQueueTestRoutes:
    def __init__(self, runtime_provider: Callable[[], BuildQueueRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-build-queue-proof",
            self.test_setup_build_queue_proof,
            methods=["POST"],
        )

    def test_setup_build_queue_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)
        viewer, red = game.players

        viewer.faction_id = payload.get("faction_id", "liberals")
        viewer.base = payload.get("base", "香港城")
        viewer.organizations = dict(payload.get("organizations") or {viewer.base: 1})
        red.faction_id = "red_army"
        red.base = payload.get("enemy_base", "北京")
        red.organizations = dict(
            payload.get("enemy_organizations") or {red.base: 1}
        )

        card_names = list(payload.get("cards") or ["組織經驗丙", "組織經驗乙"])
        support_names = {entry.get("name") for entry in game.support_taxonomy}
        viewer.hand = []
        for name in card_names:
            if name in support_names:
                viewer.hand.append(game._make_support_card(name))
                continue
            card_def = next(
                (card for card in game.structured_cards if card.get("name") == name),
                None,
            )
            if card_def is None:
                return {"error": f"Unknown action card: {name}"}
            viewer.hand.append(
                Card(
                    card_def["name"],
                    card_def.get("type", "test"),
                    card_def.get("resources", {}),
                )
            )
        forced_support_tiers = {
            str(name): int(tier)
            for name, tier in dict(payload.get("support_tiers") or {}).items()
        }
        if forced_support_tiers:
            original_support_card_tier = game._support_card_tier

            def proof_support_card_tier(player, card):
                card_name = getattr(card, "name", str(card))
                if card_name in forced_support_tiers:
                    return (
                        forced_support_tiers[card_name],
                        int(getattr(card, "variant_index", 0) or 0),
                        [],
                    )
                return original_support_card_tier(player, card)

            setattr(game, "_support_card_tier", proof_support_card_tier)
        viewer.deck.discard_pile = []

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

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(
            game_id, {}
        )
        runtime.lobby[game_id] = [
            (player.id, player.name) for player in game.players
        ]
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
            "state": game.state(viewer.id),
        }
