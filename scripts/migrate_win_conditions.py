# -*- coding: utf-8 -*-
"""A1 資料轉換：把 45 個 text-only 陣營的 win_condition_text 轉成結構化 win_conditions。

保留原 win_condition_text 供對照；每一條一般形式都做「往返檢查」——由結構化資料
重建原句並逐字比對，任何不一致直接失敗，確保零失真。特殊案例（宛、朝鮮）為
明確硬編碼並記錄依據。可重複執行（已有 win_conditions 的陣營跳過）。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACTIONS = ROOT / 'data' / 'factions' / 'all_faction.integrated.v2.json'
MAP = ROOT / 'data' / 'map.json'

RE_COUNT_ONLY = re.compile(r'^回合結束時在牆內擁有至少(\d+)個有效組織。$')
RE_WITH_REQUIRED = re.compile(r'^回合結束時在(牆內與牆外共|牆內)擁有至少(\d+)個有效組織，其中必須包含(.+)。$')

# 特殊案例（依 2026-07-11 A1 作業紀錄）：
# - wan（宛）：「全宛地」＝主地圖南陽＋宛擴充地圖城鎮；目前地圖僅有南陽，
#   以自訂 scope '宛地' 表達，_count_scope 對應為 {南陽} ∪ 未來的宛地圖城鎮。
# - chaoxian（朝鮮）：牆內12含延邊，「並且在平壤或首爾擁有組織」→ required_any_of。
SPECIAL = {
    'wan': [{
        'type': 'count_only',
        'scope': '宛地',
        'count': 14,
        'note': '全宛地＝主地圖南陽＋宛地圖城鎮（宛地圖尚未建模，目前僅計南陽）',
    }],
    'chaoxian': [{
        'type': 'count_and_required',
        'scope': '牆內',
        'count': 12,
        'required_locations': ['延邊'],
        'required_any_of': [['平壤', '首爾']],
    }],
}


def rebuild_text(cond):
    scope = cond['scope']
    scope_text = '牆內與牆外共' if scope == '牆內與牆外' else scope
    base = f"回合結束時在{scope_text}擁有至少{cond['count']}個有效組織"
    if cond.get('required_locations'):
        return f"{base}，其中必須包含{'、'.join(cond['required_locations'])}。"
    return f"{base}。"


def main():
    towns = set(json.load(open(MAP, encoding='utf-8'))['towns'])
    data = json.load(open(FACTIONS, encoding='utf-8'))
    converted, skipped, failures = [], [], []
    for f in data['factions']:
        if f.get('win_conditions'):
            skipped.append(f['id'])
            continue
        text = (f.get('win_condition_text') or '').strip()
        fid = f['id']
        if fid in SPECIAL:
            f['win_conditions'] = SPECIAL[fid]
            converted.append((fid, 'special'))
            continue
        m = RE_COUNT_ONLY.match(text)
        if m:
            cond = {'type': 'count_only', 'scope': '牆內', 'count': int(m.group(1))}
            if rebuild_text(cond) != text:
                failures.append((fid, 'roundtrip', text))
                continue
            f['win_conditions'] = [cond]
            converted.append((fid, 'count_only'))
            continue
        m = RE_WITH_REQUIRED.match(text)
        if m:
            scope = '牆內與牆外' if m.group(1) == '牆內與牆外共' else '牆內'
            required = [x.strip() for x in m.group(2 + 1).split('、')]
            unknown = [t for t in required if t not in towns]
            if unknown:
                failures.append((fid, f'unknown towns {unknown}', text))
                continue
            cond = {'type': 'count_and_required', 'scope': scope, 'count': int(m.group(2)), 'required_locations': required}
            if rebuild_text(cond) != text:
                failures.append((fid, 'roundtrip', text))
                continue
            f['win_conditions'] = [cond]
            converted.append((fid, 'count_and_required'))
            continue
        failures.append((fid, 'unparsed', text))

    if failures:
        for item in failures:
            print('FAIL:', item)
        return 1
    json.dump(data, open(FACTIONS, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(FACTIONS, 'a', encoding='utf-8').write('\n')
    print(json.dumps({
        'converted': len(converted),
        'skipped_already_structured': len(skipped),
        'by_kind': {k: sum(1 for _, kind in converted if kind == k) for k in {'count_only', 'count_and_required', 'special'}},
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
