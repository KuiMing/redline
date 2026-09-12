"""Unit tests for mcp_server.summarize and mcp_server.rules_data against
fabricated (already viewer-scoped, per Game.state()'s own contract) state
dicts — no live server needed. These cover the two things most likely to
silently regress: hidden-information leakage, and the legal-actions
projection matching what the real WS action handlers actually accept.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server import summarize
from mcp_server.rules_data import (
    faction_dispatchable_action_names,
    faction_win_condition_texts,
    resolve_faction_detail,
)

ME = "p-me"
OTHER = "p-other"


def _base_state(**overrides):
    state = {
        "turn": 3,
        "game_phase": "main",
        "turn_phase": "action",
        "current_player": "Me",
        "winner": None,
        "co_winners": [],
        "pending_choice": None,
        "pending_base_choices": {},
        "hk_free_base_relocation": False,
        "faction_action_used": False,
        "current_event": {"name": "歲月靜好"},
        "purchase_area": [],
        "purchase_area_costs": [],
        "purchase_area_affordable": [],
        "action_log": ["a", "b", "c"],
        "map": {"legal_organization_moves": {}},
        "topdeck_candidates_count": 0,
        "players": [
            {
                "id": ME,
                "name": "Me",
                "faction": "taiwan_green",
                "base": "臺北",
                "resources": {"money": 2, "propaganda": 1},
                "hand": ["追隨者", "追隨者"],
                "hand_action_legality": [{"playable": True}, {"playable": False, "reason": "no legal town"}],
                "organization_counts": {"total": 1},
            },
            {
                "id": OTHER,
                "name": "Other",
                "faction": "hong_kong",
                "base": "香港城",
                "resources": {"money": 0, "propaganda": 0},
                "hand": ["未知手牌", "未知手牌"],
                "hand_action_legality": [None, None],
                "organization_counts": {"total": 1},
            },
        ],
    }
    state.update(overrides)
    return state


FACTION_CATALOG = {
    "categories": [
        {
            "id": "taiwan",
            "options": [{"id": "taiwan_green", "name": "臺灣", "abilities": []}],
        },
        {
            "id": "red_army",
            "options": [
                {
                    "id": "red_army",
                    "name": "紅軍",
                    "win_conditions": [{"type": "default_survival", "text": "存活到底"}],
                    "abilities": [
                        {"name": "統戰部", "type": "activated"},
                        {"name": "政工部", "type": "activated"},
                        {"name": "國安部", "type": "activated"},
                        {"name": "中紀委", "type": "activated"},
                        {"name": "安全屋", "type": "passive"},
                    ],
                }
            ],
        },
        {
            "id": "tibet",
            "options": [
                {
                    "id": "tibet_family",
                    "name": "西藏",
                    "abilities": [{"name": "殉道者", "type": "activated"}],
                    "variant_details": {
                        "德拉敦": {
                            "id": "tibet_dehradun",
                            "abilities": [{"name": "立場試探", "type": "activated"}],
                            "win_condition_text": "牆內14個組織",
                        }
                    },
                }
            ],
        },
    ]
}


# ---------------- privacy ----------------


def test_summarize_never_exposes_raw_hand_contents():
    state = _base_state()
    summary = summarize.summarize_state(state, ME)
    dumped = str(summary)
    assert "未知手牌" not in dumped
    assert "追隨者" not in dumped  # summary reports counts, not card names
    assert summary["my_hand_size"] == 2


def test_pending_choice_content_hidden_from_non_owning_viewer():
    state = _base_state(
        pending_choice={
            "type": "card_choice",
            "choice_key": "guess_ability_bottom_card",
            "player_id": OTHER,
            "player_name": "Other",
            "prompt": "Pick a card to bottom-deck",
            "cards": ["秘密卡A", "秘密卡B"],  # Other's own hand — must never reach Me
            "cancellable": False,
        }
    )
    summary = summarize.summarize_state(state, ME)
    assert "cards" not in summary["pending_choice"]
    assert "秘密卡A" not in str(summary)

    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    assert legal["actions"] == []
    assert legal["waiting_on"] == "Other"
    assert "秘密卡A" not in str(legal)


def test_pending_choice_content_visible_to_owning_viewer():
    state = _base_state(
        pending_choice={
            "type": "card_choice",
            "choice_key": "guess_ability_bottom_card",
            "player_id": ME,
            "player_name": "Me",
            "prompt": "Pick a card to bottom-deck",
            "cards": ["追隨者", "樂捐者"],
            "cancellable": False,
        }
    )
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    assert len(legal["actions"]) == 1
    entry = legal["actions"][0]
    assert entry["kind"] == "resolve_pending_choice"
    assert entry["cards"] == ["追隨者", "樂捐者"]
    assert entry["index_range"] == [0, 1]


def test_multi_card_choice_flags_indices_param_needed():
    # server/game_card_play.py's _resolve_multi_card_choice expects a LIST of
    # indices (the WS "index" field is polymorphic); the LLM must be told to
    # use resolve_pending_choice(indices=[...]) instead of a bare index.
    state = _base_state(
        pending_choice={
            "type": "multi_card_choice",
            "choice_key": "red_army_ccdi_discard_draw",
            "player_id": ME,
            "player_name": "Me",
            "prompt": "中紀委：棄掉任意張數的手牌",
            "cards": ["追隨者", "樂捐者", "追隨者"],
            "count": 3,
            "min_count": 0,
            "cancellable": False,
        }
    )
    entry = summarize.legal_actions(state, ME, FACTION_CATALOG)["actions"][0]
    assert entry["use_indices_param"] is True
    assert entry["count"] == 3
    assert entry["min_count"] == 0


# ---------------- turn/phase gating ----------------


def test_not_my_turn_yields_no_actions():
    state = _base_state(current_player="Other")
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    assert legal["actions"] == []
    assert legal["waiting_on"] == "Other"


def test_event_phase_only_offers_advance_turn():
    state = _base_state(turn_phase="event")
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    kinds = {a["kind"] for a in legal["actions"]}
    assert kinds == {"advance_turn"}


def test_game_over_reports_winner_and_no_actions():
    state = _base_state(game_phase="finished", winner="red_army", co_winners=["Alice"])
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    assert legal["actions"] == []
    assert legal["game_over"] is True
    assert legal["winner"] == "red_army"
    summary = summarize.summarize_state(state, ME)
    assert summary["game_over"] is True


def test_base_selection_phase_offers_set_base_with_town_options():
    state = _base_state(
        game_phase="base_selection",
        pending_base_choices={ME: {"labels": ["安全屋"], "resolved": {"安全屋": ["臺北", "高雄"]}}},
    )
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    assert legal["actions"][0]["kind"] == "set_base"
    towns = {opt["town"] for opt in legal["actions"][0]["options"]}
    assert towns == {"臺北", "高雄"}


def test_hong_kong_free_relocation_window_offers_keep_and_relocate():
    state = _base_state(hk_free_base_relocation=True)
    state["players"][0]["faction"] = "hong_kong"
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    kinds = {a["kind"] for a in legal["actions"]}
    assert kinds == {"keep_hong_kong_base", "relocate_hong_kong_base"}


# ---------------- action-phase legal actions ----------------


def test_play_card_entries_reflect_hand_action_legality():
    legal = summarize.legal_actions(_base_state(), ME, FACTION_CATALOG)
    plays = [a for a in legal["actions"] if a["kind"] == "play_card"]
    assert plays[0]["modes"] == ["resource", "action"]
    assert plays[1]["modes"] == ["resource"]
    assert plays[1]["action_mode_blocked_reason"] == "no legal town"


def test_targeted_card_gets_target_candidates_excluding_self():
    state = _base_state()
    state["players"][0]["hand"] = ["合作談判"]
    state["players"][0]["hand_action_legality"] = [{"playable": True}]
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    play = next(a for a in legal["actions"] if a["kind"] == "play_card")
    assert play["needs_target_player_id"] is True
    assert play["target_candidates"] == [OTHER]


def test_optionally_targeted_card_is_not_flagged_as_required():
    # server/game_card_play.py only validates 走漏風聲's target_player_id
    # "if target_player_id is not None" — unlike 合作談判/武裝*, it's legal
    # to play without one. get_legal_actions must not tell the LLM it's
    # mandatory (it would still be harmless if supplied, but a caller who
    # trusts "needs_target_player_id" as gospel should not be blocked from
    # omitting it).
    state = _base_state()
    state["players"][0]["hand"] = ["走漏風聲"]
    state["players"][0]["hand_action_legality"] = [{"playable": True}]
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    play = next(a for a in legal["actions"] if a["kind"] == "play_card")
    assert play["needs_target_player_id"] is False
    assert play["optional_target_player_id"] is True
    assert play["target_candidates"] == [OTHER]


def test_move_and_buy_entries_come_from_state_fields():
    state = _base_state(
        purchase_area=["宣傳家"],
        purchase_area_costs=[{"money": 1}],
        purchase_area_affordable=[True],
    )
    state["players"][0]["hand"] = []
    state["players"][0]["hand_action_legality"] = []
    state["map"]["legal_organization_moves"] = {"臺北": {"road": [{"town": "高雄", "cost": 1}], "rail": []}}
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    moves = [a for a in legal["actions"] if a["kind"] == "move_organization"]
    buys = [a for a in legal["actions"] if a["kind"] == "buy_card"]
    assert moves == [{"kind": "move_organization", "from_town": "臺北", "to_town": "高雄", "mode": "road", "cost": 1}]
    assert buys == [{"kind": "buy_card", "index": 0, "card_name": "宣傳家", "cost": {"money": 1}, "affordable": True}]


def test_red_army_faction_actions_gated_by_action_count_not_used_flag():
    state = _base_state(faction_action_used=True, red_army_action_limit=4, red_army_action_count=1)
    state["players"][0]["faction"] = "red_army"
    state["players"][0]["hand"] = []
    state["players"][0]["hand_action_legality"] = []
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    names = {a["name"] for a in legal["actions"] if a["kind"] == "faction_action"}
    assert names == {"統戰部", "政工部", "國安部", "中紀委"}
    propaganda_entry = next(a for a in legal["actions"] if a.get("name") == "政工部")
    assert propaganda_entry["needs_target_player_id"] is True


def test_red_army_faction_actions_disappear_once_count_exhausted():
    state = _base_state(red_army_action_limit=1, red_army_action_count=1)
    state["players"][0]["faction"] = "red_army"
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    assert not any(a["kind"] == "faction_action" for a in legal["actions"])


def test_non_red_faction_action_gated_by_faction_action_used():
    state = _base_state(faction_action_used=True)
    state["players"][0]["faction"] = "tibet_dehradun"
    state["players"][0]["base"] = "德拉敦"
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    assert not any(a["kind"] == "faction_action" for a in legal["actions"])

    state["faction_action_used"] = False
    legal = summarize.legal_actions(state, ME, FACTION_CATALOG)
    names = {a["name"] for a in legal["actions"] if a["kind"] == "faction_action"}
    assert names == {"立場試探"}


# ---------------- rules_data helpers ----------------


def test_resolve_faction_detail_uses_base_variant_for_family_factions():
    detail = resolve_faction_detail(FACTION_CATALOG, "tibet_family", "德拉敦")
    assert detail["id"] == "tibet_dehradun"


def test_faction_win_condition_texts_prefers_win_condition_text():
    texts = faction_win_condition_texts(FACTION_CATALOG, "tibet_family", "德拉敦")
    assert texts == ["牆內14個組織"]


def test_faction_win_condition_texts_describes_structured_conditions():
    texts = faction_win_condition_texts(FACTION_CATALOG, "red_army", None)
    assert texts == ["存活到底"]


def test_dispatchable_action_names_excludes_non_whitelisted_activated_ability():
    names = faction_dispatchable_action_names(FACTION_CATALOG, "red_army", None)
    assert set(names) == {"統戰部", "政工部", "國安部", "中紀委"}
    assert "安全屋" not in names


def test_state_detail_rejects_unknown_section_with_helpful_message():
    import pytest

    with pytest.raises(ValueError, match="Unknown section"):
        summarize.state_detail(_base_state(), "nonsense")
