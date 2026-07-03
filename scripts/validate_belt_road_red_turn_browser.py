#!/usr/bin/env python3
"""Browser proof for 一帶一路南洋 red-turn build gating."""

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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = OUT_DIR / f"belt-road-red-turn-build-gating-{stamp}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-belt-road-red-turn-proof",
        {"advance_to_red": True, "event_name": "一帶一路 南洋"},
    )
    if setup.get("error"):
        raise AssertionError(setup)
    url = BASE_URL + setup["url"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(url, wait_until="networkidle")
        page.wait_for_function("window.lastGameState && window.lastGameState.pending_choice && window.lastGameState.pending_choice.choice_key === 'event_build_organization'", timeout=15000)
        before = page.evaluate("window.lastGameState")
        page.frame_locator("iframe").locator("body").wait_for(timeout=15000)
        page.evaluate("document.querySelector('iframe').contentWindow.sendDirectBuildAction('曼谷')")
        page.wait_for_function("window.lastGameState && !window.lastGameState.pending_choice && window.lastGameState.players.find(p => p.faction === 'red_army').orgs['曼谷'] === 1", timeout=15000)
        after_build = page.evaluate("window.lastGameState")
        page.locator("#advanceStepBtn").click()
        page.wait_for_function("window.lastGameState && window.lastGameState.turn_phase === 'end'", timeout=15000)
        after_advance = page.evaluate("window.lastGameState")
        screenshot_path = screenshot_dir / "after_bangkok_build_purchase_phase.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

    report = {
        "success": True,
        "url": url,
        "screenshot": str(screenshot_path),
        "before": {
            "turn_phase": before.get("turn_phase"),
            "pending_choice": (before.get("pending_choice") or {}).get("choice_key"),
            "current_event": (before.get("current_event") or {}).get("name"),
            "prompt": (before.get("pending_choice") or {}).get("prompt"),
        },
        "after_build": {
            "turn_phase": after_build.get("turn_phase"),
            "pending_choice": after_build.get("pending_choice"),
            "red_orgs": next(p for p in after_build["players"] if p["faction"] == "red_army")["orgs"],
            "log_tail": after_build.get("action_log", [])[-4:],
        },
        "after_advance": {
            "turn_phase": after_advance.get("turn_phase"),
            "pending_choice": after_advance.get("pending_choice"),
            "phase_label": "購買" if after_advance.get("turn_phase") == "end" else after_advance.get("turn_phase"),
            "log_tail": after_advance.get("action_log", [])[-4:],
        },
    }
    json_path = OUT_DIR / f"BELT_ROAD_RED_TURN_BROWSER_{stamp}.json"
    md_path = OUT_DIR / f"BELT_ROAD_RED_TURN_BROWSER_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        "# 一帶一路南洋 browser proof\n\n"
        f"- URL: {url}\n"
        "- Before: pending event_build_organization for 一帶一路 南洋\n"
        "- After build: 紅軍在曼谷有 1 組織，pending_choice = null\n"
        "- After advance: turn_phase = end（UI 購買階段）\n"
        f"- Screenshot: {screenshot_path}\n",
        encoding="utf-8",
    )
    print(json.dumps({"success": True, "json": str(json_path), "md": str(md_path), "screenshot": str(screenshot_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
