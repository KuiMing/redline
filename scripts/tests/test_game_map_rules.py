import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.game_map_rules import (
    is_inside_wall_town,
    town_neighbors,
    towns_within_steps,
    towns_for_region_alias,
    town_matches_region_alias,
)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _new_game():
    return Game([("p1", "A"), ("p2", "B")])


def test_is_inside_wall_town_matches_game_method_for_every_town():
    game = _new_game()
    for town in game.map.get("towns", {}):
        assert game._is_inside_wall_town(town) == is_inside_wall_town(game.map, town)


def test_town_neighbors_matches_game_method_for_sample_towns():
    game = _new_game()
    for town in ["臺北", "新北", "基隆", "桃園", "新竹"]:
        assert game._town_neighbors(town) == town_neighbors(game.map, town)


def test_town_neighbors_empty_for_falsy_town():
    game = _new_game()
    assert game._town_neighbors(None) == set() == town_neighbors(game.map, None)


def test_towns_within_steps_matches_game_method():
    game = _new_game()
    for max_steps in (0, 1, 2):
        assert game._towns_within_steps(["臺北"], max_steps) == towns_within_steps(
            game.map, ["臺北"], max_steps
        )


def test_towns_for_region_alias_matches_game_method_for_every_known_alias():
    game = _new_game()
    aliases = [
        "china", "taiwan", "hong_kong", "southeast_asia", "manchuria",
        "outer_manchuria", "mongolian_plateau", "inner_mongolia", "turkestan",
        "tibet_region", "india", "middle_east", "japan", "korean_peninsula",
        "trans_siberian", "anglo_america", "europe",
    ]
    for alias in aliases:
        assert game._towns_for_region_alias(alias) == towns_for_region_alias(
            game.map, game.towns_by_ruler, alias
        )


def test_towns_for_region_alias_camp_fallback_still_works():
    # tibet_region has no direct ruler match on the current map data and is
    # represented via camp tags instead — this exercises that fallback path.
    game = _new_game()
    result = game._towns_for_region_alias("tibet_region")
    assert result == towns_for_region_alias(game.map, game.towns_by_ruler, "tibet_region")
    assert result == sorted(result)


def test_town_matches_region_alias_matches_game_method():
    game = _new_game()
    cases = [("臺北", "taiwan"), ("臺北", "china"), ("臺北", None), ("臺北", "")]
    for town, region in cases:
        assert game._town_matches_region_alias(town, region) == town_matches_region_alias(
            game.map, game.towns_by_ruler, town, region
        )
