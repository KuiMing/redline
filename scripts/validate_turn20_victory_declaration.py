import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, GamePhase, TurnPhase


def _new_game(turn):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = 'liberals'
    b.faction_id = 'red_army'
    for p in g.players:
        p.organizations = {}
        p.hand = []
        p.deck.draw_pile = []
    g.game_phase = GamePhase.MAIN
    g.turn_phase = TurnPhase.END
    g.turn = turn
    g.round_start_player_index = 0
    g.current_player_index = 1  # 本輪最後一位玩家
    g.turn_log = g._new_turn_log()
    g.winner = None
    g.co_winners = []
    return g, a, b


def case_declared_at_round20_rollover():
    g, a, b = _new_game(20)
    deck_before = len(g.event_deck.draw_pile)
    g._end_turn()
    checks = {
        'red_army_declared_immediately': g.winner == 'red_army' and g.game_phase == GamePhase.FINISHED,
        'turn_advanced_to_21': g.turn == 21,
        'no_round_21_event_drawn': len(g.event_deck.draw_pile) == deck_before,
    }
    return {'name': 'red_survival_declared_at_round20_rollover', 'checks': checks, 'ok': all(checks.values())}


def case_no_premature_declaration_at_19():
    g, a, b = _new_game(19)
    g._end_turn()
    checks = {
        'not_finished_at_20_start': g.game_phase != GamePhase.FINISHED and g.winner is None,
        'turn_is_20': g.turn == 20,
        'round_20_event_drawn': g.current_event is not None,
    }
    return {'name': 'no_premature_declaration_entering_round_20', 'checks': checks, 'ok': all(checks.values())}


def case_mid_round_player_win_unaffected():
    g, a, b = _new_game(10)
    inner = sorted(g.towns_by_ruler.get('紅軍', []))
    a.organizations = {t: 1 for t in inner[:14]}  # 自由派 牆內14 → 勝
    g.current_player_index = 0  # 非本輪最後一位
    g._end_turn()
    checks = {'anti_communist_win_still_declared_mid_round': g.winner == 'A' and g.game_phase == GamePhase.FINISHED}
    return {'name': 'mid_round_player_victory_unaffected', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_declared_at_round20_rollover(),
        case_no_premature_declaration_at_19(),
        case_mid_round_player_win_unaffected(),
    ]
    summary = {
        'scope': ['第20回合勝利宣告時機'],
        'purpose': (
            'P1 playtest item: the red-army turn-20 survival victory (turn > 20) was only '
            'checked at the START of _end_turn, so when round 20 completed and the turn '
            'counter rolled to 21, no declaration fired — the game silently drew a round-21 '
            'event and only declared after the next player ended their turn. _end_turn now '
            'runs _check_victory immediately after the round rollover increments the turn, '
            'declaring the winner (and A4 co-winners via the same path) at the exact moment '
            'round 20 completes, without drawing a round-21 event. Victory-screen display '
            'remains a P1 UI item.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'TURN20_VICTORY_DECLARATION_VALIDATION_20260712.json'
    md_path = RECORD_DIR / 'TURN20_VICTORY_DECLARATION_VALIDATION_20260712.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 第20回合勝利宣告時機驗證\n\n'
        '可重跑指令：`python3 scripts/validate_turn20_victory_declaration.py`\n\n'
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
