"""Rulebook / card / faction reference tools (the "MCP resources or
equivalent tools" requirement) — static data only, never touches a live
game's private state.
"""

from __future__ import annotations

from typing import Any

from mcp_server.context import AppContext
from mcp_server.rules_data import faction_win_condition_texts, read_rules_markdown, resolve_faction_detail
from mcp_server.tools.errors import call_guarded


async def get_rules_text(ctx: AppContext) -> dict[str, Any]:
    return {"ok": True, "rules_markdown": read_rules_markdown()}


async def list_cards(ctx: AppContext) -> dict[str, Any]:
    catalog = await call_guarded(ctx.rules.cards())
    cards = catalog.get("cards") or {}
    return {
        "ok": True,
        "cards": [{"name": name, "kind": info.get("kind"), "strength": info.get("strength")} for name, info in cards.items()],
        "note": "Call get_card_detail(name) for full effect text.",
    }


async def get_card_detail(ctx: AppContext, name: str) -> dict[str, Any]:
    catalog = await call_guarded(ctx.rules.cards())
    cards = catalog.get("cards") or {}
    detail = cards.get(name)
    if detail is None:
        return {"ok": False, "error": f"Unknown card name: {name}"}
    return {"ok": True, "card": detail}


async def get_faction_detail(ctx: AppContext, faction_id: str, base_name: str | None = None) -> dict[str, Any]:
    catalog = await call_guarded(ctx.rules.factions())
    detail = resolve_faction_detail(catalog, faction_id, base_name)
    if detail is None:
        return {"ok": False, "error": f"Unknown faction_id: {faction_id}"}
    win_conditions = faction_win_condition_texts(catalog, faction_id, base_name)
    return {
        "ok": True,
        "faction_id": faction_id,
        "name": detail.get("name") or detail.get("variant"),
        "bases": detail.get("bases", []),
        "abilities": detail.get("abilities", []),
        "setup_effects": detail.get("setup_effects", []),
        "special_rules": detail.get("special_rules", []),
        "restrictions": detail.get("restrictions", []),
        "win_conditions": win_conditions,
    }
