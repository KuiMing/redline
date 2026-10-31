from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_LOGIC = (ROOT / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")
MAP_HTML = (ROOT / "static" / "leaflet_game_map.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")


def test_shared_organization_uses_yellow_town_circle_without_s_badge():
    assert "color: '#facc15'" in MAP_LOGIC
    assert "hasShared ? '#facc15'" in MAP_LOGIC
    assert "shared-badge" not in MAP_LOGIC
    assert ".shared-badge" not in MAP_HTML
    assert "S 標記" not in MAP_LOGIC
    assert "黃色圓圈" in MAP_LOGIC


def test_map_asset_versions_match():
    version = "contextual-route-highlight-20261004"
    assert f"leaflet_game_map_logic.js?v={version}" in MAP_HTML
    assert f"url.searchParams.set('v', '{version}')" in APP_JS