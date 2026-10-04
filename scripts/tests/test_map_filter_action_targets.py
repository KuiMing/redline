from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_LOGIC = (ROOT / "static/leaflet_game_map_logic.js").read_text()
APP_LOGIC = (ROOT / "static/app.js").read_text()
MAP_HTML = (ROOT / "static/leaflet_game_map.html").read_text()


def test_action_target_rings_follow_the_same_visible_town_filter():
    assert "const visibleTownNames = new Set(currentVisible);" in MAP_LOGIC
    assert "if (!visibleTownNames.has(townName)) return;" in MAP_LOGIC
    assert MAP_LOGIC.index("allTargetBounds.push(townBounds);") < MAP_LOGIC.index("if (!visibleTownNames.has(townName)) return;")

    filter_update = "currentVisible = visibleTowns.map(t => t.name);"
    highlight_render = "renderSupportChoiceHighlights();"
    assert MAP_LOGIC.index(filter_update) < MAP_LOGIC.index(highlight_render, MAP_LOGIC.index(filter_update))


def test_hidden_action_targets_are_not_interactive_or_stale_selected():
    assert MAP_LOGIC.count("if (!currentVisible.includes(townName)) return null;") == 2
    assert "if (!town || !currentVisible.includes(townName)) return;" in MAP_LOGIC
    assert "if (selectedTown && !visibleSet.has(selectedTown))" in MAP_LOGIC
    assert "selectedMoveTargets = [];" in MAP_LOGIC
    assert "pendingMoveTarget = null;" in MAP_LOGIC


def test_filtering_keeps_complete_server_target_list_for_restore():
    assert "supportChoiceHighlight.towns" in MAP_LOGIC
    assert "supportChoiceHighlight.towns =" not in MAP_LOGIC
    assert "allTargetBounds.push(townBounds);" in MAP_LOGIC
    assert "focusSupportChoiceTargets(focusedTargetBounds || allTargetBounds);" in MAP_LOGIC


def test_filtered_target_assets_use_the_same_cache_version():
    version = "rail-route-edges-20261004"
    assert f"url.searchParams.set('v', '{version}')" in APP_LOGIC
    assert f"leaflet_game_map_logic.js?v={version}" in MAP_HTML
