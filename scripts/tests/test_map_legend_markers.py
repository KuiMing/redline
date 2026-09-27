from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_HTML = ROOT / "static" / "leaflet_game_map.html"


def test_map_legend_keeps_route_keys_and_removes_town_state_explanations():
    html = MAP_HTML.read_text(encoding="utf-8")
    legend_start = html.index('<div class="legend">')
    legend_end = html.index("</div>", legend_start)
    legend = html[legend_start:legend_end]

    assert "一般道路：金色" in legend
    assert "鐵路：紅色虛線" in legend
    assert "已選城鎮" not in legend
    assert "候選城鎮" not in legend
    assert "可選城鎮" not in legend
    assert "legend-town-marker" not in html
    assert "<h1>逆統戰</h1>" not in html
    assert "h1 {" not in html
    assert 'id="exportView"' not in html
    assert "匯出畫面" not in html
    assert '<button id="focusBase">根據地</button>' in html


def test_selected_town_brightens_connected_routes_and_uses_red_rail():
    logic = (ROOT / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")

    assert "poly.__redlineRoute = { source: link.source, target: link.target, type: link.type };" in logic
    assert "function highlightConnectedRoutes(townName)" in logic
    assert "route.source === townName || route.target === townName" in logic
    assert "color: '#d8a04a', opacity: 0.9" in logic
    assert "color: '#ef4444', opacity: 0.9" in logic
    assert "weight: roadWeight(map.getZoom())" in logic
    assert "weight: railWeight(map.getZoom())" in logic
    assert "roadWeight(map.getZoom()) +" not in logic
    assert "railWeight(map.getZoom()) +" not in logic
    assert "color:'#ef4444'" in logic
    assert "color: '#ef4444'" in logic
    assert "#42667a" not in logic


def test_organization_actions_are_above_focus_controls_in_sidebar():
    html = MAP_HTML.read_text(encoding="utf-8")

    assert html.index('id="organizationActionsCard"') < html.index('id="focusControlsCard"')


def test_base_toolbar_action_focuses_viewers_base():
    logic = (ROOT / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")

    assert "function focusOwnBase()" in logic
    assert "const me = currentPlayerState();" in logic
    assert "document.getElementById('focusBase').addEventListener('click', focusOwnBase);" in logic
