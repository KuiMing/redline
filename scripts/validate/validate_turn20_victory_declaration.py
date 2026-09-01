import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
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


def case_mid_round_player_win_deferred_to_round_wrap():
    # P1（宣布勝利時機應等整輪含紅軍行動完才公布）：非本輪最後一位玩家在自己回合
    # 結束時達成勝利條件，不應立即宣告——必須等整輪（含紅軍）都行動完、繞回起點的
    # round-wrap 邊界才判定。此案例先驗證非 wrap 回合不宣告，再驗證條件在紅軍行動後
    # 仍成立時、於整輪 wrap 邊界才正確宣告。
    g, a, b = _new_game(10)
    inner = sorted(g.towns_by_ruler.get('紅軍', []))
    a.organizations = {t: 1 for t in inner[:14]}  # 自由派 牆內14 → 條件達成
    g.current_player_index = 0  # 非本輪最後一位：結束後只前進到 index 1，不 wrap
    g._end_turn()
    mid_round_not_declared = g.winner is None and g.game_phase != GamePhase.FINISHED
    # 紅軍（本輪最後一位，index 1）行動完後 current_player_index 繞回 round_start(0)
    # 觸發整輪 wrap，條件在紅軍行動後仍成立 → 此刻才宣告 A 勝利。
    g._end_turn()
    checks = {
        'not_declared_on_own_mid_round_turn': mid_round_not_declared,
        'declared_at_round_wrap_after_red_army_acted': g.winner == 'A' and g.game_phase == GamePhase.FINISHED,
        'round_wrapped': g.current_player_index == g.round_start_player_index,
    }
    return {'name': 'mid_round_player_victory_deferred_to_round_wrap', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_declared_at_round20_rollover(),
        case_no_premature_declaration_at_19(),
        case_mid_round_player_win_deferred_to_round_wrap(),
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
            'remains a P1 UI item. P1 (宣布勝利時機應等整輪含紅軍行動完才公布): victory is now '
            'judged ONLY at the round-wrap boundary — a non-red player meeting a condition on '
            'its own mid-round turn is no longer declared immediately; it is declared at the '
            'wrap once every player incl. Red Army has acted and the condition still holds.'
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
        '可重跑指令：`python3 scripts/validate/validate_turn20_victory_declaration.py`\n\n'
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
