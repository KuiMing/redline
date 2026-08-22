#!/usr/bin/env python3
from __future__ import annotations

import json
import os

import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000")
RECORD_DIR = ROOT / "docs/records/event-cards"
JSON_PATH = RECORD_DIR / "BELT_ROAD_NANYANG_MAP_FOCUS_VALIDATION.json"
MD_PATH = RECORD_DIR / "BELT_ROAD_NANYANG_MAP_FOCUS_VALIDATION.md"
SCREENSHOT = RECORD_DIR / "BELT_ROAD_NANYANG_MAP_FOCUS.png"


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def map_coordinates() -> dict[str, list[float]]:
    with urllib.request.urlopen(BASE_URL + "/map-geo-coordinates", timeout=10) as response:
        return json.load(response)


def record(checks: list[dict], name: str, passed: bool, details) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    setup = post_json(
        "/test/setup-belt-road-red-turn-proof",
        {"advance_to_red": True, "event_name": "一帶一路 南洋"},
    )
    state = setup.get("state") or {}
    choice = state.get("pending_choice") or {}
    candidate_names = [entry.get("town") for entry in choice.get("towns", []) if entry.get("town")]
    coords = map_coordinates()
    candidate_lat_lngs = [[coords[name][1], coords[name][0]] for name in candidate_names if name in coords]

    record(
        checks,
        "red_turn_has_nanyang_event_build_choice",
        state.get("current_player") == "紅軍"
        and state.get("turn_phase") == "action"
        and choice.get("choice_key") == "event_build_organization"
        and choice.get("region") == "southeast_asia"
        and len(candidate_names) >= 1,
        {
            "current_player": state.get("current_player"),
            "turn_phase": state.get("turn_phase"),
            "choice_key": choice.get("choice_key"),
            "region": choice.get("region"),
            "candidate_names": candidate_names,
        },
    )

    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto(f"{BASE_URL}{setup['url']}&v=belt-road-nanyang-map-focus", wait_until="domcontentloaded")
        page.wait_for_function(
            """() => {
              const frame = document.getElementById('strategicMapFrame');
              const state = frame?.contentWindow?.lastGameState;
              return frame?.contentWindow?.__redlinePlayableMap
                && state?.pending_choice?.choice_key === 'event_build_organization';
            }""",
            timeout=15000,
        )
        page.wait_for_function(
            """() => document.querySelector('.game-tab.active')?.dataset.view === 'map'""",
            timeout=10000,
        )
        page.wait_for_timeout(1500)
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)

        geometry = page.evaluate(
            """candidateLatLngs => {
              const frame = document.getElementById('strategicMapFrame');
              const win = frame.contentWindow;
              const map = win.__redlinePlayableMap;
              const bounds = map.getBounds();
              const center = map.getCenter();
              const hint = win.document.getElementById('interactionHint')?.textContent || '';
              return {
                activeView: document.querySelector('.game-tab.active')?.dataset.view || null,
                center: {lat: center.lat, lng: center.lng},
                zoom: map.getZoom(),
                bounds: {
                  north: bounds.getNorth(), south: bounds.getSouth(),
                  east: bounds.getEast(), west: bounds.getWest(),
                },
                candidateVisibility: candidateLatLngs.map(([lat, lng]) => ({lat, lng, visible: bounds.contains([lat, lng])})),
                hint,
              };
            }""",
            candidate_lat_lngs,
        )
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        observer_page = browser.new_page(viewport={"width": 1280, "height": 720})
        observer_errors: list[str] = []
        observer_page.on("console", lambda message: observer_errors.append(message.text) if message.type == "error" else None)
        observer_page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=belt-road-observer-base-focus",
            wait_until="domcontentloaded",
        )
        observer_page.wait_for_function("window.lastGameState?.pending_choice?.choice_key === 'event_build_organization'", timeout=15000)
        reveal = observer_page.locator("#eventRevealModal")
        if reveal.is_visible():
            reveal.click(position={"x": 10, "y": 10})
        observer_page.locator('.game-tab[data-view="map"]').click()
        observer_page.wait_for_function(
            "document.getElementById('strategicMapFrame')?.contentWindow?.__redlinePlayableMap?.getZoom() === 9",
            timeout=15000,
        )
        observer_geometry = observer_page.evaluate(
            """() => {
              const map = document.getElementById('strategicMapFrame').contentWindow.__redlinePlayableMap;
              const center = map.getCenter();
              return {center: {lat: center.lat, lng: center.lng}, zoom: map.getZoom()};
            }"""
        )
        console_errors.extend(observer_errors)
        browser.close()

    visible_candidate_count = sum(item["visible"] for item in geometry["candidateVisibility"])
    center = geometry["center"]
    center_in_nanyang = -10 <= center["lat"] <= 25 and 90 <= center["lng"] <= 130
    record(checks, "event_choice_opens_strategic_map", geometry["activeView"] == "map", geometry)
    record(
        checks,
        "map_auto_focuses_nanyang_instead_of_beijing_base",
        center_in_nanyang and geometry["zoom"] >= 5,
        {"center": center, "zoom": geometry["zoom"], "bounds": geometry["bounds"]},
    )
    record(
        checks,
        "nanyang_core_candidates_are_visible_without_forcing_all_edges_into_view",
        visible_candidate_count >= 6,
        {"visible": visible_candidate_count, "total": len(geometry["candidateVisibility"]), "candidates": geometry["candidateVisibility"]},
    )
    record(
        checks,
        "map_hint_matches_event_candidates",
        "一帶一路 南洋" in geometry["hint"] and f"可建立城鎮：{len(candidate_names)} 個" in geometry["hint"],
        geometry["hint"],
    )
    observer_center = observer_geometry["center"]
    record(
        checks,
        "non_acting_viewer_keeps_own_base_initial_focus",
        observer_geometry["zoom"] == 9
        and abs(observer_center["lat"] - 25.033) < 0.5
        and abs(observer_center["lng"] - 121.5654) < 0.5,
        observer_geometry,
    )
    record(checks, "browser_console_has_no_errors", not console_errors, console_errors)

    summary = {
        "total": len(checks),
        "passed": sum(1 for item in checks if item["passed"]),
        "failed": sum(1 for item in checks if not item["passed"]),
    }
    payload = {
        "summary": summary,
        "base_url": BASE_URL,
        "scenario": {
            "event": "一帶一路 南洋",
            "current_player": "紅軍",
            "setup_endpoint": "/test/setup-belt-road-red-turn-proof",
        },
        "checks": checks,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 一帶一路南洋地圖自動對焦驗證",
        "",
        f"Summary: {summary['passed']}/{summary['total']} passed",
        "",
        f"- Screenshot: `{SCREENSHOT.relative_to(ROOT)}`",
        "- Re-run: `uv run --with playwright python scripts/validate_belt_road_nanyang_map_focus.py`",
        "",
    ]
    for item in checks:
        lines.extend(
            [
                f"## {'PASS' if item['passed'] else 'FAIL'} — {item['name']}",
                "",
                "```json",
                json.dumps(item["details"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
