import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def ok(name, condition, detail=''):
    return {'name': name, 'ok': bool(condition), 'detail': detail}


def make_game(faction_id, base, enemy='red_army'):
    g = Game([('p1', 'A'), ('p2', 'B')])
    for p in g.players:
        if p.id == 'p1':
            p.faction_id = faction_id
            p.base = base
            p.organizations = {base: 1}
        else:
            p.faction_id = enemy
            p.base = '北京'
            p.organizations = {'北京': 1}
    g.faction_by_id = {f['id']: f for f in g.factions}
    return g


def test_nonviolence_play_block():
    g = make_game('uyghur_munich', '慕尼黑')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    p.hand = [Card('武裝測試', 'armed', {'money': 0})]
    result = g.play_card(0, mode='action')
    return ok('nonviolence_play_block', result.get('error') == '非暴力：不能打出武裝類卡牌', str(result))


def test_nonviolence_buy_block():
    g = make_game('tibet_dharamsala', '達蘭薩拉')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    g.purchase_area = [Card('武裝者', 'armed', {'propaganda': 1})]
    result = g.buy_card(0)
    return ok('nonviolence_buy_block', result.get('error') == '非暴力：不能購買武裝類卡牌', str(result))


def test_guerrilla_forces_red_discard():
    g = make_game('uyghur_istanbul', '伊斯坦堡')
    p = g.players[0]
    red = g.players[1]
    red.faction_id = 'red_army'
    red.hand = [Card('紅軍手牌', 'money', {'money': 1})]
    before = len(red.hand)
    g._apply_guerrilla_on_build(p, '北京')
    return ok('guerrilla_forces_red_discard', len(red.hand) == before - 1, f"red_hand={len(red.hand)}")


def test_guerrilla_draw_if_red_empty():
    g = make_game('tibet_chogu', '哲古宗')
    p = g.players[0]
    red = g.players[1]
    red.faction_id = 'red_army'
    p.hand = []
    p.deck.draw_pile = [Card('補牌A', 'money', {'money': 1})]
    red.hand = []
    g._apply_guerrilla_on_build(p, '北京')
    return ok('guerrilla_draw_if_red_empty', len(p.hand) == 1, f"hand={len(p.hand)}")


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        test_nonviolence_play_block(),
        test_nonviolence_buy_block(),
        test_guerrilla_forces_red_discard(),
        test_guerrilla_draw_if_red_empty(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    out = {'summary': summary, 'results': results}
    (RECORD_DIR / 'FACTION_ABILITY_PHASE3_VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# FACTION ABILITY PHASE3 VALIDATION', '', f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", '']
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {r['detail']}")
    (RECORD_DIR / 'FACTION_ABILITY_PHASE3_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
