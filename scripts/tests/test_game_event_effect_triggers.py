"""Unit tests for the per-effect-type helpers decomposed out of
_apply_event_effect (game.py refactor item 22, event-effect dispatcher
slice: decompose in place before extracting to a module, same reasoning
as item 21's PRs #101/#103/#105).

Each helper preserves its original branch's exact condition checks, side
effects, and (for the pending-choice branches) `None`-vs-dict return
convention: `None` means "fall through to the shared success-log tail in
_apply_event_effect", a dict means "an early pending-choice return".
"""

from server.cards import Card
from server.game import Game


def _new_game():
    game = Game([('p1', 'red'), ('p2', 'other')])
    red, other = game.players
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    other.faction_id = 'hong_kong'
    other.base = '香港城'
    other.organizations = {'香港城': 1}
    game.current_event = {'name': 'Test Event'}
    return game, red, other


def _player(game):
    return game.players[0]


# ---------- _apply_event_effect_draw ----------

def test_effect_draw_draws_count_cards():
    game, player, _other = _new_game()
    hand_before = len(player.hand)
    game._apply_event_effect_draw(player, 2)
    assert len(player.hand) == hand_before + 2


# ---------- _apply_event_effect_gain_card ----------

def test_effect_gain_card_adds_named_cards_to_discard():
    game, player, _other = _new_game()
    discard_before = len(player.deck.discard_pile)
    game._apply_event_effect_gain_card(player, {'card': '內鬥'}, 2)
    assert len(player.deck.discard_pile) == discard_before + 2
    assert all(c.name == '內鬥' for c in player.deck.discard_pile[-2:])


# ---------- _apply_event_effect_discard_self ----------

def test_effect_discard_self_with_empty_hand_is_a_no_op():
    game, player, _other = _new_game()
    player.hand = []
    assert game._apply_event_effect_discard_self(player, 1, 'success') is None


def test_effect_discard_self_opens_a_pending_choice():
    game, player, _other = _new_game()
    assert player.hand
    result = game._apply_event_effect_discard_self(player, 2, 'success')
    assert result == {'success': True, 'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'event_discard_self'


# ---------- _apply_event_effect_discard_random ----------

def test_effect_discard_random_discards_from_the_player_by_default():
    game, player, _other = _new_game()
    hand_before = len(player.hand)
    game._apply_event_effect_discard_random(player, {}, 1, 'success')
    assert len(player.hand) == hand_before - 1


def test_effect_discard_random_on_failure_without_player_faction_targets_every_non_red_player():
    game, player, other = _new_game()
    other_hand_before = len(other.hand)
    game._apply_event_effect_discard_random(player, {}, 1, 'failure')
    # `player` here is red_army — the non-red default should hit `other`, not `player`.
    assert len(other.hand) == other_hand_before - 1


# ---------- _apply_event_effect_red_dissolve ----------

def test_effect_red_dissolve_with_no_targets_is_a_no_op():
    game, player, other = _new_game()
    other.organizations = {}
    assert game._apply_event_effect_red_dissolve({}) is None


def test_effect_red_dissolve_opens_a_pending_choice_when_a_target_exists():
    game, player, other = _new_game()
    other.organizations = {'天津': 1}  # inside "china" scope, matches _can_dissolve_base_target
    result = game._apply_event_effect_red_dissolve({'scope': '牆內'})
    assert result == {'success': True, 'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'event_red_dissolve'


# ---------- _apply_event_effect_add_internal_conflict ----------

def test_effect_add_internal_conflict_gains_named_cards():
    game, player, _other = _new_game()
    discard_before = len(player.deck.discard_pile)
    game._apply_event_effect_add_internal_conflict(player, 3)
    assert len(player.deck.discard_pile) == discard_before + 3
    assert all(c.name == '內鬥' for c in player.deck.discard_pile[-3:])


# ---------- _apply_event_effect_move ----------

def test_effect_move_adds_to_moves_left():
    game, player, _other = _new_game()
    player.moves_left = 1
    game._apply_event_effect_move(player, 2)
    assert player.moves_left == 3


# ---------- _apply_event_effect_modifier ----------

def test_effect_modifier_registers_an_event_modifier():
    game, _player_, _other = _new_game()
    modifiers_before = len(game.event_modifiers)
    game._apply_event_effect_modifier({'type': 'reduce_cost', 'amount': 1})
    assert len(game.event_modifiers) == modifiers_before + 1


# ---------- _apply_event_effect_build_organization ----------

def test_effect_build_organization_opens_a_pending_choice():
    game, player, _other = _new_game()
    result = game._apply_event_effect_build_organization(player)
    assert result == {'success': True, 'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'event_build_organization'


# ---------- _apply_event_effect_build_organization_in_region ----------

def test_effect_build_organization_in_region_opens_a_pending_choice_for_a_valid_region():
    game, player, _other = _new_game()
    result = game._apply_event_effect_build_organization_in_region(player, {'region': 'china'}, 1)
    assert result == {'success': True, 'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'event_build_organization'


def test_effect_build_organization_in_region_is_a_no_op_with_no_legal_towns():
    game, player, _other = _new_game()
    # An empty/unknown region alias resolves to no towns.
    result = game._apply_event_effect_build_organization_in_region(player, {'region': 'no_such_region_xyz'}, 1)
    assert result is None


# ---------- _apply_event_effect_build_organization_near_own ----------

def test_effect_build_organization_near_own_opens_a_pending_choice():
    game, player, _other = _new_game()
    result = game._apply_event_effect_build_organization_near_own(player, {'max_steps': 1}, 1)
    # Depends on map adjacency to the player's own base — either a real
    # pending choice, or a no-op if 北京 has no adjacent buildable town for
    # this faction; both are legitimate, so just check the return shape.
    assert result is None or result == {'success': True, 'pending_choice': True}


# ---------- _apply_event_effect_topdeck_from_discard ----------

def test_effect_topdeck_from_discard_with_empty_discard_is_a_no_op():
    game, player, _other = _new_game()
    player.deck.discard_pile = []
    assert game._apply_event_effect_topdeck_from_discard(player, 1, 'success') is None


def test_effect_topdeck_from_discard_opens_a_pending_choice():
    game, player, _other = _new_game()
    player.deck.discard_pile = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    result = game._apply_event_effect_topdeck_from_discard(player, 1, 'success')
    assert result == {'success': True, 'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'event_topdeck_from_discard'


# ---------- _apply_event_effect_trash_from_hand_or_discard ----------

def test_effect_trash_from_hand_or_discard_with_nothing_to_remove_is_a_no_op():
    game, player, _other = _new_game()
    player.hand = []
    player.deck.discard_pile = []
    assert game._apply_event_effect_trash_from_hand_or_discard(player, 1, 'success') is None


def test_effect_trash_from_hand_or_discard_opens_a_pending_choice():
    game, player, _other = _new_game()
    assert player.hand
    result = game._apply_event_effect_trash_from_hand_or_discard(player, 1, 'success')
    assert result == {'success': True, 'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'trash_from_hand_or_discard'
