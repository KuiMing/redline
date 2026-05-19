import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'shared-actions'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def ok(name, condition, detail=''):
    return {'name': name, 'ok': bool(condition), 'detail': detail}


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    g = Game([('p1', 'HK'), ('p2', 'Yue')])
    hk, yue = g.players
    hk.faction_id = 'hong_kong'
    yue.faction_id = 'yue'
    hk.base = '香港城'
    yue.base = '廣州'
    hk.organizations = {'香港城': 1}
    yue.organizations = {'廣州': 1, '香港城': 1}
    g.turn_phase = TurnPhase.ACTION

    can_hk_use_shared = g._town_has_shared_org_access(hk, '香港城')
    can_yue_use_shared = g._town_has_shared_org_access(yue, '香港城')
    result = g.build_organization('香港城')

    out = {
        'shared_hk': can_hk_use_shared,
        'shared_yue': can_yue_use_shared,
        'build_result': result,
        'hk_orgs': hk.organizations,
    }
    summary = {
        'total': 1,
        'passed': 1 if (can_hk_use_shared and can_yue_use_shared and result.get('success') is True) else 0,
        'failed': 0 if (can_hk_use_shared and can_yue_use_shared and result.get('success') is True) else 1,
    }
    payload = {'summary': summary, 'result': out}
    (RECORD_DIR / 'SHARED_ORGANIZATIONS_PHASE6_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (RECORD_DIR / 'SHARED_ORGANIZATIONS_PHASE6_VALIDATION.md').write_text(
        '# SHARED ORGANIZATIONS PHASE6 VALIDATION\n\n'
        f"- shared_hk: {can_hk_use_shared}\n"
        f"- shared_yue: {can_yue_use_shared}\n"
        f"- build_result: {json.dumps(result, ensure_ascii=False)}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
