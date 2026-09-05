from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "static" / "app.js"


def test_shared_faction_result_modal_closes_when_current_player_changes():
    source = APP_JS.read_text(encoding="utf-8")

    assert "let activeSharedFactionActionResult = null;" in source
    assert "function closeSharedFactionActionResultOnTurnHandoff(state)" in source
    assert "active.currentPlayer !== (state.current_player || '')" in source
    assert "title?.textContent === active.title" in source
    assert "closeUnavailableActionModal();" in source
    assert "closeSharedFactionActionResultOnTurnHandoff(state);" in source
    assert "currentPlayer: state.current_player || ''" in source