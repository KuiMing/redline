"""Unit tests for server/game_build_eligibility_rules.py — the pure
build/org-eligibility cluster extracted from game.py (found during the same
purity audit that unlocked server/game_organization_scope_rules.py). Actually
placing/removing an organization stays in game.py — those mutate
player.organizations.
"""

from server.game import Game
from server.game_build_eligibility_rules import (
    ANTI_COMMUNIST_ORG_SUPPLY,
    RED_ARMY_ORG_SUPPLY,
    camp_token_for_player,
    red_army_base_build_blocked,
    can_faction_develop_in_town,
    organization_entries_at,
    town_has_physical_organization,
    organization_occupancy_violations,
    rail_reachable_within_three,
    org_supply_limit,
    has_org_supply,
    can_develop_in_town,
    player_is_nonviolent,
    player_is_distance_restricted,
    faction_restricts_ignore_distance_build,
    era_restricts_ignore_distance_build,
    ignore_distance_build_restricted,
    restricted_build_fallback_towns,
    active_era_effects,
)


def _new_game():
    game = Game([('p1', 'a'), ('p2', 'b')])
    a, b = game.players
    a.faction_id = 'hong_kong'
    a.base = '香港城'
    a.organizations = {'香港城': 1}
    b.faction_id = 'red_army'
    b.base = '北京'
    b.organizations = {'北京': 1}
    return game, a, b


# ---------- camp_token_for_player / red_army_base_build_blocked ----------

def test_camp_token_for_player_matches_game_method():
    game, a, _b = _new_game()
    assert camp_token_for_player(game.faction_by_id, a) == game._camp_token_for_player(a)


def test_red_army_base_build_blocked_false_with_no_turn_log_entry():
    game, _a, b = _new_game()
    assert red_army_base_build_blocked(game.turn_log, 'red_army', '北京') is False


def test_red_army_base_build_blocked_true_when_town_is_in_the_turn_log_list():
    turn_log = {'red_army_base_build_blocks': ['北京']}
    assert red_army_base_build_blocked(turn_log, 'red_army', '北京') is True
    assert red_army_base_build_blocked(turn_log, 'hong_kong', '北京') is False


# ---------- can_faction_develop_in_town ----------

def test_can_faction_develop_in_town_matches_game_method_for_red_army():
    game, _a, _b = _new_game()
    expected = game.can_faction_develop_in_town('red_army', '北京')
    actual = can_faction_develop_in_town(game.map, game.faction_by_id, game.turn_log, 'red_army', '北京')
    assert expected == actual


def test_can_faction_develop_in_town_returns_false_for_an_unknown_town():
    game, _a, _b = _new_game()
    assert can_faction_develop_in_town(game.map, game.faction_by_id, game.turn_log, 'red_army', '不存在的城鎮_xyz') is False


# ---------- organization_entries_at / town_has_physical_organization ----------

def test_organization_entries_at_lists_owning_players():
    game, a, _b = _new_game()
    entries = organization_entries_at(game.players, '香港城')
    assert entries == [(a, 1)]


def test_town_has_physical_organization_true_and_false():
    game, _a, _b = _new_game()
    assert town_has_physical_organization(game.players, '香港城') is True
    assert town_has_physical_organization(game.players, '澳門') is False


def test_organization_occupancy_violations_matches_game_method():
    game, _a, _b = _new_game()
    expected = game._organization_occupancy_violations()
    actual = organization_occupancy_violations(game.map, game.players)
    assert expected == actual


# ---------- rail_reachable_within_three ----------

def test_rail_reachable_within_three_matches_game_method():
    game, a, _b = _new_game()
    expected = game._rail_reachable_within_three(a, '香港城', '香港城')
    actual = rail_reachable_within_three(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, '香港城', '香港城')
    assert expected == actual
    assert actual is True  # a town is trivially rail-reachable from itself


# ---------- org_supply_limit / has_org_supply / can_develop_in_town ----------

def test_org_supply_limit_differs_between_red_army_and_others():
    game, a, b = _new_game()
    assert org_supply_limit(a) == ANTI_COMMUNIST_ORG_SUPPLY
    assert org_supply_limit(b) == RED_ARMY_ORG_SUPPLY


def test_has_org_supply_true_when_under_the_limit():
    game, a, _b = _new_game()
    assert has_org_supply(a, count=1) is True


def test_has_org_supply_false_when_at_the_limit():
    a_faction = type('P', (), {'faction_id': 'hong_kong', 'total_organizations': lambda self: ANTI_COMMUNIST_ORG_SUPPLY})()
    assert has_org_supply(a_faction, count=1) is False


def test_can_develop_in_town_matches_game_method():
    game, a, _b = _new_game()
    expected = game.can_develop_in_town(a, '澳門')
    actual = can_develop_in_town(game.map, game.faction_by_id, game.players, game.turn_log, a, '澳門')
    assert expected == actual


def test_can_develop_in_town_false_when_town_already_has_a_physical_organization():
    game, a, _b = _new_game()
    assert can_develop_in_town(game.map, game.faction_by_id, game.players, game.turn_log, a, '香港城') is False


# ---------- player_is_nonviolent / player_is_distance_restricted ----------

def test_player_is_nonviolent_matches_game_method():
    game, a, _b = _new_game()
    expected = game._player_is_nonviolent(a)
    actual = player_is_nonviolent(game.faction_by_id, game.ability_templates, a)
    assert expected == actual


def test_player_is_distance_restricted_matches_game_method():
    game, a, _b = _new_game()
    expected = game._player_is_distance_restricted(a)
    actual = player_is_distance_restricted(game.faction_by_id, game.ability_templates, a)
    assert expected == actual


# ---------- faction/era ignore-distance-build restrictions ----------

def test_faction_restricts_ignore_distance_build_false_for_a_non_restricted_faction():
    game, a, _b = _new_game()
    assert faction_restricts_ignore_distance_build(
        game.map, game.towns_by_ruler, game.faction_by_id, game.ability_templates, a, '香港城'
    ) is False


def test_era_restricts_ignore_distance_build_false_with_no_active_effects():
    game, a, _b = _new_game()
    assert era_restricts_ignore_distance_build([], game.faction_by_id, game.map, game.towns_by_ruler, a, '香港城') is False


def test_ignore_distance_build_restricted_matches_game_method():
    game, a, _b = _new_game()
    expected = game._ignore_distance_build_restricted(a, '香港城')
    actual = ignore_distance_build_restricted(
        game.map, game.towns_by_ruler, game.faction_by_id, game.ability_templates, game._active_era_effects(), a, '香港城'
    )
    assert expected == actual


# ---------- restricted_build_fallback_towns ----------

def test_restricted_build_fallback_towns_empty_for_zero_range():
    game, a, _b = _new_game()
    assert restricted_build_fallback_towns(game.map, game.faction_by_id, game.players, game.ability_templates, a, 0) == set()


def test_restricted_build_fallback_towns_matches_game_method():
    game, a, _b = _new_game()
    expected = game._restricted_build_fallback_towns(a, 1)
    actual = restricted_build_fallback_towns(game.map, game.faction_by_id, game.players, game.ability_templates, a, 1)
    assert expected == actual


# ---------- active_era_effects ----------

def test_active_era_effects_empty_with_no_active_eras():
    assert active_era_effects([]) == []


def test_active_era_effects_flattens_effects_dict_into_tuples():
    detail = {'id': 'era1', 'effects': {'red': {'type': 'x'}, 'non_red': {'type': 'y'}}}
    result = active_era_effects([detail])
    assert (detail, 'red', {'type': 'x'}) in result
    assert (detail, 'non_red', {'type': 'y'}) in result
