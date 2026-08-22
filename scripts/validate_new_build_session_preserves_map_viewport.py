#!/usr/bin/env python3
"""Formal Browser proof: a new build-card session preserves the last map viewport."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8767").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "action-cards" / "build-session-viewport"
JSON_PATH = RECORD_DIR / "NEW_BUILD_SESSION_PRESERVES_MAP_VIEWPORT_VALIDATION.json"
MD_PATH = RECORD_DIR / "NEW_BUILD_SESSION_PRESERVES_MAP_VIEWPORT_VALIDATION.md"
BEFORE_SHOT = RECORD_DIR / "los_angeles_view_before_second_build_card_20260822.png"
AFTER_SHOT = RECORD_DIR / "los_angeles_view_preserved_after_second_build_card_20260822.png"


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def make_formal_game() -> dict:
    create = post_json("/create")
    join = post_json("/join", {"game_id": create["game_id"], "name": "自由派"})
    for player_id, faction_id, base_name in [
        (create["host_id"], "red_army", "北京"),
        (join["player_id"], "taiwan_green", "臺北"),
    ]:
        chosen = post_json(
            "/choose-faction",
            {"game_id": create["game_id"], "player_id": player_id, "faction_id": faction_id, "base_name": base_name},
        )
        if chosen.get("error"):
            raise AssertionError(chosen)
        ready = post_json("/ready", {"game_id": create["game_id"], "player_id": player_id, "ready": True})
        if ready.get("error"):
            raise AssertionError(ready)
    started = post_json(
        "/start",
        {"game_id": create["game_id"], "player_id": create["host_id"], "market_mode": "sample_53"},
    )
    if started.get("error"):
        raise AssertionError(started)
    setup = post_json(
        "/test/setup-build-view-persistence-proof",
        {"game_id": create["game_id"], "player_id": join["player_id"]},
    )
    if not setup.get("success"):
        raise AssertionError(setup)
    return {
        "game_id": create["game_id"],
        "player_id": join["player_id"],
        "resume_token": join["resume_token"],
        "name": "自由派",
    }


def map_view(frame) -> dict:
    return frame.evaluate(
        """() => {
          const map = window.__redlinePlayableMap;
          const center = map.getCenter();
          return {center: {lat: center.lat, lng: center.lng}, zoom: map.getZoom()};
        }"""
    )


def same_view(left: dict, right: dict, tolerance: float = 0.02) -> bool:
    return (
        abs(left["zoom"] - right["zoom"]) < tolerance
        and abs(left["center"]["lat"] - right["center"]["lat"]) < tolerance
        and abs(left["center"]["lng"] - right["center"]["lng"]) < tolerance
    )


def resolve_one_build(page, frame, *, avoid_town: str | None = None) -> str:
    pending = page.evaluate("window.lastGameState.pending_choice")
    names = [entry["town"] for entry in pending["towns"]]
    town = next((name for name in names if name != avoid_town), names[0])
    frame.evaluate("town => window.selectTownForCurrentMapAction(town, {autoFocus: false})", town)
    page.wait_for_function(
        """() => {
          const frame = document.getElementById('strategicMapFrame');
          const button = frame?.contentDocument?.getElementById('directBuildBtn');
          return button && !button.disabled && button.textContent.includes('效果');
        }""",
        timeout=10000,
    )
    page.frame_locator("#strategicMapFrame").locator("#directBuildBtn").click()
    return town


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    session = make_formal_game()
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details=None) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(BASE_URL + "/", wait_until="domcontentloaded")
        page.evaluate(
            """session => localStorage.setItem('redline.sessions.v1', JSON.stringify({
              [session.game_id]: {
                game_id: session.game_id,
                player_id: session.player_id,
                resume_token: session.resume_token,
                name: session.name,
                saved_at: Date.now(),
              },
            }))""",
            session,
        )
        page.goto(BASE_URL + "/?v=new-build-session-view", wait_until="domcontentloaded")
        page.wait_for_function(
            "playerId => window.lastGameState?.players?.find(player => player.id === playerId)?.hand?.includes('組織經驗丙')",
            arg=session["player_id"],
            timeout=15000,
        )
        page.evaluate(
            """() => {
              closeEventReveal?.();
              minimizeEraAchievement?.();
              document.getElementById('closeFactionActionModal')?.click();
              setActiveGameView('command');
            }"""
        )
        page.evaluate("closeEventReveal?.()")
        page.wait_for_function("document.getElementById('eventRevealModal')?.style.display === 'none'")
        page.locator("button.hand-card-action-btn[data-card-name='組織經驗丙'][data-card-mode='action']").click()
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'card_build_organization' && window.lastGameState.pending_choice.remaining_builds === 1",
            timeout=10000,
        )
        page.frame_locator("#strategicMapFrame").locator("#map").wait_for(state="visible", timeout=15000)
        map_frame = next(frame for frame in page.frames if "leaflet_game_map.html" in frame.url)
        map_frame.wait_for_function("window.__redlinePlayableMap?._loaded === true", timeout=15000)
        first_session_view = map_view(map_frame)
        resolve_one_build(page, map_frame, avoid_town="洛杉磯")
        page.wait_for_function("!window.lastGameState?.pending_choice", timeout=10000)
        record("first_build_card_completes_its_own_session", True, first_session_view)

        second_setup = post_json(
            "/test/setup-build-view-persistence-proof",
            {"game_id": session["game_id"], "player_id": session["player_id"], "stage": "second"},
        )
        if not second_setup.get("success"):
            raise AssertionError(second_setup)
        page.wait_for_function(
            "playerId => window.lastGameState?.players?.find(player => player.id === playerId)?.hand?.includes('組織經驗乙')",
            arg=session["player_id"],
            timeout=10000,
        )
        page.evaluate("setActiveGameView('map')")
        page.wait_for_function("document.getElementById('mapView')?.classList.contains('active')")
        page.wait_for_timeout(300)

        desired_view = {"center": {"lat": 34.0522, "lng": -118.2437}, "zoom": 8}
        map_frame.evaluate(
            "view => { window.__redlinePlayableMap.setView([view.center.lat, view.center.lng], view.zoom, {animate: false}); }",
            desired_view,
        )
        page.wait_for_timeout(250)
        before_second = map_view(map_frame)
        record("player_selected_los_angeles_view_before_next_card", same_view(before_second, desired_view), before_second)
        page.screenshot(path=str(BEFORE_SHOT), full_page=True)

        page.evaluate("setActiveGameView('command')")
        page.locator("button.hand-card-action-btn[data-card-name='組織經驗乙'][data-card-mode='action']").click()
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'card_build_organization' && window.lastGameState.pending_choice.remaining_builds === 2",
            timeout=10000,
        )
        page.wait_for_timeout(500)
        after_second_started = map_view(map_frame)
        second_pending = page.evaluate("window.lastGameState.pending_choice")
        second_towns = [entry["town"] for entry in second_pending["towns"]]
        record(
            "new_build_card_session_preserves_previous_center_and_zoom",
            same_view(after_second_started, before_second),
            {"before": before_second, "after": after_second_started},
        )
        record(
            "remote_los_angeles_target_remains_available_without_forced_zoom_out",
            "洛杉磯" in second_towns and len(second_towns) > 1,
            {"contains_los_angeles": "洛杉磯" in second_towns, "candidate_count": len(second_towns)},
        )
        page.screenshot(path=str(AFTER_SHOT), full_page=True)

        preserved_during_builds = []
        for expected_remaining in (1, 0):
            before_build = map_view(map_frame)
            resolve_one_build(page, map_frame, avoid_town="洛杉磯")
            if expected_remaining:
                page.wait_for_function(
                    "expected => window.lastGameState?.pending_choice?.remaining_builds === expected",
                    arg=expected_remaining,
                    timeout=10000,
                )
            else:
                page.wait_for_function("!window.lastGameState?.pending_choice", timeout=10000)
            page.wait_for_timeout(300)
            after_build = map_view(map_frame)
            preserved_during_builds.append({
                "expected_remaining": expected_remaining,
                "before": before_build,
                "after": after_build,
                "preserved": same_view(before_build, after_build),
            })
        record(
            "second_card_two_builds_also_preserve_view",
            all(entry["preserved"] for entry in preserved_during_builds),
            preserved_during_builds,
        )
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
    }
    report = {
        "summary": summary,
        "service": BASE_URL,
        "session": "formal create/join/start/restore; credentials [REDACTED]",
        "checks": checks,
        "screenshots": [str(BEFORE_SHOT.relative_to(ROOT)), str(AFTER_SHOT.relative_to(ROOT))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# New Build Session Preserves Map Viewport Validation",
        "",
        f"- Summary: {summary['passed']}/{summary['total']} passed",
        "- Session: formal create/join/start/restore; credentials `[REDACTED]`",
        "",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in checks)
    lines.extend(["", f"- Before: `{BEFORE_SHOT.relative_to(ROOT)}`", f"- After: `{AFTER_SHOT.relative_to(ROOT)}`"])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
