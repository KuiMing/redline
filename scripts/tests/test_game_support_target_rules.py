"""Unit tests for server/game_support_target_rules.py — the pure
interactive-support/dissolve target-finder cluster extracted from game.py.
Found during the same purity audit as game_organization_scope_rules.py /
game_build_eligibility_rules.py / game_card_rules.py.

_interactive_support_build_towns and _can_replace_dissolved_org_with_own
stay as Game methods (not extracted here) — see the module docstring for
why (org-supply monkeypatch chain / transient self-restoring mutation).
"""

from server.game import Game
from server.game_support_target_rules import (
    can_dissolve_base_target,
    target_players_for_interaction,
    player_has_org_within_steps_of_player,
    find_target_town_within_steps_of_player,
    interactive_support_dissolve_targets,
    interactive_support_dissolve_targets_near_town,
    interactive_support_discard_targets_near,
    interactive_support_sacrifice_towns,
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


# ---------- can_dissolve_base_target ----------

def test_can_dissolve_base_target_true_for_a_non_base_town():
    game, a, _b = _new_game()
    assert can_dissolve_base_target(a, '澳門') == (True, None)


def test_can_dissolve_base_target_true_for_red_army_base():
    game, _a, b = _new_game()
    assert can_dissolve_base_target(b, '北京') == (True, None)


def test_can_dissolve_base_target_false_for_a_non_red_army_base():
    game, a, _b = _new_game()
    assert can_dissolve_base_target(a, '香港城') == (False, "Non-Red-Army bases cannot be dissolved")


def test_game_wrapper_can_dissolve_base_target_matches_module_function():
    game, a, _b = _new_game()
    assert game._can_dissolve_base_target(a, '香港城') == can_dissolve_base_target(a, '香港城')


# ---------- target_players_for_interaction ----------

def test_target_players_for_interaction_defaults_to_all_other_players():
    game, a, b = _new_game()
    assert target_players_for_interaction(game.players, a) == [b]


def test_target_players_for_interaction_with_explicit_target_id():
    game, a, b = _new_game()
    assert target_players_for_interaction(game.players, a, target_player_id=b.id) == [b]


def test_target_players_for_interaction_excludes_self_target():
    game, a, _b = _new_game()
    assert target_players_for_interaction(game.players, a, target_player_id=a.id) == []


# ---------- player_has_org_within_steps_of_player / find_target_town_within_steps_of_player ----------

def test_player_has_org_within_steps_of_player_matches_game_method():
    game, a, b = _new_game()
    expected = game._player_has_org_within_steps_of_player(a, b, max_steps=99)
    actual = player_has_org_within_steps_of_player(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, b, max_steps=99)
    assert expected == actual


def test_find_target_town_within_steps_of_player_matches_game_method():
    game, a, b = _new_game()
    expected = game._find_target_town_within_steps_of_player(a, b, max_steps=99)
    actual = find_target_town_within_steps_of_player(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, b, max_steps=99)
    assert expected == actual
    assert actual == '北京'


# ---------- interactive_support_dissolve_targets ----------

def test_interactive_support_dissolve_targets_matches_game_method():
    game, a, _b = _new_game()
    expected = game._interactive_support_dissolve_targets(a, max_steps=99)
    actual = interactive_support_dissolve_targets(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, max_steps=99)
    assert expected == actual
    assert any(t['town'] == '北京' for t in actual)


def test_interactive_support_dissolve_targets_near_town_matches_game_method():
    game, a, _b = _new_game()
    expected = game._interactive_support_dissolve_targets_near_town(a, '香港城', max_steps=99)
    actual = interactive_support_dissolve_targets_near_town(
        game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, '香港城', max_steps=99
    )
    assert expected == actual


# ---------- interactive_support_discard_targets_near ----------

def test_interactive_support_discard_targets_near_matches_game_method():
    game, a, _b = _new_game()
    expected = game._interactive_support_discard_targets_near(a)
    actual = interactive_support_discard_targets_near(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a)
    assert expected == actual


# ---------- interactive_support_sacrifice_towns ----------

def test_interactive_support_sacrifice_towns_matches_game_method():
    game, a, _b = _new_game()
    expected = game._interactive_support_sacrifice_towns(a, max_steps=99)
    actual = interactive_support_sacrifice_towns(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, max_steps=99)
    assert expected == actual


def test_interactive_support_sacrifice_towns_excludes_the_players_own_base():
    game, a, _b = _new_game()
    # a's only organization is its own base town, which is excluded as a
    # sacrifice option regardless of reachable targets.
    result = interactive_support_sacrifice_towns(game.map, game.towns_by_ruler, game.faction_by_id, game.players, a, max_steps=99)
    assert all(entry['town'] != a.base for entry in result)
