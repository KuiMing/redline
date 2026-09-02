#!/usr/bin/env python3
"""Formal browser proof that each faction filter produces a visible strategic-map camera focus."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "map-ui" / "faction-filter-focus"
REPORT_JSON = RECORD_DIR / "FACTION_FILTER_FOCUS_BROWSER_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "hong_kong_filter_focus.png"
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def browser_executable() -> str | None:
    configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
    if configured and Path(configured).exists():
        return configured
    cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    patterns = [
        "chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell",
        "chromium_headless_shell-*/chrome-headless-shell-mac/headless_shell",
        "chromium-*/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium",
        "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    ]
    candidates = sorted(
        (path for pattern in patterns for path in cache.glob(pattern) if path.exists()),
        reverse=True,
    )
    return str(candidates[0]) if candidates else None


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        launch_options: dict[str, object] = {"headless": True}
        executable = browser_executable()
        if executable:
            launch_options["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(f"{BASE_URL}/static/leaflet_game_map.html", wait_until="domcontentloaded")
        page.wait_for_function("typeof map !== 'undefined' && towns?.length > 0 && currentVisible?.length > 0")
        camps = page.eval_on_selector_all(
            "#campFilter option",
            "options => options.map(option => option.value).filter(Boolean)",
        )

        for camp in camps:
            page.evaluate("focusAsia()")
            page.wait_for_timeout(150)
            before = page.evaluate("({zoom: map.getZoom(), center: map.getCenter()})")
            page.select_option("#campFilter", camp)
            page.dispatch_event("#campFilter", "input")
            page.wait_for_function(
                "camp => document.querySelector('#campFilter').value === camp && currentVisible.length > 0",
                arg=camp,
            )
            filtered_count = page.evaluate("currentVisible.length")
            page.click("#fitFiltered")
            page.wait_for_timeout(900)
            after = page.evaluate("({zoom: map.getZoom(), center: map.getCenter(), audit: window.__lastFilterFocus || null})")
            changed = (
                after["zoom"] > before["zoom"]
                or abs(after["center"]["lat"] - before["center"]["lat"]) >= 2
                or abs(after["center"]["lng"] - before["center"]["lng"]) >= 2
            )
            audit = after.get("audit") or {}
            centered = (
                audit.get("targetCenter")
                and abs(after["center"]["lat"] - audit["targetCenter"][0]) < 1
                and abs(after["center"]["lng"] - audit["targetCenter"][1]) < 1
            )
            ok = (
                filtered_count > 0
                and after["zoom"] >= 4
                and changed
                and audit.get("faction") == camp
                and audit.get("strategy") == "median-cluster"
                and centered
            )
            checks.append({
                "name": f"faction_filter_{camp}_visibly_focuses",
                "ok": ok,
                "detail": {"camp": camp, "filtered_count": filtered_count, "before": before, "after": after},
            })

        page.select_option("#campFilter", "香港")
        page.dispatch_event("#campFilter", "input")
        page.click("#fitFiltered")
        page.wait_for_timeout(900)
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        context.close()
        browser.close()

    checks.append({"name": "browser_console_has_no_errors", "ok": not console_errors, "detail": console_errors})
    passed = sum(check["ok"] for check in checks)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "status": "passed" if passed == len(checks) else "failed",
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "console_errors": console_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(checks), "passed": passed, "failed": len(checks) - passed}, ensure_ascii=False))
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
