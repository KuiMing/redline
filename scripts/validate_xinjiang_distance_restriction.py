import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def _new_game(faction_id):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = 'red_army'
    a.organizations = {}
    b.organizations = {}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    return g, a, b


def _card_effect(g, card_name):
    card = next(c for c in g.structured_cards if c['name'] == card_name)
    return next(e for e in card['effect'] if e.get('type') == 'build')


def case_ability_resolved():
    g, a, b = _new_game('uyghur_munich')
    checks = {
        'munich_is_restricted': g._player_is_distance_restricted(a) is True,
        'kazakh_not_restricted': True,
    }
    g2, a2, b2 = _new_game('kazakh')
    checks['kazakh_not_restricted'] = g2._player_is_distance_restricted(a2) is False
    inner_town = '北京'
    outer_town = '慕尼黑'
    checks['restricts_inner'] = g._faction_restricts_ignore_distance_build(a, inner_town) is True
    checks['not_restrict_outer'] = g._faction_restricts_ignore_distance_build(a, outer_town) is False
    return {'name': 'ability_resolved_and_scoped_to_inner', 'checks': checks, 'ok': all(checks.values())}


def case_ideologue_excludes_inner_for_restricted():
    inner_towns = None
    g, a, b = _new_game('uyghur_munich')
    inner_towns = set(g._towns_for_region_alias('china'))
    a.organizations = {'喀什': 1}
    effect = _card_effect(g, '思想家')
    towns = {c['town'] for c in g._card_build_town_choices(a, effect)}
    g2, a2, b2 = _new_game('kazakh')
    a2.organizations = {'喀什': 1}
    towns_unrestricted = {c['town'] for c in g2._card_build_town_choices(a2, _card_effect(g2, '思想家'))}
    near = g._towns_within_steps(['喀什'], max_steps=1)
    checks = {
        'restricted_gets_no_inner_towns': not (towns & inner_towns),
        # 對照組（無此限制的陣營）在其發展空間內可無視距離拿到 1 格以外的牆內城鎮
        'unrestricted_gets_distant_inner': bool((towns_unrestricted & inner_towns) - near),
    }
    return {'name': 'ideologue_ignore_distance_excludes_inner_for_restricted',
            'restricted_sample': sorted(towns)[:5], 'checks': checks, 'ok': all(checks.values())}


def case_org_experience_a_inner_fallback():
    g, a, b = _new_game('uyghur_munich')
    inner_towns = set(g._towns_for_region_alias('china'))
    a.organizations = {'喀什': 1}
    near_inner = g._towns_within_steps(['喀什'], max_steps=1) & inner_towns
    effect = _card_effect(g, '組織經驗甲')
    towns = {c['town'] for c in g._card_build_town_choices(a, effect)}
    inner_offered = towns & inner_towns
    checks = {
        'effect_has_fallback_clause': int(effect.get('inner_fallback_range', 0) or 0) == 1,
        'inner_offers_limited_to_1_step': bool(inner_offered) and inner_offered <= near_inner,
        'distant_inner_excluded': '北京' not in towns,
    }
    g2, a2, b2 = _new_game('kazakh')
    a2.organizations = {'喀什': 1}
    towns_unrestricted = {c['town'] for c in g2._card_build_town_choices(a2, _card_effect(g2, '組織經驗甲'))}
    near_any = g._towns_within_steps(['喀什'], max_steps=1)
    checks['unrestricted_still_ignore_distance'] = bool((towns_unrestricted & inner_towns) - near_any)
    return {'name': 'org_experience_a_inner_fallback_range_1',
            'inner_offered': sorted(inner_offered), 'checks': checks, 'ok': all(checks.values())}


def case_east_asia_support_tier3_downgrade():
    g, a, b = _new_game('uyghur_munich')
    a.organizations = {'喀什': 1}
    anywhere = {t['town'] for t in g._interactive_support_build_towns(a, near_only=False)}
    near = {t['town'] for t in g._interactive_support_build_towns(a, near_only=True)}
    g2, a2, b2 = _new_game('kazakh')
    a2.organizations = {'喀什': 1}
    anywhere_unrestricted = {t['town'] for t in g2._interactive_support_build_towns(a2, near_only=False)}
    checks = {
        'restricted_anywhere_downgraded_to_near': anywhere == near,
        'unrestricted_anywhere_larger_than_near': len(anywhere_unrestricted) > len(near),
    }
    return {'name': 'east_asia_support_tier3_downgraded_to_near_for_restricted',
            'restricted_count': len(anywhere), 'unrestricted_count': len(anywhere_unrestricted),
            'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_ability_resolved(),
        case_ideologue_excludes_inner_for_restricted(),
        case_org_experience_a_inner_fallback(),
        case_east_asia_support_tier3_downgrade(),
    ]
    summary = {
        'scope': ['新疆社會管控 (S2, affects ALL FOUR uyghur variants per faction data — the audit initially said munich only)', '組織經驗甲 inner-fallback clause'],
        'purpose': (
            'S2 (second-pass audit): uyghur_munich\'s restriction 新疆社會管控 ("無法無視距離'
            '建立牆內組織") had zero implementation — every ignore-distance build path ignored '
            'it. Now enforced via _player_is_distance_restricted/_faction_restricts_ignore_'
            'distance_build at: _card_build_town_choices (思想家/組織經驗甲 card builds, with '
            '組織經驗甲\'s printed inner_fallback_range=1 clause expressed in the card data), '
            'the support-build target distance check, the 東洋奧援 tier-3 interactive list '
            '(anywhere_inner downgraded to near_inner for restricted players — implementation '
            'ruling following 組織經驗甲\'s printed downgrade convention), and the '
            'non-interactive build_anywhere_inner fallback. Outer-wall ignore-distance builds '
            'remain unaffected; other factions unaffected.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'XINJIANG_DISTANCE_RESTRICTION_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'XINJIANG_DISTANCE_RESTRICTION_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 新疆社會管控距離限制驗證（S2）\n\n'
        '可重跑指令：`python3 scripts/validate_xinjiang_distance_restriction.py`\n\n'
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}\n\n"
        '## Results\n\n'
        + '\n'.join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: checks={json.dumps(r['checks'], ensure_ascii=False)}"
            for r in results
        )
        + '\n',
        encoding='utf-8',
    )
    print(json.dumps(payload, ensure_ascii=False, default=str))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
