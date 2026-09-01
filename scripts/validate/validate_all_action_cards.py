import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, TurnPhase
from server.cards import Card

CARDS = json.loads((BASE / 'data' / 'action_cards_structured.v1.1.json').read_text(encoding='utf-8'))['cards']


def names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def starter(name, card_type='starter'):
    return Card(name, card_type, {})


def mk_game(player_count=2):
    players = [(f'p{i}', f'player{i}') for i in range(1, player_count + 1)]
    g = Game(players)
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    return g


def ensure_current_player(g):
    return g.current_player()


def setup_for_card(g, card_def):
    p = ensure_current_player(g)
    p.resources = {'money': 0, 'propaganda': 0}
    p.moves_left = 3
    p.build_range_bonus = 0
    g.purchase_area = []
    g.turn_log = g._new_turn_log()
    g.action_log = []

    # deterministic baselines
    p.organizations = {'北京': 1, '上海': 1}
    p.base = '北京'
    for idx, other in enumerate(g.players):
        if other is p:
            continue
        other.organizations = {f'對手城{idx}': 1}
        other.hand = [starter('追隨者'), starter('樂捐者')]
        other.deck.draw_pile = [starter('對手抽牌A'), starter('對手抽牌B')]
        other.deck.discard_pile = [starter('對手棄牌A')]
        other.resources = {'money': 0, 'propaganda': 0}
        other.moves_left = 3

    # current player baseline hand/deck/discard
    p.hand = [Card(card_def['name'], card_def['type'], card_def.get('resources', {}))]
    p.deck.draw_pile = [starter('抽牌A'), starter('抽牌B'), starter('抽牌C'), starter('抽牌D')]
    p.deck.discard_pile = [starter('棄牌A'), starter('棄牌B')]

    effects = [e['type'] for e in card_def.get('effect', [])]

    if 'optional_trash' in effects:
        p.hand.insert(0, Card('可垃圾牌', 'command', {}))

    if 'discard_self' in effects:
        p.hand.extend([Card('自棄1', 'command', {}), Card('自棄2', 'command', {})])

    if 'gain_from_discard' in effects or 'gain_any_from_discard' in effects:
        p.deck.discard_pile = [Card('可回收牌', 'command', {})]

    if 'trash_from_hand_or_discard' in effects:
        p.hand.insert(0, Card('非起始牌', 'command', {}))
        p.deck.discard_pile = [starter('追隨者'), Card('棄牌區非起始牌', 'command', {})]

    if 'conditional_draw' in effects:
        conds = [e for e in card_def.get('effect', []) if e['type'] == 'conditional_draw']
        for cond in conds:
            c = cond.get('condition')
            if c == 'played_propaganda_card':
                g.turn_log['played_propaganda_card'] = True
            elif c == 'played_money_card':
                g.turn_log['played_money_card'] = True
            elif c == 'successful_discard':
                g.turn_log['successful_discard'] = True
            elif c == 'canceled_propaganda_card':
                g.turn_log['canceled_propaganda_card'] = True

    if 'conditional_bonus' in effects:
        g.turn_log['non_starter_discard'] = True

    if 'shared_draw' in effects:
        for other in g.players:
            if other is not p:
                other.hand = [starter('對手手牌1')]
                other.deck.draw_pile = [starter('對手共抽1'), starter('對手共抽2')]

    if 'dissolve' in effects:
        p.organizations = {'北京': 1}
        for other in g.players:
            if other is not p:
                other.organizations = {'香港城': 1}
                break

    if 'refresh_purchase_area' in effects:
        p.deck.draw_pile = [Card('市場1', 'command', {}), Card('市場2', 'command', {}), Card('市場3', 'command', {}), Card('市場4', 'command', {})]

    return p


def validate_card(card_def):
    g = mk_game(2)
    p = setup_for_card(g, card_def)
    before = {
        'hand': names(p.hand),
        'resources': dict(p.resources),
        'moves_left': p.moves_left,
        'orgs': dict(p.organizations),
        'discard': names(p.deck.discard_pile),
        'purchase_area': names(g.purchase_area),
        'other_hands': {op.name: len(op.hand) for op in g.players if op is not p},
    }

    play_index = next(
        i for i, card in enumerate(p.hand)
        if getattr(card, 'name', str(card)) == card_def['name']
    )
    result = g.play_card(play_index, mode='action')

    after = {
        'hand': names(p.hand),
        'resources': dict(p.resources),
        'moves_left': p.moves_left,
        'orgs': dict(p.organizations),
        'discard': names(p.deck.discard_pile),
        'purchase_area': names(g.purchase_area),
        'other_hands': {op.name: len(op.hand) for op in g.players if op is not p},
        'turn_log': dict(g.turn_log),
        'log_tail': g.action_log[-3:],
    }

    checks = []
    if result.get('success') is True:
        checks.append('play_success')

    # played card should leave hand
    if card_def['name'] not in after['hand']:
        checks.append('card_left_hand')

    resources_delta = {
        k: after['resources'][k] - before['resources'][k]
        for k in before['resources']
    }

    summary = {
        'name': card_def['name'],
        'type': card_def['type'],
        'effects': [e['type'] for e in card_def.get('effect', [])],
        'result': result,
        'checks': checks,
        'resources_delta': resources_delta,
        'before': before,
        'after': after,
    }
    return summary


def main():
    results = [validate_card(card) for card in CARDS]
    records_dir = BASE / 'docs' / 'records' / 'card-ui'
    records_dir.mkdir(parents=True, exist_ok=True)
    out = records_dir / 'CARD_VALIDATION_RESULTS.json'
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

    md = []
    md.append('# CARD VALIDATION RESULTS')
    md.append('')
    md.append('日期：2026-05-03')
    md.append('')
    md.append(f'總卡數：{len(results)}')
    md.append('')
    for r in results:
        md.append(f"## {r['name']} ({r['type']})")
        md.append(f"- effects: {', '.join(r['effects']) if r['effects'] else 'none'}")
        md.append(f"- checks: {', '.join(r['checks'])}")
        md.append(f"- resources delta: money {r['resources_delta']['money']}, propaganda {r['resources_delta']['propaganda']}")
        md.append(f"- hand before → after: {len(r['before']['hand'])} → {len(r['after']['hand'])}")
        md.append(f"- moves_left before → after: {r['before']['moves_left']} → {r['after']['moves_left']}")
        md.append(f"- orgs before → after: {r['before']['orgs']} → {r['after']['orgs']}")
        md.append(f"- discard after: {r['after']['discard']}")
        md.append(f"- purchase_area after: {r['after']['purchase_area']}")
        md.append(f"- other_hands before → after: {r['before']['other_hands']} → {r['after']['other_hands']}")
        md.append(f"- turn_log after: {r['after']['turn_log']}")
        md.append(f"- log tail: {r['after']['log_tail']}")
        md.append('')
    md_out = records_dir / 'CARD_VALIDATION_RESULTS.md'
    md_out.write_text('\n'.join(md), encoding='utf-8')
    print(out)
    print(md_out)


if __name__ == '__main__':
    main()
