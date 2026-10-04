"""TDD regression scenarios for red_army_policy's ScoringEngine (plan
section 5's "real對弈教訓" table, turned into testable rules).

These are pure unit tests against hand-built `Assessment` objects and
hand-built `legal_actions()`-shaped candidate dicts — they do not need a
live `Game`/server round trip, matching ScoringEngine's own "pure function
over already-projected state" design (plan section 2, stage ③). The
state-machine-level regression scenarios (pending choice resolution,
waiting on a human, stale-command recovery, step-budget loop guard) live in
test_red_army_policy_state_machine.py instead, since those need a real
`Game` object to exercise Game's actual action methods.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from red_army_policy.config import PolicyConfig, ScoringWeights
from red_army_policy.scoring import rank, score_all
from red_army_policy.state_assessor import assess


def _state(*, my_hand_size=2, opponent_progress=0.1, purchased_count=0):
    return {
        "current_player": "Red",
        "purchased_cards_this_turn_count": purchased_count,
        "players": [
            {
                "id": "red",
                "name": "Red",
                "faction": "red_army",
                "resources": {"money": 3, "propaganda": 1},
                "organization_counts": {"total": 2},
                "condition_progress": 0.0,
                "taiwan_organization_count": 0,
                "hand": ["x"] * my_hand_size,
            },
            {
                "id": "opp1",
                "name": "Opp1",
                "faction": "taiwan_green",
                "resources": {"money": 2, "propaganda": 2},
                "organization_counts": {"total": 7},
                "condition_progress": opponent_progress,
                "taiwan_organization_count": 0,
            },
        ],
    }


def _assessment(**kwargs):
    state = _state(**kwargs)
    return assess(state, "red"), state


_BUY_CARD = {"kind": "buy_card", "index": 0, "card_name": "追隨者", "cost": {"money": 1}, "affordable": True}
_ADVANCE_TURN = {"kind": "advance_turn", "why": "end action phase"}
_STATE_SECURITY = {"kind": "faction_action", "name": "國安部", "note": "Server re-validates target/count limits per use."}
_GROWTH_PLAY_CARD = {
    "kind": "play_card",
    "index": 0,
    "card_name": "組織經驗丙",
    "modes": ["resource", "action"],
    "action_effect_text": "於己方組織1格內建立1個組織。",
}
_MOVE_ORG = {"kind": "move_organization", "from_town": "北京", "to_town": "天津", "mode": "road", "cost": 1}


def test_legal_printed_action_outranks_maximum_generic_purchase_score():
    assessment, state = _assessment(my_hand_size=0, opponent_progress=0.1)
    action_card = {
        "kind": "play_card",
        "index": 0,
        "card_name": "企畫遊說",
        "modes": ["resource", "action"],
        "action_effect_text": "展示牌庫頂牌並執行效果。",
    }

    scored = score_all([_BUY_CARD, action_card, _ADVANCE_TURN], state, assessment, PolicyConfig())
    chosen, _ = rank(scored)

    assert chosen.action["kind"] == "play_card"
    assert chosen.action["card_name"] == "企畫遊說"
    assert chosen.submit_overrides["mode"] == "action"


# ---------- 1. 國安部 must not be crowded out by a low-value buy_card ----------

def test_state_security_outranks_low_value_buy_card_when_opponent_progress_high():
    assessment, state = _assessment(my_hand_size=2, opponent_progress=0.6)
    actions = [_BUY_CARD, _STATE_SECURITY, _ADVANCE_TURN]
    config = PolicyConfig()

    scored = score_all(actions, state, assessment, config)
    chosen, _tie = rank(scored)

    assert chosen.action["kind"] == "faction_action"
    assert chosen.action["name"] == "國安部"
    assert chosen.breakdown.get("opponent_block_priority_override") is True


def test_state_security_override_only_triggers_above_threshold():
    # Below threshold: the override must NOT fire, so a decent buy_card can
    # legitimately outrank 國安部's modest base score.
    assessment, state = _assessment(my_hand_size=0, opponent_progress=0.1)
    actions = [_BUY_CARD, _STATE_SECURITY, _ADVANCE_TURN]
    config = PolicyConfig()

    scored = score_all(actions, state, assessment, config)
    state_security_entry = next(c for c in scored if c.action.get("name") == "國安部")
    assert "opponent_block_priority_override" not in state_security_entry.breakdown


# ---------- 2. Not a fixed if/else script: choice tracks the board state ----------

def test_opponent_progress_driven_choice_differs_from_ordinary_state():
    # Covers the "stop the opponent instead of following a fixed sequence"
    # half of the lesson specifically: 國安部 absent/available is itself the
    # varying axis here, with the opponent-progress override as the
    # mechanism — see test_state_security_outranks_low_value_buy_card_*
    # and test_state_security_override_only_triggers_above_threshold above
    # for the override's own dedicated coverage.
    config = PolicyConfig()

    assessment_a, state_a = _assessment(my_hand_size=1, opponent_progress=0.1)
    actions_a = [_BUY_CARD, _ADVANCE_TURN]
    scored_a = score_all(actions_a, state_a, assessment_a, config)
    chosen_a, _ = rank(scored_a)

    assessment_b, state_b = _assessment(my_hand_size=1, opponent_progress=0.6)
    actions_b = [_BUY_CARD, _STATE_SECURITY, _ADVANCE_TURN]
    scored_b = score_all(actions_b, state_b, assessment_b, config)
    chosen_b, _ = rank(scored_b)

    assert chosen_a.action["kind"] == "buy_card"
    assert chosen_b.action["kind"] == "faction_action"
    assert chosen_a.action["kind"] != chosen_b.action["kind"]


def test_ranking_itself_tracks_organization_distribution_not_just_the_override():
    """Stronger evidence against "fixed priority chain" than the override
    test above: 國安部 is absent in BOTH states (never a factor here), and
    opponent_progress is identical and low in both (0.1 — nowhere near the
    override threshold), and hand_size is identical in both too (so this
    is not a re-run of the hand-size-driven buy_card ceiling tests below).
    The only thing that differs between A and B is the board's
    organization distribution — whether a cheap, high-value
    move_organization opportunity exists — and the plain weighted scoring
    (not any hardcoded priority rule) must be what picks it up. A
    hardcoded chain like "if opponent_progress>=0.5 and 國安部 legal: pick
    it, elif buy_card legal: pick it" would pick buy_card in BOTH states
    below, since neither condition it checks differs between them —
    failing this test.
    """
    config = PolicyConfig()

    # State A: several purchases this turn have pushed buying past its ceiling,
    # and there is no organizational-move opportunity on the board.
    assessment_a, state_a = _assessment(
        my_hand_size=4,
        opponent_progress=0.1,
        purchased_count=4,
    )
    actions_a = [_BUY_CARD, _ADVANCE_TURN]
    scored_a = score_all(actions_a, state_a, assessment_a, config)
    chosen_a, _ = rank(scored_a)

    # State B: identical hand size and opponent progress — but the board
    # now offers a cheap move_organization (the "organization distribution"
    # axis): red has a one-step, low-cost expansion available.
    assessment_b, state_b = _assessment(
        my_hand_size=4,
        opponent_progress=0.1,
        purchased_count=4,
    )
    actions_b = [_BUY_CARD, _MOVE_ORG, _ADVANCE_TURN]
    scored_b = score_all(actions_b, state_b, assessment_b, config)
    chosen_b, _ = rank(scored_b)

    assert chosen_a.action["kind"] == "advance_turn"
    assert chosen_b.action["kind"] == "move_organization"
    assert chosen_a.action["kind"] != chosen_b.action["kind"]


# ---------- 3. Card-buying diminishes after each purchase, not after spending hand cards ----------

def test_spending_hand_as_resource_does_not_increase_buy_score():
    full_hand, full_state = _assessment(my_hand_size=8, opponent_progress=0.1, purchased_count=1)
    empty_hand, empty_state = _assessment(my_hand_size=0, opponent_progress=0.1, purchased_count=1)
    config = PolicyConfig()

    full_score = score_all([_BUY_CARD], full_state, full_hand, config)[0]
    empty_score = score_all([_BUY_CARD], empty_state, empty_hand, config)[0]

    assert full_score.score == empty_score.score
    assert full_score.breakdown["purchased_cards_this_turn_count"] == 1


def test_each_purchase_reduces_next_purchase_score():
    config = PolicyConfig()

    scores = []
    for purchased_count in (0, 1, 2):
        assessment, state = _assessment(
            my_hand_size=1,
            opponent_progress=0.1,
            purchased_count=purchased_count,
        )
        scores.append(score_all([_BUY_CARD], state, assessment, config)[0].score)

    assert scores[0] > scores[1] > scores[2]


# ---------- 4. Own organization growth scores positively and can be chosen ----------

def test_organization_growth_play_card_scores_positively_and_is_chosen():
    assessment, state = _assessment(my_hand_size=2, opponent_progress=0.1)
    actions = [_GROWTH_PLAY_CARD, _BUY_CARD, _MOVE_ORG, _ADVANCE_TURN]
    config = PolicyConfig()

    scored = score_all(actions, state, assessment, config)
    growth_entry = next(c for c in scored if c.action["kind"] == "play_card")
    chosen, _tie = rank(scored)

    assert growth_entry.breakdown["organization_growth"] > 0
    assert chosen.action["kind"] == "play_card"
    assert chosen.submit_overrides.get("mode") == "action"


# ---------- 5. Determinism: same state + seed + policy version -> same choice ----------

def test_same_state_same_seed_same_policy_version_is_deterministic():
    assessment, state = _assessment(my_hand_size=3, opponent_progress=0.4)
    actions = [_BUY_CARD, _STATE_SECURITY, _GROWTH_PLAY_CARD, _MOVE_ORG, _ADVANCE_TURN]
    config = PolicyConfig(weights=ScoringWeights(), noise_scale=0.3, seed=20261002)

    scored_1 = score_all(list(actions), state, assessment, config)
    chosen_1, tie_1 = rank(scored_1)
    scored_2 = score_all(list(actions), state, assessment, config)
    chosen_2, tie_2 = rank(scored_2)

    assert [c.score for c in scored_1] == [c.score for c in scored_2]
    assert chosen_1.action == chosen_2.action
    assert tie_1 == tie_2
    assert config.policy_version == "programmed-red-army-v1"


def test_tie_break_is_by_lowest_candidate_index_not_random():
    assessment, state = _assessment(my_hand_size=1, opponent_progress=0.1)
    # Two advance_turn-equivalent (score 0.0) candidates; index 0 must win.
    actions = [dict(_ADVANCE_TURN), dict(_ADVANCE_TURN)]
    config = PolicyConfig()

    scored = score_all(actions, state, assessment, config)
    chosen, tie_breaker_used = rank(scored)

    assert tie_breaker_used is True
    assert chosen.index == 0
