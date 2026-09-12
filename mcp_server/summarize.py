"""Turn a raw (already viewer-scoped) `Game.state(player_id)` payload into
model-friendly summaries: a compact status snapshot, a legal-actions
projection, and on-demand detail sections — so a tool call never has to dump
the entire state object to make progress.

Nothing here adds information beyond what `state` already contains. The
privacy boundary is entirely upstream (server/game.py's `state()`); this
module only reshapes and filters, it never reads a different viewer's data.
"""

from __future__ import annotations

from typing import Any

from mcp_server.rules_data import (
    HIDDEN_HAND_CARD_LABEL,
    TARGETED_ACTION_CARD_NAMES,
    faction_dispatchable_action_names,
)

STATE_DETAIL_SECTIONS = {
    "map",
    "purchase_area",
    "players",
    "action_log",
    "pending_choice",
    "active_eras",
    "active_era_details",
    "era_notification",
    "current_event",
    "static_purchase_supply",
}


def _find_player(state: dict, player_id: str) -> dict | None:
    for player in state.get("players") or []:
        if player.get("id") == player_id:
            return player
    return None


def _pending_option_count(pending: dict) -> int:
    for key in ("options", "towns", "targets", "cards"):
        values = pending.get(key)
        if values:
            return len(values)
    return 0


def _pending_choice_summary(pending: dict, player_id: str) -> dict:
    return {
        "type": pending.get("type"),
        "choice_key": pending.get("choice_key"),
        "prompt": pending.get("prompt"),
        "source_name": pending.get("source_name"),
        "for_player_id": pending.get("player_id"),
        "for_player_name": pending.get("player_name"),
        "is_mine_to_resolve": pending.get("player_id") == player_id,
        "cancellable": bool(pending.get("cancellable")),
        "option_count": _pending_option_count(pending),
        "min_count": pending.get("min_count"),
        "count": pending.get("count"),
    }


def summarize_state(state: dict, player_id: str) -> dict:
    me = _find_player(state, player_id)
    current_player_name = state.get("current_player")
    is_my_turn = bool(me and me.get("name") == current_player_name)
    pending = state.get("pending_choice")
    game_over = state.get("game_phase") == "finished"
    event = state.get("current_event") or {}

    return {
        "turn": state.get("turn"),
        "game_phase": state.get("game_phase"),
        "turn_phase": state.get("turn_phase"),
        "current_player_name": current_player_name,
        "is_my_turn": is_my_turn,
        "my_player_id": player_id,
        "my_faction": me.get("faction") if me else None,
        "my_base": me.get("base") if me else None,
        "my_resources": me.get("resources") if me else None,
        "my_hand_size": len(me.get("hand") or []) if me else 0,
        "game_over": game_over,
        "winner": state.get("winner"),
        "co_winners": state.get("co_winners") or [],
        "pending_choice": _pending_choice_summary(pending, player_id) if pending else None,
        "pending_base_choice_for_me": bool((state.get("pending_base_choices") or {}).get(player_id)),
        "hk_relocation_open_for_me": bool(state.get("hk_free_base_relocation")) and bool(me) and me.get("faction") == "hong_kong",
        "current_event_name": event.get("name"),
        "purchase_area": state.get("purchase_area") or [],
        "players": [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "faction": p.get("faction"),
                "resources": p.get("resources"),
                "organization_total": (p.get("organization_counts") or {}).get("total"),
            }
            for p in state.get("players") or []
        ],
        "recent_log": (state.get("action_log") or [])[-5:],
    }


def state_detail(state: dict, section: str) -> Any:
    if section not in STATE_DETAIL_SECTIONS:
        raise ValueError(
            f"Unknown section '{section}'. Valid sections: {', '.join(sorted(STATE_DETAIL_SECTIONS))}"
        )
    return state.get(section)


def _hand_action_legality_for(me: dict, index: int) -> dict | None:
    legality_list = me.get("hand_action_legality") or []
    if 0 <= index < len(legality_list):
        return legality_list[index]
    return None


def legal_actions(state: dict, player_id: str, faction_catalog: dict) -> dict:
    me = _find_player(state, player_id)
    if me is None:
        return {"waiting_on": None, "reason": "Player not found in this game's state", "actions": []}

    if state.get("game_phase") == "finished":
        return {
            "waiting_on": None,
            "reason": "Game is over",
            "game_over": True,
            "winner": state.get("winner"),
            "co_winners": state.get("co_winners") or [],
            "actions": [],
        }

    pending = state.get("pending_choice")
    if pending:
        if pending.get("player_id") == player_id:
            return {
                "waiting_on": None,
                "reason": None,
                "actions": [_pending_choice_action_entry(pending)],
            }
        return {
            "waiting_on": pending.get("player_name") or pending.get("player_id"),
            "reason": f"Waiting for {pending.get('player_name')} to resolve a pending choice ({pending.get('choice_key')})",
            "actions": [],
        }

    if state.get("game_phase") == "base_selection":
        base_choice = (state.get("pending_base_choices") or {}).get(player_id)
        if base_choice:
            return {
                "waiting_on": None,
                "reason": None,
                "actions": [
                    {
                        "kind": "set_base",
                        "options": [
                            {"label": label, "town": town}
                            for label, towns in (base_choice.get("resolved") or {}).items()
                            for town in towns
                        ],
                    }
                ],
            }
        return {"waiting_on": "other players", "reason": "Waiting for other players to choose a base", "actions": []}

    if bool(state.get("hk_free_base_relocation")) and me.get("faction") == "hong_kong":
        return {
            "waiting_on": None,
            "reason": None,
            "actions": [
                {"kind": "keep_hong_kong_base", "current_base": me.get("base")},
                {"kind": "relocate_hong_kong_base", "why": "See faction detail for legal relocation towns"},
            ],
        }

    current_player_name = state.get("current_player")
    if me.get("name") != current_player_name:
        return {
            "waiting_on": current_player_name,
            "reason": f"Not your turn; waiting for {current_player_name}",
            "actions": [],
        }

    turn_phase = state.get("turn_phase")
    if turn_phase == "event":
        return {
            "waiting_on": None,
            "reason": None,
            "turn_phase": turn_phase,
            "actions": [
                {"kind": "advance_turn", "why": "Resolve/pass the event phase and move into the action phase."}
            ],
        }

    actions: list[dict] = []
    hand = me.get("hand") or []
    for index, card_name in enumerate(hand):
        entry: dict[str, Any] = {"kind": "play_card", "index": index, "card_name": card_name, "modes": ["resource"]}
        if card_name != HIDDEN_HAND_CARD_LABEL:
            legality = _hand_action_legality_for(me, index)
            if legality is None or legality.get("playable", True):
                entry["modes"].append("action")
            elif legality.get("reason"):
                entry["action_mode_blocked_reason"] = legality["reason"]
            if card_name in TARGETED_ACTION_CARD_NAMES:
                entry["needs_target_player_id"] = True
                entry["target_candidates"] = [p["id"] for p in state.get("players") or [] if p.get("id") != player_id]
        actions.append(entry)

    legal_moves = ((state.get("map") or {}).get("legal_organization_moves")) or {}
    for from_town, modes in legal_moves.items():
        for mode_name, destinations in (modes or {}).items():
            for destination in destinations or []:
                actions.append(
                    {
                        "kind": "move_organization",
                        "from_town": from_town,
                        "to_town": destination.get("town"),
                        "mode": mode_name,
                        "cost": destination.get("cost"),
                    }
                )

    purchase_area = state.get("purchase_area") or []
    affordable = state.get("purchase_area_affordable") or []
    costs = state.get("purchase_area_costs") or []
    for index, card_name in enumerate(purchase_area):
        actions.append(
            {
                "kind": "buy_card",
                "index": index,
                "card_name": card_name,
                "cost": costs[index] if index < len(costs) else None,
                "affordable": affordable[index] if index < len(affordable) else None,
            }
        )

    actions.extend(_faction_action_entries(state, me, faction_catalog))

    if state.get("topdeck_candidates_count"):
        actions.append({"kind": "use_topdeck_right", "candidate_count": state.get("topdeck_candidates_count")})

    actions.append(
        {"kind": "advance_turn", "why": "End the action phase: draw back to 5, refill the market, pass the turn."}
    )

    return {
        "waiting_on": None,
        "reason": None,
        "turn_phase": turn_phase,
        "actions": actions,
    }


def compact_legal_action_kinds(legal: dict) -> dict:
    """Collapse a full legal_actions() result into just kind counts, for
    embedding in every action tool's response as a next-step nudge. Call
    get_legal_actions separately for the indices/params needed to act.
    """
    kinds: dict[str, int] = {}
    for action in legal.get("actions") or []:
        kind = action.get("kind", "unknown")
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "waiting_on": legal.get("waiting_on"),
        "reason": legal.get("reason"),
        "kind_counts": kinds,
    }


def _pending_choice_action_entry(pending: dict) -> dict:
    entry = {
        "kind": "resolve_pending_choice",
        "choice_type": pending.get("type"),
        "choice_key": pending.get("choice_key"),
        "prompt": pending.get("prompt"),
    }
    for key in ("options", "towns", "targets", "cards"):
        values = pending.get(key)
        if values:
            entry["index_range"] = [0, len(values) - 1]
            entry[key] = values
            break
    if pending.get("type") == "multi_card_choice":
        entry["use_indices_param"] = True
        entry["count"] = pending.get("count")
        entry["min_count"] = pending.get("min_count")
    if pending.get("cancellable"):
        entry["cancel_available"] = True
    return entry


def _faction_action_entries(state: dict, me: dict, faction_catalog: dict) -> list[dict]:
    faction_id = me.get("faction")
    if not faction_id:
        return []
    candidate_names = faction_dispatchable_action_names(faction_catalog, faction_id, me.get("base"))
    if not candidate_names:
        return []

    entries: list[dict] = []
    is_red_army = faction_id == "red_army"
    if is_red_army:
        limit = state.get("red_army_action_limit")
        used = state.get("red_army_action_count") or 0
        remaining = None if limit is None else max(0, limit - used)
        if remaining == 0:
            return []
        for name in candidate_names:
            entry = {"kind": "faction_action", "name": name, "note": "Server re-validates target/count limits per use."}
            if name == "政工部":
                entry["needs_target_player_id"] = True
                entry["target_candidates"] = [p["id"] for p in state.get("players") or [] if p.get("id") != me.get("id")]
            entries.append(entry)
        return entries

    if state.get("faction_action_used"):
        return []
    for name in candidate_names:
        entry = {"kind": "faction_action", "name": name}
        if name in {"賭徒耳語", "民族祭儀"}:
            entry["needs_guess"] = "odd_or_even"
        entries.append(entry)
    return entries
