#!/usr/bin/env python3
"""Runtime validator for event-card MVP."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, TurnPhase, GamePhase

RECORD_DIR = ROOT / "docs" / "records" / "event-cards"
JSON_OUT = RECORD_DIR / "EVENT_CARDS_RUNTIME_VALIDATION.json"
MD_OUT = RECORD_DIR / "EVENT_CARDS_RUNTIME_VALIDATION.md"


def make_game(event_name="歲月靜好"):
    game = Game([("viewer", "viewer"), ("red", "red")], market_mode="all_cards")
    game.players[0].faction_id = "liberals"
    game.players[1].faction_id = "red_army"
    game.players[0].base = "臺北"
    game.players[1].base = "北京"
    game.players[0].organizations = {"臺北": 1}
    game.players[1].organizations = {"北京": 1}
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.EVENT
    event = game._event_by_name(event_name)
    assert event, f"missing event: {event_name}"
    game.event_deck.draw_pile = [event]
    game.event_deck.discard_pile = []
    game.current_event = None
    game.event_progress = None
    game.event_modifiers = []
    game.event_notification = None
    return game


def assert_ok(result, label):
    assert not result.get("error"), f"{label}: {result}"
    return result


def names(cards):
    return [getattr(c, "name", str(c)) for c in cards]


def test_idle_noop():
    game = make_game("歲月靜好")
    assert_ok(game.advance_turn_phase(), "draw idle event")
    state = game.state()
    assert state["turn_phase"] == TurnPhase.EVENT
    assert state["current_event"]["name"] == "歲月靜好"
    assert state["current_event"]["status"] == "idle"
    assert_ok(game.advance_turn_phase(), "enter action after idle display")
    assert game.turn_phase == TurnPhase.ACTION
    return {"event": "歲月靜好", "status": state["current_event"]["status"], "phase_after_second_advance": game.turn_phase}


def test_hong_kong_success_static_supply():
    game = make_game("香港抗暴之戰")
    player = game.players[0]
    player.hand = [Card("資助者", "money", {"money": 2})]
    game.static_purchase_supply["宣傳家"] = 1
    before_discard = names(player.deck.discard_pile)
    before_count = before_discard.count("宣傳家")
    assert_ok(game.advance_turn_phase(), "draw hk event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.play_card(0, mode="resource"), "play money-cost card")
    assert game.event_progress["succeeded"] is True
    assert game.event_progress["settled"] is True
    discard = names(player.deck.discard_pile)
    assert discard.count("宣傳家") == before_count + 1, {"before": before_discard, "after": discard}
    assert game.static_purchase_supply["宣傳家"] == 0
    return {"event": "香港抗暴之戰", "progress": game.event_progress, "discard": discard, "initial_static_card_count": before_count, "static_supply": game.static_purchase_supply["宣傳家"]}


def test_hong_kong_failure_discard_choice():
    game = make_game("香港抗暴之戰")
    player = game.players[0]
    player.hand = [Card("追隨者", "propaganda", {"propaganda": 1}), Card("樂捐者", "money", {"money": 1})]
    assert_ok(game.advance_turn_phase(), "draw hk event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = assert_ok(game.advance_turn_phase(), "settle failure")
    assert result.get("pending_choice") is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_discard_self"
    assert choice["count"] == 1
    assert_ok(game.resolve_pending_choice(player.id, [0]), "resolve discard")
    assert names(player.deck.discard_pile)[-1] == "追隨者"
    return {"event": "香港抗暴之戰", "choice_key": choice["choice_key"], "discard": names(player.deck.discard_pile)}


def test_major_disaster_success():
    game = make_game("重大災難")
    player = game.players[0]
    player.hand = [Card("宣傳家", "propaganda", {"propaganda": 2})]
    game.static_purchase_supply["宣傳家"] = 1
    assert_ok(game.advance_turn_phase(), "draw disaster event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.play_card(0, mode="resource"), "play propaganda-cost card")
    assert game.event_progress["succeeded"] is True
    assert game.event_progress["settled"] is True
    assert game.static_purchase_supply["宣傳家"] == 0
    return {"event": "重大災難", "progress": game.event_progress, "discard": names(player.deck.discard_pile)}


def test_draw_trigger_succeeds():
    game = make_game("北京政爭")
    player = game.players[0]
    before = len(player.hand)
    assert_ok(game.advance_turn_phase(), "draw beijing event")
    assert_ok(game.advance_turn_phase(), "enter action")
    game._draw_player_cards(player, 1)
    assert game.event_progress["succeeded"] is True
    assert game.event_progress["settled"] is True
    # 北京政爭成功獎勵也會抽 1 張；若牌庫不足，至少確認觸發抽牌有進手牌。
    assert len(player.hand) >= before + 1
    return {"event": "北京政爭", "progress": game.event_progress, "hand_count": len(player.hand)}


def test_trade_war_purchase_trigger_topdecks_from_discard():
    game = make_game("貿易戰加劇")
    player = game.players[0]
    player.resources = {"money": 4, "propaganda": 0}
    player.deck.discard_pile = [Card("舊棄牌", "command", {"money": 0})]
    player.deck.draw_pile = [Card("原牌庫頂下方", "command", {})]
    target = Card("四點行動", "command", {"money": 0})
    static_count = len(game._static_purchase_cards())
    game.purchase_area = game._static_purchase_cards() + [target]
    game._card_purchase_cost = lambda card: {"money": 4, "propaganda": 0} if getattr(card, "name", "") == "四點行動" else {"money": 0, "propaganda": 0}

    assert_ok(game.advance_turn_phase(), "draw trade war event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = assert_ok(game.buy_card(static_count), "buy total-cost-4 card")
    assert result.get("pending_choice") is True, result
    assert game.event_progress["succeeded"] is True
    assert game.event_progress["settled"] is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_topdeck_from_discard"
    assert names(choice["cards"]) == ["舊棄牌", "四點行動"], names(choice["cards"])
    assert_ok(game.resolve_pending_choice(player.id, 1), "topdeck purchased card")
    assert names(player.deck.draw_pile)[-1] == "四點行動"
    assert "四點行動" not in names(player.deck.discard_pile)
    return {"event": "貿易戰加劇", "choice_key": choice["choice_key"], "deck_top": names(player.deck.draw_pile)[-1], "discard": names(player.deck.discard_pile)}


def test_trade_war_purchase_trigger_ignores_low_cost_non_anglo_support():
    game = make_game("貿易戰加劇")
    player = game.players[0]
    player.resources = {"money": 3, "propaganda": 0}
    game.purchase_area = game._static_purchase_cards() + [Card("低費行動", "command", {"money": 0})]
    static_count = len(game._static_purchase_cards())
    game._card_purchase_cost = lambda card: {"money": 3, "propaganda": 0} if getattr(card, "name", "") == "低費行動" else {"money": 0, "propaganda": 0}

    assert_ok(game.advance_turn_phase(), "draw trade war event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.buy_card(static_count), "buy low-cost non-support card")
    assert game.event_progress["succeeded"] is False
    assert game.pending_choice is None
    return {"event": "貿易戰加劇", "progress": game.event_progress, "pending_choice": game.pending_choice}


def test_trade_war_purchase_trigger_accepts_anglo_support_by_name():
    game = make_game("貿易戰加劇")
    player = game.players[0]
    player.resources = {"money": 0, "propaganda": 0}
    player.deck.discard_pile = [Card("可置頂牌", "command", {})]
    support = Card("英美奧援", "support", {})
    game.purchase_area = game._static_purchase_cards() + [support]
    static_count = len(game._static_purchase_cards())
    game._card_purchase_cost = lambda card: {"money": 0, "propaganda": 0}

    assert_ok(game.advance_turn_phase(), "draw trade war event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = assert_ok(game.buy_card(static_count), "buy 英美奧援 by name")
    assert result.get("pending_choice") is True, result
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_topdeck_from_discard"
    assert names(choice["cards"]) == ["可置頂牌", "英美奧援"], names(choice["cards"])
    return {"event": "貿易戰加劇", "triggered_by": "英美奧援", "choice_key": choice["choice_key"]}


def test_elite_defection_trashes_from_hand_after_three_moves():
    game = make_game("紅軍權貴出逃")
    player = game.players[0]
    player.moves_left = 3
    player.organizations = {"臺北": 1, "桃園": 1, "基隆": 1, "臺中": 1}
    player.hand = [Card("手牌移除目標", "command", {})]
    player.deck.discard_pile = [Card("棄牌保留", "command", {})]

    assert_ok(game.advance_turn_phase(), "draw elite defection event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.move_organization("桃園", "新竹", mode="rail"), "first move")
    assert_ok(game.move_organization("基隆", "新北", mode="road"), "second move")
    assert_ok(game.move_organization("臺中", "南投", mode="road"), "third move")
    assert game.pending_choice is not None
    assert game.event_progress["succeeded"] is True
    assert game.event_progress["settled"] is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "trash_from_hand_or_discard"
    assert choice["cards"] == [
        {"name": "手牌移除目標", "zone": "hand", "zone_label": "手牌"},
        {"name": "棄牌保留", "zone": "discard", "zone_label": "棄牌堆"},
    ], choice["cards"]
    resolve = assert_ok(game.resolve_pending_choice(player.id, 0), "trash hand card")
    assert resolve["chosen_card"] == "手牌移除目標"
    assert resolve["zone"] == "hand"
    assert names(player.hand) == []
    assert names(player.deck.discard_pile) == ["棄牌保留"]
    assert resolve["removed_card"]["name"] == "手牌移除目標"
    assert resolve["removed_card"]["zone"] in {"deck_discard", "static_supply", "removed"}
    return {"event": "紅軍權貴出逃", "choice_key": choice["choice_key"], "trashed": resolve["chosen_card"], "zone": resolve["zone"]}


def test_elite_defection_trashes_from_discard_after_three_moves():
    game = make_game("紅軍權貴出逃")
    player = game.players[0]
    player.moves_left = 3
    player.organizations = {"臺北": 1, "桃園": 1, "基隆": 1, "臺中": 1}
    player.hand = [Card("手牌保留", "command", {})]
    player.deck.discard_pile = [Card("棄牌移除目標", "command", {})]

    assert_ok(game.advance_turn_phase(), "draw elite defection event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.move_organization("桃園", "新竹", mode="rail"), "first move")
    assert_ok(game.move_organization("基隆", "新北", mode="road"), "second move")
    assert_ok(game.move_organization("臺中", "南投", mode="road"), "third move")
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "trash_from_hand_or_discard"
    resolve = assert_ok(game.resolve_pending_choice(player.id, 1), "trash discard card")
    assert resolve["chosen_card"] == "棄牌移除目標"
    assert resolve["zone"] == "discard"
    assert names(player.hand) == ["手牌保留"]
    assert names(player.deck.discard_pile) == []
    assert resolve["removed_card"]["name"] == "棄牌移除目標"
    assert resolve["removed_card"]["zone"] in {"deck_discard", "static_supply", "removed"}
    return {"event": "紅軍權貴出逃", "choice_key": choice["choice_key"], "trashed": resolve["chosen_card"], "zone": resolve["zone"]}


def test_elite_defection_structured_matches_raw_rule():
    game = make_game("紅軍權貴出逃")
    event = game._event_by_name("紅軍權貴出逃")
    assert event["trigger"] == {"type": "move_organization", "count": 3}
    assert event["success"] == {"type": "trash_from_hand_or_discard", "count": 1}
    assert event["failure"] == {"type": "discard_self", "count": 1}
    duplicate = game._event_by_name("紅軍權貴出逃（副本）")
    assert duplicate["success"] == event["success"]
    return {"event": event["name"], "trigger": event["trigger"], "success": event["success"], "duplicate_success": duplicate["success"]}


def test_urumqi_end_turn_wall_org_builds_near_own_org():
    game = make_game("烏魯木齊七五事件")
    player = game.players[0]
    player.organizations = {"北京": 1}
    player.hand = [Card("保留手牌", "command", {})]

    assert_ok(game.advance_turn_phase(), "draw urumqi event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = assert_ok(game.advance_turn_phase(), "settle end-turn wall org success")
    assert result.get("pending_choice") is True, result
    assert game.event_progress["count"] == 1
    assert game.event_progress["succeeded"] is True
    assert game.event_progress["settled"] is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_build_organization"
    assert choice["type"] == "town_choice"
    choice_towns = [item["town"] for item in choice["towns"]]
    assert "天津" in choice_towns, choice_towns
    assert "臺北" not in choice_towns, choice_towns
    assert "石家莊" in choice_towns, choice_towns
    idx = choice_towns.index("天津")
    resolve = assert_ok(game.resolve_pending_choice(player.id, idx), "build near own org")
    assert resolve["town"] == "天津"
    assert player.organizations.get("天津") == 1
    assert names(player.hand) == ["保留手牌"]
    return {"event": "烏魯木齊七五事件", "trigger_count": game.event_progress["count"], "choice_key": choice["choice_key"], "sample_towns": choice_towns[:6], "built": resolve["town"]}


def test_urumqi_end_turn_without_wall_org_fails_random_discard():
    game = make_game("烏魯木齊七五事件")
    player = game.players[0]
    player.organizations = {"臺北": 1}
    player.hand = [Card("會被隨機棄掉", "command", {})]

    assert_ok(game.advance_turn_phase(), "draw urumqi event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.advance_turn_phase(), "settle end-turn no wall org failure")
    assert game.event_progress["count"] == 0
    assert game.event_progress["succeeded"] is False
    assert game.event_progress["settled"] is True
    assert names(player.hand) == []
    assert names(player.deck.discard_pile)[-1] == "會被隨機棄掉"
    return {"event": "烏魯木齊七五事件", "trigger_count": game.event_progress["count"], "discard": names(player.deck.discard_pile)[-1]}


def test_urumqi_structured_matches_raw_rule():
    game = make_game("烏魯木齊七五事件")
    event = game._event_by_name("烏魯木齊七五事件")
    assert event["trigger"] == {"type": "end_turn_state", "count": 1, "condition": "own_organization_in_scope", "scope": "牆內"}
    assert event["success"] == {"type": "build_organization_near_own", "count": 1, "max_steps": 1}
    assert event["failure"] == {"type": "discard_random", "count": 1}
    return {"event": event["name"], "trigger": event["trigger"], "success": event["success"], "failure": event["failure"]}


def test_event_deck_uses_declared_counts_without_structured_duplicate_overcount():
    game = make_game("歲月靜好")
    counts = {}
    for card in game._initial_event_cards():
        counts[card["name"]] = counts.get(card["name"], 0) + 1
    assert counts["全國人大召開"] == 2, counts
    assert counts["重大災難"] == 2, counts
    assert "全國人大召開（副本）" not in counts
    assert "重大災難（副本）" not in counts
    return {"全國人大召開": counts["全國人大召開"], "重大災難": counts["重大災難"], "total": sum(counts.values())}


def test_trade_war_structured_matches_raw_rule():
    game = make_game("貿易戰加劇")
    event = game._event_by_name("貿易戰加劇")
    assert event["trigger"] == {"type": "buy_card", "count": 1, "min_cost": 4, "card_names": ["英美奧援"]}
    assert event["success"] == {"type": "topdeck_from_discard", "count": 1}
    assert event["failure"] == {"type": "none"}
    return {"event": event["name"], "trigger": event["trigger"], "success": event["success"]}


def test_event_modifiers_are_consumed_by_runtime_rules():
    game = make_game("歲月靜好")
    player = game.players[0]

    game.event_modifiers = [{"type": "reduce_cost", "amount": 1}]
    assert game._event_reduce_cost_amount() == 1

    game.turn_phase = TurnPhase.ACTION
    card_index = next(i for i, card in enumerate(game.purchase_area) if getattr(card, "name", "") == "資助者")
    player.resources = {"money": 1, "propaganda": 1}
    assert_ok(game.buy_card(card_index), "buy reduced-cost static card")

    game.event_modifiers = [{"type": "restrict_build"}]
    blocked = game.build_organization("臺北")
    assert blocked.get("error") == "Current event restricts building organizations"

    game.event_modifiers = [{"type": "ignore_distance"}]
    player.moves_left = 1
    player.organizations["臺北"] = 2
    moved = game.move_organization("臺北", "北京", mode="road")
    assert_ok(moved, "ignore_distance move")
    return {"reduce_cost_buy": names(player.deck.discard_pile), "restrict_build_error": blocked.get("error"), "ignore_distance_move": moved}


def test_pending_choice_blocks_phase_advance_until_resolved():
    game = make_game("香港抗暴之戰")
    player = game.players[0]
    player.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    assert_ok(game.advance_turn_phase(), "draw hk event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = assert_ok(game.advance_turn_phase(), "settle failure")
    assert result.get("pending_choice") is True
    blocked = game.advance_turn_phase()
    assert blocked.get("error") == "Resolve pending choice before advancing phase"
    assert_ok(game.resolve_pending_choice(player.id, [0]), "resolve event pending choice")
    assert_ok(game.advance_turn_phase(), "advance after resolving pending choice")
    return {"event": "香港抗暴之戰", "blocked_error": blocked.get("error"), "phase_after_resolve": game.turn_phase}


def test_shanghai_cooperation_scoped_modifier_structured_matches_raw_rule():
    game = make_game("上海合作組織")
    event = game._event_by_name("上海合作組織")
    expected = {
        "type": "scoped_card_range",
        "duration": 1,
        "player_faction": "red_army",
        "card_types": ["armed", "spy"],
        "target_region": "outer_manchuria",
        "range": 5,
    }
    assert event["effect"] == expected
    return {"event": event["name"], "effect": event["effect"]}


def test_shanghai_cooperation_auto_modifier():
    game = make_game("上海合作組織")
    game.current_player_index = 1
    assert_ok(game.advance_turn_phase(), "draw auto event")
    assert game.current_event["name"] == "上海合作組織"
    assert game.event_modifiers and game.event_modifiers[0]["type"] == "scoped_card_range"
    assert game.event_modifiers[0]["range"] == 5
    assert game.event_modifiers[0]["target_region"] == "outer_manchuria"
    assert game.event_progress["status"] == "auto"
    return {"event": "上海合作組織", "modifiers": game.event_modifiers, "status": game.event_progress["status"]}


def test_shanghai_cooperation_armed_reaches_north_org_at_five_steps_only():
    game = make_game("上海合作組織")
    red = game.players[1]
    target = game.players[0]
    game.current_player_index = 1
    red.organizations = {"北京": 1}
    target.organizations = {"海參崴": 1}
    red.hand = [Card("武裝者", "armed", {})]
    target.hand = [Card("被棄目標", "command", {})]
    assert_ok(game.advance_turn_phase(), "draw shanghai event")
    assert_ok(game.advance_turn_phase(), "enter red action")
    result = assert_ok(game.play_card(0, mode="action", target_player_id=target.id), "armed reaches north org at 5 steps")
    assert result.get("pending_choice") is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "armed_target_discard"

    blocked_game = make_game("上海合作組織")
    blocked_red = blocked_game.players[1]
    blocked_target = blocked_game.players[0]
    blocked_game.current_player_index = 1
    blocked_red.organizations = {"北京": 1}
    blocked_target.organizations = {"臺北": 1}
    blocked_red.hand = [Card("武裝者", "armed", {})]
    blocked_target.hand = [Card("不該被棄", "command", {})]
    assert_ok(blocked_game.advance_turn_phase(), "draw shanghai event blocked case")
    assert_ok(blocked_game.advance_turn_phase(), "enter red action blocked case")
    blocked = blocked_game.play_card(0, mode="action", target_player_id=blocked_target.id)
    assert blocked.get("error") == "Target player has no organization within range"

    non_red_game = make_game("上海合作組織")
    non_red_actor = non_red_game.players[0]
    non_red_target = non_red_game.players[1]
    non_red_game.current_player_index = 0
    non_red_actor.organizations = {"北京": 1}
    non_red_target.organizations = {"海參崴": 1}
    non_red_actor.hand = [Card("武裝者", "armed", {})]
    non_red_target.hand = [Card("不該被非紅軍棄", "command", {})]
    assert_ok(non_red_game.advance_turn_phase(), "draw shanghai event non-red case")
    assert_ok(non_red_game.advance_turn_phase(), "enter non-red action")
    non_red_blocked = non_red_game.play_card(0, mode="action", target_player_id=non_red_target.id)
    assert non_red_blocked.get("error") == "Target player has no organization within range"
    return {"event": "上海合作組織", "allowed_target": "海參崴", "blocked_target": "臺北", "non_red_blocked": True, "choice_key": choice["choice_key"]}


def test_shanghai_cooperation_spy_targets_north_org_at_five_steps():
    game = make_game("上海合作組織")
    red = game.players[1]
    target = game.players[0]
    game.current_player_index = 1
    red.organizations = {"北京": 1}
    target.organizations = {"海參崴": 1}
    red.hand = [Card("內應間諜", "spy", {})]
    assert_ok(game.advance_turn_phase(), "draw shanghai event")
    assert_ok(game.advance_turn_phase(), "enter red action")
    result = assert_ok(game.play_card(0, mode="action", target_player_id=target.id), "spy reaches north org at 5 steps")
    assert result.get("pending_choice") is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "card_dissolve_interaction"
    assert [entry["town"] for entry in choice["targets"]] == ["海參崴"]
    return {"event": "上海合作組織", "choice_key": choice["choice_key"], "targets": choice["targets"]}


def test_event_deck_reshuffle():
    game = make_game("歲月靜好")
    event = game.event_deck.draw_pile.pop()
    game.event_deck.discard_pile = [event]
    assert_ok(game.advance_turn_phase(), "draw reshuffled event")
    assert game.current_event["name"] == "歲月靜好"
    assert len(game.event_deck.draw_pile) == 0
    assert len(game.event_deck.discard_pile) == 1
    return {"event": game.current_event["name"], "discard_count": len(game.event_deck.discard_pile)}


def main():
    tests = [
        test_idle_noop,
        test_hong_kong_success_static_supply,
        test_hong_kong_failure_discard_choice,
        test_major_disaster_success,
        test_draw_trigger_succeeds,
        test_trade_war_purchase_trigger_topdecks_from_discard,
        test_trade_war_purchase_trigger_ignores_low_cost_non_anglo_support,
        test_trade_war_purchase_trigger_accepts_anglo_support_by_name,
        test_elite_defection_trashes_from_hand_after_three_moves,
        test_elite_defection_trashes_from_discard_after_three_moves,
        test_elite_defection_structured_matches_raw_rule,
        test_urumqi_end_turn_wall_org_builds_near_own_org,
        test_urumqi_end_turn_without_wall_org_fails_random_discard,
        test_urumqi_structured_matches_raw_rule,
        test_shanghai_cooperation_scoped_modifier_structured_matches_raw_rule,
        test_shanghai_cooperation_auto_modifier,
        test_shanghai_cooperation_armed_reaches_north_org_at_five_steps_only,
        test_shanghai_cooperation_spy_targets_north_org_at_five_steps,
        test_event_deck_uses_declared_counts_without_structured_duplicate_overcount,
        test_trade_war_structured_matches_raw_rule,
        test_event_modifiers_are_consumed_by_runtime_rules,
        test_pending_choice_blocks_phase_advance_until_resolved,
        test_event_deck_reshuffle,
    ]
    results = []
    for test in tests:
        results.append({"name": test.__name__, "status": "passed", "detail": test()})
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"status": "passed", "passed": len(results), "results": results}
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Event Cards Runtime Validation", "", f"Status: passed ({len(results)} passed)", ""]
    for item in results:
        lines.append(f"- {item['name']}: passed — {item['detail']}")
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
