"""Unit tests for the per-ability trigger helpers decomposed out of
_apply_card_play_faction_abilities / _apply_turn_end_faction_abilities
(game.py refactor item 21, phase 2: decompose in place before extracting
to a separate module). Each helper is now independently testable — this
is the actual point of the decomposition, not just "the replay scenario
still passes."

Behavior must be byte-identical to the pre-decomposition elif chain: same
turn_log flag names, same trigger conditions, same side effects. See the
commit that introduced these helpers for the original chain this was
extracted from.
"""

from server.game import Game


def _new_game():
    return Game([('p1', 'a'), ('p2', 'b')])


def _player(game):
    return game.players[0]


# ---------- _maybe_trigger_first_money_draw (商貿組織) ----------

def test_first_money_draw_ignores_wrong_ability_name():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_first_money_draw(player, '其他能力', True) is False


def test_first_money_draw_requires_cost_has_money():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_first_money_draw(player, '商貿組織', False) is False


def test_first_money_draw_triggers_once_per_turn():
    game = _new_game()
    player = _player(game)
    hand_before = len(player.hand)
    assert game._maybe_trigger_first_money_draw(player, '商貿組織', True) is True
    assert len(player.hand) == hand_before + 1
    assert game.turn_log.get('faction_first_money_triggered') is True
    # Same turn, already triggered — must not fire again.
    hand_after_first = len(player.hand)
    assert game._maybe_trigger_first_money_draw(player, '商貿組織', True) is False
    assert len(player.hand) == hand_after_first


# ---------- _maybe_trigger_first_propaganda_draw (民族調和/星星之火) ----------

def test_first_propaganda_draw_accepts_either_name():
    for name in ('民族調和', '星星之火'):
        game = _new_game()
        player = _player(game)
        hand_before = len(player.hand)
        assert game._maybe_trigger_first_propaganda_draw(player, name, True) is True
        assert len(player.hand) == hand_before + 1
        assert game.turn_log.get('faction_first_propaganda_triggered') is True


def test_first_propaganda_draw_requires_cost_has_propaganda():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_first_propaganda_draw(player, '星星之火', False) is False


# ---------- _maybe_trigger_first_propaganda_gain (人同此心) ----------

def test_first_propaganda_gain_adds_two_propaganda_once():
    game = _new_game()
    player = _player(game)
    player.resources['propaganda'] = 0
    assert game._maybe_trigger_first_propaganda_gain(player, '人同此心', True) is True
    assert player.resources['propaganda'] == 2
    assert game._maybe_trigger_first_propaganda_gain(player, '人同此心', True) is False
    assert player.resources['propaganda'] == 2


# ---------- _maybe_trigger_first_money_gain (基金會/共合會) ----------

def test_first_money_gain_accepts_either_name():
    for name in ('基金會', '共合會'):
        game = _new_game()
        player = _player(game)
        player.resources['money'] = 0
        assert game._maybe_trigger_first_money_gain(player, name, True) is True
        assert player.resources['money'] == 2


def test_first_money_gain_requires_cost_has_money():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_first_money_gain(player, '基金會', False) is False


# ---------- _maybe_trigger_combo_reward (展現實力) ----------

def test_combo_reward_requires_three_distinct_nonstarter_names():
    game = _new_game()
    player = _player(game)
    game.turn_log['played_nonstarter_names'] = ['甲', '乙']
    assert game._maybe_trigger_combo_reward(player, '展現實力') is False
    game.turn_log['played_nonstarter_names'] = ['甲', '乙', '丙']
    assert game._maybe_trigger_combo_reward(player, '展現實力') is True
    assert game.turn_log.get('combo_reward_triggered') is True
    # _maybe_trigger_combo_reward immediately calls
    # _continue_show_strength_choice_queue(), which pops the player off
    # _pending_show_strength_players and opens the actual pending choice —
    # so the queue is empty again by the time this returns, and the
    # observable effect is the pending choice itself.
    assert (game.pending_choice or {}).get('choice_key') == 'show_strength_reward'
    assert (game.pending_choice or {}).get('player_id') == player.id


def test_combo_reward_only_triggers_once_per_turn():
    game = _new_game()
    player = _player(game)
    game.turn_log['played_nonstarter_names'] = ['甲', '乙', '丙']
    assert game._maybe_trigger_combo_reward(player, '展現實力') is True
    assert game._maybe_trigger_combo_reward(player, '展現實力') is False


# ---------- _maybe_trigger_india_research_room (印度研究分析室) ----------

def test_india_research_room_requires_ability_and_flag_card():
    game = _new_game()
    player = _player(game)
    # No played_card at all.
    assert game._maybe_trigger_india_research_room(player, None) is False


def test_india_research_room_ignores_player_without_the_ability():
    game = _new_game()
    player = _player(game)
    # Force a faction without 印度研究分析室 (random assignment can otherwise
    # coincidentally hold it) so this isolates the ability-check branch.
    player.faction_id = 'red_army'
    from server.cards import Card
    card = Card('印度旗', 'command', {})
    assert game._player_has_india_research_room(player) is False
    assert game._maybe_trigger_india_research_room(player, card) is False


def test_india_research_room_requires_a_flag_card():
    game = _new_game()
    player = _player(game)
    player.faction_id = 'tibet_dehradun'  # holds 印度研究分析室
    from server.cards import Card
    assert game._player_has_india_research_room(player) is True
    non_flag_card = Card('追隨者', 'propaganda', {'propaganda': 1})
    assert game._is_india_flag_card(non_flag_card) is False
    assert game._maybe_trigger_india_research_room(player, non_flag_card) is False


# ---------- _maybe_trigger_turn_end_build_draw (本土社團/還我河山) ----------

def test_turn_end_build_draw_requires_built_in_china():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_turn_end_build_draw(player, '本土社團', False) is False
    hand_before = len(player.hand)
    assert game._maybe_trigger_turn_end_build_draw(player, '本土社團', True) is True
    assert len(player.hand) == hand_before + 1


def test_turn_end_build_draw_accepts_either_name():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_turn_end_build_draw(player, '還我河山', True) is True


# ---------- _maybe_trigger_turn_end_expansion_draw (民國之心) ----------

def test_turn_end_expansion_draw_requires_china_or_nanyang():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_turn_end_expansion_draw(player, '民國之心', False, False) is False
    hand_before = len(player.hand)
    assert game._maybe_trigger_turn_end_expansion_draw(player, '民國之心', False, True) is True
    assert len(player.hand) == hand_before + 1


def test_turn_end_expansion_draw_ignores_wrong_name():
    game = _new_game()
    player = _player(game)
    assert game._maybe_trigger_turn_end_expansion_draw(player, '本土社團', True, True) is False
