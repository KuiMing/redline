"""Unit tests for the per-action helpers decomposed out of
_activated_faction_action's red-army branches (統戰部/政工部/國安部/中紀委)
— game.py refactor item 21, second slice, phase 2: decompose in place
before extracting to a separate module (see
test_game_faction_ability_triggers.py / PR #101 for the first slice on
the card-play/turn-end ability dispatchers, same reasoning).

Each helper preserves its original branch's exact condition checks and
side effects (see the commit that introduced them for the source it was
extracted from). Uses a 2-player red_army-vs-non-red setup so
_red_army_can_use_action's target-eligibility paths have someone to act on.
"""

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
    return game, red, other


# ---------- _activate_red_army_united_front (統戰部) ----------

def test_united_front_draws_one_card():
    game, red, _other = _new_game()
    hand_before = len(red.hand)
    result = game._activate_red_army_united_front(red)
    assert result['success'] is True
    assert result['result']['drawn'] == 1
    assert len(red.hand) == hand_before + 1
    assert game.turn_log.get('red_army_action_count') == 1


def test_united_front_respects_the_per_turn_action_limit():
    game, red, _other = _new_game()
    game.turn_log['red_army_action_count'] = game._red_army_action_limit()
    result = game._activate_red_army_united_front(red)
    assert 'error' in result


# ---------- _activate_red_army_propaganda_department (政工部) ----------

def test_propaganda_department_topdecks_onto_the_target():
    game, red, other = _new_game()
    result = game._activate_red_army_propaganda_department(red, other.id)
    assert result['success'] is True
    assert result['result']['target_player_name'] == other.name
    assert game.turn_log.get('red_army_action_count') == 1


def test_propaganda_department_opens_a_pending_choice_without_an_explicit_target():
    game, red, _other = _new_game()
    result = game._activate_red_army_propaganda_department(red, None)
    assert result.get('pending_choice') is True
    assert game.pending_choice is not None


def test_propaganda_department_rejects_an_invalid_target():
    game, red, _other = _new_game()
    result = game._activate_red_army_propaganda_department(red, 'no-such-player')
    assert 'error' in result


# ---------- _activate_red_army_state_security_action (國安部) ----------

def test_state_security_respects_the_per_turn_action_limit():
    game, red, _other = _new_game()
    game.turn_log['red_army_action_count'] = game._red_army_action_limit()
    result = game._activate_red_army_state_security_action(red)
    assert 'error' in result


def test_state_security_delegates_to_start_red_army_state_security():
    game, red, other = _new_game()
    # Give `other` an organization that is both inside the "china" region
    # alias and within 1 step of red's base, matching
    # _red_army_state_security_targets()'s requirement — otherwise this is
    # a no-op "no_dissolve_target" result regardless of the helper itself.
    other.organizations['天津'] = 1
    result = game._activate_red_army_state_security_action(red)
    assert result.get('pending_choice') is True
    assert game.pending_choice.get('choice_key') == 'red_army_state_security_target'


# ---------- _activate_red_army_discipline_inspection (中紀委) ----------

def test_discipline_inspection_with_empty_hand_is_an_immediate_no_op():
    game, red, _other = _new_game()
    red.hand = []
    result = game._activate_red_army_discipline_inspection(red)
    assert result == {'success': True, 'result': {'name': '中紀委', 'discarded': 0, 'drawn': 0}}
    assert game.turn_log.get('red_army_action_count') == 1


def test_discipline_inspection_with_hand_cards_opens_a_pending_choice():
    game, red, _other = _new_game()
    assert red.hand  # sanity: starting hand is non-empty
    result = game._activate_red_army_discipline_inspection(red)
    assert result == {'pending_choice': True}
    assert game.pending_choice.get('choice_key') == 'red_army_ccdi_discard_draw'
    # The action-use count is only marked when the choice resolves, not on open.
    assert game.turn_log.get('red_army_action_count', 0) == 0
