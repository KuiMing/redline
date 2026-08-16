#!/usr/bin/env python3
"""Formal UI proof for 香港安全屋：基隆組織＋宣傳家在臺北建立會完成全國人大召開。"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "faction-ui" / "safehouse-taipei"
REPORT = RECORD_DIR / "SAFEHOUSE_TAIPEI_BROWSER_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "safehouse_taipei_npc_success.png"


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
        "chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-head-shell",
        "chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell",
        "chromium-*/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium",
    ]
    candidates = sorted(
        (path for pattern in patterns for path in cache.glob(pattern) if path.exists()),
        reverse=True,
    )
    return str(candidates[0]) if candidates else None


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-hand-preview", {
        "faction_id": "hong_kong",
        "base": "香港城",
        "orgs": {"香港城": 1, "基隆": 1},
        "hand_names": ["宣傳家"],
        "draw_pile": [f"補牌{i}" for i in range(1, 8)],
        "red_hand_names": [],
        "event_name": "全國人大召開",
    })
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
            "(id) => window.lastGameState?.players?.find(player => player.id === id)?.hand?.includes('宣傳家')",
            arg=setup["player_id"],
            timeout=15000,
        )
        page.evaluate("""() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          document.getElementById('closeFactionActionModal')?.click();
          setActiveGameView('command');
        }""")

        page.locator("button.hand-card-action-btn[data-card-name='宣傳家'][data-card-mode='action']").click()
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'",
            timeout=10000,
        )
        pending = page.evaluate("window.lastGameState.pending_choice")
        target_entry = next(item for item in pending.get("towns") or [] if item.get("town") == "臺北")
        record("propagandist_projects_taipei_as_legal_target", bool(target_entry), target_entry)

        frame = page.frame_locator("#strategicMapFrame")
        frame.locator("#map").wait_for(state="visible", timeout=15000)
        map_frame = next(frame for frame in page.frames if "leaflet_game_map.html" in frame.url)
        map_frame.wait_for_function("currentMarkers?.has('臺北') && map", timeout=10000)
        map_frame.evaluate("() => { map.setView([byName.get('臺北').lat, byName.get('臺北').lon], 8, {animate:false}); }")
        page.wait_for_timeout(250)
        map_frame.evaluate("() => { currentMarkers.get('臺北').fire('click'); }")
        frame.locator("#directBuildBtn").wait_for(state="visible", timeout=5000)
        frame.locator("#directBuildBtn").click()

        page.wait_for_function(
            """(id) => {
              const state = window.lastGameState;
              const actor = state?.players?.find(player => player.id === id);
              return actor?.orgs?.臺北 === 1
                && state?.action_log?.some(entry => entry.includes('triggered 安全屋 while building in 臺北'));
            }""",
            arg=setup["player_id"],
            timeout=10000,
        )
        built_state = page.evaluate("window.lastGameState")
        actor = next(player for player in built_state["players"] if player["id"] == setup["player_id"])
        record("taipei_organization_is_built_through_map_selection", actor.get("orgs", {}).get("臺北") == 1, actor.get("orgs"))
        record(
            "safehouse_trigger_is_logged",
            any("triggered 安全屋 while building in 臺北" in entry for entry in built_state.get("action_log", [])),
            built_state.get("action_log", [])[-8:],
        )
        battle_text_before_settlement = page.locator("body").inner_text()
        record(
            "national_people_congress_is_success_pending",
            "任務進度 1/1" in battle_text_before_settlement,
            "任務進度 1/1" if "任務進度 1/1" in battle_text_before_settlement else battle_text_before_settlement[-800:],
        )

        page.get_by_role("button", name="開始購買階段", exact=True).click()
        page.wait_for_function("window.lastGameState?.turn_phase === 'end'", timeout=10000)
        page.get_by_role("button", name="結束回合", exact=True).click()
        page.wait_for_function(
            """(id) => {
              const state = window.lastGameState;
              const actor = state?.players?.find(player => player.id === id);
              return actor?.hand?.length === 6
                && state?.action_log?.some(entry => entry.includes('Event success resolved: 全國人大召開'));
            }""",
            arg=setup["player_id"],
            timeout=15000,
        )
        final_state = page.evaluate("window.lastGameState")
        actor = next(player for player in final_state["players"] if player["id"] == setup["player_id"])
        record("event_success_draws_one_extra_card_after_refill", len(actor.get("hand", [])) == 6, actor.get("hand"))
        record(
            "event_success_is_visible_in_battle_log",
            any("Event success resolved: 全國人大召開" in entry for entry in final_state.get("action_log", [])),
            final_state.get("action_log", [])[-10:],
        )

        page.get_by_role("button", name="戰況紀錄", exact=True).click()
        page.wait_for_timeout(300)
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        record("browser_console_has_no_errors", not console_errors, console_errors)
        context.close()
        browser.close()

    passed = sum(check["ok"] for check in checks)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "status": "passed" if passed == len(checks) else "failed",
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "console_errors": console_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(checks), "passed": passed, "failed": len(checks) - passed}, ensure_ascii=False))
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
