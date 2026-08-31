from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def make_purchase_game():
    game = Game([('p1', 'P1'), ('p2', 'P2')])
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.END
    game.current_player_index = 0
    game.pending_base_choices = {}
    game.current_event = dict(game._event_by_name('歲月靜好') or {})
    game.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    game.event_modifiers = []
    game.pending_choice = None
    return game


def card_names(cards):
    return [getattr(card, 'name', str(card)) for card in cards]


def test_buy_cards_purchases_static_and_random_cards_as_one_batch():
    game = make_purchase_game()
    player = game.current_player()
    player.resources = {'money': 20, 'propaganda': 20}
    static_name = game.purchase_area[0].name
    random_name = game.purchase_area[6].name
    static_supply_before = game.static_purchase_supply[static_name]
    purchase_count_before = len(game.purchase_area)
    payments = [game._purchase_payment_cost(player, game.purchase_area[index]) for index in (0, 6)]
    expected_payment = {
        'money': sum(payment['money'] for payment in payments),
        'propaganda': sum(payment['propaganda'] for payment in payments),
    }

    result = game.buy_cards([0, 6])

    assert result.get('success') is True, result
    assert result.get('purchased_cards') == [static_name, random_name]
    assert result.get('payment') == expected_payment
    assert player.resources == {
        'money': 20 - expected_payment['money'],
        'propaganda': 20 - expected_payment['propaganda'],
    }
    assert card_names(player.deck.discard_pile)[-2:] == [static_name, random_name]
    assert game.static_purchase_supply[static_name] == static_supply_before - 1
    assert len(game.purchase_area) == purchase_count_before - 1


def test_buy_cards_rejects_unaffordable_batch_without_partial_mutation():
    game = make_purchase_game()
    player = game.current_player()
    player.resources = {'money': 0, 'propaganda': 7}
    resources_before = dict(player.resources)
    discard_before = list(player.deck.discard_pile)
    supply_before = dict(game.static_purchase_supply)

    result = game.buy_cards([0, 1])

    assert result.get('error') == 'Not enough resources'
    assert player.resources == resources_before
    assert player.deck.discard_pile == discard_before
    assert game.static_purchase_supply == supply_before


def test_buy_cards_rejects_duplicate_or_invalid_indices():
    game = make_purchase_game()

    assert game.buy_cards([0, 0]).get('error') == 'Duplicate purchase index'
    assert game.buy_cards([999]).get('error') == 'Invalid index'
    assert game.buy_cards([]).get('error') == 'No cards selected'


def test_purchase_state_exposes_actual_payment_costs_for_batch_totals():
    game = make_purchase_game()
    player = game.current_player()
    player.faction_id = 'falun_gong'
    player.resources = {'money': 9, 'propaganda': 0}

    state = game.state(player.id)

    assert state['purchase_area_costs'][0] == {'money': 0, 'propaganda': 3}
    assert state['purchase_area_payments'][0] == {'money': 3, 'propaganda': 0}
    assert state['purchase_area_affordable'][0] is True


def make_flexible_payment_game(base='倫敦', resources=None):
    game = make_purchase_game()
    player = game.current_player()
    player.faction_id = 'hong_kong'
    player.base = base
    player.resources = dict(resources or {'money': 3, 'propaganda': 2})
    game.turn_log = game._new_turn_log()
    game.action_log = []
    return game, player


def test_international_line_uses_propaganda_first_and_money_only_for_shortfall():
    game, player = make_flexible_payment_game(resources={'money': 3, 'propaganda': 2})

    result = game.buy_card(1)  # 思想家：5 宣傳

    assert result == {
        'success': True,
        'purchased_cards': ['思想家'],
        'payment': {'money': 3, 'propaganda': 2},
    }
    assert player.resources == {'money': 0, 'propaganda': 0}
    assert sum('triggered 國際線' in entry for entry in game.action_log) == 1


def test_chinese_language_media_uses_the_same_flexible_payment_policy():
    game, player = make_flexible_payment_game(resources={'money': 3, 'propaganda': 2})
    player.faction_id = 'falun_gong'
    player.base = '紐約'

    result = game.buy_card(1)

    assert result['payment'] == {'money': 3, 'propaganda': 2}
    assert player.resources == {'money': 0, 'propaganda': 0}
    assert sum('triggered 華文傳媒' in entry for entry in game.action_log) == 1


def test_international_line_does_not_trigger_when_propaganda_covers_cost():
    game, player = make_flexible_payment_game(resources={'money': 9, 'propaganda': 5})
    tracked_triggers = []
    original_track = game._track_event_progress

    def track(trigger_type, *args, **kwargs):
        tracked_triggers.append(trigger_type)
        return original_track(trigger_type, *args, **kwargs)

    game._track_event_progress = track

    result = game.buy_card(1)

    assert result['payment'] == {'money': 0, 'propaganda': 5}
    assert player.resources == {'money': 9, 'propaganda': 0}
    assert not any('triggered 國際線' in entry for entry in game.action_log)
    assert 'use_faction_ability' not in tracked_triggers


def test_international_line_rejects_combined_shortfall_atomically():
    game, player = make_flexible_payment_game(resources={'money': 2, 'propaganda': 2})
    resources_before = dict(player.resources)
    discard_before = list(player.deck.discard_pile)
    supply_before = dict(game.static_purchase_supply)

    result = game.buy_card(1)

    assert result == {'error': 'Not enough resources'}
    assert player.resources == resources_before
    assert player.deck.discard_pile == discard_before
    assert game.static_purchase_supply == supply_before
    assert not game.action_log


def test_international_line_is_inactive_away_from_london():
    game, player = make_flexible_payment_game(base='香港城', resources={'money': 5, 'propaganda': 0})

    result = game.buy_card(1)

    assert result == {'error': 'Not enough resources'}
    assert player.resources == {'money': 5, 'propaganda': 0}


def test_international_line_allocates_shared_resources_once_across_batch():
    game, player = make_flexible_payment_game(resources={'money': 3, 'propaganda': 3})
    game.purchase_area[1] = Card('宣傳家', 'propaganda', {})

    result = game.buy_cards([0, 1])

    assert result['payment'] == {'money': 3, 'propaganda': 3}
    assert player.resources == {'money': 0, 'propaganda': 0}
    assert sum('triggered 國際線' in entry for entry in game.action_log) == 1


def test_flexible_payment_preserves_original_money_cost():
    game, player = make_flexible_payment_game(resources={'money': 4, 'propaganda': 1})
    card = Card('混合費用宣傳牌', 'propaganda', {})

    allocation = game._allocate_purchase_payments(
        player,
        [card],
        [{'money': 2, 'propaganda': 3}],
    )

    assert allocation['success'] is True
    assert allocation['payments'] == [{'money': 4, 'propaganda': 1}]
    assert allocation['payment'] == {'money': 4, 'propaganda': 1}


def test_flexible_payment_applies_to_propaganda_cost_on_non_propaganda_card_type():
    game, player = make_flexible_payment_game(resources={'money': 2, 'propaganda': 0})
    card = Card('思想建設', 'command', {})

    allocation = game._allocate_purchase_payments(
        player,
        [card],
        [{'money': 1, 'propaganda': 1}],
    )

    assert allocation['success'] is True
    assert allocation['payments'] == [{'money': 2, 'propaganda': 0}]
    assert allocation['substitution_money'] == [1]


def test_purchase_state_projects_resource_aware_payment_and_explicit_policy():
    game, player = make_flexible_payment_game(resources={'money': 3, 'propaganda': 2})

    state = game.state(player.id)

    assert state['purchase_area_costs'][1] == {'money': 0, 'propaganda': 5}
    assert state['purchase_area_payments'][1] == {'money': 3, 'propaganda': 2}
    assert state['purchase_area_affordable'][1] is True
    assert state['purchase_payment_policy'] == {
        'type': 'propaganda_then_money_shortfall',
        'active': True,
        'ability_name': '國際線',
        'eligible_cost': 'propaganda',
        'allocation_scope': 'batch',
    }


def test_ordinary_player_payment_projection_is_unchanged():
    game = make_purchase_game()
    player = game.current_player()
    player.resources = {'money': 9, 'propaganda': 9}

    state = game.state(player.id)

    assert state['purchase_area_payments'][1] == {'money': 0, 'propaganda': 5}
    assert state['purchase_payment_policy']['active'] is False
