"""Pure map-topology queries over static map/catalog data (no player or turn state)."""

REGION_ALIAS_TO_RULER = {
    "china": "紅軍",
    "taiwan": "臺灣",
    "hong_kong": "紅軍",
    "southeast_asia": "南洋",
    "manchuria": "滿洲",
    "outer_manchuria": "北國",
    "mongolian_plateau": "蒙古",
    "inner_mongolia": "紅軍",
    "turkestan": "紅軍",
    "tibet_region": "藏國",
    "india": "印度",
    "middle_east": "天方",
    "japan": "東洋",
    "korean_peninsula": "東洋",
    "trans_siberian": "北國",
    "anglo_america": "英美",
    "europe": "歐洲",
}


def is_inside_wall_town(map_data, town):
    """Classify a town by canonical map ruler, not runtime controller."""
    town_data = (map_data.get("towns", {}) or {}).get(town, {})
    return "紅軍" in (town_data.get("ruler") or [])


def town_neighbors(map_data, town):
    if not town:
        return set()
    entry = map_data.get('towns', {}).get(town, {}) or {}
    return set(entry.get('road', []) or []) | set(entry.get('rail', []) or [])


def towns_within_steps(map_data, origins, max_steps=1):
    origins = [town for town in (origins or []) if town in map_data.get('towns', {})]
    if max_steps < 0 or not origins:
        return set()
    seen = set(origins)
    frontier = [(town, 0) for town in origins]
    while frontier:
        town, dist = frontier.pop(0)
        if dist >= max_steps:
            continue
        for nxt in town_neighbors(map_data, town):
            if nxt not in seen:
                seen.add(nxt)
                frontier.append((nxt, dist + 1))
    return seen


def towns_for_region_alias(map_data, towns_by_ruler, region):
    ruler = REGION_ALIAS_TO_RULER.get(region, region)
    towns = list(towns_by_ruler.get(ruler, []))
    if towns:
        return towns
    # Some era regions (for example tibet_region) are represented by camp tags
    # rather than ruler tags on the current map data.
    camp_towns = [
        town for town, info in (map_data.get("towns", {}) or {}).items()
        if ruler in (info.get("camp") or [])
    ]
    camp_towns.sort()
    return camp_towns


def town_matches_region_alias(map_data, towns_by_ruler, town, region):
    if not region:
        return True
    return town in set(towns_for_region_alias(map_data, towns_by_ruler, region))
