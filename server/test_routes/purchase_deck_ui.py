"""Test-only route for the purchase deck UI proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class PurchaseDeckUiTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-purchase-deck-ui",
            self.test_setup_purchase_deck_ui,
            methods=["POST"],
        )

    def test_setup_purchase_deck_ui(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        viewer = game.players[0]
        red = game.players[1]

        viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
        viewer.base = payload.get("base", "德拉敦")
        viewer.organizations = payload.get("orgs") or {viewer.base: 1}
        viewer.resources = payload.get("resources") or {"money": 5, "propaganda": 5}
        viewer.hand = []

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}

        # full purchase UI path: static 6 + 5 random. Tests may pin the
        # random slots to verify a specific market-card purchase/refill flow.
        pinned_random = payload.get("purchase_area_random") or []
        if pinned_random:
            game.purchase_area = game._static_purchase_cards()[:]
            for name in pinned_random[:5]:
                support = game._support_taxonomy_entry(name)
                if support:
                    game.purchase_area.append(game._make_support_card(name))
                    continue
                card_def = next(
                    (c for c in game.structured_cards if c.get("name") == name), None
                )
                if card_def:
                    game.purchase_area.append(
                        Card(
                            card_def["name"],
                            card_def.get("type", "command"),
                            card_def.get("resources", {}),
                        )
                    )
                else:
                    game.purchase_area.append(Card(name, "command", {}))
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
