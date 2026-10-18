"""香港抗暴之戰免費遷移根據地：state 明確提供做決定的香港玩家 player_id（hot-seat 交接用）。

hk_base_relocation_player_id 只有 hk_free_base_relocation 開啟且能唯一找到香港玩家時才是該玩家 id，
其餘一律為 null；它對每個檢視者（含未驗證的公開檢視）都相同，不帶任何私密資料。
"""

import json

from test_hong_kong_base_relocation import (
    end_turns_through_red,
    make_game,
    make_three_player_game,
    pin_hong_kong_event,
    settle_event,
)
from server.game import Card, Game, TurnPhase

KEY = 'hk_base_relocation_player_id'


def viewer_values(game):
    views = [game.state(p.id) for p in game.players] + [game.state(None)]
    for view in views:
        assert KEY in view
        json.dumps(view, ensure_ascii=False)  # 仍可序列化
    return {view[KEY] for view in views}


def test_id_is_null_until_the_window_opens_then_names_hong_kong_for_every_viewer():
    game, first, second, red = make_three_player_game()
    game.current_player_index = 0
    first.hand = [Card('第一位手牌', 'command', {})]
    second.hand = [Card('第二位手牌', 'command', {})]
    pin_hong_kong_event(game)

    assert viewer_values(game) == {None}
    assert end_turns_through_red(game).get('pending_choice') is True
    # 棄牌仍待決：窗口尚未開啟，pending_choice 才是行動者
    assert game.hk_free_base_relocation is False
    assert viewer_values(game) == {None}
    game.resolve_pending_choice(first.id, [0])
    assert viewer_values(game) == {None}
    game.resolve_pending_choice(second.id, [0])

    assert game.pending_choice is None
    assert game.hk_free_base_relocation is True
    assert game.current_player() is red  # 換人凍結，current_player 不是香港
    assert viewer_values(game) == {first.id}
    assert game.state(None)['hk_free_base_relocation'] is True

    assert game.relocate_hong_kong_base(first.id, '倫敦').get('success') is True
    assert game.current_player() is first
    assert game.turn_phase == TurnPhase.ACTION
    assert viewer_values(game) == {None}


def test_keep_and_next_round_close_the_window_and_clear_the_id():
    game, hk, red = make_game()
    pin_hong_kong_event(game)
    game._track_event_progress('play_card_with_money', player=hk)
    assert end_turns_through_red(game).get('pending_hk_relocation') is True
    assert viewer_values(game) == {hk.id}

    assert game.keep_hong_kong_base(hk.id).get('success') is True
    assert viewer_values(game) == {None}

    reopened, hk2, _ = make_game()
    settle_event(reopened)
    assert viewer_values(reopened) == {hk2.id}
    reopened._start_event_phase()
    assert reopened.hk_free_base_relocation is False
    assert viewer_values(reopened) == {None}


def test_rejected_decisions_keep_the_window_and_the_id():
    game, hk, red = make_game()
    settle_event(game)
    red.organizations = {'多倫多': 1}

    assert game.relocate_hong_kong_base(hk.id, '多倫多') == {'error': 'Cannot relocate base into occupied town'}
    assert game.keep_hong_kong_base(red.id) == {'error': 'Only Hong Kong can decide its base relocation'}
    assert viewer_values(game) == {hk.id}


def test_window_without_a_unique_hong_kong_player_fails_closed_to_null():
    no_hk = Game([('tw', '臺灣玩家'), ('red', '紅軍玩家')])
    no_hk.players[0].faction_id = 'taiwan_green'
    no_hk.players[1].faction_id = 'red_army'
    no_hk.hk_free_base_relocation = True  # 異常殘留旗標
    assert viewer_values(no_hk) == {None}

    two_hk, first, _ = make_game()
    two_hk.players[1].faction_id = 'hong_kong'
    two_hk.hk_free_base_relocation = True
    assert viewer_values(two_hk) == {None}

    closed, _, _ = make_game()
    closed.hk_free_base_relocation = False
    assert viewer_values(closed) == {None}
