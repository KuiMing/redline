#!/usr/bin/env python3
"""Validate that the lobby clearly exposes room-code join/share UI."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "static" / "index.html"
APP = ROOT / "static" / "app.js"
STYLE = ROOT / "static" / "style.css"
RECORD_DIR = ROOT / "docs" / "records" / "lobby"
JSON_OUT = RECORD_DIR / "LOBBY_JOIN_ROOM_CODE_UI_VALIDATION.json"
MD_OUT = RECORD_DIR / "LOBBY_JOIN_ROOM_CODE_UI_VALIDATION.md"


def main() -> None:
    index = INDEX.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    style = STYLE.read_text(encoding="utf-8")
    checks = [
        {
            "name": "room_code_label_mentions_join",
            "passed": "建立 / 加入房間代碼" in index,
            "detail": "The room-code field label must tell non-host players this is also where they paste a room code.",
        },
        {
            "name": "room_code_placeholder_explains_paste",
            "passed": "貼上房間代碼" in index and "建立新作戰室" in index,
            "detail": "Placeholder must explain both paste-to-join and create-room flows.",
        },
        {
            "name": "join_helper_text_visible",
            "passed": "要加入別人的房間" in index and "進入作戰室" in index and "lobby-field-hint" in style,
            "detail": "A visible helper line must tell another player to paste the shared code then press enter/join room.",
        },
        {
            "name": "join_room_trims_code",
            "passed": "value || '').trim()" in app and "roomInput.value = gameId" in app,
            "detail": "joinRoom() should trim copied room codes and write the trimmed value back to the field.",
        },
        {
            "name": "join_room_empty_feedback",
            "passed": "請先把房間代碼貼到" in app,
            "detail": "Pressing join with an empty field should show clear in-page feedback instead of sending an empty request.",
        },
        {
            "name": "no_duplicate_top_room_code_banner",
            "passed": "lobbyRoomBanner" not in index and "lobbyRoomBannerCode" not in index and "lobby-room-banner" not in style,
            "detail": "Playtest feedback: a second top banner duplicating the room-code input's display was itself redundant screen space, not just a duplicate copy button — the banner was removed entirely rather than kept as a read-only display.",
        },
        {
            "name": "copy_fallback_selects_room_code",
            "passed": "selectRoomCodeForManualCopy" in app and "已選取房間代碼" in app and "Ctrl+C / ⌘C" in app,
            "detail": "If automatic copy is blocked, fallback should select the full room code and give explicit manual-copy instructions.",
        },
        {
            "name": "copy_uses_exec_command_before_clipboard_api",
            "passed": "function copyRoomIdWithExecCommand" in app and "document.execCommand" in app and app.find("copyRoomIdWithExecCommand(roomIdValue)") < app.find("navigator.clipboard.writeText"),
            "detail": "Copy should first use a click-gesture execCommand path so LAN/http browsers can copy even when navigator.clipboard is unavailable.",
        },
        {
            "name": "copy_records_runtime_result_for_browser_proof",
            "passed": "window.__lastRoomCopyResult" in app and "method: 'execCommand'" in app and "method: 'manual-select'" in app,
            "detail": "Browser proof can inspect the last copy result to distinguish real automatic copy from manual-select fallback.",
        },
        {
            "name": "copy_status_survives_lobby_sync",
            "passed": "lobbyTransientStatus" in app and "hint.textContent = transient || deriveLobbyHint" in app,
            "detail": "The copied/manual-select status should stay visible instead of being overwritten by the lobby polling refresh.",
        },
        {
            "name": "confirm_faction_bar_remains_clickable",
            "passed": "#factionConfirmBar" in style and "bottom: 0" in style and "確認陣營" in index,
            "detail": "Long faction details should keep the confirm-faction button sticky inside the faction panel instead of under the fixed action bar.",
        },
        {
            "name": "faction_panel_stays_bounded_and_scrollable",
            "passed": ".lobby-faction-panel" in style and "#factionPicker" in style and style.count("max-height: 190px") >= 2,
            "detail": "The faction panel and picker must stay height-bounded with internal scroll instead of growing the lobby card unbounded.",
        },
    ]
    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed
    result = {"summary": {"total": len(checks), "passed": passed, "failed": failed}, "checks": checks}
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Lobby join room-code UI validation", "", f"- total: {len(checks)}", f"- passed: {passed}", f"- failed: {failed}", "", "## Checks"]
    for c in checks:
        lines.append(f"- {'✅' if c['passed'] else '❌'} `{c['name']}` — {c['detail']}")
    lines.append("")
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
