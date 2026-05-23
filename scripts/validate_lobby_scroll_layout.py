#!/usr/bin/env python3
"""Validate that the lobby can scroll when faction setup content exceeds the fixed stage."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "static" / "style.css"
RECORD_DIR = ROOT / "docs" / "records" / "lobby"
JSON_OUT = RECORD_DIR / "LOBBY_SCROLL_LAYOUT_VALIDATION.json"
MD_OUT = RECORD_DIR / "LOBBY_SCROLL_LAYOUT_VALIDATION.md"


def block_for(selector: str, css: str) -> str:
    marker = f"{selector} {{"
    start = css.find(marker)
    if start == -1:
        return ""
    depth = 0
    for idx in range(start, len(css)):
        if css[idx] == "{":
            depth += 1
        elif css[idx] == "}":
            depth -= 1
            if depth == 0:
                return css[start : idx + 1]
    return ""


def main() -> None:
    css = STYLE.read_text(encoding="utf-8")
    lobby = block_for("#lobby", css)
    checks = [
        {
            "name": "lobby_uses_vertical_scroll",
            "passed": "overflow-y: auto" in lobby,
            "detail": "#lobby must allow vertical scrolling for tall faction setup/detail content.",
        },
        {
            "name": "lobby_keeps_horizontal_clip",
            "passed": "overflow-x: hidden" in lobby,
            "detail": "#lobby should still avoid horizontal spill while allowing vertical scroll.",
        },
        {
            "name": "lobby_scroll_contained",
            "passed": "overscroll-behavior: contain" in lobby,
            "detail": "Scroll gestures should stay inside the fixed 1280x720 lobby stage.",
        },
        {
            "name": "lobby_no_single_overflow_hidden_shorthand",
            "passed": "overflow: hidden" not in lobby,
            "detail": "A single overflow:hidden on #lobby clips the faction picker bottom on smaller screens.",
        },
    ]
    passed = sum(1 for check in checks if check["passed"])
    failed = len(checks) - passed
    result = {
        "summary": {"total": len(checks), "passed": passed, "failed": failed},
        "checks": checks,
        "notes": "Validates the lobby/faction picker scroll fix for overflowing faction detail content.",
    }
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Lobby scroll layout validation",
        "",
        f"- total: {len(checks)}",
        f"- passed: {passed}",
        f"- failed: {failed}",
        "",
        "## Checks",
    ]
    for check in checks:
        mark = "✅" if check["passed"] else "❌"
        lines.append(f"- {mark} `{check['name']}` — {check['detail']}")
    lines.append("")
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
