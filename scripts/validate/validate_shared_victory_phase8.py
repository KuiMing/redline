import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game
from server.victory import VictoryEngine

RECORD_DIR = ROOT / 'docs' / 'records' / 'shared-actions'
OUT_JSON = RECORD_DIR / 'SHARED_VICTORY_PHASE8_VALIDATION.json'
OUT_MD = RECORD_DIR / 'SHARED_VICTORY_PHASE8_VALIDATION.md'


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    g = Game([('p1', 'TW'), ('p2', 'Hakka')])
    tw, hakka = g.players
    tw.faction_id = 'taiwan_green'
    hakka.faction_id = 'hakka'
    inside = sorted(g.towns_by_ruler.get('紅軍', []))
    assert len(inside) >= 14
    tw.organizations = {town: 1 for town in inside[:13]}
    hakka.organizations = {inside[13]: 1}
    g.faction_by_id = {f['id']: f for f in g.factions}
    ve = VictoryEngine(g.factions)
    count = ve._count_scope(tw, '牆內', g)
    distinct_physical_towns = set(tw.organizations) | set(hakka.organizations)
    payload = {
        'summary': {
            'total': 3,
            'passed': sum((count == 14, len(distinct_physical_towns) == 14, all(value == 1 for value in tw.organizations.values()) and all(value == 1 for value in hakka.organizations.values()))),
            'failed': sum((count != 14, len(distinct_physical_towns) != 14, not (all(value == 1 for value in tw.organizations.values()) and all(value == 1 for value in hakka.organizations.values())))),
        },
        'count': count,
        'owned_count': len(tw.organizations),
        'shared_count': count - len(tw.organizations),
        'distinct_physical_towns': len(distinct_physical_towns),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    OUT_MD.write_text(
        '# SHARED VICTORY PHASE8 VALIDATION\n\n'
        f"- count: {count}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
