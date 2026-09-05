import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.game_catalog import (
    MAP_PATH,
    FACTIONS_PATH,
    STRUCTURED_ACTION_PATH,
    ERA_STRUCTURED_PATH,
    SUPPORT_CARDS_PATH,
    SUPPORT_TAXONOMY_PATH,
    EVENT_STRUCTURED_PATH,
    build_towns_by_ruler,
)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _new_game():
    return Game([("p1", "A"), ("p2", "B")])


def test_game_map_matches_direct_file_read():
    game = _new_game()
    assert game.map == _load(MAP_PATH)


def test_game_factions_data_matches_direct_file_read():
    game = _new_game()
    factions_data = _load(FACTIONS_PATH)
    assert game.factions_data == factions_data
    assert game.factions == factions_data["factions"]
    assert game.ability_templates == factions_data.get("ability_templates", {})


def test_game_towns_by_ruler_matches_pure_rebuild_from_map():
    game = _new_game()
    assert game.towns_by_ruler == build_towns_by_ruler(_load(MAP_PATH))


def test_game_structured_cards_matches_direct_file_read():
    game = _new_game()
    assert game.structured_cards == _load(STRUCTURED_ACTION_PATH)["cards"]


def test_game_support_cards_matches_direct_file_read():
    game = _new_game()
    assert game.support_cards == _load(SUPPORT_CARDS_PATH)


def test_game_support_taxonomy_matches_direct_file_read():
    game = _new_game()
    expected = _load(SUPPORT_TAXONOMY_PATH).get("cards", []) if SUPPORT_TAXONOMY_PATH.exists() else []
    assert game.support_taxonomy == expected


def test_game_structured_eras_matches_direct_file_read():
    game = _new_game()
    assert game.structured_eras == _load(ERA_STRUCTURED_PATH)["eras"]


def test_game_structured_events_matches_direct_file_read():
    game = _new_game()
    assert game.structured_events == _load(EVENT_STRUCTURED_PATH).get("events", [])
