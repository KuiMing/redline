"""Production /start opens each round at the seat right after Red, so Red always acts last.

Drives the real lobby `start_game()` (not a hand-built Game) and walks one full event round:
every seat acts exactly once, Red is last, and the mission settles only after Red ends.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from server import main
from server.game import TurnPhase

FACTIONS = {'Ben': 'aomen', 'Angie': 'mongol', 'Cy': 'liberals', 'Red': 'red_army'}
BASES = {'Ben': '澳門', 'Angie': '烏蘭巴托', 'Cy': '臺北', 'Red': '北京'}


def start_room(seats, ai_red=False, pending=()):
    """seats = table order of the human lobby (join order); AI Red is appended last by /start."""
    client = TestClient(main.app)
    tag = f"{'-'.join(seats)}-{ai_red}"
    created = client.post('/create', json={'name': seats[0], 'device_id': f'seat-{tag}-0'}).json()
    game_id = created['game_id']
    ids = {seats[0]: created['host_id']}
    for index, name in enumerate(seats[1:], start=1):
        ids[name] = client.post('/join', json={
            'game_id': game_id, 'name': name, 'device_id': f'seat-{tag}-{index}'}).json()['player_id']
    if ai_red:
        assert client.post('/ai-red-army', json={
            'game_id': game_id, 'player_id': ids[seats[0]], 'enabled': True}).json().get('success')
    main.lobby_factions[game_id] = {ids[n]: ('uyghur_family' if n in pending else FACTIONS[n]) for n in seats}
    main.lobby_bases[game_id] = {ids[n]: BASES[n] for n in seats if n not in pending}
    main.lobby_ready[game_id] = {ids[n]: True for n in seats}
    result = client.post('/start', json={'game_id': game_id, 'player_id': ids[seats[0]]}).json()
    assert result.get('success') is True, result
    game = main.manager.games[game_id]
    if pending:
        assert game.game_phase.name == 'BASE_SELECTION' and game.pending_base_choices
        assert (game.current_player_index, game.round_start_player_index) == (0, 0)
        for name in pending:
            assert game.set_base_choice(ids[name], '伊斯坦堡' if name == pending[0] else '慕尼黑').get('success')
        assert game.game_phase.name == 'MAIN' and not game.pending_base_choices
    # The opening event is random; pin a mission card so the settlement boundary is observable.
    game.event_deck.draw_pile = [game._event_by_name('重大災難')]
    game.event_deck.discard_pile = []
    game.current_event = None
    game.pending_choice = None
    game._start_event_phase()
    assert game.current_event['name'] == '重大災難'
    return game


def end_turn(game):
    game.turn_phase = TurnPhase.ACTION
    return game.advance_turn_phase()


CASES = [
    (('Red', 'Ben', 'Angie'), 'first', ['Ben', 'Angie', 'Red']),
    (('Ben', 'Red', 'Angie'), 'middle', ['Angie', 'Ben', 'Red']),
    (('Ben', 'Angie', 'Red'), 'last', ['Ben', 'Angie', 'Red']),
    (('Ben', 'Red', 'Angie', 'Cy'), 'middle-4p', ['Angie', 'Cy', 'Ben', 'Red']),
]


def walk_round(game, expected_order):
    progress = game.event_progress
    turn_before = game.turn
    acted = []
    for position, name in enumerate(expected_order):
        assert game.current_player().name == name
        acted.append(name)
        assert not progress.get('settlement_started') and not progress.get('settled')
        end_turn(game)
        if position < len(expected_order) - 1:
            assert game.turn == turn_before
            assert not progress.get('settlement_started') and not progress.get('settled')
    assert acted == expected_order                                # each seat exactly once, Red last
    assert next(p for p in game.players if p.name == acted[-1]).faction_id == 'red_army'
    # Red's turn end is the full-round end: settlement ran and the round wrapped here.
    assert progress.get('settlement_started') or progress.get('settled')
    assert game.turn == turn_before + 1 or game.pending_choice or game.game_phase.name == 'FINISHED'


@pytest.mark.parametrize('seats, label, order', CASES, ids=[c[1] for c in CASES])
def test_start_game_opens_round_after_red_and_settles_after_red(seats, label, order):
    game = start_room(seats)
    assert [p.name for p in game.players] == list(seats)          # circular table order unchanged
    red_index = seats.index('Red')
    start = (red_index + 1) % len(seats)
    assert (game.current_player_index, game.round_start_player_index) == (start, start)
    assert game.current_player().name == order[0]
    walk_round(game, order)


@pytest.mark.parametrize('humans', [('Ben', 'Angie'), ('Ben', 'Angie', 'Cy')], ids=['2h', '3h'])
def test_ai_red_seat_is_appended_last_and_acts_last(humans):
    game = start_room(humans, ai_red=True)
    assert game.players[-1].faction_id == 'red_army'
    assert game.ai_red_army_player_id == game.players[-1].id
    assert (game.current_player_index, game.round_start_player_index) == (0, 0)
    assert game.current_player().name == humans[0]
    walk_round(game, [p.name for p in game.players])


@pytest.mark.parametrize('seats, label, order', CASES, ids=[c[1] for c in CASES])
def test_pending_base_choices_complete_into_round_after_red(seats, label, order):
    game = start_room(seats, pending=('Ben',))
    start = (seats.index('Red') + 1) % len(seats)
    assert (game.current_player_index, game.round_start_player_index) == (start, start)
    assert game.current_player().name == order[0]
    walk_round(game, order)


def test_base_choice_after_setup_does_not_reset_round_in_progress():
    game = start_room(('Ben', 'Red', 'Angie'), pending=('Ben',))
    end_turn(game)                                    # Angie acted; Ben is up
    state = (game.current_player_index, game.round_start_player_index, game.turn)
    assert game.set_base_choice(game.players[0].id, '慕尼黑').get('error')
    assert (game.current_player_index, game.round_start_player_index, game.turn) == state
