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


def test_democracy_frontline():
    g = make_game('minyun', '巴黎')
    p = g.players[0]
    p.resources = {'money': 1, 'propaganda': 1}
    before = len(p.deck.discard_pile)
    result = g._activated_faction_action(p, '民主陣線')
    after = len(p.deck.discard_pile)
    return ok('democracy_frontline', result.get('success') is True and after == before + 1, f"result={result}, discard={after}")


def test_political_probe():
    g = make_game('liberals', '北京')
    p = g.players[0]
    p.hand = []
    p.deck.draw_pile = [Card('奇數牌', 'money', {'money': 1})]
    g._top_card_cost_total = lambda card: 1
    result = g._activated_faction_action(p, '立場試探')
    return ok('political_probe', result.get('success') is True and len(p.hand) == 1, f"result={result}, hand={len(p.hand)}")


def test_huawen_media_spend_money():
    g = make_game('falun_gong', '紐約')
    p = g.players[0]
    g.turn_phase = TurnPhase.ACTION
    g.purchase_area = [Card('宣傳家', 'propaganda', {'propaganda': 2})]
    p.resources = {'money': 3, 'propaganda': 0}
    result = g.buy_card(0)
    return ok('huawen_media_spend_money', result.get('success') is True and p.resources['money'] == 0, f"result={result}, resources={p.resources}")


def test_gambler_whisper():
    g = make_game('aomen', '澳門')
    p = g.players[0]
    p.hand = [Card('墊牌', 'money', {'money': 1})]
    p.deck.draw_pile = [Card('奇數牌', 'money', {'money': 1})]
    g._top_card_cost_total = lambda card: 1
    before = dict(p.resources)
    result = g._activated_faction_action(p, '賭徒耳語', guess='odd')
    after = dict(p.resources)
    return ok('gambler_whisper', result.get('success') is True and after['money'] >= before['money'] + 3 and after['propaganda'] >= before['propaganda'] + 3, f"result={result}, resources={after}")


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        test_democracy_frontline(),
        test_political_probe(),
        test_huawen_media_spend_money(),
        test_gambler_whisper(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    out = {'summary': summary, 'results': results}
    (RECORD_DIR / 'FACTION_ABILITY_PHASE5_VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# FACTION ABILITY PHASE5 VALIDATION', '', f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", '']
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {r['detail']}")
    (RECORD_DIR / 'FACTION_ABILITY_PHASE5_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
