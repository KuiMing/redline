#!/usr/bin/env python3
"""Browser proof for route legend and selected-town routes."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/map-ui/map-legend-markers"
REPORT = OUT / "MAP_LEGEND_MARKERS_VALIDATION.json"
SCREENSHOT = OUT / "map_legend_markers.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-move-confirmation-proof",
        {"mover_faction": "taiwan_green", "mover_base": "新竹", "mover_town": "基隆", "moves_left": 5},
    )
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail: object) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(BASE_URL + setup["url"], wait_until="networkidle")
        page.wait_for_selector("#gameShell", state="visible")
        page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
        page.click('button.game-tab[data-view="map"]')
        page.wait_for_function(
            "document.getElementById('strategicMapFrame')?.contentWindow?.__routeStylesForTest"
        )
        page.wait_for_timeout(400)

        legend = page.evaluate(
            """() => {
              const doc = document.getElementById('strategicMapFrame').contentDocument;
              return {
                labels: [...doc.querySelectorAll('.legend span')].map(element => element.textContent.trim()),
                legendText: doc.querySelector('.legend').textContent,
                sidebarTitleCount: doc.querySelectorAll('aside > h1').length,
                firstCardTop: doc.querySelector('aside > .card').getBoundingClientRect().top,
                firstCardId: doc.querySelector('aside > .card').id,
                actionCardTop: doc.getElementById('organizationActionsCard').getBoundingClientRect().top,
                focusCardTop: doc.getElementById('focusControlsCard').getBoundingClientRect().top,
                toolbarLabels: [...doc.querySelectorAll('.toolbar button')].map(element => element.textContent.trim()),
              };
            }"""
        )
        record(
            "legend_keeps_gold_road_and_red_dashed_rail_explanations",
            legend["labels"] == ["一般道路：金色", "鐵路：紅色虛線"],
            legend["labels"],
        )
        record(
            "legend_removes_town_state_explanations",
            all(term not in legend["legendText"] for term in ("已選城鎮", "候選城鎮", "可選城鎮")),
            legend["legendText"].strip(),
        )
        record(
            "sidebar_title_is_removed_and_content_starts_at_top",
            legend["sidebarTitleCount"] == 0 and legend["firstCardTop"] <= 30,
            {
                "sidebar_title_count": legend["sidebarTitleCount"],
                "first_card_top": legend["firstCardTop"],
            },
        )
        record(
            "organization_actions_are_above_focus_controls",
            legend["firstCardId"] == "organizationActionsCard"
            and legend["actionCardTop"] < legend["focusCardTop"],
            {
                "first_card_id": legend["firstCardId"],
                "action_card_top": legend["actionCardTop"],
                "focus_card_top": legend["focusCardTop"],
            },
        )
        record(
            "toolbar_replaces_export_view_with_base_focus",
            legend["toolbarLabels"] == ["顯示全部", "聚焦亞洲", "根據地"],
            legend["toolbarLabels"],
        )
        page.evaluate(
            """() => {
              const doc = document.getElementById('strategicMapFrame').contentDocument;
              doc.getElementById('focusAsia').click();
              doc.getElementById('focusBase').click();
            }"""
        )
        page.wait_for_timeout(600)
        base_view = page.evaluate(
            """() => {
              const map = document.getElementById('strategicMapFrame').contentWindow.__redlinePlayableMap;
              const center = map.getCenter();
              return {lat: center.lat, lng: center.lng, zoom: map.getZoom()};
            }"""
        )
        record(
            "base_button_focuses_viewers_base",
            abs(base_view["lat"] - 24.8039) < 0.02
            and abs(base_view["lng"] - 120.9687) < 0.02
            and base_view["zoom"] == 9,
            base_view,
        )

        before = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__routeStylesForTest()"
        )
        base_rails = [route for route in before if route["type"] == "rail"]
        record(
            "railway_routes_are_red_before_selection",
            bool(base_rails) and all(route["color"] == "#ef4444" for route in base_rails),
            {"rail_count": len(base_rails), "colors": sorted({route["color"] for route in base_rails})},
        )

        selection = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__selectTownForTest('基隆')"
        )
        page.wait_for_timeout(300)
        after = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__routeStylesForTest()"
        )
        connected = [
            route for route in after if route["source"] == "基隆" or route["target"] == "基隆"
        ]
        connected_roads = [route for route in connected if route["type"] == "road"]
        connected_rails = [route for route in connected if route["type"] == "rail"]
        unrelated = [
            route for route in after if route["source"] != "基隆" and route["target"] != "基隆"
        ]
        record(
            "selecting_town_brightens_only_its_connected_routes",
            selection.get("ok") is True
            and bool(connected_roads)
            and bool(connected_rails)
            and all(route["color"] == "#d8a04a" and route["opacity"] == 0.9 for route in connected_roads)
            and all(route["color"] == "#ef4444" and route["opacity"] == 0.9 and route["dashArray"] for route in connected_rails)
            and bool(unrelated)
            and all(route["opacity"] < 0.9 for route in unrelated),
            {
                "selection": selection,
                "connected_roads": connected_roads,
                "connected_rails": connected_rails,
                "unrelated_opacity_max": max((route["opacity"] for route in unrelated), default=None),
            },
        )

        empty_selection = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__selectTownForTest('高雄')"
        )
        page.wait_for_timeout(300)
        empty_styles = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__routeStylesForTest()"
        )
        empty_connected = [
            route for route in empty_styles if route["source"] == "高雄" or route["target"] == "高雄"
        ]
        record(
            "non_actionable_selected_town_still_brightens_connected_routes",
            empty_selection.get("ok") is True
            and empty_selection.get("canAct") is False
            and bool(empty_connected)
            and all(route["opacity"] == 0.9 for route in empty_connected),
            {"selection": empty_selection, "connected": empty_connected},
        )

        page.evaluate(
            """() => {
              const win = document.getElementById('strategicMapFrame').contentWindow;
              win.__redlinePlayableMap.setZoom(win.__redlinePlayableMap.getZoom() + 1, {animate:false});
            }"""
        )
        page.wait_for_timeout(300)
        zoom_styles = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__routeStylesForTest()"
        )
        zoom_connected = [
            route for route in zoom_styles if route["source"] == "高雄" or route["target"] == "高雄"
        ]
        record(
            "selected_route_highlight_survives_zoom_restyle",
            bool(zoom_connected) and all(route["opacity"] == 0.9 for route in zoom_connected),
            zoom_connected,
        )
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        cleared = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__clearTownSelectionForTest()"
        )
        page.wait_for_timeout(300)
        reset_styles = page.evaluate(
            "() => document.getElementById('strategicMapFrame').contentWindow.__routeStylesForTest()"
        )
        reset_roads = [route for route in reset_styles if route["type"] == "road"]
        reset_rails = [route for route in reset_styles if route["type"] == "rail"]
        zoom_weights = {
            (route["type"], route["source"], route["target"]): route["weight"]
            for route in zoom_styles
        }
        reset_weights = {
            (route["type"], route["source"], route["target"]): route["weight"]
            for route in reset_styles
        }
        record(
            "selected_route_highlight_does_not_change_line_width",
            zoom_weights == reset_weights,
            {
                "selected_widths": sorted(set(zoom_weights.values())),
                "base_widths": sorted(set(reset_weights.values())),
            },
        )
        record(
            "clearing_selection_restores_base_route_styles",
            cleared.get("ok") is True
            and bool(reset_roads)
            and bool(reset_rails)
            and all(route["opacity"] == 0.24 for route in reset_roads)
            and all(route["color"] == "#ef4444" and route["opacity"] == 0.34 for route in reset_rails),
            {
                "cleared": cleared,
                "road_opacities": sorted({route["opacity"] for route in reset_roads}),
                "rail_colors": sorted({route["color"] for route in reset_rails}),
                "rail_opacities": sorted({route["opacity"] for route in reset_rails}),
            },
        )
        record("browser_console_has_no_errors", not console_errors, console_errors)
        browser.close()

    payload = {
        "status": "passed" if all(check["ok"] for check in checks) else "failed",
        "checks_passed": sum(1 for check in checks if check["ok"]),
        "checks_total": len(checks),
        "checks": checks,
        "console_errors": console_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
        "identifiers": "[REDACTED]",
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "checks_passed", "checks_total")}, ensure_ascii=False))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
