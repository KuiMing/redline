"""Unit tests for server/game_choice_rules.py — the pure pending_choice
classifier extracted from game.py (_choice_is_card_map_interaction).
"""

from server.game_choice_rules import choice_is_card_map_interaction


def test_non_dict_choice_is_not_a_map_interaction():
    assert choice_is_card_map_interaction(None) is False
    assert choice_is_card_map_interaction('not a dict') is False


def test_card_build_organization_is_a_map_interaction():
    assert choice_is_card_map_interaction({'choice_key': 'card_build_organization'}) is True


def test_intel_network_dissolve_target_is_a_map_interaction():
    assert choice_is_card_map_interaction({'choice_key': 'intel_network_dissolve_target'}) is True


def test_support_interaction_town_step_with_matching_effect_type_is_a_map_interaction():
    choice = {
        'choice_key': 'support_interaction',
        'step': 'town',
        'context': {'effect_type': 'interactive_build_near_inner'},
    }
    assert choice_is_card_map_interaction(choice) is True


def test_support_interaction_town_step_with_non_matching_effect_type_is_not():
    choice = {
        'choice_key': 'support_interaction',
        'step': 'town',
        'context': {'effect_type': 'gain_resource'},
    }
    assert choice_is_card_map_interaction(choice) is False


def test_unrelated_choice_key_is_not_a_map_interaction():
    assert choice_is_card_map_interaction({'choice_key': 'draw_choice'}) is False
