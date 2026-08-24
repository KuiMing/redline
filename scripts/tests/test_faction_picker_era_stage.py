from server.main import (
    canonical_inside_wall_towns,
    choose_faction,
    list_factions,
    lobby,
    lobby_bases,
    lobby_factions,
    lobby_ready,
)


def _option(categories, category_id, option_id=None):
    category = next(item for item in categories if item["id"] == category_id)
    if option_id is None:
        return category["options"][0]
    return next(item for item in category["options"] if item["id"] == option_id)


def test_faction_catalog_projects_personal_era_stage_for_every_non_red_camp():
    categories = list_factions()["categories"]
    expected = {
        "taiwan": "[臺灣]綏靖派反對介入對岸",
        "hong_kong": "[香港]香港人被自殺",
        "uyghur": "[維吾爾]莎車大屠殺",
        "tibet": "[藏國]藏國騷亂",
        "manchuria": "[滿洲]滿洲地方派系凝聚",
        "mongol": "[蒙古]莫日根事件爆發",
        "kazakh": "[哈薩克]伊塔事件",
        "rebel": "[反賊]公知世代的終結",
    }
    for category_id, era_name in expected.items():
        category = next(item for item in categories if item["id"] == category_id)
        for option in category["options"]:
            stage = option.get("era_stage")
            assert stage and stage["name"] == era_name, (category_id, option["id"])
            assert stage["trigger_text"]
            assert stage["success_text"]
            assert stage["fail_text"]
    assert not _option(categories, "red_army").get("era_stage")


def test_show_strength_catalog_wording_uses_comma_and_player_choice_copy():
    categories = list_factions()["categories"]
    manchuria = _option(categories, "manchuria")
    ability = next(item for item in manchuria["abilities"] if item.get("name") == "展現實力")
    assert ability["trigger"] == "在己方行動階段打出至少3張不同名稱的非起始牌"
    assert ability["effect"] == "獲得3點宣傳或3點資金"

    rebel = _option(categories, "rebel", "xiang")
    text = next(item for item in rebel["abilities_text"] if "展現實力" in item)
    assert text == "【展現實力】在己方行動階段打出至少3張不同名稱的非起始牌，獲得3點宣傳或3點資金"
    assert "則可" not in text


def test_any_inside_wall_base_expands_to_canonical_map_towns_only():
    categories = list_factions()["categories"]
    inside_wall = set(canonical_inside_wall_towns())
    assert inside_wall
    assert "任意牆內" not in inside_wall
    assert "任意牆內城鎮" not in inside_wall

    for option_id in ["republican", "underground_church"]:
        option = _option(categories, "rebel", option_id)
        semantic_key = next(key for key in option["base_resolved"] if key in {"任意牆內", "任意牆內城鎮"})
        assert set(option["base_resolved"][semantic_key]) == inside_wall


def test_choose_faction_rejects_a_base_already_selected_by_another_player():
    game_id = "occupied-base-unit-proof"
    p1, p2, red = "p1", "p2", "red"
    lobby[game_id] = [(p1, "P1"), (p2, "P2"), (red, "Red")]
    lobby_factions[game_id] = {red: "red_army"}
    lobby_bases[game_id] = {red: "北京"}
    lobby_ready[game_id] = {}
    try:
        first = choose_faction({"game_id": game_id, "player_id": p1, "faction_id": "manchuria", "base_name": "東京"})
        assert first.get("success") is True

        occupied = choose_faction({"game_id": game_id, "player_id": p2, "faction_id": "mongol", "base_name": "東京"})
        assert occupied == {"error": "Base already taken"}
        assert p2 not in lobby_factions[game_id]
        assert p2 not in lobby_bases[game_id]

        available = choose_faction({"game_id": game_id, "player_id": p2, "faction_id": "mongol", "base_name": "紐約"})
        assert available.get("success") is True
    finally:
        lobby.pop(game_id, None)
        lobby_factions.pop(game_id, None)
        lobby_bases.pop(game_id, None)
        lobby_ready.pop(game_id, None)
