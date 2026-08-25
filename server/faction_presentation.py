"""Build faction, base, and era-stage presentation data for the lobby API."""

import json
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
FACTION_DATA_PATH = BASE_DIR / "data" / "factions" / "all_faction.integrated.v2.json"
ERA_DATA_PATH = BASE_DIR / "data" / "era_structured.v1.1.json"
ERA_CARD_DATA_PATH = BASE_DIR / "data" / "cards" / "event_and_era_cards.v1.1.json"


def faction_category(faction_id: str):
    if faction_id == "red_army":
        return "red_army"
    if faction_id in {"taiwan_green", "taiwan_blue"}:
        return "taiwan"
    if faction_id in {
        "uyghur_family",
        "uyghur_istanbul",
        "uyghur_munich",
        "uyghur_washington",
        "uyghur_almaty",
    }:
        return "uyghur"
    if faction_id in {
        "tibet_family",
        "tibet_dharamsala",
        "tibet_dehradun",
        "tibet_chogu",
    }:
        return "tibet"
    if faction_id in {"hong_kong", "manchuria", "mongol", "kazakh"}:
        return faction_id
    return "rebel"


@lru_cache(maxsize=1)
def canonical_inside_wall_towns():
    path = BASE_DIR / "data" / "map.json"
    with path.open(encoding="utf-8") as f:
        map_data = json.load(f)
    return tuple(
        town
        for town, info in (map_data.get("towns", {}) or {}).items()
        if "紅軍" in (info.get("ruler") or [])
    )


def semantic_base_pool(option_name: str):
    pools = {
        "任意牆內": list(canonical_inside_wall_towns()),
        "任意牆內城鎮": list(canonical_inside_wall_towns()),
        "任意英美城鎮": [
            "華盛頓",
            "紐約",
            "多倫多",
            "卡加利",
            "溫哥華",
            "舊金山",
            "洛杉磯",
            "倫敦",
        ],
        "任意南洋": [
            "曼谷",
            "吉隆坡",
            "新加坡",
            "雅加達",
            "河內",
            "胡志明市",
            "仰光",
        ],
        "任意南洋城鎮": [
            "曼谷",
            "吉隆坡",
            "新加坡",
            "雅加達",
            "河內",
            "胡志明市",
            "仰光",
        ],
        "任意東洋": ["東京", "大阪", "福岡", "札幌", "仙臺", "沖繩", "首爾", "釜山"],
    }
    return pools.get(option_name, [])


def faction_base_options(by_id, faction_id: str):
    if faction_id == "mongol":
        return ["烏蘭巴托", "東京", "紐約"]
    if faction_id == "manchuria":
        return ["東京", "舊金山", "海參崴"]
    if faction_id == "kazakh":
        return ["阿拉木圖"]
    if faction_id == "hong_kong":
        return ["香港城"]
    if faction_id in {
        "uyghur_family",
        "uyghur_istanbul",
        "uyghur_munich",
        "uyghur_washington",
        "uyghur_almaty",
    }:
        return ["伊斯坦堡", "慕尼黑", "華盛頓", "阿拉木圖"]
    if faction_id in {
        "tibet_family",
        "tibet_dharamsala",
        "tibet_dehradun",
        "tibet_chogu",
    }:
        return ["達蘭薩拉", "德拉敦", "哲古宗"]

    faction = by_id.get(faction_id, {})
    options = []
    for base in faction.get("bases", []):
        name = base.get("name") if isinstance(base, dict) else base
        if name and name not in options:
            options.append(name)
    return options


def faction_base_resolved(by_id, faction_id: str):
    options = faction_base_options(by_id, faction_id)
    resolved = {}
    for option in options:
        towns = semantic_base_pool(option)
        resolved[option] = towns if towns else [option]
    return resolved


def build_faction_presentation():
    with FACTION_DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    factions = data["factions"]
    by_id = {faction["id"]: faction for faction in factions}
    rebels = [faction for faction in factions if faction.get("camp") == "rebel"]
    ability_templates = data.get("ability_templates", {})

    with ERA_DATA_PATH.open(encoding="utf-8") as f:
        era_rows = json.load(f).get("eras", [])
    with ERA_CARD_DATA_PATH.open(encoding="utf-8") as f:
        era_card_rows = json.load(f)
    era_cards_by_name = {
        row[0]: row
        for row in era_card_rows
        if isinstance(row, list)
        and len(row) >= 5
        and isinstance(row[0], str)
        and row[0].startswith("[")
    }
    era_stage_by_camp = {}
    for era in era_rows:
        camp = (era.get("trigger") or {}).get("camp")
        if not camp:
            continue
        card_row = era_cards_by_name.get(era.get("name"), [])
        era_stage_by_camp[camp] = {
            "id": era.get("id"),
            "name": era.get("name"),
            "summary_text": card_row[1] if len(card_row) > 1 else "",
            "trigger_text": card_row[2] if len(card_row) > 2 else "",
            "success_text": card_row[3] if len(card_row) > 3 else "",
            "fail_text": card_row[4] if len(card_row) > 4 else "",
        }

    def resolve_ui_faction(faction):
        resolved = dict(faction)
        resolved_abilities = []
        for ability in faction.get("abilities", []):
            if isinstance(ability, dict) and ability.get("ref"):
                template = ability_templates.get(ability.get("ref"), {})
                merged = dict(template)
                merged.update({key: value for key, value in ability.items() if key != "ref"})
                if ability.get("name_override"):
                    merged["name"] = ability["name_override"]
                resolved_abilities.append(merged)
            else:
                resolved_abilities.append(ability)
        resolved["abilities"] = resolved_abilities
        if faction.get("camp") in era_stage_by_camp:
            resolved["era_stage"] = dict(era_stage_by_camp[faction.get("camp")])
        return resolved

    def resolve_family_ui_faction(family_id, name, camp, variant_ids):
        bases = []
        variant_details = {}
        for variant_id in variant_ids:
            variant = resolve_ui_faction(by_id[variant_id])
            base = next(
                (
                    base
                    for base in variant.get("bases", [])
                    if isinstance(base, dict) and base.get("name")
                ),
                None,
            )
            base_name = base.get("name") if base else variant.get("variant")
            if base_name:
                bases.append({"name": base_name, "variant_faction": variant_id})
                variant_details[base_name] = variant
        result = {
            "id": family_id,
            "name": name,
            "camp": camp,
            "bases": bases,
            "variant_details": variant_details,
        }
        if camp in era_stage_by_camp:
            result["era_stage"] = dict(era_stage_by_camp[camp])
        return result

    categories = [
        {
            "id": "red_army",
            "label": "紅軍",
            "mode": "direct",
            "options": [resolve_ui_faction(by_id["red_army"])],
        },
        {
            "id": "taiwan",
            "label": "臺灣",
            "mode": "variant",
            "options": [
                resolve_ui_faction(by_id["taiwan_green"]),
                resolve_ui_faction(by_id["taiwan_blue"]),
            ],
        },
        {
            "id": "hong_kong",
            "label": "香港",
            "mode": "direct",
            "options": [resolve_ui_faction(by_id["hong_kong"])],
        },
        {
            "id": "uyghur",
            "label": "維吾爾",
            "mode": "direct",
            "options": [
                resolve_family_ui_faction(
                    "uyghur_family",
                    "維吾爾",
                    "uyghur",
                    [
                        "uyghur_istanbul",
                        "uyghur_munich",
                        "uyghur_washington",
                        "uyghur_almaty",
                    ],
                )
            ],
        },
        {
            "id": "tibet",
            "label": "西藏",
            "mode": "direct",
            "options": [
                resolve_family_ui_faction(
                    "tibet_family",
                    "西藏",
                    "tibet",
                    [
                        "tibet_dharamsala",
                        "tibet_dehradun",
                        "tibet_chogu",
                    ],
                )
            ],
        },
        {
            "id": "manchuria",
            "label": "滿洲",
            "mode": "direct",
            "options": [resolve_ui_faction(by_id["manchuria"])],
        },
        {
            "id": "mongol",
            "label": "蒙古",
            "mode": "direct",
            "options": [resolve_ui_faction(by_id["mongol"])],
        },
        {
            "id": "kazakh",
            "label": "哈薩克",
            "mode": "direct",
            "options": [resolve_ui_faction(by_id["kazakh"])],
        },
        {
            "id": "rebel",
            "label": "反賊",
            "mode": "variant",
            "options": [resolve_ui_faction(faction) for faction in rebels],
        },
    ]

    for category in categories:
        for option in category["options"]:
            option["base_options"] = faction_base_options(by_id, option["id"])
            option["base_resolved"] = faction_base_resolved(by_id, option["id"])

    return {"categories": categories}
