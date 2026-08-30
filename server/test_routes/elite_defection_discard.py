"""Test-only route for the elite defection (紅軍權貴出逃) discard proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class EliteDefectionDiscardTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-elite-defection-discard-proof",
            self.test_setup_elite_defection_discard_proof,
            methods=["POST"],
        )

    def test_setup_elite_defection_discard_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        game = Game([(str(uuid.uuid4()), "host"), (str(uuid.uuid4()), "hostda")])
        host, red = game.players
        host.faction_id = "taiwan_green"
        host.base = "臺北"
        host.organizations = {"臺北": 2}
        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}

        selected_donor = Card("樂捐者", "resource", {"money": 1})
        played_donor = Card("樂捐者", "resource", {"money": 1})
        host.hand = []
        host.deck.draw_pile = [
            Card("牌庫甲", "command", {}),
            Card("牌庫乙", "command", {}),
            selected_donor,
        ]
        host.deck.discard_pile = [played_donor] + [
            Card(f"既有棄牌{i}", "command", {}) for i in range(9)
        ]
        red.hand = [game._make_support_card("天方奧援")] + [
            Card(f"紅軍手牌{i}", "command", {}) for i in range(4)
        ]

        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.END
        game.current_player_index = 0
        game.round_start_player_index = 0
        game.pending_base_choices = {}
        game.pending_choice = None
        game.current_event = game._event_by_name("紅軍權貴出逃")
        game.event_progress = {
            "count": 0,
            "required": 3,
            "succeeded": False,
            "settled": False,
            "status": "active",
            "last_actor_id": host.id,
        }
        game.event_deck.draw_pile = [game._event_by_name("上海合作組織")]
        game.event_deck.discard_pile = []
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = {}
        runtime.lobby[game_id] = [(host.id, host.name), (red.id, red.name)]
        runtime.lobby_hosts[game_id] = host.id
        runtime.lobby_factions[game_id] = {
            host.id: host.faction_id,
            red.id: red.faction_id,
        }
        runtime.lobby_bases[game_id] = {host.id: host.base, red.id: red.base}
        runtime.lobby_ready[game_id] = {host.id: True, red.id: True}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": host.id,
            "red_player_id": red.id,
            "state": game.state(host.id),
        }
