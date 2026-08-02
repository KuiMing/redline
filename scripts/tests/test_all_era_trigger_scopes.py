from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game


ERA_CASES = [
    ("hong_kong", "hong_kong", 10),
    ("mongolia", "mongol", 4),
    ("tibet", "tibet_dharamsala", 7),
    ("uyghur", "uyghur_istanbul", 7),
    ("manchuria", "manchuria", 10),
    ("rebels", "liberals", 4),
    ("taiwan", "taiwan_green", 7),
]


def make_game(faction_id):
    game = Game([("actor", "actor"), ("red", "red")], market_mode="all_cards")
    actor, red = game.players
    actor.id = "actor"
    actor.name = "actor"
    actor.faction_id = faction_id
    actor.organizations = {}
    red.id = "red"
    red.name = "red"
    red.faction_id = "red_army"
    red.organizations = {}
    return game, actor


def era_definition(game, era_id):
    return next(era for era in game.structured_eras if era["id"] == era_id)


def inside_towns(game):
    return [town for town in game.map["towns"] if game._is_inside_wall_town(town)]


def outside_towns(game):
    return [town for town in game.map["towns"] if not game._is_inside_wall_town(town)]


@pytest.mark.parametrize("era_id,faction_id,count", ERA_CASES)
def test_every_canonical_inside_wall_count_only_era_uses_china_scope(era_id, faction_id, count):
    game, _actor = make_game(faction_id)
    trigger = era_definition(game, era_id)["trigger"]
    assert trigger == {
        "type": "count_only",
        "camp": trigger["camp"],
        "region": "china",
        "count": count,
    }


@pytest.mark.parametrize("era_id,faction_id,count", ERA_CASES)
def test_every_inside_wall_era_rejects_outside_only_and_honors_boundary(era_id, faction_id, count):
    game, actor = make_game(faction_id)
    trigger = era_definition(game, era_id)["trigger"]
    inside = inside_towns(game)
    outside = outside_towns(game)
    assert len(inside) >= count
    assert len(outside) >= count

    actor.organizations = {town: 1 for town in outside[:count]}
    assert game._evaluate_era_trigger(trigger) is False

    actor.organizations = {town: 1 for town in inside[: count - 1]}
    assert game._evaluate_era_trigger(trigger) is False

    actor.organizations[inside[count - 1]] = 1
    assert game._evaluate_era_trigger(trigger) is True


def test_kazakh_era_requires_both_northland_seven_and_inside_wall_three():
    game, actor = make_game("kazakh")
    trigger = era_definition(game, "kazakh")["trigger"]
    assert trigger == {
        "type": "count_and_required",
        "camp": "kazakh",
        "requirements": [
            {"ruler": "北國", "count": 7},
            {"region": "china", "count": 3},
        ],
    }
    northland = [town for town, data in game.map["towns"].items() if "北國" in (data.get("ruler") or [])]
    inside = [town for town in inside_towns(game) if town not in northland]
    outside = [town for town in outside_towns(game) if town not in northland]
    assert len(northland) >= 7 and len(inside) >= 3 and len(outside) >= 3

    actor.organizations = {town: 1 for town in northland[:7] + outside[:3]}
    assert game._evaluate_era_trigger(trigger) is False

    actor.organizations = {town: 1 for town in northland[:7] + inside[:2]}
    assert game._evaluate_era_trigger(trigger) is False

    actor.organizations[inside[2]] = 1
    assert game._evaluate_era_trigger(trigger) is True


def test_raw_era_rows_and_structured_ids_are_complete_and_one_to_one():
    raw_rows = json.loads((ROOT / "data/cards/event_and_era_cards.v1.1.json").read_text())
    in_era = False
    raw_names = []
    for row in raw_rows:
        if not isinstance(row, list) or not row:
            continue
        if row[0] == "時代關卡名稱":
            in_era = True
            continue
        if in_era and row[0]:
            raw_names.append(row[0])
    structured = json.loads((ROOT / "data/era_structured.v1.1.json").read_text())["eras"]
    assert len(raw_names) == 8
    assert len(structured) == 8
    assert {era["name"] for era in structured} == set(raw_names)
