import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def _make_four_player_urumqi_game():
    game = Game([
        ('first', '第一位反共'),
        ('second', '第二位反共'),
        ('third', '第三位反共'),
        ('red', '紅軍'),
    ])
    first, second, third, red = game.players
    for player, faction, base in (
        (first, 'hong_kong', '香港城'),
        (second, 'taiwan_green', '臺北'),
        (third, 'tibet', '達蘭薩拉'),
        (red, 'red_army', '北京'),
    ):
        player.faction_id = faction
        player.base = base
        player.organizations = {base: 1}
        player.hand = [Card(f'{player.name}手牌', 'command', {})]
    game.pending_base_choices = {}
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 3
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.END
    game.current_event = game._event_by_name('烏魯木齊七五事件')
    game.event_progress = {
        'count': 0,
        'required': 1,
        'succeeded': False,
        'settled': False,
        'status': 'active',
        'settlement_target_player_id': third.id,
    }
    game.pending_choice = None
    game.event_deck.draw_pile = []
    game.event_deck.discard_pile = []
    return game, first, second, third, red


def test_urumqi_success_queues_one_build_for_each_qualifying_non_red_player():
    game, first, second, third, red = _make_four_player_urumqi_game()
    inside_towns = game._towns_for_region_alias('china')
    found_origins = None
    for first_origin in inside_towns:
        for second_origin in inside_towns:
            if second_origin == first_origin:
                continue
            first.organizations = {first_origin: 1}
            second.organizations = {second_origin: 1}
            third.organizations = {'臺北': 1}
            if game._event_build_towns_near_own(first) and game._event_build_towns_near_own(second):
                found_origins = (first_origin, second_origin)
                break
        if found_origins:
            break
    assert found_origins is not None
    third.organizations = {'臺北': 1}
    before_first = first.total_organizations()
    before_second = second.total_organizations()
    before_third = third.total_organizations()

    settlement = game._settle_current_event()

    assert settlement.get('pending_choice') is True
    assert game.event_progress['qualified_player_ids'] == [first.id, second.id]
    assert game.pending_choice.get('player_id') == first.id
    assert game.pending_choice.get('source_name') == '烏魯木齊七五事件'

    first_result = game.resolve_pending_choice(first.id, 0)

    assert first_result.get('pending_choice') is True
    assert game.pending_choice.get('player_id') == second.id
    assert game.pending_choice.get('source_name') == '烏魯木齊七五事件'

    second_result = game.resolve_pending_choice(second.id, 0)

    assert second_result.get('success') is True
    assert game.pending_choice is None
    assert first.total_organizations() == before_first + 1
    assert second.total_organizations() == before_second + 1
    assert third.total_organizations() == before_third
    assert red.total_organizations() == 1


def test_urumqi_failure_randomly_discards_from_every_non_red_player_only():
    game, first, second, third, red = _make_four_player_urumqi_game()
    outside_towns = [town for town in game.map.get('towns', {}) if not game._is_inside_wall_town(town)]
    assert len(outside_towns) >= 3
    first.organizations = {outside_towns[0]: 1}
    second.organizations = {outside_towns[1]: 1}
    third.organizations = {outside_towns[2]: 1}

    game._settle_current_event()

    assert game.event_progress['qualified_player_ids'] == []
    assert game.event_progress['status'] == 'failure'
    assert len(first.hand) == 0
    assert len(second.hand) == 0
    assert len(third.hand) == 0
    assert len(red.hand) == 1


def test_elite_defection_trash_choice_hides_private_hand_candidates_from_other_players():
    game, first, second, _third, red = _make_four_player_urumqi_game()
    game.current_event = game._event_by_name('紅軍權貴出逃')
    game.event_progress = {
        'count': 3,
        'required': 3,
        'succeeded': True,
        'settled': False,
        'status': 'success_pending',
        'last_actor_id': first.id,
    }
    first.hand = [Card('秘密手牌', 'command', {})]
    first.deck.discard_pile = [Card('公開棄牌', 'command', {})]

    settlement = game._settle_current_event()

    assert settlement.get('pending_choice') is True
    assert game.state(first.id)['pending_choice']['cards']
    assert game.state(second.id)['pending_choice']['cards'] == []
    assert game.state(red.id)['pending_choice']['cards'] == []
    assert '秘密手牌' not in str(game.state(second.id)['pending_choice'])
