"""Pure interactive-support/dissolve target-finder rules (reads
player.organizations/hand and the static map/faction catalogs only, no
mutation).

`_interactive_support_build_towns` stays in `game.py` as a Game method
(not extracted here) even though its own body is pure: it transitively
calls `can_develop_in_town`/`_has_org_supply`, which must stay routed
through `self._org_supply_limit` (not a module composite) so that
`test_build_entitlement_queue.py`'s monkeypatch of `Game._org_supply_limit`
still takes effect — same trap as `game_card_rules.py`'s
`_card_build_town_choices`.

`_can_replace_dissolved_org_with_own` (Taiwan-III's dissolve-then-build
preflight) also stays in `game.py`, despite its docstring calling itself
"non-mutating": it transiently mutates `target_player.organizations[town]`
inside a try/finally before restoring it, which fails the zero-mutation
bar used here. That taints `_support_interaction_targets`'s
`interactive_dissolve_and_build` branch and `_support_card_has_legal_target`
— both stay in `game.py` too.
"""

from server.game_map_rules import towns_within_steps, town_matches_region_alias
from server.game_organization_scope_rules import organization_towns_for_player, shared_origin_owner


def can_dissolve_base_target(target_owner, town):
    if town != getattr(target_owner, 'base', None):
        return True, None
    if getattr(target_owner, 'faction_id', None) == 'red_army':
        return True, None
    return False, "Non-Red-Army bases cannot be dissolved"


def target_players_for_interaction(players, player, target_player_id=None):
    if target_player_id is not None:
        target = next((p for p in players if getattr(p, 'id', None) == target_player_id), None)
        return [target] if target is not None and target is not player else []
    return [other for other in players if other is not player]


def player_has_org_within_steps_of_player(map_data, towns_by_ruler, faction_by_id, players, source_player, target_player, max_steps=1, target_region=None):
    source_towns = organization_towns_for_player(map_data, faction_by_id, players, source_player)
    target_towns = {
        town
        for town in organization_towns_for_player(map_data, faction_by_id, players, target_player)
        if town_matches_region_alias(map_data, towns_by_ruler, town, target_region)
    }
    if not source_towns or not target_towns:
        return False
    reachable = towns_within_steps(map_data, source_towns, max_steps=max_steps)
    return bool(reachable & target_towns)


def find_target_town_within_steps_of_player(map_data, towns_by_ruler, faction_by_id, players, source_player, target_player, max_steps=1, target_region=None):
    source_towns = organization_towns_for_player(map_data, faction_by_id, players, source_player)
    if not source_towns:
        return None
    reachable = towns_within_steps(map_data, source_towns, max_steps=max_steps)
    for town in organization_towns_for_player(map_data, faction_by_id, players, target_player):
        target_owner = shared_origin_owner(faction_by_id, players, target_player, town)
        if (
            target_owner is not None
            and town in reachable
            and town_matches_region_alias(map_data, towns_by_ruler, town, target_region)
            and can_dissolve_base_target(target_owner, town)[0]
        ):
            return town
    return None


def interactive_support_dissolve_targets(
    map_data, towns_by_ruler, faction_by_id, players, player,
    require_self_sacrifice=False, max_steps=1, target_players=None, target_region=None,
):
    targets = []
    seen_physical_targets = set()
    opponents = list(target_players) if target_players is not None else [other for other in players if other is not player]
    source_towns = organization_towns_for_player(map_data, faction_by_id, players, player)
    reachable = towns_within_steps(map_data, source_towns, max_steps=max_steps)
    for other in opponents:
        if other is None or other is player:
            continue
        for town in organization_towns_for_player(map_data, faction_by_id, players, other):
            target_owner = shared_origin_owner(faction_by_id, players, other, town)
            target_key = (getattr(target_owner, 'id', None), town)
            if (
                target_owner is None
                or target_owner is player
                or target_key in seen_physical_targets
                or town not in reachable
                or not town_matches_region_alias(map_data, towns_by_ruler, town, target_region)
            ):
                continue
            if not can_dissolve_base_target(target_owner, town)[0]:
                continue
            seen_physical_targets.add(target_key)
            targets.append({
                'id': f'{getattr(other, "id", other.name)}::{town}',
                'label': f'{other.name}｜{town}',
                'player_id': getattr(other, 'id', None),
                'town': town,
                'requires_self_sacrifice': require_self_sacrifice,
            })
    return targets


def interactive_support_dissolve_targets_near_town(
    map_data, towns_by_ruler, faction_by_id, players, player, origin_town,
    max_steps=1, target_players=None, target_region=None,
):
    reachable = towns_within_steps(map_data, [origin_town], max_steps=max_steps)
    targets = []
    seen_physical_targets = set()
    opponents = list(target_players) if target_players is not None else [other for other in players if other is not player]
    for other in opponents:
        if other is None or other is player:
            continue
        for town in organization_towns_for_player(map_data, faction_by_id, players, other):
            target_owner = shared_origin_owner(faction_by_id, players, other, town)
            target_key = (getattr(target_owner, 'id', None), town)
            if (
                target_owner is None
                or target_owner is player
                or target_key in seen_physical_targets
                or town not in reachable
                or not town_matches_region_alias(map_data, towns_by_ruler, town, target_region)
            ):
                continue
            if not can_dissolve_base_target(target_owner, town)[0]:
                continue
            seen_physical_targets.add(target_key)
            targets.append({
                'id': f'{getattr(other, "id", other.name)}::{town}',
                'label': f'{other.name}｜{town}',
                'player_id': getattr(other, 'id', None),
                'town': town,
                'sacrifice_town': origin_town,
            })
    return targets


def interactive_support_discard_targets_near(map_data, towns_by_ruler, faction_by_id, players, player):
    targets = []
    for other in players:
        if other is player:
            continue
        if not getattr(other, 'hand', None):
            continue
        if not player_has_org_within_steps_of_player(map_data, towns_by_ruler, faction_by_id, players, player, other, max_steps=1):
            continue
        targets.append({
            'id': getattr(other, 'id', None),
            'label': getattr(other, 'name', str(getattr(other, 'id', ''))),
            'player_id': getattr(other, 'id', None),
        })
    return targets


def interactive_support_sacrifice_towns(
    map_data, towns_by_ruler, faction_by_id, players, player, max_steps=1, target_players=None, target_region=None,
):
    towns = []
    for town in organization_towns_for_player(map_data, faction_by_id, players, player):
        target_owner = shared_origin_owner(faction_by_id, players, player, town)
        if target_owner is None:
            continue
        if town == getattr(target_owner, 'base', None):
            continue
        targets = interactive_support_dissolve_targets_near_town(
            map_data, towns_by_ruler, faction_by_id, players, player, town,
            max_steps=max_steps, target_players=target_players, target_region=target_region,
        )
        if not targets:
            continue
        towns.append({
            'town': town,
            'label': f'{town}（可瓦解鄰近敵方組織）',
            'target_count': len(targets),
        })
    return towns
