#!/usr/bin/env python3
"""Browser proof：待選效果使用自訂提示視窗，不再只顯示 HUD 提示或原生 alert。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/pending-choice-reminder-modal"
REPORT_JSON = OUT / "PENDING_CHOICE_REMINDER_MODAL_VALIDATION.json"
REPORT_MD = OUT / "PENDING_CHOICE_REMINDER_MODAL_VALIDATION.md"
SCREENSHOT_1280 = OUT / "pending_choice_reminder_1280x720_20260824.png"
SCREENSHOT_1024 = OUT / "pending_choice_reminder_1024x768_20260824.png"


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
    setup = post_setup()
    checks: list[dict] = []
    console_errors: list[str] = []
    dialogs: list[dict] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.on("dialog", lambda dialog: (dialogs.append({"type": dialog.type, "message": dialog.message}), dialog.dismiss()))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=pending-choice-modal-20260824",
            wait_until="networkidle",
        )
        page.wait_for_function("window.lastGameState && window.lastGameState.players?.length >= 2", timeout=15000)
        page.evaluate("closeEventReveal?.()")

        own_state = page.evaluate(
            """() => {
              const base = window.lastGameState;
              const me = base.players.find(player => player.id === playerId);
              const state = {...base, pending_choice: {
                type: 'option_choice', choice_key: 'guerrilla_reward', player_id: me.id,
                source_name: '游擊隊', prompt: '游擊隊：請選擇抽 1 張牌，或令紅軍棄 1 張手牌。',
                options: [{label:'抽 1 張牌'}, {label:'令紅軍棄 1 張手牌'}]
              }};
              closeChoiceModal();
              showPendingChoiceReminderModal(state);
              return {
                modalVisible: document.getElementById('choiceModal')?.style.display === 'flex',
                title: document.getElementById('choiceModalTitle')?.textContent.trim() || '',
                desc: document.getElementById('choiceModalDesc')?.textContent.trim() || '',
                options: Array.from(document.querySelectorAll('#choiceModalCards .modal-choice-btn')).map(button => button.textContent.trim()),
              };
            }"""
        )
        record(
            "owner_reopens_actionable_choice_modal",
            own_state["modalVisible"] and own_state["title"] == "游擊隊" and own_state["options"] == ["抽 1 張牌", "令紅軍棄 1 張手牌"],
            own_state,
        )
        page.evaluate("closeChoiceModal()")

        waiting_state = page.evaluate(
            """() => {
              const base = window.lastGameState;
              const me = base.players.find(player => player.id === playerId);
              const other = base.players.find(player => player.id !== me.id);
              const state = {...base, pending_choice: {
                type: 'option_choice', choice_key: 'guerrilla_reward', player_id: other.id,
                player_name: other.name, source_name: '游擊隊', prompt: '請進行選擇。',
                options: [{label:'抽 1 張牌'}, {label:'令紅軍棄 1 張手牌'}]
              }};
              showPendingChoiceReminderModal(state);
              const modal = document.getElementById('unavailableActionModal');
              const glass = modal?.querySelector('.unavailable-action-glass');
              const rect = glass?.getBoundingClientRect();
              return {
                modalVisible: modal?.style.display === 'flex' && modal?.getAttribute('aria-hidden') === 'false',
                title: document.getElementById('unavailableActionTitle')?.textContent.trim() || '',
                message: document.getElementById('unavailableActionMessage')?.textContent.trim() || '',
                ownerName: other.name,
                focusedId: document.activeElement?.id || '',
                hudNotice: document.getElementById('phaseActionNotice')?.textContent.trim() || '',
                rect: rect ? {left:rect.left, top:rect.top, right:rect.right, bottom:rect.bottom} : null,
              };
            }"""
        )
        page.wait_for_timeout(50)
        waiting_state["focusedId"] = page.evaluate("document.activeElement?.id || ''")
        page.screenshot(path=str(SCREENSHOT_1280), full_page=True)
        rect = waiting_state["rect"] or {}
        record(
            "other_player_wait_uses_custom_modal",
            waiting_state["modalVisible"] and waiting_state["title"] == "等待其他玩家處理效果" and waiting_state["ownerName"] in waiting_state["message"] and waiting_state["focusedId"] == "closeUnavailableActionModalBtn" and not waiting_state["hudNotice"],
            waiting_state,
        )
        record(
            "modal_fits_1280x720",
            rect and rect["left"] >= 0 and rect["top"] >= 0 and rect["right"] <= 1280 and rect["bottom"] <= 720,
            rect,
        )

        page.set_viewport_size({"width": 1024, "height": 768})
        page.wait_for_timeout(100)
        page.screenshot(path=str(SCREENSHOT_1024), full_page=True)
        rect_1024 = page.evaluate(
            """() => { const rect=document.querySelector('#unavailableActionModal .unavailable-action-glass')?.getBoundingClientRect(); return rect ? {left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom}:null; }"""
        )
        record(
            "modal_fits_1024x768",
            rect_1024 and rect_1024["left"] >= 0 and rect_1024["top"] >= 0 and rect_1024["right"] <= 1024 and rect_1024["bottom"] <= 768,
            rect_1024,
        )
        browser.close()

    record("pending_choice_prompt_uses_no_native_dialog", not dialogs, dialogs)
    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {"total": len(checks), "passed": sum(1 for check in checks if check["passed"]), "failed": sum(1 for check in checks if not check["passed"])}
    report = {"summary": summary, "service": BASE_URL, "checks": checks, "screenshots": [str(SCREENSHOT_1280.relative_to(ROOT)), str(SCREENSHOT_1024.relative_to(ROOT))]}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join(["# 待選效果提示視窗 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "", *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], ""]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
