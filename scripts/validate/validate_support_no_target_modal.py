#!/usr/bin/env python3
"""Formal Playwright proof for the 東洋奧援 no-legal-target modal contract."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8769").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "support-cards" / "east-support-no-target-modal"
REPORT_JSON = RECORD_DIR / "SUPPORT_NO_TARGET_MODAL_VALIDATION.json"
REPORT_MD = RECORD_DIR / "SUPPORT_NO_TARGET_MODAL_VALIDATION.md"
SCREENSHOT = RECORD_DIR / "east_support_no_target_modal_1024x768.png"
RAW_ERROR = "No legal target for interactive support card"
MESSAGE = "這張奧援卡目前沒有合法目標。"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


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


def wait_for_error_state(page: Page) -> bool:
    try:
        page.wait_for_function("raw => window.lastGameState?.error === raw", arg=RAW_ERROR, timeout=8000)
        return True
    except PlaywrightTimeoutError:
        return False


def modal_snapshot(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const modal = document.getElementById('unavailableActionModal');
          const glass = modal?.querySelector('.unavailable-action-glass');
          const notice = document.getElementById('phaseActionNotice');
          const rect = glass?.getBoundingClientRect();
          return {
            visible: modal?.style.display === 'flex' && modal?.getAttribute('aria-hidden') === 'false',
            title: document.getElementById('unavailableActionTitle')?.textContent.trim() || '',
            message: document.getElementById('unavailableActionMessage')?.textContent.trim() || '',
            hudText: notice?.textContent.trim() || '',
            hudVisible: !!notice?.classList.contains('visible'),
            rect: rect ? {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom} : null,
          };
        }"""
    )


def player_state(page: Page, player_id: str) -> dict:
    return page.evaluate(
        """id => {
          const state = window.lastGameState || {};
          const me = (state.players || []).find(player => player.id === id) || {};
          return {
            rawError: state.error || '',
            hand: [...(me.hand || [])],
            discard: [...(me.discard_pile || [])],
            discardCount: Number(me.discard_count ?? (me.discard_pile || []).length),
            pendingChoice: state.pending_choice ?? null,
          };
        }""",
        player_id,
    )


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-support-proof",
        {
            "support_name": "東洋奧援",
            "tier": 3,
            "faction_id": "taiwan_green",
            "base": "臺北",
            "orgs": {"臺北": 22},
            "enemy_orgs": {"北京": 1},
            "matched_regions": ["東洋"],
            "player_name": "東洋奧援測試玩家",
            "enemy_name": "紅軍測試玩家",
        },
    )
    if not setup.get("success"):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []
    dialogs: list[dict] = []

    def record(name: str, passed: bool, details=None) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        launch_options: dict[str, object] = {"headless": True}
        executable = browser_executable()
        if executable:
            launch_options["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(viewport={"width": 1024, "height": 768})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))

        def dismiss_dialog(dialog) -> None:
            dialogs.append({"type": dialog.type, "message": dialog.message})
            dialog.dismiss()

        page.on("dialog", dismiss_dialog)
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=east-support-no-target-modal",
            wait_until="domcontentloaded",
        )
        page.locator("#gameShell").wait_for(state="visible", timeout=15000)
        page.wait_for_function(
            "id => window.lastGameState?.players?.find(player => player.id === id)?.hand?.includes('東洋奧援')",
            arg=setup["player_id"],
            timeout=15000,
        )
        page.evaluate(
            """() => {
              if (typeof closeEventReveal === 'function') closeEventReveal();
              if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
              document.getElementById('closeFactionActionModal')?.click();
              if (typeof setActiveGameView === 'function') setActiveGameView('command');
            }"""
        )

        action_button = page.locator(
            "button.hand-card-action-btn[data-card-name='東洋奧援'][data-card-mode='action']"
        )
        action_button.wait_for(state="visible", timeout=10000)
        before = player_state(page, setup["player_id"])
        action_button.click()
        first_error_received = wait_for_error_state(page)
        page.wait_for_timeout(150)
        first_modal = modal_snapshot(page)
        first_state = player_state(page, setup["player_id"])

        record("raw_server_error_received", first_error_received and first_state["rawError"] == RAW_ERROR, first_state["rawError"])
        record(
            "modal_visible_with_east_support_title_and_localized_message",
            first_modal["visible"]
            and first_modal["title"] == "東洋奧援無法使用"
            and first_modal["message"] == MESSAGE,
            first_modal,
        )
        record(
            "hud_notice_remains_empty_and_invisible",
            not first_modal["hudText"] and not first_modal["hudVisible"],
            {"text": first_modal["hudText"], "visible": first_modal["hudVisible"]},
        )
        record(
            "rejected_play_retains_card_discard_and_pending_state",
            first_state["hand"] == before["hand"]
            and first_state["hand"].count("東洋奧援") == before["hand"].count("東洋奧援") == 1
            and first_state["discard"] == before["discard"]
            and first_state["discardCount"] == before["discardCount"]
            and first_state["pendingChoice"] is None,
            {"before": before, "after": first_state},
        )

        close_icon = page.locator("#closeUnavailableActionModalIcon")
        if first_modal["visible"]:
            close_icon.click()
        closed_snapshot = modal_snapshot(page)
        closed_by_x = first_modal["visible"] and not closed_snapshot["visible"]
        record("icon_close_hides_modal", closed_by_x, closed_snapshot)

        page.evaluate("async () => { await render(window.lastGameState); }")
        page.wait_for_timeout(100)
        same_render = modal_snapshot(page)
        record("same_server_state_render_stays_closed", not same_render["visible"], same_render)

        action_button = page.locator(
            "button.hand-card-action-btn[data-card-name='東洋奧援'][data-card-mode='action']"
        )
        action_button.click()
        wait_for_error_state(page)
        try:
            page.wait_for_function(
                "() => document.getElementById('unavailableActionModal')?.style.display === 'flex'",
                timeout=8000,
            )
        except PlaywrightTimeoutError:
            pass
        second_modal = modal_snapshot(page)
        second_state = player_state(page, setup["player_id"])
        record(
            "second_same_turn_click_is_new_attempt_and_reopens",
            second_modal["visible"]
            and second_modal["title"] == "東洋奧援無法使用"
            and second_modal["message"] == MESSAGE,
            second_modal,
        )
        record(
            "second_rejection_also_preserves_zones_and_pending",
            second_state["hand"] == before["hand"]
            and second_state["discard"] == before["discard"]
            and second_state["discardCount"] == before["discardCount"]
            and second_state["pendingChoice"] is None,
            second_state,
        )

        page.screenshot(path=str(SCREENSHOT), full_page=True)
        rect = second_modal.get("rect") or {}
        record(
            "modal_fits_1024x768_viewport",
            bool(rect)
            and rect["right"] > rect["left"]
            and rect["bottom"] > rect["top"]
            and rect["left"] >= 0
            and rect["top"] >= 0
            and rect["right"] <= 1024
            and rect["bottom"] <= 768,
            rect,
        )
        context.close()
        browser.close()

    record("native_dialog_count_is_zero", len(dialogs) == 0, dialogs)
    record("browser_console_error_count_is_zero", len(console_errors) == 0, console_errors)
    passed = sum(1 for check in checks if check["passed"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "東洋奧援 tier 3；臺北反共組織供應已達 22，無合法建立目標",
        "service": BASE_URL,
        "status": "passed" if passed == len(checks) else "failed",
        "summary": {"passed": passed, "total": len(checks), "failed": len(checks) - passed},
        "checks": checks,
        "native_dialogs": dialogs,
        "console_errors": console_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(
        "\n".join(
            [
                "# 東洋奧援 no-target modal Browser 驗證",
                "",
                f"結果：**{passed}/{len(checks)} passed**",
                "",
                "情境：東洋奧援 tier 3；臺北反共組織供應已達 22，後端回傳無合法互動目標且交易回滾。",
                "",
                *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks],
                "",
                f"Screenshot: `{SCREENSHOT.relative_to(ROOT)}`",
                "",
                "重跑：`REDLINE_BASE_URL=http://127.0.0.1:8769 uv run --with playwright python scripts/validate/validate_support_no_target_modal.py`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
