"""End-to-end smoke test for the top-level entry point
(`red_army_policy.run_red_army_turn`) against a real `Game`, real card/
faction catalogs (the actual in-process data files, not test fakes), and
no monkeypatching — this is the "does the whole wired-together pipeline
actually work" check requirement #11 asks for, complementing the
finer-grained unit/state-machine tests in the other two
test_red_army_policy_*.py files.

Not a full multi-game soak test (the plan's section 9 suggests 20+ full
games across random seeds as a separate, heavier acceptance step) — this
is a bounded, single-call smoke test that the production entry point
with the real catalogs produces a valid, well-formed run without
exceptions or illegal submissions.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.game_models import GamePhase

from red_army_policy import PolicyConfig, run_red_army_turn
from red_army_policy.action_submitter import action_error_message


def _new_real_red_vs_taiwan_game():
    game = Game([('p1', 'red'), ('p2', 'other')])
    red, other = game.players
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    other.faction_id = 'taiwan_green'
    other.base = '臺北'
    other.organizations = {'臺北': 1}
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    return game, red, other


def test_run_red_army_turn_with_real_catalogs_produces_no_illegal_submissions():
    game, red, _other = _new_real_red_vs_taiwan_game()
    config = PolicyConfig(max_steps=20)

    # No faction_catalog/card_catalog override: exercises the real
    # production path (server.faction_presentation.build_faction_presentation(),
    # server.card_presentation.CARD_PRESENTATION_CATALOG).
    result = run_red_army_turn(game, red.id, config=config)

    # "blocked_retry_exhausted" is deliberately NOT in this list. It used to
    # be — and this exact fixture (Red/opponent on non-adjacent bases, an
    # ordinary 2-player board) used to hit it deterministically, with ZERO
    # successful submissions for the entire turn, because 國安部 could be
    # offered with no legal target and the policy kept re-deriving and
    # re-picking the identical doomed candidate (see
    # test_red_army_policy_state_machine.py's
    # test_candidate_rejected_for_lacking_a_target_falls_through_not_stuck
    # for the dedicated regression test). After the fix, exhausting the
    # retry budget on an ordinary board state like this one is itself a
    # regression, not an acceptable terminal status to silently allow.
    assert result.status in {
        "waiting_turn",
        "waiting_other_pending",
        "game_over",
        "blocked_step_budget",
        "blocked_fingerprint_loop",
        "no_legal_actions",
    }
    assert result.steps_taken == len(result.decisions)
    assert result.steps_taken <= config.max_steps

    successful_submissions = [
        d for d in result.decisions if action_error_message(d["submit_result"]) is None
    ]
    assert successful_submissions, (
        "expected at least one successful submission for this ordinary board "
        f"state; decisions={result.decisions}"
    )

    for decision in result.decisions:
        assert "turn" in decision
        assert "decision_point" in decision
        assert decision["policy_version"] == config.policy_version
        assert "chosen" in decision
        assert "chosen_reason" in decision
        assert "submit_result" in decision
        # Every *submitted* action must have been a real, server-rejectable
        # submission attempt, not a silently fabricated success — if the
        # server rejected it, action_error_message must say so (requirement
        # #2: the AI never mutates Game state directly, it always goes
        # through a real action method and checks the real result).
        error = action_error_message(decision["submit_result"])
        if decision["decision_point"] == "action_phase_choice":
            assert isinstance(decision["candidates"], list) and decision["candidates"]
            for candidate in decision["candidates"]:
                assert "action" in candidate and "score" in candidate and "breakdown" in candidate
        # A rejected submission is allowed (the run should recover or stop
        # safely — see test_red_army_policy_state_machine.py) but must never
        # be silently treated as success in the log.
        if error is not None:
            assert decision["submit_result"].get("success") is False or decision["submit_result"].get("error")
