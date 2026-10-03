"""Stage 3 — ScoringEngine.

Pure function(s): (state, Assessment, one legal_actions() candidate) -> a
score + an explainable breakdown. Never mutates `state`/`Assessment`, never
calls into `Game` or submits anything. This is the one genuinely new piece
of logic in the whole pipeline (plan section 2's closing paragraph) — every
upstream value it reads (condition_progress, organization totals,
affordability, action_effect_text, ...) was already computed authoritatively
by server/game.py or mcp_server/summarize.py.

Per-candidate scores are heuristic estimates, not server-verified "if I did
this, the resulting state would be X" dry-runs (plan section 4.2 explicitly
allows falling back to heuristics when no cheap dry-run path exists, and
documents that heuristic scores must be labelled as such). None of
REDLINE's action methods expose a side-effect-free "preview" call, so every
dimension below is a heuristic estimate — `breakdown["_heuristic"]` is
always `True` on every entry this module produces, to keep that honest in
the decision log rather than implying server-verified precision.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from red_army_policy.config import PolicyConfig
from red_army_policy.state_assessor import Assessment

# Keywords read off the server's own card_presentation `effect_text` (same
# field summarize.py's `_action_effect_text` already surfaces on the
# candidate as `action_effect_text`) — detecting "this action-mode card
# builds an organization" from text the server already computed is reading
# a label, not re-deriving a rule: the server, not this heuristic, decides
# whether the card mode is legal to play at all.
_GROWTH_EFFECT_KEYWORDS = ("建立", "組織")
_DISSOLVE_EFFECT_KEYWORDS = ("瓦解",)


def candidate_signature(action: dict) -> tuple:
    """A hashable identity for "this specific candidate, with whatever
    target/index/mode it would actually be submitted with" — used by
    run_red_army_turn to remember "this exact candidate was just rejected
    this decision cycle, don't re-pick it" (see policy.py's
    `excluded_signatures` handling). Deliberately includes `target_player_id`
    for `faction_action` (so a different target for the same ability name
    is a different candidate, not excluded together) — callers must compute
    this from the *effective* action (raw candidate merged with
    ScoringEngine's own `submit_overrides`, e.g. a chosen target/mode), not
    the bare legal_actions() candidate, so the signature matches what
    actually gets submitted.
    """
    kind = action.get("kind")
    if kind == "faction_action":
        return (kind, action.get("name"), action.get("target_player_id"))
    if kind in ("play_card", "buy_card"):
        return (kind, action.get("index"))
    if kind == "move_organization":
        return (kind, action.get("from_town"), action.get("to_town"), action.get("mode"))
    if kind == "resolve_pending_choice":
        return (kind, action.get("choice_id"))
    return (kind,)


@dataclass
class ScoredCandidate:
    index: int
    action: dict[str, Any]
    score: float | None
    breakdown: dict[str, Any]
    excluded_reason: str | None = None
    # Extra submission parameters ScoringEngine/TargetSelector decided on
    # top of the raw legal_actions() candidate (e.g. which `mode` to play a
    # card in, which target_player_id to aim a targeted action at).
    submit_overrides: dict[str, Any] = field(default_factory=dict)


def _buy_card_score(action: dict, assessment: Assessment, config: PolicyConfig) -> tuple[float | None, dict, str | None]:
    weights = config.weights
    if action.get("affordable") is False:
        return None, {"_heuristic": True, "affordable": False}, "unaffordable"
    raw = (
        weights.buy_card_base_value
        - weights.buy_card_diminishing_rate * assessment.purchased_cards_this_turn_count
    )
    score = weights.w5_resource_efficiency * raw
    breakdown = {
        "_heuristic": True,
        "resource_efficiency": score,
        "purchased_cards_this_turn_count": assessment.purchased_cards_this_turn_count,
        "diminishing_marginal_value": raw,
    }
    return score, breakdown, None


def _play_card_score(action: dict, assessment: Assessment, config: PolicyConfig) -> tuple[float, dict, dict]:
    weights = config.weights
    modes = action.get("modes") or ["resource"]
    effect_text = action.get("action_effect_text") or ""
    overrides: dict[str, Any] = {}
    # A legal printed action is the AI's immediate tactical opportunity. It
    # must outrank the highest possible generic purchase score; otherwise the
    # v1 weights greedily shop first and delay every real card action until no
    # further purchase is affordable.
    action_mode_floor = weights.w5_resource_efficiency * (weights.buy_card_base_value + 0.5)
    if "action" in modes and any(k in effect_text for k in _GROWTH_EFFECT_KEYWORDS):
        score = max(weights.w4_organization_growth * 3.0, action_mode_floor)
        breakdown = {"_heuristic": True, "organization_growth": score, "reason": "action_effect_text suggests building an organization"}
        overrides["mode"] = "action"
    elif "action" in modes and any(k in effect_text for k in _DISSOLVE_EFFECT_KEYWORDS):
        blocking_bonus = weights.w2_block_opponent_progress * 0.5 * assessment.max_opponent_progress
        score = action_mode_floor + blocking_bonus
        breakdown = {
            "_heuristic": True,
            "legal_action_priority": action_mode_floor,
            "block_opponent_progress": blocking_bonus,
            "reason": "action_effect_text suggests a dissolve/disruption effect",
        }
        overrides["mode"] = "action"
    elif "action" in modes and effect_text:
        score = action_mode_floor
        breakdown = {"_heuristic": True, "legal_action_priority": score, "reason": "play a legal printed action before generic market purchases"}
        overrides["mode"] = "action"
    else:
        score = weights.w5_resource_efficiency * 0.4
        breakdown = {"_heuristic": True, "resource_mode_fallback": score}
        overrides["mode"] = "resource"
    if action.get("needs_target_player_id") or action.get("optional_target_player_id"):
        target_candidates = action.get("target_candidates") or []
        best = _best_target_player_id(target_candidates, assessment)
        if best is not None:
            overrides["target_player_id"] = best
    return score, breakdown, overrides


def _best_target_player_id(candidate_ids: list[str], assessment: Assessment) -> str | None:
    best_id = None
    best_progress = -1.0
    for pid in candidate_ids:
        opponent = assessment.opponent_by_id(pid)
        progress = opponent.condition_progress if opponent else 0.0
        if progress > best_progress:
            best_progress = progress
            best_id = pid
    return best_id


def _move_organization_score(action: dict, config: PolicyConfig) -> tuple[float, dict]:
    cost = float(action.get("cost") or 1.0)
    raw = max(0.1, 2.0 - 0.5 * cost)
    score = config.weights.w3_region_control * raw
    return score, {"_heuristic": True, "region_control": score, "move_cost": cost}


def _faction_action_score(action: dict, assessment: Assessment, config: PolicyConfig) -> tuple[float, dict, dict]:
    weights = config.weights
    name = action.get("name")
    base = weights.faction_action_base.get(name, 1.0)
    overrides: dict[str, Any] = {}
    breakdown: dict[str, Any] = {"_heuristic": True, "faction_action_base": base}
    score = base
    if name == "國安部":
        bonus = weights.w2_block_opponent_progress * assessment.max_opponent_progress
        score += bonus
        breakdown["block_opponent_progress"] = bonus
        breakdown["opponent_progress_considered"] = assessment.max_opponent_progress
    elif name == "政工部":
        bonus = weights.w2_block_opponent_progress * 0.2 * assessment.max_opponent_progress
        score += bonus
        breakdown["block_opponent_progress_secondary"] = bonus
        if action.get("needs_target_player_id"):
            best = _best_target_player_id(action.get("target_candidates") or [], assessment)
            if best is not None:
                overrides["target_player_id"] = best
    elif name == "統戰部":
        breakdown["card_advantage"] = 0.0
    elif name == "中紀委":
        breakdown["hand_quality"] = 0.0
    return score, breakdown, overrides


def score_candidate(action: dict, state: dict, assessment: Assessment, config: PolicyConfig) -> tuple[float | None, dict, str | None, dict]:
    """Return (score, breakdown, excluded_reason, submit_overrides) for one
    legal_actions() candidate dict. `score is None` means excluded (never
    chosen regardless of tie-break); breakdown is always present so the
    decision log can show why.
    """
    kind = action.get("kind")
    if kind == "buy_card":
        score, breakdown, excluded = _buy_card_score(action, assessment, config)
        return score, breakdown, excluded, {}
    if kind == "play_card":
        score, breakdown, overrides = _play_card_score(action, assessment, config)
        return score, breakdown, None, overrides
    if kind == "move_organization":
        score, breakdown = _move_organization_score(action, config)
        return score, breakdown, None, {}
    if kind == "faction_action":
        score, breakdown, overrides = _faction_action_score(action, assessment, config)
        return score, breakdown, None, overrides
    if kind == "use_topdeck_right":
        score = config.weights.w5_resource_efficiency * 0.5
        return score, {"_heuristic": True, "card_advantage": score}, None, {}
    if kind == "advance_turn":
        return 0.0, {"_heuristic": True, "baseline": 0.0}, None, {}
    # Unmodelled kinds (set_base/keep_hong_kong_base/relocate_hong_kong_base,
    # or anything legal_actions() adds in the future before this module is
    # updated for it): a safe, deterministic, always-available fallback
    # rather than crashing or silently skipping the candidate.
    return 0.0, {"_heuristic": True, "unmodelled_kind_fallback": True}, None, {}


def score_all(
    actions: list[dict],
    state: dict,
    assessment: Assessment,
    config: PolicyConfig,
    rng: random.Random | None = None,
    excluded_signatures: set | None = None,
) -> list[ScoredCandidate]:
    """Score every candidate. `rng` is this policy's own injectable seeded
    random source for difficulty-level scoring noise (plan section 7, knob
    1) — NOT the game engine's RNG (see config.py's module docstring for the
    exact determinism boundary). Only consulted when `config.noise_scale`
    is nonzero; defaults to a fresh `random.Random(config.seed)` so calling
    this twice with the same `config.seed` and the same candidate order
    reproduces the same noise sequence. Noise is applied in a fixed order
    (candidate index) so the sequence of `rng` draws is itself deterministic
    given the same candidate list, independent of dict/set iteration order.

    Known follow-up, not yet an issue because `config.noise_scale` defaults
    to 0.0 and nothing wires up a nonzero value today: `policy.step()` never
    passes an `rng` through, so each call here falls back to a *fresh*
    `random.Random(config.seed)` rather than one `rng` instance threaded
    across a turn's several decision points. Once `noise_scale != 0` is
    ever wired up to a difficulty setting, every decision point in the same
    turn would draw the identical per-candidate-index noise sequence
    instead of a continuing one. Fix then: have `run_red_army_turn` own one
    `random.Random(config.seed)` and pass it into every `step()` call.

    `excluded_signatures` (plan-independent, added after the first real
    repro of a Critical bug — see policy.py's `run_red_army_turn`
    docstring): a candidate that `candidate_signature()` matches against
    this set is forced to `score=None` (never chosen), no matter how it
    would otherwise score. This exists because `legal_actions()` lists a
    faction_action as a candidate purely on dispatchability (per-turn count
    not exhausted) — NOT on whether a target is actually in range right
    now (mcp_server/summarize.py's own comment on `_faction_action_entries`:
    "Server re-validates target/count limits per use."). 國安部 in
    particular can be offered with zero legal dissolve targets this turn
    (e.g. no opposing organization is within 1 step of a Red Army
    organization) and still carry a high base weight, including the
    opponent-progress override — without this exclusion mechanism, a
    rejected 國安部 gets re-derived from an unchanged state and re-selected
    identically forever, submitting nothing for the whole turn. Excluding a
    rejected candidate's exact signature for the rest of this decision
    cycle lets the next-best legal candidate (e.g. 政工部, which only needs
    "another player exists") actually get submitted instead.
    """
    if rng is None:
        rng = random.Random(config.seed)
    excluded_signatures = excluded_signatures or set()

    scored: list[ScoredCandidate] = []
    for index, action in enumerate(actions):
        score, breakdown, excluded_reason, overrides = score_candidate(action, state, assessment, config)
        effective_action = {**action, **overrides}
        if score is not None and candidate_signature(effective_action) in excluded_signatures:
            score = None
            excluded_reason = "previously_rejected_this_decision_cycle"
            breakdown = {**breakdown, "previously_rejected_this_decision_cycle": True}
        if score is not None and config.noise_scale:
            noise = rng.uniform(-config.noise_scale, config.noise_scale)
            breakdown = {**breakdown, "scoring_noise": noise}
            score = score + noise
        scored.append(
            ScoredCandidate(
                index=index,
                action=action,
                score=score,
                breakdown=breakdown,
                excluded_reason=excluded_reason,
                submit_overrides=overrides,
            )
        )
    _apply_state_security_priority_override(scored, assessment, config)
    return scored


def _apply_state_security_priority_override(
    scored: list[ScoredCandidate], assessment: Assessment, config: PolicyConfig
) -> None:
    """Hard rule from plan section 5 (the real "整局未用國安部" lesson): if
    國安部 is a legal candidate and any opponent's condition_progress is at
    or above the threshold, 國安部 must outrank every other candidate this
    decision point — not merely "score reasonably well among many options".
    Implemented as a post-processing override (rather than an unbounded
    weight) so the override is visible and asserted on directly in the
    decision log instead of being an emergent, hard-to-verify side effect of
    weight tuning.
    """
    if assessment.max_opponent_progress < config.state_security_priority_threshold:
        return
    state_security = next(
        (c for c in scored if c.action.get("kind") == "faction_action" and c.action.get("name") == "國安部"),
        None,
    )
    if state_security is None or state_security.score is None:
        return
    other_scores = [c.score for c in scored if c is not state_security and c.score is not None]
    ceiling = max(other_scores) if other_scores else state_security.score
    if state_security.score <= ceiling:
        state_security.score = ceiling + 1.0
    state_security.breakdown["opponent_block_priority_override"] = True
    state_security.breakdown["override_threshold"] = config.state_security_priority_threshold
    state_security.breakdown["override_reason"] = (
        f"opponent condition_progress={assessment.max_opponent_progress:.3f} "
        f">= threshold={config.state_security_priority_threshold}; 國安部 forced to top rank"
    )


def rank(scored: list[ScoredCandidate]) -> tuple[ScoredCandidate | None, bool]:
    """Pick the winner: highest score, ties broken by lower original index
    (plan section 4.3's deterministic tie-break — never random/dict order).
    Returns (chosen_or_None, tie_breaker_used).
    """
    eligible = [c for c in scored if c.score is not None]
    if not eligible:
        return None, False
    best_score = max(c.score for c in eligible)
    tied = [c for c in eligible if c.score == best_score]
    tied.sort(key=lambda c: c.index)
    return tied[0], len(tied) > 1
