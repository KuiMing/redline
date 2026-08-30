"""Test-only route for the 安全屋 (safehouse) build-range proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class SafehouseRangeTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-safehouse-range-proof",
            self.test_setup_safehouse_range_proof,
            methods=["POST"],
        )

    def test_setup_safehouse_range_proof(self, payload: dict):
        """Proof setup for the 2026-08-09 playtest bug: 安全屋 是被動能力（passive），
        不該有任何專屬按鈕／面板／地圖捷徑；它唯一的表現方式，是玩家用正常方式（打出帶
        build 效果的行動卡）建立組織時，牆內目標的可建立距離 +1。

        payload:
          base: "臺北"（預設）或 "香港城"，兩個都是帶安全屋的香港根據地。
          card: 選填，發一張指定的行動卡到 viewer 手上，用來證明「卡牌觸發的建立候選
                清單仍然含有 2 格外的牆內城鎮」（正面案例，例：組織經驗丙）。
        """
        runtime = self._runtime_provider()
        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "opponent")]
        game = Game(players)

        viewer = game.players[0]
        opponent = game.players[1]

        base = payload.get("base", "臺北")

        viewer.faction_id = "hong_kong"
        viewer.base = base
        viewer.organizations = {base: 1}
        viewer.hand = []
        viewer.deck.draw_pile = []
        viewer.deck.discard_pile = []

        card_name = payload.get("card")
        if card_name:
            card_def = next(
                (c for c in game.structured_cards if c.get("name") == card_name), None
            )
            if not card_def:
                return {"error": f"找不到卡牌：{card_name}"}
            viewer.hand = [
                Card(card_def["name"], card_def["type"], card_def.get("resources", {}) or {})
            ]

        opponent.faction_id = "red_army"
        opponent.base = "北京"
        opponent.organizations = {"北京": 1}
        opponent.hand = []

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
            "state": game.state(),
        }
