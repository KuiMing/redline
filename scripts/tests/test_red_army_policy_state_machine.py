"""State-machine-level regression scenarios for red_army_policy, against
real `Game` instances (same fixture style as
scripts/tests/test_game_red_army_action_triggers.py) and a tiny frozen fake
`Game` double for the loop-guard scenario that needs a state that provably
never progresses.

Covers the remaining required regression scenarios not already exercised
by test_red_army_policy_scoring.py's pure ScoringEngine unit tests:
- a required pending choice gets resolved for Red Army
- a pending choice belonging to another player blocks and waits (never
  resolved on the human's behalf)
- a rejected/stale submission triggers fresh re-decisioning, not a blind
  retry of the same payload, with a safe stop if re-decisioning also fails
- a candidate that `legal_actions()` lists purely on dispatchability but
  that the server rejects for having no actual target (e.g. 國安部 with no
  opponent organization in range) does not stall the whole turn — the
  policy falls through to the next-best legal candidate instead of
  re-deriving and re-picking the identical doomed candidate forever
  (Critical bug found by independent review on 2026-10-02; see
  red_army_policy/policy.py's `run_red_army_turn` docstring and
  red_army_policy/scoring.py's `candidate_signature`/`excluded_signatures`)
- an infinite loop is blocked by the step/fingerprint budget
- TargetSelector finds a target by matching a field (player_id/progress),
  never by manually counting list positions
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import copy

from server.game import Game
from server.game_models import GamePhase

from red_army_policy import action_submitter
from red_army_policy.config import PolicyConfig
from red_army_policy.policy import run_red_army_turn, step
from red_army_policy.state_assessor import assess
from red_army_policy.target_selector import select_pending_choice_submission

# Empty catalogs keep these tests independent of the real data files/CSVs —
# CandidateGenerator still calls the real mcp_server.summarize.legal_actions(),
# just with no faction abilities/card effect text to offer, so the only
# candidate a stripped-down fixture offers is advance_turn.
_EMPTY_FACTION_CATALOG: dict = {"categories": []}
_EMPTY_CARD_CATALOG: dict = {}


def _new_red_vs_taiwan_game():
    game = Game([('p1', 'red'), ('p2', 'other')])
    red, other = game.players
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    other.faction_id = 'taiwan_green'
    other.base = '臺北'
    other.organizations = {'天津': 1}
    # The fixture's random initial faction/base assignment (overwritten
    # above) can leave the game in GamePhase.BASE_SELECTION depending on
    # what it randomly assigned before the override — force MAIN/ACTION
    # deterministically rather than depending on that draw.
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    # Turn 1's event draw can rarely (~1% over many runs, observed directly)
    # grant the first player a free immediate build-organization choice
    # (e.g. 一帶一路) before this fixture ever gets a chance to run — that's
    # real, correct game behavior, just irrelevant variance for tests that
    # are specifically about action-phase candidate ranking/retry, not
    # event-phase pending choices. Clear it so these tests start from a
    # deterministic, pending-choice-free action phase.
    game.pending_choice = None
    return game, red, other


# ---------- required pending choice gets resolved for Red Army ----------

def test_required_pending_choice_for_red_army_gets_resolved():
    game, red, other = _new_red_vs_taiwan_game()
    opened = game._activated_faction_action(red, '國安部')
    assert opened.get('pending_choice') is True
    assert game.pending_choice['choice_key'] == 'red_army_state_security_target'
    assert game.pending_choice['player_id'] == red.id

    result = step(game, red.id)

    assert result.status == "decision_made"
    assert result.decision["decision_point"] == "pending_choice_resolution"
    assert game.pending_choice is None
    assert other.organizations.get('天津', 0) == 0  # dissolved


# ---------- a pending choice belonging to another player blocks and waits ----------

def test_pending_choice_for_another_player_blocks_and_is_never_resolved_for_them():
    game, red, other = _new_red_vs_taiwan_game()
    game._set_pending_town_choice(
        other, 'test_choice_key', [{'town': '臺北'}], 'test prompt', source_name='test',
    )
    assert game.pending_choice['player_id'] == other.id

    result = step(game, red.id)

    assert result.status == "waiting_other_pending"
    # Never resolved on the human's behalf.
    assert game.pending_choice is not None
    assert game.pending_choice['player_id'] == other.id


# ---------- rejected/stale submission: fresh re-decisioning, not a blind retry ----------

def test_rejected_submission_recovers_via_fresh_redecision_within_retry_budget(monkeypatch):
    # Deliberately NOT stripped down to a single candidate here: a real
    # fresh game's hand (5 cards) + purchase area gives several distinct
    # legal candidates, so a rejection of whichever one scores best must
    # make the policy fall through to a *different* one on the very next
    # attempt (candidate_signature()-based exclusion — see policy.py),
    # rather than there being nowhere else to fall through to.
    game, red, _other = _new_red_vs_taiwan_game()

    real_submit = action_submitter.submit
    calls: list[dict] = []

    def flaky_submit(g, player_id, action):
        calls.append(dict(action))
        if len(calls) == 1:
            # Simulate the documented false-positive-legality class of bug
            # (summarize.py's use_topdeck_right case): the candidate looked
            # legal, the server rejects it anyway.
            return {"error": "Simulated transient server rejection"}
        return real_submit(g, player_id, action)

    monkeypatch.setattr("red_army_policy.policy.action_submitter.submit", flaky_submit)

    # max_steps is generous on purpose: once the second (real) submission
    # succeeds, run_red_army_turn correctly keeps driving the rest of the
    # turn forward (more cards/buys) rather than stopping after one
    # decision — this test only cares about the first two attempts.
    config = PolicyConfig(max_steps=20, max_retries_per_decision=3)
    result = run_red_army_turn(game, red.id, config=config, faction_catalog=_EMPTY_FACTION_CATALOG, card_catalog=_EMPTY_CARD_CATALOG)

    assert len(calls) >= 2
    assert len(result.decisions) >= 2
    assert action_submitter.action_error_message(result.decisions[0]["submit_result"]) == "Simulated transient server rejection"
    assert action_submitter.action_error_message(result.decisions[1]["submit_result"]) is None
    # The second attempt was a genuinely different candidate, not a retry
    # of the exact same rejected one.
    assert result.decisions[0]["chosen"] != result.decisions[1]["chosen"]
    # Never blindly looped forever on the same rejected command.
    assert result.status != "blocked_retry_exhausted"


def test_persistently_rejected_submission_stops_safely_at_retry_budget(monkeypatch):
    # Same non-stripped fixture as above: there are more legal candidates
    # than `max_retries_per_decision`, so when EVERY submission is
    # rejected, the retry-budget guard (not candidate exhaustion) is what
    # trips first — proving the two safety nets are independent.
    game, red, _other = _new_red_vs_taiwan_game()
    assert len(red.hand) >= 4  # sanity: comfortably more candidates than the retry budget below

    def always_rejects(g, player_id, action):
        return {"error": "Always rejected (simulated)"}

    monkeypatch.setattr("red_army_policy.policy.action_submitter.submit", always_rejects)

    config = PolicyConfig(max_steps=10, max_retries_per_decision=3)
    result = run_red_army_turn(game, red.id, config=config, faction_catalog=_EMPTY_FACTION_CATALOG, card_catalog=_EMPTY_CARD_CATALOG)

    assert result.status == "blocked_retry_exhausted"
    assert len(result.decisions) == 3
    assert result.steps_taken == 3
    # Three distinct candidates were tried (not the same one three times).
    attempted_kinds_and_indices = {
        (d["chosen"].get("kind"), d["chosen"].get("index"), d["chosen"].get("name")) for d in result.decisions
    }
    assert len(attempted_kinds_and_indices) == 3


# ---------- Critical: a candidate with no actual target must not stall the whole turn ----------

def test_candidate_rejected_for_lacking_a_target_falls_through_not_stuck():
    """Independent-review repro (2026-10-02): legal_actions() lists 國安部
    as a candidate purely because it is dispatchable this turn
    (mcp_server/summarize.py's own comment: "Server re-validates
    target/count limits per use.") — NOT because it actually has a legal
    dissolve target. Red based in 北京, opponent based in 臺北 (outside the
    "china" region alias entirely, so 國安部 has zero legal targets by
    construction, matching test_red_army_policy_entry_point.py's own
    fixture) used to make run_red_army_turn return
    status=blocked_retry_exhausted with all 3 attempts rejected and ZERO
    successful submissions for the entire turn, deterministically and
    repeatably. After the fix, 國安部's rejection must be excluded and the
    policy must fall through to a different legal candidate (e.g. 政工部)
    and make real forward progress this turn.

    Hand/purchase_area are stripped so this is deterministic regardless of
    the random deck shuffle: with a real (opponent condition_progress==0,
    i.e. the override is NOT what's making 國安部 attractive here) fresh
    game, a hand card with a strong growth/dissolve effect_text can
    legitimately outscore 國安部's flat base weight, which would make
    *which* candidate fails first a function of the random deal rather
    than the bug this test exists to pin down. Real faction/card catalogs
    are still used (no faction_catalog/card_catalog override) — this must
    hold against the actual production ability list, not a stripped-down
    fake.
    """
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
    red.hand = []
    red.moves_left = 0
    game.purchase_area = []
    # See _new_red_vs_taiwan_game()'s comment: a rare turn-1 event-granted
    # free build choice is irrelevant real-game variance for this test.
    game.pending_choice = None

    config = PolicyConfig(max_steps=10, max_retries_per_decision=3)
    result = run_red_army_turn(game, red.id, config=config)

    assert result.status != "blocked_retry_exhausted"
    successful = [d for d in result.decisions if action_submitter.action_error_message(d["submit_result"]) is None]
    assert successful, f"expected at least one successful submission this turn; decisions={result.decisions}"
    # The first attempt (國安部, the highest-scoring candidate with no
    # target) must actually have been rejected — otherwise this isn't
    # exercising the bug at all.
    first_attempt = result.decisions[0]
    assert first_attempt["chosen"].get("kind") == "faction_action"
    assert first_attempt["chosen"].get("name") == "國安部"
    assert action_submitter.action_error_message(first_attempt["submit_result"]) is not None


# ---------- infinite loop is blocked by the step/fingerprint budget ----------

class _FrozenGame:
    """A game double whose state never changes no matter what gets
    submitted — simulating a scoring/state bug that would otherwise loop
    forever re-deciding the same actionable state. Proves run_red_army_turn
    terminates safely rather than hanging."""

    def __init__(self):
        self._state = {
            "game_phase": "main",
            "turn_phase": "action",
            "current_player": "Red",
            "pending_choice": None,
            "hk_free_base_relocation": False,
            "players": [
                {
                    "id": "red",
                    "name": "Red",
                    "faction": "red_army",
                    "hand": [],
                    "hand_action_legality": [],
                    "resources": {"money": 0, "propaganda": 0},
                    "organization_counts": {"total": 0},
                    "condition_progress": 0.0,
                    "taiwan_organization_count": 0,
                }
            ],
            "map": {"legal_organization_moves": {}},
            "purchase_area": [],
            "purchase_area_affordable": [],
            "purchase_area_costs": [],
            "red_army_action_limit": 0,
            "red_army_action_count": 0,
            "pending_topdeck_uses": 0,
            "turn": 1,
        }
        self.advance_calls = 0

    def state(self, player_id=None):
        return copy.deepcopy(self._state)

    def advance_turn_phase(self):
        self.advance_calls += 1
        # Deliberately never changes self._state: simulates the exact
        # failure mode the loop guard exists for.
        return {"success": True}


def test_infinite_loop_is_blocked_by_the_step_and_fingerprint_budget():
    fake_game = _FrozenGame()
    config = PolicyConfig(max_steps=6, max_consecutive_same_fingerprint=2)

    result = run_red_army_turn(
        fake_game, "red", config=config, faction_catalog=_EMPTY_FACTION_CATALOG, card_catalog=_EMPTY_CARD_CATALOG
    )

    assert result.status in {"blocked_fingerprint_loop", "blocked_step_budget"}
    assert result.steps_taken <= config.max_steps
    assert fake_game.advance_calls <= config.max_steps


# ---------- TargetSelector finds a target by matching a field, not counting ----------

def test_target_selector_finds_target_by_progress_not_list_position():
    state = {
        "current_player": "Red",
        "players": [
            {"id": "red", "name": "Red", "faction": "red_army", "condition_progress": 0.0, "taiwan_organization_count": 0, "organization_counts": {"total": 1}, "resources": {}},
            {"id": "low", "name": "Low", "faction": "x", "condition_progress": 0.1, "taiwan_organization_count": 0, "organization_counts": {"total": 1}, "resources": {}},
            {"id": "high", "name": "High", "faction": "y", "condition_progress": 0.7, "taiwan_organization_count": 0, "organization_counts": {"total": 1}, "resources": {}},
        ],
    }
    assessment = assess(state, "red")
    pending = {
        "type": "target_choice",
        "targets": [
            {"id": "low::A", "player_id": "low", "town": "A"},
            {"id": "high::B", "player_id": "high", "town": "B"},
        ],
    }

    submission = select_pending_choice_submission(pending, assessment)

    # The higher-progress opponent is at list position 1, not 0 — picking it
    # correctly proves the lookup matched on player_id/progress rather than
    # defaulting to (or miscounting into) the first entry.
    assert submission["index"] == 1
