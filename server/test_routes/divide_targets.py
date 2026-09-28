"""Test-only route for the 離間 multi-target proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class DivideTargetsTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-divide-targets-proof",
            self.test_setup_divide_targets_proof,
            methods=["POST"],
        )

    def test_setup_divide_targets_proof(self, payload: dict):
        runtime = self._runtime_provider()
        players = [
            (str(uuid.uuid4()), "Ben"),
            (str(uuid.uuid4()), "香港玩家"),
            (str(uuid.uuid4()), "自由派玩家"),
            (str(uuid.uuid4()), "紅軍玩家"),
        ]
        game = Game(players, market_mode="all_cards")
        actor, hong_kong, liberals, red = game.players
        faction_ids = ["taiwan_green", "hong_kong", "liberals", "red_army"]
        bases = ["臺北", "香港城", "上海", "北京"]
        for player, faction_id, base in zip(game.players, faction_ids, bases):
            player.faction_id = faction_id
            player.base = base
            player.organizations = {base: 1}
            player.hand = []
            player.deck.draw_pile = []
            player.deck.discard_pile = []
        via_business_network = bool(payload.get("via_business_network"))
        actor.hand = [
            game._starter_card("企業人脈" if via_business_network else "離間")
        ]
        if via_business_network:
            game.purchase_area = [game._starter_card("離間")]
        game.pending_base_choices = {}
        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.ACTION
        game.current_player_index = 0
        game.current_event = None
        game.event_progress = {}

        game_id = str(uuid.uuid4())
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(player.id, player.name) for player in game.players]
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {player.id: player.faction_id for player in game.players}
        runtime.lobby_bases[game_id] = {player.id: player.base for player in game.players}
        runtime.lobby_ready[game_id] = {player.id: True for player in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "target_player_ids": [hong_kong.id, liberals.id, red.id],
            "via_business_network": via_business_network,
            "url": f"/?game_id={game_id}&player_id={actor.id}",
        }
