import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'shared-actions'
sys.path.insert(0, str(ROOT))

from server.game import Game


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    g = Game([('p1', 'Taiwan'), ('p2', 'Church')])
    tw, church = g.players
    tw.faction_id = 'taiwan_green'
    church.faction_id = 'underground_church'
    tw.base = '臺北'
    church.base = '北京'
    tw.organizations = {}
    church.organizations = {'北京': 1}
    g.faction_by_id = {f['id']: f for f in g.factions}

    count_tw = g._shared_org_count(tw, '北京')
    count_church = g._shared_org_count(church, '北京')
    payload = {
        'summary': {
            'total': 1,
            'passed': 1 if count_tw == 1 and count_church == 1 and not g._organization_occupancy_violations() else 0,
            'failed': 0 if count_tw == 1 and count_church == 1 and not g._organization_occupancy_violations() else 1,
        },
        'count_tw': count_tw,
        'count_church': count_church,
    }
    (RECORD_DIR / 'SHARED_ORG_COUNT_PHASE6B_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (RECORD_DIR / 'SHARED_ORG_COUNT_PHASE6B_VALIDATION.md').write_text(
        '# SHARED ORG COUNT PHASE6B VALIDATION\n\n'
        f"- count_tw: {count_tw}\n"
        f"- count_church: {count_church}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
