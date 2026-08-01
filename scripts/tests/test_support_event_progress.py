from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


GENERAL_SUPPORTS = [
    '英美奧援', '東洋奧援', '南洋奧援', '印度奧援',
    '天方奧援', '歐洲奧援', '北國奧援', '臺灣奧援',
]


def make_event_game():
    game = Game([('actor', 'Actor'), ('red', 'Red')])
    actor, red = game.players
    actor.faction_id = 'liberals'
    actor.base = '香港城'
    actor.organizations = {'香港城': 1, '承德': 1}
    actor.deck.draw_pile = []
    actor.deck.discard_pile = []

    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    red.hand = [Card('資助者', 'resource', {'money': 1})]

    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.pending_base_choices = {}
    game.pending_choice = None
    event = game._event_by_name('東突厥集中營')
    assert event is not None
    game.current_event = dict(event)
    game.event_progress = {
        'count': 0,
        'required': 1,
        'succeeded': False,
        'settled': False,
        'status': 'active',
    }
    game.event_notification = game._event_display_payload()
    return game, actor, red


@pytest.mark.parametrize('support_name', GENERAL_SUPPORTS)
def test_every_general_support_counts_for_east_turkestan_propaganda_cost_mission(support_name):
    game, actor, _ = make_event_game()
    actor.hand = [game._make_support_card(support_name, variant_index=0)]
    if support_name == '南洋奧援':
        actor.deck.draw_pile = [Card('資助者', 'resource', {'money': 1})]
    game._support_card_tier = lambda player, card: (1, 0, [])

    result = game.play_card(0, mode='action')

    assert result.get('success') is True, (support_name, result)
    assert game.event_progress['count'] == 1, (support_name, result, game.pending_choice)
    assert game.event_progress['succeeded'] is True
    assert game.event_progress['last_actor_id'] == actor.id


def test_taiwan_support_pending_target_counts_when_card_is_committed():
    game, actor, _ = make_event_game()
    actor.hand = [game._make_support_card('臺灣奧援', variant_index=0)]
    game._support_card_tier = lambda player, card: (2, 0, [])

    result = game.play_card(0, mode='action')

    assert result.get('pending_choice') is True, result
    assert game.pending_choice and game.pending_choice['choice_key'] == 'support_interaction'
    assert game.event_progress['count'] == 1
    assert game.event_progress['succeeded'] is True


def test_rejected_no_target_support_does_not_count_event_progress():
    game, actor, red = make_event_game()
    red.organizations = {}
    actor.hand = [game._make_support_card('臺灣奧援', variant_index=0)]
    game._support_card_tier = lambda player, card: (2, 0, [])

    result = game.play_card(0, mode='action')

    assert result.get('no_legal_target') is True, result
    assert actor.hand and actor.hand[0].name == '臺灣奧援'
    assert game.event_progress['count'] == 0
    assert game.event_progress['succeeded'] is False


def test_cancelled_north_support_rolls_back_event_progress_with_card_and_turn_flags():
    game, actor, _ = make_event_game()
    card = game._make_support_card('北國奧援', variant_index=0)
    actor.hand = [card]
    game._support_card_tier = lambda player, support: (1, 0, [])

    played = game.play_card(0, mode='action')
    assert played.get('pending_choice') is True, played
    assert game.event_progress['count'] == 1

    cancelled = game.cancel_pending_choice(actor.id)

    assert cancelled.get('cancelled') is True, cancelled
    assert actor.hand == [card]
    assert game.event_progress['count'] == 0
    assert game.event_progress['succeeded'] is False
    assert game.event_progress['status'] == 'active'
    notification = game.event_notification
    assert isinstance(notification, dict)
    assert notification['progress']['count'] == 0
    assert notification['progress']['succeeded'] is False


def test_red_support_has_no_purchase_cost_and_does_not_count_mission():
    game, _, red = make_event_game()
    game.current_player_index = 1
    red.hand = [game._make_support_card('紅軍奧援')]
    red.deck.draw_pile = [Card('資助者', 'resource', {'money': 1})]

    result = game.play_card(0, mode='action')

    assert result.get('success') is True, result
    assert game.event_progress['count'] == 0
    assert game.event_progress['succeeded'] is False
