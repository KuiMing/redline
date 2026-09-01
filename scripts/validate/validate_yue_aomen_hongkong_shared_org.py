import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game

TOWN = '廣州'
OTHER_TOWN = '深圳'


def _new_game(faction_a, faction_b):
    g = Game([('p1', 'player'), ('p2', 'player2')])
    a, b = g.players
    a.id = 'p1'
    b.id = 'p2'
    a.faction_id = faction_a
    b.faction_id = faction_b
    return g, a, b


def _check_pair(owner_faction, viewer_faction, town, expect_shared):
    g, owner, viewer = _new_game(owner_faction, viewer_faction)
    viewer.organizations = {}
    owner.organizations = {town: 1}
    count = g._shared_org_count(viewer, town)
    origin = g._shared_origin_owner(viewer, town)
    ok = (count == (1 if expect_shared else 0)) and (
        (origin is owner) if expect_shared else (origin is None)
    )
    return {
        'name': f'{viewer_faction}_sees_{owner_faction}_org_in_{town}',
        'viewer_faction': viewer_faction,
        'owner_faction': owner_faction,
        'town': town,
        'expect_shared': expect_shared,
        'shared_org_count': count,
        'origin_owner_faction': getattr(origin, 'faction_id', None),
        'ok': ok,
    }


def main():
    cases = [
        # Previously broken direction: yue/aomen player should see hong_kong's org as shared.
        _check_pair('hong_kong', 'yue', TOWN, expect_shared=True),
        _check_pair('hong_kong', 'aomen', OTHER_TOWN, expect_shared=True),
        # Regression: the already-working direction must still work.
        _check_pair('yue', 'hong_kong', TOWN, expect_shared=True),
        _check_pair('aomen', 'hong_kong', OTHER_TOWN, expect_shared=True),
        # Sanity: unrelated faction pair must NOT be treated as sharing.
        _check_pair('hong_kong', 'liberals', TOWN, expect_shared=False),
    ]

    summary = {
        'scope': ['yue', 'aomen', 'hong_kong'],
        'purpose': (
            'Regression proof for A3 fix: _factions_sharing_with in server/game.py only '
            'matched hard-coded substrings (\'粵、澳門\', \'藍線臺灣\', \'綠線臺灣\') in a '
            'faction\'s own special_rules text, so hong_kong -> yue/aomen worked but the '
            'reverse (yue/aomen -> hong_kong, declared via each faction\'s own '
            '"遊戲過程中可與香港共用組織。" special_rules text) never matched. Added a '
            "'香港' pattern so the relationship is symmetric."
        ),
        'total': len(cases),
        'passed': sum(1 for c in cases if c['ok']),
        'failed': sum(1 for c in cases if not c['ok']),
    }
    payload = {'summary': summary, 'results': cases}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'YUE_AOMEN_HONGKONG_SHARED_ORG_FIX_VALIDATION_20260710.json'
    md_path = RECORD_DIR / 'YUE_AOMEN_HONGKONG_SHARED_ORG_FIX_VALIDATION_20260710.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 粵/澳門 <-> 香港 共用組織修正驗證\n\n'
        '可重跑指令：`python3 scripts/validate/validate_yue_aomen_hongkong_shared_org.py`\n\n'
        f"- scope: {', '.join(summary['scope'])}\n"
        f"- total: {summary['total']}\n"
        f"- passed: {summary['passed']}\n"
        f"- failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if c['ok'] else 'FAIL'} {c['name']}: "
            f"expect_shared={c['expect_shared']} shared_org_count={c['shared_org_count']} "
            f"origin_owner_faction={c['origin_owner_faction']}"
            for c in cases
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
