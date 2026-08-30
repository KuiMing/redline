"""Test-only route for the trash-from-hand-or-discard choice UI proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class TrashChoiceUiTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-trash-choice-ui",
            self.test_setup_trash_choice_ui,
            methods=["POST"],
        )

    def test_setup_trash_choice_ui(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players)

        viewer = game.players[0]
        red = game.players[1]

        viewer.faction_id = payload.get("faction_id", "red_army")
        viewer.base = payload.get("base", "北京")
        viewer.organizations = payload.get("orgs") or {viewer.base: 1}
        viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
        viewer.hand = [
            Card("思想家", "command", {"propaganda": 2}),
            Card("宣傳家", "propaganda", {"propaganda": 1}),
        ]
        viewer.deck.discard_pile = [
            Card("資本家", "money", {"money": 3}),
            Card("樂捐者", "money", {"money": 1}),
        ]

        red.faction_id = "hong_kong"
        red.base = "香港城"
        red.organizations = {"香港城": 1}
        red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        red.deck.discard_pile = []

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
        source_name = payload.get("source_name", "批判")
        count = int(payload.get("count", 1) or 1)
        cards = [
            {"card": viewer.hand[0], "zone": "hand", "zone_label": "手牌"},
            {"card": viewer.hand[1], "zone": "hand", "zone_label": "手牌"},
            {"card": viewer.deck.discard_pile[0], "zone": "discard", "zone_label": "棄牌堆"},
            {"card": viewer.deck.discard_pile[1], "zone": "discard", "zone_label": "棄牌堆"},
        ]
        prompt = f"{source_name}：請從己方手牌或棄牌堆中移除 {count} 張牌。"
        if count <= 1:
            game._set_pending_card_choice(
                viewer,
                "trash_from_hand_or_discard",
                cards,
                prompt,
                source_name=source_name,
                count=1,
            )
        else:
            game._set_pending_multi_card_choice(
                viewer,
                "trash_from_hand_or_discard",
                cards,
                prompt,
                count=count,
                source_name=source_name,
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
            "state": game.state(),
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
        }
