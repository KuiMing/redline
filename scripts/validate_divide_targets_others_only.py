import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'action-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


def _new_game(n_players=3, red_plays=True):
    names = [('p1', 'RED'), ('p2', 'X'), ('p3', 'Y'), ('p4', 'Z')][:n_players]
    g = Game(names)
    for i, p in enumerate(g.players):
        p.faction_id = 'red_army' if i == 0 else 'liberals'
        p.deck.discard_pile = []
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    caster = g.players[0]
    caster.hand = [Card('離間', 'spy', {'propaganda': 2})]
    return g, caster


def _names(cards):
    return [getattr(c, 'name', str(c)) for c in cards]


def case_red_divide_targets_others_only():
    g, red = _new_game(3)
    ic_before = g.static_purchase_supply['內鬥']
    result = g.play_card(0, mode='action')
    others = g.players[1:]
    checks = {
        'play_ok': result.get('success') is True,
        'caster_deck_has_no_internal_conflict': '內鬥' not in _names(red.deck.discard_pile),
        'each_other_player_got_one': all(_names(p.deck.discard_pile).count('內鬥') == 1 for p in others),
        'supply_consumed_two': g.static_purchase_supply['內鬥'] == ic_before - 2,
    }
    return {'name': 'red_divide_targets_others_only', 'checks': checks, 'ok': all(checks.values())}


def case_max_three_targets():
    g, red = _new_game(4)
    g.play_card(0, mode='action')
    others = g.players[1:]
    got = [_names(p.deck.discard_pile).count('內鬥') for p in others]
    checks = {
        'three_targets_each_one': got == [1, 1, 1],
        'caster_untouched': '內鬥' not in _names(red.deck.discard_pile),
    }
    return {'name': 'up_to_three_targets_one_each', 'got': got, 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_red_divide_targets_others_only(),
        case_max_three_targets(),
    ]
    summary = {
        'scope': ['離間'],
        'purpose': (
            'P1 playtest item: 離間 ("在至多3位玩家棄牌堆各放入1張內鬥") was structured as '
            'count:3 with no target, and add_internal_conflict\'s no-target fallback placed '
            'all three 內鬥 into the CASTER\'s own discard pile — the reported red-army bug. '
            'The card is now target_scope:"others"/max_targets:3/count:1-each, the fallback '
            'to the caster is removed (logged no-op instead), and the supply-consumption fix '
            'from C1 applies. 情報網 option A shares the same path.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'DIVIDE_TARGETS_OTHERS_ONLY_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'DIVIDE_TARGETS_OTHERS_ONLY_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 離間內鬥僅放對方牌堆驗證\n\n'
        '可重跑指令：`python3 scripts/validate_divide_targets_others_only.py`\n\n'
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
