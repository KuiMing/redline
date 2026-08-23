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


def choose_target(game, player, town=None):
    choices = game.pending_choice['targets']
    index = 0 if town is None else next(i for i, entry in enumerate(choices) if entry['town'] == town)
    chosen = choices[index]['town']
    result = game.resolve_pending_choice(player.id, index)
    return chosen, result


def make_dissolve_game():
    game, actor = make_game()
    actor.faction_id = 'taiwan'
    actor.base = '臺北'
    actor.organizations = {'臺北': 1}
    enemy = game.players[1]
    enemy.organizations = {'北京': 1, '新北': 1, '桃園': 1}
    return game, actor, enemy


def test_two_internal_spies_queue_before_map_and_resolve_fifo():
    game, actor, enemy = make_dissolve_game()
    actor.hand = [action_card(game, '內應間諜'), action_card(game, '內應間諜')]

    first = game.play_card(0, mode='action', target_player_id=enemy.id)
    assert first.get('pending_choice') is True, first
    projected = game.state(actor.id)['pending_choice']
    assert projected['interaction_kind'] == 'dissolve_organization'
    assert projected['queueable_card_names'] == ['內應間諜']

    second = game.play_card(0, mode='action', target_player_id=enemy.id)
    assert second.get('pending_choice') is True, second
    assert actor.hand == []
    assert game.pending_choice['source_name'] == '內應間諜'
    assert len(game._queued_card_build_choices) == 1

    first_town, first_result = choose_target(game, actor, '新北')
    assert first_town == '新北'
    assert first_result.get('pending_choice') is True, first_result
    second_town, second_result = choose_target(game, actor, '桃園')
    assert second_town == '桃園'
    assert second_result.get('success') is True, second_result
    assert game.pending_choice is None
    assert '新北' not in enemy.organizations
    assert '桃園' not in enemy.organizations


def test_two_intel_network_dissolves_collect_options_before_map():
    game, actor, enemy = make_dissolve_game()
    actor.hand = [action_card(game, '情報網'), action_card(game, '情報網')]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    assert game.pending_choice['choice_key'] == 'choose_one'
    assert game.resolve_pending_choice(actor.id, 1).get('pending_choice') is True
    assert game.state(actor.id)['pending_choice']['queueable_card_names'] == ['情報網']

    assert game.play_card(0, mode='action').get('pending_choice') is True
    assert game.pending_choice['choice_key'] == 'choose_one'
    queued = game.resolve_pending_choice(actor.id, 1)
    assert queued.get('pending_choice') is True, queued
    assert game.pending_choice['choice_key'] == 'intel_network_dissolve_target'
    assert len(game._queued_card_build_choices) == 1

    _, first_result = choose_target(game, actor, '新北')
    assert first_result.get('pending_choice') is True, first_result
    _, second_result = choose_target(game, actor, '桃園')
    assert second_result.get('success') is True, second_result
    assert game.pending_choice is None


def test_non_map_option_on_queued_intel_network_restores_original_dissolve_choice():
    game, actor, enemy = make_dissolve_game()
    actor.hand = [action_card(game, '內應間諜'), action_card(game, '情報網')]

    assert game.play_card(0, mode='action', target_player_id=enemy.id).get('pending_choice') is True
    assert game.play_card(0, mode='action').get('pending_choice') is True
    assert game.pending_choice['choice_key'] == 'choose_one'

    resolved = game.resolve_pending_choice(actor.id, 0)

    assert resolved.get('pending_choice') is True, resolved
    assert game.pending_choice['choice_key'] == 'card_dissolve_interaction'
    assert game._deferred_build_choice is None
    assert game._queued_card_build_choices == []
    assert [card.name for card in actor.hand] == []


def test_queued_map_card_reaction_decline_adds_card_once_and_restores_fifo_head():
    game, actor = make_game()
    reactor = game.players[1]
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, '組織經驗丙')]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    reactor.hand = [action_card(game, '爆料黑幕')]
    offered = game.play_card(0, mode='action')
    assert offered.get('pending_choice') is True, offered
    assert game.pending_choice['choice_key'] == 'cancel_other_player_action'

    declined = game.resolve_pending_choice(reactor.id, 0)

    assert declined.get('pending_choice') is True, declined
    assert game.pending_choice['choice_key'] == 'card_build_organization'
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 2
    assert len(game._queued_card_build_choices) == 1


def test_queued_map_card_reaction_cancel_restores_fifo_head_without_new_entry():
    game, actor = make_game()
    reactor = game.players[1]
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, '組織經驗丙')]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    reactor.hand = [action_card(game, '爆料黑幕')]
    assert game.play_card(0, mode='action').get('pending_choice') is True

    cancelled = game.resolve_pending_choice(reactor.id, 1)

    assert cancelled.get('success') is True, cancelled
    assert game.pending_choice['choice_key'] == 'card_build_organization'
    assert game.state(actor.id)['pending_choice']['remaining_builds'] == 1
    assert game._queued_card_build_choices == []
    assert [card.name for card in actor.hand] == []


def test_queued_field_agent_finishes_sacrifice_step_before_joining_fifo():
    game, actor = make_game()
    enemy = game.players[1]
    actor.base = '北京'
    actor.organizations = {'北京': 1, '上海': 1}
    enemy.organizations = {'天津': 1, '杭州': 1, '香港城': 1}
    actor.hand = [action_card(game, '內應間諜'), action_card(game, '派遣間諜')]

    assert game.play_card(0, mode='action', target_player_id=enemy.id).get('pending_choice') is True
    second = game.play_card(0, mode='action', target_player_id=enemy.id)
    assert second.get('pending_choice') is True, second
    assert game.pending_choice['choice_key'] == 'card_dissolve_interaction'
    assert game.pending_choice['step'] == 'sacrifice_town'
    assert game._deferred_build_choice is not None

    sacrificed = game.resolve_pending_choice(actor.id, 0)

    assert sacrificed.get('pending_choice') is True, sacrificed
    assert actor.organizations == {'北京': 1}
    assert game.pending_choice['choice_key'] == 'card_dissolve_interaction'
    assert game.pending_choice['step'] == 'target'
    assert game._deferred_build_choice is None
    assert len(game._queued_card_build_choices) == 1

    first_town = next(entry['town'] for entry in game.pending_choice['targets'])
    _, first_result = choose_target(game, actor, first_town)
    assert first_result.get('pending_choice') is True, first_result
    assert game.pending_choice['source_name'] == '派遣間諜'
    assert game.pending_choice['step'] == 'target'
    final_town = game.pending_choice['targets'][0]['town']
    _, final_result = choose_target(game, actor, final_town)
    assert final_result.get('success') is True, final_result
    assert game.pending_choice is None


def test_build_and_dissolve_cards_share_one_fifo_map_queue():
    game, actor = make_game()
    enemy = game.players[1]
    enemy.organizations = {'北京': 1, '赤柱': 1}
    actor.hand = [action_card(game, '組織經驗丙'), action_card(game, '內應間諜')]

    assert game.play_card(0, mode='action').get('pending_choice') is True
    queued = game.play_card(0, mode='action', target_player_id=enemy.id)
    assert queued.get('pending_choice') is True, queued
    projected = game.state(actor.id)['pending_choice']
    assert projected['interaction_kind'] == 'build_organization'
    assert projected['queueable_card_names'] == []

    _, build_result = choose_town(game, actor)
    assert build_result.get('pending_choice') is True, build_result
    projected = game.state(actor.id)['pending_choice']
    assert projected['interaction_kind'] == 'dissolve_organization'
    _, dissolve_result = choose_target(game, actor, '赤柱')
    assert dissolve_result.get('success') is True, dissolve_result
    assert game.pending_choice is None


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
