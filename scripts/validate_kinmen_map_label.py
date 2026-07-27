#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000")
RECORD_DIR = ROOT / "docs/records/map-ui"
JSON_PATH = RECORD_DIR / "KINMEN_LABEL_VALIDATION_2026_07_28.json"
MD_PATH = RECORD_DIR / "KINMEN_LABEL_VALIDATION_2026_07_28.md"
SCREENSHOT = RECORD_DIR / "KINMEN_LABEL_UI_2026_07_28.png"


def record(checks: list[dict], name: str, passed: bool, details) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def label_geometry(page, zoom: int) -> dict:
    page.evaluate(
        """zoom => {
          window.__redlinePlayableMap.setView([24.5, 119.8], zoom, {animate: false});
        }""",
        zoom,
    )
    page.wait_for_timeout(450)
    return page.evaluate(
        """() => {
          const wanted = new Set(['金門', '廈門']);
          const labels = {};
          document.querySelectorAll('.town-label').forEach(el => {
            const text = String(el.textContent || '').trim();
            if (!wanted.has(text)) return;
            const rect = el.getBoundingClientRect();
            labels[text] = {
              text,
              rect: {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height},
              classes: [...el.classList],
              display: getComputedStyle(el).display,
              opacity: getComputedStyle(el).opacity,
            };
          });
          const mapRect = document.getElementById('map').getBoundingClientRect();
          const a = labels['金門']?.rect;
          const b = labels['廈門']?.rect;
          const overlapWidth = a && b ? Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) : null;
          const overlapHeight = a && b ? Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)) : null;
          return {
            zoom: window.__redlinePlayableMap.getZoom(),
            labels,
            mapRect: {left: mapRect.left, top: mapRect.top, right: mapRect.right, bottom: mapRect.bottom},
            overlapArea: overlapWidth == null || overlapHeight == null ? null : overlapWidth * overlapHeight,
          };
        }"""
    )


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    source = (ROOT / "static/leaflet_game_map_logic.js").read_text(encoding="utf-8")
    html = (ROOT / "static/leaflet_game_map.html").read_text(encoding="utf-8")
    record(
        checks,
        "kinmen_has_explicit_collision_safe_label_placement_and_cache_bust",
        "function townLabelOptions" in source
        and "townName === '金門'" in source
        and "kinmen-label-20260728" in html,
        "town-specific tooltip options + map script cache bust",
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        console_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto(f"{BASE_URL}/static/leaflet_game_map.html?v=kinmen-label-proof", wait_until="domcontentloaded")
        page.wait_for_function("window.__redlinePlayableMap && document.querySelectorAll('.leaflet-marker-pane').length >= 0")
        page.wait_for_timeout(900)

        states = [label_geometry(page, zoom) for zoom in (5, 6, 7)]
        middle = states[1]
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        labels_exist = all("金門" in state["labels"] and "廈門" in state["labels"] for state in states)
        record(checks, "kinmen_and_xiamen_labels_exist_at_auto_label_zooms", labels_exist, states)
        record(
            checks,
            "kinmen_label_uses_bottom_placement",
            "leaflet-tooltip-bottom" in middle.get("labels", {}).get("金門", {}).get("classes", []),
            middle.get("labels", {}).get("金門"),
        )
        record(
            checks,
            "kinmen_label_does_not_overlap_xiamen_at_zooms_5_to_7",
            labels_exist and all(state["overlapArea"] == 0 for state in states),
            [{"zoom": state["zoom"], "overlapArea": state["overlapArea"], "labels": state["labels"]} for state in states],
        )
        kinmen = middle.get("labels", {}).get("金門", {})
        rect = kinmen.get("rect", {})
        map_rect = middle["mapRect"]
        in_view = bool(rect) and rect["left"] >= map_rect["left"] and rect["right"] <= map_rect["right"] and rect["top"] >= map_rect["top"] and rect["bottom"] <= map_rect["bottom"]
        record(checks, "kinmen_label_is_visible_inside_map", in_view and kinmen.get("display") == "block" and float(kinmen.get("opacity", 0)) > 0, {"kinmen": kinmen, "mapRect": map_rect})
        record(checks, "browser_console_has_no_errors", not console_errors, console_errors)
        browser.close()

    summary = {
        "total": len(checks),
        "passed": sum(1 for item in checks if item["passed"]),
        "failed": sum(1 for item in checks if not item["passed"]),
    }
    payload = {
        "summary": summary,
        "base_url": BASE_URL,
        "checks": checks,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 金門地圖標籤驗證",
        "",
        f"Summary: {summary['passed']}/{summary['total']} passed",
        "",
        f"- Screenshot: `{SCREENSHOT.relative_to(ROOT)}`",
        "- Re-run: `uv run --with playwright python scripts/validate_kinmen_map_label.py`",
        "",
    ]
    for item in checks:
        lines.extend([
            f"## {'PASS' if item['passed'] else 'FAIL'} — {item['name']}",
            "",
            "```json",
            json.dumps(item["details"], ensure_ascii=False, indent=2),
            "```",
            "",
        ])
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
