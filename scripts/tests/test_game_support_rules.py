"""Unit tests for server/game_support_rules.py — the pure support-card
taxonomy/effect-resolution cluster extracted from game.py (item 24,
extract-support-service).

support_card_tier was added in a later slice once
game_organization_scope_rules.player_ruler_leadership (and its
dependents) were verified pure. Support card interaction/execution
(_execute_support_card, _start_support_interaction, ...) stays in
game.py — those mutate state.
"""

from server.cards import Card
from server.game import Game
from server.game_support_rules import (
    support_taxonomy_entry,
    is_starter_support_card,
    support_card_runtime_type,
    is_support_card,
    is_india_flag_card,
    support_card_variant_info,
    support_card_effect_text,
    resolve_support_card_effect,
    make_support_card,
    support_card_tier,
)


def _new_game():
    return Game([('p1', 'a'), ('p2', 'b')])


# ---------- support_taxonomy_entry ----------

def test_support_taxonomy_entry_finds_a_known_card():
    game = _new_game()
    entry = support_taxonomy_entry(game.support_taxonomy, '紅軍奧援')
    assert entry is not None
    assert entry.get('name') == '紅軍奧援'


def test_support_taxonomy_entry_returns_none_for_unknown_card():
    game = _new_game()
    assert support_taxonomy_entry(game.support_taxonomy, '不存在的卡_xyz') is None


# ---------- is_starter_support_card ----------

def test_is_starter_support_card_for_red_support():
    game = _new_game()
    assert is_starter_support_card(game.support_taxonomy, '紅軍奧援') is True


def test_is_starter_support_card_for_non_starter():
    game = _new_game()
    assert is_starter_support_card(game.support_taxonomy, '英美奧援') is False


# ---------- support_card_runtime_type ----------

def test_support_card_runtime_type_known_names_are_support():
    for name in ('英美奧援', '東洋奧援', '紅軍奧援'):
        assert support_card_runtime_type(name) == 'support'


def test_support_card_runtime_type_defaults_to_support_for_unknown_name():
    assert support_card_runtime_type('不存在的卡_xyz') == 'support'


# ---------- is_support_card / is_india_flag_card ----------

def test_is_support_card_true_for_a_support_card():
    game = _new_game()
    card = make_support_card(game.support_taxonomy, '英美奧援')
    assert is_support_card(game.support_taxonomy, card) is True


def test_is_support_card_false_for_a_non_support_card():
    game = _new_game()
    card = Card('追隨者', 'propaganda', {'propaganda': 1})
    assert is_support_card(game.support_taxonomy, card) is False


def test_is_india_flag_card_reflects_taxonomy_flag():
    game = _new_game()
    india_card = make_support_card(game.support_taxonomy, '印度奧援')
    entry = support_taxonomy_entry(game.support_taxonomy, '印度奧援')
    expected = bool(entry.get('counts_as_flag_card'))
    assert is_india_flag_card(game.support_taxonomy, india_card) == expected


def test_is_india_flag_card_false_for_non_support_card():
    game = _new_game()
    card = Card('追隨者', 'propaganda', {'propaganda': 1})
    assert is_india_flag_card(game.support_taxonomy, card) is False


# ---------- support_card_variant_info ----------

def test_support_card_variant_info_none_for_non_support_card():
    game = _new_game()
    card = Card('追隨者', 'propaganda', {'propaganda': 1})
    assert support_card_variant_info(game.support_taxonomy, card) is None


def test_support_card_variant_info_reflects_the_cards_own_variant_index():
    game = _new_game()
    entry = support_taxonomy_entry(game.support_taxonomy, '英美奧援')
    regions = entry.get('regions', []) or []
    if not regions:
        return  # nothing to assert if this catalog entry has no regions
    card = make_support_card(game.support_taxonomy, '英美奧援', variant_index=0)
    info = support_card_variant_info(game.support_taxonomy, card)
    assert info is not None
    assert info['variant_index'] == 0
    assert info['support_region'] == entry.get('support_region')


# ---------- support_card_effect_text / resolve_support_card_effect ----------

def test_support_card_effect_text_none_for_out_of_range_region_index():
    game = _new_game()
    assert support_card_effect_text(game.support_taxonomy, '英美奧援', 1, 999) is None


def test_resolve_support_card_effect_red_support_is_hardcoded():
    game = _new_game()
    kind, payload = resolve_support_card_effect(game.support_taxonomy, '紅軍奧援', 1, 0)
    assert kind == 'red_support_draw_and_pass'
    assert payload == {'draw': 1}


def test_resolve_support_card_effect_scales_with_tier_for_a_known_card():
    game = _new_game()
    kind1, payload1 = resolve_support_card_effect(game.support_taxonomy, '英美奧援', 1, 0)
    kind3, payload3 = resolve_support_card_effect(game.support_taxonomy, '英美奧援', 3, 0)
    assert kind1 == 'gain_resource' and kind3 == 'gain_resource'
    assert payload3['money'] >= payload1['money']


def test_resolve_support_card_effect_none_when_no_text_available():
    game = _new_game()
    assert resolve_support_card_effect(game.support_taxonomy, '英美奧援', 1, 999) == (None, None)


# ---------- make_support_card ----------

def test_make_support_card_red_support_has_printed_resources():
    game = _new_game()
    card = make_support_card(game.support_taxonomy, '紅軍奧援')
    assert card.resources == {'money': 1, 'propaganda': 1}
    assert card.card_type == 'support'


def test_make_support_card_normal_support_has_no_printed_resources():
    game = _new_game()
    card = make_support_card(game.support_taxonomy, '英美奧援')
    # Card.__init__ falls back to a zeroed dict for a falsy `resources` arg
    # (`{} or {"money": 0, "propaganda": 0}`) — this is existing Card
    # behavior, not something make_support_card itself controls.
    assert card.resources == {'money': 0, 'propaganda': 0}


def test_make_support_card_records_variant_index():
    game = _new_game()
    card = make_support_card(game.support_taxonomy, '英美奧援', variant_index=1)
    assert card.variant_index == 1


# ---------- support_card_tier ----------

def test_support_card_tier_defaults_to_tier_1_with_no_ruler_leadership():
    game = _new_game()
    player = game.players[0]
    card = make_support_card(game.support_taxonomy, '英美奧援')
    tier, variant_index, matched = support_card_tier(
        game.support_taxonomy, game.map, game.faction_by_id, game.players, player, card
    )
    assert tier == 1
    assert variant_index == 0
    assert matched == []


def test_support_card_tier_returns_tier_1_for_a_card_with_no_taxonomy_entry():
    game = _new_game()
    player = game.players[0]
    card = Card('不存在的奧援卡_xyz', 'support', {})
    tier, variant_index, matched = support_card_tier(
        game.support_taxonomy, game.map, game.faction_by_id, game.players, player, card
    )
    assert (tier, variant_index, matched) == (1, None, [])


def test_game_wrapper_support_card_tier_matches_the_module_function():
    game = _new_game()
    player = game.players[0]
    card = make_support_card(game.support_taxonomy, '英美奧援')
    assert game._support_card_tier(player, card) == support_card_tier(
        game.support_taxonomy, game.map, game.faction_by_id, game.players, player, card
    )
