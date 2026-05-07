import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def test_india_support_tier3_adds_three_distractions():
    g = Game([('p1', 'Tibet'), ('p2', 'Red')])
    t, r = g.players
    t.faction_id = 'tibet_dehradun'
    t.organizations = {'河內': 1, '紐約': 1}
    t.base = '德拉敦'
    r.faction_id = 'red_army'
    r.organizations = {'北京': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    t.hand = [g._make_support_card('印度奧援')]
    before = len(r.deck.discard_pile)
    result = g.play_card(0)
    after = len(r.deck.discard_pile)
    ok = result.get('success') and after - before == 3
    return {'name': 'india_support_tier3_adds_three_distractions', 'ok': ok, 'detail': {'before': before, 'after': after}}


def test_anglo_support_tier2_gains_money():
    g = Game([('p1', 'Any'), ('p2', 'Red')])
    a, r = g.players
    a.faction_id = 'federalists'
    a.organizations = {'東京': 1}
    a.base = '北京'
    r.faction_id = 'red_army'
    r.organizations = {'北京': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    a.hand = [g._make_support_card('英美奧援')]
    before = a.resources['money']
    result = g.play_card(0)
    after = a.resources['money']
    ok = result.get('success') and after - before >= 2
    return {'name': 'anglo_support_tier2_gains_money', 'ok': ok, 'detail': {'before': before, 'after': after}}


def test_nanyang_support_tier1_draw_then_discard_net_zero():
    g = Game([('p1', 'Any'), ('p2', 'Red')])
    a, r = g.players
    a.faction_id = 'federalists'
    a.organizations = {'北京': 1}
    a.base = '北京'
    r.faction_id = 'red_army'
    r.organizations = {'北京': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    a.hand = [g._make_support_card('南洋奧援'), Card('測試牌', 'command', {})]
    a.deck.draw_pile = [Card('補牌', 'command', {})]
    before = len(a.hand)
    result = g.play_card(0)
    after = len(a.hand)
    ok = result.get('success') and after == before - 1
    return {'name': 'nanyang_support_tier1_draw_then_discard_net_zero', 'ok': ok, 'detail': {'before': before, 'after': after}}


def test_east_asia_support_tier1_gains_two_propaganda():
    g = Game([('p1', 'Any'), ('p2', 'Red')])
    a, r = g.players
    a.faction_id = 'federalists'
    a.organizations = {'東京': 1, '北京': 1}
    a.base = '北京'
    r.faction_id = 'red_army'
    r.organizations = {'台東': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    a.hand = [g._make_support_card('東洋奧援')]
    before = a.resources['propaganda']
    result = g.play_card(0)
    after = a.resources['propaganda']
    ok = result.get('success') and after == before + 2
    return {'name': 'east_asia_support_tier1_gains_two_propaganda', 'ok': ok, 'detail': {'before': before, 'after': after}}


def test_northland_support_tier2_dissolves_one():
    g = Game([('p1', 'Any'), ('p2', 'Red')])
    a, r = g.players
    a.faction_id = 'federalists'
    a.organizations = {'東京': 1}
    a.base = '北京'
    r.faction_id = 'red_army'
    r.organizations = {'南京': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    a.hand = [g._make_support_card('北國奧援')]
    before = dict(r.organizations)
    result = g.play_card(0)
    after_total = sum(r.organizations.values())
    ok = result.get('success') and after_total == sum(before.values()) - 1
    return {'name': 'northland_support_tier2_dissolves_one', 'ok': ok, 'detail': {'before': before, 'after': r.organizations}}


def test_taiwan_support_tier1_gains_one_propaganda():
    g = Game([('p1', 'Any'), ('p2', 'Red')])
    a, r = g.players
    a.faction_id = 'federalists'
    a.organizations = {'莫斯科': 1}
    a.base = '北京'
    r.faction_id = 'red_army'
    r.organizations = {'南京': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    a.hand = [g._make_support_card('臺灣奧援')]
    before = a.resources['propaganda']
    result = g.play_card(0)
    after = a.resources['propaganda']
    ok = result.get('success') and after == before + 1
    return {'name': 'taiwan_support_tier1_gains_one_propaganda', 'ok': ok, 'detail': {'before': before, 'after': after}}


def main():
    results = [
        test_india_support_tier3_adds_three_distractions(),
        test_anglo_support_tier2_gains_money(),
        test_nanyang_support_tier1_draw_then_discard_net_zero(),
        test_east_asia_support_tier1_gains_two_propaganda(),
        test_northland_support_tier2_dissolves_one(),
        test_taiwan_support_tier1_gains_one_propaganda(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    (ROOT / 'SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'SUPPORT_CARD_EFFECTS_RUNTIME_VALIDATION.md').write_text(
        '# SUPPORT CARD EFFECTS RUNTIME VALIDATION\n\n' +
        f"- total: {summary['total']}\n- passed: {summary['passed']}\n- failed: {summary['failed']}\n\n" +
        '\n'.join(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {json.dumps(r['detail'], ensure_ascii=False)}" for r in results) + '\n',
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
