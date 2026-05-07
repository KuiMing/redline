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
    return g, t, o


def test_non_support_card_no_bonus():
    g, t, _ = make_game()
    t.hand = [Card('交通經驗丙', 'transport', {'money': 1})]
    before = t.resources['money']
    result = g.play_card(0)
    after = t.resources['money']
    ok = result.get('success') and after == before + 1
    return {'name': 'non_support_card_no_bonus', 'ok': ok, 'detail': {'result': result, 'before': before, 'after': after}}


def test_buy_non_support_card_allowed():
    g, t, _ = make_game()
    t.resources = {'money': 5, 'propaganda': 5}
    g.purchase_area = [Card('資助者', 'money', {'money': 2})]
    result = g.buy_card(0)
    ok = result.get('success') is True
    return {'name': 'buy_non_support_card_allowed', 'ok': ok, 'detail': result}


def test_gain_from_discard_non_support_card_allowed():
    g, t, _ = make_game()
    t.deck.discard_pile = [Card('資助者', 'money', {'money': 2})]
    g.effect_engine.execute({'type': 'gain_any_from_discard'}, t, g)
    ok = any(getattr(c, 'name', '') == '資助者' for c in t.hand)
    return {'name': 'gain_from_discard_non_support_card_allowed', 'ok': ok, 'detail': {'hand': [c.name for c in t.hand]}}


def main():
    results = [
        test_non_support_card_no_bonus(),
        test_buy_non_support_card_allowed(),
        test_gain_from_discard_non_support_card_allowed(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    (ROOT / 'INDIA_RESEARCH_ROOM_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# INDIA RESEARCH ROOM VALIDATION', '', f"- total: {summary['total']}", f"- passed: {summary['passed']}", f"- failed: {summary['failed']}", '']
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {json.dumps(r['detail'], ensure_ascii=False)}")
    (ROOT / 'INDIA_RESEARCH_ROOM_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
