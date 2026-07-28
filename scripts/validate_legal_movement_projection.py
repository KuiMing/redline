import json
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'map-ui'
OUT_JSON = RECORD_DIR / 'LEGAL_MOVEMENT_PROJECTION_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LEGAL_MOVEMENT_PROJECTION_VALIDATION.md'
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game, GamePhase, TurnPhase


def make_game():
    game = Game([('p1', 'mover'), ('p2', 'other')])
    mover, other = game.players
    mover.name = 'mover'
    mover.faction_id = 'taiwan_green'
    mover.base = '臺北'
    mover.organizations = {'臺北': 1, '新北': 1}
    mover.moves_left = 2
    other.name = 'other'
    other.faction_id = 'red_army'
    other.base = '北京'
    other.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.action_log = []
    return game, mover, other


def snapshot(game):
    return {
        'players': [
            {
                'id': player.id,
                'orgs': dict(player.organizations),
                'moves_left': player.moves_left,
                'base': player.base,
            }
            for player in game.players
        ],
        'action_log': deepcopy(game.action_log),
        'turn_phase': game.turn_phase,
    }


def destinations(projection, origin):
    modes = projection.get(origin, {})
    return {
        mode: {entry['town']: entry['cost'] for entry in modes.get(mode, [])}
        for mode in ('road', 'rail')
    }


def run_checks():
    checks = []

    game, mover, other = make_game()
    before = snapshot(game)
    own_state = game.state(mover.id)
    after = snapshot(game)
    projected = own_state['map']['legal_organization_moves']
    new_taipei = destinations(projected, '新北')
    checks.append({
        'name': 'current_player_receives_backend_legal_moves_without_mutation',
        'ok': before == after and '新北' in projected and '苗栗' in new_taipei['rail'],
        'detail': {'new_taipei': new_taipei, 'state_unchanged': before == after},
    })

    checks.append({
        'name': 'other_viewer_receives_no_actionable_projection',
        'ok': game.state(other.id)['map']['legal_organization_moves'] == {},
        'detail': game.state(other.id)['map']['legal_organization_moves'],
    })

    checks.append({
        'name': 'base_anchor_is_not_a_movable_origin',
        'ok': '臺北' not in projected,
        'detail': {'origins': sorted(projected)},
    })

    all_projected = [
        (origin, entry['town'], mode, entry['cost'])
        for origin, modes in projected.items()
        for mode in ('road', 'rail')
        for entry in modes.get(mode, [])
    ]
    consistency = []
    for origin, destination, mode, cost in all_projected:
        result = game._validate_organization_move(origin, destination, mode)
        consistency.append(result.get('success') is True and result.get('cost') == cost)
    checks.append({
        'name': 'every_projected_move_matches_the_shared_validator_and_cost',
        'ok': bool(all_projected) and all(consistency),
        'detail': {'projected_count': len(all_projected), 'all_consistent': all(consistency)},
    })

    actual_projection = set(all_projected)
    expected_projection = set()
    for origin in game._organization_towns_for_player(mover):
        for destination in game.map['towns']:
            for mode in ('road', 'rail'):
                result = game._validate_organization_move(origin, destination, mode)
                if result.get('success') is True:
                    expected_projection.add((origin, destination, mode, result['cost']))
    checks.append({
        'name': 'projection_is_exactly_bidirectionally_equivalent_to_shared_validator',
        'ok': actual_projection == expected_projection,
        'detail': {
            'actual_count': len(actual_projection),
            'expected_count': len(expected_projection),
            'missing': sorted(expected_projection - actual_projection),
            'extra': sorted(actual_projection - expected_projection),
        },
    })

    game, mover, other = make_game()
    mover.moves_left = 0
    checks.append({
        'name': 'zero_move_points_projects_no_destinations',
        'ok': game.state(mover.id)['map']['legal_organization_moves'] == {},
        'detail': game.state(mover.id)['map']['legal_organization_moves'],
    })

    game, mover, other = make_game()
    other.organizations = {'苗栗': 1, '北京': 1}
    projected = game.state(mover.id)['map']['legal_organization_moves']
    options = destinations(projected, '新北')
    checks.append({
        'name': 'occupied_destination_is_absent_from_projection',
        'ok': '苗栗' not in options['rail'] and '苗栗' not in options['road'],
        'detail': options,
    })

    game, mover, other = make_game()
    projected = game.state(mover.id)['map']['legal_organization_moves']
    options = destinations(projected, '新北')
    checks.append({
        'name': 'faction_inapplicable_destination_is_absent_from_projection',
        'ok': '觀塘' not in options['road'] and '觀塘' not in options['rail'],
        'detail': options,
    })

    return checks


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks = run_checks()
    summary = {
        'total': len(checks),
        'passed': sum(1 for check in checks if check['ok']),
        'failed': sum(1 for check in checks if not check['ok']),
    }
    payload = {'date': date.today().isoformat(), 'summary': summary, 'checks': checks}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# LEGAL MOVEMENT PROJECTION VALIDATION', '', f"日期：{payload['date']}", '', f"結果：{summary['passed']}/{summary['total']} PASS", '']
    for check in checks:
        lines.extend([f"## {'PASS' if check['ok'] else 'FAIL'} — {check['name']}", '', f"- detail: `{json.dumps(check['detail'], ensure_ascii=False)}`", ''])
    OUT_MD.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    print(json.dumps({'summary': summary, 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    raise SystemExit(1 if summary['failed'] else 0)


if __name__ == '__main__':
    main()
