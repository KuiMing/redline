import json
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = BASE / 'docs' / 'records' / 'map-ui'
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, GamePhase, TurnPhase

OUT_JSON = RECORD_DIR / 'MOVEMENT_RULES_VALIDATION.json'
OUT_MD = RECORD_DIR / 'MOVEMENT_RULES_VALIDATION.md'


def make_game():
    game = Game([('p1', 'mover'), ('p2', 'other')])
    player = game.players[0]
    other = game.players[1]
    player.name = 'mover'
    player.faction_id = 'hong_kong'
    player.base = '香港城'
    player.organizations = {'香港城': 1}
    other.name = 'other'
    other.faction_id = 'red_army'
    other.base = '北京'
    other.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    player.moves_left = 0
    return game, player


def snapshot(player):
    return {
        'orgs': dict(player.organizations),
        'moves_left': player.moves_left,
        'base': player.base,
    }


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def run_checks():
    checks = []

    game, player = make_game()
    player.moves_left = 3
    game.turn_phase = TurnPhase.EVENT
    before = snapshot(player)
    result = game.move_organization('香港城', '澳門', 'road')
    after = snapshot(player)
    checks.append(check(
        'movement_rejected_outside_action_phase',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player = make_game()
    player.organizations = {'澳門': 1}
    player.base = '香港城'
    before = snapshot(player)
    result = game.move_organization('澳門', '香港城', 'road')
    after = snapshot(player)
    checks.append(check(
        'initial_zero_move_points_cannot_move',
        bool(result.get('error'))
        and result.get('error') == 'Not enough move points'
        and before == after,
        {'result': result, 'before': before, 'after': after, 'rule': '一開始沒有移動點；必須靠卡牌或效果取得移動點後才能移動。'},
    ))

    game, player = make_game()
    player.organizations = {'澳門': 1}
    player.base = '香港城'
    player.moves_left = 1
    before = snapshot(player)
    result = game.move_organization('澳門', '香港城', 'road')
    after = snapshot(player)
    checks.append(check(
        'road_adjacent_move_costs_one_and_moves_org',
        result.get('success') is True
        and after['orgs'].get('澳門', 0) == 0
        and after['orgs'].get('香港城') == 1
        and after['moves_left'] == before['moves_left'] - 1,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player = make_game()
    player.faction_id = 'liberals'  # 2026-07-12 目的城鎮陣營適用規則後：天津不適用香港，改用適用的陣營
    player.organizations = {'北京': 1}
    player.base = '香港城'
    player.moves_left = 1
    before = snapshot(player)
    result = game.move_organization('北京', '天津', 'rail')
    after = snapshot(player)
    checks.append(check(
        'rail_adjacent_move_costs_one_move_count_and_moves_org',
        result.get('success') is True
        and after['orgs'].get('北京', 0) == 0
        and after['orgs'].get('天津') == 1
        and after['moves_left'] == 0,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player = make_game()
    player.faction_id = 'taiwan_green'  # 2026-07-12 臺灣城鎮僅臺灣陣營適用
    player.organizations = {'新北': 1}
    player.base = '香港城'
    player.moves_left = 1
    before = snapshot(player)
    result = game.move_organization('新北', '苗栗', 'rail')
    after = snapshot(player)
    checks.append(check(
        'rail_three_step_move_costs_one_move_count_and_moves_org',
        result.get('success') is True
        and after['orgs'].get('新北', 0) == 0
        and after['orgs'].get('苗栗') == 1
        and after['moves_left'] == 0,
        {'result': result, 'before': before, 'after': after, 'rule': 'rules.md：鐵路一次最多 3 格；新北→桃園→新竹→苗栗 consumes 1 move count.'},
    ))

    game, player = make_game()
    player.organizations = {'新北': 1}
    player.base = '香港城'
    player.moves_left = 1
    before = snapshot(player)
    result = game.move_organization('新北', '彰化', 'rail')
    after = snapshot(player)
    checks.append(check(
        'rail_four_step_move_rejected_without_spending_points',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after, 'rule': '新北→彰化 requires 4 rail edges, exceeding the 3-step rail limit.'},
    ))

    game, player = make_game()
    other = game.players[1]
    player.organizations = {'新北': 1}
    other.organizations = {'新竹': 1}
    player.base = '香港城'
    player.moves_left = 1
    before = snapshot(player)
    result = game.move_organization('新北', '苗栗', 'rail')
    after = snapshot(player)
    checks.append(check(
        'rail_three_step_cannot_pass_enemy_organization',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after, 'enemy_org': dict(other.organizations), 'rule': '可跨越己方組織，但不可跨越敵方。'},
    ))

    game, player = make_game()
    player.organizations = {'北京': 1}
    player.base = '香港城'
    player.moves_left = 0
    before = snapshot(player)
    result = game.move_organization('北京', '天津', 'rail')
    after = snapshot(player)
    checks.append(check(
        'rail_move_rejected_when_no_move_count_left',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player = make_game()
    player.organizations = {'香港城': 2}
    player.moves_left = 3
    before = snapshot(player)
    result = game.move_organization('香港城', '天津', 'road')
    after = snapshot(player)
    checks.append(check(
        'non_adjacent_move_rejected_without_spending_points',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player = make_game()
    player.organizations = {'香港城': 2}
    player.moves_left = 3
    before = snapshot(player)
    result = game.move_organization('香港城', '澳門', 'air')
    after = snapshot(player)
    checks.append(check(
        'invalid_move_mode_rejected_without_state_change',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player = make_game()
    player.moves_left = 3
    before = snapshot(player)
    result = game.move_organization('不存在', '澳門', 'road')
    after = snapshot(player)
    checks.append(check(
        'invalid_origin_rejected_without_state_change',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player = make_game()
    player.organizations = {'香港城': 1}
    player.moves_left = 3
    before = snapshot(player)
    result = game.move_organization('香港城', '澳門', 'road')
    after = snapshot(player)
    checks.append(check(
        'base_anchor_organization_cannot_leave_base',
        bool(result.get('error'))
        and before == after
        and after['orgs'].get('香港城') == 1,
        {
            'rule': 'RULES.md: 根據地的組織棋在遊戲過程中不得離開根據地底座。',
            'result': result,
            'before': before,
            'after': after,
        },
    ))

    game, player = make_game()
    player.organizations = {'香港城': 2}
    player.moves_left = 3
    before = snapshot(player)
    result = game.move_organization('香港城', '澳門', 'road')
    after = snapshot(player)
    checks.append(check(
        'extra_organization_on_base_can_move_but_anchor_remains',
        result.get('success') is True
        and after['orgs'].get('香港城') == 1
        and after['orgs'].get('澳門') == 1
        and after['moves_left'] == before['moves_left'] - 1,
        {
            'rule': '只有根據地底座上的保底組織不可離開；同城額外組織仍可正常遷移。',
            'result': result,
            'before': before,
            'after': after,
        },
    ))

    return checks


def write_outputs(checks):
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    out = {'date': date.today().isoformat(), 'summary': summary, 'checks': checks}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = ['# MOVEMENT RULES VALIDATION', '', f"日期：{out['date']}", '', f"summary: {summary}", '']
    for item in checks:
        status = 'PASS' if item['passed'] else 'FAIL'
        lines.append(f"## {item['name']} — {status}")
        for k, v in item['details'].items():
            lines.append(f"- {k}: {v}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return out


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    out = write_outputs(run_checks())
    print(json.dumps({'summary': out['summary'], 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    if out['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
