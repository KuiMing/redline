"""Load the static game-data catalog (map, factions, cards, eras, events) consumed by Game."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = BASE_DIR / "data" / "map.json"
FACTIONS_PATH = BASE_DIR / "data" / "factions" / "all_faction.integrated.v2.json"
STRUCTURED_ACTION_PATH = BASE_DIR / "data" / "action_cards_structured.v1.1.json"
ERA_STRUCTURED_PATH = BASE_DIR / "data" / "era_structured.v1.1.json"
SUPPORT_CARDS_PATH = BASE_DIR / "data" / "cards" / "support_cards.v1.1.json"
SUPPORT_TAXONOMY_PATH = BASE_DIR / "data" / "cards" / "support_taxonomy.v1.1.json"
EVENT_STRUCTURED_PATH = BASE_DIR / "data" / "events_structured.v1.1.json"
EVENT_CARD_COUNTS_PATH = BASE_DIR / "data" / "cards" / "event_and_era_cards.v1.1.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_towns_by_ruler(map_data):
    grouped = {}
    for town, info in (map_data.get("towns", {}) or {}).items():
        for ruler in (info.get("ruler") or []):
            grouped.setdefault(ruler, []).append(town)
    for towns in grouped.values():
        towns.sort()
    return grouped
