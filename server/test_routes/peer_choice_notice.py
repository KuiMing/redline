"""Test-only route for the peer-action-notice-vs-pending-choice proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class PeerChoiceNoticeTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-peer-choice-notice-proof",
            self.test_setup_peer_choice_notice_proof,
            methods=["POST"],
        )

    def test_setup_peer_choice_notice_proof(self, payload: dict):
        """Proof setup for the 2026-08-09 playtest request: when a card (e.g. 武裝小隊) forces the
        OTHER player into a pending choice they must resolve (e.g. choosing which card to discard),
        that player's screen should go straight to the choice UI — not force them to first minimize
        the big "peer action notice" broadcast overlay about the card that was just played."""
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "actor"), (str(uuid.uuid4()), "viewer")]
        game = Game(players)

        actor = game.players[0]
        viewer = game.players[1]

        source_name = payload.get("source_name", "武裝小隊")
        hand_names = payload.get("viewer_hand", ["情報網", "領導", "謀劃"])

        def proof_card(name):
            entry = next(
                (c for c in game.structured_cards if c.get("name") == name), None
            )
            if entry:
                return Card(
                    entry["name"], entry.get("type", "command"), dict(entry.get("resources", {}) or {})
                )
            return Card(name, "command", {})

        actor.faction_id = payload.get("actor_faction_id", "red_army")
        actor.base = "北京"
        actor.organizations = {"北京": 1}
        actor.hand = []
        actor.deck.discard_pile = []

        viewer.faction_id = payload.get("viewer_faction_id", "liberals")
        viewer.base = payload.get("viewer_base", "德拉敦")
        viewer.organizations = {viewer.base: 1}
        viewer.hand = [proof_card(name) for name in hand_names]
        viewer.deck.draw_pile = [Card("補牌", "command", {})]
        viewer.deck.discard_pile = []

        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        game.game_phase = GamePhase.MAIN
        game.pending_base_choices = {}
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
        game.id = game_id

        # 直接建立 armed_target_discard pending choice（比照 effect_engine.py 的 force_discard
        # 分支對武裝系列卡牌的真正處理方式），略過武裝卡本身的合法目標檢查，聚焦在驗證
        # 「viewer 是否直接看到選擇視窗，而不是先被通知疊層擋住」這件事本身。
        game._set_pending_card_choice(
            viewer,
            "armed_target_discard",
            list(viewer.hand),
            f"{source_name}：從所有手牌中棄掉任 1 張牌。",
            source_name=source_name,
            initiator_player_id=actor.id,
            initiator_player_name=actor.name,
            target_player_name=viewer.name,
        )
        game.log(
            f"{actor.name} used {source_name} to ask {viewer.name} to choose 1 discard(s)"
        )

        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = list(
            zip([p.id for p in game.players], [p.name for p in game.players])
        )
        runtime.lobby_hosts[game_id] = actor.id
        runtime.lobby_factions[game_id] = {
            actor.id: actor.faction_id,
            viewer.id: viewer.faction_id,
        }
        runtime.lobby_bases[game_id] = {actor.id: actor.base, viewer.id: viewer.base}

        return {
            "success": True,
            "game_id": game_id,
            "actor_player_id": actor.id,
            "viewer_player_id": viewer.id,
            "state": game.state(),
        }
