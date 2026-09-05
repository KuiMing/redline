#!/usr/bin/env python3
"""Browser proof: 紅軍四種公開結果只使用中央提示，不疊加其他玩家動態。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs" / "records" / "faction-ui" / "red-army-single-result-prompt"
REPORT = OUT / "RED_ARMY_SINGLE_RESULT_PROMPT_VALIDATION.json"
SCREENSHOT = OUT / "red_army_united_front_single_prompt_1280x720.png"
RED_ARMY_ACTIONS = ("統戰部", "政工部", "國安部", "中紀委")


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details=None) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    def prompt_state(page) -> dict:
        return page.evaluate(
            """() => ({
              result: window.lastGameState?.last_action_result || null,
              currentPlayer: window.lastGameState?.current_player || '',
              modalDisplay: getComputedStyle(document.getElementById('unavailableActionModal')).display,
              modalTitle: document.getElementById('unavailableActionTitle').textContent,
              modalMessage: document.getElementById('unavailableActionMessage').textContent,
              peerDisplay: getComputedStyle(document.getElementById('peerActionNotice')).display,
              peerMinimized: document.getElementById('peerActionNotice').classList.contains('peer-action-notice-minimized'),
            })"""
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        def open_view(setup: dict, pid: str):
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            page.goto(
                f"{BASE_URL}/?game_id={setup['game_id']}&player_id={pid}&v=red-army-single-result-prompt",
                wait_until="domcontentloaded",
            )
            page.wait_for_function("window.lastGameState?.game_phase === 'main'", timeout=15000)
            page.evaluate("closeEventReveal?.()")
            return page

        for action_name in RED_ARMY_ACTIONS:
            setup = post_json("/test/setup-red-army-abilities-proof")
            actor_id = setup["player_id"]
            observer_id = setup["target_player_id"]
            actor = open_view(setup, actor_id)
            observer = open_view(setup, observer_id)

            actor.locator("#redArmyAbilityBtn").click()
            actor.locator("#factionActionModalChoices button", has_text=f"發動 {action_name}").click()
            actor.wait_for_function(
                "name => window.lastGameState?.last_action_result?.name === name || Boolean(window.lastGameState?.pending_choice)",
                arg=action_name,
                timeout=10000,
            )
            pending = actor.evaluate("window.lastGameState?.pending_choice || null")
            if pending:
                resolution = [0] if action_name == "中紀委" else 0
                actor.evaluate("index => sendAction('resolve_choice', {index})", resolution)

            for page in (actor, observer):
                page.wait_for_function(
                    "name => window.lastGameState?.last_action_result?.name === name",
                    arg=action_name,
                    timeout=10000,
                )
                page.wait_for_timeout(400)

            actor_state = prompt_state(actor)
            observer_state = prompt_state(observer)
            record(
                f"{action_name}_observer_sees_centered_result",
                observer_state["modalDisplay"] == "flex"
                and observer_state["modalTitle"] == f"{action_name}結果"
                and observer_state["result"].get("name") == action_name,
                observer_state,
            )
            record(
                f"{action_name}_observer_has_exactly_one_result_surface",
                observer_state["modalDisplay"] == "flex" and observer_state["peerDisplay"] == "none",
                observer_state,
            )
            record(
                f"{action_name}_actor_has_no_redundant_result_surface",
                actor_state["modalDisplay"] == "none" and actor_state["peerDisplay"] == "none",
                actor_state,
            )

            if action_name == "統戰部":
                observer.screenshot(path=str(SCREENSHOT), full_page=True)

            original_actor = actor_state["currentPlayer"]
            actor.evaluate("sendAction('advance')")
            observer.wait_for_function(
                "name => window.lastGameState?.current_player !== name",
                arg=original_actor,
                timeout=10000,
            )
            observer.wait_for_timeout(150)
            observer_handoff = prompt_state(observer)
            record(
                f"{action_name}_result_modal_closes_on_turn_handoff",
                observer_handoff["modalDisplay"] == "none",
                observer_handoff,
            )
            observer.evaluate("sendAction('advance')")
            observer.wait_for_function(
                "name => window.lastGameState?.current_player !== name",
                arg=observer_handoff["currentPlayer"],
                timeout=10000,
            )
            observer.wait_for_timeout(400)
            no_replay = prompt_state(observer)
            record(
                f"{action_name}_suppressed_log_does_not_replay_after_next_handoff",
                no_replay["peerDisplay"] == "none",
                no_replay,
            )

            actor.close()
            observer.close()

        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {
        "total": len(checks),
        "passed": sum(check["passed"] for check in checks),
        "failed": sum(not check["passed"] for check in checks),
    }
    report = {
        "summary": summary,
        "service": BASE_URL,
        "scenario": "紅軍依序發動四種能力；發動者與其他玩家只保留必要提示；識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [str(SCREENSHOT.relative_to(ROOT))],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
