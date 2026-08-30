"""Test-only route for the shared-organization dissolve proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class SharedDissolveTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-shared-dissolve",
            self.test_setup_shared_dissolve,
            methods=["POST"],
        )

    def test_setup_shared_dissolve(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [
            (str(uuid.uuid4()), "atk"),
            (str(uuid.uuid4()), "hu"),
            (str(uuid.uuid4()), "taiwan"),
        ]
        game = Game(players)

        attacker = game.players[0]
        hu = game.players[1]
        tw = game.players[2]

        attacker.faction_id = payload.get("attacker_faction", "red_army")
        attacker.base = payload.get("attacker_base", "南京")
        attacker.organizations = {attacker.base: 1}
        attacker.hand = (
            []
            if payload.get("attacker_no_hand")
            else [Card("測試手牌", "money", {"money": 1})]
        )

        hu.faction_id = "hu"
        hu.base = payload.get("hu_base", "紐約")
        hu.organizations = {hu.base: 1}
        hu.hand = []

        tw.faction_id = payload.get("tw_faction", "taiwan_green")
        tw.base = payload.get("tw_base", "臺北")
        tw.organizations = {
            payload.get("shared_town", "上海"): 1,
            tw.base: 1,
        }
        tw.hand = []
        tw.deck.draw_pile = [Card("補牌A", "money", {"money": 1})]

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
        runtime.lobby_hosts[game_id] = attacker.id
        runtime.lobby_factions[game_id] = {
            attacker.id: attacker.faction_id,
            hu.id: "hu",
            tw.id: tw.faction_id,
        }
        runtime.lobby_bases[game_id] = {
            attacker.id: attacker.base,
            hu.id: hu.base,
            tw.id: tw.base,
        }

        return {
            "success": True,
            "game_id": game_id,
            "player_id": attacker.id,
            "shared_town": payload.get("shared_town", "上海"),
            "turn_phase": game.turn_phase,
            "game_phase": game.game_phase,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players
            ],
            "state": game.state(),
        }
