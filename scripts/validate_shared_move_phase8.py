import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def main():
    g = Game([('p1', 'HK'), ('p2', 'Yue')])
    hk, yue = g.players
    hk.faction_id = 'hong_kong'
    yue.faction_id = 'yue'
    hk.base = '香港城'
    yue.base = '廣州'
    hk.organizations = {}
    yue.organizations = {'廣州': 1}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0

    result = g.move_organization('廣州', '深圳', 'rail')

    payload = {
        'summary': {
            'total': 1,
            'passed': 1 if (result.get('success') and yue.organizations.get('廣州', 0) == 0 and hk.organizations.get('深圳', 0) == 1) else 0,
            'failed': 0 if (result.get('success') and yue.organizations.get('廣州', 0) == 0 and hk.organizations.get('深圳', 0) == 1) else 1,
        },
        'result': result,
        'hk_orgs': hk.organizations,
        'yue_orgs': yue.organizations,
    }
    (ROOT / 'SHARED_MOVE_PHASE8_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'SHARED_MOVE_PHASE8_VALIDATION.md').write_text(
        '# SHARED MOVE PHASE8 VALIDATION\n\n'
        f"- result: {json.dumps(result, ensure_ascii=False)}\n"
        f"- hk_orgs: {json.dumps(hk.organizations, ensure_ascii=False)}\n"
        f"- yue_orgs: {json.dumps(yue.organizations, ensure_ascii=False)}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
