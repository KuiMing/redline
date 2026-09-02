"""Pure base-option classification/enumeration rules (no player or pending-choice state).

`Game._compute_pending_base_choices` / `set_base_choice` / `_assign_starting_bases`
/ `_player_base_data` own the actual base-selection pending-choice flow (reads/
writes `self.pending_base_choices`, mutates `player.base`/`player.organizations`,
transitions `self.game_phase`) and stay in `game.py`, out of scope here.

`Game.can_faction_develop_in_town` is turn_log-coupled (via
`_red_army_base_build_blocked`, which reads `self.turn_log`) and also stays in
`game.py` untouched — these functions take it as a `can_develop(faction_id,
town) -> bool` callable instead, so this module has no `Game`/turn_log coupling.
"""

from server.game_map_rules import towns_for_region_alias

_STATIC_SEMANTIC_POOLS = {
    "任意英美城鎮": ["華盛頓", "紐約", "多倫多", "卡加利", "溫哥華", "舊金山", "洛杉磯", "倫敦"],
    "任意南洋": ["曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"],
    "任意南洋城鎮": ["曼谷", "吉隆坡", "新加坡", "雅加達", "河內", "胡志明市", "仰光"],
    "任意東洋": ["東京", "大阪", "福岡", "札幌", "仙臺", "沖繩", "首爾", "釜山"],
}
_REGION_ALIAS_SEMANTIC_LABELS = {
    "任意牆內": "china",
    "任意牆內城鎮": "china",
}


def _semantic_base_pool(map_data, towns_by_ruler, label):
    region = _REGION_ALIAS_SEMANTIC_LABELS.get(label)
    if region is not None:
        return towns_for_region_alias(map_data, towns_by_ruler, region)
    return _STATIC_SEMANTIC_POOLS.get(label, [])


def classify_base_options(faction):
    bases = faction.get("bases", [])
    names = []
    for b in bases:
        if isinstance(b, dict):
            name = b.get("name")
        else:
            name = b
        if name:
            names.append(name)
    tags = set(faction.get("tags", []))

    if faction.get("id") == "hong_kong":
        return "special", names
    if any(name.startswith("任意") for name in names):
        return "flex", names
    if "flex_base" in tags:
        return "flex", names
    first_base = bases[0] if bases else None
    if len(names) == 1 and isinstance(first_base, dict) and first_base.get("type") == "fixed":
        return "fixed", names
    return "candidate", names


def resolve_starting_base(map_data, towns_by_ruler, can_develop, faction, used):
    kind, names = classify_base_options(faction)
    towns = map_data.get("towns", {})

    # fixed / candidate / special currently choose first legal explicit town deterministically
    if kind in {"fixed", "candidate", "special"}:
        for name in names:
            if name in towns and name not in used and can_develop(faction.get("id"), name):
                return name
        return None

    # flex rules: deterministic fallback by semantic token
    if kind == "flex":
        for label in names:
            pool = _semantic_base_pool(map_data, towns_by_ruler, label)
            for town in pool:
                if town in towns and town not in used and can_develop(faction.get("id"), town):
                    return town
        return None

    return None


def base_option_to_towns(map_data, towns_by_ruler, can_develop, faction, option_name):
    towns = map_data.get("towns", {})
    if option_name in towns:
        return [option_name] if can_develop(faction.get("id"), option_name) else []

    pool = _semantic_base_pool(map_data, towns_by_ruler, option_name)
    ordered = []
    seen = set()
    for town in pool:
        if town in towns and town not in seen and can_develop(faction.get("id"), town):
            seen.add(town)
            ordered.append(town)
    return ordered


def candidate_base_names(map_data, towns_by_ruler, can_develop, faction):
    if faction.get("id") in {"uyghur_family", "tibet_family"}:
        return [b.get("name") for b in faction.get("bases", []) if b.get("name")]
    _, names = classify_base_options(faction)
    candidates = []
    seen = set()
    for option_name in names:
        for town in base_option_to_towns(map_data, towns_by_ruler, can_develop, faction, option_name):
            if town not in seen:
                seen.add(town)
                candidates.append(town)
    return candidates
