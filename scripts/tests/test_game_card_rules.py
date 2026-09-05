"""Unit tests for server/game_card_rules.py — the pure card build/dissolve
catalog rules and event-modifier reads extracted from game.py. Found
during the same purity audit as game_organization_scope_rules.py /
game_build_eligibility_rules.py.

_card_build_town_choices / _card_action_legality stay as Game methods
(not extracted into this module) — see the module docstring for why.
"""

from server.game import Game
from server.game_card_rules import (
    active_event_modifiers,
    event_modifier_active,
    card_matches_types,
    card_build_effects,
    card_dissolve_effects,
    card_can_queue_build,
)


def _new_game():
    return Game([('p1', 'a'), ('p2', 'b')])


# ---------- active_event_modifiers / event_modifier_active ----------

def test_active_event_modifiers_filters_expired_modifiers():
    modifiers = [
        {'type': 'restrict_build', 'remaining_turns': 1},
        {'type': 'other', 'remaining_turns': 0},
    ]
    assert active_event_modifiers(modifiers) == [modifiers[0]]


def test_active_event_modifiers_defaults_remaining_turns_to_one():
    modifiers = [{'type': 'restrict_build'}]
    assert active_event_modifiers(modifiers) == modifiers


def test_event_modifier_active_true_and_false():
    modifiers = [{'type': 'restrict_build', 'remaining_turns': 1}]
    assert event_modifier_active(modifiers, 'restrict_build') is True
    assert event_modifier_active(modifiers, 'other') is False


def test_game_wrapper_methods_match_the_module_functions_for_event_modifiers():
    game = _new_game()
    game.event_modifiers = [{'type': 'restrict_build', 'remaining_turns': 1}]
    assert game._active_event_modifiers() == active_event_modifiers(game.event_modifiers)
    assert game._event_modifier_active('restrict_build') == event_modifier_active(game.event_modifiers, 'restrict_build')


# ---------- card_matches_types ----------

def test_card_matches_types_true_when_no_filter():
    assert card_matches_types(object(), []) is True


def test_card_matches_types_checks_card_type_membership():
    card = type('C', (), {'card_type': 'armed'})()
    assert card_matches_types(card, {'armed', 'equipment'}) is True
    assert card_matches_types(card, {'support'}) is False


# ---------- card_build_effects / card_dissolve_effects / card_can_queue_build ----------

def test_card_build_effects_matches_game_method_for_a_real_build_card():
    game = _new_game()
    cards = game._action_engine_cards()
    build_card_name = next(
        (name for name, card_def in cards.items()
         if any(isinstance(e, dict) and e.get('type') == 'build' for e in (card_def.get('effect') or []))),
        None,
    )
    assert build_card_name is not None, "expected at least one build-type action card in the catalog"
    card = type('C', (), {'name': build_card_name})()
    expected = game._card_build_effects(card)
    actual = card_build_effects(cards, card)
    assert expected == actual
    assert len(actual) > 0


def test_card_build_effects_empty_for_unknown_card():
    game = _new_game()
    card = type('C', (), {'name': '不存在的卡_xyz'})()
    assert card_build_effects(game._action_engine_cards(), card) == []


def test_card_dissolve_effects_matches_game_method():
    game = _new_game()
    cards = game._action_engine_cards()
    for name, card_def in list(cards.items())[:20]:
        card = type('C', (), {'name': name})()
        expected = game._card_dissolve_effects(card)
        actual = card_dissolve_effects(cards, card)
        assert expected == actual


def test_card_can_queue_build_matches_game_method():
    game = _new_game()
    cards = game._action_engine_cards()
    for name in list(cards.keys())[:20]:
        card = type('C', (), {'name': name})()
        expected = game._card_can_queue_build(card)
        actual = card_can_queue_build(cards, card)
        assert expected == actual
