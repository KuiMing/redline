#!/usr/bin/env python3
"""Browser proof：紅軍根據地組織被移除後，地圖不再顯示根據地標示。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/map-ui/destroyed-red-base-marker"
REPORT_JSON = OUT / "DESTROYED_RED_BASE_MARKER_VALIDATION.json"
REPORT_MD = OUT / "DESTROYED_RED_BASE_MARKER_VALIDATION.md"


def setup(destroyed: bool) -> dict:
    request = urllib.request.Request(
        BASE_URL + "/test/setup-destroyed-red-base-marker-proof",
        data=json.dumps({"destroyed": destroyed}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def open_map(page, fixture: dict) -> None:
    page.goto(f"{BASE_URL}/?game_id={fixture['game_id']}&player_id={fixture['player_id']}&v=destroyed-red-base-marker-proof", wait_until="networkidle")
    page.wait_for_function("window.lastGameState?.players?.length === 2", timeout=15000)
    page.evaluate("closeEventReveal?.()")
    page.locator('.game-tab[data-view="map"]').click()
    frame = page.frame_locator("#strategicMapFrame")
    frame.locator("#map").wait_for(state="visible", timeout=15000)
    page.wait_for_timeout(700)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    console_errors: list[str] = []
    screenshots: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        intact = setup(False)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        open_map(page, intact)
        frame = page.frame_locator("#strategicMapFrame")
        intact_state = page.evaluate(
            """() => {
              const frame = document.getElementById('strategicMapFrame').contentWindow;
              return {
                beijingBadge: frame.document.querySelectorAll('.base-badge[data-base-town="北京"]').length,
                mongolBadge: frame.document.querySelectorAll('.base-badge[data-base-town="烏蘭巴托"]').length,
                beijingBaseFaction: frame.baseFactionIdForTown('北京'),
              };
            }"""
        )
        record("intact_red_base_still_shows_beijing_base_marker", intact_state["beijingBadge"] == 1 and intact_state["beijingBaseFaction"] == "red_army", intact_state)
        page.close()

        for width, height in ((1280, 720), (1024, 768)):
            destroyed = setup(True)
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            open_map(page, destroyed)
            state = page.evaluate(
                """() => {
                  const frame = document.getElementById('strategicMapFrame').contentWindow;
                  const red = window.lastGameState.players.find(player => player.faction === 'red_army');
                  const legal = window.lastGameState.map?.legal_organization_moves?.['張家口'] || {};
                  return {
                    beijingBadge: frame.document.querySelectorAll('.base-badge[data-base-town="北京"]').length,
                    mongolBadge: frame.document.querySelectorAll('.base-badge[data-base-town="烏蘭巴托"]').length,
                    beijingBaseFaction: frame.baseFactionIdForTown('北京'),
                    redBase: red?.base || null,
                    redOrganizations: red?.orgs || {},
                    railTargets: (legal.rail || []).map(move => typeof move === 'string' ? move : move.town),
                    roadTargets: (legal.road || []).map(move => typeof move === 'string' ? move : move.town),
                  };
                }"""
            )
            page.wait_for_timeout(250)
            record(f"{width}x{height}_destroyed_beijing_has_no_base_marker", state["beijingBadge"] == 0 and state["beijingBaseFaction"] is None, state)
            record(f"{width}x{height}_other_active_base_marker_remains", state["mongolBadge"] == 1, state)
            record(f"{width}x{height}_beijing_is_empty_and_legal_from_zhangjiakou", state["redBase"] == "北京" and "北京" not in state["redOrganizations"] and "北京" in state["railTargets"], state)

            selected = page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__selectTownForTest('張家口')")
            clicked = page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__clickMoveTargetForTest('北京')")
            confirmed = page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.__confirmPendingMoveForTest()")
            page.wait_for_function(
                """() => (window.lastGameState?.map?.towns?.['北京'] || []).some(entry => entry.player === 'mongol' && Number(entry.count || 0) > 0)""",
                timeout=15000,
            )
            page.wait_for_function(
                """() => (document.getElementById('strategicMapFrame').contentWindow.lastGameState?.map?.towns?.['北京'] || []).some(entry => entry.player === 'mongol' && Number(entry.count || 0) > 0)""",
                timeout=15000,
            )
            moved_state = page.evaluate(
                """() => {
                  const frame = document.getElementById('strategicMapFrame').contentWindow;
                  return {
                    beijing: window.lastGameState.map.towns['北京'] || [],
                    zhangjiakou: window.lastGameState.map.towns['張家口'] || [],
                    movesLeft: window.lastGameState.players.find(player => player.faction === 'mongol')?.moves_left,
                    beijingBadge: frame.document.querySelectorAll('.base-badge[data-base-town="北京"]').length,
                    beijingBaseFaction: frame.baseFactionIdForTown('北京'),
                  };
                }"""
            )
            record(
                f"{width}x{height}_mongol_organization_moves_into_beijing_without_restoring_red_base_marker",
                bool(selected and clicked.get("ok") and confirmed.get("ok"))
                and any(entry.get("player") == "mongol" and int(entry.get("count") or 0) > 0 for entry in moved_state["beijing"])
                and not any(entry.get("player") == "mongol" and int(entry.get("count") or 0) > 0 for entry in moved_state["zhangjiakou"])
                and moved_state["movesLeft"] == 2
                and moved_state["beijingBadge"] == 0
                and moved_state["beijingBaseFaction"] is None,
                {"selected": selected, "clicked": clicked, "confirmed": confirmed, "state": moved_state},
            )
            frame = page.frame_locator("#strategicMapFrame")
            frame.locator("#searchBox").fill("北京")
            frame.locator("#fitFiltered").click()
            page.evaluate(
                """() => {
                  const frame = document.getElementById('strategicMapFrame').contentWindow;
                  frame.document.querySelector('.leaflet-popup-close-button')?.click();
                  frame.__selectTownForTest('北京');
                  frame.__openTownPopupForTest('北京');
                }"""
            )
            page.wait_for_timeout(300)
            screenshot = OUT / f"mongol_moved_to_beijing_{width}x{height}_20260823.png"
            page.screenshot(path=str(screenshot), full_page=True)
            screenshots.append(str(screenshot.relative_to(ROOT)))
            page.close()

        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {"total": len(checks), "passed": sum(check["passed"] for check in checks), "failed": sum(not check["passed"] for check in checks)}
    report = {"summary": summary, "service": BASE_URL, "scenario": "識別碼 [REDACTED]", "checks": checks, "screenshots": screenshots}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join(["# 紅軍根據地瓦解後標示驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "", *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], ""]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
