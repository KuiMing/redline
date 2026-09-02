"""Test-only route for the end-of-turn discard reshuffle proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class DiscardReshuffleTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-discard-reshuffle-proof",
            self.test_setup_discard_reshuffle_proof,
            methods=["POST"],
        )

    def test_setup_discard_reshuffle_proof(self, payload: dict):
        runtime = self._runtime_provider()
        scenario = str(payload.get("scenario") or "sufficient")
        if scenario not in {"sufficient", "exhausted"}:
            return {"error": "scenario must be sufficient or exhausted"}

        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "紅軍"), (str(uuid.uuid4()), "對手")]
        game = Game(players)
        red, opponent = game.players
        red.faction_id = "red_army"
        red.base = "北京"
        red.organizations = {"北京": 1}
        opponent.faction_id = "taiwan_green"
        opponent.base = "臺北"
        opponent.organizations = {"臺北": 1}

        red.hand = [Card(f"保留手牌{i}", "command", {}) for i in range(1, 5)]
        red.deck.draw_pile = (
            [] if scenario == "exhausted" else [Card("牌庫保留牌", "command", {})]
        )
        red.deck.discard_pile = [Card("棄牌唯一一張", "command", {})]
        red.resources = {"money": 0, "propaganda": 0}
        red.moves_left = 0

        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.END
        game.current_player_index = 0
        game.pending_base_choices = {}
        game.pending_choice = None
        game._deferred_auto_event = False
        noop_event = game._event_by_name("歲月靜好")
        game.current_event = dict(noop_event or {})
        game.event_progress = {
            "count": 0,
            "required": 0,
            "succeeded": True,
            "settled": True,
            "status": "idle",
        }
        game.event_modifiers = []
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = {}
        runtime.lobby[game_id] = [(red.id, red.name), (opponent.id, opponent.name)]
        runtime.lobby_hosts[game_id] = red.id
        runtime.lobby_factions[game_id] = {
            red.id: red.faction_id,
            opponent.id: opponent.faction_id,
        }
        runtime.lobby_bases[game_id] = {red.id: red.base, opponent.id: opponent.base}
        runtime.lobby_ready[game_id] = {red.id: True, opponent.id: True}

        return {
            "success": True,
            "scenario": scenario,
            "game_id": game_id,
            "player_id": red.id,
            "opponent_id": opponent.id,
            "state": game.state(red.id),
        }
