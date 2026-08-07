#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "state-guards" / "pending-choice-board-actions"
REPORT_JSON = RECORD_DIR / "PENDING_CHOICE_BOARD_ACTION_GUARD_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "pending_choice_blocks_board_actions.png"
EXPECTED_ERROR = "請先完成目前的選擇"


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def state_projection(state: dict, actor_id: str, red_id: str) -> dict:
    actor = next(player for player in state["players"] if player["id"] == actor_id)
    red = next(player for player in state["players"] if player["id"] == red_id)
    pending = state.get("pending_choice") or {}
    return {
        "town_control": state.get("town_control"),
        "actor_resources": actor.get("resources"),
        "actor_moves": actor.get("moves_left"),
        "actor_base": actor.get("base"),
        "red_base": red.get("base"),
        "pending_choice_key": pending.get("choice_key"),
        "pending_player_id": pending.get("player_id"),
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-pending-choice-board-guard")
    if not setup.get("success"):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []
    dialogs: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))

        def accept_dialog(dialog) -> None:
            dialogs.append(dialog.message)
            dialog.accept()

        page.on("dialog", accept_dialog)
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until="domcontentloaded",
        )
        page.locator("#gameShell").wait_for(state="visible", timeout=15000)
        page.wait_for_function(
            "() => window.lastGameState?.pending_choice?.choice_key === 'recruit_talent'",
            timeout=10000,
        )
        page.evaluate(
            """() => {
              document.getElementById('closeFactionActionModal')?.click();
              if (typeof closeEventReveal === 'function') closeEventReveal();
              if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
            }"""
        )
        page.locator("#choiceModal").wait_for(state="visible", timeout=10000)
        prompt_text = page.locator("#choiceModalDesc").inner_text().strip()
        record(
            "required_card_choice_remains_visible",
            prompt_text == "網羅人才：請選擇一張牌。",
            {"prompt": prompt_text},
        )

        before = state_projection(
            page.evaluate("window.lastGameState"), setup["player_id"], setup["red_player_id"]
        )
        move = setup["move"]
        attempts = [
            ("direct_build", {"action": "build", "town": "臺北"}),
            ("supported_build", {"action": "build", "from": "臺北", "town": "桃園"}),
            ("move", {"action": "move", **move}),
            ("dissolve", {"action": "dissolve", "defender": setup["red_player_id"], "town": "上海"}),
            ("relocate_base", {"action": "relocate_base", "town": "倫敦"}),
        ]
        for name, payload in attempts:
            dialog_count = len(dialogs)
            page.evaluate("payload => ws.send(JSON.stringify(payload))", payload)
            page.wait_for_timeout(250)
            new_dialogs = dialogs[dialog_count:]
            record(
                f"{name}_is_blocked_with_clear_message",
                new_dialogs == [EXPECTED_ERROR],
                {"dialogs": new_dialogs, "payload": payload},
            )

        after_state = page.evaluate("window.lastGameState")
        after = state_projection(after_state, setup["player_id"], setup["red_player_id"])
        record(
            "blocked_actions_leave_board_and_pending_choice_unchanged",
            before == after and after["pending_choice_key"] == "recruit_talent",
            {"before": before, "after": after},
        )
        page.locator("#choiceModal").wait_for(state="visible", timeout=5000)
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "status": "passed" if all(check["ok"] for check in checks) else "failed",
        "checks_passed": sum(1 for check in checks if check["ok"]),
        "checks_total": len(checks),
        "checks": checks,
        "console_errors": console_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "checks_passed": report["checks_passed"],
        "checks_total": report["checks_total"],
    }, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
