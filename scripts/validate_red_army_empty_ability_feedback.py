#!/usr/bin/env python3
"""Browser proof：紅軍能力缺少合法目標或可用供應時顯示明確提示。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/playtest-flow/red-army-empty-ability-feedback"
REPORT_JSON = OUT / "RED_ARMY_EMPTY_ABILITY_FEEDBACK_VALIDATION.json"
REPORT_MD = OUT / "RED_ARMY_EMPTY_ABILITY_FEEDBACK_VALIDATION.md"
SCREENSHOT = OUT / "red_army_no_dissolve_target_notice_1280x720_20260823.png"
SCREENSHOT_1024 = OUT / "red_army_no_dissolve_target_notice_1024x768_20260823.png"


def post_setup() -> dict:
    request = urllib.request.Request(
        BASE_URL + "/test/setup-red-army-abilities-proof",
        data=json.dumps({"empty_actions": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    expected = {
        "政工部": "沒有可放到目標牌庫頂的卡牌",
        "國安部": "沒有可以瓦解的組織",
        "中紀委": "沒有手牌可以棄掉",
    }
    checks: list[dict] = []
    console_errors: list[str] = []
    dialogs: list[dict] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for ability_name, expected_text in expected.items():
            setup = post_setup()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))

            def accept_dialog(dialog, ability=ability_name):
                dialogs.append({"ability": ability, "type": dialog.type, "message": dialog.message})
                dialog.accept()

            page.on("dialog", accept_dialog)
            page.goto(
                f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=red-empty-ability-20260823",
                wait_until="networkidle",
            )
            page.wait_for_function("window.lastGameState && document.getElementById('redArmyAbilityBtn')?.style.display !== 'none'", timeout=15000)
            page.evaluate("closeEventReveal?.()")
            page.locator("#redArmyAbilityBtn").click()
            page.locator("#factionActionModalChoices .modal-choice-btn", has_text=f"發動 {ability_name}").click()
            page.wait_for_timeout(700)
            state = page.evaluate(
                """() => ({
                  notice: document.getElementById('phaseActionNotice')?.textContent.trim() || '',
                  noticeTitle: document.getElementById('phaseActionNotice')?.title || '',
                  noticeVisible: document.getElementById('phaseActionNotice')?.classList.contains('visible') || false,
                  pendingChoice: window.lastGameState?.pending_choice?.choice_key || null,
                  usedCount: Number(window.lastGameState?.red_army_action_count || 0),
                  result: window.lastGameState?.last_action_result || null,
                })"""
            )
            record(
                f"{ability_name}_shows_in_page_unavailable_notice",
                state["noticeVisible"] and expected_text in state["notice"] and state["noticeTitle"] == state["notice"] and state["pendingChoice"] is None and state["usedCount"] == 0,
                state,
            )
            if ability_name == "國安部":
                page.screenshot(path=str(SCREENSHOT), full_page=True)
                page.set_viewport_size({"width": 1024, "height": 768})
                page.wait_for_timeout(150)
                page.screenshot(path=str(SCREENSHOT_1024), full_page=True)
            page.close()
        browser.close()

    record("unavailable_abilities_do_not_use_blocking_alert", not dialogs, dialogs)
    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {"total": len(checks), "passed": sum(1 for check in checks if check["passed"]), "failed": sum(1 for check in checks if not check["passed"])}
    report = {
        "summary": summary,
        "service": BASE_URL,
        "scenario": "紅軍需要合法目標或可用供應的能力均無可執行內容；識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [str(SCREENSHOT.relative_to(ROOT)), str(SCREENSHOT_1024.relative_to(ROOT))],
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 紅軍能力無可執行內容 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
