"""Room lifecycle: create/join/resume, faction+base selection, ready, start.

Every function here is a thin, privacy-irrelevant wrapper around
RedlineClient's HTTP calls (server/lobby_routes.py) — lobby data (player
names, chosen factions, ready flags) is not hidden information in REDLINE.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from mcp_server.context import AppContext
from mcp_server.redline_client import RedlineError
from mcp_server.tools.errors import call_guarded, game_error_result


async def create_room(ctx: AppContext, player_name: str) -> dict[str, Any]:
    try:
        data = await call_guarded(ctx.client.create_room(player_name))
    except RedlineError as exc:
        return game_error_result(exc)
    return {
        "ok": True,
        "game_id": data["game_id"],
        "player_id": data["host_id"],
        "resume_token": data["resume_token"],
        "role": "host",
        "next_step": "Call choose_faction, then set_ready. Once every seat is ready, the host calls start_game.",
    }


async def join_room(
    ctx: AppContext,
    game_id: str,
    player_name: str,
    player_id: str | None = None,
    resume_token: str | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    try:
        data = await call_guarded(
            ctx.client.join_room(game_id, player_name, player_id=player_id, resume_token=resume_token, device_id=device_id)
        )
    except RedlineError as exc:
        return game_error_result(exc)
    return {
        "ok": True,
        "game_id": game_id,
        "player_id": data["player_id"],
        "resume_token": data.get("resume_token"),
        "resumed": bool(data.get("resumed")),
        "role": "guest",
        "next_step": "Call choose_faction, then set_ready, and wait for the host to start_game.",
    }


async def resume_room(ctx: AppContext, game_id: str, player_id: str, resume_token: str) -> dict[str, Any]:
    try:
        data = await call_guarded(ctx.client.resume_room(game_id, player_id, resume_token))
    except RedlineError as exc:
        return game_error_result(exc)
    return {
        "ok": True,
        "game_id": data["game_id"],
        "player_id": data["player_id"],
        "name": data.get("name"),
        "resume_token": data.get("resume_token"),
        "started": bool(data.get("started")),
        "faction_id": data.get("faction_id"),
        "base": data.get("base"),
        "next_step": "Game already started: call get_state. Otherwise continue lobby setup.",
    }


async def get_room_status(ctx: AppContext, game_id: str) -> dict[str, Any]:
    try:
        data = await call_guarded(ctx.client.room_status(game_id))
    except RedlineError as exc:
        return game_error_result(exc)
    return {
        "ok": True,
        "game_id": game_id,
        "players": [{"player_id": pid, "name": name} for pid, name in data.get("players", [])],
        "host_id": data.get("host_id"),
        "seat_count": data.get("count"),
        "factions": data.get("factions", {}),
        "bases": data.get("bases", {}),
        "ready": data.get("ready", {}),
        "started": bool(data.get("started")),
        "market_mode": data.get("market_mode"),
        "required_faction_by_player": data.get("required_faction_by_player", {}),
    }


async def list_known_rooms(ctx: AppContext) -> dict[str, Any]:
    """Rooms this MCP process has created/joined/queried since it started —
    session-local bookkeeping, NOT a global room directory (REDLINE has no
    such endpoint; game_ids are shared out of band, like a room code)."""
    room_ids = ctx.client.known_room_ids()
    rooms = []
    for game_id in room_ids:
        try:
            status = await get_room_status(ctx, game_id)
        except ToolError:
            status = {"ok": False, "game_id": game_id, "error": "unreachable"}
        rooms.append(status)
    return {"ok": True, "rooms": rooms, "note": "Session-local list only; not a global room directory."}


async def choose_faction(
    ctx: AppContext, game_id: str, player_id: str, faction_id: str, base_name: str | None = None
) -> dict[str, Any]:
    try:
        data = await call_guarded(ctx.client.choose_faction(game_id, player_id, faction_id, base_name=base_name))
    except RedlineError as exc:
        return game_error_result(exc)
    return {"ok": True, "factions": data.get("factions", {}), "bases": data.get("bases", {})}


async def set_ready(ctx: AppContext, game_id: str, player_id: str, ready: bool = True) -> dict[str, Any]:
    try:
        data = await call_guarded(ctx.client.set_ready(game_id, player_id, ready=ready))
    except RedlineError as exc:
        return game_error_result(exc)
    return {"ok": True, "ready": data.get("ready", {})}


async def set_market_mode(ctx: AppContext, game_id: str, player_id: str, market_mode: str) -> dict[str, Any]:
    try:
        data = await call_guarded(ctx.client.set_market_mode(game_id, player_id, market_mode))
    except RedlineError as exc:
        return game_error_result(exc)
    return {"ok": True, "market_mode": data.get("market_mode")}


async def start_game(ctx: AppContext, game_id: str, player_id: str, market_mode: str | None = None) -> dict[str, Any]:
    try:
        data = await call_guarded(ctx.client.start_game(game_id, player_id, market_mode=market_mode))
    except RedlineError as exc:
        return game_error_result(exc)
    return {
        "ok": True,
        "market_mode": data.get("market_mode"),
        "next_step": "Call get_state for each seated player_id to see whether base selection is needed before the first turn.",
    }


async def list_factions(ctx: AppContext) -> dict[str, Any]:
    catalog = await call_guarded(ctx.rules.factions())
    summary = []
    for category in catalog.get("categories") or []:
        for option in category.get("options") or []:
            summary.append(
                {
                    "faction_id": option.get("id"),
                    "name": option.get("name") or option.get("variant") or option.get("label"),
                    "category": category.get("id"),
                    "base_options": option.get("base_options") or [],
                }
            )
    return {"ok": True, "factions": summary, "note": "Call get_faction_detail(faction_id) for abilities/win conditions."}
