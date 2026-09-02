"""Test-only route for the remove-to-purchase proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class RemoveToPurchaseTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-remove-to-purchase",
            self.test_setup_remove_to_purchase,
            methods=["POST"],
        )

    def test_setup_remove_to_purchase(self, payload: dict):
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

        card_name = payload.get("card_name", "宣傳家")
        card_def = next(
            (c for c in game.structured_cards if c.get("name") == card_name), None
        )
        if card_def:
            viewer.hand = [
                Card(card_def["name"], card_def["type"], card_def.get("resources", {}))
            ]
        else:
            viewer.hand = [Card(card_name, "command", {})]

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        red.hand = []

        game.purchase_area = game._static_purchase_cards()[:]
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
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players}

        return {
            "game_id": game_id,
            "player_id": viewer.id,
            "card_name": card_name,
            "purchase_area": [getattr(c, "name", str(c)) for c in game.purchase_area],
            "hand": [getattr(c, "name", str(c)) for c in viewer.hand],
        }
