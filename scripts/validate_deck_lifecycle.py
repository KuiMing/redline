import json
import random
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.cards import Card
from server.deck import Deck
from server.game import Game, GamePhase, TurnPhase

OUT_JSON = BASE / 'DECK_LIFECYCLE_VALIDATION.json'
OUT_MD = BASE / 'DECK_LIFECYCLE_VALIDATION.md'


def make_card(name, card_type='test', money=0, propaganda=0):
    return Card(name, card_type, {'money': money, 'propaganda': propaganda})


def card_names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def player_zone_snapshot(player):
    return {
        'hand': card_names(player.hand),
        'draw_pile': card_names(player.deck.draw_pile),
        'discard_pile': card_names(player.deck.discard_pile),
        'hand_count': len(player.hand),
        'draw_count': len(player.deck.draw_pile),
        'discard_count': len(player.deck.discard_pile),
        'total_cards': len(player.hand) + len(player.deck.draw_pile) + len(player.deck.discard_pile),
    }


def make_game():
    random.seed(20260510)
    game = Game([('p1', 'actor'), ('p2', 'red')])
    actor = game.players[0]
    other = game.players[1]

    actor.id = 'p1'
    actor.name = 'actor'
    actor.faction_id = 'red_army'
    actor.base = '北京'
    actor.organizations = {'北京': 1}
    actor.resources = {'money': 0, 'propaganda': 0}
    actor.moves_left = 0

    other.id = 'p2'
    other.name = 'other'
    other.faction_id = 'hong_kong'
    other.base = '香港城'
    other.organizations = {'香港城': 1}

    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.winner = None
    return game, actor


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def end_turn_from_action(game):
    # ACTION -> END -> next player's EVENT
    action_to_end = game.advance_turn_phase()
    end_to_next = game.advance_turn_phase()
    return {'action_to_end': action_to_end, 'end_to_next': end_to_next}


def run_checks():
    checks = []

    # 1. End turn discards current hand, resets turn resources, and draws back to five.
    game, player = make_game()
    player.hand = [make_card('H1'), make_card('H2'), make_card('H3')]
    # Deck.draw pops from the end, so D4/D3 are drawn first; exact order is not the rule under test.
    player.deck = Deck([])
    player.deck.draw_pile = [make_card('D1'), make_card('D2'), make_card('D3'), make_card('D4')]
    player.deck.discard_pile = [make_card('X1'), make_card('X2')]
    player.resources = {'money': 7, 'propaganda': 6}
    player.moves_left = 0
    before = player_zone_snapshot(player) | {'resources': dict(player.resources), 'moves_left': player.moves_left}
    result = end_turn_from_action(game)
    after = player_zone_snapshot(player) | {'resources': dict(player.resources), 'moves_left': player.moves_left, 'turn_phase': game.turn_phase.value, 'current_player': game.current_player().name}
    checks.append(check(
        'end_turn_discards_hand_resets_and_draws_to_five',
        result['action_to_end'].get('success') is True
        and result['end_to_next'].get('success') is True
        and after['hand_count'] == 5
        and after['total_cards'] == before['total_cards']
        and after['resources'] == {'money': 0, 'propaganda': 0}
        and after['moves_left'] == 0
        and after['turn_phase'] == TurnPhase.EVENT.value
        and after['current_player'] == 'other'
        and set(after['hand']).issubset(set(before['hand'] + before['draw_pile'] + before['discard_pile'])),
        {'before': before, 'result': result, 'after': after, 'rule': '回合結束：棄掉當前手牌、重置資源與移動點為 0、補到 5 張且總牌數守恆。'},
    ))

    # 2. Drawing more cards than draw pile contains reshuffles discard pile and continues drawing.
    game, player = make_game()
    player.hand = []
    player.deck = Deck([])
    player.deck.draw_pile = [make_card('D1'), make_card('D2')]
    player.deck.discard_pile = [make_card('R1'), make_card('R2'), make_card('R3')]
    before = player_zone_snapshot(player)
    drawn = player.deck.draw(4)
    after = player_zone_snapshot(player)
    checks.append(check(
        'draw_reshuffles_discard_when_draw_pile_runs_out',
        len(drawn) == 4
        and set(card_names(drawn)).issubset({'D1', 'D2', 'R1', 'R2', 'R3'})
        and after['total_cards'] + len(drawn) == before['total_cards']
        and after['discard_count'] == 0,
        {'before': before, 'drawn': card_names(drawn), 'after': after, 'rule': '牌庫不足抽牌時，棄牌堆洗回牌庫並繼續抽；不憑空增減牌。'},
    ))

    # 3. If draw pile and discard are both exhausted, draw only what exists and do not crash.
    game, player = make_game()
    player.hand = []
    player.deck = Deck([])
    player.deck.draw_pile = [make_card('Only1'), make_card('Only2')]
    player.deck.discard_pile = []
    before = player_zone_snapshot(player)
    drawn = player.deck.draw(5)
    after = player_zone_snapshot(player)
    checks.append(check(
        'draw_with_insufficient_total_cards_draws_available_cards_only',
        card_names(drawn) == ['Only2', 'Only1']
        and after['draw_count'] == 0
        and after['discard_count'] == 0
        and after['total_cards'] + len(drawn) == before['total_cards'],
        {'before': before, 'drawn': card_names(drawn), 'after': after, 'rule': '牌庫與棄牌堆都不足時，不 crash；能抽幾張就抽幾張。'},
    ))

    # 4. Played ordinary cards leave hand and enter discard; total cards remain conserved.
    game, player = make_game()
    player.hand = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    player.deck = Deck([])
    player.deck.draw_pile = []
    player.deck.discard_pile = []
    before = player_zone_snapshot(player) | {'resources': dict(player.resources)}
    result = game.play_card(0, mode='resource')
    after = player_zone_snapshot(player) | {'resources': dict(player.resources)}
    checks.append(check(
        'ordinary_played_card_moves_from_hand_to_discard',
        result.get('success') is True
        and after['hand'] == []
        and after['discard_pile'] == ['追隨者']
        and after['total_cards'] == before['total_cards']
        and after['resources'] == {'money': 0, 'propaganda': 1},
        {'before': before, 'result': result, 'after': after, 'rule': '普通打出的卡從手牌離開後進玩家棄牌堆，並保持玩家牌張總數守恆。'},
    ))

    # 5. Purchased random-market cards enter the buyer discard pile and leave the market slot.
    game, player = make_game()
    player.resources = {'money': 99, 'propaganda': 99}
    static_count = len(game._static_purchase_cards())
    buy_index = static_count
    card_to_buy = game.purchase_area[buy_index]
    card_name = getattr(card_to_buy, 'name', str(card_to_buy))
    before = player_zone_snapshot(player) | {
        'resources': dict(player.resources),
        'purchase_area_count': len(game.purchase_area),
        'purchase_area': card_names(game.purchase_area),
        'buy_index': buy_index,
        'card_to_buy': card_name,
    }
    result = game.buy_card(buy_index)
    after = player_zone_snapshot(player) | {
        'resources': dict(player.resources),
        'purchase_area_count': len(game.purchase_area),
        'purchase_area': card_names(game.purchase_area),
    }
    checks.append(check(
        'purchased_random_market_card_enters_discard_and_leaves_market',
        result.get('success') is True
        and card_name in after['discard_pile']
        and after['total_cards'] == before['total_cards'] + 1
        and after['purchase_area_count'] == before['purchase_area_count'] - 1
        and len(after['purchase_area']) == len(before['purchase_area']) - 1,
        {'before': before, 'result': result, 'after': after, 'rule': '購買隨機市場牌後，該牌進玩家棄牌堆，並從購買區移除；補市場由回合結束流程處理。'},
    ))

    # 6. End turn refills random market back to static + five when purchase deck has cards.
    before_market_count = len(game.purchase_area)
    refill_result = end_turn_from_action(game)
    after_market = card_names(game.purchase_area)
    checks.append(check(
        'end_turn_refills_random_market_to_static_plus_five',
        refill_result['action_to_end'].get('success') is True
        and refill_result['end_to_next'].get('success') is True
        and before_market_count == static_count + 4
        and len(after_market) == static_count + 5,
        {'before_market_count': before_market_count, 'result': refill_result, 'after_market_count': len(after_market), 'after_market': after_market, 'rule': '回合結束時購買區補回常設 6 張 + 隨機 5 張。'},
    ))

    return checks


def write_outputs(checks):
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    out = {'date': date.today().isoformat(), 'summary': summary, 'checks': checks}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    lines = ['# DECK LIFECYCLE VALIDATION', '', f"日期：{out['date']}", '', f"summary: {summary}", '']
    for item in checks:
        status = 'PASS' if item['passed'] else 'FAIL'
        lines.append(f"## {item['name']} — {status}")
        for k, v in item['details'].items():
            lines.append(f"- {k}: {v}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return out


def main():
    out = write_outputs(run_checks())
    print(json.dumps({'summary': out['summary'], 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    if out['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
