"""Test-only route for the press-advantage proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class PressAdvantageTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-press-advantage-proof",
            self.test_setup_press_advantage_proof,
            methods=["POST"],
        )

    def test_setup_press_advantage_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [
            (str(uuid.uuid4()), "viewer"),
            (str(uuid.uuid4()), "enemy"),
        ]
        game = Game(players)
        viewer, enemy = game.players

        def proof_card(name):
            card_def = next(
                (c for c in game.structured_cards if c.get("name") == name),
                None,
            )
            if card_def:
                return Card(
                    card_def["name"],
                    card_def.get("type", "command"),
                    dict(card_def.get("resources", {}) or {}),
                )
            return Card(name, "command", {})

        viewer.faction_id = payload.get("viewer_faction", "red_army")
        viewer.base = payload.get("viewer_base", "北京")
        viewer.organizations = {viewer.base: 1}
        viewer.hand = [proof_card("乘勝追擊")]
        viewer.deck.draw_pile = [
            proof_card(name)
            for name in payload.get("draw_pile", ["抽牌A", "抽牌B"])
        ]
        discard_names = payload.get("discard_pile") or [
            "宣傳家",
            "合作談判",
            "走漏風聲",
        ]
        viewer.deck.discard_pile = [proof_card(name) for name in discard_names]
        viewer.resources = {"money": 0, "propaganda": 0}

        enemy.faction_id = payload.get("enemy_faction", "hong_kong")
        enemy.base = payload.get("enemy_base", "香港城")
        enemy.organizations = {enemy.base: 1}
        enemy.hand = [proof_card("對手手牌A")]
        enemy.deck.draw_pile = [proof_card("對手抽牌A")]
        enemy.deck.discard_pile = []
        enemy.resources = {"money": 0, "propaganda": 0}

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.id = game_id
        game.log(
            "UI proof setup: viewer has 乘勝追擊; discard pile contains 宣傳家 / 合作談判 / 走漏風聲."
        )

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(
            game_id, {}
        )
        runtime.lobby[game_id] = list(
            zip(
                [player.id for player in game.players],
                [player.name for player in game.players],
            )
        )
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id for player in game.players
        }
        runtime.lobby_bases[game_id] = {
            player.id: player.base for player in game.players
        }

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "faction": player.faction_id,
                    "base": player.base,
                }
                for player in game.players
            ],
            "state": game.state(),
        }
