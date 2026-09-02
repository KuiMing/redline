from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.cards import Card
from server.game_market_cost_rules import (
    support_card_cost,
    card_purchase_cost,
    event_reduce_cost_amount,
    armory_purchase_cost_reduction,
    era_purchase_cost_reduction,
    purchase_area_card_cost_total,
    purchase_area_card_cost_money,
    top_card_cost_total,
)


def _new_game():
    return Game([("p1", "A"), ("p2", "B")])


def test_support_card_cost_matches_game_method():
    game = _new_game()
    for entry in game.support_taxonomy[:10]:
        name = entry.get("name")
        assert game._support_card_cost(name) == support_card_cost(game.support_taxonomy, name)


def test_card_purchase_cost_matches_game_method_for_action_and_support_cards():
    game = _new_game()
    armed = Card("武裝者", "armed", {})
    support = Card("英美奧援", "support", {})
    unknown = Card("不存在的卡", "command", {})
    for card in (armed, support, unknown):
        assert game._card_purchase_cost(card) == card_purchase_cost(
            game.structured_cards, game.support_taxonomy, card
        )
    assert game._card_purchase_cost(armed) == {"money": 2, "propaganda": 0}
    assert game._card_purchase_cost(unknown) == {"money": 0, "propaganda": 0}


def test_event_reduce_cost_amount_matches_game_method():
    game = _new_game()
    assert game._event_reduce_cost_amount() == 0 == event_reduce_cost_amount(
        game._active_event_modifiers()
    )
    game.event_modifiers = [
        {"type": "reduce_cost", "amount": 2, "remaining_turns": 1},
        {"type": "reduce_cost", "amount": 1, "remaining_turns": 1},
        {"type": "restrict_build", "amount": 99, "remaining_turns": 1},
        {"type": "reduce_cost", "amount": 5, "remaining_turns": 0},  # expired, excluded
    ]
    assert game._event_reduce_cost_amount() == 3 == event_reduce_cost_amount(
        game._active_event_modifiers()
    )


def test_armory_purchase_cost_reduction_matches_game_method():
    game = _new_game()
    player = game.players[0]
    armed = Card("武裝者", "armed", {})
    non_armed = Card("宣傳家", "propaganda", {})
    armory_towns = [
        town for town, info in game.map.get("towns", {}).items()
        if info.get("type") == "軍火庫"
    ]
    assert len(armory_towns) >= 4, "expected at least 4 armory towns in map data for this test"

    # Non-armed card: never reduced regardless of organizations.
    player.organizations = {armory_towns[0]: 1}
    assert game._armory_purchase_cost_reduction(player, non_armed) == 0 == \
        armory_purchase_cost_reduction(game.map, non_armed, player.organizations)

    # One armory town owned -> reduction of 1.
    assert game._armory_purchase_cost_reduction(player, armed) == 1 == \
        armory_purchase_cost_reduction(game.map, armed, player.organizations)

    # Four+ armory towns owned -> capped at 3.
    player.organizations = {town: 1 for town in armory_towns[:4]}
    assert game._armory_purchase_cost_reduction(player, armed) == 3 == \
        armory_purchase_cost_reduction(game.map, armed, player.organizations)


def test_era_purchase_cost_reduction_matches_game_method_with_no_active_effects():
    game = _new_game()
    player = game.players[0]
    armed = Card("武裝者", "armed", {})
    assert game._era_purchase_cost_reduction(player, armed) == {"money": 0, "propaganda": 0}


def test_era_purchase_cost_reduction_pure_function_applies_matching_effects_only():
    armed = Card("武裝者", "armed", {})
    propaganda_card = Card("宣傳家", "propaganda", {})
    active_era_effects = [
        (
            {"id": "test_era"},
            "red",
            {
                "type": "reduce_purchase_cost",
                "target_camp": "紅軍",
                "card_types": ["armed"],
                "resource": "money",
                "amount": 2,
            },
        ),
        (
            {"id": "test_era"},
            "red",
            {"type": "some_other_effect", "amount": 99},
        ),
    ]
    # Matching camp + card type -> reduction applies.
    assert era_purchase_cost_reduction(active_era_effects, "紅軍", "red_army", armed) == {
        "money": 2,
        "propaganda": 0,
    }
    # Wrong camp -> no reduction.
    assert era_purchase_cost_reduction(active_era_effects, "臺灣", "taiwan", armed) == {
        "money": 0,
        "propaganda": 0,
    }
    # Right camp, wrong card type -> no reduction.
    assert era_purchase_cost_reduction(active_era_effects, "紅軍", "red_army", propaganda_card) == {
        "money": 0,
        "propaganda": 0,
    }


def test_purchase_area_card_cost_total_and_money_and_top_card_match_game_methods():
    game = _new_game()
    for name in ("武裝者", "宣傳家", "英美奧援"):
        card = Card(name, "armed", {})
        assert game._purchase_area_card_cost_total(card) == purchase_area_card_cost_total(
            game.structured_cards, game.support_taxonomy, card
        )
        assert game._purchase_area_card_cost_money(card) == purchase_area_card_cost_money(
            game.structured_cards, game.support_taxonomy, card
        )
        assert game._top_card_cost_total(card) == top_card_cost_total(
            game.structured_cards, game.support_taxonomy, card
        )


def test_effective_purchase_cost_still_composes_all_reductions():
    # _effective_purchase_cost itself was NOT moved (it only orchestrates the
    # now-extracted primitives via self._x wrapper calls) — this pins that its
    # behavior is unchanged after the extraction.
    game = _new_game()
    player = game.players[0]
    armed = Card("武裝者", "armed", {})
    assert game._effective_purchase_cost(player, armed) == {"money": 2, "propaganda": 0}

    armory_towns = [
        town for town, info in game.map.get("towns", {}).items()
        if info.get("type") == "軍火庫"
    ]
    player.organizations = {town: 1 for town in armory_towns[:1]}
    assert game._effective_purchase_cost(player, armed) == {"money": 1, "propaganda": 0}

    game.event_modifiers = [{"type": "reduce_cost", "amount": 1, "remaining_turns": 1}]
    assert game._effective_purchase_cost(player, armed) == {"money": 0, "propaganda": 0}
