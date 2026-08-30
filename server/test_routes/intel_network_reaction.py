"""Test-only routes for the information-network cancel-reaction proof."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class IntelNetworkReactionTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-intel-network-cancel-reaction-proof",
            self.test_setup_intel_network_cancel_reaction_proof,
            methods=["POST"],
        )
        self.router.add_api_route(
            "/test/resolve-intel-network-cancel-reaction-proof",
            self.test_resolve_intel_network_cancel_reaction_proof,
            methods=["POST"],
        )

    def test_setup_intel_network_cancel_reaction_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [
            (str(uuid.uuid4()), "actor"),
            (str(uuid.uuid4()), "reactor"),
        ]
        game = Game(players)
        actor, reactor = game.players

        def proof_card(name):
            card_def = next(
                (c for c in game.structured_cards if c.get("name") == name), None
            )
            if card_def:
                return Card(
                    card_def["name"],
                    card_def.get("type", "command"),
                    dict(card_def.get("resources", {}) or {}),
                )
            return Card(name, "command", {})

        actor_card = payload.get("actor_card", "領導")
        reaction_card = payload.get("reaction_card", "情報網")

        actor.faction_id = payload.get("actor_faction", "hong_kong")
        actor.base = payload.get("actor_base", "香港城")
        actor.organizations = {actor.base: 1}
        actor.hand = [proof_card(actor_card)]
        actor.deck.draw_pile = [
            proof_card(payload.get("actor_draw_top", "ShouldNotDraw"))
        ]
        actor.deck.discard_pile = []
        actor.resources = {"money": 0, "propaganda": 0}

        reactor.faction_id = payload.get("reactor_faction", "red_army")
        reactor.base = payload.get("reactor_base", "北京")
        reactor.organizations = {reactor.base: 1}
        reactor.hand = [proof_card(reaction_card)]
        reactor.deck.draw_pile = [
            proof_card(
                payload.get("reactor_draw_top", "IntelShouldNotDrawBonus")
            )
        ]
        reactor.deck.discard_pile = []
        reactor.resources = {"money": 0, "propaganda": 0}

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.id = game_id
        game.log(
            f"{reaction_card}取消反應測試：actor 準備打出 {actor_card}；reactor 手牌有 {reaction_card} 可取消。"
        )

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(
            game_id, {}
        )
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {
            p.id: p.faction_id for p in game.players
        }
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players}

        return {
            "success": True,
            "game_id": game_id,
            "actor_id": actor.id,
            "reactor_id": reactor.id,
            "players": [
                {"id": p.id, "name": p.name, "faction": p.faction_id}
                for p in game.players
            ],
            "state": game.state(),
        }

    def test_resolve_intel_network_cancel_reaction_proof(self, payload: dict):
        runtime = self._runtime_provider()
        game_id = payload.get("game_id")
        game = runtime.manager.get_game(game_id)
        if not game:
            return {"error": "Game not found"}
        actor = next(
            (
                p
                for p in game.players
                if p.name == payload.get("actor_name", "actor")
            ),
            game.current_player(),
        )
        reactor = next(
            (
                p
                for p in game.players
                if p.name == payload.get("reactor_name", "reactor")
            ),
            None,
        )
        if not actor or not reactor:
            return {"error": "Proof players not found"}
        for idx, candidate in enumerate(game.players):
            if candidate.id == actor.id:
                game.current_player_index = idx
                break
        result = game.play_card(
            0,
            mode="action",
            reaction={"player_id": reactor.id, "card_index": 0},
        )
        state = game.state()
        state["last_action_result"] = result
        return {
            "success": not bool(result.get("error"))
            if isinstance(result, dict)
            else True,
            "result": result,
            "state": state,
        }
