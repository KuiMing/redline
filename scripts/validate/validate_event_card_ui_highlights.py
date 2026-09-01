#!/usr/bin/env python3
"""Static validator for event-card pending choice map-highlight wiring."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "event-cards"
JSON_OUT = RECORD_DIR / "EVENT_CARD_UI_HIGHLIGHT_VALIDATION.json"
MD_OUT = RECORD_DIR / "EVENT_CARD_UI_HIGHLIGHT_VALIDATION.md"
APP_JS = ROOT / "static" / "app.js"
LEAFLET_JS = ROOT / "static" / "leaflet_game_map_logic.js"
SERVER_MAIN = ROOT / "server" / "main.py"


def assert_contains(text: str, needle: str, label: str, failures: list[str]) -> None:
    if needle not in text:
        failures.append(f"missing {label}: {needle}")


def main() -> None:
    app = APP_JS.read_text(encoding="utf-8")
    server_main = SERVER_MAIN.read_text(encoding="utf-8")
    leaflet = LEAFLET_JS.read_text(encoding="utf-8")
    failures: list[str] = []
    checks = [
        {
            "name": "event build town choices are routed through the unified build-map helper",
            "needle": "const isStandardBuildChoice = choice?.interaction_kind === 'build_organization'",
            "text": app,
        },
        {
            "name": "event build town choices use existing support-targets highlight payload",
            "needle": "mode: 'support-targets'",
            "text": app,
        },
        {
            "name": "unified build-map helper includes event build pending choices",
            "needle": "['event_build_organization', 'era_red_build_near_target', 'card_build_organization'].includes(choice?.choice_key)",
            "text": app,
        },
        {
            "name": "event build town choices read pending choice towns with indices",
            "needle": "towns: towns.map((entry, index) => ({",
            "text": app,
        },
        {
            "name": "event build map flow reuses the strategic map tab instead of a two-step modal",
            "needle": "Failed to focus strategic map for event build choice",
            "text": app,
        },
        {
            "name": "map side recognizes event build highlighted towns",
            "needle": "function eventBuildChoiceForTown(townName)",
            "text": leaflet,
        },
        {
            "name": "map direct build button resolves event build pending choice",
            "needle": "mapWs.send(JSON.stringify({ action: 'resolve_choice', index: eventChoice.index }));",
            "text": leaflet,
        },
        {
            "name": "map direct build hint labels event-card build behavior",
            "needle": "在目前城鎮建立組織（事件卡）",
            "text": leaflet,
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
