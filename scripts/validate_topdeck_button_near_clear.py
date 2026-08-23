#!/usr/bin/env python3
"""Browser proof：「卡牌置頂」位於購買控制列的「清除」旁邊。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/topdeck-near-clear"
REPORT_JSON = OUT / "TOPDECK_NEAR_CLEAR_VALIDATION.json"
REPORT_MD = OUT / "TOPDECK_NEAR_CLEAR_VALIDATION.md"


def setup_proof() -> dict:
    request = urllib.request.Request(
        BASE_URL + "/test/setup-end-turn-topdeck-proof",
        data=json.dumps({"phase": "action", "pending_topdeck_uses": 1, "bought_cards": ["行動預告", "輿論不墜"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    console_errors: list[str] = []
    screenshots: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in ((1280, 720), (1024, 768)):
            setup = setup_proof()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=topdeck-near-clear-proof", wait_until="networkidle")
            page.wait_for_function("window.lastGameState && document.getElementById('topdeckRightBtn')?.style.display !== 'none'", timeout=15000)
            page.evaluate("closeEventReveal?.()")
            page.wait_for_timeout(150)
            layout = page.evaluate(
                """() => {
                  const box = el => { const r=el.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}; };
                  const controls=document.getElementById('purchaseSelectionControls');
                  const clear=document.getElementById('clearPurchaseSelectionBtn');
                  const topdeck=document.getElementById('topdeckRightBtn');
                  const buy=document.getElementById('openPurchaseConfirmBtn');
                  const secondary=document.getElementById('phaseActionBar');
                  const hud=document.getElementById('hud');
                  const shell=document.getElementById('gameShell');
                  return {
                    text:topdeck.textContent.trim(), title:topdeck.title, disabled:topdeck.disabled,
                    parentId:topdeck.parentElement?.id || '', previousId:topdeck.previousElementSibling?.id || '', nextId:topdeck.nextElementSibling?.id || '',
                    controls:box(controls), clear:box(clear), topdeck:box(topdeck), buy:box(buy), hud:box(hud), shell:box(shell),
                    secondaryDisplay:getComputedStyle(secondary).display,
                    position:getComputedStyle(topdeck).position,
                  };
                }"""
            )
            scale = layout["hud"]["width"] / 1280
            same_row = abs(layout["clear"]["top"] - layout["topdeck"]["top"]) <= 1 and abs(layout["clear"]["height"] - layout["topdeck"]["height"]) <= 1
            adjacent = layout["clear"]["left"] >= layout["topdeck"]["right"] and layout["clear"]["left"] - layout["topdeck"]["right"] <= 16 * scale
            record(f"{width}x{height}_topdeck_is_renamed_and_left_of_clear", layout["text"] == "卡牌置頂 (1)" and layout["parentId"] == "purchaseSelectionControls" and layout["previousId"] == "purchaseSelectionSummary" and layout["nextId"] == "clearPurchaseSelectionBtn" and same_row and adjacent and layout["position"] == "static", layout)
            record(f"{width}x{height}_topdeck_no_longer_creates_secondary_row", layout["secondaryDisplay"] == "none" and layout["shell"]["top"] <= layout["hud"]["bottom"] + 10 * scale, {"secondaryDisplay": layout["secondaryDisplay"], "hud": layout["hud"], "shell": layout["shell"], "scale": scale})

            screenshot = OUT / f"topdeck_near_clear_{width}x{height}_20260823.png"
            page.screenshot(path=str(screenshot), full_page=True)
            screenshots.append(str(screenshot.relative_to(ROOT)))

            if width == 1280:
                page.locator("#topdeckRightBtn").click()
                page.wait_for_function("window.lastGameState?.pending_choice?.choice_key === 'topdeck_purchased_choice'")
                record("card_topdeck_button_keeps_existing_choice_flow", page.evaluate("document.getElementById('choiceModal')?.style.display === 'flex' && window.lastGameState.pending_topdeck_uses === 0"), {"choiceKey": page.evaluate("window.lastGameState?.pending_choice?.choice_key"), "pendingUses": page.evaluate("window.lastGameState?.pending_topdeck_uses")})
            page.close()
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {"total": len(checks), "passed": sum(check["passed"] for check in checks), "failed": sum(not check["passed"] for check in checks)}
    report = {"summary": summary, "service": BASE_URL, "scenario": "識別碼 [REDACTED]", "checks": checks, "screenshots": screenshots}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join(["# 卡牌置頂按鈕位置驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "", *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], ""]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
