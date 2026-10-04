"""Tunable constants for the programmed Red Army policy.

Everything here is a *policy-layer* number (scoring weights, thresholds,
budgets) — never a game rule. Game rules/legality stay entirely inside
server/game.py and mcp_server/summarize.py; this module never re-derives or
duplicates them (see red_army_policy/__init__.py's module docstring for the
full boundary statement).

RNG / determinism boundary (see plan section 4.3 and the top-level report):
`seed` here seeds ONLY this policy's own tie-break/scoring-noise random
source (an injected `random.Random`, never the global `random` module). The
underlying REDLINE game engine (server/deck.py, server/events.py,
server/game_card_play.py, server/game.py) calls the global `random` module
directly at 10+ call sites with no seed-injection point of its own — that is
unrelated to, and unaffected by, this seed. "Same seed -> same policy
choice" therefore only holds for an *identical sequence of authoritative
game states* fed into the policy; it is not a claim that seeding this value
can replay or reproduce an entire game from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

POLICY_VERSION = "programmed-red-army-v1"

# 紅軍勝利／反共勝利門檊：rules.md「牆內／臺灣城鎮至少14個有效組織」。
TAIWAN_ORG_VICTORY_THRESHOLD = 14
SURVIVAL_TURN_THRESHOLD = 20

# Opponent condition_progress at/above this forces 國安部 to the top of the
# ranking this decision point (plan section 5, "整局未用國安部" lesson).
# 0.5 == 7/14 for a 14-count win condition, matching the plan's own example.
STATE_SECURITY_PRIORITY_THRESHOLD = 0.5


@dataclass(frozen=True)
class ScoringWeights:
    """Linear-combination weights for ScoringEngine (plan section 4.2).

    w6 (瓦解威脅 / exposure risk) and w7 (未來回合價值 / lookahead) are kept at
    0.0 for v1 — the plan explicitly flags both as P1/P2 dimensions with no
    existing server function to read from (unlike condition_progress), so a
    first implementation would be a brand-new, untested heuristic on both
    sides of the scale. Stubbing them at zero weight (rather than omitting
    the dimension entirely) keeps the breakdown shape stable for callers and
    documents exactly where future weight would plug in.
    """

    w1_own_victory_progress: float = 6.0
    w2_block_opponent_progress: float = 10.0
    w3_region_control: float = 1.0
    w4_organization_growth: float = 4.0
    w5_resource_efficiency: float = 2.5
    w6_dissolve_threat: float = 0.0  # stubbed P1 (未新增既有函式可重用，見 plan 第4.1節)
    w7_future_value: float = 0.0  # stubbed P2 (無既有深度搜尋基礎，見 plan 第6節)

    buy_card_diminishing_rate: float = 0.9  # subtracted per card already purchased this turn
    buy_card_base_value: float = 3.0

    faction_action_base: dict = field(
        default_factory=lambda: {
            "統戰部": 1.5,
            "政工部": 2.0,
            "國安部": 2.5,  # before the opponent-progress bonus/override below
            "中紀委": 1.0,
        }
    )


@dataclass(frozen=True)
class PolicyConfig:
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    policy_version: str = POLICY_VERSION
    state_security_priority_threshold: float = STATE_SECURITY_PRIORITY_THRESHOLD
    # Scoring noise for difficulty levels (plan section 7, knob 1) — 0.0 for
    # v1's default (hardest/most "correct") difficulty. Any nonzero value is
    # applied through the injected RNG only, never through `random` globally.
    noise_scale: float = 0.0
    seed: int | None = None
    max_steps: int = 60
    max_retries_per_decision: int = 3
    # Same (state, legal_actions) fingerprint repeating this many times in a
    # row trips the STALE_STATE/RETRY safety net even if retries-per-decision
    # never fires (e.g. a scoring bug that deterministically re-picks an
    # action that keeps getting rejected for a *different* reason each time).
    max_consecutive_same_fingerprint: int = 5
