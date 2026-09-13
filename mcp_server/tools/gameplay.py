"""In-game tools: read state, discover legal actions, and act.

Every action tool sends exactly one WebSocket message to the real REDLINE
server (server/main.py's `/ws/{game_id}/{player_id}` handler) and waits for
the resulting state, so gameplay behaves identically to a browser client —
including the server remaining the sole authority on legality.
"""

from __future__ import annotations

from typing import Any

from mcp_server import summarize
from mcp_server.context import AppContext
from mcp_server.tools.errors import call_guarded

VALID_PLAY_MODES = {"resource", "action"}
VALID_MOVE_MODES = {"road", "rail"}


async def _summary_bundle(ctx: AppContext, state: dict, player_id: str) -> dict[str, Any]:
    faction_catalog = await call_guarded(ctx.rules.factions())
    card_catalog = await call_guarded(ctx.rules.cards())
    legal = summarize.legal_actions(state, player_id, faction_catalog, card_catalog.get("cards") or {})
    return {
        "state": summarize.summarize_state(state, player_id),
        "legal_action_kinds": summarize.compact_legal_action_kinds(legal),
    }


async def get_state(ctx: AppContext, game_id: str, player_id: str, resume_token: str | None = None) -> dict[str, Any]:
    state = await call_guarded(ctx.client.get_state(game_id, player_id, resume_token=resume_token))
    bundle = await _summary_bundle(ctx, state, player_id)
    return {"ok": True, **bundle}


async def get_state_detail(ctx: AppContext, game_id: str, player_id: str, section: str) -> dict[str, Any]:
    state = await call_guarded(ctx.client.get_state(game_id, player_id))
    try:
        value = summarize.state_detail(state, section)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "valid_sections": sorted(summarize.STATE_DETAIL_SECTIONS)}
    return {"ok": True, "section": section, "value": value}


async def get_legal_actions(ctx: AppContext, game_id: str, player_id: str) -> dict[str, Any]:
    state = await call_guarded(ctx.client.get_state(game_id, player_id))
    faction_catalog = await call_guarded(ctx.rules.factions())
    card_catalog = await call_guarded(ctx.rules.cards())
    legal = summarize.legal_actions(state, player_id, faction_catalog, card_catalog.get("cards") or {})
    return {"ok": True, **legal}


async def _do_action(ctx: AppContext, game_id: str, player_id: str, action: str, payload: dict) -> dict[str, Any]:
    state, error = await call_guarded(ctx.client.send_action(game_id, player_id, action, payload))
    bundle = await _summary_bundle(ctx, state, player_id)
    if error:
        return {"ok": False, "error": error, **bundle}
    return {"ok": True, **bundle}


async def play_card(
    ctx: AppContext,
    game_id: str,
    player_id: str,
    index: int,
    mode: str,
    target_player_id: str | None = None,
) -> dict[str, Any]:
    if mode not in VALID_PLAY_MODES:
        return {"ok": False, "error": f"mode must be one of {sorted(VALID_PLAY_MODES)}"}
    payload: dict[str, Any] = {"index": index, "mode": mode}
    if target_player_id:
        payload["target_player_id"] = target_player_id
    return await _do_action(ctx, game_id, player_id, "play_card", payload)


async def build_organization(ctx: AppContext, game_id: str, player_id: str, town: str) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "build", {"town": town})


async def move_organization(
    ctx: AppContext, game_id: str, player_id: str, from_town: str, to_town: str, mode: str = "road"
) -> dict[str, Any]:
    if mode not in VALID_MOVE_MODES:
        return {"ok": False, "error": f"mode must be one of {sorted(VALID_MOVE_MODES)}"}
    return await _do_action(ctx, game_id, player_id, "move", {"from": from_town, "to": to_town, "mode": mode})


async def buy_card(ctx: AppContext, game_id: str, player_id: str, index: int) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "buy_card", {"index": index})


async def buy_cards(ctx: AppContext, game_id: str, player_id: str, indices: list[int]) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "buy_cards", {"indices": indices})


async def dissolve_organization(
    ctx: AppContext, game_id: str, player_id: str, defender_player_id: str, town: str
) -> dict[str, Any]:
    """Direct board dissolve for the rare interactions that use it rather
    than a pending_choice target list (see server/main.py's 'dissolve'
    action). Most dissolve flows arrive as a pending_choice instead — check
    get_legal_actions first; if it shows a resolve_pending_choice entry, use
    that, not this tool."""
    return await _do_action(
        ctx, game_id, player_id, "dissolve", {"defender": defender_player_id, "town": town}
    )


async def use_faction_action(
    ctx: AppContext,
    game_id: str,
    player_id: str,
    name: str,
    guess: str | None = None,
    target_player_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": name}
    if guess:
        payload["guess"] = guess
    if target_player_id:
        payload["target_player_id"] = target_player_id
    return await _do_action(ctx, game_id, player_id, "faction_action", payload)


async def advance_turn(ctx: AppContext, game_id: str, player_id: str) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "advance", {})


async def use_topdeck_right(ctx: AppContext, game_id: str, player_id: str) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "use_topdeck_right", {})


async def resolve_pending_choice(
    ctx: AppContext, game_id: str, player_id: str, index: int | None = None, indices: list[int] | None = None
) -> dict[str, Any]:
    """Most pending choices take a single `index`. A few (choice_type
    'multi_card_choice' — see get_legal_actions' `count`/`min_count`) need
    several at once: pass those as `indices` instead. Exactly one of
    `index`/`indices` must be given."""
    if (index is None) == (indices is None):
        return {"ok": False, "error": "Provide exactly one of index or indices"}
    return await _do_action(ctx, game_id, player_id, "resolve_choice", {"index": indices if indices is not None else index})


async def cancel_pending_choice(ctx: AppContext, game_id: str, player_id: str) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "cancel_choice", {})


async def set_base(ctx: AppContext, game_id: str, player_id: str, town: str, label: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"town": town}
    if label:
        payload["label"] = label
    return await _do_action(ctx, game_id, player_id, "set_base", payload)


async def relocate_hong_kong_base(ctx: AppContext, game_id: str, player_id: str, town: str) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "relocate_base", {"town": town})


async def keep_hong_kong_base(ctx: AppContext, game_id: str, player_id: str) -> dict[str, Any]:
    return await _do_action(ctx, game_id, player_id, "keep_hong_kong_base", {})


async def disconnect_session(ctx: AppContext, game_id: str, player_id: str) -> dict[str, Any]:
    await ctx.client.close_session(game_id, player_id)
    return {"ok": True, "note": "Connection closed; the next tool call for this player will reconnect."}
