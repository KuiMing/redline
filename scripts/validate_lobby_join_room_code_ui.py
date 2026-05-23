#!/usr/bin/env python3
"""Validate that the lobby clearly exposes room-code join UI."""

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
