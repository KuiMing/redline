from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, GamePhase, TurnPhase


def make_game():
    g = Game([('p1', 'P1'), ('p2', 'P2')])
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.pending_base_choices = {}
    return g


def card(g, name):
    c = next(c for c in g.structured_cards if c['name'] == name)
    return Card(c['name'], c['type'], c.get('resources', {}))


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def play_only(g, name):
    p = g.current_player()
    p.hand = [card(g, name)]
    p.resources = {'money': 0, 'propaganda': 0}
    result = g.play_card(0, mode='action')
    assert result.get('success'), result
    return p


def test_recruit_talent_selects_any_card_from_own_deck_not_topdeck_only():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '網羅人才')]
    # Deck top is TopCard (last element). DesiredCard is deliberately not on top.
    p.deck.draw_pile = [Card('DesiredCard', 'command', {}), Card('MiddleCard', 'command', {}), Card('TopCard', 'command', {})]
    p.deck.discard_pile = []

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert g.pending_choice and g.pending_choice['type'] == 'recruit_talent'
    assert names(g.pending_choice['cards']) == ['DesiredCard', 'MiddleCard', 'TopCard']
    resolved = g.resolve_pending_choice(p.id, 0)
    assert resolved.get('success'), resolved
    assert 'DesiredCard' in names(p.hand)
    assert 'TopCard' not in names(p.hand)


def test_imitate_tactics_uses_target_player_top_card_not_own_top_card():
    g = make_game()
    p1, p2 = g.players
    p1.hand = [card(g, '模仿戰術')]
    p1.deck.draw_pile = [Card('OwnTop', 'command', {})]
    p2.deck.draw_pile = [Card('TargetBottom', 'command', {}), Card('OpponentTop', 'command', {'money': 1})]

    result = g.play_card(0, mode='action', target_player_id=p2.id)

    assert result.get('success'), result
    assert 'OpponentTop' in names(p1.hand)
    assert 'OwnTop' not in names(p1.hand)
    assert names(p2.deck.draw_pile) == ['TargetBottom']

    idx = names(p1.hand).index('OpponentTop')
    result = g.play_card(idx, mode='resource')
    assert result.get('success'), result
    assert names(p2.deck.draw_pile)[-1] == 'OpponentTop'
    assert 'OpponentTop' not in names(p1.deck.discard_pile)


def test_intel_network_runs_only_one_default_option_not_cancel_too():
    g = make_game()
    p = play_only(g, '情報網')

    assert names(p.deck.discard_pile).count('內鬥') == 1
    assert not g.turn_log.get('canceled_propaganda_card')


def test_announce_action_topdecks_latest_card_bought_this_turn_and_gains_propaganda():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動預告')

    assert p.resources['propaganda'] == 1
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)


def test_action_fundraising_topdecks_latest_card_bought_this_turn_and_gains_money():
    g = make_game()
    p = g.current_player()
    bought = Card('PurchasedCard', 'command', {})
    p.deck.discard_pile = [bought]
    g.turn_log['purchased_cards_this_turn'] = [bought]

    p = play_only(g, '行動募資')

    assert p.resources['money'] == 1
    assert names(p.deck.draw_pile)[-1] == 'PurchasedCard'
    assert 'PurchasedCard' not in names(p.deck.discard_pile)


def test_missing_cards_exist_in_structured_action_data():
    g = make_game()
    structured = {c['name']: c for c in g.structured_cards}
    for name in ['企業人脈', '產業滲透', '企畫遊說', '行動募資']:
        assert name in structured
        assert structured[name].get('effect'), name


def test_planning_lobby_reveals_top_card_cost_and_grants_correct_money():
    g = make_game()
    p = g.current_player()
    p.hand = [card(g, '企畫遊說')]
    p.deck.draw_pile = [Card('CheapBottom', 'command', {}), Card('ExpensiveTop', 'command', {})]
    # Make ExpensiveTop cost >= 3 via structured card lookup name.
    g.structured_cards.append({'name': 'ExpensiveTop', 'cost': {'money': 3, 'propaganda': 0}})

    result = g.play_card(0, mode='action')

    assert result.get('success'), result
    assert p.resources['money'] == 4
    assert names(p.deck.draw_pile)[-1] == 'ExpensiveTop'


if __name__ == '__main__':
    tests = [obj for name, obj in globals().items() if name.startswith('test_')]
    failures = 0
    for test in tests:
        try:
            test()
            print(f'PASS {test.__name__}')
        except Exception as exc:
            failures += 1
            print(f'FAIL {test.__name__}: {exc}')
    if failures:
        raise SystemExit(1)
