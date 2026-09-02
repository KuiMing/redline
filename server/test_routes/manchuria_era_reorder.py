"""Test-only route for the Manchuria era activation/reorder proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class ManchuriaEraReorderTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-manchuria-era-reorder-proof",
            self.test_setup_manchuria_era_reorder_proof,
            methods=["POST"],
        )

    def test_setup_manchuria_era_reorder_proof(self, payload: dict):
        runtime = self._runtime_provider()
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players, market_mode="all_cards")
        viewer = game.players[0]
        red = game.players[1]
        viewer.faction_id = "manchuria"
        red.faction_id = "red_army"
        viewer.base = "瀋陽"
        red.base = "北京"
        viewer.organizations = {"瀋陽": 1}
        red.organizations = {"北京": 1}
        viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        viewer.deck.draw_pile = [Card(f"底牌{i}", "command", {}) for i in range(3)] + [
            Card("第七張", "command", {}),
            Card("第六張", "command", {}),
            Card("第五張", "command", {}),
            Card("第四張", "command", {}),
            Card("第三張", "command", {}),
            Card("第二張", "command", {}),
            Card("第一張", "command", {}),
        ]
        viewer.deck.discard_pile = []
        red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.era_engine.activate_era("manchuria")
        era = game.era_engine.get_definition("manchuria")
        runtime_effects = game._apply_era_activation_effects(era)
        game.era_notification = {
            "id": era.get("id") if era else "manchuria",
            "name": era.get("name") if era else "[滿洲]滿洲地方派系凝聚",
            "runtime_effects": runtime_effects,
        }

        game_id = str(uuid.uuid4())
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "red_player_id": red.id,
            "era_name": era.get("name") if era else None,
            "runtime_effects": runtime_effects,
            "url": f"/?game_id={game_id}&player_id={viewer.id}",
            "state": game.state(),
        }
