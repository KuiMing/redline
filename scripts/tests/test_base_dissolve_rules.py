from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game


def make_game():
    game = Game([('red', '紅軍'), ('a', '甲'), ('b', '乙')])
    red, attacker_a, attacker_b = game.players
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    attacker_a.faction_id = 'liberals'
    attacker_a.base = '香港城'
    attacker_a.organizations = {'香港城': 1, '巴黎': 1}
    attacker_b.faction_id = 'taiwan_green'
    attacker_b.base = '臺北'
    attacker_b.organizations = {'臺北': 1, '東京': 1}
    game.turn_log = game._new_turn_log()
    return game, red, attacker_a, attacker_b


def target_pairs(targets):
    return {(entry['player_id'], entry['town']) for entry in targets}


def test_non_red_base_cannot_be_dissolved_but_normal_and_red_base_targets_remain_legal():
    game, red, attacker, defender = make_game()
    defender.organizations['大阪'] = 1

    rejected = game.dissolve_organization(attacker, defender, '臺北', source='card')
    targets = game._interactive_support_dissolve_targets(
        attacker,
        max_steps=99,
        target_players=[red, defender],
    )

    assert rejected.get('error') == 'Non-Red-Army bases cannot be dissolved'
    assert defender.organizations.get('臺北') == 1
    assert (defender.id, '臺北') not in target_pairs(targets)
    assert (defender.id, '大阪') in target_pairs(targets)
    assert (red.id, '北京') in target_pairs(targets)


def test_same_attacker_second_red_base_hit_removes_org_keeps_base_and_blocks_build_this_turn():
    game, red, attacker, _ = make_game()

    first = game.dissolve_organization(attacker, red, '北京', source='card')
    second = game.dissolve_organization(attacker, red, '北京', source='card')

    assert first == {
        'success': True,
        'actual_owner': red.name,
        'shared_target': False,
        'red_base_hit': True,
        'red_base_destroyed': False,
    }
    assert '北京' not in red.organizations
    assert second.get('success') is True
    assert second.get('red_base_destroyed') is True
    assert red.base == '北京'
    assert game.can_faction_develop_in_town('red_army', '北京') is False
    assert game._place_organization(red, '北京', require_development=False) is False


def test_red_base_build_block_resets_at_turn_boundary():
    game, red, attacker, _ = make_game()
    game.dissolve_organization(attacker, red, '北京', source='card')
    game.dissolve_organization(attacker, red, '北京', source='card')

    game.turn_log = game._new_turn_log()

    assert game.can_faction_develop_in_town('red_army', '北京') is True
    assert game._place_organization(red, '北京') is True
    assert red.base == '北京'
    assert red.organizations.get('北京') == 1


def test_different_attackers_hits_do_not_combine():
    game, red, attacker_a, attacker_b = make_game()

    first = game.dissolve_organization(attacker_a, red, '北京', source='card')
    other_attacker = game.dissolve_organization(attacker_b, red, '北京', source='card')

    assert first.get('red_base_destroyed') is False
    assert other_attacker.get('red_base_destroyed') is False
    assert red.organizations.get('北京') == 1
    assert game.can_faction_develop_in_town('red_army', '北京') is True


def test_same_attacker_hits_across_turns_do_not_combine():
    game, red, attacker, _ = make_game()

    first = game.dissolve_organization(attacker, red, '北京', source='card')
    game.turn_log = game._new_turn_log()
    next_turn = game.dissolve_organization(attacker, red, '北京', source='card')

    assert first.get('red_base_destroyed') is False
    assert next_turn.get('red_base_destroyed') is False
    assert red.organizations.get('北京') == 1
    assert game.can_faction_develop_in_town('red_army', '北京') is True


def test_self_sacrifice_cannot_select_or_forge_own_base():
    game, _, actor, defender = make_game()
    actor.organizations = {'香港城': 1, '承德': 1}
    defender.base = '臺北'
    defender.organizations = {'天津': 1}

    choices = game._interactive_support_sacrifice_towns(
        actor,
        max_steps=1,
        target_players=[defender],
    )
    choice_towns = [entry['town'] for entry in choices]
    forged = game._resolve_support_interaction_result(
        actor,
        {'town': '香港城'},
        {
            'choice_key': 'support_interaction',
            'step': 'sacrifice_town',
            'context': {
                'effect_type': 'interactive_dissolve_self_and_enemy',
                'card_name': '北國奧援',
                'effect_payload': {'range': 1},
                'target_player_id': defender.id,
            },
        },
    )

    assert choice_towns == ['承德']
    assert forged.get('error') == 'Base organization cannot be sacrificed'
    assert actor.organizations == {'香港城': 1, '承德': 1}


def test_legacy_self_sacrifice_does_not_pay_cost_when_only_enemy_target_is_non_red_base():
    game, _, actor, defender = make_game()
    actor.organizations = {'香港城': 1, '承德': 1}
    defender.base = '天津'
    defender.organizations = {'天津': 1}
    before = dict(actor.organizations)

    result = game.effect_engine.execute(
        {'type': 'dissolve', 'range': 1, 'requires_self_sacrifice': True},
        actor,
        game,
        context={'target_player_id': defender.id, 'card_name': 'legacy-test'},
    )

    assert result == {'no_target': True}
    assert actor.organizations == before
    assert defender.organizations == {'天津': 1}
