import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game


def _national_people_congress_game():
    game = Game([
        ('ben', 'BEN'),
        ('other', 'OTHER'),
        ('red', 'RED'),
    ])
    ben, other, red = game.players
    ben.faction_id = 'taiwan_green'
    ben.base = '臺北'
    ben.organizations = {'臺北': 1, '上海': 1}
    other.faction_id = 'hong_kong'
    other.base = '香港城'
    other.organizations = {'香港城': 1}
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}

    event = game._event_by_name('全國人大召開')
    game.event_deck.draw_pile = [event]
    game.event_deck.discard_pile = []
    game._start_event_phase()
    return game, ben, other, red


def test_national_people_congress_requires_every_non_red_player_once():
    game, ben, other, _red = _national_people_congress_game()

    assert game.event_progress['required'] == 2
    assert game.event_progress['count'] == 0
    payload = game._event_display_payload()
    assert payload is not None
    assert payload['trigger_text'] == '每位非紅軍玩家各自使用或觸發陣營特殊能力至少 1 次'

    game._track_event_progress('use_faction_ability', player=ben)
    game._track_event_progress('use_faction_ability', player=ben)
    game._track_event_progress('use_faction_ability', player=_red)
    game._track_event_progress('use_faction_ability')

    assert game.event_progress['count'] == 1
    assert game.event_progress['succeeded'] is False
    assert game.event_progress['completed_player_ids'] == [ben.id]

    game._track_event_progress('use_faction_ability', player=other)

    assert game.event_progress['count'] == 2
    assert game.event_progress['succeeded'] is True
    assert set(game.event_progress['completed_player_ids']) == {ben.id, other.id}


def test_national_people_congress_judges_each_non_red_player_individually():
    game, ben, other, red = _national_people_congress_game()
    other_hand_before = len(other.hand)

    game._track_event_progress('use_faction_ability', player=other)
    settlement = game._settle_current_event()

    # `other` triggered an ability -> own success (draws 1); ben did not -> own failure.
    assert game.event_progress['player_progress'][other.id]['result'] == 'success'
    assert game.event_progress['player_progress'][ben.id]['result'] == 'failure'
    # Results are applied one player at a time in seat order: ben's pending decision holds
    # other's reward in the queue.
    assert len(other.hand) == other_hand_before
    assert settlement.get('pending_choice') is True
    assert game.pending_choice['player_id'] == red.id
    assert game.pending_choice['choice_key'] == 'event_red_dissolve'
    # Red only dissolves the failed player's own organizations (never the successful one's).
    assert {target['player_id'] for target in game.pending_choice['targets']} == {ben.id}

    resolved = game.resolve_pending_choice(red.id, 0)

    assert resolved.get('success') is True
    assert len(other.hand) == other_hand_before + 1
    assert game.event_progress['settled'] is True
    assert game.event_progress['status'] == 'mixed'
    assert other.organizations == {'香港城': 1}
