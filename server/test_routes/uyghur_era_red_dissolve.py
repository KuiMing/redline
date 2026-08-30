"""Test-only route for the Uyghur era activation red-army dissolve/discard proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class UyghurEraRedDissolveTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-uyghur-era-red-dissolve-proof",
            self.test_setup_uyghur_era_red_dissolve_proof,
            methods=["POST"],
        )

    def test_setup_uyghur_era_red_dissolve_proof(self, payload: dict):
        runtime = self._runtime_provider()
        players = [(str(uuid.uuid4()), "維吾爾"), (str(uuid.uuid4()), "紅軍")]
        game = Game(players, market_mode="all_cards")
        actor = game.players[0]
        red = game.players[1]
        actor.faction_id = "uyghur_istanbul"
        red.faction_id = "red_army"
        actor.base = "烏魯木齊"
        red.base = "北京"
        actor.organizations = {"天津": 1}
        red.organizations = {"北京": 1}
        actor.hand = [Card("維吾爾棄牌 UI proof", "money", {"money": 1})]
        actor.deck.discard_pile = []
        red.hand = [Card("武裝者", "armed", {"propaganda": 1})]
        red.deck.discard_pile = []
        actor.resources = {"money": 0, "propaganda": 0}
        red.resources = {"money": 0, "propaganda": 0}
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 1
        game.turn_phase = TurnPhase.ACTION
        game.era_engine.activate_era("uyghur")
        play_result = game.play_card(0, mode="action", target_player_id=actor.id)
        discard_choice = dict(game.pending_choice or {})
        discard_result = game.resolve_pending_choice(actor.id, 0)

        game_id = str(uuid.uuid4())
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": red.id,
            "actor_player_id": actor.id,
            "play_result": play_result,
            "discard_choice": discard_choice,
            "discard_result": discard_result,
            "pending_choice": game.pending_choice,
            "url": f"/?game_id={game_id}&player_id={red.id}",
            "state": game.state(),
        }
