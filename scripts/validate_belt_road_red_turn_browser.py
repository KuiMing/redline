#!/usr/bin/env python3
"""Browser proof for 一帶一路南洋 red-turn build gating and stale-choice recovery."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000")
OUT_DIR = ROOT / "docs" / "records" / "event-cards"


def post_json(path: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))


def run_case(browser, screenshot_dir: Path, *, stale_visual_build: bool, recovery_action: str = "build") -> dict:
    if stale_visual_build and recovery_action == "advance":
        case_name = "stale_advance_recovery"
    else:
        case_name = "stale_recovery" if stale_visual_build else "normal_generic_build"
    setup = post_json(
        "/test/setup-belt-road-red-turn-proof",
        {
            "advance_to_red": True,
            "event_name": "一帶一路 南洋",
            "stale_visual_build": stale_visual_build,
            "stale_town": "曼谷",
        },
    )
    if setup.get("error"):
        raise AssertionError(setup)
    url = BASE_URL + setup["url"]

    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(url, wait_until="networkidle")
    page.wait_for_function(
        "window.lastGameState && window.lastGameState.pending_choice && window.lastGameState.pending_choice.choice_key === 'event_build_organization'",
        timeout=15000,
    )
    before = page.evaluate("window.lastGameState")
    page.frame_locator("iframe").locator("body").wait_for(timeout=15000)
    page.evaluate("closeEventReveal?.()")
    page.wait_for_function("document.getElementById('eventRevealModal')?.style.display === 'none'")
    if recovery_action == "advance":
        page.locator("#advanceStepBtn").click()
    else:
        page.evaluate("document.querySelector('iframe').contentWindow.sendDirectBuildAction('曼谷')")
    page.wait_for_function(
        "window.lastGameState && !window.lastGameState.pending_choice && window.lastGameState.players.find(p => p.faction === 'red_army').orgs['曼谷'] === 1",
        timeout=15000,
    )
    after_build = page.evaluate("window.lastGameState")
    if after_build.get("current_player") != "BEN":
        page.evaluate("closeEventReveal?.()")
        page.locator("#advanceStepBtn").click()
    page.wait_for_function(
        "window.lastGameState && window.lastGameState.current_player === 'BEN' && !window.lastGameState.pending_choice",
        timeout=15000,
    )
    after_advance = page.evaluate("window.lastGameState")
    screenshot_path = screenshot_dir / f"{case_name}_after_bangkok_build_turn_advanced.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    page.close()

    return {
        "case": case_name,
        "url": "[REDACTED]",
        "screenshot": str(screenshot_path),
        "before": {
            "turn_phase": before.get("turn_phase"),
            "pending_choice": (before.get("pending_choice") or {}).get("choice_key"),
            "current_event": (before.get("current_event") or {}).get("name"),
            "prompt": (before.get("pending_choice") or {}).get("prompt"),
            "red_bangkok_orgs": next(p for p in before["players"] if p["faction"] == "red_army")["orgs"].get("曼谷", 0),
        },
        "after_build": {
            "turn_phase": after_build.get("turn_phase"),
            "pending_choice": after_build.get("pending_choice"),
            "red_bangkok_orgs": next(p for p in after_build["players"] if p["faction"] == "red_army")["orgs"].get("曼谷", 0),
            "log_tail": after_build.get("action_log", [])[-4:],
        },
        "after_advance": {
            "turn_phase": after_advance.get("turn_phase"),
            "pending_choice": after_advance.get("pending_choice"),
            "phase_label": after_advance.get("turn_phase"),
            "log_tail": after_advance.get("action_log", [])[-4:],
        },
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = OUT_DIR / f"belt-road-red-turn-build-gating-{stamp}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        cases = [
            run_case(browser, screenshot_dir, stale_visual_build=False),
            run_case(browser, screenshot_dir, stale_visual_build=True),
            run_case(browser, screenshot_dir, stale_visual_build=True, recovery_action="advance"),
        ]
        browser.close()

    report = {"success": True, "base_url": BASE_URL, "cases": cases}
    json_path = OUT_DIR / f"BELT_ROAD_RED_TURN_BROWSER_{stamp}.json"
    md_path = OUT_DIR / f"BELT_ROAD_RED_TURN_BROWSER_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "# 一帶一路南洋 browser proof\n\n"
        f"- Base URL: {BASE_URL}\n"
        "- Normal generic-build path: pending event_build_organization resolved, 紅軍在曼谷有 1 組織，phase advances to end/purchase.\n"
        "- Stale visual-build recovery path: 曼谷已有紅軍組織但 pending_choice 仍存在時，再按曼谷會清空 pending_choice，不重複建立，phase advances to end/purchase.\n"
        "- Stale advance-button recovery path: 曼谷已有紅軍組織但 pending_choice 仍存在時，直接按開始購買階段也會自動清空 pending_choice 並進入 end/purchase.\n"
        + "".join(f"- Screenshot ({case['case']}): {case['screenshot']}\n" for case in cases),
        encoding="utf-8",
    )
    print(json.dumps({"success": True, "json": str(json_path), "md": str(md_path), "screenshots": [c["screenshot"] for c in cases]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
