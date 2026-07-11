import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game


def _inner_towns(g, n):
    towns = sorted(g.towns_by_ruler.get('紅軍', []))
    return towns[:n]


def _new_game():
    g = Game([('p1', 'W'), ('p2', 'C'), ('p3', 'R')])
    w, c, r = g.players
    w.faction_id = 'tibet_dehradun'   # count_only 牆內 14
    c.faction_id = 'tibet_chogu'      # count_only 牆內 14
    r.faction_id = 'red_army'
    for p in g.players:
        p.organizations = {}
    g.winner = None
    g.co_winners = []
    return g, w, c, r


def _give_inner_orgs(g, player, n):
    player.organizations = {t: 1 for t in _inner_towns(g, n)}


def case_co_winner_at_two_thirds():
    g, w, c, r = _new_game()
    _give_inner_orgs(g, w, 14)   # 達成勝利
    _give_inner_orgs(g, c, 10)   # 10/14 ≈ 0.714 >= 2/3 → 共同勝利
    g._check_victory()
    checks = {
        'winner_is_W': g.winner == 'W',
        'C_is_co_winner': g.co_winners == ['C'],
        'state_exposes_co_winners': g.state().get('co_winners') == ['C'],
    }
    return {'name': 'co_winner_at_or_above_two_thirds', 'co': g.co_winners, 'checks': checks, 'ok': all(checks.values())}


def case_below_two_thirds_not_co_winner():
    g, w, c, r = _new_game()
    _give_inner_orgs(g, w, 14)
    _give_inner_orgs(g, c, 9)    # 9/14 ≈ 0.643 < 2/3
    g._check_victory()
    checks = {
        'winner_is_W': g.winner == 'W',
        'C_not_co_winner': g.co_winners == [],
    }
    return {'name': 'below_two_thirds_not_co_winner', 'checks': checks, 'ok': all(checks.values())}


def case_red_army_victory_has_no_co_winners():
    g, w, c, r = _new_game()
    _give_inner_orgs(g, c, 13)   # 高進度也不算
    g.turn = 21                  # 第20回合後紅軍保底獲勝
    g._check_victory()
    checks = {
        'red_wins': g.winner == 'red_army',
        'no_co_winners_on_red_victory': g.co_winners == [],
    }
    return {'name': 'red_army_victory_no_co_winners', 'checks': checks, 'ok': all(checks.values())}


def case_red_army_never_co_winner():
    g, w, c, r = _new_game()
    _give_inner_orgs(g, w, 14)
    _give_inner_orgs(g, r, 20)   # 紅軍組織再多也不是共同勝利者（且紅軍無 count 條件）
    g._check_victory()
    checks = {
        'winner_is_W': g.winner == 'W',
        'red_not_co_winner': 'R' not in (g.co_winners or []),
    }
    return {'name': 'red_army_never_co_winner', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_co_winner_at_two_thirds(),
        case_below_two_thirds_not_co_winner(),
        case_red_army_victory_has_no_co_winners(),
        case_red_army_never_co_winner(),
    ]
    summary = {
        'scope': ['A4 共同勝利'],
        'purpose': (
            'A4 per 2026-07-11 user ruling: when an anti-communist player wins, every OTHER '
            'anti-communist player whose progress toward their own faction\'s win condition '
            'is >= 2/3 (inclusive) is a co-winner. Red Army victories grant no co-winners, '
            'and Red Army is never a co-winner. Progress = achieved count / required count '
            '(max across a faction\'s conditions); the old dead formula "2/3 of the number '
            'of conditions" was replaced by any-one-condition-wins. Currently effective for '
            'the 15 structured-condition factions; the 46 text-only factions gain coverage '
            'when A1 lands.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'CO_WINNERS_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'CO_WINNERS_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 共同勝利（2/3 進度）驗證（A4）\n\n'
        '可重跑指令：`python3 scripts/validate_co_winners.py`\n\n'
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
