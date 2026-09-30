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

from server.game_faction_rules import player_has_ability
from server.game_map_rules import towns_within_steps, town_matches_region_alias
from server.game_organization_scope_rules import organization_towns_for_player, shared_origin_owner


def can_dissolve_base_target(target_owner, town):
    if town != getattr(target_owner, 'base', None):
        return True, None
    if getattr(target_owner, 'faction_id', None) == 'red_army':
        return True, None
    return False, "Non-Red-Army bases cannot be dissolved"


def _target_owner_has_mongol_shield(faction_by_id, ability_templates, target_owner):
    """Whether dissolving one of `target_owner`'s organizations requires the attacker to first
    discard a hand card (盟旗學校) -- `ability_templates` may be `None` for callers that don't
    care about this check at all (e.g. existing direct unit tests of this module predating the
    ability), in which case this always reports "no shield" rather than raising.
    """
    if ability_templates is None:
        return False
    return player_has_ability(
        faction_by_id, ability_templates,
        getattr(target_owner, 'faction_id', None), getattr(target_owner, 'base', None),
        "盟旗學校",
    )


def target_players_for_interaction(players, player, target_player_id=None):
    if target_player_id is not None:
        target = next((p for p in players if getattr(p, 'id', None) == target_player_id), None)
        return [target] if target is not None and target is not player else []
    return [other for other in players if other is not player]


def player_has_org_within_steps_of_player(map_data, towns_by_ruler, faction_by_id, players, source_player, target_player, max_steps=1, target_region=None, include_shared_source=True):
    source_towns = (
        organization_towns_for_player(map_data, faction_by_id, players, source_player)
        if include_shared_source else list(source_player.organizations)
    )
    target_towns = {
        town
        for town in target_player.organizations
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
    include_shared_source=False, ability_templates=None, pre_reserved_shield_discards=0,
    exclude_target_keys=None,
):
    """`ability_templates` (optional, defaults to no-shield-checking for existing direct callers
    that predate this) and `pre_reserved_shield_discards` gate 盟旗學校-protected targets by
    whether the attacker (`player`) could actually pay its discard-a-hand-card cost -- a
    protected organization the attacker cannot currently afford is simply not a legal target at
    all, exactly like any other range/ownership check, so it must never be offered here in the
    first place (parent-level review, defect 1: previously this was only checked much later, at
    actual mutation time inside dissolve_organization(), by which point the player had already
    been shown -- and could select -- a target that was always going to fail).

    `pre_reserved_shield_discards` accounts for hand-card costs already committed to OTHER
    protected targets earlier in the SAME multi-pick flow (accumulated_dissolve_picks from a
    previous resolve call) -- e.g. if the attacker has exactly 1 hand card and 2 Mongol
    organizations are in range, only 1 may ever be offered as a legal target across the whole
    selection, not both.

    `exclude_target_keys` (an iterable of `(player_id, town)` pairs) removes specific candidates
    from consideration ENTIRELY -- before they ever compete for `available_shield_discards`
    budget -- rather than being filtered out of the returned list afterward. This matters: an
    already-accumulated pick's town is still physically present in `other.organizations` (board
    mutation is deferred to final commit), so if it were merely filtered out of the RESULT list
    after the fact, it would still have consumed 1 unit of shield-discard budget while being
    walked, silently starving a later, still-uncommitted, genuinely-affordable Mongol candidate
    of budget purely as an artifact of `other.organizations` dict iteration order (parent-level
    review, defect 1 follow-up / Critical 2) -- passing the already-picked keys here instead of
    (or in addition to) a bare `pre_reserved_shield_discards` count ensures they never enter the
    walk at all, so only genuinely-still-open candidates ever compete for the remaining budget.
    """
    targets = []
    seen_physical_targets = set()
    excluded_keys = set(exclude_target_keys or ())
    opponents = list(target_players) if target_players is not None else [other for other in players if other is not player]
    source_towns = (
        organization_towns_for_player(map_data, faction_by_id, players, player)
        if include_shared_source else list(player.organizations)
    )
    reachable = towns_within_steps(map_data, source_towns, max_steps=max_steps)
    available_shield_discards = max(0, len(getattr(player, 'hand', None) or []) - int(pre_reserved_shield_discards or 0))
    for other in opponents:
        if other is None or other is player:
            continue
        for town in other.organizations:
            target_owner = other
            target_key = (getattr(target_owner, 'id', None), town)
            if (
                target_owner is None
                or target_owner is player
                or target_key in seen_physical_targets
                or target_key in excluded_keys
                or town not in reachable
                or not town_matches_region_alias(map_data, towns_by_ruler, town, target_region)
            ):
                continue
            if not can_dissolve_base_target(target_owner, town)[0]:
                continue
            if _target_owner_has_mongol_shield(faction_by_id, ability_templates, target_owner):
                if available_shield_discards <= 0:
                    continue
                available_shield_discards -= 1
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
    max_steps=1, target_players=None, target_region=None, excluded_target=None,
    ability_templates=None, pre_reserved_shield_discards=0, exclude_target_keys=None,
):
    # See interactive_support_dissolve_targets's docstring for the full rationale --
    # 盟旗學校-protected targets the attacker cannot currently afford must never be offered, and
    # already-accumulated picks (exclude_target_keys) must never compete for shield-discard
    # budget in the first place (Critical 2 / dict-iteration-order under-delivery).
    reachable = towns_within_steps(map_data, [origin_town], max_steps=max_steps)
    targets = []
    seen_physical_targets = set()
    excluded_keys = set(exclude_target_keys or ())
    opponents = list(target_players) if target_players is not None else [other for other in players if other is not player]
    available_shield_discards = max(0, len(getattr(player, 'hand', None) or []) - int(pre_reserved_shield_discards or 0))
    for other in opponents:
        if other is None or other is player:
            continue
        for town in other.organizations:
            target_owner = other
            target_key = (getattr(target_owner, 'id', None), town)
            if (
                target_owner is None
                or target_owner is player
                or target_key == excluded_target
                or target_key in seen_physical_targets
                or target_key in excluded_keys
                or town not in reachable
                or not town_matches_region_alias(map_data, towns_by_ruler, town, target_region)
            ):
                continue
            if not can_dissolve_base_target(target_owner, town)[0]:
                continue
            if _target_owner_has_mongol_shield(faction_by_id, ability_templates, target_owner):
                if available_shield_discards <= 0:
                    continue
                available_shield_discards -= 1
            seen_physical_targets.add(target_key)
            targets.append({
                'id': f'{getattr(other, "id", other.name)}::{town}',
                'label': f'{other.name}｜{town}',
                'player_id': getattr(other, 'id', None),
                'town': town,
                'sacrifice_town': origin_town,
            })
    return targets


def interactive_support_discard_targets_near(
    map_data, towns_by_ruler, faction_by_id, players, player, max_steps=1,
    target_players=None, target_region=None, include_shared_source=False,
):
    targets = []
    opponents = list(target_players) if target_players is not None else players
    for other in opponents:
        if other is player:
            continue
        if not getattr(other, 'hand', None):
            continue
        if not player_has_org_within_steps_of_player(
            map_data, towns_by_ruler, faction_by_id, players, player, other,
            max_steps=max_steps, target_region=target_region,
            include_shared_source=include_shared_source,
        ):
            continue
        targets.append({
            'id': getattr(other, 'id', None),
            'label': getattr(other, 'name', str(getattr(other, 'id', ''))),
            'player_id': getattr(other, 'id', None),
        })
    return targets


def interactive_support_sacrifice_towns(
    map_data, towns_by_ruler, faction_by_id, players, player, max_steps=1, target_players=None, target_region=None,
    include_shared_source=False,
):
    towns = []
    source_towns = (
        organization_towns_for_player(map_data, faction_by_id, players, player)
        if include_shared_source else list(player.organizations)
    )
    for town in source_towns:
        target_owner = shared_origin_owner(faction_by_id, players, player, town) if include_shared_source else player
        if target_owner is None:
            continue
        if town == getattr(target_owner, 'base', None):
            continue
        targets = interactive_support_dissolve_targets_near_town(
            map_data, towns_by_ruler, faction_by_id, players, player, town,
            max_steps=max_steps, target_players=target_players, target_region=target_region,
            excluded_target=(getattr(target_owner, 'id', None), town),
        )
        if not targets:
            continue
        towns.append({
            'town': town,
            'label': f'{town}（可瓦解鄰近敵方組織）',
            'target_count': len(targets),
        })
    return towns
