"""Test-only route for the Hong Kong era activation red-army discard proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class HongKongEraRedDiscardTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-hong-kong-era-red-discard-proof",
            self.test_setup_hong_kong_era_red_discard_proof,
            methods=["POST"],
        )

    def test_setup_hong_kong_era_red_discard_proof(self, payload: dict):
        runtime = self._runtime_provider()
        players = [(str(uuid.uuid4()), "香港"), (str(uuid.uuid4()), "紅軍")]
        game = Game(players, market_mode="all_cards")
        actor = game.players[0]
        red = game.players[1]
        actor.faction_id = "hong_kong"
        red.faction_id = "red_army"
        actor.base = "香港城"
        red.base = "北京"
        actor.organizations = {"天津": 1}
        red.organizations = {"北京": 1}
        actor.hand = [
            Card("香港目標手牌", "money", {"money": 1}),
            Card("香港保留手牌", "propaganda", {"propaganda": 1}),
        ]
        actor.deck.discard_pile = []
        red.hand = [Card("內應間諜", "spy", {"propaganda": 2})]
        red.deck.discard_pile = []
        actor.resources = {"money": 0, "propaganda": 0}
        red.resources = {"money": 0, "propaganda": 0}
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 1
        game.turn_phase = TurnPhase.ACTION
        game.era_engine.activate_era("hong_kong")
        era = game.era_engine.get_definition("hong_kong")
        game.era_notification = (
            game._era_notification_payload(era)
            if era
            else {"id": "hong_kong", "name": "[香港]香港人被自殺"}
        )
        game.era_notification["runtime_effects"] = {
            "red_suppression": (era.get("effects") or {}).get("red_suppression")
            if era
            else None,
            "revolution_counterattack": (era.get("effects") or {}).get(
                "revolution_counterattack"
            )
            if era
            else None,
        }

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
            "red_player_id": red.id,
            "hong_kong_player_id": actor.id,
            "target_town": "天津",
            "red_url": f"/?game_id={game_id}&player_id={red.id}",
            "hong_kong_url": f"/?game_id={game_id}&player_id={actor.id}",
            "url": f"/?game_id={game_id}&player_id={red.id}",
            "state": game.state(),
        }
