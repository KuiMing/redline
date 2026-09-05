from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.cards import Card
from server.game_market_transactions import (
    purchase_payment_policy,
    allocate_purchase_payments,
)


def _new_game():
    return Game([("p1", "A"), ("p2", "B")])


def test_purchase_payment_policy_matches_game_method_when_inactive():
    game = _new_game()
    player = game.players[0]
    assert game._purchase_payment_policy(player) == purchase_payment_policy(lambda name: False)


def test_purchase_payment_policy_prefers_first_matching_ability():
    policy = purchase_payment_policy(lambda name: name in ("華文傳媒", "國際線"))
    assert policy == {
        'type': 'propaganda_then_money_shortfall',
        'active': True,
        'ability_name': '華文傳媒',
        'eligible_cost': 'propaganda',
        'allocation_scope': 'batch',
    }
    policy2 = purchase_payment_policy(lambda name: name == "國際線")
    assert policy2['ability_name'] == '國際線'
    assert policy2['active'] is True


def test_allocate_purchase_payments_matches_game_method_money_only():
    game = _new_game()
    player = game.players[0]
    player.resources = {'money': 5, 'propaganda': 5}
    card = Card("武裝者", "armed", {})
    cost = game._effective_purchase_cost(player, card)
    expected = game._allocate_purchase_payments(player, [card], [cost])
    policy = game._purchase_payment_policy(player)
    actual = allocate_purchase_payments(player.resources, policy, [card], [cost])
    assert actual == expected


def test_allocate_purchase_payments_inactive_policy_pays_printed_costs():
    inactive_policy = purchase_payment_policy(lambda name: False)
    resources = {'money': 10, 'propaganda': 10}
    costs = [{'money': 2, 'propaganda': 1}]
    result = allocate_purchase_payments(resources, inactive_policy, ['card'], costs)
    assert result['success'] is True
    assert result['payments'] == [{'money': 2, 'propaganda': 1}]
    assert result['substitution_money'] == [0]


def test_allocate_purchase_payments_substitutes_propaganda_when_active():
    active_policy = purchase_payment_policy(lambda name: name == "國際線")
    resources = {'money': 10, 'propaganda': 1}
    costs = [{'money': 2, 'propaganda': 3}]
    result = allocate_purchase_payments(resources, active_policy, ['card'], costs)
    # 3 propaganda cost, only 1 available -> 1 covered by propaganda, 2 shortfall to money.
    assert result['payments'] == [{'money': 4, 'propaganda': 1}]
    assert result['substitution_money'] == [2]
    assert result['success'] is True


def test_allocate_purchase_payments_shares_propaganda_across_batch_in_order():
    active_policy = purchase_payment_policy(lambda name: name == "國際線")
    resources = {'money': 0, 'propaganda': 3}
    costs = [{'money': 0, 'propaganda': 2}, {'money': 0, 'propaganda': 2}]
    result = allocate_purchase_payments(resources, active_policy, ['a', 'b'], costs)
    # First card takes 2 propaganda, second only has 1 left -> 1 shortfall to money.
    assert result['payments'] == [
        {'money': 0, 'propaganda': 2},
        {'money': 1, 'propaganda': 1},
    ]


def test_allocate_purchase_payments_reports_failure_when_insufficient():
    inactive_policy = purchase_payment_policy(lambda name: False)
    resources = {'money': 1, 'propaganda': 0}
    costs = [{'money': 2, 'propaganda': 0}]
    result = allocate_purchase_payments(resources, inactive_policy, ['card'], costs)
    assert result['success'] is False


def test_allocate_purchase_payments_rejects_mismatched_lengths():
    policy = purchase_payment_policy(lambda name: False)
    try:
        allocate_purchase_payments({'money': 0, 'propaganda': 0}, policy, ['a', 'b'], [{}])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for mismatched cards/effective_costs length")
