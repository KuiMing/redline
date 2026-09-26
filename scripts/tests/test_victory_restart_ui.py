from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "static" / "index.html"
STYLE_CSS = ROOT / "static" / "style.css"


def test_victory_modal_places_restart_link_next_to_final_board_button():
    html = INDEX_HTML.read_text(encoding="utf-8")
    actions_start = html.index('<div class="era-achievement-actions">', html.index('id="victoryModal"'))
    actions_end = html.index("</div>", actions_start)
    actions = html[actions_start:actions_end]

    final_board = '<button id="victoryMinimizeBtn" class="modal-choice-btn">檢視最終盤面</button>'
    restart = '<a id="victoryRestartBtn" class="modal-choice-btn" href="/new-game">重新開始</a>'

    assert final_board in actions
    assert restart in actions
    assert actions.index(final_board) < actions.index(restart)


def test_victory_restart_link_uses_button_layout_and_no_link_decoration():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".victory-glass > .era-achievement-actions" in css
    assert "display: flex" in css
    assert "#victoryRestartBtn" in css
    assert "text-decoration: none" in css
