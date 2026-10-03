"""Stage 5 (pending_choice/reaction resolver) + top-level orchestration.

`run_red_army_turn()` is the entry point requirement #11 asks for: given a
live `Game` object and the Red Army player's id, drive the policy forward
— resolving pending choices, taking action-phase decisions — until control
must return to a human (not Red Army's turn, or a pending choice belongs to
another player), the game ends, or a safety budget trips. It never mutates
`Game` directly; every state change goes through `action_submitter.submit()`
calling `Game`'s own existing action methods, and every decision re-reads
`Game.state()` fresh first (requirement #5 — no blind retries of a stale
command).

`step()` performs exactly one state-machine transition (plan section 3) and
is itself a fine building block for tests that want to inspect a single
decision without running a whole turn.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from red_army_policy import action_submitter
from red_army_policy.candidate_generator import generate_candidates
from red_army_policy.config import PolicyConfig
from red_army_policy.scoring import candidate_signature, rank, score_all
from red_army_policy.state_assessor import assess
from red_army_policy.target_selector import select_pending_choice_submission


def _find_player(state: dict, player_id: str) -> dict | None:
    for player in state.get("players") or []:
        if player.get("id") == player_id:
            return player
    return None


def _fingerprint(state: dict, legal: dict, excluded_signatures: frozenset | None = None) -> str:
    """Same idea as red_army_controller/controller.py's state_fingerprint():
    a stable hash of (state, legal_actions) used purely as a loop-guard
    signal, not for any gameplay decision.

    Also folds in the current `excluded_signatures` set (see
    `run_red_army_turn`'s docstring): a rejection that grows the exclusion
    set is real forward progress (the next iteration will try a different
    candidate) even though `state`/`legal` themselves are byte-identical to
    the previous iteration (the rejected submission was a no-op). Without
    this, the loop-guard could mistake "working through several doomed
    candidates in a row against an unchanged state" for "stuck re-deciding
    the exact same thing" and trip early.
    """
    material = {
        "state": state,
        "legal": legal,
        "excluded": sorted(repr(sig) for sig in (excluded_signatures or ())),
    }
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class StepResult:
    status: str  # "decision_made" | "waiting_other_pending" | "waiting_turn" | "game_over" | "no_legal_actions"
    decision: dict[str, Any] | None = None
    submit_result: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    legal: dict[str, Any] | None = None
    # The candidate_signature() of the action that was actually submitted
    # this step (action-phase decisions only — None for pending_choice
    # resolution, where there is no alternative candidate to fall back to).
    # run_red_army_turn adds this to its exclusion set on rejection.
    attempted_signature: tuple | None = None


@dataclass
class RunResult:
    status: str
    decisions: list[dict[str, Any]] = field(default_factory=list)
    steps_taken: int = 0


def _explain(chosen) -> str:
    breakdown = chosen.breakdown
    if breakdown.get("opponent_block_priority_override"):
        return breakdown.get("override_reason")
    numeric = {k: v for k, v in breakdown.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    if numeric:
        key = max(numeric, key=lambda k: abs(numeric[k]))
        return f"{key}={numeric[key]:.3f} was the dominant term in this candidate's score ({chosen.score:.3f})"
    return f"score={chosen.score}"


def _build_action_phase_decision_record(state: dict, decision_point: str, scored, chosen, tie: bool, config: PolicyConfig) -> dict:
    candidates_log = []
    for c in scored:
        entry: dict[str, Any] = {"action": c.action, "score": c.score, "breakdown": c.breakdown}
        if c.excluded_reason:
            entry["excluded_reason"] = c.excluded_reason
        candidates_log.append(entry)
    return {
        "turn": state.get("turn"),
        "decision_point": decision_point,
        "policy_version": config.policy_version,
        "candidates": candidates_log,
        "chosen": chosen.action,
        "chosen_reason": _explain(chosen),
        "tie_breaker_used": tie,
    }


def _resolve_pending_choice_step(game: Any, player_id: str, state: dict, config: PolicyConfig) -> StepResult:
    pending = state.get("pending_choice") or {}
    assessment = assess(state, player_id)
    submission = select_pending_choice_submission(pending, assessment)
    action: dict[str, Any] = {"kind": "resolve_pending_choice", "choice_id": pending.get("choice_id")}
    if "indices" in submission:
        action["indices"] = submission["indices"]
    else:
        action["index"] = submission["index"]

    option_list = (
        pending.get("targets")
        or pending.get("towns")
        or pending.get("options")
        or pending.get("cards")
        or []
    )
    decision = {
        "turn": state.get("turn"),
        "decision_point": "pending_choice_resolution",
        "policy_version": config.policy_version,
        "pending_choice_key": pending.get("choice_key"),
        "candidates": [{"index": i, "option": option} for i, option in enumerate(option_list)],
        "chosen": action,
        "chosen_reason": submission.get("reason"),
        "tie_breaker_used": False,
    }
    result = action_submitter.submit(game, player_id, action)
    decision["submit_result"] = result
    return StepResult("decision_made", decision, result, state=state)


def step(
    game: Any,
    player_id: str,
    *,
    config: PolicyConfig | None = None,
    faction_catalog: dict | None = None,
    card_catalog: dict | None = None,
    excluded_signatures: set | None = None,
) -> StepResult:
    config = config or PolicyConfig()
    state = game.state(player_id)

    if state.get("game_phase") == "finished":
        return StepResult("game_over", state=state)

    pending = state.get("pending_choice")
    if pending:
        if pending.get("player_id") != player_id:
            return StepResult("waiting_other_pending", state=state)
        return _resolve_pending_choice_step(game, player_id, state, config)

    me = _find_player(state, player_id)
    current_player_name = state.get("current_player")
    if me is None or me.get("name") != current_player_name:
        return StepResult("waiting_turn", state=state)

    legal = generate_candidates(state, player_id, faction_catalog=faction_catalog, card_catalog=card_catalog)
    if legal.get("waiting_on"):
        return StepResult("waiting_turn", state=state, legal=legal)

    actions = legal.get("actions") or []
    if not actions:
        return StepResult("no_legal_actions", state=state, legal=legal)

    turn_phase = state.get("turn_phase")
    if turn_phase == "event":
        action = dict(actions[0])
        decision = {
            "turn": state.get("turn"),
            "decision_point": "event_phase_advance",
            "policy_version": config.policy_version,
            "candidates": [{"action": action, "score": 0.0, "breakdown": {"forced": True}}],
            "chosen": action,
            "chosen_reason": "event phase only ever offers advance_turn",
            "tie_breaker_used": False,
        }
        result = action_submitter.submit(game, player_id, action)
        decision["submit_result"] = result
        return StepResult(
            "decision_made", decision, result, state=state, legal=legal,
            attempted_signature=candidate_signature(action),
        )

    assessment = assess(state, player_id)
    scored = score_all(actions, state, assessment, config, excluded_signatures=excluded_signatures)
    chosen, tie = rank(scored)
    if chosen is None:
        # Every legal candidate is either genuinely excluded (unaffordable,
        # etc.) or was rejected earlier this decision cycle and is sitting
        # in `excluded_signatures` — nothing left to try. A safe terminal
        # stop, not a hang: run_red_army_turn treats this like any other
        # "no legal actions" state.
        return StepResult("no_legal_actions", state=state, legal=legal)

    action = dict(chosen.action)
    action.update(chosen.submit_overrides)
    decision = _build_action_phase_decision_record(state, "action_phase_choice", scored, chosen, tie, config)
    result = action_submitter.submit(game, player_id, action)
    decision["submit_result"] = result
    decision["chosen_submitted_action"] = action
    return StepResult(
        "decision_made", decision, result, state=state, legal=legal,
        attempted_signature=candidate_signature(action),
    )


_TERMINAL_STATUSES = {"game_over", "waiting_other_pending", "waiting_turn", "no_legal_actions"}


def run_red_army_turn(
    game: Any,
    player_id: str,
    *,
    config: PolicyConfig | None = None,
    faction_catalog: dict | None = None,
    card_catalog: dict | None = None,
) -> RunResult:
    """Drive the Red Army policy forward until control must return to a
    human, the AI is blocked on another player's pending choice/reaction,
    the game ends, or a safety budget trips.

    Two independent loop guards (requirement #7): `config.max_steps` bounds
    total decisions regardless of anything else; `config.max_consecutive_same_fingerprint`
    (a (state, legal_actions, excluded_signatures) hash, same technique as
    red_army_controller/controller.py's `state_fingerprint`) catches a
    scoring bug that keeps re-deciding the same actionable state without
    ever making progress, even if that happens to stay under the step
    budget. `config.max_retries_per_decision` separately bounds consecutive
    *rejected* submissions (requirement #5's stale/rejected-command case) —
    distinct from the fingerprint guard because a healthy policy can submit
    many *different*, all-successful decisions in a row without ever
    repeating a fingerprint.

    `excluded_signatures` tracking (fixes a real Critical bug found by
    independent review): `legal_actions()` can list a faction_action as a
    candidate purely because it's dispatchable this turn, not because it
    currently has a legal target (mcp_server/summarize.py's own comment:
    "Server re-validates target/count limits per use."). 國安部 in
    particular can be offered with zero legal dissolve targets and still
    score highest (including the opponent-progress override) — rejected,
    re-derived from an unchanged state, and re-selected identically,
    submitting nothing for the whole turn. Each rejected decision's exact
    `candidate_signature()` is added to `excluded_signatures` so the SAME
    decision cycle's next retry is forced to fall through to the next-best
    legal candidate (e.g. 政工部, which only needs "another player exists")
    instead of re-picking the one that just failed. The set resets on every
    successful submission (a new decision cycle has genuinely begun) and is
    folded into the loop-guard fingerprint so "trying several different,
    doomed candidates in a row" is never mistaken for "stuck repeating the
    exact same decision".
    """
    config = config or PolicyConfig()
    decisions: list[dict[str, Any]] = []
    consecutive_retry_failures = 0
    last_fingerprint: str | None = None
    same_fingerprint_streak = 0
    excluded_signatures: set = set()

    for _ in range(config.max_steps):
        result = step(
            game, player_id, config=config, faction_catalog=faction_catalog, card_catalog=card_catalog,
            excluded_signatures=excluded_signatures,
        )

        if result.status in _TERMINAL_STATUSES:
            return RunResult(result.status, decisions, len(decisions))

        fingerprint = _fingerprint(result.state or {}, result.legal or {}, frozenset(excluded_signatures))
        if fingerprint == last_fingerprint:
            same_fingerprint_streak += 1
        else:
            last_fingerprint = fingerprint
            same_fingerprint_streak = 1
        if same_fingerprint_streak > config.max_consecutive_same_fingerprint:
            return RunResult("blocked_fingerprint_loop", decisions, len(decisions))

        decisions.append(result.decision)
        error = action_submitter.action_error_message(result.submit_result)
        if error:
            consecutive_retry_failures += 1
            if result.attempted_signature is not None:
                excluded_signatures.add(result.attempted_signature)
            if consecutive_retry_failures >= config.max_retries_per_decision:
                return RunResult("blocked_retry_exhausted", decisions, len(decisions))
            continue
        consecutive_retry_failures = 0
        excluded_signatures = set()

    return RunResult("blocked_step_budget", decisions, len(decisions))
