import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase, ANTI_COMMUNIST_ORG_SUPPLY, RED_ARMY_ORG_SUPPLY


def _new_game(faction_id='liberals', partner='red_army'):
    g = Game([('p1', 'A'), ('p2', 'B')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = partner
    a.organizations = {}
    b.organizations = {}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    return g, a, b


def case_anti_communist_limit_22():
    g, a, b = _new_game('liberals')
    a.organizations = {'北京': ANTI_COMMUNIST_ORG_SUPPLY - 1}  # 21
    ok_at_21 = g.build_organization('北京')
    blocked_at_22 = g.build_organization('北京')
    checks = {
        'constant_is_22': ANTI_COMMUNIST_ORG_SUPPLY == 22,
        'build_allowed_at_21': ok_at_21.get('success') is True and a.total_organizations() == 22,
        'build_blocked_at_22': '組織棋已達上限' in str(blocked_at_22.get('error')),
        'total_stays_22': a.total_organizations() == 22,
    }
    return {'name': 'anti_communist_limit_22', 'blocked': blocked_at_22, 'checks': checks, 'ok': all(checks.values())}


def case_red_army_limit_40():
    g, a, b = _new_game('red_army', partner='liberals')
    a.organizations = {'北京': 25}  # 超過 22，證明紅軍上限不是 22
    ok_past_22 = g.build_organization('北京')
    a.organizations = {'北京': RED_ARMY_ORG_SUPPLY - 1}  # 39
    ok_at_39 = g.build_organization('北京')
    blocked_at_40 = g.build_organization('北京')
    checks = {
        'constant_is_40': RED_ARMY_ORG_SUPPLY == 40,
        'red_can_build_past_22': ok_past_22.get('success') is True,
        'build_allowed_at_39': ok_at_39.get('success') is True and a.total_organizations() == 40,
        'build_blocked_at_40': '組織棋已達上限（40）' in str(blocked_at_40.get('error')),
    }
    return {'name': 'red_army_limit_40_user_decision', 'blocked': blocked_at_40, 'checks': checks, 'ok': all(checks.values())}


def case_dissolve_frees_supply():
    g, a, b = _new_game('liberals')
    a.organizations = {'北京': ANTI_COMMUNIST_ORG_SUPPLY}
    blocked = g.build_organization('北京')
    a.organizations['北京'] -= 1  # 模擬被瓦解 1 個
    allowed = g.build_organization('北京')
    checks = {
        'blocked_at_limit': '組織棋已達上限' in str(blocked.get('error')),
        'allowed_after_dissolve': allowed.get('success') is True,
    }
    return {'name': 'dissolve_frees_supply', 'checks': checks, 'ok': all(checks.values())}


def case_ui_eligibility_gate():
    g, a, b = _new_game('liberals')
    a.organizations = {'北京': ANTI_COMMUNIST_ORG_SUPPLY}
    at_limit = g.can_develop_in_town(a, '上海')
    a.organizations = {'北京': ANTI_COMMUNIST_ORG_SUPPLY - 1}
    below_limit = g.can_develop_in_town(a, '上海')
    checks = {
        'develop_gate_false_at_limit': at_limit is False,
        'develop_gate_true_below_limit': below_limit is True,
    }
    return {'name': 'ui_eligibility_gate_via_can_develop', 'checks': checks, 'ok': all(checks.values())}


def case_shared_org_move_consumes_supply():
    # taiwan_green 可與 underground_church 共用組織；移動共享組織會把組織轉為移動者所有（總數+1）
    g, a, b = _new_game('taiwan_green', partner='underground_church')
    b.organizations = {'臺北': 1}
    a.moves_left = 2
    a.organizations = {'高雄': ANTI_COMMUNIST_ORG_SUPPLY}  # 滿編
    blocked = g.move_organization('臺北', '基隆', mode='rail')
    a.organizations = {'高雄': ANTI_COMMUNIST_ORG_SUPPLY - 1}
    allowed = g.move_organization('臺北', '基隆', mode='rail')
    checks = {
        'shared_move_blocked_at_limit': '組織棋已達上限' in str(blocked.get('error')),
        'shared_move_allowed_below_limit': allowed.get('success') is True,
        'total_after_transfer_at_limit': a.total_organizations() == ANTI_COMMUNIST_ORG_SUPPLY,
    }
    return {'name': 'shared_org_move_consumes_supply', 'blocked': blocked, 'checks': checks, 'ok': all(checks.values())}


def case_own_move_free_at_limit():
    g, a, b = _new_game('taiwan_green', partner='red_army')
    a.moves_left = 1
    a.organizations = {'臺北': ANTI_COMMUNIST_ORG_SUPPLY - 1, '高雄': 1}  # 滿編 22，含臺北
    result = g.move_organization('臺北', '基隆', mode='rail')
    checks = {
        'own_move_allowed_at_limit': result.get('success') is True,  # 淨變化 0，不消耗供應
        'total_unchanged': a.total_organizations() == ANTI_COMMUNIST_ORG_SUPPLY,
    }
    return {'name': 'own_org_move_free_at_limit', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_anti_communist_limit_22(),
        case_red_army_limit_40(),
        case_dissolve_frees_supply(),
        case_ui_eligibility_gate(),
        case_shared_org_move_consumes_supply(),
        case_own_move_free_at_limit(),
    ]
    summary = {
        'scope': ['organization supply limits (S1)'],
        'purpose': (
            'S1 (second-pass audit): rules.md step 4 fixes each anti-communist faction at 22 '
            'organization pieces as the hard build maximum; no limit existed anywhere in code. '
            'Red Army limit is a flat 40 per user decision on 2026-07-11 (rulebook formula is '
            '8×players +8 with Taiwan; deliberately overridden). Enforcement lives in '
            'can_develop_in_town (single funnel for every build path and UI eligibility list), '
            'with clear error messages in build_organization, plus a supply check when moving '
            'a shared organization owned by another player (ownership transfer = net +1). '
            'Own-org moves and dissolves are unaffected; dissolving frees supply.'
        ),
        'anti_communist_limit': ANTI_COMMUNIST_ORG_SUPPLY,
        'red_army_limit': RED_ARMY_ORG_SUPPLY,
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'ORG_SUPPLY_LIMITS_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'ORG_SUPPLY_LIMITS_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 組織棋供應上限驗證（S1）\n\n'
        '可重跑指令：`python3 scripts/validate_org_supply_limits.py`\n\n'
        f"- 反共陣營上限: {ANTI_COMMUNIST_ORG_SUPPLY}\n"
        f"- 紅軍上限: {RED_ARMY_ORG_SUPPLY}（2026-07-11 使用者決定，取代規則書 8×N+8 公式）\n"
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
