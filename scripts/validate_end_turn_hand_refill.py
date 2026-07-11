import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'playtest-flow'
sys.path.insert(0, str(ROOT))

from server.game import Game, GamePhase, TurnPhase
from server.cards import Card


def _new_game(faction_id='liberals'):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = 'red_army'
    a.organizations = {}
    b.organizations = {}
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.END
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    a.deck.draw_pile = [Card(f'補{i}', 'command', {}) for i in range(1, 11)]
    a.deck.discard_pile = []
    return g, a, b


def case_keep_hand_top_up():
    g, a, b = _new_game()
    kept = [Card('留著1', 'command', {}), Card('留著2', 'command', {})]
    a.hand = list(kept)
    g._end_turn()
    names = [c.name for c in a.hand]
    checks = {
        'hand_size_five': len(a.hand) == 5,
        'existing_cards_kept': all(c in a.hand for c in kept),
        'kept_cards_not_discarded': not any(c.name.startswith('留著') for c in a.deck.discard_pile),
        'drew_only_three': sum(1 for n in names if n.startswith('補')) == 3,
    }
    return {'name': 'keep_hand_and_top_up_to_five', 'hand': names, 'checks': checks, 'ok': all(checks.values())}


def case_five_or_more_no_draw():
    g, a, b = _new_game()
    a.hand = [Card(f'滿{i}', 'command', {}) for i in range(6)]
    g._end_turn()
    checks = {
        'six_cards_kept': len(a.hand) == 6,
        'no_extra_draw': not any(c.name.startswith('補') for c in a.hand),
    }
    return {'name': 'five_or_more_cards_no_draw_no_discard', 'checks': checks, 'ok': all(checks.values())}


def case_local_society_extra_draw():
    # 本土社團（台灣綠線）：本回合曾於牆內建立組織 → 行動階段結束時額外抽1張 → 最終6張
    g, a, b = _new_game('taiwan_green')
    a.hand = [Card(f'手{i}', 'command', {}) for i in range(3)]
    g.turn_log['built_towns'] = ['昆明']  # 牆內
    g._end_turn()
    checks = {
        'ends_with_six_cards': len(a.hand) == 6,
        'ability_logged': any('本土社團' in str(line) for line in g.action_log),
    }
    return {'name': 'local_society_extra_draw_reaches_six', 'hand_size': len(a.hand), 'checks': checks, 'ok': all(checks.values())}


def case_no_build_no_extra():
    g, a, b = _new_game('taiwan_green')
    a.hand = [Card(f'手{i}', 'command', {}) for i in range(3)]
    g._end_turn()  # 沒建立組織
    checks = {'exactly_five': len(a.hand) == 5}
    return {'name': 'no_inner_build_no_extra_draw', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_keep_hand_top_up(),
        case_five_or_more_no_draw(),
        case_local_society_extra_draw(),
        case_no_build_no_extra(),
    ]
    summary = {
        'scope': ['回合結束補牌', '本土社團'],
        'purpose': (
            'P1 playtest items 11+12: _end_turn used to run faction end-turn draws FIRST, '
            'then discard the whole hand and draw a fresh 5 — wiping both kept cards and the '
            '本土社團 bonus draw. Per the reported rule, end-of-turn refill keeps the hand and '
            'only tops up to 5 (no draw at 5+), and end-turn ability draws (本土社團/還我河山/'
            '民國之心) now happen AFTER the refill so the bonus card survives (hand can reach 6).'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'END_TURN_HAND_REFILL_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'END_TURN_HAND_REFILL_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 回合結束補牌（保留手牌補到5）＋本土社團額外抽驗證\n\n'
        '可重跑指令：`python3 scripts/validate_end_turn_hand_refill.py`\n\n'
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
