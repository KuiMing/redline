import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game
from server.cards import Card


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    g = Game([('p1', 'Mongol'), ('p2', 'Attacker')])
    mongol = g.players[0]
    attacker = g.players[1]

    mongol.faction_id = 'mongol'
    mongol.base = '烏蘭巴托'
    mongol.organizations = {'烏蘭巴托': 1}

    attacker.faction_id = 'red_army'
    attacker.base = '北京'
    attacker.organizations = {'北京': 1}

    attacker.hand = [Card('測試棄牌', 'money', {'money': 1})]
    result_success = g.dissolve_organization(attacker, mongol, '烏蘭巴托', source='card')
    hand_after_success = [c.name for c in attacker.hand]
    discard_after_success = [c.name for c in attacker.deck.discard_pile]
    mongol_after_success = dict(mongol.organizations)

    mongol.organizations = {'烏蘭巴托': 1}
    attacker.hand = []
    result_fail = g.dissolve_organization(attacker, mongol, '烏蘭巴托', source='card')

    out = {
        'success_case': {
            'result': result_success,
            'attacker_hand_after': hand_after_success,
            'attacker_discard_after': discard_after_success,
            'mongol_orgs_after': mongol_after_success,
        },
        'fail_case': {
            'result': result_fail,
            'mongol_orgs_after': dict(mongol.organizations),
        }
    }
    (RECORD_DIR / 'MONGOL_DISCARD_SHIELD_VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# MONGOL DISCARD SHIELD VALIDATION',
        '',
        f"- success_case: {json.dumps(result_success, ensure_ascii=False)}",
        f"- attacker_discard_after: {discard_after_success}",
        f"- fail_case: {json.dumps(result_fail, ensure_ascii=False)}",
    ]
    (RECORD_DIR / 'MONGOL_DISCARD_SHIELD_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
