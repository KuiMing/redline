import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, TurnPhase


def make_red_game():
    game = Game([("red", "紅軍"), ("lib", "自由派"), ("hk", "香港")], market_mode="all_cards")
    red, liberals, hong_kong = game.players
    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    liberals.faction_id = "liberals"
    liberals.base = "香港城"
    liberals.organizations = {}
    hong_kong.faction_id = "hong_kong"
    hong_kong.base = "香港城"
    hong_kong.organizations = {}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game.pending_choice = None
    return game, red, liberals, hong_kong


def unavailable_result(result, ability_name, reason):
    payload = result.get("result") or {}
    assert result.get("error") is None
    assert payload.get("name") == ability_name
    assert payload.get("unavailable") is True
    assert payload.get("reason") == reason
    assert payload.get("message")
    return payload


def assert_not_consumed(game):
    assert game._red_army_action_count() == 0
    assert game.pending_choice is None


def test_united_front_reshuffles_discard_pile_before_drawing():
    game, red, _, _ = make_red_game()
    red.hand = []
    red.deck.draw_pile = []
    red.deck.discard_pile = [Card("棄牌補牌", "money", {"money": 1})]

    result = game._activated_faction_action(red, "統戰部")

    assert result == {"success": True, "result": {"name": "統戰部", "drawn": 1}}
    assert [card.name for card in red.hand] == ["棄牌補牌"]
    assert red.deck.discard_pile == []
    assert game._red_army_action_count() == 1


def test_propaganda_department_reports_when_card_supplies_are_empty():
    game, red, _, _ = make_red_game()
    game.static_purchase_supply["內鬥"] = 0
    game.static_purchase_supply["分神"] = 0

    result = game._activated_faction_action(red, "政工部")

    payload = unavailable_result(result, "政工部", "no_topdeck_supply")
    assert "內鬥" in payload["message"] and "分神" in payload["message"]
    assert_not_consumed(game)


def test_state_security_reports_when_no_organization_can_be_dissolved():
    game, red, _, _ = make_red_game()

    result = game._activated_faction_action(red, "國安部")

    payload = unavailable_result(result, "國安部", "no_dissolve_target")
    assert "沒有可以瓦解的組織" in payload["message"]
    assert_not_consumed(game)


def test_ccdi_reports_when_there_is_no_hand_card_to_exchange():
    game, red, _, _ = make_red_game()
    red.hand = []
    red.deck.draw_pile = [Card("補牌", "money", {"money": 1})]

    result = game._activated_faction_action(red, "中紀委")

    payload = unavailable_result(result, "中紀委", "no_hand_cards")
    assert "沒有手牌可以棄掉" in payload["message"]
    assert_not_consumed(game)


def test_unavailable_ability_does_not_open_a_cancel_reaction_window():
    game, red, _, _ = make_red_game()

    def unexpected_reaction_prompt(*_args, **_kwargs):
        raise AssertionError("An unavailable ability must stop before reaction prompting")

    game._red_army_action_reaction_prompt = unexpected_reaction_prompt
    result = game._activated_faction_action(red, "國安部")

    unavailable_result(result, "國安部", "no_dissolve_target")
    assert_not_consumed(game)
