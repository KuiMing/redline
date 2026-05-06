import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game
from server.victory import VictoryEngine


def main():
    g = Game([('p1', 'TW'), ('p2', 'HU')])
    tw, hu = g.players
    tw.faction_id = 'taiwan_green'
    hu.faction_id = 'hu'

    tw.organizations = {'上海': 1, '北京': 2}
    hu.organizations = {'紐約': 10}

    shared_with = g._factions_sharing_with('hu')
    access = g._town_has_shared_org_access(hu, '上海')
    count = g._shared_org_count(hu, '上海')

    ve = VictoryEngine(g.factions, g.board_regions)
    win, winner = ve._check_player_conditions(hu, g)

    payload = {
        'summary': {
            'total': 4,
            'passed': sum([
                'taiwan_green' in shared_with,
                access,
                count == 1,
                bool(win),
            ]),
            'failed': 4 - sum([
                'taiwan_green' in shared_with,
                access,
                count == 1,
                bool(win),
            ]),
        },
        'shared_with': sorted(shared_with),
        'access_shanghai': access,
        'shared_count_shanghai': count,
        'win': win,
        'winner': winner,
    }

    (ROOT / 'HU_SHARED_AND_WIN_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'HU_SHARED_AND_WIN_VALIDATION.md').write_text(
        '# HU SHARED AND WIN VALIDATION\n\n'
        f"- shared_with: {json.dumps(sorted(shared_with), ensure_ascii=False)}\n"
        f"- access_shanghai: {access}\n"
        f"- shared_count_shanghai: {count}\n"
        f"- win: {win}\n"
        f"- winner: {winner}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
