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
            "name": "top_banner_exists_after_room_created",
            "passed": "id=\"lobbyRoomBanner\"" in index and "房間代碼" in index and "分享給其他玩家加入" in index,
            "detail": "Lobby must include a top room-code banner so the created room code stays visible above faction selection.",
        },
        {
            "name": "top_banner_syncs_from_game_id",
            "passed": "currentRoomCode()" in app and "lobbyRoomBannerCode" in app and "room-active" in app,
            "detail": "The banner must sync from the active game id and toggle lobby room-active spacing when a room exists.",
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
            "name": "banner_is_top_sticky_not_covering_actions",
            "passed": "position: sticky" in style and ".lobby-room-banner" in style and "#lobby.room-active .lobby-brand" in style and "max-height: 190px" in style,
            "detail": "The banner must be placed at the top of the lobby and reserve visual space instead of overlapping faction/action controls.",
        },
        {
            "name": "confirm_faction_bar_remains_clickable",
            "passed": "#factionConfirmBar" in style and "bottom: 0" in style and "確認陣營" in index,
            "detail": "Long faction details should keep the confirm-faction button sticky inside the faction panel instead of under the fixed action bar.",
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
