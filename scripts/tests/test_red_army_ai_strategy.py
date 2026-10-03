"""Regression tests for the programmed Red Army's organization-disruption
strategy, its 印度奧援 purchase exclusion, and the Taiwan/Red Army special
victory copy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.summarize import legal_actions
from red_army_policy.catalogs import default_card_catalog, default_faction_catalog
from red_army_policy.config import PolicyConfig
from red_army_policy.scoring import rank, score_all
from red_army_policy.state_assessor import assess
from red_army_policy.target_selector import select_pending_choice_submission
from server.faction_presentation import build_faction_presentation
from server.game import Game
from server.game_models import GamePhase

RED_VICTORY_TEXT = "若有玩家為台灣陣營，紅軍於回合結束時在臺灣城鎮擁有至少14個有效組織，則紅軍直接獲勝。"


def _player(pid, faction, progress=0.0, total=0, orgs=None):
    return {
        "id": pid,
        "name": pid.upper(),
        "faction": faction,
        "resources": {"money": 3, "propaganda": 1},
        "organization_counts": {"total": total},
        "condition_progress": progress,
        "taiwan_organization_count": 0,
        "orgs": orgs or {},
        "hand": [],
    }


def _state(opponents):
    return {
        "current_player": "RED",
        "purchased_cards_this_turn_count": 0,
        "players": [_player("red", "red_army", total=2)] + opponents,
    }


def _score(actions, opponents):
    state = _state(opponents)
    return score_all(actions, state, assess(state, "red"), PolicyConfig())


BUY = {"kind": "buy_card", "index": 0, "card_name": "追隨者", "cost": {"money": 1}, "affordable": True}
INDIA = {"kind": "buy_card", "index": 1, "card_name": "印度奧援", "cost": {"money": 1}, "affordable": True}
END = {"kind": "advance_turn"}
GROWTH = {
    "kind": "play_card", "index": 0, "card_name": "組織經驗丙",
    "modes": ["resource", "action"], "action_effect_text": "於己方組織1格內建立1個組織。",
}
SPY = {
    "kind": "play_card", "index": 1, "card_name": "派遣間諜",
    "modes": ["resource", "action"], "action_effect_text": "瓦解1個組織。",
}


def _security(targets=None):
    entry = {"kind": "faction_action", "name": "國安部"}
    if targets is not None:
        entry["dissolve_targets"] = targets
    return entry


# ---------- 1. 印度奧援 ----------

def test_policy_never_buys_india_support_even_when_cheap_and_affordable():
    scored = _score([INDIA, END], [_player("o", "taiwan_green")])
    india = scored[0]
    assert india.score is None
    assert india.excluded_reason == "red_army_never_buys_india_support"
    chosen, _ = rank(scored)
    assert chosen.action["kind"] == "advance_turn"


def test_india_exclusion_leaves_other_purchases_alone():
    scored = _score([INDIA, BUY], [_player("o", "taiwan_green")])
    chosen, _ = rank(scored)
    assert chosen.action["card_name"] == "追隨者"


def test_server_still_offers_india_support_as_a_generic_legal_buy():
    state = {
        "current_player": "RED", "turn_phase": "action", "game_phase": "main",
        "purchase_area": ["印度奧援"], "purchase_area_affordable": [True], "purchase_area_costs": [{"money": 1}],
        "players": [_player("red", "red_army")],
    }
    state["players"][0]["name"] = "RED"
    legal = legal_actions(state, "red", default_faction_catalog(), default_card_catalog())
    assert any(a.get("card_name") == "印度奧援" for a in legal["actions"] if a["kind"] == "buy_card")


# ---------- 2. disruption strategy ----------

def test_state_security_with_real_target_outranks_growth_and_purchase_at_low_progress():
    target = {"player_id": "o", "town": "天津"}
    scored = _score([BUY, GROWTH, _security([target]), END], [_player("o", "taiwan_green", 0.1, 3, {"天津": 1})])
    chosen, _ = rank(scored)
    assert chosen.action["name"] == "國安部"
    assert "threat" in chosen.breakdown


def test_state_security_without_any_dissolve_target_is_not_chosen():
    scored = _score([BUY, _security([]), END], [_player("o", "taiwan_green", 0.9, 3)])
    sec = scored[1]
    assert sec.score is None and sec.excluded_reason == "no_legal_dissolve_target"
    assert rank(scored)[0].action["kind"] == "buy_card"


def test_dissolve_card_outranks_growth_when_opponent_has_organizations():
    scored = _score([GROWTH, SPY, END], [_player("o", "taiwan_green", 0.2, 4, {"天津": 1})])
    assert rank(scored)[0].action["card_name"] == "派遣間諜"


def test_dissolve_card_does_not_beat_growth_when_nobody_has_organizations():
    scored = _score([GROWTH, SPY, END], [_player("o", "taiwan_green", 0.0, 0)])
    assert rank(scored)[0].action["card_name"] == "組織經驗丙"


def test_threat_scoring_prefers_opponent_closest_to_victory_then_largest_footprint():
    opponents = [
        _player("a", "taiwan_green", 0.3, 9, {"天津": 1}),
        _player("b", "liberals", 0.8, 11, {"上海": 1}),
    ]
    state = _state(opponents)
    pending = {"type": "target_choice", "targets": [
        {"player_id": "a", "town": "天津"}, {"player_id": "b", "town": "上海"}]}
    assert select_pending_choice_submission(pending, assess(state, "red"))["index"] == 1
    tie = _state([_player("a", "x", 0.5, 4, {"天津": 1}), _player("b", "y", 0.5, 8, {"上海": 1})])
    assert select_pending_choice_submission(pending, assess(tie, "red"))["index"] == 1


def test_threat_is_lexicographic_progress_beats_organization_count():
    opponents = [
        _player("a", "taiwan_green", 0.49, 2, {"天津": 1}),
        _player("b", "liberals", 0.50, 0, {"上海": 1}),
    ]
    state = _state(opponents)
    pending = {"type": "target_choice", "targets": [
        {"player_id": "a", "town": "天津"}, {"player_id": "b", "town": "上海"}]}
    assert select_pending_choice_submission(pending, assess(state, "red"))["index"] == 1
    targets = [{"player_id": "a", "town": "天津"}, {"player_id": "b", "town": "上海"}]
    chosen = rank(_score([_security(targets)], opponents))[0]
    assert chosen.breakdown["threat_target_player_id"] == "b"
    assert chosen.breakdown["threat"] == 0.50


def test_threat_exact_tie_uses_organizations_then_first_candidate():
    pending = {"type": "target_choice", "targets": [
        {"player_id": "a", "town": "天津"}, {"player_id": "b", "town": "上海"}]}
    same = _state([_player("a", "x", 0.5, 4, {"天津": 1}), _player("b", "y", 0.5, 4, {"上海": 1})])
    assert select_pending_choice_submission(pending, assess(same, "red"))["index"] == 0


def test_stale_replanning_uses_fresh_state_after_exclusion():
    target = {"player_id": "o", "town": "天津"}
    opponents = [_player("o", "taiwan_green", 0.6, 3, {"天津": 1})]
    state = _state(opponents)
    actions = [BUY, _security([target]), END]
    first = rank(score_all(actions, state, assess(state, "red"), PolicyConfig()))[0]
    assert first.action["name"] == "國安部"
    # server rejected it; then the authoritative state shows no target left
    actions2 = [BUY, _security([]), END]
    second = rank(score_all(actions2, state, assess(state, "red"), PolicyConfig(),
                            excluded_signatures={("faction_action", "國安部", None)}))[0]
    assert second.action["kind"] == "buy_card"


def _game():
    g = Game([("p1", "red"), ("p2", "other")])
    red, other = g.players
    red.faction_id, red.base, red.organizations = "red_army", "北京", {"北京": 1}
    other.faction_id, other.base, other.organizations = "taiwan_green", "臺北", {"天津": 1}
    g.game_phase = GamePhase.MAIN
    g.pending_base_choices = {}
    g.pending_choice = None
    g.current_player_index = 0
    return g, red


def test_server_state_exposes_viewer_safe_state_security_targets_for_red_only():
    g, red = _game()
    st = g.state(viewer_player_id=red.id)
    assert {"player_id": g.players[1].id, "town": "天津"}.items() <= st["red_army_state_security_targets"][0].items()
    assert "red_army_state_security_targets" not in g.state(viewer_player_id=g.players[1].id)
    entry = next(a for a in legal_actions(st, red.id, default_faction_catalog(), default_card_catalog())["actions"]
                 if a.get("name") == "國安部")
    assert entry["dissolve_targets"] == [{"player_id": g.players[1].id, "town": "天津"}]
    assert "hand" not in json.dumps(entry)


# ---------- 3. copy ----------

def _options():
    cats = {c["id"]: c for c in build_faction_presentation()["categories"]}
    return cats["red_army"]["options"][0], {o["id"]: o for o in cats["taiwan"]["options"]}


def test_red_army_win_condition_text_is_exact():
    red, _ = _options()
    texts = [w.get("text") for w in red["win_conditions"]]
    assert RED_VICTORY_TEXT in texts


def test_taiwan_green_and_blue_show_red_special_victory():
    _, tw = _options()
    for fid in ("taiwan_green", "taiwan_blue"):
        assert RED_VICTORY_TEXT in tw[fid]["special_rules"]


def test_all_faction_data_files_use_exact_copy_and_no_stale_wording():
    for path in (ROOT / "data" / "factions").glob("*.json"):
        assert "若有玩家選用臺灣，紅軍於回合結束時" not in path.read_text(encoding="utf-8"), path.name
    for name in ("red_army.v1.1.json", "taiwan_green.v1.1.json", "taiwan_blue.v1.1.json",
                 "all_faction.json", "all_faction.integrated.v2.json"):
        assert RED_VICTORY_TEXT in (ROOT / "data" / "factions" / name).read_text(encoding="utf-8")


def test_red_taiwan_victory_requires_taiwan_player_at_runtime():
    g, red = _game()
    taiwan_towns = sorted(g.victory_engine._towns_for_ruler(g, "臺灣"))[:14]
    assert len(taiwan_towns) == 14
    red.organizations = {t: 1 for t in taiwan_towns}
    g.players[1].faction_id = "taiwan_blue"
    assert g.victory_engine._check_player_conditions(red, g) == (True, "red_army")
    g.players[1].faction_id = "liberals"
    assert g.victory_engine._check_player_conditions(red, g)[0] is False
    g.players[1].faction_id = "taiwan_green"
    red.organizations = {t: 1 for t in taiwan_towns[:13]}
    assert g.victory_engine._check_player_conditions(red, g)[0] is False
