from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
