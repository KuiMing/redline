"""Test-only route for the era activation notification proof state."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase
from server.test_routes.runtime import GameSetupRuntime


class EraNotificationTestRoutes:
    def __init__(self, runtime_provider: Callable[[], GameSetupRuntime]):
        self._runtime_provider = runtime_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-era-notification-proof",
            self.test_setup_era_notification_proof,
            methods=["POST"],
        )

    def test_setup_era_notification_proof(self, payload: dict):
        runtime = self._runtime_provider()
        era_id = payload.get("era_id") or payload.get("id") or "mongolia"
        players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
        game = Game(players, market_mode="all_cards")
        viewer = game.players[0]
        red = game.players[1]
        era = game.era_engine.get_definition(era_id)
        if not era:
            return {"success": False, "error": f"Unknown era: {era_id}"}

        trigger = era.get("trigger") or {}
        camp_to_faction = {
            "mongol": ("mongol", "烏蘭巴托"),
            "tibet": ("tibet", "拉薩"),
            "kazakh": ("kazakh", "阿拉木圖"),
            "uyghur": ("uyghur", "烏魯木齊"),
            "manchuria": ("manchuria", "瀋陽"),
            "rebel": ("liberals", "上海"),
            "taiwan": ("taiwan_green", "臺北"),
            "hong_kong": ("hong_kong", "香港"),
        }
        viewer.faction_id, viewer.base = camp_to_faction.get(
            trigger.get("camp"), ("liberals", "上海")
        )
        red.faction_id = "red_army"
        red.base = "北京"
        viewer.organizations = {viewer.base: 1}
        red.organizations = {"北京": 1}
        viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
        game.pending_base_choices = []
        game.game_phase = GamePhase.MAIN
        game.current_player_index = 0
        game.turn_phase = TurnPhase.ACTION
        via_lifecycle = bool(payload.get("via_lifecycle"))
        if via_lifecycle:
            region = trigger.get("region")
            required = int(trigger.get("count", 0) or 0)
            legal_towns = [
                town
                for town in game._towns_for_region_alias(region)
                if game.can_faction_develop_in_town(viewer.faction_id, town)
            ]
            if trigger.get("type") != "count_only" or len(legal_towns) < required:
                return {
                    "success": False,
                    "error": f"Era cannot use lifecycle proof setup: {era_id}",
                }
            viewer.organizations = {town: 1 for town in legal_towns[:required]}
            game.current_event = {"id": "test-idle", "name": "測試靜止事件", "type": "idle"}
            game.event_progress = {
                "count": 0,
                "required": 0,
                "succeeded": True,
                "settled": True,
                "status": "idle",
            }
            # Era trigger detection now runs only at the round-wrap boundary (after every
            # player incl. Red Army has acted). Advance from Red Army's seat (the last
            # seat) so ending its turn wraps the round and detection activates the era —
            # ending the viewer's own turn mid-round no longer triggers detection.
            # 出牌與購買已合併為單一行動階段：一次 advance 現在就會結束紅軍回合並跨輪。
            game.current_player_index = game.players.index(red)
            game.advance_turn_phase()
            if era_id not in game.era_engine.get_active_eras():
                return {
                    "success": False,
                    "error": f"Era did not activate through lifecycle: {era_id}",
                }
        else:
            game.era_engine.activate_era(era_id)
            game.era_notification = game._era_notification_payload(era)
            game.era_notification["runtime_effects"] = {
                "red_suppression": (era.get("effects") or {}).get("red_suppression"),
                "revolution_counterattack": (era.get("effects") or {}).get(
                    "revolution_counterattack"
                ),
            }

        game_id = str(uuid.uuid4())
        runtime.manager.games[game_id] = game
        runtime.manager.connections[game_id] = runtime.manager.connections.get(game_id, {})
        runtime.lobby[game_id] = [(p.id, p.name) for p in game.players]
        runtime.lobby_hosts[game_id] = viewer.id
        runtime.lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
        runtime.lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
        runtime.lobby_ready[game_id] = {p.id: True for p in game.players}
        return {
            "success": True,
            "game_id": game_id,
            "player_id": viewer.id,
            "red_player_id": red.id,
            "era_id": era.get("id"),
            "era_name": era.get("name"),
            "via_lifecycle": via_lifecycle,
            "viewer_organizations": dict(viewer.organizations),
            "url": f"/?game_id={game_id}&player_id={viewer.id}",
            "state": game.state(),
        }
