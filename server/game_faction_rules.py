"""Pure faction/ability lookup rules (catalog reads only, no player mutation).

Ability *execution* (`Game._activated_faction_action`,
`_apply_card_play_faction_abilities`, `_apply_turn_end_faction_abilities`)
stays in `game.py` — those mutate player/turn state. `can_faction_develop_in_town`
also stays in `game.py`, since it is turn_log-coupled via
`_red_army_base_build_blocked`.
"""

_CAMP_TOKEN_BY_CAMP = {
    "red_army": "紅軍",
    "taiwan": "臺灣",
    "hong_kong": "香港",
    "manchuria": "滿洲",
    "mongol": "蒙古",
    "kazakh": "哈薩克",
    "tibet": "藏國",
    "uyghur": "維吾爾",
    "rebel": "反賊",
}

_CANONICAL_FACTION_NAME_TO_ID = {
    '地下教會': 'underground_church',
    '性別革命': 'gender_revolution',
    '客家': 'hakka',
    '潮汕': 'chaoshan',
    '閩': 'min',
    '吳越': 'wuyue',
    '滇': 'dian',
    '滬': 'hu',
    '粵': 'yue',
    '澳門': 'aomen',
    '綠線臺灣': 'taiwan_green',
    '藍線臺灣': 'taiwan_blue',
    '民國派': 'republican',
}

_ABILITY_TEXT_ALIAS_MAPPING = {
    "商貿組織": {"ref": "first_money_draw", "name_override": "商貿組織"},
    "展現實力": {"ref": "combo_three_unique", "name_override": "展現實力"},
    "殉道者": {"ref": "martyr_draw", "name_override": "殉道者"},
    "青山里": {"ref": "martyr_draw", "name_override": "青山里"},
    "星星之火": {"ref": "first_propaganda_draw", "name_override": "星星之火"},
    "民族調和": {"ref": "first_propaganda_draw", "name_override": "民族調和"},
    "基金會": {"ref": "first_money_gain2", "name_override": "基金會"},
    "共合會": {"ref": "first_money_gain2", "name_override": "共合會"},
    "本土社團": {"ref": "on_build_draw_inner", "name_override": "本土社團"},
    "民國之心": {"ref": "on_build_draw_inner_or_nanyang", "name_override": "民國之心"},
    "還我河山": {"ref": "on_build_draw", "name_override": "還我河山"},
}

_ABILITY_TEXT_DIRECT_MAPPING = {
    "華文傳媒": {"name": "華文傳媒", "type": "passive", "effect": "可以用資金支付宣傳。"},
    "各界資助": {"name": "各界資助", "type": "setup", "effect": "在遊戲開始時額外將1張資助者洗入起始牌庫。"},
    "民主陣線": {"name": "民主陣線", "type": "activated", "effect": "您可以用2點任意資源購買已被移除的任1張牌。"},
    "立場試探": {"name": "立場試探", "type": "activated", "effect": "展示牌庫頂牌；若購買費用為奇數則加入手牌，若為偶數則放入棄牌堆。"},
    "賭徒耳語": {"name": "賭徒耳語", "type": "activated", "effect": "將1張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶；若猜中獲得3點宣傳與3點資金。"},
    "活動家": {"name": "活動家", "type": "setup", "effect": "在遊戲開始時額外將2張宣傳家洗入起始牌庫。"},
    "人同此心": {"name": "人同此心", "type": "triggered", "effect": "當您每回合第1次打出購買費用含宣傳的牌時，獲得2點宣傳。"},
    "共享組織": {"name": "共享組織", "type": "passive", "effect": "可與指定陣營共用組織。"},
    "非暴力": {"name": "非暴力", "type": "restriction", "effect": "禁止持有武裝類卡牌。"},
    "民族祭儀": {"name": "民族祭儀", "type": "activated", "effect": "將1張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶並展示；猜中獲得2點宣傳與2點資金，沒猜中獲得2點宣傳或2點資金。"},
    "紅軍派系": {"name": "紅軍派系", "type": "activated", "effect": "每回合可檢視1次牌庫頂3張牌，將其以任意順序放回牌庫頂，並抽1張牌。"},
}


def resolve_ability_ref(ability_templates, ability):
    if isinstance(ability, dict) and ability.get("ref"):
        template = dict(ability_templates.get(ability.get("ref"), {}))
        template.update({k: v for k, v in ability.items() if k != "ref"})
        if ability.get("name_override"):
            template["name"] = ability["name_override"]
        return template
    return ability if isinstance(ability, dict) else None


def resolve_ability_text(ability_templates, text):
    if not isinstance(text, str) or "【" not in text or "】" not in text:
        return None
    name = text.split("【", 1)[1].split("】", 1)[0]
    mapped = _ABILITY_TEXT_ALIAS_MAPPING.get(name)
    if mapped:
        return resolve_ability_ref(ability_templates, mapped)
    return _ABILITY_TEXT_DIRECT_MAPPING.get(name)


def resolve_faction_abilities(faction_by_id, ability_templates, faction_id):
    faction = faction_by_id.get(faction_id, {})
    resolved = []
    for ability in faction.get("abilities", []):
        item = resolve_ability_ref(ability_templates, ability)
        if item:
            resolved.append(item)
    for text in faction.get("abilities_text", []):
        item = resolve_ability_text(ability_templates, text)
        if item:
            resolved.append(item)
    return resolved


def player_base_data(faction_by_id, player_faction_id, player_base):
    faction = faction_by_id.get(player_faction_id, {})
    for base in faction.get("bases", []):
        if isinstance(base, dict) and base.get("name") == player_base:
            return base
    return None


def player_effective_abilities(faction_by_id, ability_templates, player_faction_id, player_base):
    abilities = list(resolve_faction_abilities(faction_by_id, ability_templates, player_faction_id))
    base = player_base_data(faction_by_id, player_faction_id, player_base)
    if base:
        abilities.extend(base.get("abilities", []))
    return abilities


def player_has_ability(faction_by_id, ability_templates, player_faction_id, player_base, name):
    abilities = player_effective_abilities(faction_by_id, ability_templates, player_faction_id, player_base)
    return any(isinstance(a, dict) and a.get("name") == name for a in abilities)


def camp_token_for_faction_id(faction_by_id, faction_id):
    faction = faction_by_id.get(faction_id, {})
    camp = faction.get("camp")
    return _CAMP_TOKEN_BY_CAMP.get(camp)


def canonical_faction_name_to_id(name):
    return _CANONICAL_FACTION_NAME_TO_ID.get(name, name)


def factions_sharing_with(faction_by_id, faction_id):
    faction = faction_by_id.get(faction_id, {})
    shared = {canonical_faction_name_to_id(x) for x in (faction.get('shared_organizations_with', []) or [])}
    for text in faction.get('special_rules', []) or []:
        if '共用組織' in text:
            if '粵、澳門' in text:
                shared.update(['yue', 'aomen'])
            if '藍線臺灣' in text:
                shared.update(['taiwan_blue'])
            if '綠線臺灣' in text:
                shared.update(['taiwan_green'])
            if '香港' in text:
                shared.update(['hong_kong'])
    return shared
