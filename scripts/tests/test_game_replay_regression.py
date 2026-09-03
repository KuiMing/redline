"""Differential replay regression test.

Re-runs the deterministic 2p scenario and diffs the full multi-viewer state
sequence against a committed baseline. Function-level characterization
tests can miss interaction bugs across a pending_choice / reaction /
turn-handoff sequence; this catches divergence anywhere in that sequence,
for every player's view, not just one function's return value.

To intentionally update the baseline after a real behavior change (should be
rare and deliberate, never to silence a refactor regression): regenerate
scripts/tests/fixtures/game_replay_2p_baseline.json using
game_replay_harness.run_scenario(scenario, seed=20260510) and review the
diff to the old baseline before committing it.
"""

import json
from pathlib import Path

from game_replay_harness import run_scenario, diff_steps
from game_replay_scenario_2p import scenario

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'game_replay_2p_baseline.json'


def test_2p_scenario_matches_baseline():
    baseline = json.loads(FIXTURE.read_text(encoding='utf-8'))
    current = run_scenario(scenario, seed=20260510)
    diff = diff_steps(baseline, current)
    assert diff is None, diff
