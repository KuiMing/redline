"""Pure purchase-cost calculation rules (catalog/state reads only, no mutation).

Orchestration that also needs shared helpers (active event modifiers, active
era effects, player camp) beyond a card/catalog lookup — e.g. `Game.
_effective_purchase_cost` — stays in `Game` and composes these functions,
since those helpers are used far more broadly than just cost calculation.
"""

import re


def _taxonomy_entry(support_taxonomy, card_name):
    for entry in support_taxonomy:
        if entry.get("name") == card_name:
            return entry
    return None


def support_card_cost(support_taxonomy, support_name):
    entry = _taxonomy_entry(support_taxonomy, support_name) or {}
    text = entry.get('cost', '')
    if text == '起始牌':
        return {'money': 0, 'propaganda': 0}
    money = 0
    propaganda = 0
    if isinstance(text, str):
        m = re.search(r'(\d+)資金', text)
        p = re.search(r'(\d+)宣傳', text)
        money = int(m.group(1)) if m else 0
        propaganda = int(p.group(1)) if p else 0
    return {'money': money, 'propaganda': propaganda}


def card_purchase_cost(structured_cards, support_taxonomy, card):
    card_name = getattr(card, 'name', str(card))
    if getattr(card, "card_type", None) == "support" or getattr(card, "type", None) == "support":
        return support_card_cost(support_taxonomy, card_name)
    for c in structured_cards:
        if c.get('name') == card_name:
            cost = c.get('cost', {}) or {}
            return {
                'money': int(cost.get('money', 0) or 0),
                'propaganda': int(cost.get('propaganda', 0) or 0),
            }
    return {'money': 0, 'propaganda': 0}


def event_reduce_cost_amount(active_event_modifiers):
    return sum(
        int((m or {}).get('amount', 0) or 0)
        for m in active_event_modifiers
        if (m or {}).get('type') == 'reduce_cost'
    )


def armory_purchase_cost_reduction(map_data, card, player_organizations):
    # 2026-08-04 使用者回報規則：玩家在軍火庫城鎮每擁有1個組織，購買每張武裝類卡牌
    # 所需支付的費用減少1點資金，至多可藉軍火庫減少3點資金。「一城一組織」invariant
    # 下每座軍火庫城鎮最多只會計1個組織，因此這裡直接數玩家目前有多少座「不同的」
    # 軍火庫城鎮擁有組織（不是城鎮內組織數，那永遠是0或1），再夾到3點上限。
    if getattr(card, 'card_type', None) != 'armed':
        return 0
    towns = map_data.get('towns', {}) or {}
    armory_towns_owned = sum(
        1
        for town, count in (player_organizations or {}).items()
        if count > 0 and (towns.get(town) or {}).get('type') == '軍火庫'
    )
    return min(3, armory_towns_owned)


def era_purchase_cost_reduction(active_era_effects, player_camp, player_faction_id, card):
    reductions = {'money': 0, 'propaganda': 0}
    for _era, _side, effect in active_era_effects:
        if (effect or {}).get('type') != 'reduce_purchase_cost':
            continue
        target_camp = effect.get('target_camp')
        if target_camp and not (player_camp == target_camp or player_faction_id == target_camp):
            continue
        card_types = effect.get('card_types') or []
        if card_types and getattr(card, 'card_type', None) not in set(card_types):
            continue
        resource = effect.get('resource', 'money')
        if resource not in reductions:
            continue
        reductions[resource] += int(effect.get('amount', 0) or 0)
    return reductions


def purchase_area_card_cost_total(structured_cards, support_taxonomy, card):
    card_name = getattr(card, 'name', str(card))
    for c in structured_cards:
        if c.get('name') == card_name:
            cost = c.get('cost', {})
            return int(cost.get('money', 0) or 0) + int(cost.get('propaganda', 0) or 0)
    entry = _taxonomy_entry(support_taxonomy, card_name)
    if entry and isinstance(entry.get('cost'), str):
        text = entry['cost']
        money = 0
        propaganda = 0
        if '資金' in text:
            try:
                money = int(text.split('資金')[0].split('+')[-1].strip()[-1])
            except Exception:
                money = 0
        if '宣傳' in text:
            try:
                propaganda = int(text.split('宣傳')[0].split('+')[-1].strip()[-1])
            except Exception:
                propaganda = 0
        return money + propaganda
    return 0


def purchase_area_card_cost_money(structured_cards, support_taxonomy, card):
    card_name = getattr(card, 'name', str(card))
    for c in structured_cards:
        if c.get('name') == card_name:
            cost = c.get('cost', {})
            return int(cost.get('money', 0) or 0)
    entry = _taxonomy_entry(support_taxonomy, card_name)
    if entry and isinstance(entry.get('cost'), str) and '資金' in entry['cost']:
        try:
            return int(entry['cost'].split('資金')[0].split('+')[-1].strip()[-1])
        except Exception:
            return 0
    return 0


def top_card_cost_total(structured_cards, support_taxonomy, card):
    return purchase_area_card_cost_total(structured_cards, support_taxonomy, card)
