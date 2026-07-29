from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def make_game():
    game = Game([('red', 'Red'), ('taiwan_green', 'Taiwan')])
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.players[0].faction_id = 'red_army'
    game.players[1].faction_id = 'taiwan_green'
    game.pending_base_choices = {}
    noop_event = game._event_by_name('歲月靜好')
    game.current_event = dict(noop_event or {})
    game.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    game.event_modifiers = []
    game.pending_choice = None
    return game


def action_card(game, name):
    definition = next(card for card in game.structured_cards if card['name'] == name)
    return Card(definition['name'], definition['type'], definition.get('resources', {}))


def card_names(cards):
    return [getattr(card, 'name', str(card)) for card in cards]


def test_end_turn_logs_reshuffle_only_when_refill_exhausts_draw_pile():
    enough = make_game()
    player = enough.current_player()
    player.hand = [Card(f'保留{i}', 'command', {}) for i in range(4)]
    player.deck.draw_pile = [Card('牌庫保留牌', 'command', {})]
    player.deck.discard_pile = [Card('棄牌唯一一張', 'command', {})]
    enough._end_turn()
    assert not any('牌庫用盡' in line and '洗牌' in line for line in enough.action_log)

    exhausted = make_game()
    player = exhausted.current_player()
    player.hand = [Card(f'保留{i}', 'command', {}) for i in range(4)]
    player.deck.draw_pile = []
    player.deck.discard_pile = [Card('棄牌唯一一張', 'command', {})]
    exhausted._end_turn()
    assert any('牌庫用盡' in line and '將棄牌堆 1 張牌洗成新牌庫' in line for line in exhausted.action_log)


def test_red_end_turn_preserves_discard_when_draw_pile_can_complete_refill():
    game = make_game()
    red = game.current_player()
    red.hand = [Card('保留手牌', 'command', {})]
    red.deck.draw_pile = [Card(f'抽牌{i}', 'command', {}) for i in range(1, 5)]
    red.deck.discard_pile = [Card('既有棄牌A', 'command', {}), Card('既有棄牌B', 'command', {})]
    before_total = len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile)

    game._end_turn()

    assert len(red.hand) == 5
    assert card_names(red.deck.discard_pile) == ['既有棄牌A', '既有棄牌B']
    assert len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile) == before_total


def test_red_end_turn_reshuffles_discard_only_after_draw_pile_is_exhausted_and_conserves_cards():
    game = make_game()
    red = game.current_player()
    red.hand = [Card('保留手牌', 'command', {})]
    red.deck.draw_pile = [Card('牌庫最後一張', 'command', {})]
    red.deck.discard_pile = [Card(f'棄牌{i}', 'command', {}) for i in range(1, 5)]
    before_total = len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile)

    game._end_turn()

    assert len(red.hand) == 5
    assert len(red.deck.draw_pile) == 1
    assert red.deck.discard_pile == []
    assert len(red.hand) + len(red.deck.draw_pile) + len(red.deck.discard_pile) == before_total


def test_taiwan_support_counts_as_prior_propaganda_cost_card_for_ignite_passion():
    game = make_game()
    red = game.current_player()
    red.hand = [game._make_support_card('臺灣奧援', variant_index=0), action_card(game, '點燃熱情')]
    red.deck.draw_pile = [Card('抽牌底', 'command', {}), Card('抽牌一', 'command', {}), Card('抽牌二', 'command', {})]

    support_result = game.play_card(0, mode='action')
    assert support_result.get('success'), support_result
    assert game.pending_choice is None

    ignite_result = game.play_card(0, mode='action')
    assert ignite_result.get('success'), ignite_result
    assert card_names(red.hand) == ['抽牌二', '抽牌一']


def test_north_support_initial_choice_can_be_cancelled_without_spending_card_or_mutating_board():
    game = make_game()
    red, opponent = game.players
    red.organizations = {'北京': 1}
    opponent.organizations = {'天津': 1}
    north_support = game._make_support_card('北國奧援', variant_index=0)
    red.hand = [north_support]
    red.deck.discard_pile = []

    play_result = game.play_card(0, mode='action')

    assert play_result.get('pending_choice') is True, play_result
    assert game.pending_choice and game.pending_choice.get('cancellable') is True
    assert game.state(red.id)['pending_choice']['cancellable'] is True
    assert red.hand == []
    assert red.deck.discard_pile == [north_support]
    assert red.organizations == {'北京': 1}
    assert opponent.organizations == {'天津': 1}

    cancel_result = game.cancel_pending_choice(red.id)

    assert cancel_result.get('success') is True, cancel_result
    assert game.pending_choice is None
    assert red.hand == [north_support]
    assert red.deck.discard_pile == []
    assert red.organizations == {'北京': 1}
    assert opponent.organizations == {'天津': 1}
    assert game.turn_log['played_money_card'] is False
    assert game.turn_log['played_propaganda_card'] is False


def test_discard_state_preserves_support_variant_for_full_card_preview():
    game = make_game()
    red = game.current_player()
    support = game._make_support_card('臺灣奧援', variant_index=1)
    red.deck.discard_pile = [action_card(game, '點燃熱情'), support]

    red_state = next(player for player in game.state(red.id)['players'] if player['id'] == red.id)

    assert red_state['discard_pile'] == ['點燃熱情', '臺灣奧援']
    assert red_state['discard_variants'][0] is None
    assert red_state['discard_variants'][1]['variant_index'] == 1


def test_multiple_propagandists_accumulate_build_entitlements_and_resolve_two_builds():
    game = make_game()
    red = game.current_player()
    game.players[1].organizations = {}
    red.organizations = {'臺北': 1}
    red.hand = [action_card(game, '宣傳家'), action_card(game, '宣傳家')]

    first_play = game.play_card(0, mode='action')
    assert first_play.get('pending_choice') is True, first_play
    assert game.pending_choice and game.pending_choice['source_name'] == '宣傳家'
    assert game.state(red.id)['pending_choice']['remaining_builds'] == 1

    second_play = game.play_card(0, mode='action')
    assert second_play.get('pending_choice') is True, second_play
    assert game.pending_choice and game.pending_choice['remaining_builds'] == 2
    assert game.state(red.id)['pending_choice']['remaining_builds'] == 2

    first_towns = [entry['town'] for entry in game.pending_choice['towns']]
    first_town = first_towns[0]
    first_build = game.resolve_pending_choice(red.id, 0)
    assert first_build.get('pending_choice') is True, first_build
    assert first_build.get('remaining_builds') == 1
    assert red.organizations[first_town] == 1
    assert red.moves_left == 1
    assert game.pending_choice and game.pending_choice['remaining_builds'] == 1

    second_towns = [entry['town'] for entry in game.pending_choice['towns']]
    assert first_town not in second_towns
    second_town = second_towns[0]
    second_build = game.resolve_pending_choice(red.id, 0)
    assert second_build.get('remaining_builds') == 0, second_build
    assert game.pending_choice is None
    assert red.organizations[second_town] == 1
    assert red.moves_left == 2
    assert len(red.organizations) == 3


def test_north_support_tier_three_resolves_two_targets_and_only_initial_step_is_cancellable():
    game = make_game()
    red, opponent = game.players
    red.organizations = {'北京': 1}
    opponent.organizations = {'天津': 1, '石家莊': 1}
    red.hand = [game._make_support_card('北國奧援', variant_index=0)]
    game._support_card_tier = lambda player, card: (3, 0, ['北國'])

    play_result = game.play_card(0, mode='action')
    assert play_result.get('pending_choice') is True, play_result
    assert game.pending_choice and game.pending_choice.get('cancellable') is True
    assert len(game.pending_choice['targets']) == 2

    first_result = game.resolve_pending_choice(red.id, 0)
    assert first_result.get('pending_choice') is True, first_result
    assert first_result.get('remaining_count') == 1
    assert game.pending_choice and game.pending_choice.get('cancellable') is not True
    assert game.cancel_pending_choice(red.id).get('error') == 'This choice cannot be cancelled'
    assert sum(opponent.organizations.values()) == 1

    second_result = game.resolve_pending_choice(red.id, 0)
    assert second_result.get('success') is True, second_result
    assert game.pending_choice is None
    assert opponent.organizations == {}
