import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game, GamePhase

OUT_JSON = ROOT / 'VICTORY_RULES_VALIDATION.json'
OUT_MD = ROOT / 'VICTORY_RULES_VALIDATION.md'


def china_towns(game, count=14):
    return list(game.board_regions.get('china', {}).get('towns', []))[:count]


def taiwan_towns(game, count=14):
    return list(game.board_regions.get('taiwan', {}).get('towns', []))[:count]


def resolve_base_selection(game):
    if game.game_phase == GamePhase.BASE_SELECTION:
        for pid, choice_data in list(game.pending_base_choices.items()):
            labels = choice_data.get('labels', [])
            resolved = choice_data.get('resolved', {})
            for label in labels:
                for town in resolved.get(label, []):
                    result = game.set_base_choice(pid, town, label=label)
                    if result.get('success'):
                        break
                if pid not in game.pending_base_choices:
                    break
    return game


def make_game():
    return resolve_base_selection(Game([('p1', 'anti'), ('p2', 'red')]))


def evaluate(game):
    game._check_victory()
    return game.game_phase, game.winner


def ok(name, passed, detail):
    return {'name': name, 'ok': bool(passed), 'detail': detail}


def test_red_survival_after_turn_20():
    g = make_game()
    anti, red = g.players
    anti.faction_id = 'hong_kong'
    red.faction_id = 'red_army'
    anti.organizations = {'香港城': 1}
    red.organizations = {'北京': 1}
    g.turn = 21
    phase, winner = evaluate(g)
    return ok(
        'red_survival_after_turn_20',
        phase == GamePhase.FINISHED and winner == 'red_army',
        {'phase': phase, 'winner': winner, 'turn': g.turn},
    )


def test_red_taiwan_14_orgs_early_win():
    g = make_game()
    anti, red = g.players
    anti.faction_id = 'taiwan_green'
    red.faction_id = 'red_army'
    red.organizations = {town: 1 for town in taiwan_towns(g, 14)}
    phase, winner = evaluate(g)
    return ok(
        'red_taiwan_14_orgs_early_win',
        phase == GamePhase.FINISHED and winner == 'red_army',
        {'phase': phase, 'winner': winner, 'red_orgs': red.organizations},
    )


def test_non_red_china_14_orgs_win():
    g = make_game()
    anti, red = g.players
    anti.name = 'anti'
    anti.faction_id = 'hong_kong'
    red.faction_id = 'red_army'
    anti.organizations = {town: 1 for town in china_towns(g, 14)}
    red.organizations = {'北京': 1}
    phase, winner = evaluate(g)
    return ok(
        'non_red_china_14_orgs_win',
        phase == GamePhase.FINISHED and winner == anti.name,
        {'phase': phase, 'winner': winner, 'anti_org_count': sum(anti.organizations.values())},
    )


def test_shared_orgs_count_for_non_red_victory():
    g = resolve_base_selection(Game([('tw', 'Taiwan'), ('hu', 'Hu'), ('red', 'Red')]))
    tw, hu, red = g.players
    tw.faction_id = 'taiwan_green'
    hu.faction_id = 'hu'
    red.faction_id = 'red_army'
    tw.name = 'Taiwan'
    hu.name = 'Hu'
    towns = china_towns(g, 14)
    tw.organizations = {town: 1 for town in towns[:8]}
    hu.organizations = {town: 1 for town in towns[8:14]}
    red.organizations = {'北京': 1}
    count = g.victory_engine._count_scope(tw, '牆內', g)
    phase, winner = evaluate(g)
    return ok(
        'shared_orgs_count_for_non_red_victory',
        count >= 14 and phase == GamePhase.FINISHED and winner == tw.name,
        {'shared_count': count, 'phase': phase, 'winner': winner, 'tw_orgs': tw.organizations, 'hu_orgs': hu.organizations},
    )


def test_no_win_when_below_threshold():
    g = make_game()
    anti, red = g.players
    anti.faction_id = 'hong_kong'
    red.faction_id = 'red_army'
    anti.organizations = {town: 1 for town in china_towns(g, 13)}
    red.organizations = {'北京': 1}
    g.turn = 20
    phase, winner = evaluate(g)
    return ok(
        'no_win_when_below_threshold',
        phase != GamePhase.FINISHED and winner is None,
        {'phase': phase, 'winner': winner, 'anti_org_count': sum(anti.organizations.values()), 'turn': g.turn},
    )


def main():
    results = [
        test_red_survival_after_turn_20(),
        test_red_taiwan_14_orgs_early_win(),
        test_non_red_china_14_orgs_win(),
        test_shared_orgs_count_for_non_red_victory(),
        test_no_win_when_below_threshold(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# VICTORY RULES VALIDATION', '', '日期：2026-05-09', '', f"summary: {summary}", '']
    for r in results:
        lines.append(f"## {r['name']}")
        lines.append(f"- result: {'PASS' if r['ok'] else 'FAIL'}")
        lines.append(f"- detail: {json.dumps(r['detail'], ensure_ascii=False)}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
