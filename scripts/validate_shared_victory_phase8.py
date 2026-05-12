import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game
from server.victory import VictoryEngine


def main():
    g = Game([('p1', 'TW'), ('p2', 'Church')])
    tw, church = g.players
    tw.faction_id = 'taiwan_green'
    church.faction_id = 'underground_church'
    tw.organizations = {'北京': 8, '南京': 3, '廣州': 3}
    church.organizations = {'北京': 2, '南京': 0, '廣州': 0}
    g.faction_by_id = {f['id']: f for f in g.factions}
    ve = VictoryEngine(g.factions)
    count = ve._count_scope(tw, '牆內', g)
    payload = {
        'summary': {
            'total': 1,
            'passed': 1 if count >= 14 else 0,
            'failed': 0 if count >= 14 else 1,
        },
        'count': count,
    }
    Path('SHARED_VICTORY_PHASE8_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path('SHARED_VICTORY_PHASE8_VALIDATION.md').write_text(
        '# SHARED VICTORY PHASE8 VALIDATION\n\n'
        f"- count: {count}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
