from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def action_card(game, name):
    definition = next(card for card in game.structured_cards if card['name'] == name)
    return Card(definition['name'], definition['type'], definition.get('resources', {}))


def make_game():
    game = Game([('actor', 'Actor'), ('enemy', 'Enemy')])
    actor, enemy = game.players
    actor.faction_id = 'liberals'
    actor.base = '香港城'
    actor.organizations = {'香港城': 1}
    enemy.faction_id = 'red_army'
    enemy.base = '北京'
    enemy.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.pending_base_choices = {}
    game.pending_choice = None
    noop = game._event_by_name('歲月靜好')
    game.current_event = dict(noop or {})
    game.event_progress = {'count': 0, 'required': 0, 'succeeded': True, 'settled': True, 'status': 'idle'}
    game.event_notification = game._event_display_payload()
    return game, actor


def choose_town(game, player, town=None):
    choices = game.pending_choice['towns']
    index = 0 if town is None else next(i for i, entry in enumerate(choices) if entry['town'] == town)
    chosen = choices[index]['town']
    result = game.resolve_pending_choice(player.id, index)
    return chosen, result


@pytest.mark.parametrize(
    ('second_name', 'expected_builds'),
    [
        ('宣傳家', 2),
        ('思想家', 2),
        ('組織經驗丙', 2),
        ('組織經驗乙', 3),
        ('組織經驗甲', 2),
    ],
)
def test_every_action_card_with_a_printed_build_effect_can_join_the_queue(second_name, expected_builds):
    game, actor = make_game()
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, second_name)]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    initial_pending = game.state(actor.id)['pending_choice']
    assert initial_pending['queueable_card_names'] == [second_name]
    enemy_state = game.state(game.players[1].id)
    assert enemy_state['pending_choice']['queueable_card_names'] == []
    queued = game.play_card(0, mode='action')

    assert queued.get('pending_choice') is True, (second_name, queued)
    assert game.pending_choice['choice_key'] == 'card_build_organization'
    projected = game.state(actor.id)['pending_choice']
    assert projected['remaining_builds'] == expected_builds
    assert projected['queueable_card_names'] == []


def test_org_experience_c_and_b_can_be_played_before_resolving_three_fifo_builds():
    game, actor = make_game()
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, '組織經驗乙')]

    first = game.play_card(0, mode='action')
    assert first.get('pending_choice') is True, first
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 1

    second = game.play_card(0, mode='action')
    assert second.get('pending_choice') is True, second
    assert actor.hand == []
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 3

    built = []
    for expected_remaining in (2, 1, 0):
        town, result = choose_town(game, actor)
        built.append(town)
        assert result.get('remaining_builds') == expected_remaining, result
        projected = game.state(actor.id).get('pending_choice') or {}
        assert projected.get('remaining_builds', 0) == expected_remaining

    assert len(set(built)) == 3
    assert game.pending_choice is None
    assert len(actor.organizations) == 4
    assert [card.name for card in actor.deck.discard_pile] == ['組織經驗丙', '組織經驗乙']


def test_queued_build_uses_each_cards_own_range_and_recomputes_targets():
    game, actor = make_game()
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, '組織經驗甲')]

    first = game.play_card(0, mode='action')
    assert first.get('pending_choice') is True
    near_towns = {entry['town'] for entry in game.pending_choice['towns']}

    second = game.play_card(0, mode='action')
    assert second.get('pending_choice') is True, second
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 2

    first_town, first_result = choose_town(game, actor)
    assert first_result.get('remaining_builds') == 1
    assert first_town not in {entry['town'] for entry in game.pending_choice['towns']}
    far_towns = {entry['town'] for entry in game.pending_choice['towns']}
    assert far_towns - near_towns, (near_towns, far_towns)

    second_town, second_result = choose_town(game, actor, sorted(far_towns - near_towns)[0])
    assert second_result.get('remaining_builds') == 0
    assert game.pending_choice is None
    assert actor.organizations[first_town] == 1
    assert actor.organizations[second_town] == 1


def test_queue_stops_cleanly_when_organization_supply_is_exhausted():
    game, actor = make_game()
    supply_limit = actor.total_organizations() + 1
    game._org_supply_limit = lambda player: supply_limit
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, '組織經驗乙')]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    assert game.play_card(0, mode='action').get('pending_choice') is True
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 3

    _, result = choose_town(game, actor)

    assert result.get('no_more_valid_towns') is True, result
    assert result.get('remaining_builds_unresolved') == 2
    assert game.pending_choice is None
    assert game._has_org_supply(actor) is False


def test_static_thinker_build_queues_with_its_own_followup_move():
    game, actor = make_game()
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, '思想家')]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    second = game.play_card(0, mode='action')

    assert second.get('pending_choice') is True, second
    assert game.pending_choice['choice_key'] == 'card_build_organization'
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 2
    near_towns = {entry['town'] for entry in game.pending_choice['towns']}
    _, first_result = choose_town(game, actor)
    assert first_result.get('remaining_builds') == 1
    far_towns = {entry['town'] for entry in game.pending_choice['towns']}
    assert far_towns - near_towns
    _, second_result = choose_town(game, actor, sorted(far_towns - near_towns)[0])
    assert second_result.get('remaining_builds') == 0
    assert actor.moves_left == 3


def test_stacked_card_with_no_legal_build_is_rejected_and_keeps_original_active_choice():
    game, actor = make_game()
    actor.hand = [action_card(game, '組織經驗甲'), action_card(game, '組織經驗丙')]
    near_effect = {'type': 'build', 'range': 1}
    near_towns = game._card_build_town_choices(actor, near_effect)
    enemy = game.players[1]
    enemy.organizations = {entry['town']: 1 for entry in near_towns}

    first = game.play_card(0, mode='action')
    assert first.get('pending_choice') is True, first
    original_towns = [entry['town'] for entry in game.pending_choice['towns']]
    assert original_towns

    second = game.play_card(0, mode='action')

    assert second == {
        'error': '目前沒有城鎮可以建立組織。',
        'no_legal_build_town': True,
        'card_name': '組織經驗丙',
    }
    assert game.pending_choice['source_name'] == '組織經驗甲'
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 1
    assert [entry['town'] for entry in game.pending_choice['towns']] == original_towns
    assert [card.name for card in actor.hand] == ['組織經驗丙']
    assert [card.name for card in actor.deck.discard_pile] == ['組織經驗甲']


def test_org_experience_a_repeat_prompt_resumes_later_queued_card_when_declined():
    game, actor = make_game()
    actor.hand = [
        action_card(game, '組織經驗甲'),
        action_card(game, '組織經驗丙'),
        action_card(game, '資本家'),
    ]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    assert game.play_card(0, mode='action').get('pending_choice') is True
    _, first_build = choose_town(game, actor)
    assert first_build.get('pending_choice') is True
    assert game.pending_choice['choice_key'] == 'org_exp_repeat_prompt'

    declined = game.resolve_pending_choice(actor.id, 0)

    assert declined.get('pending_choice') is True, declined
    assert game.pending_choice['choice_key'] == 'card_build_organization'
    assert game.pending_choice['source_name'] == '組織經驗丙'
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 1
    _, second_build = choose_town(game, actor)
    assert second_build.get('remaining_builds') == 0
    assert game.pending_choice is None


def test_non_build_card_remains_blocked_while_build_queue_is_pending():
    game, actor = make_game()
    actor.hand = [action_card(game, '組織經驗丙'), Card('追隨者', 'propaganda', {'propaganda': 1})]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    blocked = game.play_card(0, mode='resource')

    assert blocked.get('error') == 'Please resolve the pending choice first'
    assert [card.name for card in actor.hand] == ['追隨者']
