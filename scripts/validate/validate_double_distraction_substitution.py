import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def _new_game():
    g = Game([('p1', 'A'), ('p2', 'B'), ('p3', 'C')])
    a, b, c = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    c.faction_id = 'hong_kong'
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    for p in g.players:
        p.deck.discard_pile = []
    return g, a, b, c


def _names(cards):
    return [getattr(x, 'name', str(x)) for x in cards]


def case_helper_normal_and_substitution():
    g, a, b, c = _new_game()
    normal = g._take_internal_conflict_cards(2, reason='test')
    g.static_purchase_supply['內鬥'] = 0
    ds_before = g.static_purchase_supply['分神']
    substituted = g._take_internal_conflict_cards(1, reason='test')
    checks = {
        'normal_two_internal_conflicts': _names(normal) == ['內鬥', '內鬥'],
        'normal_consumed_supply': g.static_purchase_supply['內鬥'] == 0 and True,
        'substituted_two_distractions': _names(substituted) == ['分神', '分神'],
        'distraction_supply_consumed': g.static_purchase_supply['分神'] == ds_before - 2,
    }
    return {'name': 'helper_normal_and_substitution', 'checks': checks, 'ok': all(checks.values())}


def case_helper_partial_and_empty():
    g, a, b, c = _new_game()
    g.static_purchase_supply['內鬥'] = 0
    g.static_purchase_supply['分神'] = 1
    partial = g._take_internal_conflict_cards(1, reason='test')
    empty = g._take_internal_conflict_cards(1, reason='test')
    checks = {
        'partial_gives_one_distraction': _names(partial) == ['分神'],
        'empty_gives_nothing': empty == [],
        'both_empty_logged': any('內鬥與分神供應皆空' in str(line) for line in g.action_log),
    }
    return {'name': 'helper_partial_and_both_empty', 'checks': checks, 'ok': all(checks.values())}


def case_divide_card_consumes_supply_and_substitutes():
    # 離間（add_internal_conflict）過去憑空創造內鬥、不扣供應；現在應扣供應且耗盡時替代
    g, a, b, c = _new_game()
    ic_before = g.static_purchase_supply['內鬥']
    g.effect_engine.execute({'type': 'add_internal_conflict', 'count': 2, 'target_player_id': c.id}, a, g, context={'card_name': '離間'})
    checks = {
        'target_gained_two_internal_conflicts': _names(c.deck.discard_pile) == ['內鬥', '內鬥'],
        'supply_consumed': g.static_purchase_supply['內鬥'] == ic_before - 2,
    }
    g2, a2, b2, c2 = _new_game()
    g2.static_purchase_supply['內鬥'] = 1
    ds_before = g2.static_purchase_supply['分神']
    g2.effect_engine.execute({'type': 'add_internal_conflict', 'count': 2, 'target_player_id': c2.id}, a2, g2, context={'card_name': '離間'})
    checks.update({
        'mixed_substitution_when_supply_runs_out_midway': _names(c2.deck.discard_pile) == ['內鬥', '分神', '分神'],
        'distraction_supply_consumed': g2.static_purchase_supply['分神'] == ds_before - 2,
    })
    return {'name': 'divide_card_consumes_supply_and_substitutes', 'checks': checks, 'ok': all(checks.values())}


def case_event_gain_substitutes():
    g, a, b, c = _new_game()
    g.static_purchase_supply['內鬥'] = 0
    gained = g._gain_event_card(a, '內鬥', 1)
    checks = {
        'gained_two_substitutes': gained == 2 and _names(a.deck.discard_pile) == ['分神', '分神'],
    }
    return {'name': 'event_gain_internal_conflict_substitutes', 'checks': checks, 'ok': all(checks.values())}


def case_leak_card_substitutes():
    g, a, b, c = _new_game()
    g.static_purchase_supply['內鬥'] = 0
    c.deck.draw_pile = [Card('高價牌', 'command', {})]
    g._card_purchase_cost = lambda card: {'money': 2, 'propaganda': 0}
    g.effect_engine.execute({'type': 'leak_top_deck'}, a, g, context={'card_name': '走漏風聲', 'target_player_id': c.id})
    names = _names(c.deck.discard_pile)
    checks = {
        'top_card_discarded_plus_two_distractions': names == ['高價牌', '分神', '分神'],
    }
    return {'name': 'leak_top_deck_substitutes', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_helper_normal_and_substitution(),
        case_helper_partial_and_empty(),
        case_divide_card_consumes_supply_and_substitutes(),
        case_event_gain_substitutes(),
        case_leak_card_substitutes(),
    ]
    summary = {
        'scope': ['C1 雙倍分神替代', '政工部', '離間/情報網A', '走漏風聲', '事件放入內鬥'],
        'purpose': (
            'C1 per 2026-07-11 user ruling (option B): whenever an effect places 內鬥 and the '
            '內鬥 static supply is exhausted, substitute 2×分神 per 內鬥 (partial if 分神 '
            'supply is short; logged no-op when both are empty). Centralized in '
            '_take_internal_conflict_cards and wired into every placement site: 政工部 '
            'topdeck, event gains, 走漏風聲, and the add_internal_conflict etype (離間/'
            '情報網A) — the last of which previously created 內鬥 out of thin air without '
            'consuming supply at all; it now consumes supply too.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'DOUBLE_DISTRACTION_SUBSTITUTION_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'DOUBLE_DISTRACTION_SUBSTITUTION_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 內鬥耗盡改雙倍分神替代驗證（C1）\n\n'
        '可重跑指令：`python3 scripts/validate/validate_double_distraction_substitution.py`\n\n'
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False, default=str))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
