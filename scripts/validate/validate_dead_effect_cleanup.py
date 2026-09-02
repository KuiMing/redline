#!/usr/bin/env python3
"""凝聚共識/武裝集團 dead-effect JSON cleanup: behavior must be unchanged.

The JSON used to declare a conditional_bonus (凝聚共識) and a conditional_draw
(武裝集團) step after a pending-choice step. Both card pipelines stop at the
pending choice and their resolvers do NOT resume remaining_effects — the bonus
is granted via the choice's grant_propaganda_if_all_non_starter flag and the
draw via draw_on_success — so those JSON steps were unreachable dead
declarations. This validator pins the real behavior and asserts the dead
declarations stay removed.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def case_forge_consensus_bonus_via_choice_flag():
    g = Game([('p1', 'me'), ('p2', 'opp')])
    me = g.players[0]
    for p in g.players:
        p.faction_id = 'liberals'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    me.hand = [Card('凝聚共識', 'command', {'propaganda': 3}), Card('非起始A', 'command', {}), Card('非起始B', 'command', {})]
    me.deck.draw_pile = [Card(f'抽{i}', 'command', {}) for i in range(3)]
    me.resources = {'money': 0, 'propaganda': 0}
    g.play_card(0, mode='action')
    pc = g.pending_choice or {}
    cards = pc.get('cards') or []
    idxs = [i for i, c in enumerate(cards) if c.name in ('非起始A', '非起始B')][:2]
    g.resolve_pending_choice(me.id, idxs)
    checks = {
        'bonus_flag_on_choice': pc.get('grant_propaganda_if_all_non_starter') == 2,
        'bonus_granted_once': me.resources['propaganda'] == 2,
        'hand_after': len(me.hand) == 3,  # 3 drawn + 2 discarded from 5
    }
    return {'name': 'forge_consensus_bonus_flows_through_choice_flag', 'checks': checks, 'ok': all(checks.values())}


def case_armed_unit_draw_via_draw_on_success():
    g = Game([('p1', 'me'), ('p2', 'opp')])
    me, opp = g.players
    me.faction_id = 'red_army'
    opp.faction_id = 'liberals'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    me.organizations = {'北京': 1}
    opp.organizations = {'天津': 1}
    me.hand = [Card('武裝集團', 'armed', {'money': 1, 'propaganda': 2})]
    me.deck.draw_pile = [Card('成功抽牌', 'command', {})]
    opp.hand = [Card('opp手1', 'command', {}), Card('opp手2', 'command', {}), Card('opp手3', 'command', {})]
    g.play_card(0, mode='action', target_player_id=opp.id)
    pc = g.pending_choice or {}
    hand_before = len(me.hand)
    g.resolve_pending_choice(opp.id, [0, 1])
    checks = {
        'choice_key': pc.get('choice_key') == 'armed_target_discard',
        'draw_on_success_flag': pc.get('draw_on_success') == 1,
        'initiator_drew_one': len(me.hand) - hand_before == 1,
        'target_discarded_two': len(opp.hand) == 1,
    }
    return {'name': 'armed_unit_success_draw_flows_through_draw_on_success', 'checks': checks, 'ok': all(checks.values())}


def case_dead_declarations_removed():
    data = json.load(open(ROOT / 'data' / 'action_cards_structured.v1.1.json', encoding='utf-8'))
    cards = data['cards'] if isinstance(data, dict) and 'cards' in data else data
    if isinstance(cards, dict):
        cards = list(cards.values())
    by_name = {c['name']: c for c in cards}
    forge_types = [e['type'] for e in by_name['凝聚共識']['effect']]
    armed_types = [e['type'] for e in by_name['武裝集團']['effect']]
    checks = {
        'forge_has_no_conditional_bonus': 'conditional_bonus' not in forge_types and forge_types == ['draw', 'discard_self'],
        'armed_has_no_conditional_draw': 'conditional_draw' not in armed_types and armed_types == ['force_discard'],
    }
    return {'name': 'dead_declarations_removed_from_json', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_forge_consensus_bonus_via_choice_flag(),
        case_armed_unit_draw_via_draw_on_success(),
        case_dead_declarations_removed(),
    ]
    summary = {
        'scope': ['凝聚共識/武裝集團 死代碼 JSON 宣告清理'],
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    (RECORD_DIR / 'DEAD_EFFECT_CLEANUP_VALIDATION.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (RECORD_DIR / 'DEAD_EFFECT_CLEANUP_VALIDATION.md').write_text(
        '# 凝聚共識/武裝集團 死代碼 JSON 宣告清理驗證\n\n'
        '可重跑指令：`python3 scripts/validate/validate_dead_effect_cleanup.py`\n\n'
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
