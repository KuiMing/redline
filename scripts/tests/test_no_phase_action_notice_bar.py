from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "static" / "app.js"
INDEX_HTML = ROOT / "static" / "index.html"
STYLE_CSS = ROOT / "static" / "style.css"


def test_top_notice_bar_is_removed_from_dom_css_and_javascript():
    app = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    for obsolete in ("phaseActionBar", "phaseActionControls", "phaseActionNotice"):
        assert obsolete not in app
        assert obsolete not in html
        assert obsolete not in css
    assert "setPhaseActionNotice" not in app
    assert "showStickyPlayerErrorNotice" not in app
    assert "stickyPlayerErrorNotice" not in app
    assert "stickyPlayerErrorTimer" not in app


def test_previous_notice_sinks_have_explicit_replacements():
    app = APP_JS.read_text(encoding="utf-8")

    assert "showActionMessageModal('無法打出手牌', message);" in app
    assert "showActionMessageModal('企業人脈結果', message);" in app
    assert "typeof result?.chosen_card === 'string'" in app
    assert "Number.isInteger(result.purchase_index)" in app
    assert "const slotText = result.zone_label || '購買區';" in app
    assert "showPlayerErrorModal(state, playerError);" in app
    assert "outboundActionSequence += 1;" in app
    assert "outboundActionSequence," in app
    assert "alert(playerError)" not in app
    assert "等待其他玩家選擇根據地" in app
    assert "waitingForOtherBaseSelections" in app
