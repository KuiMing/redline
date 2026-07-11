import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-cards'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase
from server.cards import Card


CARD = '東洋奧援'

# Each case: org_towns picks towns whose map 'ruler' tags exercise a specific
# region-dominance combination for 東洋奧援 (支援卡: 東洋).
CASES = [
    {
        'name': 'tier3_own_region',
        'org_towns': ['沖繩'],  # ruler: 東洋 (own support_region)
        'expected_tier': 3,
        'expected_effect_type': 'interactive_build_anywhere_inner',
    },
    {
        'name': 'tier2_taiwan_southeast_asia_pair',
        'org_towns': ['臺北', '河內'],  # ruler: 臺灣, 南洋 (region index 0 after fix)
        'expected_tier': 2,
        'expected_effect_type': 'interactive_build_near_inner',
    },
    {
        'name': 'tier2_northland_anglo_pair',
        'org_towns': ['伯力', '紐約'],  # ruler: 北國, 英美 (region index 1; previously unreachable/stuck at tier 1)
        'expected_tier': 2,
        'expected_effect_type': 'interactive_build_near_inner',
    },
    {
        'name': 'tier2_taiwan_only_or_semantics',
        'org_towns': ['臺北'],  # 只主導配對其中一個地區（臺灣）即應達 II 級（2026-07-11 裁決：OR）
        'expected_tier': 2,
        'expected_effect_type': 'interactive_build_near_inner',
    },
    {
        'name': 'tier2_northland_only_or_semantics',
        'org_towns': ['伯力'],  # 只主導北國
        'expected_tier': 2,
        'expected_effect_type': 'interactive_build_near_inner',
    },
    {
        'name': 'tier1_fallback',
        'org_towns': ['北京'],  # ruler: 牆內 only, none of the above
        'expected_tier': 1,
        'expected_effect_type': 'gain_resource',
    },
]


def _new_game(org_towns):
    g = Game([('p1', 'player'), ('p2', 'red')])
    player, red = g.players
    player.id = 'p1'
    red.id = 'p2'
    player.faction_id = 'support_validator'
    player.base = org_towns[0]
    player.organizations = {town: 1 for town in org_towns}
    red.faction_id = 'red_army'
    red.base = '北京'
    red.organizations = {'北京': 1}
    red.hand = []
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    support = g._make_support_card(CARD)
    player.hand = [support]
    player.deck.draw_pile = [Card(f'補牌{i}', 'command', {}) for i in range(1, 5)]
    player.deck.discard_pile = []
    player.resources = {'money': 0, 'propaganda': 0}
    return g, player, red


def _run_case(case):
    g, player, red = _new_game(case['org_towns'])
    detected_tier, region_index, matched = g._support_card_tier(player, CARD)
    effect_type, payload = g._resolve_support_card_effect(CARD, detected_tier, region_index)
    before_propaganda = player.resources['propaganda']
    result = g.play_card(0, mode='action')
    after_propaganda = player.resources['propaganda']

    checks = {
        'play_card_success': result.get('success') is True,
        'tier_detected': detected_tier == case['expected_tier'],
        'effect_type_matches': effect_type == case['expected_effect_type'],
    }
    if case['expected_effect_type'] == 'gain_resource':
        checks['propaganda_gained_2'] = after_propaganda - before_propaganda == 2

    return {
        'name': case['name'],
        'org_towns': case['org_towns'],
        'expected_tier': case['expected_tier'],
        'detected_tier': detected_tier,
        'region_index': region_index,
        'matched_rulers': matched,
        'expected_effect_type': case['expected_effect_type'],
        'actual_effect_type': effect_type,
        'result': result,
        'checks': checks,
        'ok': all(checks.values()),
    }


def main():
    results = [_run_case(case) for case in CASES]
    summary = {
        'scope': [CARD],
        'purpose': (
            'Regression proof for B1-a fix: data/cards/support_taxonomy.v1.1.json 東洋奧援 '
            'entry was missing the 北國/英美 secondary-region pair (stale/corrupted vs. its own '
            'generator script). Also verifies the region_index==0 tier-2 effect branch in '
            'server/game.py:_resolve_support_card_effect grants the correct near-range build, '
            'not the ignore-distance build, now that region_index 0 legitimately resolves to '
            'tier 2 for the 臺灣/南洋 pair.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'EAST_ASIA_SUPPORT_TAXONOMY_FIX_VALIDATION_20260710.json'
    md_path = RECORD_DIR / 'EAST_ASIA_SUPPORT_TAXONOMY_FIX_VALIDATION_20260710.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 東洋奧援 taxonomy fix validation\n\n'
        '可重跑指令：`python3 scripts/validate_east_asia_support_taxonomy_fix.py`\n\n'
        f"- scope: {', '.join(summary['scope'])}\n"
        f"- total: {summary['total']}\n"
        f"- passed: {summary['passed']}\n"
        f"- failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: "
            f"tier={r['detected_tier']} region_index={r['region_index']} matched={json.dumps(r['matched_rulers'], ensure_ascii=False)} "
            f"effect={r['actual_effect_type']} checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
