"""Pure support-card taxonomy/effect-resolution rules (catalog reads only,
no Game mutation).

Support card *interaction*/*execution* (`_execute_support_card`,
`_start_support_interaction`, `_resolve_support_interaction_result`, and
everything that creates/resolves a pending_choice for an interactive
support effect) stays in `game.py` — those mutate turn_log/pending_choice/
player state, unlike everything here.

`_support_card_tier` / `_player_ruler_organization_counts` /
`_player_ruler_leadership` also stay in `game.py`: they depend on
`Game._organization_towns_for_player`, which wasn't verified pure in this
pass (same reasoning as the era-rules extraction in PR #109 leaving
`_evaluate_era_trigger` behind).
"""

from server.cards import Card


def support_taxonomy_entry(support_taxonomy, card_name):
    for entry in support_taxonomy:
        if entry.get("name") == card_name:
            return entry
    return None


def is_starter_support_card(support_taxonomy, support_name):
    entry = support_taxonomy_entry(support_taxonomy, support_name) or {}
    return entry.get('cost') == '起始牌'


def support_card_runtime_type(name):
    mapping = {
        '英美奧援': 'support',
        '東洋奧援': 'support',
        '南洋奧援': 'support',
        '印度奧援': 'support',
        '天方奧援': 'support',
        '歐洲奧援': 'support',
        '北國奧援': 'support',
        '臺灣奧援': 'support',
        '紅軍奧援': 'support',
    }
    return mapping.get(name, 'support')


def is_support_card(support_taxonomy, card):
    card_name = getattr(card, "name", str(card))
    return support_taxonomy_entry(support_taxonomy, card_name) is not None


def is_india_flag_card(support_taxonomy, card):
    entry = support_taxonomy_entry(support_taxonomy, getattr(card, "name", str(card)))
    if entry is not None:
        return bool(entry.get("counts_as_flag_card"))
    return False


def support_card_variant_info(support_taxonomy, card):
    """Which II 級門檻地區這張特定奧援卡實體印的是哪一組，供前端顯示這張牌實際印的
    那組地區（而不是同名卡另一種變體的地區）。非奧援卡回傳 None。"""
    card_name = getattr(card, "name", str(card))
    entry = support_taxonomy_entry(support_taxonomy, card_name)
    if not entry:
        return None
    regions = entry.get("regions", []) or []
    if not regions:
        return None
    variant_index = getattr(card, "variant_index", 0) or 0
    if variant_index >= len(regions):
        variant_index = 0
    region = regions[variant_index]
    return {
        "variant_index": variant_index,
        "support_region": entry.get("support_region"),
        "tier2_regions": list(region.get("preferred_rulers", []) or []),
    }


def support_card_effect_text(support_taxonomy, card_name, tier, region_index):
    entry = support_taxonomy_entry(support_taxonomy, card_name)
    if not entry:
        return None
    regions = entry.get('regions', []) or []
    if region_index is None or region_index >= len(regions):
        return None
    region_entry = regions[region_index]
    if tier >= 3:
        return region_entry.get('tier_3')
    if tier == 2:
        return region_entry.get('tier_2') or region_entry.get('tier_3')
    return region_entry.get('tier_1')


def resolve_support_card_effect(support_taxonomy, card_name, tier, region_index):
    if card_name == '紅軍奧援':
        return 'red_support_draw_and_pass', {'draw': 1}
    text = support_card_effect_text(support_taxonomy, card_name, tier, region_index)
    if not text:
        return None, None

    if card_name == '印度奧援':
        count = 3 if tier >= 3 else 2 if tier == 2 else 1
        return 'add_internal_conflict', {'count': count, 'target': 'red_army'}
    if card_name == '英美奧援':
        amount = 3 if tier >= 3 else 2 if tier == 2 else 1
        return 'gain_resource', {'money': amount}
    if card_name == '歐洲奧援':
        amount = 4 if tier >= 3 else 3 if tier == 2 else 2
        return 'gain_resource', {'propaganda': amount}
    if card_name == '南洋奧援':
        if tier >= 3:
            return 'draw', {'count': 2}
        if tier == 2:
            return 'draw', {'count': 1}
        return 'draw_then_discard', {'draw': 1, 'discard': 1}
    if card_name == '東洋奧援':
        if tier >= 3:
            return 'interactive_build_anywhere_inner', {'count': 1}
        if tier == 2:
            return 'interactive_build_near_inner', {'count': 1}
        return 'gain_resource', {'propaganda': 2}
    if card_name == '北國奧援':
        if tier >= 3:
            return 'interactive_dissolve_many_near', {'count': 2}
        if tier == 2:
            return 'interactive_dissolve_many_near', {'count': 1}
        return 'interactive_dissolve_self_and_enemy', {'count': 1}
    if card_name == '臺灣奧援':
        if tier >= 3:
            return 'interactive_dissolve_and_build', {'count': 1}
        if tier == 2:
            return 'interactive_dissolve_many_near', {'count': 1}
        return 'gain_resource', {'propaganda': 1}
    if card_name == '天方奧援':
        if tier >= 3:
            return 'force_discard_near', {'count': 2, 'random': True}
        if tier == 2:
            return 'force_discard_near', {'count': 1, 'random': True}
        return 'force_discard_near', {'count': 1, 'random': False}
    if card_name == '紅軍奧援':
        return 'red_support_draw_and_pass', {'draw': 1}
    return 'text_only', {'text': text}


def make_support_card(support_taxonomy, support_name, variant_index=0):
    entry = support_taxonomy_entry(support_taxonomy, support_name) or {}
    # 普通奧援沒有資源模式印刷產出；紅軍奧援是 canonical 明載的唯一例外：
    # 它是零購買費用的起始牌，但可作為資源取得 1資金＋1宣傳。兩者不可混用。
    printed_resources = {'money': 1, 'propaganda': 1} if support_name == '紅軍奧援' else {}
    card = Card(
        support_name,
        support_card_runtime_type(support_name),
        printed_resources,
        effect={'support_taxonomy': entry},
    )
    # 每種奧援卡實體上印有兩種不同的 II 級門檻地區組合（見 support_cards.csv 兩列），
    # 一張實體卡只印其中一組；variant_index 記住這張牌抽到的是哪一組，讓 _support_card_tier
    # 只檢查該卡實際印刷的那組地區，而不是把兩組地區都算進同一張牌（2026-07-16 使用者裁決）。
    card.variant_index = variant_index
    return card
