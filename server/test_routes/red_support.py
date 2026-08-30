"""Test-only route for the red army support-card (紅軍奧援) proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class RedSupportTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-red-support-proof",
            self.test_setup_red_support_proof,
            methods=["POST"],
        )

    def test_setup_red_support_proof(self, payload: dict):
        runtime = self._runtime_provider()
        mode = payload.get("mode", "resource")
        actor_faction = payload.get("actor_faction", "liberals")
        opponent_faction = payload.get(
            "opponent_faction",
            "red_army" if actor_faction != "red_army" else "liberals",
        )

        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "target")]
        game = Game(players)

        viewer = game.players[0]
        target = game.players[1]

        viewer.faction_id = actor_faction
        viewer.base = "北京" if actor_faction == "red_army" else "德拉敦"
        viewer.organizations = {viewer.base: 1}
        viewer.resources = {"money": 0, "propaganda": 0}
        viewer.hand = [game._make_support_card("紅軍奧援")]
        viewer.deck.draw_pile = []
        viewer.deck.discard_pile = []

        target.faction_id = opponent_faction
        target.base = "北京" if opponent_faction == "red_army" else "香港城"
        target.organizations = {target.base: 1}
        target.resources = {"money": 0, "propaganda": 0}
        target.hand = []
        target.deck.draw_pile = []
        target.deck.discard_pile = []

        if mode == "action":
            viewer.deck.discard_pile = [Card("抽到展示牌", "command", {})]

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
        runtime.lobby_factions[game_id] = {
            viewer.id: viewer.faction_id,
            target.id: target.faction_id,
        }
        runtime.lobby_bases[game_id] = {viewer.id: viewer.base, target.id: target.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "mode": mode,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
