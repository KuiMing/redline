"""Test-only route for the Tibet era activation red-army discard/build proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class TibetEraRedBuildTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-tibet-era-red-build-proof",
            self.test_setup_tibet_era_red_build_proof,
            methods=["POST"],
        )

    def test_setup_tibet_era_red_build_proof(self, payload: dict):
        runtime = self._runtime_provider()
        players = [(str(uuid.uuid4()), "藏國"), (str(uuid.uuid4()), "紅軍")]
        game = Game(players, market_mode="all_cards")
        actor = game.players[0]
        red = game.players[1]
        actor.faction_id = "tibet"
        red.faction_id = "red_army"
        actor.base = "拉薩"
        red.base = "北京"
        actor.resources = {"money": 0, "propaganda": 0}
        red.resources = {"money": 0, "propaganda": 0}
        tibet_town = "列城"
        actor.organizations = {tibet_town: 1}
        red.organizations = {"北京": 1}
        red.hand = [
            Card("紅軍棄牌 UI proof 一", "money", {"money": 1}),
            Card("紅軍棄牌 UI proof 二", "propaganda", {"propaganda": 1}),
            Card("紅軍保留 UI proof", "money", {"money": 1}),
        ]
        red.deck.discard_pile = []
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 1
        game.turn_phase = TurnPhase.ACTION
        game.era_engine.activate_era("tibet")
        era = game.era_engine.get_definition("tibet")
        runtime_effects = game._apply_era_activation_effects(era)
        discard_result = None
        if payload.get("resolve_discard", True):
            discard_indices = payload.get("discard_indices")
            if discard_indices is None:
                discard_indices = [0, 1]
            discard_result = game.resolve_pending_choice(red.id, discard_indices)

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
            "tibet_town": tibet_town,
            "runtime_effects": runtime_effects,
            "discard_result": discard_result,
            "pending_choice": game.pending_choice,
            "url": f"/?game_id={game_id}&player_id={red.id}",
            "state": game.state(),
        }
