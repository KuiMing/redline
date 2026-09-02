import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def _new_game(faction_id, era_id=None):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = 'red_army'
    a.organizations = {}
    b.organizations = {}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    if era_id:
        assert g.era_engine.activate_era(era_id), f'era {era_id} 未能啟用'
    return g, a, b


def _card_effect(g, card_name):
    card = next(c for c in g.structured_cards if c['name'] == card_name)
    return next(e for e in card['effect'] if e.get('type') == 'build')


def _build_towns(g, player, card_name):
    return {c['town'] for c in g._card_build_town_choices(player, _card_effect(g, card_name))}


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


def case_era_restriction_resolved():
    """時代關卡 restrict_ignore_distance_build 的判定本身：只限本陣營、只限 scope 內。"""
    g, a, b = _new_game('liberals', era_id='rebels')       # liberals 屬 rebel 陣營
    g_off, a_off, _ = _new_game('kazakh', era_id='rebels')  # 其他陣營，同一時代生效中
    g_none, a_none, _ = _new_game('liberals')               # 同陣營，但時代尚未觸發
    g_kz, a_kz, _ = _new_game('kazakh', era_id='kazakh')     # 同型效果的另一個時代關卡
    checks = {
        'rebels_era_restricts_inner': g._era_restricts_ignore_distance_build(a, '北京') is True,
        'rebels_era_not_restrict_outer': g._era_restricts_ignore_distance_build(a, '東京') is False,
        'other_camp_unaffected': g_off._era_restricts_ignore_distance_build(a_off, '北京') is False,
        'inactive_era_unaffected': g_none._era_restricts_ignore_distance_build(a_none, '北京') is False,
        'kazakh_era_restricts_inner': g_kz._era_restricts_ignore_distance_build(a_kz, '北京') is True,
        'kazakh_era_not_restrict_outer': g_kz._era_restricts_ignore_distance_build(a_kz, '阿拉木圖') is False,
    }
    return {'name': 'era_restrict_ignore_distance_build_resolved_and_scoped',
            'checks': checks, 'ok': all(checks.values())}


def case_ideologue_inner_fallback():
    """（改寫）思想家過去在受限時被「整片牆內全部排除」，但卡面規則只是不能無視距離，
    正確行為是退回近距離（1格，另有增加建立距離的能力時為2格）。"""
    g, a, b = _new_game('uyghur_munich')
    inner_towns = set(g._towns_for_region_alias('china'))
    a.organizations = {'喀什': 1}
    effect = _card_effect(g, '思想家')
    towns = _build_towns(g, a, '思想家')
    inner_offered = towns & inner_towns
    near_inner = g._towns_within_steps(['喀什'], max_steps=1) & inner_towns

    g2, a2, b2 = _new_game('kazakh')
    a2.organizations = {'喀什': 1}
    towns_unrestricted = _build_towns(g2, a2, '思想家')
    near_any = g._towns_within_steps(['喀什'], max_steps=1)
    checks = {
        # 舊版斷言為 'restricted_gets_no_inner_towns': not (towns & inner_towns)——
        # 那是把「不能無視距離」誤解成「完全不能建立」，已於本次修正。
        'effect_has_fallback_clause': int(effect.get('inner_fallback_range', 0) or 0) == 1,
        'inner_offers_present_not_empty': bool(inner_offered),
        'inner_offers_limited_to_1_step': inner_offered <= near_inner,
        'distant_inner_excluded': '北京' not in towns,
        'outer_wall_still_ignore_distance': bool((towns - inner_towns) - near_any),
        'unrestricted_gets_distant_inner': bool((towns_unrestricted & inner_towns) - near_any),
    }
    return {'name': 'ideologue_inner_fallback_range_1_for_restricted',
            'inner_offered': sorted(inner_offered), 'checks': checks, 'ok': all(checks.values())}


def case_org_experience_a_inner_fallback():
    g, a, b = _new_game('uyghur_munich')
    inner_towns = set(g._towns_for_region_alias('china'))
    a.organizations = {'喀什': 1}
    near_inner = g._towns_within_steps(['喀什'], max_steps=1) & inner_towns
    effect = _card_effect(g, '組織經驗甲')
    towns = _build_towns(g, a, '組織經驗甲')
    inner_offered = towns & inner_towns
    checks = {
        'effect_has_fallback_clause': int(effect.get('inner_fallback_range', 0) or 0) == 1,
        'inner_offers_limited_to_1_step': bool(inner_offered) and inner_offered <= near_inner,
        'distant_inner_excluded': '北京' not in towns,
    }
    g2, a2, b2 = _new_game('kazakh')
    a2.organizations = {'喀什': 1}
    towns_unrestricted = _build_towns(g2, a2, '組織經驗甲')
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


def _era_card_build_case(name, faction_id, era_id, origin):
    """時代關卡生效後，思想家／組織經驗甲的牆內候選降為近距離、牆外維持無視距離。"""
    g, a, b = _new_game(faction_id, era_id=era_id)
    a.organizations = {origin: 1}
    inner_towns = set(g._towns_for_region_alias('china'))
    near_inner = g._towns_within_steps([origin], max_steps=1) & inner_towns
    near_any = g._towns_within_steps([origin], max_steps=1)

    g0, a0, _ = _new_game(faction_id)  # 對照組：同陣營但時代尚未觸發
    a0.organizations = {origin: 1}

    checks = {}
    detail = {}
    for card_name in ('思想家', '組織經驗甲'):
        towns = _build_towns(g, a, card_name)
        inner_offered = towns & inner_towns
        baseline_inner = _build_towns(g0, a0, card_name) & inner_towns
        detail[card_name] = sorted(inner_offered)
        checks[f'{card_name}_inner_limited_to_1_step'] = bool(inner_offered) and inner_offered <= near_inner
        checks[f'{card_name}_outer_still_ignore_distance'] = bool((towns - inner_towns) - near_any)
        checks[f'{card_name}_baseline_had_distant_inner'] = bool(baseline_inner - near_inner)

    # 增加建立距離的能力（build_range_bonus）時放寬為 2 格
    g2, a2, _ = _new_game(faction_id, era_id=era_id)
    a2.organizations = {origin: 1}
    a2.build_range_bonus = 1
    bonus_inner = _build_towns(g2, a2, '思想家') & inner_towns
    near_inner_2 = g2._towns_within_steps([origin], max_steps=2) & inner_towns
    checks['bonus_extends_fallback_to_2_steps'] = bool(bonus_inner - near_inner) and bonus_inner <= near_inner_2
    detail['bonus_inner'] = sorted(bonus_inner)

    return {'name': name, 'detail': detail, 'checks': checks, 'ok': all(checks.values())}


def case_rebels_era_card_builds():
    return _era_card_build_case(
        'rebels_era_restricts_ideologue_and_org_experience_a', 'liberals', 'rebels', '上海')


def case_kazakh_era_card_builds():
    return _era_card_build_case(
        'kazakh_era_restricts_ideologue_and_org_experience_a', 'kazakh', 'kazakh', '烏魯木齊')


def _era_support_case(name, faction_id, era_id, origin):
    g, a, b = _new_game(faction_id, era_id=era_id)
    a.organizations = {origin: 1}
    anywhere = {t['town'] for t in g._interactive_support_build_towns(a, near_only=False)}
    near = {t['town'] for t in g._interactive_support_build_towns(a, near_only=True)}
    g0, a0, _ = _new_game(faction_id)
    a0.organizations = {origin: 1}
    anywhere_baseline = {t['town'] for t in g0._interactive_support_build_towns(a0, near_only=False)}
    checks = {
        'era_anywhere_downgraded_to_near': anywhere == near,
        'baseline_anywhere_larger_than_near': len(anywhere_baseline) > len(near),
    }
    return {'name': name, 'restricted_towns': sorted(anywhere),
            'baseline_count': len(anywhere_baseline), 'checks': checks, 'ok': all(checks.values())}


def case_rebels_era_east_asia_support():
    return _era_support_case(
        'rebels_era_downgrades_east_asia_support_tier3', 'liberals', 'rebels', '上海')


def case_kazakh_era_east_asia_support():
    return _era_support_case(
        'kazakh_era_downgrades_east_asia_support_tier3', 'kazakh', 'kazakh', '烏魯木齊')


def case_other_camp_unaffected_while_era_active():
    """反賊時代生效中，非 rebel 陣營玩家的三條路徑完全不受影響。"""
    g, a, b = _new_game('kazakh', era_id='rebels')
    origin = '烏魯木齊'
    a.organizations = {origin: 1}
    inner_towns = set(g._towns_for_region_alias('china'))
    near_inner = g._towns_within_steps([origin], max_steps=1) & inner_towns
    checks = {}
    for card_name in ('思想家', '組織經驗甲'):
        inner_offered = _build_towns(g, a, card_name) & inner_towns
        checks[f'{card_name}_still_ignore_distance'] = bool(inner_offered - near_inner)
    anywhere = {t['town'] for t in g._interactive_support_build_towns(a, near_only=False)}
    near = {t['town'] for t in g._interactive_support_build_towns(a, near_only=True)}
    checks['support_anywhere_not_downgraded'] = len(anywhere) > len(near)
    return {'name': 'other_camp_unaffected_while_rebels_era_active',
            'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_ability_resolved(),
        case_era_restriction_resolved(),
        case_ideologue_inner_fallback(),
        case_org_experience_a_inner_fallback(),
        case_east_asia_support_tier3_downgrade(),
        case_rebels_era_card_builds(),
        case_kazakh_era_card_builds(),
        case_rebels_era_east_asia_support(),
        case_kazakh_era_east_asia_support(),
        case_other_camp_unaffected_while_era_active(),
    ]
    summary = {
        'scope': [
            '新疆社會管控 (S2, affects ALL FOUR uyghur variants per faction data)',
            '時代關卡 restrict_ignore_distance_build（[反賊]公知世代的終結／[哈薩克]伊塔事件，'
            '及任何未來同型效果）',
            '思想家 / 組織經驗甲 / 東洋奧援 tier-3 的 inner-fallback 降級',
        ],
        'purpose': (
            'S2 (second-pass audit): uyghur_munich\'s restriction 新疆社會管控 ("無法無視距離'
            '建立牆內組織") had zero implementation — every ignore-distance build path ignored '
            'it. Now enforced via _player_is_distance_restricted/_faction_restricts_ignore_'
            'distance_build. S3 (2026-08-09 playtest): the ERA-sourced version of the same '
            'restriction (era_structured.v1.1.json restrict_ignore_distance_build, ids "rebels" '
            'and "kazakh") was handled inconsistently — _card_build_town_choices hard-excluded '
            'every inner town instead of falling back to near range, and '
            '_interactive_support_build_towns never checked the era restriction at all, so '
            '東洋奧援 tier-3 fully bypassed it. Both restriction sources are now unified through '
            '_ignore_distance_build_restricted()/_restricted_build_fallback_towns(), 思想家 got '
            'the printed inner_fallback_range=1 clause its sibling 組織經驗甲 already had, and '
            'the fallback honours build_range_bonus / 安全屋 (1 step, or 2 with a '
            'distance-extending ability). Outer-wall ignore-distance builds remain unaffected; '
            'players outside the era\'s target_camp are unaffected.'
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
        '# 無視距離建立牆內組織的限制驗證（S2 陣營能力 + S3 時代關卡）\n\n'
        '可重跑指令：`python3 scripts/validate/validate_xinjiang_distance_restriction.py`\n\n'
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
