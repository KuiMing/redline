"""Programmed (deterministic, rule/scoring-based) Red Army AI.

This package is the production decision path for an AI Red Army seat. It
does **not** depend on an LLM, MCP, Hermes, Claude, Docker, or any external
API/process — every call in its pipeline is a plain in-process Python
function/method call into `server/game.py` (the authoritative `Game`
object's own existing action methods) and `mcp_server/summarize.py` (the
existing, already-correct legal-action enumerator). The sibling package
`red_army_controller/` (MCP + Hermes/LLM) is untouched by this work and
stays available only as a separate, optional dev-time comparison tool —
nothing in this package imports from it, and nothing in it imports from
this package.

Pipeline (see the plan this was built from, section 2/3), each stage its
own module:

    state_assessor.assess()            — ① read Game.state(), no legality
    candidate_generator.generate_candidates()
                                        — ② wraps mcp_server.summarize.legal_actions()
    scoring.score_all() / rank()       — ③ the one genuinely new logic: weighted
                                          utility scoring over the candidates ② produced
    target_selector.select_*()         — ④ pick among already-legal targets/indices
    policy._resolve_pending_choice_step()
                                        — ⑤ pending_choice / reaction-window branch
    action_submitter.submit()          — ⑥ calls Game's existing action methods,
                                          never mutates Game state directly

`policy.run_red_army_turn(game, player_id)` is the top-level entry point
(requirement #11): drives the pipeline forward until control must return to
a human, the AI is blocked on another player's pending choice/reaction, the
game ends, or a safety budget trips. `policy.step(...)` performs exactly
one decision for callers (including tests) that want finer-grained control.

RNG / determinism boundary — read this before assuming "seeded" means
"fully reproducible": see config.py's module docstring and
`PolicyConfig.seed`'s doc comment for the exact, precise statement. Short
version: this package's own tie-break/scoring-noise seed is injectable and
deterministic; the underlying REDLINE game engine's `random` usage
(card shuffling, event draws, etc. in server/deck.py, server/events.py,
server/game_card_play.py, server/game.py) is not seeded by anything in this
package and was explicitly out of scope for this version (see the plan's
section 4.3 and the top-level implementation report for why).
"""

from __future__ import annotations

from red_army_policy.config import POLICY_VERSION, PolicyConfig, ScoringWeights
from red_army_policy.policy import RunResult, StepResult, run_red_army_turn, step

__all__ = [
    "POLICY_VERSION",
    "PolicyConfig",
    "ScoringWeights",
    "RunResult",
    "StepResult",
    "run_red_army_turn",
    "step",
]
