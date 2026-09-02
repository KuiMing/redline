"""Test-only route for the end-turn topdeck proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class EndTurnTopdeckTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-end-turn-topdeck-proof",
            self.test_setup_end_turn_topdeck_proof,
            methods=["POST"],
        )

    def test_setup_end_turn_topdeck_proof(self, payload: dict):
        """Proof setup for the 行動預告/行動募資 topdeck-right flow (2026-08-07 改版):
        the viewer already played the card (right banked, resource already granted) and has a
        purchased card sitting in discard — either to drive the manual "頂牌" button (default
        ACTION phase) or the auto-drain-on-end-turn path (phase="end")."""
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        viewer = game.players[0]
        red = game.players[1]

        card_name = payload.get("card_name", "行動預告")
        bought_card_names = payload.get("bought_cards") or [
            payload.get("bought_card", "本回合購得牌")
        ]
        extra_hand = payload.get("extra_hand") or ["Filler"]
        pending_topdeck_uses = payload.get("pending_topdeck_uses", 1)
        phase = payload.get("phase", "action")

        def proof_card(name):
            card_def = next(
                (c for c in game.structured_cards if c.get("name") == name), None
            )
            if card_def:
                return Card(
                    card_def["name"],
                    card_def.get("type", "command"),
                    dict(card_def.get("resources", {}) or {}),
                )
            return Card(name, "command", {})

        bought_cards = [proof_card(name) for name in bought_card_names]
        resource_key = "propaganda" if card_name == "行動預告" else "money"
        default_resources = {"money": 0, "propaganda": 0}
        default_resources[resource_key] = pending_topdeck_uses

        viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
        viewer.base = payload.get("base", "德拉敦")
        viewer.organizations = {viewer.base: 1}
        viewer.resources = payload.get("resources") or default_resources
        viewer.hand = [proof_card(name) for name in extra_hand]
        viewer.deck.draw_pile = [
            proof_card(name)
            for name in (payload.get("draw_pile") or ["補牌1", "補牌2", "補牌3", "補牌4", "補牌5"])
        ]
        viewer.deck.discard_pile = list(bought_cards)

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        red.hand = []

        game.current_player_index = 0
        game.turn_phase = TurnPhase.END if phase == "end" else TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.turn_log["purchased_cards_this_turn"] = list(bought_cards)
        game.turn_log["pending_topdeck_uses"] = pending_topdeck_uses
        game.id = game_id
        game.log(
            f"UI proof setup: viewer already played {card_name} "
            f"({pending_topdeck_uses} banked right); bought cards {bought_card_names} "
            "are in discard."
        )

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
            "card_name": card_name,
            "bought_cards": bought_card_names,
            "state": game.state(),
        }
