import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, TurnPhase


def _new_game():
    g = Game([('p1', 'HK'), ('p2', 'R')])
    hk, red = g.players
    hk.faction_id = 'hong_kong'
    red.faction_id = 'red_army'
    hk.base = '香港城'
    hk.organizations = {'香港城': 1}
    red.organizations = {}
    g.turn_phase = TurnPhase.ACTION
    g.current_player_index = 0
    g.turn_log = g._new_turn_log()
    g.pending_choice = None
    g.hk_free_base_relocation = False
    return g, hk, red


def case_free_window_after_event_settlement():
    g, hk, red = _new_game()
    g.current_event = {'name': '香港抗暴之戰', 'type': 'mission', 'success': {'type': 'none'}, 'failure': {'type': 'none'}}
    g.event_progress = {'count': 0, 'required': 1, 'succeeded': False, 'settled': False, 'status': 'active'}
    g._settle_current_event()  # 失敗結算也算「完成結算」
    window_open = g.hk_free_base_relocation is True
    hk.moves_left = 0  # 免費：不需要移動點
    result = g.relocate_hong_kong_base(hk.id, '倫敦')
    checks = {
        'window_opens_on_settlement_even_on_failure': window_open,
        'free_relocation_succeeds_without_moves': result.get('success') is True and result.get('free') is True,
        'base_moved': hk.base == '倫敦' and hk.organizations.get('倫敦', 0) == 1 and hk.organizations.get('香港城', 0) == 0,
        'window_consumed': g.hk_free_base_relocation is False,
        'state_exposes_window': 'hk_free_base_relocation' in g.state(),
    }
    return {'name': 'free_window_after_event_settlement', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_window_closes_at_next_round():
    g, hk, red = _new_game()
    g.hk_free_base_relocation = True
    g._start_event_phase()  # 新回合事件階段開始 → 窗口關閉
    hk.moves_left = 0
    result = g.relocate_hong_kong_base(hk.id, '倫敦')
    checks = {
        'window_closed': g.hk_free_base_relocation is False,
        'no_free_relocation_after_close': result.get('error') is not None,
    }
    return {'name': 'window_closes_when_next_round_starts', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_airport_is_not_paid_base_relocation():
    g, hk, red = _new_game()
    hk.moves_left = 2
    result = g.relocate_hong_kong_base(hk.id, '臺北')
    checks = {
        'relocation_blocked_without_event_window': '香港抗暴之戰尚未完成結算' in str(result.get('error')),
        'moves_not_spent': hk.moves_left == 2,
        'base_unchanged': hk.base == '香港城' and hk.organizations.get('香港城', 0) == 1,
    }
    return {'name': 'airport_is_not_paid_base_relocation', 'result': result, 'checks': checks, 'ok': all(checks.values())}


def case_restrictions():
    g, hk, red = _new_game()
    g.hk_free_base_relocation = True
    bad_target = g.relocate_hong_kong_base(hk.id, '曼谷')
    red.organizations = {'倫敦': 1}
    enemy_blocked = g.relocate_hong_kong_base(hk.id, '倫敦')
    g.current_player_index = 1  # 免費前移窗口不要求輪到香港
    out_of_turn_free = g.relocate_hong_kong_base(hk.id, '臺北')
    g2, hk2, red2 = _new_game()
    g2.hk_free_base_relocation = True
    red2_result = g2.relocate_hong_kong_base(red2.id, '臺北')
    checks = {
        'only_four_cities': '根據地只能遷移至' in str(bad_target.get('error')),
        'occupied_destination_blocked': 'occupied town' in str(enemy_blocked.get('error')),
        'free_window_allows_hk_choice_out_of_turn': out_of_turn_free.get('success') is True,
        'non_hk_faction_blocked': 'Only Hong Kong' in str(red2_result.get('error')),
    }
    return {'name': 'relocation_restrictions', 'checks': checks, 'ok': all(checks.values())}


def case_base_anchor_moves_and_new_base_ability():
    g, hk, red = _new_game()
    g.hk_free_base_relocation = True
    g.relocate_hong_kong_base(hk.id, '倫敦')
    has_intl = g._player_has_ability(hk, '國際線')  # 倫敦根據地能力
    checks = {
        'new_base_ability_active': has_intl is True,
        'anchor_cannot_move_from_new_base': g.move_organization('倫敦', '臺北', mode='road').get('error') is not None,
    }
    return {'name': 'base_anchor_and_base_ability_follow_relocation', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_free_window_after_event_settlement(),
        case_window_closes_at_next_round(),
        case_airport_is_not_paid_base_relocation(),
        case_restrictions(),
        case_base_anchor_moves_and_new_base_ability(),
    ]
    summary = {
        'scope': ['香港根據地遷移（S5-1 + 機場根據地用途）'],
        'purpose': (
            'Event card 香港抗暴之戰 opens a one-time free base-forward window after settlement '
            '(success or failure). Hong Kong may move its base to 臺北/倫敦/卡加利/多倫多 '
            'before the next round begins, or keep the current base and consume the window. '
            'The separate 赤鱲角 airport rule moves a Hong Kong organization for 2 migrations; '
            'it is not a paid base-relocation method. The base anchor organization moves with '
            'the base, the new base ability activates, and occupied destinations are blocked.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'HK_BASE_RELOCATION_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'HK_BASE_RELOCATION_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 香港根據地遷移驗證（S5-1＋機場根據地用途）\n\n'
        '可重跑指令：`python3 scripts/validate_hk_base_relocation.py`\n\n'
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
