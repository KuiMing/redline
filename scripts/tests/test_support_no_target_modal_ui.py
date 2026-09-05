from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "static" / "app.js"
RAW_ERROR = "No legal target for interactive support card"


def function_source(source: str, name: str) -> str:
    """Return one named JS function using balanced braces, not a whole-file substring."""
    match = re.search(rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"missing function {name}"
    start = match.start()
    brace = match.end() - 1
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(brace, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated function {name}")


def test_action_click_records_a_local_support_play_attempt_before_sending() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    play = function_source(source, "playHandCard")
    assert "recordSupportCardPlayAttempt(cardName, mode, state)" in play
    assert play.index("recordSupportCardPlayAttempt(cardName, mode, state)") < play.index("sendAction('play_card', payload)")

    recorder = function_source(source, "recordSupportCardPlayAttempt")
    assert "supportCardPlayAttemptSequence += 1" in recorder
    assert "cardName" in recorder
    assert "mode !== 'action'" in recorder


def test_raw_no_target_error_has_attempt_aware_modal_contract() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    handler = function_source(source, "showSupportNoTargetModal")

    assert f"state.error !== '{RAW_ERROR}'" in handler
    assert "showActionMessageModal(" in handler
    assert "'東洋奧援無法使用'" in handler
    assert "'奧援卡無法使用'" in handler
    assert "playerMessageZhTw(state.error)" in handler
    assert "lastShownSupportNoTargetAttemptSequence" in handler
    assert "supportCardPlayAttemptSequence" in handler


def test_special_case_returns_before_generic_modal_sink() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    render = function_source(source, "render")

    assert "showSupportNoTargetModal(state)" in render
    assert "showPlayerErrorModal(state, playerError)" in render
    assert "alert(playerError)" not in render
    special_index = render.index("showSupportNoTargetModal(state)")
    generic_index = render.index("showPlayerErrorModal(state, playerError)")
    assert special_index < generic_index
    assert re.search(
        r"if \(showSupportNoTargetModal\(state\)\)\s*\{[^}]*syncPlayerErrorToStrategicMap\(playerError\);[^}]*\}\s*else",
        render,
        re.DOTALL,
    ), "special support error must be handled in an exclusive branch before the generic modal"
