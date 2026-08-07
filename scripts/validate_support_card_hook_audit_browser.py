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
RECORD_DIR = ROOT / "docs" / "records" / "support-cards" / "hook-audit"
REPORT_JSON = RECORD_DIR / "SUPPORT_CARD_HOOK_AUDIT_BROWSER_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "india_support_reaction_and_supply.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def connect_page(context, game_id: str, player_id: str, console_errors: list[str]):
    page = context.new_page()
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: console_errors.append(str(error)))
    page.goto(f"{BASE_URL}/?game_id={game_id}&player_id={player_id}", wait_until="domcontentloaded")
    page.locator("#gameShell").wait_for(state="visible", timeout=15000)
    page.evaluate(
        """() => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          setActiveGameView('command');
        }"""
    )
    try:
        page.locator("#eventRevealModal").wait_for(state="visible", timeout=1500)
        page.evaluate("closeEventReveal()")
    except Exception:
        pass
    return page


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-support-card-play",
        {
            "support_name": "印度奧援",
            "faction_id": "tibet_dehradun",
            "base": "德拉敦",
            "orgs": {"德里": 1},
            "enemy_hand_names": ["爆料黑幕"],
            "distraction_supply": 2,
            "mission_name": "全國人大召開",
        },
    )
    if not setup.get("success"):
        raise RuntimeError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    initial = setup["state"]
    record(
        "fixture_uses_real_india_tier_three_gate",
        setup.get("support_tier") == 3,
        {"tier": setup.get("support_tier"), "organizations": initial["players"][0].get("orgs")},
    )
    record(
        "fixture_starts_with_two_distractions_and_use_ability_mission",
        initial.get("static_purchase_supply", {}).get("分神") == 2
        and initial.get("current_event", {}).get("trigger", {}).get("type") == "use_faction_ability",
        {
            "supply": initial.get("static_purchase_supply", {}).get("分神"),
            "event": initial.get("current_event"),
        },
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        player_page = connect_page(context, setup["game_id"], setup["player_id"], console_errors)
        red_page = connect_page(context, setup["game_id"], setup["red_player_id"], console_errors)

        action_button = player_page.locator(
            "button.hand-card-action-btn[data-card-name='印度奧援'][data-card-mode='action']"
        ).first
        action_button.wait_for(state="visible", timeout=10000)
        action_button.click()

        red_page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'cancel_other_player_action'",
            timeout=15000,
        )
        reaction_state = red_page.evaluate("window.lastGameState")
        record(
            "formal_ui_prompts_red_player_to_cancel_india_support",
            reaction_state.get("pending_choice", {}).get("player_id") == setup["red_player_id"]
            and reaction_state.get("pending_choice", {}).get("played_card_name") == "印度奧援",
            reaction_state.get("pending_choice"),
        )
        overlay_display = red_page.locator("#peerActionNotice").evaluate("element => getComputedStyle(element).display")
        record(
            "reaction_choice_is_not_blocked_by_peer_action_notice",
            overlay_display == "none",
            {"peer_action_notice_display": overlay_display},
        )
        decline = red_page.get_by_role("button", name="不取消", exact=True)
        decline.wait_for(state="visible", timeout=10000)
        decline.click()

        player_page.wait_for_function(
            """([playerId, redId]) => {
              const state = window.lastGameState;
              const actor = state?.players?.find(player => player.id === playerId);
              const red = state?.players?.find(player => player.id === redId);
              return !state?.pending_choice
                && actor?.resources?.money === 2
                && red?.discard_pile?.filter(name => name === '分神').length === 2
                && state?.static_purchase_supply?.['分神'] === 0
                && state?.current_event?.progress?.succeeded === true;
            }""",
            arg=[setup["player_id"], setup["red_player_id"]],
            timeout=15000,
        )
        state = player_page.evaluate("window.lastGameState")
        red_view_state = red_page.evaluate("window.lastGameState")
        actor = next(player for player in state["players"] if player["id"] == setup["player_id"])
        red = next(player for player in state["players"] if player["id"] == setup["red_player_id"])
        red_self_view = next(player for player in red_view_state["players"] if player["id"] == setup["red_player_id"])
        logs = state.get("action_log", [])
        event_progress = state.get("current_event", {}).get("progress", {})

        record(
            "declined_reaction_resolves_india_support_once",
            state.get("pending_choice") is None
            and actor.get("discard_pile", []).count("印度奧援") == 1
            and "爆料黑幕" in red_self_view.get("hand", []),
            {"actor_discard": actor.get("discard_pile"), "red_hand": red_self_view.get("hand")},
        )
        record(
            "india_research_room_grants_two_money_after_reaction",
            actor.get("resources", {}).get("money") == 2
            and sum("triggered 印度研究分析室" in entry for entry in logs) == 1,
            {"resources": actor.get("resources"), "logs": logs[-12:]},
        )
        record(
            "india_research_room_counts_for_use_faction_ability_event",
            event_progress.get("count") == 1 and event_progress.get("succeeded") is True,
            event_progress,
        )
        record(
            "india_support_consumes_only_available_distraction_supply",
            state.get("static_purchase_supply", {}).get("分神") == 0
            and red.get("discard_pile", []).count("分神") == 2
            and any("分神供應" in entry for entry in logs),
            {
                "supply": state.get("static_purchase_supply", {}).get("分神"),
                "red_discard": red.get("discard_pile"),
                "logs": logs[-12:],
            },
        )

        player_page.evaluate("setActiveGameView('log')")
        player_page.locator("#logView").wait_for(state="visible", timeout=5000)
        player_page.screenshot(path=str(SCREENSHOT))

        context.close()
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    passed = sum(1 for check in checks if check["ok"])
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
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "checks_passed": passed, "checks_total": len(checks)}, ensure_ascii=False))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
