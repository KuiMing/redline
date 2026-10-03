"""Stage 4 — TargetSelector.

Picks WHICH legal target/index to submit for a candidate that needs one.
Every target list this module chooses from (pending_choice's projected
`targets`/`towns`/`options`/`cards`, or a `faction_action` candidate's
`target_candidates`) was already enumerated by `state()`/`legal_actions()`;
this module only ranks/picks among them by index or by matching a field
(player_id, town name) already present on each entry — it never computes
adjacency, legality, or a town/player list of its own. In particular, index
selection is always "find the list entry whose own field matches what I
want" (enumerate + compare), never "count N items into the list" — the
exact class of index-off-by-one mistake the plan's regression table calls
out from a real session (建錯城鎮).

Scope cut (documented, not a regression requirement): choosing the best
TOWN for a build-type pending choice (event_build_organization,
era_red_build_near_target, card_build_organization, interactive_build_*)
falls back to the first offered town, index 0. `state()` does not expose
which faction currently rules a town (only who has organizations there),
so there is no server-authoritative signal this module could read to
prefer e.g. a Taiwan town over any other without re-deriving ruler data
itself — which would violate the "never re-derive server-authoritative
facts" boundary. A future iteration that exposes town ruler on `map.towns`
could upgrade this to prefer Taiwan towns for red_army's own
taiwan_organization_count progress.
"""

from __future__ import annotations

from typing import Any

from red_army_policy.state_assessor import Assessment


def _best_index_by_player_progress(entries: list[dict], assessment: Assessment) -> int:
    best_index = 0
    best_progress = -1.0
    for i, entry in enumerate(entries):
        player_id = entry.get("player_id") or entry.get("id")
        opponent = assessment.opponent_by_id(player_id)
        progress = opponent.condition_progress if opponent else -1.0
        if progress > best_progress:
            best_progress = progress
            best_index = i
    return best_index


def select_pending_choice_submission(pending: dict, assessment: Assessment) -> dict[str, Any]:
    """Return kwargs for `game.resolve_pending_choice(player_id, **kwargs)`
    (minus `player_id`/`expected_choice_id`, which the caller already has).

    Always resolves rather than cancels (even for choices the projection
    marks `cancellable`) — evaluating "cancel and do something else instead"
    is the plan's documented P1/P2 enhancement (section 3's PENDING_CHOICE
    node), not a required v1 regression scenario; always resolving forward
    is the safe, always-correct default for every pending choice REDLINE can
    open, cancellable or not.
    """
    choice_type = pending.get("type")
    reason = "default: first offered option"
    if choice_type == "target_choice":
        targets = pending.get("targets") or []
        index = _best_index_by_player_progress(targets, assessment) if targets else 0
        if targets:
            reason = "picked the target belonging to the opponent with the highest condition_progress"
        return {"index": index, "reason": reason}
    if choice_type == "town_choice":
        # Scope cut — see module docstring.
        return {"index": 0, "reason": "town_choice scope cut: first offered town (no ruler data exposed in state() to rank by)"}
    if choice_type == "option_choice":
        return {"index": 0, "reason": reason}
    if choice_type == "card_choice":
        return {"index": 0, "reason": reason}
    if choice_type == "multi_card_choice":
        min_count = int(pending.get("min_count") or 0)
        cards = pending.get("cards") or []
        indices = list(range(min(min_count, len(cards))))
        return {"indices": indices, "reason": f"picked the minimum required {min_count} card(s) by index order"}
    # support_flow_choice / reaction_choice / anything else this module
    # doesn't have a dedicated rule for yet: index 0 is always a safe,
    # always-in-range default when the choice carries any option list.
    return {"index": 0, "reason": "unmodelled choice type fallback: first offered option"}
