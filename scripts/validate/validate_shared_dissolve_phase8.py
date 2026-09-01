import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'shared-actions'
sys.path.insert(0, str(ROOT))

from server.game import Game
from server.cards import Card


def validate_shared_dissolve_hits_actual_owner():
    g = Game([('a', 'atk'), ('h', 'hu'), ('t', 'tw')])
    atk, hu, tw = g.players
    atk.faction_id = 'red_army'
    atk.hand = [Card('測試手牌', 'money', {'money': 1})]
    hu.faction_id = 'hu'
    tw.faction_id = 'taiwan_green'
    hu.organizations = {'紐約': 1}
    tw.organizations = {'上海': 1, '臺北': 1}

    result = g.dissolve_organization(atk, hu, '上海', source='card')
    ok = result.get('success') and tw.organizations.get('上海', 0) == 0 and hu.organizations.get('上海', 0) == 0
    return {
        'name': 'shared_dissolve_hits_actual_owner',
        'ok': ok,
        'detail': {
            'result': result,
            'hu_orgs': hu.organizations,
            'tw_orgs': tw.organizations,
        }
    }


def validate_shared_dissolve_triggers_defense():
    g = Game([('a', 'atk'), ('h', 'hu'), ('t', 'tw')])
    atk, hu, tw = g.players
    atk.faction_id = 'red_army'
    atk.hand = []
    hu.faction_id = 'hu'
    tw.faction_id = 'mongol'
    hu.organizations = {'紐約': 1}
    hu.base = '紐約'
    tw.organizations = {'上海': 1}
    tw.base = '上海'

    hu_faction = dict(g.faction_by_id['hu'])
    hu_faction['shared_organizations_with'] = ['mongol']
    g.faction_by_id['hu'] = hu_faction

    result = g.dissolve_organization(atk, hu, '上海', source='card')
    ok = result.get('error') == '盟旗學校：須先棄1張手牌，才可以瓦解蒙古組織'
    return {
        'name': 'shared_dissolve_triggers_defense',
        'ok': ok,
        'detail': {
            'result': result,
            'hu_orgs': hu.organizations,
            'tw_orgs': tw.organizations,
        }
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        validate_shared_dissolve_hits_actual_owner(),
        validate_shared_dissolve_triggers_defense(),
    ]
    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    (RECORD_DIR / 'SHARED_DISSOLVE_PHASE8_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# SHARED DISSOLVE PHASE8 VALIDATION',
        '',
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        '',
    ]
    for r in results:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {json.dumps(r['detail'], ensure_ascii=False)}")
    (RECORD_DIR / 'SHARED_DISSOLVE_PHASE8_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
