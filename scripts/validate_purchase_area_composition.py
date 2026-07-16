#!/usr/bin/env python3
"""C3: data-consistency validation of the purchase-area composition.

Hard checks (must pass) pin the data pipeline and the CURRENT implementation:
  - static purchase area = exactly the 6 fixed cards, supplies matching data/raw CSV
  - starter cards exist only in the CSV (by design) and never enter the purchase deck
  - structured action-card JSON covers exactly the CSV's non-starter cards
  - support taxonomy covers exactly the support CSV's card names
  - runtime deck composition matches what the current code intends per market mode

Known deviations from rules.md 步驟⑧ are REPORTED (not failed) so the numbers stay
visible without permanently red-flagging deliberate MVP choices; see the report block.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'purchase'
sys.path.insert(0, str(ROOT))

from server.game import Game, STATIC_PURCHASE_CARD_SUPPLY

ACTION_CSV = ROOT / 'data' / 'raw' / 'action_cards.csv'
SUPPORT_CSV = ROOT / 'data' / 'raw' / 'support_cards.csv'
STRUCTURED_JSON = ROOT / 'data' / 'action_cards_structured.v1.1.json'
TAXONOMY_JSON = ROOT / 'data' / 'cards' / 'support_taxonomy.v1.1.json'

RULEBOOK_SUPPORT_SAMPLE = 18
RULEBOOK_GENERAL_SAMPLE = 35
MANDATORY_KINDS = ('間諜', '組織', '整肅')


def load_action_csv():
    rows = [r for r in csv.DictReader(open(ACTION_CSV, encoding='utf-8')) if r.get('行動卡名稱')]
    return {
        r['行動卡名稱']: {
            'copies': int(r.get('卡牌張數') or 0),
            'kind': r.get('種類'),
            'position': r.get('位置'),
        }
        for r in rows
    }


def load_support_csv():
    per = {}
    for r in csv.DictReader(open(SUPPORT_CSV, encoding='utf-8')):
        name = r.get('奧援卡名稱')
        if name:
            per.setdefault(name, []).append(int(r.get('卡牌張數') or 0))
    return per


def load_structured_names():
    data = json.load(open(STRUCTURED_JSON, encoding='utf-8'))
    cards = data['cards'] if isinstance(data, dict) and 'cards' in data else data
    if isinstance(cards, dict):
        cards = list(cards.values())
    return {c['name']: c for c in cards}


def load_taxonomy():
    data = json.load(open(TAXONOMY_JSON, encoding='utf-8'))
    entries = data['cards'] if isinstance(data, dict) and 'cards' in data else data
    if isinstance(entries, dict):
        entries = list(entries.values())
    return {e.get('name'): e for e in entries if e.get('name')}


def deck_names(game):
    return [getattr(c, 'name', str(c)) for c in game.purchase_deck.draw_pile] + [
        getattr(c, 'name', str(c)) for c in game.purchase_deck.discard_pile
    ]


def main():
    csv_cards = load_action_csv()
    support_rows = load_support_csv()
    structured = load_structured_names()
    taxonomy = load_taxonomy()

    checks = []

    def check(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # --- 1. Static purchase area & supplies vs CSV ---
    static_positions = {'常設購買區', '常設購買區（可視為起始牌）'}
    csv_static = {n: v['copies'] for n, v in csv_cards.items() if v['position'] in static_positions}
    check(
        'static_supply_matches_csv',
        dict(STATIC_PURCHASE_CARD_SUPPLY) == csv_static,
        {'code': dict(STATIC_PURCHASE_CARD_SUPPLY), 'csv': csv_static},
    )
    game = Game([('p1', 'a'), ('p2', 'b')])
    static_names = [getattr(c, 'name', str(c)) for c in game._static_purchase_cards()]
    check(
        'static_area_is_exactly_the_six_fixed_cards',
        static_names == list(STATIC_PURCHASE_CARD_SUPPLY),
        {'runtime': static_names},
    )

    # --- 2. Starters stay out of the purchase deck (by design they are CSV-only) ---
    csv_starters = {n for n, v in csv_cards.items() if v['position'] == '起始牌'}
    check(
        'starters_are_csv_only',
        csv_starters == {'追隨者', '樂捐者'} and not (csv_starters & set(structured)),
        {'csv_starters': sorted(csv_starters)},
    )

    # --- 3. Structured JSON covers exactly the CSV non-starter cards ---
    expected_structured = set(csv_cards) - csv_starters
    check(
        'structured_json_matches_csv_nonstarters',
        set(structured) == expected_structured,
        {
            'missing_in_json': sorted(expected_structured - set(structured)),
            'extra_in_json': sorted(set(structured) - expected_structured),
        },
    )

    # --- 4. Support taxonomy names match the support CSV ---
    check(
        'taxonomy_names_match_support_csv',
        set(taxonomy) == set(support_rows),
        {'taxonomy_only': sorted(set(taxonomy) - set(support_rows)), 'csv_only': sorted(set(support_rows) - set(taxonomy))},
    )

    # --- 5. Runtime composition per market mode matches the current implementation ---
    support_names = set(taxonomy)
    non_starter_support = {n for n in support_names if (taxonomy[n] or {}).get('cost') != '起始牌'}
    support_pool_size = sum(int((taxonomy[n] or {}).get('copies') or 0) for n in non_starter_support)
    general_names = expected_structured - set(STATIC_PURCHASE_CARD_SUPPLY)
    # structured JSON has no copies field, so the deck builder falls back to 1 per card
    general_pool_size = len(general_names)

    g53 = Game([('p1', 'a'), ('p2', 'b')], market_mode='sample_53')
    names53 = deck_names(g53) + [getattr(c, 'name', str(c)) for c in g53.purchase_area if getattr(c, 'name', str(c)) not in static_names]
    support53 = [n for n in names53 if n in support_names]
    general53 = [n for n in names53 if n in general_names]
    check(
        'sample_53_deck_is_18_support_plus_35_general',
        len(support53) == RULEBOOK_SUPPORT_SAMPLE and len(general53) == RULEBOOK_GENERAL_SAMPLE
        and len(names53) == RULEBOOK_SUPPORT_SAMPLE + RULEBOOK_GENERAL_SAMPLE,
        {'support': len(support53), 'general': len(general53), 'total': len(names53)},
    )
    check(
        'sample_53_deck_has_no_static_or_starter_cards',
        not (set(names53) & set(STATIC_PURCHASE_CARD_SUPPLY)) and not (set(names53) & csv_starters)
        and '紅軍奧援' not in names53,
        {'unexpected': sorted((set(names53) & (set(STATIC_PURCHASE_CARD_SUPPLY) | csv_starters)) | ({'紅軍奧援'} & set(names53)))},
    )

    gall = Game([('p1', 'a'), ('p2', 'b')], market_mode='all_cards')
    names_all = deck_names(gall) + [getattr(c, 'name', str(c)) for c in gall.purchase_area if getattr(c, 'name', str(c)) not in static_names]
    check(
        'all_cards_deck_is_the_full_pool',
        len(names_all) == support_pool_size + general_pool_size,
        {'total': len(names_all), 'expected': support_pool_size + general_pool_size,
         'support_pool': support_pool_size, 'general_pool': general_pool_size},
    )

    # --- 6. Support card physical copy totals: CSV vs taxonomy (2026-07-16 使用者裁決) ---
    # support CSV 每種奧援有兩列，各代表一種實體印刷變體（各印一組不同的 II 級門檻地區），
    # 各 4 張、合計 8 張；taxonomy 的 regions[] 兩個項目對應這兩種變體，且各自帶 copies:4，
    # 加總後的頂層 copies 應與 CSV 兩列相加後的總數一致。這曾被誤記為「需規則書確認的
    # ambiguous deviation」，實際上就是單純的加總，已於 2026-07-16 修正 taxonomy 並改為
    # 強制檢查（原本 taxonomy 頂層 copies 只抄了其中一列的 4，短少一半購買牌庫的奧援卡）。
    support_csv_totals = {n: sum(v) for n, v in support_rows.items()}
    taxonomy_copies = {n: int((taxonomy[n] or {}).get('copies') or 0) for n in taxonomy}
    non_starter_taxonomy_copies = {n: v for n, v in taxonomy_copies.items() if n in non_starter_support}
    non_starter_csv_totals = {n: v for n, v in support_csv_totals.items() if n in non_starter_support}
    check(
        'support_taxonomy_copies_match_csv_row_totals',
        non_starter_taxonomy_copies == non_starter_csv_totals,
        {'csv_totals': non_starter_csv_totals, 'taxonomy': non_starter_taxonomy_copies},
    )

    # --- Informational report: remaining deviations from rules.md 步驟⑧ (not failed) ---
    mandatory_expected = {n: v['copies'] for n, v in csv_cards.items() if v['kind'] in MANDATORY_KINDS}
    mandatory_total = sum(mandatory_expected.values())
    csv_copy_diffs = {
        n: {'csv': v['copies'], 'deck_builder': 1}
        for n, v in csv_cards.items()
        if n in general_names and v['copies'] != 1
    }
    report = {
        'rulebook_step8_expected_deck': f'間諜/組織/整肅全部 {mandatory_total} 張 + 隨機 {RULEBOOK_SUPPORT_SAMPLE} 張奧援 + 隨機 {RULEBOOK_GENERAL_SAMPLE} 張其它一般卡 = {mandatory_total + RULEBOOK_SUPPORT_SAMPLE + RULEBOOK_GENERAL_SAMPLE} 張',
        'deviation_1_market_modes': (
            'sample_53（lobby「53 張核心」選項）＝18 奧援＋35 一般卡，未保證間諜/組織/整肅全數入庫；'
            'all_cards（「全部卡牌」）＝整個 pool。兩種模式都不是規則書步驟⑧的組成——sample_53 為刻意的 MVP 精簡選項。'
        ),
        'deviation_2_structured_json_has_no_copies': (
            'action_cards_structured.v1.1.json 沒有張數欄位，_initial_purchase_deck 對每種一般卡 fallback 為 1 份；'
            'CSV 卡牌張數（如 批判 8、派遣間諜 5）目前不影響牌庫內份數。'
        ),
        'deviation_2_affected_cards': csv_copy_diffs,
        'resolved_2026_07_16_support_copies': {
            'note': '原 deviation_3：support CSV 每種奧援兩列（各一種實體印刷變體、各印一組不同 II 級地區）各 4 張、'
                     '合計 8；taxonomy 曾誤記頂層 copies 為 4（只抄一列）。已修正 taxonomy 讓每個 regions[] 項目各自'
                     '帶 copies:4，頂層加總為 8，且 game.py 的 _support_card_tier 改為只依牌本身的 variant_index 檢查'
                     '該卡印刷的那組地區，不再把兩種變體地區併查。',
            'csv_totals': support_csv_totals,
            'taxonomy': taxonomy_copies,
        },
        'deviation_4_deck_refill': '規則書「牌庫用盡時從剩餘行動卡任取一疊補上」；實作為重建整份 initial deck（近似）。',
        'mandatory_kind_copies_csv': mandatory_expected,
    }

    summary = {
        'scope': ['C3 購買區組成資料校驗'],
        'total': len(checks),
        'passed': sum(1 for c in checks if c['ok']),
        'failed': sum(1 for c in checks if not c['ok']),
    }
    payload = {'summary': summary, 'checks': checks, 'rulebook_deviation_report': report}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    (RECORD_DIR / 'PURCHASE_AREA_COMPOSITION_VALIDATION.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# C3 購買區組成資料校驗',
        '',
        '可重跑指令：`python3 scripts/validate_purchase_area_composition.py`',
        '',
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}",
        '',
        '## Checks（硬性：資料一致性與現行組成行為）',
        '',
    ]
    for c in checks:
        lines.append(f"- {'PASS' if c['ok'] else 'FAIL'} {c['name']}: {json.dumps(c['detail'], ensure_ascii=False)}")
    lines += ['', '## 規則書步驟⑧偏差報告（資訊性，不列失敗）', '']
    for k, v in report.items():
        lines.append(f"- **{k}**: {json.dumps(v, ensure_ascii=False)}")
    lines.append('')
    (RECORD_DIR / 'PURCHASE_AREA_COMPOSITION_VALIDATION.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
