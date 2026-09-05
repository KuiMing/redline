from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "static" / "app.js"


def test_red_army_results_use_the_shared_modal_without_peer_notice_duplication():
    source = APP_JS.read_text(encoding="utf-8")

    assert "const RED_ARMY_RESULT_ACTION_NAMES = new Set(['統戰部', '政工部', '國安部', '中紀委']);" in source
    assert "const SHARED_RESULT_MODAL_ACTION_NAMES = new Set([" in source
    assert "if (SHARED_RESULT_MODAL_ACTION_NAMES.has(sharedResultName))" in source
    assert "closePeerActionNotice(entries);" in source
    assert "const usesSharedResultModal = SHARED_RESULT_MODAL_ACTION_NAMES.has(result.name)" in source