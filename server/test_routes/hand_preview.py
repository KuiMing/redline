"""Test-only route for constructing the hand-preview proof state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
import uuid

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


@dataclass(frozen=True)
class HandPreviewRuntime:
    manager: Any
    lobby: dict
    lobby_hosts: dict
    lobby_factions: dict
    lobby_bases: dict


class HandPreviewTestRoutes:
    def __init__(self, runtime_provider: Callable[[], HandPreviewRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-hand-preview",
            self.test_setup_hand_preview,
            methods=["POST"],
        )

    def test_setup_hand_preview(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        viewer = game.players[0]
        red = game.players[1]

        viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
        viewer.base = payload.get("base", "德拉敦")
        viewer.organizations = payload.get("orgs") or {viewer.base: 1}
        viewer.resources = payload.get("resources") or {"money": 4, "propaganda": 3}

        def preview_card(name):
            support_entry = game._support_taxonomy_entry(name)
            if support_entry:
                return game._make_support_card(name)
            card_def = next(
                (c for c in game.structured_cards if c.get("name") == name),
                None,
            )
            if card_def:
                return Card(
                    card_def["name"],
                    card_def["type"],
                    card_def.get("resources", {}),
                )
            return Card(name, "command", {})

        hand_names = payload.get("hand_names") or ["宣傳家", "印度奧援", "東洋奧援"]
        viewer.hand = [preview_card(name) for name in hand_names]
        viewer.deck.discard_pile = [
            preview_card(name) for name in payload.get("viewer_discard_names", [])
        ]

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        red.deck.discard_pile = [
            preview_card(name) for name in payload.get("red_discard_names", [])
        ]

        if "action_log" in payload:
            game.action_log = [str(entry) for entry in payload.get("action_log", [])]
            game._action_log_visibility = [None for _ in game.action_log]

        while len(game.purchase_area) < 11:
            drawn = game._draw_purchase_cards(1)
            if not drawn:
                break
            game.purchase_area.extend(drawn)

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
            "hand_names": hand_names,
            "turn_phase": game.turn_phase,
            "game_phase": game.game_phase,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id}
                for p in game.players
            ],
            "state": game.state(),
        }
