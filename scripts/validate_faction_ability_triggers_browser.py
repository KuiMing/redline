#!/usr/bin/env python3
"""Formal browser proof for faction-trigger paths, including the reported Taiwan-green support build."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "faction-ui" / "trigger-audit"
REPORT_JSON = RECORD_DIR / "FACTION_ABILITY_TRIGGER_BROWSER_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "taiwan_green_support_build_turn_end.png"
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
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


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-support-proof",
        {
            "support_name": "東洋奧援",
            "tier": 3,
            "faction_id": "taiwan_green",
            "base": "臺北",
            "orgs": {"臺北": 1},
            "enemy_orgs": {"北京": 1},
            "draw_pile": ["補牌一", "補牌二", "補牌三", "補牌四", "補牌五", "本土社團加抽"],
            "player_name": "台灣綠線",
            "enemy_name": "紅軍",
        },
    )
    if not setup.get("success"):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as playwright:
        launch_options: dict[str, object] = {"headless": True}
        executable = browser_executable()
        if executable:
            launch_options["executable_path"] = executable
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until="domcontentloaded",
        )
        page.locator("#gameShell").wait_for(state="visible", timeout=15000)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.includes('東洋奧援')",
            arg=setup["player_id"],
            timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          document.getElementById('closeFactionActionModal')?.click();
          setActiveGameView('command');
        }""")

        page.locator("button.hand-card-action-btn[data-card-name='東洋奧援'][data-card-mode='action']").click()
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'support_interaction'",
            timeout=10000,
        )
        pending = page.evaluate("window.lastGameState.pending_choice")
        build_index = next(
            index for index, entry in enumerate(pending.get("towns") or []) if entry.get("town") == "成都"
        )
        page.evaluate("(index) => sendAction('resolve_choice', {index})", build_index)
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.orgs?.成都 === 1 && !window.lastGameState?.pending_choice",
            arg=setup["player_id"],
            timeout=10000,
        )
        built_state = page.evaluate("window.lastGameState")
        actor = next(player for player in built_state["players"] if player["id"] == setup["player_id"])
        record(
            "east_support_formally_builds_wall_inner_organization",
            actor.get("orgs", {}).get("成都") == 1,
            actor.get("orgs"),
        )
        record(
            "support_build_is_logged_before_turn_end",
            any("resolved 東洋奧援 and built in 成都" in entry for entry in built_state.get("action_log", [])),
            built_state.get("action_log", [])[-8:],
        )

        page.get_by_role("button", name="開始購買階段", exact=True).click()
        page.wait_for_function("window.lastGameState?.turn_phase === 'end'", timeout=10000)
        page.get_by_role("button", name="結束回合", exact=True).click()
        try:
            page.wait_for_function(
                """(id) => {
                  const state = window.lastGameState;
                  const actor = state?.players?.find(player => player.id === id);
                  return state?.current_player !== '台灣綠線'
                    && actor?.hand?.length === 6
                    && state?.action_log?.some(entry => entry.includes('triggered 本土社團 and drew 1 card'));
                }""",
                arg=setup["player_id"],
                timeout=15000,
            )
        except Exception:
            state = page.evaluate("window.lastGameState")
            print(json.dumps({
                "current_player": state.get("current_player"),
                "turn_phase": state.get("turn_phase"),
                "actor": next(player for player in state.get("players", []) if player.get("id") == setup["player_id"]),
                "action_log": state.get("action_log", [])[-12:],
                "pending_choice": state.get("pending_choice"),
            }, ensure_ascii=False, indent=2))
            raise
        final_state = page.evaluate("window.lastGameState")
        actor = next(player for player in final_state["players"] if player["id"] == setup["player_id"])
        action_log = final_state.get("action_log", [])
        trigger_index = next(
            (index for index, entry in enumerate(action_log) if "triggered 本土社團 and drew 1 card" in entry),
            -1,
        )
        end_index = next(
            (index for index, entry in enumerate(action_log) if "End of turn for 台灣綠線" in entry),
            -1,
        )
        record(
            "taiwan_green_native_society_draws_after_refill",
            len(actor.get("hand", [])) == 6 and "本土社團加抽" in actor.get("hand", []),
            actor.get("hand"),
        )
        record(
            "native_society_trigger_occurs_before_turn_closes",
            0 <= trigger_index < end_index,
            action_log[-10:],
        )

        page.get_by_role("button", name="戰況紀錄", exact=True).click()
        page.wait_for_timeout(300)
        battle_log_text = page.locator("body").inner_text()
        record(
            "official_battle_log_ui_shows_native_society_trigger",
            "triggered 本土社團 and drew 1 card" in battle_log_text,
            battle_log_text[-1200:],
        )
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        context.close()
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
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
