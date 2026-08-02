import json
import random
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from server.game import Game, GamePhase, TurnPhase

RECORD_DIR = BASE / 'docs' / 'records' / 'misc'
OUT_JSON = RECORD_DIR / 'ERA_RULES_VALIDATION.json'
OUT_MD = RECORD_DIR / 'ERA_RULES_VALIDATION.md'


def make_game():
    random.seed(20260510)
    game = Game([('p1', 'actor'), ('p2', 'red')])
    actor = game.players[0]
    red = game.players[1]
    actor.id = 'p1'
    actor.name = 'actor'
    actor.faction_id = 'hong_kong'
    actor.base = '香港城'
    actor.organizations = {'香港城': 1}
    red.id = 'p2'
    red.name = 'red'
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.EVENT
    game.winner = None
    return game, actor, red


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def first_towns(game, region, count):
    towns = game._towns_for_region_alias(region)
    return towns[:count]


def first_ruler_towns(game, ruler, count):
    towns = [
        town for town, info in game.map.get('towns', {}).items()
        if ruler in (info.get('ruler') or [])
    ]
    return towns[:count]


def place_orgs(player, towns, count_each=1):
    player.organizations = {town: count_each for town in towns}


def run_checks():
    checks = []

    # 1. New games should not force-activate an era before its trigger is met.
    game, actor, red = make_game()
    checks.append(check(
        'new_game_starts_without_forced_hong_kong_era',
        'hong_kong' not in game.era_engine.get_active_eras(),
        {
            'rule': '時代關卡必須由觸發條件啟動；新局不應為 UI 測試強制啟動香港時代。',
            'active_eras': game.era_engine.get_active_eras(),
        }
    ))

    # 2. Hong Kong era should not trigger from the wrong faction even with ten distinct inside-wall organizations.
    game, actor, red = make_game()
    actor.faction_id = 'taiwan_green'
    place_orgs(actor, first_towns(game, 'china', 10))
    game._check_era_trigger()
    checks.append(check(
        'hong_kong_era_requires_hong_kong_faction',
        'hong_kong' not in game.era_engine.get_active_eras(),
        {
            'rule': '香港時代條件文字是「香港在牆內擁有至少10個有效組織」；應限定香港陣營，而非任意玩家。',
            'actor_faction': actor.faction_id,
            'actor_orgs': dict(actor.organizations),
            'active_eras': game.era_engine.get_active_eras(),
        }
    ))

    # 3. Hong Kong era should trigger when Hong Kong faction has ten distinct inside-wall organizations.
    game, actor, red = make_game()
    actor.faction_id = 'hong_kong'
    place_orgs(actor, first_towns(game, 'china', 10))
    game._check_era_trigger()
    checks.append(check(
        'hong_kong_era_triggers_for_hong_kong_faction',
        'hong_kong' in game.era_engine.get_active_eras(),
        {
            'rule': '香港陣營在10個不同牆內城鎮擁有有效組織時，香港時代應觸發。',
            'actor_faction': actor.faction_id,
            'actor_orgs': dict(actor.organizations),
            'active_eras': game.era_engine.get_active_eras(),
            'notification': game.era_notification,
        }
    ))

    # 4. Kazakhstan era from source card table should exist in structured runtime data.
    game, actor, red = make_game()
    checks.append(check(
        'kazakh_era_definition_exists',
        game.era_engine.get_definition('kazakh') is not None,
        {
            'rule': '原始時代卡表包含「[哈薩克]伊塔事件」，runtime structured era data 也應包含 kazakh。',
            'known_era_ids': sorted(game.era_engine.era_defs.keys()),
        }
    ))

    # 5. Kazakhstan era should require Kazakh faction, Northland-ruler towns, and inner-China towns.
    game, actor, red = make_game()
    northland_towns = first_ruler_towns(game, '北國', 7)
    actor.faction_id = 'taiwan_green'
    actor.organizations = {}
    for town in northland_towns:
        actor.organizations[town] = 1
    for town in first_towns(game, 'china', 3):
        actor.organizations[town] = 1
    game._check_era_trigger()
    wrong_faction_active = 'kazakh' in game.era_engine.get_active_eras()

    game, actor, red = make_game()
    actor.faction_id = 'kazakh'
    actor.organizations = {}
    for town in northland_towns:
        actor.organizations[town] = 1
    for town in first_towns(game, 'china', 3):
        actor.organizations[town] = 1
    game._check_era_trigger()
    kazakh_active = 'kazakh' in game.era_engine.get_active_eras()
    checks.append(check(
        'kazakh_era_requires_kazakh_faction_northland_ruler_and_inner_counts',
        len(northland_towns) >= 7 and not wrong_faction_active and kazakh_active,
        {
            'rule': '哈薩克伊塔事件需哈薩克在 map.json ruler=北國 的城鎮達7組織，且在牆內/中華區達3組織；非哈薩克不應觸發。',
            'northland_towns_sample': northland_towns,
            'wrong_faction_triggered': wrong_faction_active,
            'kazakh_triggered': kazakh_active,
            'active_eras_after_kazakh_check': game.era_engine.get_active_eras(),
        }
    ))

    return checks


def write_reports(checks):
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    payload = {
        'generated_at': date.today().isoformat(),
        'rule_area': 'era_rules',
        'summary': summary,
        'checks': checks,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        '# Era Rules Validation',
        '',
        f"Generated: {payload['generated_at']}",
        '',
        f"Summary: {summary['passed']}/{summary['total']} passed",
        '',
    ]
    for c in checks:
        lines.append(f"## {'PASS' if c['passed'] else 'FAIL'} — {c['name']}")
        lines.append('')
        lines.append('```json')
        lines.append(json.dumps(c['details'], ensure_ascii=False, indent=2))
        lines.append('```')
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return summary


def main():
    checks = run_checks()
    summary = write_reports(checks)
    print(json.dumps({'summary': summary}, ensure_ascii=False))
    return 0 if summary['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
