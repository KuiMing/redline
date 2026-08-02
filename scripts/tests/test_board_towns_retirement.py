from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.victory import VictoryEngine


def make_game():
    game = Game([("p1", "P1"), ("p2", "P2")])
    for p in game.players:
        p.organizations = {}
    return game


def test_any_inner_semantic_pool_comes_from_map_ruler_data_only():
    game = make_game()
    faction = {"id": "red_army", "bases": ["任意牆內"]}

    towns = game._base_option_to_towns(faction, "任意牆內")
    expected = [
        town
        for town in game._towns_for_region_alias("china")
        if game.can_faction_develop_in_town("red_army", town)
    ]

    assert towns == expected
    assert "北京" in towns
    assert "香港城" in towns


def test_any_inner_resolution_ignores_legacy_board_regions_shadow_attr():
    game = make_game()
    faction = {"id": "red_army", "bases": ["任意牆內"]}
    original = game._base_option_to_towns(faction, "任意牆內")

    game.board_regions = {"china": {"towns": ["假城鎮"]}}

    resolved = game._base_option_to_towns(faction, "任意牆內")

    assert resolved == original
    assert "假城鎮" not in resolved


def test_victory_engine_constructor_no_longer_requires_board_regions_argument():
    game = make_game()
    red_player = next(p for p in game.players if p.faction_id == "red_army")
    taiwan_player = next(p for p in game.players if p is not red_player)
    taiwan_player.faction_id = "taiwan_green"
    red_player.organizations = {town: 1 for town in game._towns_for_region_alias("taiwan")[:14]}

    did_win, winner = VictoryEngine(game.factions).evaluate(game)

    assert did_win is True
    assert winner == "red_army"
