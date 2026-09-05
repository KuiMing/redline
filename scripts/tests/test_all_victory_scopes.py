from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.game import Game


def make_game(actor_faction="liberals", include_taiwan=False):
    players = [("actor", "actor"), ("red", "red")]
    if include_taiwan:
        players.append(("taiwan", "taiwan"))
    game = Game(players, market_mode="all_cards")
    actor = game.players[0]
    actor.id = "actor"
    actor.name = "actor"
    actor.faction_id = actor_faction
    actor.organizations = {}
    red = game.players[1]
    red.id = "red"
    red.name = "red"
    red.faction_id = "red_army"
    red.organizations = {}
    if include_taiwan:
        taiwan = game.players[2]
        taiwan.id = "taiwan"
        taiwan.name = "taiwan"
        taiwan.faction_id = "taiwan_green"
        taiwan.organizations = {}
    return game, actor, red


def faction(game, faction_id):
    return game.faction_by_id[faction_id]


def inside_towns(game):
    return [town for town in game.map["towns"] if game._is_inside_wall_town(town)]


def outside_towns(game):
    return [town for town in game.map["towns"] if not game._is_inside_wall_town(town)]


def set_orgs(player, towns):
    player.organizations = {town: 1 for town in dict.fromkeys(towns)}


def complete_locations(condition):
    locations = list(condition.get("required_locations") or [])
    for group in condition.get("required_any_of") or []:
        locations.append(group[0])
    return locations


def fill_distinct(seed, pool, count):
    result = list(dict.fromkeys(seed))
    for town in pool:
        if town not in result:
            result.append(town)
        if len(result) >= count:
            break
    assert len(result) >= count
    return result


def wall_count_only_factions(game):
    return [
        row["id"]
        for row in game.faction_by_id.values()
        if any(
            condition.get("type") == "count_only" and condition.get("scope") == "牆內"
            for condition in row.get("win_conditions", [])
        )
    ]


@pytest.mark.parametrize("faction_id", wall_count_only_factions(make_game()[0]))
def test_every_inside_wall_count_only_victory_rejects_outside_and_honors_boundary(faction_id):
    game, actor, _red = make_game(faction_id)
    condition = next(
        condition for condition in faction(game, faction_id)["win_conditions"]
        if condition.get("type") == "count_only" and condition.get("scope") == "牆內"
    )
    required = condition["count"]
    inside = inside_towns(game)
    outside = outside_towns(game)
    assert len(inside) >= required and len(outside) >= required

    set_orgs(actor, outside[:required])
    assert game.victory_engine._check_player_conditions(actor, game)[0] is False

    set_orgs(actor, inside[: required - 1])
    assert game.victory_engine._check_player_conditions(actor, game)[0] is False

    set_orgs(actor, inside[:required])
    assert game.victory_engine._check_player_conditions(actor, game) == (True, actor.name)


@pytest.mark.parametrize("faction_id", ["republican", "chaoxian"])
def test_inside_wall_required_location_victories_keep_scope_and_location_requirements(faction_id):
    game, actor, _red = make_game(faction_id)
    condition = faction(game, faction_id)["win_conditions"][0]
    required_count = condition["count"]
    mandatory = complete_locations(condition)
    inside = inside_towns(game)
    outside = outside_towns(game)
    scoped_mandatory = [town for town in mandatory if game._is_inside_wall_town(town)]
    outside_mandatory = [town for town in mandatory if not game._is_inside_wall_town(town)]

    winning_inside = fill_distinct(scoped_mandatory, inside, required_count)
    set_orgs(actor, winning_inside + outside_mandatory)
    assert game.victory_engine._check_player_conditions(actor, game) == (True, actor.name)

    set_orgs(actor, winning_inside[:-1] + outside_mandatory)
    assert game.victory_engine._check_player_conditions(actor, game)[0] is False

    missing_required = mandatory[0]
    replacements = [town for town in inside + outside if town not in mandatory]
    replacement = next(town for town in replacements if town not in actor.organizations)
    set_orgs(actor, [town for town in winning_inside + outside_mandatory if town != missing_required] + [replacement])
    assert game.victory_engine._check_player_conditions(actor, game)[0] is False


def test_every_global_count_and_required_victory_honors_count_and_required_locations():
    game, _actor, _red = make_game()
    all_towns = list(game.map["towns"])
    conditions = [
        (row["id"], condition)
        for row in game.faction_by_id.values()
        for condition in row.get("win_conditions", [])
        if condition.get("type") == "count_and_required" and condition.get("scope") == "牆內與牆外"
    ]
    assert conditions

    for faction_id, condition in conditions:
        local, actor, _red = make_game(faction_id)
        mandatory = complete_locations(condition)
        required_count = condition["count"]
        winning = fill_distinct(mandatory, all_towns, required_count)
        set_orgs(actor, winning)
        assert local.victory_engine._check_player_conditions(actor, local) == (True, actor.name), faction_id

        set_orgs(actor, winning[:-1])
        assert local.victory_engine._check_player_conditions(actor, local)[0] is False, faction_id

        missing_required = mandatory[0]
        replacement = next(town for town in all_towns if town not in winning)
        set_orgs(actor, [town for town in winning if town != missing_required] + [replacement])
        assert len(actor.organizations) == required_count
        assert local.victory_engine._check_player_conditions(actor, local)[0] is False, faction_id


def test_kazakh_completed_condition_precedes_turn20_red_survival_fallback():
    game, actor, _red = make_game("kazakh")
    condition = faction(game, "kazakh")["win_conditions"][0]
    assert condition == {
        "type": "count_and_required",
        "scope": "牆內與牆外",
        "count": 19,
        "required_locations": ["阿勒泰", "塔城", "伊寧"],
    }
    winning = fill_distinct(condition["required_locations"], list(game.map["towns"]), condition["count"])
    set_orgs(actor, winning)
    game.turn = 21

    assert game.victory_engine._check_player_conditions(actor, game) == (True, actor.name)
    assert game.victory_engine.evaluate(game) == (True, actor.name)


def test_red_taiwan_override_requires_taiwan_player_and_fourteen_taiwan_organizations():
    game, _actor, red = make_game(include_taiwan=False)
    taiwan_towns = list(game.towns_by_ruler["臺灣"])
    assert len(taiwan_towns) >= 14
    set_orgs(red, taiwan_towns[:14])
    assert game.victory_engine._check_player_conditions(red, game)[0] is False

    game, _actor, red = make_game(include_taiwan=True)
    taiwan_towns = list(game.towns_by_ruler["臺灣"])
    red.organizations = {taiwan_towns[0]: 14}
    assert game.victory_engine._check_player_conditions(red, game)[0] is False

    set_orgs(red, taiwan_towns[:13])
    assert game.victory_engine._check_player_conditions(red, game)[0] is False
    red.organizations[taiwan_towns[13]] = 1
    assert game.victory_engine._check_player_conditions(red, game) == (True, "red_army")


def test_wan_expansion_condition_counts_南陽_and_the_20_wan_map_towns():
    from server.victory import WAN_EXPANSION_TOWNS

    game, actor, _red = make_game("wan")
    assert len(WAN_EXPANSION_TOWNS) == 21
    assert "南陽" in WAN_EXPANSION_TOWNS
    assert WAN_EXPANSION_TOWNS <= set(game.map["towns"])

    # Orgs outside the scope don't count, even with plenty of them.
    outside_scope_towns = [town for town in game.map["towns"] if town not in WAN_EXPANSION_TOWNS]
    set_orgs(actor, outside_scope_towns[:20])
    assert game.victory_engine._count_scope(actor, "宛地", game) == 0
    assert game.victory_engine._check_player_conditions(actor, game)[0] is False

    # 13 orgs inside the scope: not yet enough.
    scope_towns = sorted(WAN_EXPANSION_TOWNS)
    set_orgs(actor, scope_towns[:13])
    assert game.victory_engine._count_scope(actor, "宛地", game) == 13
    assert game.victory_engine._check_player_conditions(actor, game)[0] is False

    # 14 orgs spread across the scope (南陽 + wan-expansion towns): condition met.
    set_orgs(actor, scope_towns[:14])
    assert game.victory_engine._count_scope(actor, "宛地", game) == 14
    assert game.victory_engine._check_player_conditions(actor, game) == (True, actor.name)


def test_every_runtime_victory_scope_is_explicitly_supported():
    game, _actor, _red = make_game()
    supported = {"牆內", "牆內與牆外", "宛地"}
    scopes = {
        condition["scope"]
        for row in game.faction_by_id.values()
        for condition in row.get("win_conditions", [])
        if condition.get("scope")
    }
    assert scopes <= supported
