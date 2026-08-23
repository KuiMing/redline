#!/usr/bin/env python3
"""Browser proof：移除重複階段 chip 與紅軍陣營能力面板。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/remove-redundant-phase-and-red-army-panel"
JSON_PATH = OUT / "REMOVE_REDUNDANT_PHASE_AND_RED_ARMY_PANEL_VALIDATION.json"
MD_PATH = OUT / "REMOVE_REDUNDANT_PHASE_AND_RED_ARMY_PANEL_VALIDATION.md"
SHOT_1280 = OUT / "red_army_command_center_simplified_1280x720_20260823.png"
SHOT_1024 = OUT / "red_army_command_center_simplified_1024x768_20260823.png"


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

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=remove-redundant-red-ui-20260823",
            wait_until="networkidle",
        )
        page.wait_for_function(
            "window.lastGameState && getComputedStyle(document.getElementById('redArmyAbilityBtn')).display !== 'none'",
            timeout=15000,
        )
        page.evaluate("closeEventReveal?.()")
        page.wait_for_timeout(300)

        state = page.evaluate(
            """() => {
              const chipTexts = [...document.querySelectorAll('#hud .hud-chip')].map(element => element.textContent.trim());
              const panel = document.getElementById('factionActionPanel');
              const topButton = document.getElementById('redArmyAbilityBtn');
              const advance = document.getElementById('advanceStepBtn');
              const redBox = topButton.getBoundingClientRect();
              const advanceBox = advance.getBoundingClientRect();
              return {
                chipTexts,
                panelDisplay: getComputedStyle(panel).display,
                panelText: [
                  document.getElementById('factionActionInfo')?.textContent || '',
                  document.getElementById('factionActionButtons')?.textContent || '',
                ].join(' ').trim(),
                topButtonDisplay: getComputedStyle(topButton).display,
                topButtonText: topButton.textContent.trim(),
                advanceText: advance.textContent.trim(),
                topButtonParent: topButton.parentElement?.id || '',
                gap: advanceBox.left - redBox.right,
              };
            }"""
        )
        record(
            "hud_removes_redundant_action_phase_chip",
            "行動階段" not in state["chipTexts"] and state["chipTexts"][0] == "回合 1",
            {"chipTexts": state["chipTexts"]},
        )
        record(
            "red_army_faction_action_panel_is_removed",
            state["panelDisplay"] == "none" and not state["panelText"],
            {"display": state["panelDisplay"], "text": state["panelText"]},
        )
        record(
            "tab_row_red_army_button_remains_the_only_entry",
            state["topButtonDisplay"] != "none"
            and state["topButtonText"].startswith("紅軍能力 ")
            and state["topButtonParent"] == "turnActionButtons"
            and state["advanceText"] == "結束行動"
            and 0 <= state["gap"] <= 12,
            state,
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
        record("remaining_red_army_button_still_opens_modal", modal["display"] != "none" and modal["title"] == "紅軍能力", modal)
        page.locator("#closeFactionActionModal").click()

        non_red_panel = page.evaluate(
            """() => {
              const synthetic = structuredClone(window.lastGameState);
              const me = synthetic.players.find(player => player.id === playerId);
              me.faction = 'liberals';
              synthetic.current_player = me.name;
              synthetic.faction_action_used = false;
              synthetic.pending_choice = null;
              renderFactionActionPanel(synthetic);
              const panel = document.getElementById('factionActionPanel');
              return {
                display: getComputedStyle(panel).display,
                text: panel.textContent.trim(),
              };
            }"""
        )
        record(
            "non_red_faction_action_panels_are_not_removed",
            non_red_panel["display"] == "block" and "發動 立場試探" in non_red_panel["text"],
            non_red_panel,
        )
        page.evaluate("renderFactionActionPanel(window.lastGameState)")

        page.set_viewport_size({"width": 1024, "height": 768})
        page.wait_for_timeout(300)
        narrow = page.evaluate(
            """() => {
              const red = document.getElementById('redArmyAbilityBtn').getBoundingClientRect();
              const advance = document.getElementById('advanceStepBtn').getBoundingClientRect();
              return {
                red: {left: red.left, right: red.right, top: red.top, bottom: red.bottom},
                advance: {left: advance.left, right: advance.right, top: advance.top, bottom: advance.bottom},
                panelDisplay: getComputedStyle(document.getElementById('factionActionPanel')).display,
                chipTexts: [...document.querySelectorAll('#hud .hud-chip')].map(element => element.textContent.trim()),
              };
            }"""
        )
        record(
            "narrow_view_keeps_simplified_layout_inside_viewport",
            narrow["red"]["left"] >= 0
            and narrow["advance"]["right"] <= 1024
            and narrow["panelDisplay"] == "none"
            and "行動階段" not in narrow["chipTexts"],
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
        "# 精簡階段 chip 與紅軍陣營能力面板 Browser 驗證",
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
