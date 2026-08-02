from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game


def make_game():
    game = Game([('red', 'Red'), ('taiwan', 'Taiwan'), ('other', 'Other')])
    red, taiwan, other = game.players
    red.faction_id = 'red_army'
    taiwan.faction_id = 'taiwan_green'
    other.faction_id = 'hong_kong'
    for player in game.players:
        player.organizations = {}
    game.pending_base_choices = {}
    return game


def taiwan_trigger(game):
    return next(era['trigger'] for era in game.structured_eras if era['id'] == 'taiwan')


def ruler_towns(game, ruler):
    return [
        town
        for town, data in game.map['towns'].items()
        if ruler in (data.get('ruler') or [])
    ]


def test_taiwan_era_structured_trigger_targets_inside_wall_not_taiwan_region():
    game = make_game()

    trigger = taiwan_trigger(game)

    assert trigger['region'] == 'china'
    assert trigger['count'] == 7


def test_eight_organizations_in_taiwan_do_not_complete_inside_wall_era():
    game = make_game()
    taiwan = game.players[1]
    taiwan_towns = ruler_towns(game, '臺灣')
    assert len(taiwan_towns) >= 8
    taiwan.organizations = {town: 1 for town in taiwan_towns[:8]}

    assert game._evaluate_era_trigger(taiwan_trigger(game)) is False


def test_taiwan_era_uses_six_seven_inside_wall_boundary():
    game = make_game()
    taiwan = game.players[1]
    inside_towns = ruler_towns(game, '紅軍')
    assert len(inside_towns) >= 7
    taiwan.organizations = {town: 1 for town in inside_towns[:6]}
    assert game._evaluate_era_trigger(taiwan_trigger(game)) is False

    taiwan.organizations[inside_towns[6]] = 1
    assert game._evaluate_era_trigger(taiwan_trigger(game)) is True


def test_inside_wall_classification_depends_on_map_ruler_not_organization_owner():
    game = make_game()
    red, taiwan, other = game.players
    inside_town = ruler_towns(game, '紅軍')[0]
    outside_town = ruler_towns(game, '臺灣')[0]

    assert game._is_inside_wall_town(inside_town) is True
    assert game._is_inside_wall_town(outside_town) is False

    taiwan.organizations = {inside_town: 1}
    red.organizations = {outside_town: 1}
    other.organizations = {}
    assert game._player_organization_scope_counts(taiwan) == {
        'total': 1,
        'inside_wall': 1,
        'outside_wall': 0,
    }
    assert game._player_organization_scope_counts(red) == {
        'total': 1,
        'inside_wall': 0,
        'outside_wall': 1,
    }


def test_player_state_projects_owned_inside_outside_counts_with_total_conservation():
    game = make_game()
    red, taiwan, other = game.players
    inside_towns = ruler_towns(game, '紅軍')[:3]
    outside_towns = ruler_towns(game, '臺灣')[:2]
    taiwan.organizations = {town: 1 for town in inside_towns + outside_towns}

    state = game.state(taiwan.id)
    projected = next(player for player in state['players'] if player['id'] == taiwan.id)

    assert projected['organization_counts'] == {
        'total': 5,
        'inside_wall': 3,
        'outside_wall': 2,
    }
    assert projected['organization_counts']['inside_wall'] + projected['organization_counts']['outside_wall'] == sum(projected['orgs'].values())


def test_shared_effective_organization_counts_for_era_but_owned_status_total_stays_physical():
    game = make_game()
    red, taiwan, other = game.players
    taiwan.faction_id = 'taiwan_green'
    other.faction_id = 'hakka'
    # Hakka and green Taiwan share organizations by canonical faction rules.
    inside_towns = ruler_towns(game, '紅軍')[:7]
    other.organizations = {town: 1 for town in inside_towns}
    taiwan.organizations = {}

    assert game._evaluate_era_trigger(taiwan_trigger(game)) is True
    assert game._player_organization_scope_counts(taiwan) == {
        'total': 0,
        'inside_wall': 0,
        'outside_wall': 0,
    }
