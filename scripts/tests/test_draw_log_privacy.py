from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.effect_engine import EffectEngine
from server.game import Game, GamePhase, TurnPhase


def make_game():
    game = Game([('red', '紅軍'), ('kazakh', '哈薩克'), ('observer', '旁觀玩家')])
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.pending_base_choices = {}
    game.action_log = []
    return game


def set_draw_pile(player, *names):
    player.deck.draw_pile = [Card(name, 'starter', {}) for name in names]
    player.deck.discard_pile = []
    player.hand = []


def projected_last_log(game, viewer):
    return game.state(viewer.id)['action_log'][-1]


def assert_private_names_only_for_owner(game, owner, others, expected_names, public_fragment):
    owner_log = projected_last_log(game, owner)
    assert all(name in owner_log for name in expected_names), owner_log
    for viewer in others:
        public_log = projected_last_log(game, viewer)
        assert public_fragment in public_log, public_log
        assert all(name not in public_log for name in expected_names), public_log


def test_era_draw_names_are_private_to_drawing_player():
    game = make_game()
    red, kazakh, observer = game.players
    set_draw_pile(kazakh, '樂捐者', '追隨者')

    game._draw_player_cards(kazakh, 2, source='era')

    assert_private_names_only_for_owner(
        game,
        kazakh,
        [red, observer],
        ['樂捐者', '追隨者'],
        '哈薩克 因時代關卡效果抽了 2 張牌',
    )


def test_event_or_named_effect_draw_names_are_private_to_drawing_player():
    game = make_game()
    red, kazakh, observer = game.players
    set_draw_pile(kazakh, '樂捐者', '追隨者')

    game._draw_player_cards(kazakh, 2, source='effect', trigger_name='測試事件')

    assert_private_names_only_for_owner(
        game,
        kazakh,
        [red, observer],
        ['樂捐者', '追隨者'],
        '哈薩克 因測試事件抽了 2 張牌',
    )


def test_standard_action_draw_names_are_private_to_drawing_player():
    game = make_game()
    red, kazakh, observer = game.players
    set_draw_pile(kazakh, '樂捐者', '追隨者')

    EffectEngine()._draw(kazakh, 2, game=game, card_name='領導')

    assert_private_names_only_for_owner(
        game,
        kazakh,
        [red, observer],
        ['樂捐者', '追隨者'],
        '哈薩克 因領導抽了 2 張牌',
    )


def test_shared_draw_reveals_each_player_only_their_own_card_names():
    game = make_game()
    red, kazakh, observer = game.players
    set_draw_pile(red, '紅軍私牌')
    set_draw_pile(kazakh, '哈薩克私牌')

    EffectEngine().execute(
        {'type': 'shared_draw', 'count': 1, 'target_player_id': kazakh.id},
        red,
        game,
        context={'card_name': '合作談判', 'target_player_id': kazakh.id},
    )

    red_log = projected_last_log(game, red)
    kazakh_log = projected_last_log(game, kazakh)
    observer_log = projected_last_log(game, observer)
    assert '紅軍私牌' in red_log and '哈薩克私牌' not in red_log, red_log
    assert '哈薩克私牌' in kazakh_log and '紅軍私牌' not in kazakh_log, kazakh_log
    assert '紅軍私牌' not in observer_log and '哈薩克私牌' not in observer_log, observer_log
    assert '紅軍 與 哈薩克 因合作談判各抽了 1 張牌' in observer_log, observer_log


def test_internal_diagnostic_log_keeps_exact_drawn_names():
    game = make_game()
    _, kazakh, _ = game.players
    set_draw_pile(kazakh, '樂捐者', '追隨者')

    game._draw_player_cards(kazakh, 2, source='era')

    assert '樂捐者' in game.action_log[-1]
    assert '追隨者' in game.action_log[-1]
