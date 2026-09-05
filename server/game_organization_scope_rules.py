"""Pure organization-scope/ruler rules (reads player.organizations and the
static map/faction catalogs only, no Game mutation).

Everything that *changes* organizations (`_place_organization`, dissolve
effects, etc.) stays in `game.py` — those mutate `player.organizations`,
unlike everything here, which only counts/classifies existing organizations.
"""

from server.game_faction_rules import factions_sharing_with
from server.game_map_rules import is_inside_wall_town, towns_for_region_alias


def shared_origin_owner(faction_by_id, players, player, town):
    """Which player's organization (own or faction-shared) occupies `town`, if any."""
    if player.organizations.get(town, 0) > 0:
        return player
    shared_with = factions_sharing_with(faction_by_id, player.faction_id)
    if not shared_with:
        return None
    for other in players:
        if other is player:
            continue
        if other.faction_id in shared_with and other.organizations.get(town, 0) > 0:
            return other
    return None


def shared_org_count(faction_by_id, players, player, town):
    owner = shared_origin_owner(faction_by_id, players, player, town)
    return 1 if owner is not None else 0


def town_has_shared_org_access(faction_by_id, players, player, town):
    return shared_origin_owner(faction_by_id, players, player, town) is not None


def town_blocks_movement_for_player(faction_by_id, players, player, town):
    friendly_factions = {player.faction_id}
    friendly_factions.update(factions_sharing_with(faction_by_id, player.faction_id))
    for other in players:
        if other.faction_id in friendly_factions:
            continue
        if other.organizations.get(town, 0) > 0:
            return True
    return False


def organization_towns_for_player(map_data, faction_by_id, players, player):
    """Physical organization towns the player may use, including shared access."""
    if player is None:
        return []
    return [
        town for town in map_data.get('towns', {})
        if shared_org_count(faction_by_id, players, player, town) > 0
    ]


def player_organization_scope_counts(map_data, faction_by_id, players, player, *, include_shared=False):
    """Split owned or effective organizations into inside/outside-wall counts."""
    if player is None:
        return {"total": 0, "inside_wall": 0, "outside_wall": 0}
    if include_shared:
        entries = [(town, 1) for town in organization_towns_for_player(map_data, faction_by_id, players, player)]
    else:
        entries = [
            (town, int(count or 0))
            for town, count in (getattr(player, "organizations", {}) or {}).items()
            if int(count or 0) > 0
        ]
    inside = sum(count for town, count in entries if is_inside_wall_town(map_data, town))
    total = sum(count for _, count in entries)
    return {
        "total": total,
        "inside_wall": inside,
        "outside_wall": total - inside,
    }


def player_ruler_organization_counts(map_data, faction_by_id, players, player):
    """Count organizations by ruler region, including organizations shared with player."""
    counts = {}
    for town in organization_towns_for_player(map_data, faction_by_id, players, player):
        town_data = map_data.get("towns", {}).get(town, {})
        for ruler in (town_data.get("ruler", []) or []):
            counts[ruler] = counts.get(ruler, 0) + 1
    return counts


def player_ruler_leadership(map_data, faction_by_id, players, player):
    """Regions where player has a positive count tied for the most organizations."""
    counts_by_player = {
        other.id: player_ruler_organization_counts(map_data, faction_by_id, players, other)
        for other in players
    }
    own_counts = counts_by_player.get(player.id, {})
    leaders = set()
    for ruler, own_count in own_counts.items():
        if own_count <= 0:
            continue
        maximum = max(
            (counts.get(ruler, 0) for counts in counts_by_player.values()),
            default=0,
        )
        if own_count == maximum:
            leaders.add(ruler)
    return leaders


def player_ruler_presence(map_data, faction_by_id, players, player):
    return set(player_ruler_organization_counts(map_data, faction_by_id, players, player))


def player_region_org_count(map_data, towns_by_ruler, faction_by_id, players, player, region):
    if region in {"china", "牆內"}:
        return player_organization_scope_counts(map_data, faction_by_id, players, player, include_shared=True)["inside_wall"]
    region_towns = set(towns_for_region_alias(map_data, towns_by_ruler, region))
    return sum(
        1 for town in organization_towns_for_player(map_data, faction_by_id, players, player)
        if town in region_towns
    )


def player_requirement_org_count(map_data, towns_by_ruler, faction_by_id, players, player, requirement):
    if requirement.get("region"):
        return player_region_org_count(map_data, towns_by_ruler, faction_by_id, players, player, requirement.get("region"))
    if requirement.get("ruler"):
        ruler = requirement.get("ruler")
        return sum(
            1 for town in organization_towns_for_player(map_data, faction_by_id, players, player)
            if ruler in (map_data.get("towns", {}).get(town, {}).get("ruler") or [])
        )
    return 0
