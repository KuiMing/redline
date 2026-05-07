import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def make_game():
    g = Game([('p1', 'Tibet'), ('p2', 'Other')])
    t, o = g.players
    t.faction_id = 'tibet_dehradun'
    t.base = '德拉敦'
    t.organizations = {'德拉敦': 1}
    o.faction_id = 'red_army'
    o.base = '北京'
    o.organizations = {'北京': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    return g, t


def test_support_taxonomy_marks_india_support():
    g, _ = make_game()
    card = Card('印度奧援', 'support', {'money': 0})
    ok = g._is_india_flag_card(card) is True
    return {'name': 'support_taxonomy_marks_india_support', 'ok': ok, 'detail': {'is_india_flag': g._is_india_flag_card(card)}}


def test_buy_india_support_allowed():
    g, t = make_game()
    t.resources = {'money': 5, 'propaganda': 5}
    g.purchase_area = [Card('印度奧援', 'support', {'money': 0})]
    result = g.buy_card(0)
    ok = result.get('success') is True
    return {'name': 'buy_india_support_allowed', 'ok': ok, 'detail': result}


def test_buy_non_india_support_blocked():
    g, t = make_game()
    t.resources = {'money': 5, 'propaganda': 5}
    g.purchase_area = [Card('英美奧援', 'support', {'money': 0})]
    result = g.buy_card(0)
    ok = result.get('error') == '印度研究分析室：不能持有印度旗幟以外的旗幟卡'
    return {'name': 'buy_non_india_support_blocked', 'ok': ok, 'detail': result}


def test_gain_non_india_support_from_discard_blocked():
    g, t = make_game()
    t.deck.discard_pile = [Card('英美奧援', 'support', {'money': 0})]
    g.effect_engine.execute({'type': 'gain_any_from_discard'}, t, g)
    ok = all(getattr(c, 'name', '') != '英美奧援' for c in t.hand)
    return {'name': 'gain_non_india_support_from_discard_blocked', 'ok': ok, 'detail': {'hand': [c.name for c in t.hand]}}


def main():
    results = [
        test_support_taxonomy_marks_india_support(),
        test_buy_india_support_allowed(),
        test_buy_non_india_support_blocked(),
        test_gain_non_india_support_from_discard_blocked(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    (ROOT / 'INDIA_RESEARCH_ROOM_SUPPORT_TAXONOMY_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# INDIA RESEARCH ROOM SUPPORT TAXONOMY VALIDATION', '', f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", '']
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {json.dumps(r['detail'], ensure_ascii=False)}")
    (ROOT / 'INDIA_RESEARCH_ROOM_SUPPORT_TAXONOMY_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
