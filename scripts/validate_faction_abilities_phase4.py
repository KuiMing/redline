import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def ok(name, condition, detail=''):
    return {'name': name, 'ok': bool(condition), 'detail': detail}


def make_game(faction_id, base):
    g = Game([('p1', 'A'), ('p2', 'B')])
    for p in g.players:
        if p.id == 'p1':
            p.faction_id = faction_id
            p.base = base
            p.organizations = {base: 1}
        else:
            p.faction_id = 'red_army'
            p.base = '北京'
            p.organizations = {'北京': 1}
    g.faction_by_id = {f['id']: f for f in g.factions}
    return g


def test_huawen_chuanmei():
    g = make_game('falun_gong', '紐約')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    g.purchase_area = [Card('宣傳家', 'propaganda', {'propaganda': 2})]
    p.resources = {'money': 5, 'propaganda': 5}
    before_money = p.resources['money']
    before_prop = p.resources['propaganda']
    result = g.buy_card(0)
    spent_money = before_money - p.resources['money']
    return ok('huawen_chuanmei', result.get('success') is True and spent_money >= 0 and p.resources['propaganda'] == before_prop, f"result={result}, before_money={before_money}, resources={p.resources}")


def test_gejie_zizhu():
    g = make_game('minyun', '巴黎')
    p = g.players[0]
    g._apply_setup_abilities(p)
    names = [c.name for c in p.deck.discard_pile]
    return ok('gejie_zizhu', names.count('資助者') >= 1, str(names))


def test_huodongjia():
    g = make_game('gender_revolution', '北京')
    p = g.players[0]
    g._apply_setup_abilities(p)
    names = [c.name for c in p.deck.discard_pile]
    return ok('huodongjia', names.count('宣傳家') >= 2, str(names))


def test_ren_tong_ci_xin():
    g = make_game('gender_revolution', '北京')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    p.hand = [Card('宣傳測試', 'propaganda', {'propaganda': 1})]
    before = p.resources['propaganda']
    g.play_card(0, mode='action')
    after = p.resources['propaganda']
    return ok('ren_tong_ci_xin', after >= before + 2, f'before={before}, after={after}')


def main():
    results = [
        test_huawen_chuanmei(),
        test_gejie_zizhu(),
        test_huodongjia(),
        test_ren_tong_ci_xin(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    out = {'summary': summary, 'results': results}
    Path('FACTION_ABILITY_PHASE4_VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# FACTION ABILITY PHASE4 VALIDATION', '', f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", '']
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {r['detail']}")
    Path('FACTION_ABILITY_PHASE4_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
