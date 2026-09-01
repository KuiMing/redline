import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'safehouse'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    g = Game([('p1', 'HK'), ('p2', 'Other')])
    hk = g.players[0]
    hk.faction_id = 'hong_kong'
    hk.base = '香港城'
    hk.organizations = {'香港城': 1}
    hk.build_range_bonus = 1  # simulate 安全屋 currently selected base effect
    g.turn_phase = TurnPhase.ACTION

    near = g.build_organization_with_support('香港城', '廣州')
    far = g.build_organization_with_support('香港城', '北京')

    out = {
        'near': near,
        'far': far,
        'orgs': hk.organizations,
    }
    (RECORD_DIR / 'SAFEHOUSE_BUILD_RANGE_VALIDATION.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (RECORD_DIR / 'SAFEHOUSE_BUILD_RANGE_VALIDATION.md').write_text(
        '# SAFEHOUSE BUILD RANGE VALIDATION\n\n'
        f"- near: {json.dumps(near, ensure_ascii=False)}\n"
        f"- far: {json.dumps(far, ensure_ascii=False)}\n",
        encoding='utf-8'
    )
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
