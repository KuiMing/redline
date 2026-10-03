import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Card, Game, TurnPhase


def make_game():
    game = Game([('hk', '香港玩家'), ('red', '紅軍玩家')])
    hk, red = game.players
    hk.faction_id = 'hong_kong'
    red.faction_id = 'red_army'
    hk.base = '香港城'
    hk.organizations = {'香港城': 1}
    red.organizations = {}
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()
    game.pending_choice = None
    game.hk_free_base_relocation = False
    return game, hk, red


def make_three_player_game():
    game = Game([('first', '第一位反共'), ('second', '第二位反共'), ('red', '紅軍玩家')])
    first, second, red = game.players
    first.faction_id = 'hong_kong'
    second.faction_id = 'taiwan_green'
    red.faction_id = 'red_army'
    first.base = '香港城'
    second.base = '臺北'
    red.base = '北京'
    first.organizations = {'香港城': 1}
    second.organizations = {'臺北': 1}
    red.organizations = {'北京': 1}
    game.current_player_index = 1
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.END
    game.turn_log = game._new_turn_log()
    game.pending_choice = None
    game.hk_free_base_relocation = False
    return game, first, second, red


def make_interleaved_three_player_game():
    game = Game([('first', '第一位反共'), ('red', '紅軍玩家'), ('second', '第二位反共')])
    first, red, second = game.players
    first.faction_id = 'hong_kong'
    red.faction_id = 'red_army'
    second.faction_id = 'taiwan_green'
    first.base = '香港城'
    red.base = '北京'
    second.base = '臺北'
    first.organizations = {'香港城': 1}
    red.organizations = {'北京': 1}
    second.organizations = {'臺北': 1}
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.END
    game.turn_log = game._new_turn_log()
    game.pending_choice = None
    game.hk_free_base_relocation = False
    return game, first, red, second


def settle_event(game, name='香港抗暴之戰', succeeded=False):
    game.current_event = {
        'name': name,
        'type': 'mission',
        'trigger': {'type': 'play_card_with_money', 'count': 1},
        'success': {'type': 'none'},
        'failure': {'type': 'none'},
    }
    game.event_progress = {
        'count': 1 if succeeded else 0,
        'required': 1,
        'succeeded': succeeded,
        'settled': False,
        'status': 'active',
    }
    return game._settle_current_event()


def test_exact_hong_kong_event_name_opens_free_window_on_success_and_failure():
    failure_game, _, _ = make_game()
    success_game, _, _ = make_game()
    old_wrong_name_game, _, _ = make_game()

    settle_event(failure_game, succeeded=False)
    settle_event(success_game, succeeded=True)
    settle_event(old_wrong_name_game, name='香港抗爭之烈', succeeded=True)

    assert failure_game.hk_free_base_relocation is True
    assert success_game.hk_free_base_relocation is True
    assert old_wrong_name_game.hk_free_base_relocation is False


def test_failed_event_opens_relocation_only_after_required_discard_resolves():
    game, hk, _ = make_game()
    hk.hand = [Card('合作談判', 'command', {}), Card('追隨者', 'propaganda', {'propaganda': 1})]
    game.current_event = game._event_by_name('香港抗暴之戰')
    game.event_progress = {
        'count': 0,
        'required': 1,
        'succeeded': False,
        'settled': False,
        'status': 'active',
    }

    settlement = game._settle_current_event()

    assert settlement.get('pending_choice') is True
    assert game.pending_choice.get('choice_key') == 'event_discard_self'
    assert game.hk_free_base_relocation is False

    resolved = game.resolve_pending_choice(hk.id, [0])

    assert resolved.get('success') is True
    assert game.pending_choice is None
    assert game.hk_free_base_relocation is True
    assert game.relocate_hong_kong_base(hk.id, '倫敦').get('success') is True


def end_turn(game):
    """The current seat presses 結束行動階段."""
    game.turn_phase = TurnPhase.ACTION
    return game.advance_turn_phase()


def end_turns_through_red(game):
    """End every seat's turn up to and including the Red Army seat. Returns the Red Army
    seat's own end-turn result (earlier non-red seats must have ended without any event
    settlement, so their results are plain successes)."""
    for _ in range(len(game.players)):
        was_red = game.current_player().faction_id == 'red_army'
        result = end_turn(game)
        if was_red:
            return result
        assert result == {'success': True}
        assert not game.event_progress['settled']
        assert not game.event_progress.get('settlement_started')
    raise AssertionError('red seat never ended its turn')


def pin_hong_kong_event(game, name='香港抗暴之戰'):
    game.current_event = game._event_by_name(name)
    game.event_progress = game._new_event_progress(game.current_event)
    return game.event_progress


def test_end_turn_waits_for_hong_kong_relocation_decision_before_next_player_starts():
    game, hk, red = make_game()
    hk.hand = [Card('合作談判', 'command', {})]
    pin_hong_kong_event(game)

    ended = end_turns_through_red(game)

    assert ended.get('pending_choice') is True
    assert game.current_player() is red
    assert game.turn_phase == TurnPhase.END
    assert game.pending_choice.get('choice_key') == 'event_discard_self'
    assert game.pending_choice.get('player_id') == hk.id
    assert game.hk_free_base_relocation is False

    discarded = game.resolve_pending_choice(hk.id, [0])

    assert discarded.get('success') is True
    assert game.current_player() is red
    assert game.hk_free_base_relocation is True
    assert game.hk_relocation_blocks_turn_handoff is True

    relocated = game.relocate_hong_kong_base(hk.id, '臺北')

    assert relocated.get('success') is True
    assert game.current_player() is hk
    assert game.turn_phase == TurnPhase.ACTION


def test_three_player_failure_makes_each_non_red_player_discard_before_hong_kong_relocation():
    game, first, second, red = make_three_player_game()
    game.current_player_index = 0
    first.hand = [Card('第一位手牌', 'command', {})]
    second.hand = [Card('第二位手牌', 'command', {})]
    pin_hong_kong_event(game)

    ended = end_turns_through_red(game)

    assert ended.get('pending_choice') is True
    assert game.current_player() is red
    assert game.pending_choice.get('choice_key') == 'event_discard_self'
    assert game.pending_choice.get('player_id') == first.id

    first_discarded = game.resolve_pending_choice(first.id, [0])

    assert first_discarded.get('pending_choice') is True
    assert game.pending_choice.get('player_id') == second.id
    assert game.hk_free_base_relocation is False

    second_discarded = game.resolve_pending_choice(second.id, [0])

    assert second_discarded.get('success') is True
    assert game.pending_choice is None
    assert len(first.deck.discard_pile) == 1
    assert len(second.deck.discard_pile) == 1
    assert len(red.deck.discard_pile) == 0
    assert game.hk_free_base_relocation is True
    assert game.current_player() is red

    assert game.keep_hong_kong_base(first.id) == {'success': True, 'kept': '香港城'}
    assert game.current_player() is first
    assert game.turn_phase == TurnPhase.ACTION


def test_interleaved_red_seat_settles_when_the_red_seat_ends_not_at_a_later_non_red_seat():
    game, first, red, second = make_interleaved_three_player_game()
    first.hand = [Card('第一位手牌', 'command', {})]
    second.hand = [Card('第二位手牌', 'command', {})]
    pin_hong_kong_event(game)

    # first (before red) ends: nothing settles.
    assert end_turn(game) == {'success': True}
    assert game.current_player() is red
    assert game.pending_choice is None
    assert game.event_progress['settled'] is False

    # The Red Army seat ending is the one settlement boundary, even though `second` still has
    # a seat later in the round.
    assert end_turn(game).get('pending_choice') is True
    assert game.current_player() is red
    assert game.pending_choice.get('player_id') == first.id
    assert game.resolve_pending_choice(first.id, [0]).get('pending_choice') is True
    assert game.pending_choice.get('player_id') == second.id
    assert game.resolve_pending_choice(second.id, [0]).get('success') is True
    assert game.event_progress['settled'] is True
    assert game.hk_free_base_relocation is True
    assert game.current_player() is red

    assert game.keep_hong_kong_base(first.id).get('success') is True
    assert game.current_player() is second


def test_event_discard_choice_hides_each_players_hand_from_other_viewers():
    game, first, second, red = make_three_player_game()
    game.current_player_index = 0
    first.hand = [Card('第一位秘密手牌', 'command', {})]
    second.hand = [Card('第二位秘密手牌', 'command', {})]
    pin_hong_kong_event(game)

    assert end_turns_through_red(game).get('pending_choice') is True
    # Each seat's own end-turn refill topped the hand up to 5 before the Red Army seat settled.
    assert '第一位秘密手牌' in game.state(first.id)['pending_choice']['cards']
    assert game.state(second.id)['pending_choice']['cards'] == []
    assert game.state(red.id)['pending_choice']['cards'] == []
    assert '第一位秘密手牌' not in str(game.state(second.id)['pending_choice'])

    assert game.resolve_pending_choice(first.id, [0]).get('pending_choice') is True
    assert '第二位秘密手牌' in game.state(second.id)['pending_choice']['cards']
    assert game.state(first.id)['pending_choice']['cards'] == []
    assert game.state(red.id)['pending_choice']['cards'] == []
    assert '第二位秘密手牌' not in str(game.state(first.id)['pending_choice'])


def test_other_discard_self_event_failures_also_penalize_every_non_red_player():
    for event_name in ('重大災難', '紅軍權貴出逃'):
        game, first, second, red = make_three_player_game()
        game.current_player_index = 0
        first.hand = [Card(f'{event_name}第一位手牌', 'command', {})]
        second.hand = [Card(f'{event_name}第二位手牌', 'command', {})]
        pin_hong_kong_event(game, event_name)

        assert end_turns_through_red(game).get('pending_choice') is True
        assert game.current_player() is red
        assert game.pending_choice.get('player_id') == first.id
        assert game.resolve_pending_choice(first.id, [0]).get('pending_choice') is True
        assert game.pending_choice.get('player_id') == second.id
        assert game.resolve_pending_choice(second.id, [0]).get('success') is True
        assert game.pending_choice is None
        assert len(first.deck.discard_pile) == 1
        assert len(second.deck.discard_pile) == 1
        assert len(red.deck.discard_pile) == 0
        assert game.hk_free_base_relocation is False


def test_successful_event_also_waits_for_keep_decision_before_next_player_starts():
    game, hk, red = make_game()
    pin_hong_kong_event(game)
    game._track_event_progress('play_card_with_money', player=hk)
    assert game.event_progress['player_progress'][hk.id]['met'] is True

    ended = end_turns_through_red(game)

    assert ended.get('pending_hk_relocation') is True
    assert game.current_player() is red
    assert game.turn_phase == TurnPhase.END
    assert game.hk_free_base_relocation is True
    assert game.advance_turn_phase() == {
        'error': '請先決定香港根據地要遷移至何處，或選擇留在目前根據地'
    }

    kept = game.keep_hong_kong_base(hk.id)

    assert kept == {'success': True, 'kept': '香港城'}
    assert game.current_player() is hk


def test_free_relocation_to_existing_own_organization_promotes_it_to_base_without_removing_old_organization():
    game, hk, _ = make_game()
    hk.organizations = {'香港城': 1, '臺北': 1}
    settle_event(game)
    before_total = hk.total_organizations()

    result = game.relocate_hong_kong_base(hk.id, '臺北')

    assert result == {'success': True, 'from': '香港城', 'to': '臺北', 'free': True}
    assert hk.base == '臺北'
    assert hk.organizations == {'香港城': 1, '臺北': 1}
    assert hk.total_organizations() == before_total
    assert game.hk_free_base_relocation is False


def test_free_forward_base_move_consumes_window_without_spending_moves_and_switches_ability():
    game, hk, _ = make_game()
    settle_event(game)
    hk.moves_left = 0

    result = game.relocate_hong_kong_base(hk.id, '倫敦')

    assert result == {'success': True, 'from': '香港城', 'to': '倫敦', 'free': True}
    assert hk.base == '倫敦'
    assert hk.organizations == {'倫敦': 1}
    assert hk.moves_left == 0
    assert game.hk_free_base_relocation is False
    assert game._player_has_ability(hk, '國際線') is True
    assert game._player_has_ability(hk, '安全屋') is False


def test_airport_cannot_be_used_as_paid_base_relocation_without_event_window():
    game, hk, _ = make_game()
    hk.moves_left = 9

    result = game.relocate_hong_kong_base(hk.id, '臺北')

    assert result == {'error': '香港抗暴之戰尚未完成結算，沒有免費遷移根據地的機會'}
    assert hk.base == '香港城'
    assert hk.organizations == {'香港城': 1}
    assert hk.moves_left == 9


def test_keep_hong_kong_base_consumes_free_window():
    game, hk, _ = make_game()
    settle_event(game)

    result = game.keep_hong_kong_base(hk.id)

    assert result == {'success': True, 'kept': '香港城'}
    assert game.hk_free_base_relocation is False
    assert hk.base == '香港城'
    assert hk.organizations == {'香港城': 1}


def test_occupied_forward_base_is_blocked_without_consuming_window():
    game, hk, red = make_game()
    settle_event(game)
    red.organizations = {'多倫多': 1}

    result = game.relocate_hong_kong_base(hk.id, '多倫多')

    assert result == {'error': 'Cannot relocate base into occupied town'}
    assert game.hk_free_base_relocation is True
    assert hk.base == '香港城'


def test_free_window_closes_when_next_round_event_starts():
    game, hk, _ = make_game()
    settle_event(game)

    game._start_event_phase()
    result = game.relocate_hong_kong_base(hk.id, '卡加利')

    assert game.hk_free_base_relocation is False
    assert result == {'error': '香港抗暴之戰尚未完成結算，沒有免費遷移根據地的機會'}
