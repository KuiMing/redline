import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'rules-audit'
sys.path.insert(0, str(ROOT))

from server.game import Game, GamePhase


def _new_game(faction_id, partner='red_army'):
    g = Game([('p1', 'P'), ('p2', 'Q')])
    a, b = g.players
    a.faction_id = faction_id
    b.faction_id = partner
    a.organizations = {}
    b.organizations = {}
    g.winner = None
    g.co_winners = []
    g.game_phase = GamePhase.MAIN
    return g, a, b


def _inner(g, n, exclude=()):
    towns = [t for t in sorted(g.towns_by_ruler.get('紅軍', [])) if t not in exclude]
    return towns[:n]


def case_all_factions_structured():
    g, a, b = _new_game('liberals')
    missing = [f['id'] for f in g.factions if not f.get('win_conditions')]
    checks = {'all_60_factions_have_win_conditions': missing == [] and len(g.factions) == 60}
    return {'name': 'all_factions_have_structured_conditions', 'missing': missing, 'checks': checks, 'ok': all(checks.values())}


def case_count_only_inner():
    g, a, b = _new_game('liberals')  # 牆內 >= 14
    a.organizations = {t: 1 for t in _inner(g, 13)}
    g._check_victory()
    not_yet = g.winner is None
    a.organizations = {t: 1 for t in _inner(g, 14)}
    g._check_victory()
    checks = {'thirteen_not_enough': not_yet, 'fourteen_wins': g.winner == 'P'}
    return {'name': 'count_only_inner_liberals_14', 'checks': checks, 'ok': all(checks.values())}


def case_outer_orgs_do_not_count_for_inner_scope():
    g, a, b = _new_game('falun_gong')  # 牆內 >= 14；法輪功根據地紐約（牆外）
    a.organizations = {t: 1 for t in _inner(g, 13)}
    a.organizations['紐約'] = 1  # 牆外，不應計入
    g._check_victory()
    checks = {'thirteen_inner_plus_outer_not_win': g.winner is None}
    return {'name': 'outer_orgs_excluded_from_inner_scope', 'checks': checks, 'ok': all(checks.values())}


def case_count_and_required_yue():
    g, a, b = _new_game('yue')  # 牆內外 >= 11 必含廣州/深圳/湛茂
    required = ['廣州', '深圳', '湛茂']
    filler = _inner(g, 8, exclude=set(required))
    a.organizations = {t: 1 for t in required[:2] + filler}  # 10個、缺湛茂
    a.organizations['倫敦'] = 1  # 湊到11但仍缺必含
    g._check_victory()
    missing_required_blocked = g.winner is None
    a.organizations = {t: 1 for t in required + filler}  # 11個含全部必含
    g._check_victory()
    checks = {
        'missing_required_town_blocks_win': missing_required_blocked,
        'eleven_with_required_wins': g.winner == 'P',
    }
    return {'name': 'count_and_required_yue', 'checks': checks, 'ok': all(checks.values())}


def case_chaoxian_any_of():
    results = {}
    for extra, expect in (('平壤', True), ('首爾', True), (None, False)):
        g, a, b = _new_game('chaoxian')  # 牆內12含延邊＋（平壤或首爾）
        inner = ['延邊'] + _inner(g, 11, exclude={'延邊'})
        a.organizations = {t: 1 for t in inner}
        if extra:
            a.organizations[extra] = 1
        g._check_victory()
        results[extra or 'neither'] = g.winner
    checks = {
        'pyongyang_branch_wins': results['平壤'] == 'P',
        'seoul_branch_wins': results['首爾'] == 'P',
        'neither_blocks_win': results['neither'] is None,
    }
    return {'name': 'chaoxian_required_any_of', 'results': results, 'checks': checks, 'ok': all(checks.values())}


def case_wan_region_scope():
    g, a, b = _new_game('wan')  # 全宛地14；宛擴充地圖尚未建模，必須fail-closed
    a.organizations = {t: 1 for t in _inner(g, 14, exclude={'南陽'})}
    g._check_victory()
    spread_no_win = g.winner is None
    a.organizations = {'南陽': 14}  # 非法疊放也只能視為1個有效城鎮
    g._check_victory()
    checks = {
        'orgs_outside_wan_do_not_count': spread_no_win,
        'stacked_nanyang_fails_closed': g.winner is None,
        'nanyang_counts_as_one_effective_town': g.victory_engine._count_scope(a, '宛地', g) == 1,
    }
    return {'name': 'wan_region_scope_fails_closed_until_expansion_map_exists', 'checks': checks, 'ok': all(checks.values())}


def case_co_winner_for_text_faction():
    g = Game([('p1', 'W'), ('p2', 'C'), ('p3', 'R')])
    w, c, r = g.players
    w.faction_id = 'liberals'
    c.faction_id = 'minyun'  # 同為 text-only（牆內14），現在有結構化條件 → 可當共同勝利者
    r.faction_id = 'red_army'
    for p in g.players:
        p.organizations = {}
    g.winner = None
    g.co_winners = []
    g.game_phase = GamePhase.MAIN
    inner = sorted(g.towns_by_ruler.get('紅軍', []))
    w.organizations = {t: 1 for t in inner[:14]}
    c.organizations = {t: 1 for t in inner[20:30]}  # 10/14 >= 2/3
    g._check_victory()
    checks = {'winner': g.winner == 'W', 'text_faction_co_winner': g.co_winners == ['C']}
    return {'name': 'co_winner_now_works_for_text_factions', 'checks': checks, 'ok': all(checks.values())}


def main():
    results = [
        case_all_factions_structured(),
        case_count_only_inner(),
        case_outer_orgs_do_not_count_for_inner_scope(),
        case_count_and_required_yue(),
        case_chaoxian_any_of(),
        case_wan_region_scope(),
        case_co_winner_for_text_faction(),
    ]
    summary = {
        'scope': ['A1：45個 text-only 陣營勝利條件'],
        'purpose': (
            'A1: 45 factions had only free-text win_condition_text which no code ever read, '
            'so they could never win. All 45 are now structured (9 count_only 牆內14; 34 '
            'count_and_required with required towns, incl. republican\'s inner-scope variant; '
            '2 specials — wan\'s 宛地 region scope [fails closed with main-map 南陽 counting as one '
            'effective town until the 宛 sub-map is modeled] and chaoxian\'s required_any_of 平壤/首爾). Migration used exact '
            'text-roundtrip verification (rebuild sentence from structure, byte-compare). '
            'victory.py gained required_any_of and the 宛地 scope; co-winner progress (A4) '
            'automatically covers these factions now.'
        ),
        'total': len(results),
        'passed': sum(1 for r in results if r['ok']),
        'failed': sum(1 for r in results if not r['ok']),
    }
    payload = {'summary': summary, 'results': results}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RECORD_DIR / 'TEXT_FACTION_WIN_CONDITIONS_VALIDATION_20260711.json'
    md_path = RECORD_DIR / 'TEXT_FACTION_WIN_CONDITIONS_VALIDATION_20260711.md'
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    md_path.write_text(
        '# 45 個 text-only 陣營勝利條件實作驗證（A1）\n\n'
        '可重跑指令：`python3 scripts/validate/validate_text_faction_win_conditions.py`\n\n'
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
