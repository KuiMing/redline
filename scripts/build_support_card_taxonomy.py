import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPPORT_PATH = ROOT / 'data' / 'cards' / 'support_cards.v1.1.json'
OUT_JSON = ROOT / 'data' / 'cards' / 'support_taxonomy.v1.1.json'
OUT_MD = ROOT / 'docs' / 'records' / 'support-cards' / 'SUPPORT_CARD_TAXONOMY.md'

REGION_NAME_TO_ID = {
    '英美': 'anglo_support',
    '東洋': 'east_asia_support',
    '南洋': 'southeast_asia_support',
    '印度': 'india_support',
    '天方': 'middle_east_support',
    '歐洲': 'europe_support',
    '北國': 'northland_support',
    '臺灣': 'taiwan_support',
    '紅軍': 'red_army_support',
}

EFFECT_KIND = {
    '獲得': 'gain_resource',
    '抽': 'draw',
    '將': 'disruption_or_dissolve',
    '瓦解': 'dissolve',
    '在牆內': 'build',
    '選擇有組織位在己方組織1格內的玩家': 'discard',
}


def infer_effect_bucket(text):
    if not text or text == '未滿足任何條件':
        return 'none'
    for key, value in EFFECT_KIND.items():
        if key in text:
            return value
    return 'unknown'


def main():
    rows = json.loads(SUPPORT_PATH.read_text(encoding='utf-8'))
    grouped = {}

    for row in rows:
        name = row.get('奧援卡名稱')
        entry = grouped.setdefault(name, {
            'name': name,
            'cost': row.get('購買費用'),
            'copies': row.get('卡牌張數'),
            'regions': [],
            'support_card': True,
            'support_region': name.replace('奧援', ''),
            'counts_as_flag_card': name == '印度奧援',
            'effects': [],
        })
        regions = [x.strip() for x in (row.get('區域主導者優待') or '').split('、') if x.strip()]
        entry['regions'].append({
            'preferred_rulers': regions,
            'preferred_ruler_ids': [REGION_NAME_TO_ID.get(x, x) for x in regions],
            'tier_3': row.get('III級效果'),
            'tier_2': row.get('II級效果'),
            'tier_1': row.get('I級效果'),
        })
        entry['effects'].append({
            'tier_3_kind': infer_effect_bucket(row.get('III級效果')),
            'tier_2_kind': infer_effect_bucket(row.get('II級效果')),
            'tier_1_kind': infer_effect_bucket(row.get('I級效果')),
        })

    payload = {
        'source': str(SUPPORT_PATH.relative_to(ROOT)),
        'cards': list(grouped.values()),
        'notes': [
            'This taxonomy is a normalization layer derived from support_cards.v1.1.json.',
            'counts_as_flag_card is currently only asserted for 印度奧援, to support 印度研究分析室 without overgeneralizing unrelated support cards.',
            'preferred_ruler_ids are normalized placeholders for later runtime integration.',
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    lines = [
        '# SUPPORT CARD TAXONOMY',
        '',
        f'- source: `{SUPPORT_PATH.relative_to(ROOT)}`',
        '',
    ]
    for card in payload['cards']:
        lines.append(f"## {card['name']}")
        lines.append('')
        lines.append(f"- cost: {card['cost']}")
        lines.append(f"- copies: {card['copies']}")
        lines.append(f"- counts_as_flag_card: {card['counts_as_flag_card']}")
        for idx, region in enumerate(card['regions'], 1):
            lines.append(f"- region variant {idx}: {', '.join(region['preferred_rulers']) or '無'}")
            lines.append(f"  - III: {region['tier_3']}")
            lines.append(f"  - II: {region['tier_2']}")
            lines.append(f"  - I: {region['tier_1']}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'summary': {'total': len(payload['cards'])}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
