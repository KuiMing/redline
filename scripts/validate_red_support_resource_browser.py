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
RECORD_DIR = ROOT / "docs" / "records" / "support-cards" / "red-support-resource"
REPORT_JSON = RECORD_DIR / "RED_SUPPORT_RESOURCE_BROWSER_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "red_support_resource.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-support-card-play",
        {
            "support_name": "紅軍奧援",
            "faction_id": "red_army",
            "base": "北京",
            "orgs": {"北京": 1},
            "resources": {"money": 0, "propaganda": 0},
            "enemy_faction_id": "liberals",
            "enemy_base": "臺北",
            "enemy_orgs": {"臺北": 1},
        },
    )
    if not setup.get("success"):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until="domcontentloaded",
        )
        page.locator("#gameShell").wait_for(state="visible", timeout=15000)
        page.evaluate(
            """() => {
              document.getElementById('closeFactionActionModal')?.click();
              if (typeof closeEventReveal === 'function') closeEventReveal();
              if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
              setActiveGameView('command');
            }"""
        )

        resource_button = page.locator(
            '#hand .hand-card-action-btn[data-card-name="紅軍奧援"][data-card-mode="resource"]'
        )
        resource_button.wait_for(state="visible", timeout=10000)
        button_detail = {
            "text": resource_button.inner_text().strip(),
            "title": resource_button.get_attribute("title"),
            "disabled": resource_button.is_disabled(),
        }
        record(
            "formal_ui_shows_enabled_resource_button_for_red_support",
            button_detail["text"] == "資源"
            and not button_detail["disabled"]
            and "1資金" in (button_detail["title"] or "")
            and "1宣傳" in (button_detail["title"] or ""),
            button_detail,
        )

        resource_button.click()
        actor_id_json = json.dumps(setup["player_id"])
        page.wait_for_function(
            f"""() => {{
              const state = window.lastGameState;
              const me = state?.players?.find(player => player.id === {actor_id_json});
              return !state?.pending_choice
                && me?.resources?.money === 1
                && me?.resources?.propaganda === 1
                && !me?.hand?.includes('紅軍奧援');
            }}""",
            timeout=10000,
        )

        state = page.evaluate("window.lastGameState")
        actor = next(player for player in state["players"] if player["id"] == setup["player_id"])
        target = next(player for player in state["players"] if player["id"] == setup["red_player_id"])
        record(
            "resource_mode_finishes_without_discard_target_choice",
            state.get("pending_choice") is None,
            {"pending_choice": state.get("pending_choice")},
        )
        record(
            "resource_mode_grants_exactly_one_money_and_one_propaganda_without_draw",
            actor.get("resources") == {"money": 1, "propaganda": 1}
            and actor.get("hand") == [],
            {"resources": actor.get("resources"), "hand": actor.get("hand")},
        )
        record(
            "resource_mode_discards_red_support_to_its_users_own_discard",
            actor.get("discard_pile") == ["紅軍奧援"]
            and target.get("discard_pile") == [],
            {"actor_discard": actor.get("discard_pile"), "target_discard": target.get("discard_pile")},
        )

        page.evaluate("setActiveGameView('log')")
        page.locator("#logView").wait_for(state="visible", timeout=5000)
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
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "checks_passed": report["checks_passed"],
        "checks_total": report["checks_total"],
    }, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
