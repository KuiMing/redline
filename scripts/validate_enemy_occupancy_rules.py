import json
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RECORD_DIR = BASE / 'docs' / 'records' / 'map-ui'
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, GamePhase, TurnPhase

OUT_JSON = RECORD_DIR / 'ENEMY_OCCUPANCY_RULES_VALIDATION.json'
OUT_MD = RECORD_DIR / 'ENEMY_OCCUPANCY_RULES_VALIDATION.md'


def make_game():
    game = Game([('p1', 'f'), ('p2', '紅軍')], market_mode='all_cards')
    player = game.players[0]
    red = game.players[1]
    player.name = 'f'
    player.faction_id = 'taiwan_green'
    player.base = '臺北'
    player.organizations = {'桃園': 1}
    player.moves_left = 1
    red.name = '紅軍'
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'新竹': 1}
    game.pending_base_choices = {}
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    return game, player, red


def snapshot(player, red):
    return {
        'player_orgs': dict(player.organizations),
        'red_orgs': dict(red.organizations),
        'moves_left': player.moves_left,
    }


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def run_checks():
    checks = []

    game, player, red = make_game()
    before = snapshot(player, red)
    result = game.move_organization('桃園', '新竹', 'rail')
    after = snapshot(player, red)
    checks.append(check(
        'cannot_move_into_enemy_occupied_destination',
        bool(result.get('error'))
        and result.get('error') == 'Cannot move into occupied town'
        and before == after,
        {'result': result, 'before': before, 'after': after, 'rule': '敵方組織所在城鎮不可移入。'},
    ))

    game, player, red = make_game()
    choices = game._card_build_town_choices(player, {'type': 'build', 'range': 1})
    towns = {entry['town'] for entry in choices}
    checks.append(check(
        'propagandist_build_choices_exclude_enemy_occupied_but_include_vacated_new_taipei',
        '新竹' not in towns and '新北' in towns,
        {
            'choices_sample': sorted(towns & {'新北', '新竹', '桃園'}),
            'red_orgs': dict(red.organizations),
            'rule': '宣傳家 range 1：新竹有紅軍組織不可建立；新北目前無紅軍組織且在桃園 1 格內，可建立。',
        },
    ))

    game, player, red = make_game()
    before = snapshot(player, red)
    result = game.build_organization_with_support('桃園', '新竹')
    after = snapshot(player, red)
    checks.append(check(
        'support_build_rejects_enemy_occupied_town',
        bool(result.get('error')) and before == after,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player, red = make_game()
    before = snapshot(player, red)
    result = game.build_organization_with_support('桃園', '新北')
    after = snapshot(player, red)
    checks.append(check(
        'support_build_allows_vacated_new_taipei',
        result.get('success') is True
        and after['player_orgs'].get('新北') == 1
        and after['red_orgs'].get('新北', 0) == 0,
        {'result': result, 'before': before, 'after': after},
    ))

    game, player, red = make_game()
    player.organizations = {'新北': 1}
    red.organizations = {'新竹': 1}
    before = snapshot(player, red)
    result = game.build_organization('新北')
    after = snapshot(player, red)
    checks.append(check(
        'direct_build_rejects_second_piece_after_red_moved_out',
        bool(result.get('error'))
        and after == before
        and after['player_orgs'].get('新北') == 1
        and after['red_orgs'].get('新北', 0) == 0,
        {'result': result, 'before': before, 'after': after},
    ))

    return checks


def write_outputs(checks):
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    out = {'date': date.today().isoformat(), 'summary': summary, 'checks': checks}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# ENEMY OCCUPANCY RULES VALIDATION', '', f"日期：{out['date']}", '', f"summary: {summary}", '']
    for item in checks:
        status = 'PASS' if item['passed'] else 'FAIL'
        lines.append(f"## {item['name']} — {status}")
        for k, v in item['details'].items():
            lines.append(f"- {k}: {v}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return out


def main():
    checks = run_checks()
    out = write_outputs(checks)
    print(json.dumps({'summary': out['summary'], 'json': str(OUT_JSON), 'md': str(OUT_MD)}, ensure_ascii=False))
    if out['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
