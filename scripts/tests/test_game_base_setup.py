from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game
from server.game_base_setup import (
    classify_base_options,
    resolve_starting_base,
    base_option_to_towns,
    candidate_base_names,
)


def _new_game():
    return Game([("p1", "A"), ("p2", "B")])


def _always_true(faction_id, town):
    return True


def _always_false(faction_id, town):
    return False


def test_classify_base_options_fixed_faction():
    game = _new_game()
    faction = game.faction_by_id["red_army"]
    assert game._classify_base_options(faction) == classify_base_options(faction)
    kind, names = classify_base_options(faction)
    assert kind == "fixed"
    assert names == ["北京"]


def test_classify_base_options_special_faction():
    game = _new_game()
    faction = game.faction_by_id["hong_kong"]
    assert game._classify_base_options(faction) == classify_base_options(faction)
    kind, _ = classify_base_options(faction)
    assert kind == "special"


def test_classify_base_options_flex_faction():
    game = _new_game()
    faction = game.faction_by_id["liberals"]
    assert game._classify_base_options(faction) == classify_base_options(faction)
    kind, names = classify_base_options(faction)
    assert kind == "flex"
    assert names == ["任意牆內城鎮"]


def test_resolve_starting_base_matches_game_method_for_fixed_faction():
    game = _new_game()
    faction = game.faction_by_id["red_army"]
    expected = game._resolve_starting_base(faction, set())
    actual = resolve_starting_base(
        game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction, set()
    )
    assert expected == actual == "北京"


def test_resolve_starting_base_matches_game_method_for_flex_faction():
    game = _new_game()
    faction = game.faction_by_id["liberals"]
    expected = game._resolve_starting_base(faction, set())
    actual = resolve_starting_base(
        game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction, set()
    )
    assert expected == actual
    assert actual is not None


def test_resolve_starting_base_respects_used_set():
    game = _new_game()
    faction = game.faction_by_id["red_army"]
    result = resolve_starting_base(
        game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction, {"北京"}
    )
    assert result is None


def test_resolve_starting_base_none_when_can_develop_always_false():
    game = _new_game()
    faction = game.faction_by_id["red_army"]
    result = resolve_starting_base(game.map, game.towns_by_ruler, _always_false, faction, set())
    assert result is None


def test_base_option_to_towns_matches_game_method_for_special_faction():
    game = _new_game()
    faction = game.faction_by_id["hong_kong"]
    expected = game._base_option_to_towns(faction, "香港城")
    actual = base_option_to_towns(
        game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction, "香港城"
    )
    assert expected == actual == ["香港城"]


def test_base_option_to_towns_matches_game_method_for_semantic_label():
    game = _new_game()
    faction = game.faction_by_id["liberals"]
    expected = game._base_option_to_towns(faction, "任意牆內城鎮")
    actual = base_option_to_towns(
        game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction, "任意牆內城鎮"
    )
    assert expected == actual
    assert len(actual) > 0


def test_base_option_to_towns_empty_when_can_develop_always_false():
    game = _new_game()
    faction = game.faction_by_id["liberals"]
    result = base_option_to_towns(
        game.map, game.towns_by_ruler, _always_false, faction, "任意牆內城鎮"
    )
    assert result == []


def test_candidate_base_names_matches_game_method_for_fixed_faction():
    game = _new_game()
    faction = game.faction_by_id["red_army"]
    expected = game._candidate_base_names(faction)
    actual = candidate_base_names(game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction)
    assert expected == actual == ["北京"]


def test_candidate_base_names_matches_game_method_for_flex_faction():
    game = _new_game()
    faction = game.faction_by_id["liberals"]
    expected = game._candidate_base_names(faction)
    actual = candidate_base_names(game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction)
    assert expected == actual
    assert len(actual) > 0


def test_candidate_base_names_uyghur_family_bypasses_classification():
    game = _new_game()
    faction = game.faction_by_id.get("uyghur_family")
    if faction is None:
        return
    expected = game._candidate_base_names(faction)
    actual = candidate_base_names(game.map, game.towns_by_ruler, game.can_faction_develop_in_town, faction)
    assert expected == actual
    raw_names = [b.get("name") for b in faction.get("bases", []) if b.get("name")]
    assert actual == raw_names
