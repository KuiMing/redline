#!/usr/bin/env python3
"""Runtime validator for event-card MVP."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
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
    # Most runtime checks focus the non-red viewer as the last actor of a
    # round, so mission settlement happens on ACTION -> END without needing
    # to drive the Red Army's unrelated turn.
    game.round_start_player_index = 1
    game.turn_phase = TurnPhase.EVENT
    event = game._event_by_name(event_name)
    assert event, f"missing event: {event_name}"
    game.event_deck.draw_pile = [event]
    game.event_deck.discard_pile = []
    game.current_event = None
    game.event_progress = None
    game.event_modifiers = []
    game.event_notification = None
    game.pending_choice = None
    return game


def assert_ok(result, label):
    assert not result.get("error"), f"{label}: {result}"
    return result


def settle_round_event(game, label="settle round event"):
    """Mission progress can succeed during ACTION, but event effects resolve at round end.
    Settlement fires on the END advance (deferred until after the end-turn refill); when
    that advance also wraps the round, the settled progress is the PRE-wrap snapshot, so
    track this round's own progress object rather than game.event_progress."""
    progress = game.event_progress
    result = None
    for _ in range(3):
        result = assert_ok(game.advance_turn_phase(), label)
        if result.get("pending_choice") or progress is None or progress.get("settled"):
            break
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
    progress = game.event_progress
    settle_round_event(game, "settle hk success at round end")
    assert progress["settled"] is True
    discard = names(player.deck.discard_pile)
    assert discard.count("宣傳家") == before_count + 1, {"before": before_discard, "after": discard}
    assert game.static_purchase_supply["宣傳家"] == 0
    return {"event": "香港抗暴之戰", "progress": progress, "discard": discard, "initial_static_card_count": before_count, "static_supply": game.static_purchase_supply["宣傳家"]}


def test_hong_kong_failure_discard_choice():
    game = make_game("香港抗暴之戰")
    player = game.players[0]
    player.hand = [Card("追隨者", "propaganda", {"propaganda": 1}), Card("樂捐者", "money", {"money": 1})]
    assert_ok(game.advance_turn_phase(), "draw hk event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = settle_round_event(game, "settle failure")
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
    progress = game.event_progress
    settle_round_event(game, "settle disaster success at round end")
    assert progress["settled"] is True
    assert game.static_purchase_supply["宣傳家"] == 0
    return {"event": "重大災難", "progress": progress, "discard": names(player.deck.discard_pile)}


def test_draw_trigger_succeeds():
    game = make_game("北京政爭")
    player = game.players[0]
    before = len(player.hand)
    assert_ok(game.advance_turn_phase(), "draw beijing event")
    assert_ok(game.advance_turn_phase(), "enter action")
    game._draw_player_cards(player, 1)
    assert game.event_progress["succeeded"] is True
    progress = game.event_progress
    settle_round_event(game, "settle draw-trigger success at round end")
    assert progress["settled"] is True
    # 北京政爭成功獎勵也會抽 1 張；若牌庫不足，至少確認觸發抽牌有進手牌。
    assert len(player.hand) >= before + 1
    return {"event": "北京政爭", "progress": progress, "hand_count": len(player.hand)}



def test_event_mission_triggers_ignore_red_army_actor():
    game = make_game("全國人大召開")
    non_red = game.players[0]
    red = game.players[1]
    red.faction_id = "red_army"

    checked_triggers = [
        "use_faction_ability",
        "play_card_with_money",
        "play_card_with_propaganda",
        "build_organization",
        "move_organization",
        "draw",
    ]
    for trigger_type in checked_triggers:
        game.current_event = {
            "name": "測試事件",
            "type": "mission",
            "trigger": {"type": trigger_type, "count": 1},
            "success": {"type": "none"},
            "failure": {"type": "none"},
        }
        game.event_progress = {"count": 0, "required": 1, "succeeded": False, "settled": False, "status": "active"}
        game._track_event_progress(trigger_type, player=red)
        assert game.event_progress["count"] == 0, f"red army {trigger_type} must not satisfy event-card mission conditions"
        game._track_event_progress(trigger_type, player=non_red)
        assert game.event_progress["count"] == 1, f"non-red {trigger_type} should satisfy event-card mission conditions"

    game.current_event = {
        "name": "測試購買事件",
        "type": "mission",
        "trigger": {"type": "buy_card", "count": 1, "min_cost": 1},
        "success": {"type": "none"},
        "failure": {"type": "none"},
    }
    bought = Card("測試牌", "command", {})
    game.event_progress = {"count": 0, "required": 1, "succeeded": False, "settled": False, "status": "active"}
    game._track_event_purchase(bought, original_cost={"money": 1, "propaganda": 0}, player=red)
    assert game.event_progress["count"] == 0, "red army purchases must not satisfy event-card mission conditions"
    game._track_event_purchase(bought, original_cost={"money": 1, "propaganda": 0}, player=non_red)
    assert game.event_progress["count"] == 1, "non-red purchases should satisfy event-card mission conditions"
    success_payload = game._event_display_payload()
    assert success_payload["result_text"] == "非紅軍任務條件已達成，等待全體玩家行動結束後結算"
    # Display-text check for a settled success (settlement flow itself is covered by the
    # dedicated tests above); mirror the manual construction used for the failure case.
    game.event_progress = {"count": 1, "required": 1, "succeeded": True, "settled": True, "status": "success"}
    settled_success_payload = game._event_display_payload()
    assert settled_success_payload["result_text"] == "非紅軍任務成功"

    game.event_progress = {"count": 0, "required": 1, "succeeded": False, "settled": True, "status": "failure"}
    failure_payload = game._event_display_payload()
    assert failure_payload["result_text"] == "非紅軍任務失敗，紅軍效果生效"

    return {
        "red_progress": 0,
        "non_red_progress": success_payload["progress"]["count"],
        "checked_triggers": checked_triggers + ["buy_card"],
        "success_result_text": settled_success_payload["result_text"],
        "failure_result_text": failure_payload["result_text"],
    }

def test_remaining_six_event_structured_matches_raw_rules():
    game = make_game("歲月靜好")
    expected = {
        "全國人大召開": {
            "trigger": {"type": "use_faction_ability", "count": 1},
            "success": {"type": "draw", "count": 1},
            "failure": {"type": "red_dissolve", "count": 1, "scope": "牆內"},
        },
        "香港抗暴之戰": {
            "trigger": {"type": "play_card_with_money", "count": 1},
            "success": {"type": "gain_card", "card": "宣傳家", "count": 2},
            "failure": {"type": "discard_self", "count": 1},
        },
        "重大災難": {
            "trigger": {"type": "play_card_with_propaganda", "count": 1},
            "success": {"type": "gain_card", "card": "宣傳家", "count": 1},
            "failure": {"type": "discard_self", "count": 1},
        },
        "藏印邊境軍事對峙": {
            "trigger": {"type": "build_organization", "count": 1, "scope": "牆內"},
            "success": {"type": "move", "count": 2},
            "failure": {"type": "none"},
        },
        "東突厥集中營": {
            "trigger": {"type": "play_card_with_propaganda", "count": 1},
            "success": {"type": "gain_card", "card": "宣傳家", "count": 1},
            "failure": {"type": "discard_random", "count": 1},
        },
        "北京政爭": {
            "trigger": {"type": "draw", "count": 1},
            "success": {"type": "draw", "count": 1},
            "failure": {"type": "none"},
        },
    }
    details = {}
    for name, spec in expected.items():
        event = game._event_by_name(name)
        assert event, name
        assert event["trigger"] == spec["trigger"], {name: event["trigger"]}
        assert event["success"] == spec["success"], {name: event["success"]}
        assert event["failure"] == spec["failure"], {name: event["failure"]}
        details[name] = spec
    return {"events": details}


def test_national_people_congress_faction_ability_success_draws():
    game = make_game("全國人大召開")
    player = game.players[0]
    player.faction_id = "minyun"  # 民主陣線 belongs to 民運派; ability ownership is enforced
    player.resources = {"money": 2, "propaganda": 0}
    player.hand = [Card("保留手牌", "command", {})]
    player.deck.draw_pile = [Card("獎勵抽牌", "command", {})]
    assert_ok(game.advance_turn_phase(), "draw npc event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game._activated_faction_action(player, "民主陣線"), "use faction ability")
    assert game.event_progress["succeeded"] is True
    progress = game.event_progress
    settle_round_event(game, "settle npc success at round end")
    assert progress["settled"] is True
    assert "獎勵抽牌" in names(player.hand)
    return {"event": "全國人大召開", "progress": progress, "hand": names(player.hand), "discard": names(player.deck.discard_pile)}


def test_national_people_congress_failure_red_dissolves_wall_org_only():
    game = make_game("全國人大召開")
    viewer = game.players[0]
    red = game.players[1]
    viewer.organizations = {"北京": 1, "臺北": 1}
    viewer.hand = [Card("保留手牌", "command", {})]
    assert_ok(game.advance_turn_phase(), "draw npc event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = settle_round_event(game, "settle npc failure")
    assert result.get("pending_choice") is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_red_dissolve"
    assert choice["player_id"] == red.id
    towns = [target["town"] for target in choice["targets"]]
    assert towns == ["北京"], towns
    assert_ok(game.resolve_pending_choice(red.id, 0), "red dissolves wall org")
    assert viewer.organizations.get("北京", 0) == 0
    assert viewer.organizations.get("臺北", 0) == 1
    return {"event": "全國人大召開", "choice_key": choice["choice_key"], "targets": towns, "remaining_orgs": viewer.organizations}


def test_tibet_border_build_wall_org_grants_two_moves():
    game = make_game("藏印邊境軍事對峙")
    player = game.players[0]
    # 北京 is the red player's occupied base. Use the Manchuria faction so both the
    # occupied origin 天津 and empty target 承德 are legal under faction-tag rules.
    player.faction_id = "manchuria"
    player.organizations = {"天津": 1}
    player.moves_left = 0
    assert_ok(game.advance_turn_phase(), "draw tibet border event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.build_organization_with_support("天津", "承德"), "build wall org")
    assert game.event_progress["succeeded"] is True
    progress = game.event_progress
    settle_round_event(game, "settle border success at round end")
    assert progress["settled"] is True
    assert player.moves_left == 2
    return {"event": "藏印邊境軍事對峙", "progress": progress, "moves_left": player.moves_left, "organizations": player.organizations}


def test_east_turkestan_success_and_failure_paths():
    success_game = make_game("東突厥集中營")
    success_player = success_game.players[0]
    success_player.hand = [Card("宣傳家", "propaganda", {"propaganda": 1})]
    success_game.static_purchase_supply["宣傳家"] = 1
    assert_ok(success_game.advance_turn_phase(), "draw east turkestan success event")
    assert_ok(success_game.advance_turn_phase(), "enter action success")
    assert_ok(success_game.play_card(0, mode="resource"), "play propaganda card")
    assert success_game.event_progress["succeeded"] is True
    settle_round_event(success_game, "settle east turkestan success at round end")
    assert success_game.static_purchase_supply["宣傳家"] == 0
    assert "宣傳家" in names(success_player.deck.discard_pile)

    failure_game = make_game("東突厥集中營")
    failure_player = failure_game.players[0]
    failure_player.hand = [Card("會被隨機棄掉", "command", {})]
    # The penalty settles after the end-turn refill; empty the deck so the refill cannot
    # add cards and the single hand card is the deterministic random-discard target.
    failure_player.deck.draw_pile = []
    failure_player.deck.discard_pile = []
    assert_ok(failure_game.advance_turn_phase(), "draw east turkestan failure event")
    assert_ok(failure_game.advance_turn_phase(), "enter action failure")
    settle_round_event(failure_game, "settle failure")
    assert names(failure_player.hand) == []
    assert names(failure_player.deck.discard_pile)[-1] == "會被隨機棄掉"
    return {
        "event": "東突厥集中營",
        "success_discard": names(success_player.deck.discard_pile),
        "failure_discard": names(failure_player.deck.discard_pile),
    }


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
    assert not result.get("pending_choice"), result
    assert game.event_progress["succeeded"] is True
    progress = game.event_progress
    result = settle_round_event(game, "settle trade war success at round end")
    assert result.get("pending_choice") is True, result
    assert progress["settled"] is True
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
    assert not result.get("pending_choice"), result
    assert game.event_progress["succeeded"] is True
    result = settle_round_event(game, "settle trade war name success at round end")
    assert result.get("pending_choice") is True, result
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_topdeck_from_discard"
    assert names(choice["cards"]) == ["可置頂牌", "英美奧援"], names(choice["cards"])
    return {"event": "貿易戰加劇", "triggered_by": "英美奧援", "choice_key": choice["choice_key"]}


def test_elite_defection_trashes_from_hand_after_three_moves():
    game = make_game("紅軍權貴出逃")
    player = game.players[0]
    player.moves_left = 3
    # Use one organization moving through three currently empty, rebel-applicable towns.
    # Under the one-physical-organization-per-town invariant, pre-seeding every
    # destination would make the old fixture's moves illegal.
    player.organizations = {"天津": 1}
    player.deck.draw_pile = []
    player.hand = [Card("手牌移除目標", "command", {})]
    # keep the discard empty too: with an empty draw pile the refill reshuffles the discard
    # into hand, which would move a discard card into the hand zone before settlement.
    player.deck.discard_pile = []

    assert_ok(game.advance_turn_phase(), "draw elite defection event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.move_organization("天津", "濟南", mode="rail"), "first move")
    assert_ok(game.move_organization("濟南", "青島", mode="rail"), "second move")
    assert_ok(game.move_organization("青島", "南京", mode="road"), "third move")
    assert game.pending_choice is None
    assert game.event_progress["succeeded"] is True
    progress = game.event_progress
    settle_round_event(game, "settle elite defection success at round end")
    assert game.pending_choice is not None
    assert progress["settled"] is True
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "trash_from_hand_or_discard"
    assert choice["cards"] == [
        {"name": "手牌移除目標", "zone": "hand", "zone_label": "手牌"},
    ], choice["cards"]
    resolve = assert_ok(game.resolve_pending_choice(player.id, 0), "trash hand card")
    assert resolve["chosen_card"] == "手牌移除目標"
    assert resolve["zone"] == "hand"
    assert names(player.hand) == []
    assert names(player.deck.discard_pile) == []
    assert resolve["removed_card"]["name"] == "手牌移除目標"
    assert resolve["removed_card"]["zone"] in {"deck_discard", "static_supply", "removed"}
    return {"event": "紅軍權貴出逃", "choice_key": choice["choice_key"], "trashed": resolve["chosen_card"], "zone": resolve["zone"]}


def test_elite_defection_trashes_from_discard_after_three_moves():
    game = make_game("紅軍權貴出逃")
    player = game.players[0]
    player.moves_left = 3
    # Use one organization moving through three currently empty, rebel-applicable towns.
    # Under the one-physical-organization-per-town invariant, pre-seeding every
    # destination would make the old fixture's moves illegal.
    player.organizations = {"天津": 1}
    # give the refill enough draw-pile cards that it never reshuffles the discard pile,
    # so the discard-zone target is still in the discard when the trash choice opens.
    player.deck.draw_pile = [Card(f"補牌{i}", "command", {}) for i in range(1, 5)]
    player.hand = [Card("手牌保留", "command", {})]
    player.deck.discard_pile = [Card("棄牌移除目標", "command", {})]

    assert_ok(game.advance_turn_phase(), "draw elite defection event")
    assert_ok(game.advance_turn_phase(), "enter action")
    assert_ok(game.move_organization("天津", "濟南", mode="rail"), "first move")
    assert_ok(game.move_organization("濟南", "青島", mode="rail"), "second move")
    assert_ok(game.move_organization("青島", "南京", mode="road"), "third move")
    settle_round_event(game, "settle elite defection discard-zone success at round end")
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "trash_from_hand_or_discard"
    discard_index = next(i for i, entry in enumerate(choice["cards"]) if entry["zone"] == "discard" and entry["name"] == "棄牌移除目標")
    resolve = assert_ok(game.resolve_pending_choice(player.id, discard_index), "trash discard card")
    assert resolve["chosen_card"] == "棄牌移除目標"
    assert resolve["zone"] == "discard"
    assert "手牌保留" in names(player.hand)
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
    progress = game.event_progress
    result = settle_round_event(game, "settle end-turn wall org success")
    assert result.get("pending_choice") is True, result
    assert progress["count"] == 1
    assert progress["succeeded"] is True
    assert progress["settled"] is True
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
    assert "保留手牌" in names(player.hand)  # end-turn refill tops the hand up to 5 before settlement
    return {"event": "烏魯木齊七五事件", "trigger_count": progress["count"], "choice_key": choice["choice_key"], "sample_towns": choice_towns[:6], "built": resolve["town"]}


def test_urumqi_end_turn_without_wall_org_fails_random_discard():
    game = make_game("烏魯木齊七五事件")
    player = game.players[0]
    player.organizations = {"臺北": 1}
    player.hand = [Card("會被隨機棄掉", "command", {})]
    # penalty settles after the refill; empty the deck so the single hand card is the target
    player.deck.draw_pile = []
    player.deck.discard_pile = []

    assert_ok(game.advance_turn_phase(), "draw urumqi event")
    assert_ok(game.advance_turn_phase(), "enter action")
    progress = game.event_progress
    settle_round_event(game, "settle end-turn no wall org failure")
    assert progress["count"] == 0
    assert progress["succeeded"] is False
    assert progress["settled"] is True
    assert names(player.hand) == []
    assert names(player.deck.discard_pile)[-1] == "會被隨機棄掉"
    return {"event": "烏魯木齊七五事件", "trigger_count": progress["count"], "discard": names(player.deck.discard_pile)[-1]}


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

    game.event_modifiers = [{"type": "reduce_cost", "amount": 1, "duration": 1, "remaining_turns": 1}]
    assert game._event_reduce_cost_amount() == 1

    game.turn_phase = TurnPhase.END  # buying happens in the END (purchase) phase
    card_index = next(i for i, card in enumerate(game.purchase_area) if getattr(card, "name", "") == "資助者")
    player.resources = {"money": 1, "propaganda": 1}
    assert_ok(game.buy_card(card_index), "buy reduced-cost static card")
    game.turn_phase = TurnPhase.ACTION

    game.event_modifiers = [{"type": "restrict_build", "duration": 1, "remaining_turns": 1}]
    blocked = game.build_organization("臺北")
    assert blocked.get("error") == "Current event restricts building organizations"

    game.event_modifiers = [{"type": "ignore_distance", "duration": 1, "remaining_turns": 1}]
    player.moves_left = 1
    player.organizations["臺北"] = 2
    # 北京 is enemy-occupied (blocked); 馬祖 is rebel-applicable, same wall side, non-adjacent.
    moved = game.move_organization("臺北", "馬祖", mode="road")
    assert_ok(moved, "ignore_distance move")
    return {"reduce_cost_buy": names(player.deck.discard_pile), "restrict_build_error": blocked.get("error"), "ignore_distance_move": moved}


def test_event_modifier_duration_ticks_across_turns():
    game = make_game("歲月靜好")
    player = game.players[0]
    game.turn_phase = TurnPhase.ACTION
    game.current_event = {"id": "duration_test", "name": "持續測試事件", "type": "mission"}
    result = game._apply_event_effect({"type": "reduce_cost", "amount": 1, "duration": 2}, player)
    assert_ok(result, "apply duration modifier")
    assert game.event_modifiers[0]["duration"] == 2
    assert game.event_modifiers[0]["remaining_turns"] == 2
    assert game._event_reduce_cost_amount() == 1

    game._end_turn()
    assert game.event_modifiers[0]["remaining_turns"] == 1
    assert game._event_reduce_cost_amount() == 1

    game.turn_phase = TurnPhase.END
    game._end_turn()
    assert game.event_modifiers == []
    assert game._event_reduce_cost_amount() == 0
    return {"effect": "reduce_cost", "duration": 2, "remaining_after_first_turn": 1, "expired_after_second_turn": True}


def test_event_runtime_primitive_inventory_is_covered():
    game = make_game("歲月靜好")
    event_specs = {event["name"]: event for event in game.structured_events}
    required_triggers = {
        "購買事件 trigger": ("貿易戰加劇", "trigger", "buy_card"),
        "回合結束狀態 trigger": ("烏魯木齊七五事件", "trigger", "end_turn_state"),
    }
    required_effects = {
        "從棄牌堆選牌置頂": ("貿易戰加劇", "success", "topdeck_from_discard"),
        "從手牌/棄牌移除": ("紅軍權貴出逃", "success", "trash_from_hand_or_discard"),
        "卡種/區域/距離限定 modifier": ("上海合作組織", "effect", "scoped_card_range"),
    }
    coverage = {}
    for label, (event_name, field, effect_type) in {**required_triggers, **required_effects}.items():
        spec = event_specs[event_name][field]
        assert spec["type"] == effect_type, {label: spec}
        coverage[label] = {"event": event_name, field: spec}
    duration_spec = event_specs["上海合作組織"]["effect"]
    assert duration_spec["duration"] == 1
    coverage["持續回合 modifier"] = {"event": "上海合作組織", "effect": duration_spec}
    return coverage



def test_event_red_dissolve_ui_reuses_target_map_highlight():
    app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    needle = "targetChoicesWithMapHighlight = new Set("
    assert needle in app_js and "'event_red_dissolve'" in app_js, "event_red_dissolve should reuse existing target choice map highlight pipeline"
    return {
        "choice_key": "event_red_dissolve",
        "highlight_pipeline": "support-targets",
    }

def test_pending_choice_blocks_phase_advance_until_resolved():
    game = make_game("香港抗暴之戰")
    player = game.players[0]
    player.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    assert_ok(game.advance_turn_phase(), "draw hk event")
    assert_ok(game.advance_turn_phase(), "enter action")
    result = settle_round_event(game, "settle failure")
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


def test_belt_road_structured_matches_raw_rule():
    game = make_game("一帶一路 南洋")
    southeast = game._event_by_name("一帶一路 南洋")
    middle_east = game._event_by_name("一帶一路 天方")
    assert southeast["effect"] == {
        "type": "build_organization_in_region",
        "count": 1,
        "player_faction": "red_army",
        "region": "southeast_asia",
        "free": True,
        "ignore_distance": True,
    }
    assert middle_east["effect"] == {
        "type": "build_organization_in_region",
        "count": 1,
        "player_faction": "red_army",
        "region": "middle_east",
        "free": True,
        "ignore_distance": True,
    }
    return {"events": {southeast["name"]: southeast["effect"], middle_east["name"]: middle_east["effect"]}}


def test_belt_road_southeast_waits_until_red_turn_then_builds_in_region():
    game = make_game("一帶一路 南洋")
    viewer = game.players[0]
    red = game.players[1]
    game.current_player_index = 0
    game.round_start_player_index = 0
    viewer.organizations = {"臺北": 1}
    red.organizations = {"北京": 1}
    red.hand = [Card("紅軍保留手牌", "command", {})]

    assert_ok(game.advance_turn_phase(), "draw belt road southeast event on non-red turn")
    assert game.current_event["name"] == "一帶一路 南洋"
    assert game.event_progress["status"] == "auto_pending"
    assert game.event_progress["auto_target_player_id"] == red.id
    assert game.state()["pending_choice"] is None

    assert_ok(game.advance_turn_phase(), "non-red enters action without resolving red effect")
    assert game.turn_phase == TurnPhase.ACTION
    assert_ok(game.advance_turn_phase(), "non-red ends turn and red event effect becomes pending")
    assert game.current_player() is red
    # Current model: the turn opens in ACTION; the deferred red auto-effect is applied via
    # _apply_auto_event_if_ready during the turn handoff and raises the pending choice.
    assert game.turn_phase == TurnPhase.ACTION
    assert game.event_progress["status"] == "auto"

    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_build_organization"
    assert choice["player_id"] == red.id
    assert choice["region"] == "southeast_asia"
    towns = [item["town"] for item in choice["towns"]]
    assert "新加坡" in towns, towns
    assert "喀布爾" not in towns, towns
    assert "河內" not in towns, towns  # 南洋但非紅軍可發展城鎮，不應放行。
    idx = towns.index("新加坡")
    resolve = assert_ok(game.resolve_pending_choice(red.id, idx), "build free southeast org")
    assert resolve["town"] == "新加坡"
    assert red.organizations.get("新加坡") == 1
    assert names(red.hand) == ["紅軍保留手牌"]
    return {"event": "一帶一路 南洋", "status_before_red_turn": "auto_pending", "choice_key": choice["choice_key"], "region": choice["region"], "sample_towns": towns[:8], "built": resolve["town"]}


def test_belt_road_middle_east_auto_builds_red_org_in_region():
    game = make_game("一帶一路 天方")
    red = game.players[1]
    game.current_player_index = 1
    red.organizations = {"北京": 1}
    assert_ok(game.advance_turn_phase(), "draw belt road middle east event")
    assert game.current_event["name"] == "一帶一路 天方"
    choice = game.state()["pending_choice"]
    assert choice["choice_key"] == "event_build_organization"
    assert choice["player_id"] == red.id
    assert choice["region"] == "middle_east"
    towns = [item["town"] for item in choice["towns"]]
    assert "喀布爾" in towns, towns
    assert "新加坡" not in towns, towns
    assert "伊斯坦堡" not in towns, towns  # 天方但非紅軍可發展城鎮，不應放行。
    idx = towns.index("喀布爾")
    resolve = assert_ok(game.resolve_pending_choice(red.id, idx), "build free middle east org")
    assert red.organizations.get("喀布爾") == 1
    return {"event": "一帶一路 天方", "choice_key": choice["choice_key"], "region": choice["region"], "sample_towns": towns[:8], "built": resolve["town"]}


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
        test_event_mission_triggers_ignore_red_army_actor,
        test_remaining_six_event_structured_matches_raw_rules,
        test_national_people_congress_faction_ability_success_draws,
        test_national_people_congress_failure_red_dissolves_wall_org_only,
        test_tibet_border_build_wall_org_grants_two_moves,
        test_east_turkestan_success_and_failure_paths,
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
        test_belt_road_structured_matches_raw_rule,
        test_belt_road_southeast_waits_until_red_turn_then_builds_in_region,
        test_belt_road_middle_east_auto_builds_red_org_in_region,
        test_event_deck_uses_declared_counts_without_structured_duplicate_overcount,
        test_trade_war_structured_matches_raw_rule,
        test_event_modifiers_are_consumed_by_runtime_rules,
        test_event_modifier_duration_ticks_across_turns,
        test_event_runtime_primitive_inventory_is_covered,
        test_event_red_dissolve_ui_reuses_target_map_highlight,
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
