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


def test_hong_kong_fixed_base_resolves_to_map_json_town_name():
    game = make_game()
    hong_kong = game.faction_by_id["hong_kong"]

    resolved = game._base_option_to_towns(hong_kong, "香港城")

    assert resolved == ["香港城"]


def test_any_inner_uses_map_ruler_red_army_not_legacy_board_region_names():
    game = make_game()
    faction = {"id": "red_army", "bases": ["任意牆內"]}

    towns = game._base_option_to_towns(faction, "任意牆內")

    assert "北京" in towns
    assert "香港城" not in towns
    assert "上水" not in towns


def test_count_only_era_trigger_uses_map_ruler_scope():
    game = make_game()
    player = game.players[0]
    player.faction_id = "hong_kong"
    player.organizations = {"香港城": 10}

    trigger = {"type": "count_only", "faction_id": "hong_kong", "region": "hong_kong", "count": 10}

    assert game._evaluate_era_trigger(trigger) is True


def test_red_army_taiwan_override_uses_map_ruler_taiwan_towns():
    game = make_game()
    red_player = next(p for p in game.players if p.faction_id == "red_army")
    red_player.organizations = {"臺北": 14}

    did_win, winner = VictoryEngine(game.factions, {}).evaluate(game)

    assert did_win is True
    assert winner == "red_army"