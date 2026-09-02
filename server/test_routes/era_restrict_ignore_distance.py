"""Test-only route for the era-level build-distance restriction proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class EraRestrictIgnoreDistanceTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-era-restrict-ignore-distance-proof",
            self.test_setup_era_restrict_ignore_distance_proof,
            methods=["POST"],
        )

    def test_setup_era_restrict_ignore_distance_proof(self, payload: dict):
        """2026-08-09 playtest 回報的兩個問題共用的驗證場景：

        1. 時代關卡的 `restrict_ignore_distance_build` 紅色壓制（[反賊]公知世代的終結、
           [哈薩克]伊塔事件）生效後，思想家／組織經驗甲／東洋奧援 不該再無視距離建立
           牆內組織，只能退回己方組織 1 格內（另有增加建立距離的能力時為 2 格）；牆外
           仍維持無視距離。
        2. 「時代關卡達成」浮窗縮小之後，任何玩家（不只觸發者）都要能再點右上角的釘選
           卡片重新看到完整說明。

        payload:
          era: 時代 id，預設 "rebels"；"kazakh" 可驗證同型效果的泛用性。
          faction: 觸發方陣營，預設 "liberals"（rebel 陣營）。
          origin: 觸發方既有組織所在城鎮，預設 "上海"。
          card: 選填，發一張指定行動卡到觸發方手上（例：思想家）。
          build_range_bonus: 選填整數，用來驗證退回距離會加成到 2 格。
          extra_eras: 選填的時代 id 陣列，與 era 一併啟用——用來驗證四人局可能同時有多個
            時代關卡生效時，指揮中心提示列與釘選卡片能各自對應正確的時代（2026-08-09
            使用者回報：分頁上方的提示列比右上角釘選卡片更該是點擊入口）。
        """
        runtime = self._runtime_provider()
        era_id = payload.get("era", "rebels")
        extra_era_ids = payload.get("extra_eras") or []
        faction_id = payload.get("faction", "liberals")
        origin = payload.get("origin", "上海")

        game_id = str(uuid.uuid4())
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "opponent")]
        game = Game(players)
        viewer, opponent = game.players

        viewer.faction_id = faction_id
        viewer.base = origin
        viewer.organizations = {origin: 1}
        viewer.hand = []
        viewer.deck.draw_pile = []
        viewer.deck.discard_pile = []
        viewer.build_range_bonus = int(payload.get("build_range_bonus", 0) or 0)

        opponent.faction_id = "red_army"
        opponent.base = "北京"
        opponent.organizations = {"北京": 1}
        opponent.hand = []

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

        era_def = None
        if era_id:
            if not game.era_engine.activate_era(era_id):
                return {"error": f"時代關卡無法啟用：{era_id}"}
            era_def = game.era_engine.get_definition(era_id)
            game._apply_era_activation_effects(era_def)
            game.era_notification = game._era_notification_payload(era_def)
        for extra_era_id in extra_era_ids:
            if not game.era_engine.activate_era(extra_era_id):
                return {"error": f"時代關卡無法啟用：{extra_era_id}"}
            extra_era_def = game.era_engine.get_definition(extra_era_id)
            game._apply_era_activation_effects(extra_era_def)

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
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}

        inner_towns = set(game._towns_for_region_alias("china"))
        near_inner = set(game._towns_within_steps([origin], max_steps=1)) & inner_towns

        def _build_towns(name):
            card_def = next(
                (c for c in game.structured_cards if c.get("name") == name), None
            )
            effect = next(
                (e for e in (card_def or {}).get("effect", []) if e.get("type") == "build"),
                None,
            )
            if not effect:
                return []
            return sorted(
                {entry["town"] for entry in game._card_build_town_choices(viewer, effect)}
            )

        ideologue = _build_towns("思想家")
        org_experience_a = _build_towns("組織經驗甲")
        support_anywhere = sorted(
            {
                e["town"]
                for e in game._interactive_support_build_towns(viewer, near_only=False)
            }
        )
        support_near = sorted(
            {
                e["town"]
                for e in game._interactive_support_build_towns(viewer, near_only=True)
            }
        )

        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "opponent_player_id": opponent.id,
            "era_id": era_id,
            "era_name": (era_def or {}).get("name"),
            "origin": origin,
            "near_inner": sorted(near_inner),
            "ideologue_inner": [t for t in ideologue if t in inner_towns],
            "ideologue_outer_count": len([t for t in ideologue if t not in inner_towns]),
            "org_experience_a_inner": [t for t in org_experience_a if t in inner_towns],
            "east_asia_support_anywhere": support_anywhere,
            "east_asia_support_near": support_near,
            "url": f"/?game_id={game_id}&player_id={viewer.id}",
            "opponent_url": f"/?game_id={game_id}&player_id={opponent.id}",
            "state": game.state(),
        }
