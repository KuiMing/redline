from server import main
from server.faction_presentation import (
    build_faction_presentation,
    canonical_inside_wall_towns,
    faction_base_options,
    faction_base_resolved,
    faction_category,
    semantic_base_pool,
)


def test_faction_presentation_keeps_route_payload_and_category_order():
    payload = build_faction_presentation()

    assert main.list_factions() == payload
    assert [category["id"] for category in payload["categories"]] == [
        "red_army",
        "taiwan",
        "hong_kong",
        "uyghur",
        "tibet",
        "manchuria",
        "mongol",
        "kazakh",
        "rebel",
    ]


def test_main_keeps_faction_presentation_compatibility_exports():
    assert main.canonical_inside_wall_towns is canonical_inside_wall_towns
    assert main.faction_base_options is faction_base_options
    assert main.faction_base_resolved is faction_base_resolved
    assert main.faction_category is faction_category
    assert main.semantic_base_pool is semantic_base_pool


def test_semantic_base_pools_and_family_categories_are_preserved():
    inside_wall = canonical_inside_wall_towns()

    assert inside_wall
    assert semantic_base_pool("任意牆內") == list(inside_wall)
    assert semantic_base_pool("不存在的語意根據地") == []
    assert faction_category("uyghur_washington") == "uyghur"
    assert faction_category("tibet_chogu") == "tibet"
    assert faction_category("xiang") == "rebel"
