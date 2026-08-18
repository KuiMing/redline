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


def test_end_turn_waits_for_hong_kong_relocation_decision_before_next_player_starts():
    game, hk, red = make_game()
    hk.hand = [Card('合作談判', 'command', {})]
    game.current_event = game._event_by_name('香港抗暴之戰')
    game.event_progress = {
        'count': 0,
        'required': 1,
        'succeeded': False,
        'settled': False,
        'status': 'active',
        'settlement_target_player_id': hk.id,
    }

    ended = game.advance_turn_phase()

    assert ended.get('pending_choice') is True
    assert game.current_player() is hk
    assert game.turn_phase == TurnPhase.END
    assert game.pending_choice.get('choice_key') == 'event_discard_self'
    assert game.hk_free_base_relocation is False

    discarded = game.resolve_pending_choice(hk.id, [0])

    assert discarded.get('success') is True
    assert game.current_player() is hk
    assert game.hk_free_base_relocation is True

    relocated = game.relocate_hong_kong_base(hk.id, '臺北')

    assert relocated.get('success') is True
    assert game.current_player() is red
    assert game.turn_phase == TurnPhase.ACTION


def test_successful_event_also_waits_for_keep_decision_before_next_player_starts():
    game, hk, red = make_game()
    game.current_event = game._event_by_name('香港抗暴之戰')
    game.event_progress = {
        'count': 1,
        'required': 1,
        'succeeded': True,
        'settled': False,
        'status': 'success_pending',
        'settlement_target_player_id': hk.id,
    }

    ended = game.advance_turn_phase()

    assert ended.get('pending_hk_relocation') is True
    assert game.current_player() is hk
    assert game.turn_phase == TurnPhase.END
    assert game.hk_free_base_relocation is True
    assert game.advance_turn_phase() == {
        'error': '請先決定香港根據地要遷移至何處，或選擇留在目前根據地'
    }

    kept = game.keep_hong_kong_base(hk.id)

    assert kept == {'success': True, 'kept': '香港城'}
    assert game.current_player() is red
    assert game.turn_phase == TurnPhase.ACTION


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
