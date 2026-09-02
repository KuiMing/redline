"""Test-only route for the underground party proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class UndergroundPartyTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-underground-party",
            self.test_setup_underground_party,
            methods=["POST"],
        )

    def test_setup_underground_party(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        viewer = game.players[0]
        red = game.players[1]

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

        viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
        viewer.base = payload.get("base", "德拉敦")
        viewer.organizations = payload.get("orgs") or {viewer.base: 1}
        viewer.resources = payload.get("resources") or {"money": 4, "propaganda": 4}
        viewer.hand = [proof_card("地下黨")]
        viewer.deck.draw_pile = [proof_card("抽牌A"), proof_card("抽牌B")]
        viewer.deck.discard_pile = []

        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        red.hand = []

        # Deck.draw() pops from the end; arrange the three proof candidates so
        # the UI reveals them in this order.
        candidate_names = payload.get("candidate_names") or ["宣傳家", "合作談判", "走漏風聲"]
        game.purchase_deck.draw_pile = [
            proof_card(name) for name in reversed(candidate_names)
        ]
        game.purchase_deck.discard_pile = []
        game.purchase_area = game._static_purchase_cards()[:]
        random_market_names = payload.get("purchase_area_random") or [
            "批鬥",
            "組織經驗甲",
            "組織經驗丙",
            "北國奧援",
            "模仿戰術",
        ]
        game.purchase_area.extend(proof_card(name) for name in random_market_names)

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.id = game_id
        game.log(
            "UI proof setup: viewer has 地下黨; purchase deck top reveals "
            "宣傳家 / 合作談判 / 走漏風聲."
        )

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "purchase_draw_pile": [
                getattr(c, "name", str(c)) for c in game.purchase_deck.draw_pile
            ],
            "expected_reveal_order": list(candidate_names),
            "hand": [getattr(c, "name", str(c)) for c in viewer.hand],
            "state": game.state(),
        }
