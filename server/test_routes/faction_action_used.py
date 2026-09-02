"""Test-only route for the already-used faction action modal proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class FactionActionUsedTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-faction-action-used-proof",
            self.test_setup_faction_action_used_proof,
            methods=["POST"],
        )

    def test_setup_faction_action_used_proof(self, payload: dict):
        """Proof setup for the 2026-08-09 playtest bug: a faction with a one-per-turn activated
        ability (澳門/賭徒耳語 by default) that has ALREADY used it this turn should not have the
        centred faction-action modal keep force-reopening every time an unrelated action (e.g.
        playing a hand card as a resource) triggers a re-render."""
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "opponent")]
        game = Game(players)

        viewer = game.players[0]
        opponent = game.players[1]

        faction_id = payload.get("faction_id", "aomen")
        resource_card_name = payload.get("resource_card_name", "領導")
        faction_action_used = payload.get("faction_action_used", True)

        def proof_card(name):
            entry = next(
                (c for c in game.structured_cards if c.get("name") == name), None
            )
            if entry:
                return Card(
                    entry["name"], entry.get("type", "command"), dict(entry.get("resources", {}) or {})
                )
            return Card(name, "command", {})

        viewer.faction_id = faction_id
        viewer.base = payload.get("base", "澳門城")
        viewer.organizations = {viewer.base: 1}
        viewer.resources = {"money": 0, "propaganda": 0}
        viewer.hand = [proof_card(resource_card_name)]
        viewer.deck.draw_pile = [
            proof_card(name) for name in (payload.get("draw_pile") or ["補牌1", "補牌2"])
        ]
        viewer.deck.discard_pile = []

        opponent.faction_id = "red_army"
        opponent.base = "北京"
        opponent.organizations = {"北京": 1}
        opponent.hand = []

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
        game.pending_choice = None
        # 固定換成無效果的歲月靜好，避免隨機抽到互動型事件在 setup 當下就掛一個 pending_choice，
        # 讓這支 proof 端點的行為與初始 Game() 建構時抽到什麼事件脫鉤、可穩定重跑。
        noop_event = game._event_by_name("歲月靜好")
        game.current_event = dict(noop_event or {})
        game.event_progress = {
            "count": 0,
            "required": 0,
            "succeeded": True,
            "settled": True,
            "status": "idle",
        }
        game.event_modifiers = []
        game.turn_log["faction_action_used"] = bool(faction_action_used)
        game.id = game_id
        game.log(
            f"UI proof setup: viewer already used this turn's faction action ({faction_id})."
        )

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {
            viewer.id: viewer.faction_id,
            opponent.id: opponent.faction_id,
        }
        runtime.lobby_bases[game_id] = {viewer.id: viewer.base, opponent.id: opponent.base}

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "resource_card_name": resource_card_name,
            "state": game.state(),
        }
