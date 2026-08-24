#!/usr/bin/env python3
"""Browser proof：Lobby 使用大型陣營／根據地選擇視窗，且可重新開啟。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/faction-ui/faction-picker-modal"
REPORT_JSON = OUT / "FACTION_PICKER_MODAL_VALIDATION.json"
REPORT_MD = OUT / "FACTION_PICKER_MODAL_VALIDATION.md"
SCREENSHOT_1280 = OUT / "uyghur_faction_picker_1280x720_20260824.png"
SCREENSHOT_1024 = OUT / "uyghur_faction_picker_1024x768_20260824.png"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        host = browser.new_page(viewport={"width": 1280, "height": 720})
        host.on("console", lambda message: console_errors.append(f"host:{message.text}") if message.type == "error" else None)
        host.on("pageerror", lambda error: console_errors.append(f"host:{error}"))
        host.goto(BASE_URL, wait_until="networkidle")
        host.fill("#playerName", "host")
        host.click("#createRoomBtn")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'")

        initial = host.evaluate(
            """() => {
              const overlay = document.getElementById('factionPicker');
              const dialog = document.querySelector('.faction-picker-dialog');
              const rect = dialog?.getBoundingClientRect();
              return {
                visible: overlay?.style.display === 'flex' && overlay?.getAttribute('aria-hidden') === 'false',
                title: document.getElementById('factionPickerTitle')?.textContent.trim() || '',
                categories: Array.from(document.querySelectorAll('#factionList button')).map(button => button.textContent.trim()),
                detailPlaceholder: document.getElementById('factionDetailPanel')?.textContent.trim() || '',
                focusedId: document.activeElement?.id || '',
                rect: rect ? {left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom,width:rect.width,height:rect.height}:null,
              };
            }"""
        )
        record(
            "create_room_auto_opens_large_picker",
            initial["visible"] and initial["title"] == "選擇陣營與根據地" and len(initial["categories"]) >= 9 and "能力與觸發條件" in initial["detailPlaceholder"] and initial["focusedId"] == "closeFactionPickerBtn",
            initial,
        )
        rect = initial["rect"] or {}
        record(
            "picker_fits_1280x720",
            bool(rect) and rect["left"] >= 0 and rect["top"] >= 0 and rect["right"] <= 1280 and rect["bottom"] <= 720 and rect["width"] >= 1000,
            rect,
        )
        host.press("#closeFactionPickerBtn", "Shift+Tab")
        focus_trap = host.evaluate("document.activeElement?.closest('#factionPicker')?.id === 'factionPicker'")
        record("keyboard_focus_stays_inside_picker", focus_trap, {"focusedId": host.evaluate("document.activeElement?.id || ''"), "insidePicker": focus_trap})
        host.locator("#closeFactionPickerBtn").focus()

        host.locator("#factionList button", has_text="維吾爾").click()
        host.wait_for_function("document.querySelectorAll('#factionBaseList button').length >= 4")
        host.locator("#factionBaseList button", has_text="伊斯坦堡").click()
        host.wait_for_function("document.getElementById('confirmFactionBtn')?.offsetParent !== null")
        selected = host.evaluate(
            """() => ({
              detail: document.getElementById('factionDetailPanel')?.textContent.trim() || '',
              info: document.getElementById('factionPickerInfo')?.textContent.trim() || '',
              confirmText: document.getElementById('confirmFactionBtn')?.textContent.trim() || '',
              activeCategory: document.querySelector('#factionList .active')?.textContent.trim() || '',
              activeBase: document.querySelector('#factionBaseList .active')?.textContent.trim() || '',
            })"""
        )
        record(
            "selected_faction_shows_ability_restriction_and_win_condition",
            selected["activeCategory"] == "維吾爾" and selected["activeBase"] == "伊斯坦堡" and "游擊隊" in selected["detail"] and "新疆社會管控" in selected["detail"] and "獲勝條件" in selected["detail"] and selected["confirmText"] == "確認陣營與根據地",
            selected,
        )
        host.screenshot(path=str(SCREENSHOT_1280), full_page=True)

        host.click("#confirmFactionBtn")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'none'")
        post_confirm = host.evaluate(
            """() => ({
              modalHidden: document.getElementById('factionPicker')?.style.display === 'none',
              reopenText: document.getElementById('openFactionPickerBtn')?.textContent.trim() || '',
              reopenDisabled: document.getElementById('openFactionPickerBtn')?.disabled,
              roster: document.getElementById('lobbyRoster')?.textContent.trim() || '',
            })"""
        )
        record(
            "confirm_returns_to_lobby_with_reopen_button",
            post_confirm["modalHidden"] and post_confirm["reopenText"] == "變更陣營與根據地" and not post_confirm["reopenDisabled"] and "維吾爾" in post_confirm["roster"] and "伊斯坦堡" in post_confirm["roster"],
            post_confirm,
        )

        host.click("#openFactionPickerBtn")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'")
        reopened = host.evaluate(
            """() => ({
              info: document.getElementById('factionPickerInfo')?.textContent.trim() || '',
              activeCategory: document.querySelector('#factionList .active')?.textContent.trim() || '',
              activeBase: document.querySelector('#factionBaseList .active')?.textContent.trim() || '',
            })"""
        )
        record(
            "reopen_restores_confirmed_selection",
            reopened["activeCategory"] == "維吾爾" and reopened["activeBase"] == "伊斯坦堡" and "維吾爾" in reopened["info"] and "伊斯坦堡" in reopened["info"],
            reopened,
        )

        host.set_viewport_size({"width": 1024, "height": 768})
        host.wait_for_timeout(120)
        host.screenshot(path=str(SCREENSHOT_1024), full_page=True)
        rect_1024 = host.evaluate(
            """() => { const rect=document.querySelector('.faction-picker-dialog')?.getBoundingClientRect(); return rect ? {left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom,width:rect.width,height:rect.height}:null; }"""
        )
        record(
            "picker_fits_1024x768",
            bool(rect_1024) and rect_1024["left"] >= 0 and rect_1024["top"] >= 0 and rect_1024["right"] <= 1024 and rect_1024["bottom"] <= 768,
            rect_1024,
        )
        host.press("body", "Escape")
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'none'")
        record("escape_returns_to_lobby", True, {"display": "none"})

        room_id = host.input_value("#roomId")
        visitor = browser.new_page(viewport={"width": 1280, "height": 720})
        visitor.on("console", lambda message: console_errors.append(f"visitor:{message.text}") if message.type == "error" else None)
        visitor.on("pageerror", lambda error: console_errors.append(f"visitor:{error}"))
        visitor.goto(BASE_URL, wait_until="networkidle")
        visitor.fill("#roomId", room_id)
        visitor.fill("#playerName", "visitor")
        visitor.click("#joinRoomBtn")
        visitor.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'")
        join_state = visitor.evaluate(
            """() => ({
              visible: document.getElementById('factionPicker')?.style.display === 'flex',
              info: document.getElementById('factionPickerInfo')?.textContent.trim() || '',
              reopenEnabled: !document.getElementById('openFactionPickerBtn')?.disabled,
            })"""
        )
        record(
            "join_room_auto_opens_picker",
            join_state["visible"] and "請先選擇" in join_state["info"] and join_state["reopenEnabled"],
            join_state,
        )
        visitor.close()
        host.close()
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {"total": len(checks), "passed": sum(1 for check in checks if check["passed"]), "failed": sum(1 for check in checks if not check["passed"])}
    report = {"summary": summary, "service": BASE_URL, "checks": checks, "screenshots": [str(SCREENSHOT_1280.relative_to(ROOT)), str(SCREENSHOT_1024.relative_to(ROOT))]}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join(["# 大型陣營與根據地選擇視窗 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "", *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], ""]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
