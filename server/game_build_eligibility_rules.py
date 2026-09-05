"""Pure build/org eligibility rules (map/faction/ability catalog reads and
read-only player/turn_log reads only, no mutation).

Actually building or removing an organization (`_place_organization`,
dissolve effects) stays in `game.py` — those mutate `player.organizations`,
unlike everything here, which only classifies where a build/rail-move would
be legal.
"""

from server.game_faction_rules import (
    camp_token_for_faction_id,
    player_has_ability,
    player_matches_camp,
)
from server.game_map_rules import (
    towns_for_region_alias,
    town_matches_region_alias,
    towns_within_steps,
)
from server.game_organization_scope_rules import (
    organization_towns_for_player,
    town_blocks_movement_for_player,
)

# rules.md 步驟④：反共陣營各 22 個組織棋，此即可建立組織之最大數量。
# 紅軍上限原文為「反共陣營玩家總人數×8（有臺灣玩家再+8）」；
# 依使用者 2026-07-11 決定改為固定 40。
ANTI_COMMUNIST_ORG_SUPPLY = 22
RED_ARMY_ORG_SUPPLY = 40


def camp_token_for_player(faction_by_id, player):
    return camp_token_for_faction_id(faction_by_id, getattr(player, 'faction_id', None))


def red_army_base_build_blocked(turn_log, faction_id, town):
    return (
        faction_id == 'red_army'
        and town in set((turn_log or {}).get('red_army_base_build_blocks', []) or [])
    )


def can_faction_develop_in_town(map_data, faction_by_id, turn_log, faction_id, town):
    town_data = map_data.get("towns", {}).get(town)
    if not town_data:
        return False

    camp_tags = town_data.get("camp", []) or []
    faction_token = camp_token_for_faction_id(faction_by_id, faction_id)

    # Red Army can only develop where explicit red camp tag exists. A base that
    # suffered two successful dissolves by one attacker is blocked only this turn.
    if faction_id == "red_army":
        if red_army_base_build_blocked(turn_log, faction_id, town):
            return False
        return "紅軍" in camp_tags

    # Non-red factions may develop in their own tagged towns OR towns with no camp tags.
    if not camp_tags:
        return True
    return faction_token in camp_tags


def organization_entries_at(players, town):
    return [
        (player, int((player.organizations or {}).get(town, 0) or 0))
        for player in players
        if int((player.organizations or {}).get(town, 0) or 0) > 0
    ]


def town_has_physical_organization(players, town):
    return bool(organization_entries_at(players, town))


def organization_occupancy_violations(map_data, players):
    violations = []
    for town in map_data.get('towns', {}):
        entries = organization_entries_at(players, town)
        if len(entries) > 1 or any(count != 1 for _, count in entries):
            violations.append({
                'town': town,
                'entries': [
                    {'player_id': getattr(owner, 'id', None), 'player': owner.name, 'count': count}
                    for owner, count in entries
                ],
            })
    return violations


def rail_reachable_within_three(map_data, towns_by_ruler, faction_by_id, players, player, from_town, to_town):
    # rules.md：鐵路一次最多移動3格，但「翻牆需2次移動且僅移動1格」——
    # 多格鐵路移動不得跨越牆內/牆外邊界（跨牆只能走 move_organization 的1格跨牆分支）
    movement_rules = map_data.get('movement_rules', {}) or {}
    rail_range = max(1, int(movement_rules.get('rail_range', 3) or 3))
    inner_towns = set(towns_for_region_alias(map_data, towns_by_ruler, 'china'))
    origin_side_inner = from_town in inner_towns
    visited = {from_town}
    queue = [(from_town, 0)]
    while queue:
        town, distance = queue.pop(0)
        if distance >= rail_range:
            continue
        for neighbor in map_data.get('towns', {}).get(town, {}).get('rail', []) or []:
            if neighbor not in map_data.get('towns', {}):
                continue
            if (neighbor in inner_towns) != origin_side_inner:
                continue
            next_distance = distance + 1
            if neighbor == to_town:
                return not town_blocks_movement_for_player(faction_by_id, players, player, neighbor)
            if neighbor in visited:
                continue
            if town_blocks_movement_for_player(faction_by_id, players, player, neighbor):
                continue
            visited.add(neighbor)
            queue.append((neighbor, next_distance))
    return False


def org_supply_limit(player):
    return RED_ARMY_ORG_SUPPLY if getattr(player, 'faction_id', None) == 'red_army' else ANTI_COMMUNIST_ORG_SUPPLY


def has_org_supply(player, count=1):
    return player.total_organizations() + count <= org_supply_limit(player)


def can_develop_in_town(map_data, faction_by_id, players, turn_log, player, town):
    # 所有建立路徑都遵守：全場每城最多一個實體組織；共用組織只提供使用權，不提供疊放例外。
    if town_has_physical_organization(players, town):
        return False
    if not has_org_supply(player):
        return False
    return can_faction_develop_in_town(map_data, faction_by_id, turn_log, player.faction_id, town)


def player_is_nonviolent(faction_by_id, ability_templates, player):
    return player_has_ability(faction_by_id, ability_templates, player.faction_id, player.base, "非暴力")


def player_is_distance_restricted(faction_by_id, ability_templates, player):
    # 新疆社會管控（維吾爾慕尼黑）：無法無視距離建立牆內組織
    return player_has_ability(faction_by_id, ability_templates, player.faction_id, player.base, "新疆社會管控")


def faction_restricts_ignore_distance_build(map_data, towns_by_ruler, faction_by_id, ability_templates, player, town):
    if not player_is_distance_restricted(faction_by_id, ability_templates, player):
        return False
    return town in set(towns_for_region_alias(map_data, towns_by_ruler, "china"))


def era_restricts_ignore_distance_build(active_era_effects_list, faction_by_id, map_data, towns_by_ruler, player, target_town):
    for _era, _side, effect in active_era_effects_list:
        if (effect or {}).get('type') != 'restrict_ignore_distance_build':
            continue
        if not player_matches_camp(faction_by_id, player, effect.get('target_camp')):
            continue
        scope = effect.get('scope')
        if scope and not town_matches_region_alias(map_data, towns_by_ruler, target_town, scope):
            continue
        return True
    return False


def ignore_distance_build_restricted(
    map_data, towns_by_ruler, faction_by_id, ability_templates, active_era_effects_list, player, town
):
    """該玩家在這個城鎮是否「無法無視距離建立組織」。

    目前有兩種來源，兩者的處理方式必須一致：
    1. 陣營能力「新疆社會管控」（維吾爾）——固定限制牆內。
    2. 時代關卡的 `restrict_ignore_distance_build` 紅色壓制（[反賊]公知世代的終結、
       [哈薩克]伊塔事件……），依 `target_camp`／`scope` 判定。任何未來新增同型效果
       的時代關卡都會自動沿用同一套處理。

    兩者都只是「不能無視距離」，不是「完全不能建立」：呼叫端應改用近距離退回範圍
    （見 `restricted_build_fallback_towns()`），而不是直接把城鎮排除掉。
    """
    if faction_restricts_ignore_distance_build(map_data, towns_by_ruler, faction_by_id, ability_templates, player, town):
        return True
    return era_restricts_ignore_distance_build(active_era_effects_list, faction_by_id, map_data, towns_by_ruler, player, town)


def restricted_build_fallback_towns(map_data, faction_by_id, players, ability_templates, player, fallback_range):
    """受距離限制時可退回的建立範圍：卡面基礎格數 ＋ 建立距離加成 ＋ 安全屋 +1。

    例：組織經驗甲卡面「本牌於牆內建立組織距離為1格」＝ fallback_range 1；若該玩家
    另有增加建立距離的能力（安全屋／build_range_bonus），則放寬為 2 格。
    """
    fallback_range = int(fallback_range or 0)
    if fallback_range <= 0:
        return set()
    source_towns = organization_towns_for_player(map_data, faction_by_id, players, player)
    if not source_towns:
        return set()
    max_steps = fallback_range + int(getattr(player, 'build_range_bonus', 0) or 0)
    if player_has_ability(faction_by_id, ability_templates, player.faction_id, player.base, "安全屋"):
        max_steps += 1
    return towns_within_steps(map_data, source_towns, max_steps=max_steps)


def active_era_effects(active_era_details):
    effects = []
    for detail in active_era_details:
        for side, effect in ((detail.get('effects') or {}).items()):
            effects.append((detail, side, effect or {}))
    return effects
