#!/usr/bin/env python3
"""Static validator for event-card pending choice map-highlight wiring."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "event-cards"
JSON_OUT = RECORD_DIR / "EVENT_CARD_UI_HIGHLIGHT_VALIDATION.json"
MD_OUT = RECORD_DIR / "EVENT_CARD_UI_HIGHLIGHT_VALIDATION.md"
APP_JS = ROOT / "static" / "app.js"


def assert_contains(text: str, needle: str, label: str, failures: list[str]) -> None:
    if needle not in text:
        failures.append(f"missing {label}: {needle}")


def main() -> None:
    app = APP_JS.read_text(encoding="utf-8")
    failures: list[str] = []
    checks = [
        {
            "name": "event_build_organization town_choice is included in map-highlight allowlist",
            "needle": "new Set(['event_build_organization'])",
        },
        {
            "name": "build town choices use existing support-targets highlight payload",
            "needle": "mode: 'support-targets'",
        },
        {
            "name": "build town choices read pending choice towns",
            "needle": "const towns = (choice.towns || []).filter(entry => entry?.town);",
        },
        {
            "name": "modal tells player the map highlights buildable organization towns",
            "needle": "地圖會同步高亮可以建立組織的城鎮",
        },
        {
            "name": "strategic map iframe is mounted for choice highlight",
            "needle": "ensureStrategicMapMounted().catch(err => console.warn('Failed to mount strategic map for choice highlight', err));",
        },
    ]
    for check in checks:
        assert_contains(app, check["needle"], check["name"], failures)

    payload = {
        "status": "failed" if failures else "passed",
        "checks": [
            {"name": check["name"], "needle": check["needle"], "status": "passed" if check["needle"] in app else "failed"}
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
