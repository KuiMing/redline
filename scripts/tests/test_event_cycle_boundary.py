"""A mission event is settled once, when the whole round that follows its reveal is complete.

The window opens when the event is revealed and covers every player (Red Army included) taking
exactly one full turn in the table's own seat order. The last seat's turn end is the same
authoritative boundary as the round wrap: that is where the personal outcomes are judged, any
queued choice is fully resolved, and only then does the next round / next event start. Red Army's
seat never moves the window, the start player or the settlement point. See rules.md「任務事件」.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase

FACTIONS = {'Ben': 'aomen', 'Angie': 'mongol', 'Cy': 'liberals', 'Red': 'red_army'}
BASES = {'Ben': '澳門', 'Angie': '烏蘭巴托', 'Cy': '臺北', 'Red': '北京'}


def card(name):
    return Card(name, 'command', {})


def make_game(event_names, seats, ai_red=False, extra_orgs=None):
    """Seats in table order, exactly as the lobby would pass them (no seat rotation)."""
    players = [(f'{n.lower()}-id', n) for n in seats]
    game = Game(players, market_mode='all_cards', factions={f'{n.lower()}-id': FACTIONS[n] for n in seats})
    for player in game.players:
        player.base = BASES[player.name]
        player.organizations = {player.base: 1}
        player.organizations.update((extra_orgs or {}).get(player.name, {}))
        player.resources = {'money': 0, 'propaganda': 0}
        player.hand = [card(f'{player.name}手牌{i}') for i in range(5)]
        player.deck.draw_pile = [card(f'{player.name}補牌{i}') for i in range(12)]
        player.deck.discard_pile = [card(f'{player.name}棄牌{i}') for i in range(3)]
    if ai_red:
        game.ai_red_army_player_id = next(p.id for p in game.players if p.name == 'Red')
    game.pending_base_choices = {}
    game.game_phase = GamePhase.MAIN
    game.event_deck.draw_pile = [game._event_by_name(n) for n in reversed(event_names)]
    game.event_deck.discard_pile = []
    game.current_event = None
    game.pending_choice = None
    game.turn_log = game._new_turn_log()
    game.action_log = []
    game._start_event_phase()
    game.turn_phase = TurnPhase.ACTION
    return game


def end_turn(game):
    game.turn_phase = TurnPhase.ACTION
    return game.advance_turn_phase()


def by_name(game, name):
    return next(p for p in game.players if p.name == name)


def real_card(game, name):
    definition = next(c for c in game.structured_cards if c['name'] == name)
    return Card(definition['name'], definition['type'], definition.get('resources', {}))


def resolve_all(game):
    count = 0
    while game.pending_choice:
        count += 1
        assert count < 20
        assert game.resolve_pending_choice(game.pending_choice['player_id'], [0]).get('success')
    return count


def play_round(game, seats):
    """Walk one full round and assert nothing settles before the last seat ends."""
    progress = game.event_progress
    start_index = game.round_start_player_index
    turn_before = game.turn
    acted = []
    for position, name in enumerate(seats):
        assert game.current_player().name == name
        acted.append(name)
        assert progress['settled'] is False and not progress.get('settlement_started')
        result = end_turn(game)
        if position < len(seats) - 1:
            assert result == {'success': True}
            assert progress['settled'] is False and not progress.get('settlement_started')
            assert game.turn == turn_before
        else:
            assert progress['settlement_started'] is True
    assert acted == list(seats)                                # exactly one turn each, table order
    assert game.round_start_player_index == start_index        # the start player never moved
    return progress, turn_before


SEAT_ORDERS = [
    ('Red', 'Ben'),
    ('Ben', 'Red'),
    ('Red', 'Ben', 'Angie'),
    ('Ben', 'Red', 'Angie'),
    ('Ben', 'Angie', 'Red'),
    ('Red', 'Ben', 'Angie', 'Cy'),
    ('Ben', 'Red', 'Angie', 'Cy'),
    ('Ben', 'Angie', 'Red', 'Cy'),
    ('Ben', 'Angie', 'Cy', 'Red'),
]


@pytest.mark.parametrize('ai_red', [False, True], ids=['human_red', 'ai_red'])
@pytest.mark.parametrize('seats', SEAT_ORDERS)
def test_every_player_acts_once_in_table_order_before_the_event_settles(seats, ai_red):
    game = make_game(['重大災難', '歲月靜好'], seats, ai_red=ai_red)
    non_red = [n for n in seats if n != 'Red']
    # Red's seat never rotates the start: the round opens at the table's first seat.
    assert game.round_start_player_index == 0
    assert game.current_player().name == seats[0]

    progress, turn_before = play_round(game, seats)

    # Last seat ended: everybody failed, so each non-Red player owes a discard; the round has
    # not wrapped and the seat has not been handed over while those choices are open.
    assert game.pending_choice is not None
    assert game.turn == turn_before
    assert game.current_player().name == seats[-1]
    assert end_turn(game).get('error')                           # no skipping past the pending queue
    assert game.current_event['name'] == '重大災難'
    assert resolve_all(game) == len(non_red)

    assert progress['settled'] is True
    assert game.turn == turn_before + 1                          # wrapped exactly once
    assert game.current_event['name'] == '歲月靜好'                 # next event only after settlement
    assert game.current_player().name == seats[0]               # same start player, no extra turn
    assert game.round_start_player_index == 0


def test_ben_red_angie_angie_can_still_succeed_and_ben_gets_no_second_turn():
    game = make_game(['重大災難', '歲月靜好'], ('Ben', 'Red', 'Angie'))
    ben, red, angie = game.players
    progress = game.event_progress
    entries = progress['player_progress']
    turn = game.turn

    assert game.current_player() is ben
    assert end_turn(game) == {'success': True}                  # Ben
    assert game.current_player() is red
    assert end_turn(game) == {'success': True}                  # Red: window is NOT over
    assert game.current_player() is angie
    assert progress['settled'] is False and not progress.get('settlement_started')
    assert entries[angie.id]['met'] is False

    angie.hand.append(real_card(game, '宣傳家'))
    assert game.play_card(len(angie.hand) - 1, mode='resource').get('success')
    assert entries[angie.id]['met'] is True                     # Angie achieves it on her own turn
    assert progress['settled'] is False

    result = end_turn(game)                                      # Angie = last seat -> settle
    assert result.get('pending_choice') is True
    assert entries[angie.id]['result'] == 'success'
    assert entries[ben.id]['result'] == 'failure'
    assert red.id not in entries                                # Red is no mission participant
    assert (game.pending_choice['choice_key'], game.pending_choice['player_id']) == ('event_discard_self', ben.id)
    assert game.current_player() is angie and game.turn == turn
    assert resolve_all(game) == 1

    assert game.turn == turn + 1
    assert game.current_event['name'] == '歲月靜好'
    assert game.current_player() is ben                         # Ben only now acts again (new event)


def test_red_last_still_settles_at_red_end_which_is_the_round_end():
    game = make_game(['重大災難', '歲月靜好'], ('Ben', 'Angie', 'Red'))
    progress, turn = play_round(game, ('Ben', 'Angie', 'Red'))
    assert resolve_all(game) == 2
    assert progress['settled'] is True and game.turn == turn + 1


def test_next_event_gets_its_own_full_round_window():
    game = make_game(['重大災難', '重大災難'], ('Ben', 'Red', 'Angie'))
    first_progress, turn = play_round(game, ('Ben', 'Red', 'Angie'))
    resolve_all(game)
    second_progress = game.event_progress
    assert second_progress is not first_progress and second_progress['settled'] is False

    second_progress, turn2 = play_round(game, ('Ben', 'Red', 'Angie'))
    assert turn2 == turn + 1
    resolve_all(game)
    assert second_progress['settled'] is True and game.turn == turn2 + 1


def test_no_legal_target_failure_settles_without_pending_state_at_the_last_seat():
    # 全國人大召開 failure = Red dissolves one of the loser's 牆內 organizations; nobody has one.
    game = make_game(['全國人大召開', '歲月靜好'], ('Ben', 'Red', 'Angie'))
    progress = game.event_progress
    turn = game.turn
    assert end_turn(game) == {'success': True}
    assert end_turn(game) == {'success': True}
    assert progress['settled'] is False
    assert end_turn(game) == {'success': True}                  # nothing to choose: skipped
    assert progress['settled'] is True and progress['status'] == 'failure'
    assert game.pending_choice is None
    assert game.turn == turn + 1 and game.current_event['name'] == '歲月靜好'
    assert game.current_player().name == 'Ben'


def test_pending_choice_from_the_last_seat_is_never_overwritten_by_the_next_event():
    game = make_game(['重大災難', '歲月靜好'], ('Red', 'Ben', 'Angie'))
    for _ in range(3):
        end_turn(game)
    first_choice = game.pending_choice
    assert first_choice is not None and game.current_event['name'] == '重大災難'
    assert game.event_progress['settlement_started'] is True
    assert end_turn(game).get('error')
    assert game.pending_choice is first_choice


@pytest.mark.parametrize('seats', [('Ben', 'Red', 'Angie'), ('Red', 'Ben', 'Angie'), ('Ben', 'Angie', 'Red')])
def test_mongol_school_trigger_from_a_red_action_counts_for_the_owner_at_round_end(seats):
    game = make_game(['全國人大召開', '歲月靜好'], seats, extra_orgs={'Angie': {'西安': 1}})
    ben, angie, red = by_name(game, 'Ben'), by_name(game, 'Angie'), by_name(game, 'Red')
    entries = game.event_progress['player_progress']
    progress = game.event_progress

    for name in seats:
        player = game.current_player()
        assert player.name == name
        if name == 'Ben':
            result = game._activated_faction_action(ben, '賭徒耳語', guess='odd')
            assert not result.get('error'), result
            if game.pending_choice:
                assert game.resolve_pending_choice(ben.id, 0).get('success')
        if name == 'Red':
            red.hand = [card('紅軍代價手牌')]
            result = game.dissolve_organization(red, angie, '西安', source='faction_action')
            assert result.get('success') is True
            assert entries[angie.id]['met'] is True               # credited to the ability owner
        assert progress['settled'] is False and not progress.get('settlement_started')
        result = end_turn(game)
        assert result == {'success': True}, result

    assert red.id not in entries
    assert entries[ben.id]['result'] == 'success'
    assert entries[angie.id]['result'] == 'success'               # not Red's / not lost by seat order
    assert progress['status'] == 'success' and progress['settled'] is True
    assert game.pending_choice is None
    assert game.current_event['name'] == '歲月靜好'
