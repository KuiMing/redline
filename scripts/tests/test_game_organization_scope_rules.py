"""Unit tests for server/game_organization_scope_rules.py — the pure
organization-scope/ruler counting rules extracted from game.py (item
23/24 cleanup: _organization_towns_for_player and its dependents were
over-conservatively left behind in PRs #109/#110 pending purity
verification; verified pure and extracted here). Everything that
*changes* organizations stays in game.py.
"""

from server.game import Game
from server.game_organization_scope_rules import (
    shared_origin_owner,
    shared_org_count,
    town_has_shared_org_access,
    town_blocks_movement_for_player,
    organization_towns_for_player,
    player_organization_scope_counts,
    player_ruler_organization_counts,
    player_ruler_leadership,
    player_ruler_presence,
    player_region_org_count,
    player_requirement_org_count,
)
from server.game_choice_rules import choice_is_card_map_interaction


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


# ---------- shared_origin_owner / shared_org_count ----------

def test_shared_origin_owner_returns_the_owner_for_their_own_town():
    game, a, _b = _new_game()
    assert shared_origin_owner(game.faction_by_id, game.players, a, '香港城') is a


def test_shared_origin_owner_returns_none_for_an_unowned_unshared_town():
    game, a, _b = _new_game()
    assert shared_origin_owner(game.faction_by_id, game.players, a, '北京') is None


def test_shared_org_count_matches_shared_origin_owner_presence():
    game, a, _b = _new_game()
    assert shared_org_count(game.faction_by_id, game.players, a, '香港城') == 1
    assert shared_org_count(game.faction_by_id, game.players, a, '北京') == 0


def test_town_has_shared_org_access_matches_shared_origin_owner():
    game, a, _b = _new_game()
    assert town_has_shared_org_access(game.faction_by_id, game.players, a, '香港城') is True
    assert town_has_shared_org_access(game.faction_by_id, game.players, a, '北京') is False


# ---------- town_blocks_movement_for_player ----------

def test_town_blocks_movement_for_player_true_for_a_rival_organization():
    game, a, b = _new_game()
    assert town_blocks_movement_for_player(game.faction_by_id, game.players, a, '北京') is True


def test_town_blocks_movement_for_player_false_for_own_town():
    game, a, _b = _new_game()
    assert town_blocks_movement_for_player(game.faction_by_id, game.players, a, '香港城') is False


# ---------- organization_towns_for_player ----------

def test_organization_towns_for_player_lists_owned_towns():
    game, a, _b = _new_game()
    assert '香港城' in organization_towns_for_player(game.map, game.faction_by_id, game.players, a)
    assert '北京' not in organization_towns_for_player(game.map, game.faction_by_id, game.players, a)


def test_organization_towns_for_player_returns_empty_for_none_player():
    game, _a, _b = _new_game()
    assert organization_towns_for_player(game.map, game.faction_by_id, game.players, None) == []


# ---------- player_organization_scope_counts ----------

def test_player_organization_scope_counts_totals_owned_organizations():
    game, a, _b = _new_game()
    counts = player_organization_scope_counts(game.map, game.faction_by_id, game.players, a)
    assert counts['total'] == 1


def test_player_organization_scope_counts_none_player_returns_zeros():
    game, _a, _b = _new_game()
    counts = player_organization_scope_counts(game.map, game.faction_by_id, game.players, None)
    assert counts == {"total": 0, "inside_wall": 0, "outside_wall": 0}


# ---------- player_ruler_organization_counts / leadership / presence ----------

def test_player_ruler_organization_counts_returns_a_dict():
    game, a, _b = _new_game()
    counts = player_ruler_organization_counts(game.map, game.faction_by_id, game.players, a)
    assert isinstance(counts, dict)


def test_player_ruler_leadership_is_a_set():
    game, a, _b = _new_game()
    leadership = player_ruler_leadership(game.map, game.faction_by_id, game.players, a)
    assert isinstance(leadership, set)


def test_player_ruler_presence_matches_organization_counts_keys():
    game, a, _b = _new_game()
    counts = player_ruler_organization_counts(game.map, game.faction_by_id, game.players, a)
    presence = player_ruler_presence(game.map, game.faction_by_id, game.players, a)
    assert presence == set(counts)


# ---------- player_region_org_count / player_requirement_org_count ----------

def test_player_region_org_count_china_alias_uses_inside_wall_count():
    game, a, _b = _new_game()
    inside_wall = player_organization_scope_counts(
        game.map, game.faction_by_id, game.players, a, include_shared=True
    )['inside_wall']
    assert player_region_org_count(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, 'china') == inside_wall


def test_player_requirement_org_count_region_requirement_delegates():
    game, a, _b = _new_game()
    requirement = {'region': 'china'}
    expected = player_region_org_count(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, 'china')
    assert player_requirement_org_count(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, requirement) == expected


def test_player_requirement_org_count_unknown_requirement_returns_zero():
    game, a, _b = _new_game()
    assert player_requirement_org_count(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, {}) == 0


# ---------- Game wrapper methods still delegate correctly ----------

def test_game_wrapper_methods_match_the_module_functions():
    game, a, _b = _new_game()
    assert game._organization_towns_for_player(a) == organization_towns_for_player(
        game.map, game.faction_by_id, game.players, a
    )
    assert game._player_ruler_leadership(a) == player_ruler_leadership(
        game.map, game.faction_by_id, game.players, a
    )
