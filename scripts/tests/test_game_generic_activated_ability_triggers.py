"""Unit tests for the per-ability helpers decomposed out of
_activated_faction_action's generic activated-ability branches (民主陣線/
紅軍派系/立場試探/賭徒耳語/民族祭儀) — game.py refactor item 21, third
slice, phase 2. See test_game_faction_ability_triggers.py (PR #101) and
test_game_red_army_action_triggers.py (PR #103) for the first two slices,
same reasoning: decompose in place, don't extract to a module yet.
"""

from server.cards import Card
from server.game import Game


def _new_game():
    return Game([('p1', 'a'), ('p2', 'b')])


def _player(game):
    return game.players[0]


# ---------- _activate_democratic_front (民主陣線) ----------

def test_democratic_front_requires_two_total_resources():
    game = _new_game()
    player = _player(game)
    player.resources = {'money': 0, 'propaganda': 1}
    assert 'error' in game._activate_democratic_front(player)


def test_democratic_front_spends_propaganda_before_money():
    game = _new_game()
    player = _player(game)
    player.resources = {'money': 5, 'propaganda': 1}
    deck_before = len(player.deck.discard_pile)
    result = game._activate_democratic_front(player)
    assert result == {'success': True}
    # 1 propaganda covers part of the spend, the remaining 1 comes from money.
    assert player.resources == {'money': 4, 'propaganda': 0}
    assert len(player.deck.discard_pile) == deck_before + 1
    assert game.turn_log.get('faction_action_used') is True


def test_democratic_front_spends_all_from_propaganda_when_sufficient():
    game = _new_game()
    player = _player(game)
    player.resources = {'money': 5, 'propaganda': 3}
    game._activate_democratic_front(player)
    assert player.resources == {'money': 5, 'propaganda': 1}


# ---------- _activate_red_army_faction_deck_reorder (紅軍派系) ----------

def test_faction_deck_reorder_requires_a_nonempty_deck():
    game = _new_game()
    player = _player(game)
    player.deck.draw_pile = []
    assert 'error' in game._activate_red_army_faction_deck_reorder(player)


def test_faction_deck_reorder_opens_a_pending_choice_over_up_to_three_cards():
    game = _new_game()
    player = _player(game)
    look = min(3, len(player.deck.draw_pile))
    assert look > 0  # sanity: fresh deck has cards
    result = game._activate_red_army_faction_deck_reorder(player)
    assert result['success'] is True
    assert result['pending_choice'] is True
    assert result['result']['inspected_count'] == look
    assert game.pending_choice.get('choice_key') == 'era_inspect_deck_top_and_reorder'


# ---------- _activate_stance_probe (立場試探) ----------

def test_stance_probe_requires_a_nonempty_deck():
    game = _new_game()
    player = _player(game)
    player.deck.draw_pile = []
    assert 'error' in game._activate_stance_probe(player)


def test_stance_probe_routes_odd_cost_to_hand():
    game = _new_game()
    player = _player(game)
    odd_card = Card('資助者', 'money', {'money': 1})  # 資助者 costs money:2, propaganda:1 -> total 3 (odd)
    player.deck.draw_pile = [odd_card]
    hand_before = len(player.hand)
    result = game._activate_stance_probe(player)
    assert result['result']['destination'] == 'hand'
    assert len(player.hand) == hand_before + 1
    assert player.hand[-1] is odd_card


def test_stance_probe_routes_even_cost_to_discard():
    game = _new_game()
    player = _player(game)
    even_card = Card('分神', 'disruption', {})  # 分神 costs {'money': 0, 'propaganda': 0} -> total 0 (even)
    player.deck.draw_pile = [even_card]
    discard_before = len(player.deck.discard_pile)
    result = game._activate_stance_probe(player)
    assert result['result']['destination'] == 'discard'
    assert len(player.deck.discard_pile) == discard_before + 1


# ---------- _activate_guess_ability (賭徒耳語/民族祭儀) ----------

def test_guess_ability_requires_a_hand_card():
    game = _new_game()
    player = _player(game)
    player.hand = []
    assert 'error' in game._activate_guess_ability(player, '賭徒耳語', 'odd')


def test_guess_ability_requires_a_valid_guess():
    game = _new_game()
    player = _player(game)
    assert player.hand  # sanity
    assert 'error' in game._activate_guess_ability(player, '賭徒耳語', 'maybe')


def test_guess_ability_with_single_hand_card_resolves_immediately():
    game = _new_game()
    player = _player(game)
    player.hand = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    result = game._activate_guess_ability(player, '賭徒耳語', 'odd')
    # No pending choice for the bottom-card pick (only one option) — resolves
    # straight through _resolve_guess_ability_with_bottom_card.
    assert 'result' in result or result.get('pending_choice') is True
    assert player.hand == []  # the sole card was bottom-decked


def test_guess_ability_with_multiple_hand_cards_opens_a_pending_choice():
    game = _new_game()
    player = _player(game)
    assert len(player.hand) > 1  # sanity: fresh hand has several cards
    hand_before = list(player.hand)
    result = game._activate_guess_ability(player, '民族祭儀', 'even')
    assert result == {'success': True, 'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'guess_ability_bottom_card'
    assert player.hand == hand_before  # nothing moved yet — still choosing which card
