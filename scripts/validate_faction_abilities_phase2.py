import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def ok(name, condition, detail=''):
    return {'name': name, 'ok': bool(condition), 'detail': detail}


def make_game(faction_id='federalists', base='北京'):
    g = Game([('p1', 'A'), ('p2', 'B')])
    g.faction_by_id = {f['id']: f for f in g.factions}
    for p in g.players:
        if p.id == 'p1':
            p.faction_id = faction_id
            p.base = base
            p.organizations = {base: 1}
        else:
            p.faction_id = 'red_army'
            p.base = '北京'
            p.organizations = {'北京': 1}
    return g


def test_first_money_draw():
    g = make_game('federalists', '北京')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    p.hand = [Card('金錢測試', 'money', {'money': 1})]
    p.deck.draw_pile = [Card('補牌A', 'money', {'money': 1})]
    before = len(p.hand)
    g.play_card(0, mode='action')
    after = len(p.hand)
    return ok('first_money_draw', after >= before, f'before={before}, after={after}')


def test_combo_three_unique():
    g = make_game('manchuria', '東京')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    p.hand = [
        Card('甲', 'command', {}),
        Card('乙', 'command', {}),
        Card('丙', 'command', {}),
    ]
    g.structured_cards.extend([
        {'name': '甲', 'type': 'command', 'resources': {}, 'effect': []},
        {'name': '乙', 'type': 'command', 'resources': {}, 'effect': []},
        {'name': '丙', 'type': 'command', 'resources': {}, 'effect': []},
    ])
    g.action_engine.cards.update({c['name']: c for c in g.structured_cards if c['name'] in {'甲','乙','丙'}})
    g.play_card(0, mode='action')
    g.play_card(0, mode='action')
    g.play_card(0, mode='action')
    return ok('combo_three_unique', p.resources['money'] >= 3 or p.resources['propaganda'] >= 3, str(p.resources))


def test_martyr_draw():
    g = make_game('underground_church', '北京')
    church = g.players[0]
    attacker = g.players[1]
    church.organizations = {'北京': 1}
    church.hand = []
    church.deck.draw_pile = [Card('補牌A', 'money', {'money': 1})]
    attacker.hand = [Card('測試棄牌', 'money', {'money': 1})]
    before = len(church.hand)
    g.dissolve_organization(attacker, church, '北京', source='card')
    # current engine still missing martyr hook; this test documents target behavior
    after = len(church.hand)
    return ok('martyr_draw_target_behavior', after >= before + 1, f'before={before}, after={after}')


def test_first_money_gain2():
    g = make_game('uyghur_munich', '慕尼黑')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    p.hand = [Card('金錢測試', 'money', {'money': 1})]
    before = p.resources['money']
    g.play_card(0, mode='action')
    after = p.resources['money']
    return ok('first_money_gain2', after >= before + 2, f'before={before}, after={after}')


def main():
    results = [
        test_first_money_draw(),
        test_combo_three_unique(),
        test_martyr_draw(),
        test_first_money_gain2(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    out = {'summary': summary, 'results': results}
    Path('FACTION_ABILITY_PHASE2_VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# FACTION ABILITY PHASE2 VALIDATION', '', f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", '']
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {r['detail']}")
    Path('FACTION_ABILITY_PHASE2_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
