from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_map_action_buttons_use_short_labels():
    html = (ROOT / "static" / "leaflet_game_map.html").read_text(encoding="utf-8")
    logic = (ROOT / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")

    assert '<button id="directBuildBtn" disabled>建立組織</button>' in html
    assert '<button id="dissolveBtn" disabled>瓦解組織</button>' in html
    assert "btn.textContent = '建立組織';" in logic
    assert "dissolveBtn.textContent = '瓦解組織';" in logic
    assert "在目前城鎮建立組織（效果）" not in logic
    assert "瓦解目前城鎮組織" not in logic
