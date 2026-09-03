"""Differential replay regression tests.

Re-runs a deterministic scenario and diffs the full multi-viewer state
sequence against a committed baseline. Function-level characterization
tests can miss interaction bugs across a pending_choice / reaction /
turn-handoff sequence; this catches divergence anywhere in that sequence,
for every player's view, not just one function's return value.

Two scenarios, each targeting different code:
- game_replay_scenario_2p.py: a general 2-player playthrough (base
  selection, event choices, purchases, movement, organization building).
- game_replay_scenario_faction_abilities.py: a 4-player scenario built
  specifically to exercise `_apply_card_play_faction_abilities` /
  `_apply_turn_end_faction_abilities`'s named-ability branches ahead of
  extracting them (game.py refactor item 21) — the 2p scenario's factions
  don't hold any of those abilities.

To intentionally update a baseline after a real behavior change (should be
rare and deliberate, never to silence a refactor regression): regenerate
the relevant fixtures/*.json using
game_replay_harness.run_scenario(scenario, seed=...) (see each scenario
module for its seed) and review the diff to the old baseline before
committing it.
"""

import json
from pathlib import Path

from game_replay_harness import run_scenario, diff_steps
from game_replay_scenario_2p import scenario as scenario_2p
from game_replay_scenario_faction_abilities import scenario as scenario_faction_abilities
from game_replay_scenario_red_army_actions import scenario as scenario_red_army_actions

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def test_2p_scenario_matches_baseline():
    baseline = json.loads((FIXTURES / 'game_replay_2p_baseline.json').read_text(encoding='utf-8'))
    current = run_scenario(scenario_2p, seed=20260510)
    diff = diff_steps(baseline, current)
    assert diff is None, diff


def test_faction_abilities_scenario_matches_baseline():
    baseline = json.loads((FIXTURES / 'game_replay_faction_abilities_baseline.json').read_text(encoding='utf-8'))
    current = run_scenario(scenario_faction_abilities, seed=99001)
    diff = diff_steps(baseline, current)
    assert diff is None, diff


def test_red_army_actions_scenario_matches_baseline():
    baseline = json.loads((FIXTURES / 'game_replay_red_army_actions_baseline.json').read_text(encoding='utf-8'))
    current = run_scenario(scenario_red_army_actions, seed=55001)
    diff = diff_steps(baseline, current)
    assert diff is None, diff
