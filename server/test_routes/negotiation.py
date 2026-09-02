"""Test-only route for the cooperation-negotiation proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class NegotiationTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-negotiation-proof",
            self.test_setup_negotiation_proof,
            methods=["POST"],
        )

    def test_setup_negotiation_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [
            (str(uuid.uuid4()), "Actor"),
            (str(uuid.uuid4()), "Ally"),
            (str(uuid.uuid4()), "Enemy"),
            (str(uuid.uuid4()), "Observer"),
        ]
        game = Game(players)
        actor, ally, enemy, observer = game.players
        actor.faction_id = "liberals"
        ally.faction_id = "hong_kong"
        enemy.faction_id = "red_army"
        observer.faction_id = "taiwan_green"

        card_def = next(
            card for card in game.structured_cards if card.get("name") == "合作談判"
        )
        actor.hand = [
            Card(
                card_def["name"],
                card_def.get("type", "command"),
                card_def.get("resources", {}),
            )
        ]
        actor.deck.draw_pile = [Card("ActorDraw", "command", {})]
        ally.deck.draw_pile = [Card("AllyDraw", "command", {})]
        enemy.deck.draw_pile = [Card("EnemyDraw", "command", {})]
        observer.deck.draw_pile = [Card("ObserverDraw", "command", {})]
        for player in game.players:
            if player is not actor:
                player.hand = []
            player.deck.discard_pile = []
            player.resources = {"money": 0, "propaganda": 0}

        game.current_player_index = 0
        game.game_phase = GamePhase.MAIN
        game.turn_phase = TurnPhase.ACTION
        game.pending_base_choices = {}
        game.pending_choice = None
        noop_event = game._event_by_name("歲月靜好")
        game.current_event = dict(noop_event or {})
        game.event_progress = {
            "count": 0,
            "required": 0,
            "succeeded": True,
            "settled": True,
            "status": "idle",
        }
        game.event_notification = game._event_display_payload()
        game.event_modifiers = []
        game.id = game_id

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(
            game_id, {}
        )
        runtime.lobby[game_id] = [
            (player.id, player.name) for player in game.players
        ]
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {
            player.id: player.faction_id for player in game.players
        }
        runtime.lobby_bases[game_id] = {}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": actor.id,
            "enemy_player_id": enemy.id,
            "state": game.state(actor.id),
        }
