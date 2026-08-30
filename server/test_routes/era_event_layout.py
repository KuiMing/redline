"""Test-only route for laying out an era + event notification on an existing game."""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter


class EraEventLayoutTestRoutes:
    def __init__(self, manager_provider: Callable[[], Any]):
        self._manager_provider = manager_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-era-event-layout-proof",
            self.test_setup_era_event_layout_proof,
            methods=["POST"],
        )

    def test_setup_era_event_layout_proof(self, payload: dict):
        game_id = str(payload.get("game_id") or "")
        game = self._manager_provider().games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        requested_era_ids = payload.get("era_ids")
        era_ids = (
            [str(item) for item in requested_era_ids]
            if isinstance(requested_era_ids, list) and requested_era_ids
            else [str(payload.get("era_id") or "hong_kong")]
        )
        present_factions = {
            str(getattr(player, "faction_id", "") or "") for player in game.players
        }
        missing_factions = [era_id for era_id in era_ids if era_id not in present_factions]
        if missing_factions:
            return {
                "success": False,
                "error": "Era layout proof requires one matching player faction per active era",
                "missing_factions": missing_factions,
                "player_count": len(game.players),
            }
        eras = []
        for era_id in era_ids:
            era = game.era_engine.get_definition(era_id)
            if not era:
                return {"success": False, "error": f"Unknown era: {era_id}"}
            game.era_engine.activate_era(era_id)
            eras.append(era)
        era = eras[0]
        game.era_notification = game._era_notification_payload(era)
        game.era_notification["runtime_effects"] = {
            "red_suppression": (era.get("effects") or {}).get("red_suppression"),
            "revolution_counterattack": (era.get("effects") or {}).get(
                "revolution_counterattack"
            ),
        }

        event_name = str(payload.get("event_name") or "歲月靜好")
        event = game._event_by_name(event_name)
        if not event:
            return {"success": False, "error": f"Unknown event: {event_name}"}
        game.current_event = event
        game.event_progress = {
            "count": 0,
            "required": int((event.get("trigger") or {}).get("count", 0) or 0),
            "succeeded": True,
            "settled": True,
            "status": "idle",
        }
        game.event_notification = game._event_display_payload()
        game.event_deck.draw_pile = []
        game.event_deck.discard_pile = []
        return {
            "success": True,
            "game_id": game_id,
            "era_ids": era_ids,
            "event_name": event_name,
        }
