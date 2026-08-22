#!/usr/bin/env python3
"""Formal Browser proof for concentrated 一帶一路 南洋 map focus."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/event-cards/belt-road-nanyang-focus"
JSON_PATH = OUT / "BELT_ROAD_NANYANG_CONCENTRATED_FOCUS_VALIDATION.json"
MD_PATH = OUT / "BELT_ROAD_NANYANG_CONCENTRATED_FOCUS_VALIDATION.md"
SCREENSHOT = OUT / "belt_road_nanyang_concentrated_focus_20260822.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def formal_session() -> dict:
    created = post_json("/create", {})
    game_id = created["game_id"]
    viewer_id = created["host_id"]
    viewer_token = created["resume_token"]
    joined = post_json("/join", {"game_id": game_id, "name": "紅軍"})
    red_id = joined["player_id"]
    red_token = joined["resume_token"]
    for player_id, faction, base in (
        (viewer_id, "taiwan_green", "臺北"),
        (red_id, "red_army", "北京"),
    ):
        post_json(
            "/choose-faction",
            {"game_id": game_id, "player_id": player_id, "faction_id": faction, "base_name": base},
        )
        post_json("/ready", {"game_id": game_id, "player_id": player_id, "ready": True})
    post_json("/start", {"game_id": game_id, "player_id": viewer_id, "market_mode": "all_cards"})
    return {
        "game_id": game_id,
        "viewer_id": viewer_id,
        "viewer_token": viewer_token,
        "red_id": red_id,
        "red_token": red_token,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    session = formal_session()
    preceding = post_json(
        "/test/setup-build-view-persistence-proof",
        {"game_id": session["game_id"], "player_id": session["red_id"]},
    )
    if not preceding.get("success"):
        raise AssertionError(preceding)
    primary_towns = ["曼谷", "吉隆坡", "新加坡"]

    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.goto(
            f"{BASE_URL}/?game_id={session['game_id']}&player_id={session['red_id']}&resume_token={session['red_token']}",
            wait_until="domcontentloaded",
        )
        page.wait_for_function(
            "playerId => window.lastGameState?.players?.find(player => player.id === playerId)?.hand?.includes('組織經驗丙')",
            arg=session["red_id"],
            timeout=15000,
        )
        page.evaluate("closeEventReveal?.(); setActiveGameView('command')")
        page.locator("button.hand-card-action-btn[data-card-name='組織經驗丙'][data-card-mode='action']").click()
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'",
            timeout=15000,
        )
        page.frame_locator("#strategicMapFrame").locator("#map").wait_for(state="visible", timeout=15000)
        frame = next(item for item in page.frames if "leaflet_game_map.html" in item.url)
        frame.wait_for_function("window.__redlinePlayableMap?._loaded === true", timeout=15000)
        build_town = page.evaluate("window.lastGameState.pending_choice.towns[0].town")
        frame.evaluate("town => window.selectTownForCurrentMapAction(town, {autoFocus: false})", build_town)
        frame.locator("#directBuildBtn").click()
        page.wait_for_function("!window.lastGameState?.pending_choice", timeout=10000)
        page.evaluate("setActiveGameView('map')")
        page.wait_for_function("document.getElementById('mapView')?.classList.contains('active')")
        page.wait_for_timeout(300)
        frame.evaluate("() => { window.__redlinePlayableMap.setView([39.9042, 116.4074], 9, {animate: false}); }")
        page.wait_for_timeout(250)
        before_event = frame.evaluate(
            """() => {
              const map = window.__redlinePlayableMap;
              const center = map.getCenter();
              return {center: {lat: center.lat, lng: center.lng}, zoom: map.getZoom()};
            }"""
        )
        record(
            "prior_build_session_and_player_view_are_established",
            before_event["zoom"] == 9
            and abs(before_event["center"]["lat"] - 39.9042) < 0.1
            and abs(before_event["center"]["lng"] - 116.4074) < 0.1,
            before_event,
        )

        setup = post_json(
            "/test/setup-belt-road-red-turn-proof",
            {
                "game_id": session["game_id"],
                "player_id": session["viewer_id"],
                "red_player_id": session["red_id"],
                "advance_to_red": True,
                "event_name": "一帶一路 南洋",
            },
        )
        if not setup.get("success"):
            raise AssertionError(setup)
        choice = (setup.get("state") or {}).get("pending_choice") or {}
        candidate_names = [entry.get("town") for entry in choice.get("towns", []) if entry.get("town")]
        record(
            "formal_red_turn_has_nanyang_event_choice",
            choice.get("choice_key") == "event_build_organization"
            and choice.get("region") == "southeast_asia"
            and choice.get("source_name") == "一帶一路 南洋"
            and all(town in candidate_names for town in primary_towns),
            {"choice_key": choice.get("choice_key"), "region": choice.get("region"), "candidate_names": candidate_names},
        )
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'event_build_organization'",
            timeout=15000,
        )
        page.wait_for_function(
            "document.querySelector('.game-tab.active')?.dataset.view === 'map'",
            timeout=15000,
        )
        page.wait_for_timeout(1200)
        page.evaluate("closeEventReveal?.()")
        page.wait_for_function("document.getElementById('eventRevealModal')?.style.display === 'none'")
        geometry = frame.evaluate(
            """primaryTowns => {
              const map = window.__redlinePlayableMap;
              const center = map.getCenter();
              const bounds = map.getBounds();
              const named = Object.fromEntries(primaryTowns.map(name => {
                const town = byName.get(name);
                return [name, town ? {
                  lat: town.lat,
                  lng: town.lon,
                  visible: bounds.contains([town.lat, town.lon]),
                } : null];
              }));
              return {
                center: {lat: center.lat, lng: center.lng},
                zoom: map.getZoom(),
                bounds: {north: bounds.getNorth(), south: bounds.getSouth(), east: bounds.getEast(), west: bounds.getWest()},
                primary: named,
                hint: document.getElementById('interactionHint')?.textContent || '',
              };
            }""",
            primary_towns,
        )
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        center = geometry["center"]
        record(
            "nanyang_focus_uses_concentrated_region_view",
            geometry["zoom"] >= 5
            and -1 <= center["lat"] <= 18
            and 98 <= center["lng"] <= 112,
            geometry,
        )
        record(
            "primary_nanyang_towns_are_visible",
            all((geometry["primary"].get(name) or {}).get("visible") for name in primary_towns),
            geometry["primary"],
        )
        record(
            "all_legal_targets_remain_in_choice_and_hint",
            len(candidate_names) >= 10
            and all(name in candidate_names for name in ("仰光", "雅加達", "馬尼拉"))
            and f"可建立城鎮：{len(candidate_names)} 個" in geometry["hint"],
            {"candidate_count": len(candidate_names), "candidate_names": candidate_names, "hint": geometry["hint"]},
        )

        observer = browser.new_page(viewport={"width": 1280, "height": 720})
        observer_errors: list[str] = []
        observer.on("console", lambda message: observer_errors.append(message.text) if message.type == "error" else None)
        observer.goto(
            f"{BASE_URL}/?game_id={session['game_id']}&player_id={session['viewer_id']}&resume_token={session['viewer_token']}",
            wait_until="domcontentloaded",
        )
        observer.wait_for_function("window.lastGameState?.pending_choice?.choice_key === 'event_build_organization'", timeout=15000)
        observer.evaluate("setActiveGameView('map')")
        observer_frame = observer.frame_locator("#strategicMapFrame")
        observer_frame.locator("#map").wait_for(state="visible", timeout=15000)
        observer_map = next(item for item in observer.frames if "leaflet_game_map.html" in item.url)
        observer_map.wait_for_function("window.__redlinePlayableMap?._loaded === true", timeout=15000)
        observer.wait_for_timeout(800)
        observer_geometry = observer_map.evaluate(
            """() => {
              const map = window.__redlinePlayableMap;
              const center = map.getCenter();
              return {center: {lat: center.lat, lng: center.lng}, zoom: map.getZoom()};
            }"""
        )
        record(
            "non_acting_viewer_keeps_own_base_focus",
            observer_geometry["zoom"] == 9
            and abs(observer_geometry["center"]["lat"] - 25.033) < 0.5
            and abs(observer_geometry["center"]["lng"] - 121.5654) < 0.5,
            observer_geometry,
        )
        errors.extend(observer_errors)
        browser.close()

    record("browser_console_has_no_errors", not errors, errors)
    summary = {
        "total": len(checks),
        "passed": sum(item["passed"] for item in checks),
        "failed": sum(not item["passed"] for item in checks),
    }
    report = {
        "summary": summary,
        "service": BASE_URL,
        "session": "formal create/join/start/restore; credentials [REDACTED]",
        "checks": checks,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 一帶一路南洋集中聚焦驗證",
        "",
        f"Summary: **{summary['passed']}/{summary['total']} passed**",
        "",
        f"- Screenshot: `{SCREENSHOT.relative_to(ROOT)}`",
        "- Session credentials and identifiers: `[REDACTED]`",
        "",
    ]
    for item in checks:
        lines.extend([f"## {'PASS' if item['passed'] else 'FAIL'} — {item['name']}", "", "```json", json.dumps(item["details"], ensure_ascii=False, indent=2), "```", ""])
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
