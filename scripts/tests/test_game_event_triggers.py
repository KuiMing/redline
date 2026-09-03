"""Characterization tests for server/game_event_triggers.py — extracted
from Game._event_trigger_matches_scope / _event_trigger_actor_allowed /
_event_purchase_trigger_matches / _event_state_condition_met (game.py
refactor item 22, second pure slice — see game_event_display.py / PR #106
for the first).
"""

from server.cards import Card
from server.game import Game
from server.game_event_triggers import (
    event_trigger_matches_scope,
    event_trigger_actor_allowed,
    event_purchase_trigger_matches,
    event_state_condition_met,
)


def _new_game():
    return Game([('p1', 'a'), ('p2', 'b')])


# ---------- event_trigger_matches_scope ----------

def test_matches_scope_true_when_trigger_has_no_scope():
    game = _new_game()
    assert event_trigger_matches_scope(game.map, game.towns_by_ruler, {}, town='北京') is True


def test_matches_scope_wall_inside_true_for_a_china_town():
    game = _new_game()
    assert event_trigger_matches_scope(game.map, game.towns_by_ruler, {'scope': '牆內'}, town='北京') is True


def test_matches_scope_wall_inside_false_for_a_non_china_town():
    game = _new_game()
    assert event_trigger_matches_scope(game.map, game.towns_by_ruler, {'scope': '牆內'}, town='東京') is False


def test_matches_scope_wall_inside_true_when_town_is_none():
    game = _new_game()
    assert event_trigger_matches_scope(game.map, game.towns_by_ruler, {'scope': '牆內'}, town=None) is True


def test_matches_scope_unknown_scope_defaults_true():
    game = _new_game()
    assert event_trigger_matches_scope(game.map, game.towns_by_ruler, {'scope': '南洋'}, town='東京') is True


# ---------- event_trigger_actor_allowed ----------

def test_actor_allowed_true_for_none_player():
    assert event_trigger_actor_allowed(None) is True


def test_actor_allowed_false_for_red_army():
    game = _new_game()
    player = game.players[0]
    player.faction_id = 'red_army'
    assert event_trigger_actor_allowed(player) is False


def test_actor_allowed_true_for_non_red_army():
    game = _new_game()
    player = game.players[0]
    player.faction_id = 'hong_kong'
    assert event_trigger_actor_allowed(player) is True


# ---------- event_purchase_trigger_matches ----------

def test_purchase_trigger_false_for_non_buy_card_type():
    game = _new_game()
    card = Card('分神', 'disruption', {})
    assert event_purchase_trigger_matches(game.structured_cards, game.support_taxonomy, {'type': 'draw'}, card) is False


def test_purchase_trigger_matches_by_card_name():
    game = _new_game()
    card = Card('分神', 'disruption', {})
    trigger = {'type': 'buy_card', 'card_names': ['分神', '內鬥']}
    assert event_purchase_trigger_matches(game.structured_cards, game.support_taxonomy, trigger, card) is True


def test_purchase_trigger_matches_by_min_cost():
    game = _new_game()
    card = Card('資本家', 'money', {})  # catalog cost money:3 + propaganda:2 = 5
    trigger = {'type': 'buy_card', 'min_cost': 5}
    assert event_purchase_trigger_matches(game.structured_cards, game.support_taxonomy, trigger, card) is True


def test_purchase_trigger_below_min_cost_does_not_match():
    game = _new_game()
    card = Card('分神', 'disruption', {})  # catalog cost 0/0
    trigger = {'type': 'buy_card', 'min_cost': 1}
    assert event_purchase_trigger_matches(game.structured_cards, game.support_taxonomy, trigger, card) is False


def test_purchase_trigger_uses_original_cost_override_when_given():
    game = _new_game()
    card = Card('分神', 'disruption', {})  # catalog cost 0/0, would not match min_cost=2 on its own
    trigger = {'type': 'buy_card', 'min_cost': 2}
    override = {'money': 2, 'propaganda': 0}
    assert event_purchase_trigger_matches(game.structured_cards, game.support_taxonomy, trigger, card, original_cost=override) is True


# ---------- event_state_condition_met ----------

def test_state_condition_unknown_condition_returns_false_zero():
    game = _new_game()
    player = game.players[0]
    assert event_state_condition_met(game.map, game.towns_by_ruler, {'condition': 'nope'}, player) == (False, 0)


def test_state_condition_own_organization_in_scope_wall_inside():
    game = _new_game()
    player = game.players[0]
    player.organizations = {'北京': 2, '東京': 5}  # 北京 is inside "china"/牆內, 東京 is not
    trigger = {'condition': 'own_organization_in_scope', 'scope': '牆內', 'count': 2}
    met, count = event_state_condition_met(game.map, game.towns_by_ruler, trigger, player)
    assert (met, count) == (True, 2)


def test_state_condition_own_organization_in_scope_not_met():
    game = _new_game()
    player = game.players[0]
    player.organizations = {'北京': 1}
    trigger = {'condition': 'own_organization_in_scope', 'scope': '牆內', 'count': 2}
    met, count = event_state_condition_met(game.map, game.towns_by_ruler, trigger, player)
    assert (met, count) == (False, 1)


def test_state_condition_own_organization_in_scope_no_scope_counts_everywhere():
    game = _new_game()
    player = game.players[0]
    player.organizations = {'北京': 1, '東京': 1}
    trigger = {'condition': 'own_organization_in_scope', 'count': 2}
    met, count = event_state_condition_met(game.map, game.towns_by_ruler, trigger, player)
    assert (met, count) == (True, 2)
