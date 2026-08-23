#!/usr/bin/env python3
"""Browser proof：紅軍能力按鈕位於結束行動左側並相鄰。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/red-army-ability-next-to-end-action"
JSON_PATH = OUT / "RED_ARMY_ABILITY_NEXT_TO_END_ACTION_VALIDATION.json"
MD_PATH = OUT / "RED_ARMY_ABILITY_NEXT_TO_END_ACTION_VALIDATION.md"
SHOT_1280 = OUT / "red_army_ability_next_to_end_action_1280x720_20260823.png"
SHOT_1024 = OUT / "red_army_ability_next_to_end_action_1024x768_20260823.png"


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-red-army-abilities-proof")
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    def geometry(page) -> dict:
        return page.evaluate(
            """() => {
              const rect = id => {
                const element = document.getElementById(id);
                if (!element) return null;
                const box = element.getBoundingClientRect();
                return {
                  left: box.left, top: box.top, right: box.right, bottom: box.bottom,
                  width: box.width, height: box.height, display: getComputedStyle(element).display,
                  parentId: element.parentElement?.id || '',
                };
              };
              const red = rect('redArmyAbilityBtn');
              const advance = rect('advanceStepBtn');
              const tabs = rect('gameTabs');
              return {
                red, advance, tabs,
                redText: document.getElementById('redArmyAbilityBtn')?.textContent || '',
                advanceText: document.getElementById('advanceStepBtn')?.textContent || '',
                gap: red && advance ? advance.left - red.right : null,
                verticalDelta: red && advance ? Math.abs((red.top + red.bottom) / 2 - (advance.top + advance.bottom) / 2) : null,
                phaseBarDisplay: getComputedStyle(document.getElementById('phaseActionBar')).display,
              };
            }"""
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=red-ability-next-to-end-action-20260823",
            wait_until="networkidle",
        )
        page.wait_for_function(
            "getComputedStyle(document.getElementById('redArmyAbilityBtn')).display !== 'none' && document.getElementById('advanceStepBtn')?.textContent === '結束行動'",
            timeout=15000,
        )
        page.evaluate("closeEventReveal?.()")
        page.wait_for_timeout(300)

        wide = geometry(page)
        record(
            "red_army_button_is_immediately_left_of_end_action",
            wide["red"]["parentId"] == "turnActionButtons"
            and wide["advance"]["parentId"] == "turnActionButtons"
            and 0 <= wide["gap"] <= 12
            and wide["verticalDelta"] <= 1
            and wide["red"]["right"] <= wide["advance"]["left"],
            wide,
        )
        record(
            "red_army_button_keeps_expected_labels",
            wide["redText"].startswith("紅軍能力 ") and wide["advanceText"] == "結束行動",
            {"red": wide["redText"], "advance": wide["advanceText"]},
        )
        record(
            "red_army_button_no_longer_opens_secondary_bar_by_itself",
            wide["phaseBarDisplay"] == "none",
            {"phaseBarDisplay": wide["phaseBarDisplay"]},
        )
        page.screenshot(path=str(SHOT_1280), full_page=True)

        page.locator("#redArmyAbilityBtn").click()
        page.wait_for_function("getComputedStyle(document.getElementById('factionActionModal')).display !== 'none'")
        modal = page.evaluate(
            """() => ({
              display: getComputedStyle(document.getElementById('factionActionModal')).display,
              title: document.getElementById('factionActionModalTitle')?.textContent || '',
            })"""
        )
        record("moved_button_still_opens_red_army_ability_modal", modal["display"] != "none" and modal["title"] == "紅軍能力", modal)
        page.locator("#closeFactionActionModal").click()

        page.set_viewport_size({"width": 1024, "height": 768})
        page.wait_for_timeout(300)
        narrow = geometry(page)
        record(
            "narrow_view_keeps_adjacent_buttons_inside_viewport",
            narrow["red"]["left"] >= 0
            and narrow["advance"]["right"] <= 1024
            and 0 <= narrow["gap"] <= 12
            and narrow["verticalDelta"] <= 1,
            narrow,
        )
        page.screenshot(path=str(SHOT_1024), full_page=True)
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
        "scenario": "紅軍行動階段；識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [str(SHOT_1280.relative_to(ROOT)), str(SHOT_1024.relative_to(ROOT))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text("\n".join([
        "# 紅軍能力按鈕與結束行動相鄰 Browser 驗證",
        "",
        f"Summary: **{summary['passed']}/{summary['total']} passed**",
        "",
        *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks],
        "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
