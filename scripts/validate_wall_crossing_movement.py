import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'map-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def _new_game(faction_id, orgs, moves):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = 'red_army'
    a.organizations = dict(orgs)
    b.organizations = {}
    a.moves_left = moves
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    return g, a, b


def case_reported_dongsha_kwuntong():
    # playtest 回報案例：臺灣綠線 東沙→觀塘 只花1次移動——觀塘不適用臺灣陣營，應直接擋下
    g, a, b = _new_game('taiwan_green', {'東沙': 1}, 2)
    result = g.move_organization('東沙', '觀塘', mode='road')
    checks = {'taiwan_green_blocked_by_faction_applicability': '不適用你的陣營' in str(result.get('error'))}
    return {'name': 'reported_case_dongsha_to_kwuntong_blocked', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_crossing_costs_two():
    # 香港適用觀塘與東沙：跨牆（牆外東沙→牆內觀塘）需2次移動、1次不夠
    g, a, b = _new_game('hong_kong', {'東沙': 1, '香港城': 1}, 1)
    blocked = g.move_organization('東沙', '觀塘', mode='road')
    g2, a2, b2 = _new_game('hong_kong', {'東沙': 1, '香港城': 1}, 2)
    ok = g2.move_organization('東沙', '觀塘', mode='road')
    checks = {
        'one_move_not_enough': 'Not enough move points' in str(blocked.get('error')),
        'two_moves_succeed': ok.get('success') is True,
        'cost_two_consumed': a2.moves_left == 0,
    }
    return {'name': 'wall_crossing_costs_two_moves', 'checks': checks, 'ok': all(checks.values())}


def case_reverse_crossing_also_two():
    g, a, b = _new_game('hong_kong', {'觀塘': 1, '香港城': 1}, 2)
    ok = g.move_organization('觀塘', '東沙', mode='road')
    checks = {'inner_to_outer_also_two': ok.get('success') is True and a.moves_left == 0}
    return {'name': 'reverse_crossing_inner_to_outer_costs_two', 'checks': checks, 'ok': all(checks.values())}


def case_rail_three_cannot_cross():
    # 翻牆僅能移動1格：多步鐵路不得跨牆——平壤(牆外) 經丹東可達的牆內兩步城鎮應不可直達
    g, a, b = _new_game('chaoxian', {'平壤': 1}, 2)
    helper_blocked = g._rail_reachable_within_three(a, '平壤', '瀋陽') is False
    move_blocked = g.move_organization('平壤', '瀋陽', mode='rail')
    checks = {
        'bfs_does_not_cross_wall': helper_blocked,
        'two_step_crossing_move_rejected': 'No rail connection' in str(move_blocked.get('error')),
    }
    return {'name': 'rail_multi_step_cannot_cross_wall', 'checks': checks, 'ok': all(checks.values())}


def case_direct_rail_crossing_allowed_at_two():
    # 直接相鄰的跨牆鐵路（平壤—丹東）仍可走，花2次
    g, a, b = _new_game('chaoxian', {'平壤': 1}, 2)
    applicable = g.can_faction_develop_in_town('chaoxian', '丹東')
    result = g.move_organization('平壤', '丹東', mode='rail')
    checks = (
        {'adjacent_rail_crossing_costs_two': result.get('success') is True and a.moves_left == 0}
        if applicable else
        {'destination_not_applicable_blocked': '不適用你的陣營' in str(result.get('error'))}
    )
    return {'name': 'direct_rail_crossing', 'applicable': applicable, 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_same_side_moves_still_one():
    g, a, b = _new_game('taiwan_green', {'新北': 1}, 1)
    ok = g.move_organization('新北', '苗栗', mode='rail')  # 同側 3 步鐵路
    checks = {'same_side_rail3_costs_one': ok.get('success') is True and a.moves_left == 0}
    return {'name': 'same_side_rail_three_still_costs_one', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_reported_dongsha_kwuntong(),
        case_crossing_costs_two(),
        case_reverse_crossing_also_two(),
        case_rail_three_cannot_cross(),
        case_direct_rail_crossing_allowed_at_two(),
        case_same_side_moves_still_one(),
    ]
    summary = {
        'scope': ['翻牆移動成本', '目的城鎮陣營適用'],
        'purpose': (
            'P1 playtest item (東沙→觀塘 case): move_organization charged a flat cost of 1 '
            'and never checked destination faction applicability. Per rules.md 組織遷移: '
            'wall-crossing (牆內↔牆外) costs 2 movement points and may only move 1 step '
            '(multi-step rail-3 paths can no longer traverse the wall — the BFS is '
            'same-side-only), and the destination town must be within the moving faction\'s '
            'development space (taiwan_green cannot enter 觀塘 at all). Same-side moves and '
            'the Chek Lap Kok airport path (already 2 moves) are unaffected.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'WALL_CROSSING_MOVEMENT_VALIDATION_20260712.json'
    md_path = RECORD_DIR / 'WALL_CROSSING_MOVEMENT_VALIDATION_20260712.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 翻牆移動成本＋目的城鎮陣營適用驗證\n\n'
        '可重跑指令：`python3 scripts/validate_wall_crossing_movement.py`\n\n'
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
