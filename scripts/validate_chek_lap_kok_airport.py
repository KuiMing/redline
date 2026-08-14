import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase

AIRPORT = '赤臘角'  # 地圖對「赤鱲角」的拼寫


def _new_game(faction_id='hong_kong', moves=2):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = 'red_army'
    a.organizations = {}
    b.organizations = {}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    a.moves_left = moves
    return g, a, b


def case_airport_move_costs_two():
    g, a, b = _new_game(moves=2)
    a.organizations = {AIRPORT: 1, '香港城': 1}
    result = g.move_organization(AIRPORT, '倫敦', mode='road')
    checks = {
        'move_succeeds': result.get('success') is True,
        'org_arrived_london': a.organizations.get('倫敦', 0) == 1,
        'cost_two_moves': a.moves_left == 0,
    }
    return {'name': 'airport_move_to_outer_dev_space_costs_two', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_insufficient_moves_blocked():
    g, a, b = _new_game(moves=1)
    a.organizations = {AIRPORT: 1, '香港城': 1}
    result = g.move_organization(AIRPORT, '倫敦', mode='road')
    checks = {'blocked_with_one_move': result.get('error') == 'Not enough move points'}
    return {'name': 'insufficient_moves_blocked', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_reverse_not_allowed():
    g, a, b = _new_game(moves=2)
    a.organizations = {'倫敦': 1, '香港城': 1}
    result = g.move_organization('倫敦', AIRPORT, mode='road')
    checks = {'reverse_blocked': 'No road connection' in str(result.get('error'))}
    return {'name': 'reverse_direction_not_allowed', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_non_hong_kong_faction_blocked():
    g, a, b = _new_game(faction_id='yue', moves=2)  # 粵可與香港共用組織，但機場規則僅屬香港
    a.organizations = {AIRPORT: 1, '廣州': 1}
    result = g.move_organization(AIRPORT, '倫敦', mode='road')
    checks = {'non_hk_blocked': 'No road connection' in str(result.get('error'))}
    return {'name': 'non_hong_kong_faction_blocked', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_outside_dev_space_blocked():
    g, a, b = _new_game(moves=2)
    a.organizations = {AIRPORT: 1, '香港城': 1}
    result = g.move_organization(AIRPORT, '曼谷', mode='road')  # 香港發展空間不含曼谷
    checks = {'outside_dev_space_blocked': 'No road connection' in str(result.get('error'))}
    return {'name': 'outside_hk_dev_space_blocked', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_normal_adjacent_move_still_costs_one():
    g, a, b = _new_game(moves=2)
    a.organizations = {AIRPORT: 1, '香港城': 1}
    result = g.move_organization(AIRPORT, '澳門', mode='road')  # 赤臘角原有道路連線
    checks = {
        'adjacent_move_ok': result.get('success') is True,
        'cost_one': a.moves_left == 1,
    }
    return {'name': 'normal_adjacent_move_costs_one', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_enemy_occupied_destination_blocked():
    g, a, b = _new_game(moves=2)
    a.organizations = {AIRPORT: 1, '香港城': 1}
    b.organizations = {'倫敦': 1}
    result = g.move_organization(AIRPORT, '倫敦', mode='road')
    checks = {'enemy_destination_blocked': 'Cannot move into occupied town' in str(result.get('error'))}
    return {'name': 'enemy_occupied_destination_blocked', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_airport_move_costs_two(),
        case_insufficient_moves_blocked(),
        case_reverse_not_allowed(),
        case_non_hong_kong_faction_blocked(),
        case_outside_dev_space_blocked(),
        case_normal_adjacent_move_still_costs_one(),
        case_enemy_occupied_destination_blocked(),
    ]
    summary = {
        'scope': ['赤鱲角機場（S5-2）'],
        'purpose': (
            'S5-2 per 2026-07-11 user ruling: Hong Kong may spend 2 migrations to move a Hong '
            'Kong organization located at 赤鱲角 (map spelling: 赤臘角) ignore-distance to any '
            'outer-wall town within Hong Kong\'s development space; the reverse direction is '
            'not allowed. Only the hong_kong faction moving its own organization qualifies; '
            'normal adjacent moves from the airport still cost 1; enemy-occupied destinations '
            'remain blocked. Frontend movement highlighting for airport routes is deferred to '
            'the P1 movement-UI batch.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'CHEK_LAP_KOK_AIRPORT_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'CHEK_LAP_KOK_AIRPORT_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 赤鱲角機場規則驗證（S5-2）\n\n'
        '可重跑指令：`python3 scripts/validate_chek_lap_kok_airport.py`\n\n'
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
