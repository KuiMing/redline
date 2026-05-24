#!/usr/bin/env python3
"""Static validator for event-card pending choice map-highlight wiring."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "event-cards"
JSON_OUT = RECORD_DIR / "EVENT_CARD_UI_HIGHLIGHT_VALIDATION.json"
MD_OUT = RECORD_DIR / "EVENT_CARD_UI_HIGHLIGHT_VALIDATION.md"
APP_JS = ROOT / "static" / "app.js"
SERVER_MAIN = ROOT / "server" / "main.py"


def assert_contains(text: str, needle: str, label: str, failures: list[str]) -> None:
    if needle not in text:
        failures.append(f"missing {label}: {needle}")


def main() -> None:
    app = APP_JS.read_text(encoding="utf-8")
    server_main = SERVER_MAIN.read_text(encoding="utf-8")
    failures: list[str] = []
    checks = [
        {
            "name": "event_build_organization town_choice is included in map-highlight allowlist",
            "needle": "new Set(['event_build_organization'])",
            "text": app,
        },
        {
            "name": "build town choices use existing support-targets highlight payload",
            "needle": "mode: 'support-targets'",
            "text": app,
        },
        {
            "name": "build town choices read pending choice towns",
            "needle": "const towns = (choice.towns || []).filter(entry => entry?.town);",
            "text": app,
        },
        {
            "name": "modal explains event build town choices use a two-step map then confirm flow",
            "needle": "兩段式流程：先選城鎮，畫面會切到「戰略地圖」",
            "text": app,
        },
        {
            "name": "event build town choices keep a client-side focused selection before resolving",
            "needle": "choiceModalTwoStepSelection = { index, town };",
            "text": app,
        },
        {
            "name": "event build town choices focus the strategic map before confirmation",
            "needle": "setActiveGameView('map').catch(err => console.warn('Failed to focus strategic map for build choice', err));",
            "text": app,
        },
        {
            "name": "event build town choices require explicit confirm after map focus",
            "needle": "確認建立（請先選城鎮看地圖）",
            "text": app,
        },
        {
            "name": "strategic map iframe is mounted for choice highlight",
            "needle": "ensureStrategicMapMounted().catch(err => console.warn('Failed to mount strategic map for choice highlight', err));",
            "text": app,
        },
        {
            "name": "pending choices suppress faction action overlay during focused proof flows",
            "needle": "if (!inAction || !isMine || hasActivePendingChoice) return;",
            "text": app,
        },
        {
            "name": "Urumqi proof endpoint uses a non-faction-action viewer faction",
            "needle": "viewer.faction_id = \"taiwan_green\"",
            "text": server_main,
        },
    ]
    for check in checks:
        assert_contains(check["text"], check["needle"], check["name"], failures)

    payload = {
        "status": "failed" if failures else "passed",
        "checks": [
            {"name": check["name"], "needle": check["needle"], "status": "passed" if check["needle"] in check["text"] else "failed"}
            for check in checks
        ],
        "failures": failures,
    }
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Event Card UI Highlight Validation", "", f"Status: {payload['status']}", ""]
    for check in payload["checks"]:
        lines.append(f"- {check['status']}: {check['name']}")
    if failures:
        lines.extend(["", "## Failures"])
        lines.extend(f"- {failure}" for failure in failures)
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
