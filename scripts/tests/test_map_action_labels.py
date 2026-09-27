from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_LOGIC = ROOT / "static" / "leaflet_game_map_logic.js"


def test_map_action_buttons_use_short_labels():
    source = MAP_LOGIC.read_text(encoding="utf-8")

    assert "btn.textContent = '建立組織';" in source
    assert "dissolveBtn.textContent = '瓦解組織';" in source
    assert "btn.textContent = '在目前城鎮建立組織（效果）';" not in source
    assert "dissolveBtn.textContent = '瓦解目前城鎮組織';" not in source
    assert "使用左側「建立組織」按鈕完成建立" in source
