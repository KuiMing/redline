#!/usr/bin/env python3
"""Formal Browser proof: 組織經驗乙 triggers 哈薩克「民族調和」 exactly once."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8767").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "faction-ui" / "trigger-audit"
JSON_PATH = RECORD_DIR / "KAZAKH_ORG_EXPERIENCE_B_TRIGGER_VALIDATION.json"
MD_PATH = RECORD_DIR / "KAZAKH_ORG_EXPERIENCE_B_TRIGGER_VALIDATION.md"
SCREENSHOT = RECORD_DIR / "kazakh_org_experience_b_triggers_national_harmony_20260822.png"


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def make_formal_game() -> tuple[str, str, str]:
    create = post_json("/create")
    join = post_json("/join", {"game_id": create["game_id"], "name": "哈薩克"})
    for player_id, faction_id, base_name in [
        (create["host_id"], "red_army", "北京"),
        (join["player_id"], "kazakh", "阿拉木圖"),
    ]:
        chosen = post_json(
            "/choose-faction",
            {"game_id": create["game_id"], "player_id": player_id, "faction_id": faction_id, "base_name": base_name},
        )
        if chosen.get("error"):
            raise AssertionError(chosen)
        ready = post_json("/ready", {"game_id": create["game_id"], "player_id": player_id, "ready": True})
        if ready.get("error"):
            raise AssertionError(ready)
    started = post_json(
        "/start",
        {"game_id": create["game_id"], "player_id": create["host_id"], "market_mode": "sample_53"},
    )
    if started.get("error"):
        raise AssertionError(started)
    setup = post_json(
        "/test/setup-card-scenario",
        {"game_id": create["game_id"], "player_id": join["player_id"], "card_name": "組織經驗乙"},
    )
    if not setup.get("success"):
        raise AssertionError(setup)
    return create["game_id"], join["player_id"], join["resume_token"]


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    game_id, player_id, resume_token = make_formal_game()
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details=None) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(BASE_URL + "/", wait_until="domcontentloaded")
        page.evaluate(
            """session => localStorage.setItem('redline.sessions.v1', JSON.stringify({
              [session.game_id]: {
                game_id: session.game_id,
                player_id: session.player_id,
                resume_token: session.resume_token,
                name: '哈薩克',
                saved_at: Date.now(),
              },
            }))""",
            {"game_id": game_id, "player_id": player_id, "resume_token": resume_token},
        )
        page.goto(BASE_URL + "/?v=kazakh-org-experience-b-trigger", wait_until="domcontentloaded")
        page.wait_for_function(
            "(id) => window.lastGameState?.players?.find(p => p.id === id)?.hand?.includes('組織經驗乙')",
            arg=player_id,
            timeout=15000,
        )
        page.evaluate(
            """() => {
              closeEventReveal?.();
              minimizeEraAchievement?.();
              document.getElementById('closeFactionActionModal')?.click();
              setActiveGameView('command');
            }"""
        )
        page.locator("button.hand-card-action-btn[data-card-name='組織經驗乙'][data-card-mode='action']").click()
        page.wait_for_function(
            "window.lastGameState?.pending_choice?.choice_key === 'card_build_organization'",
            timeout=10000,
        )
        page.wait_for_function(
            "window.lastGameState?.action_log?.some(entry => entry.includes('triggered 民族調和 and drew 1 card'))",
            timeout=10000,
        )
        after_play = page.evaluate("window.lastGameState")
        actor = next(player for player in after_play["players"] if player["id"] == player_id)
        trigger_logs = [entry for entry in after_play.get("action_log", []) if "triggered 民族調和" in entry]
        record("organization_experience_b_opens_first_build_choice", after_play.get("pending_choice", {}).get("choice_key") == "card_build_organization")
        record("national_harmony_draws_immediately_after_committed_play", "抽牌D" in actor.get("hand", []), actor.get("hand", []))
        record("national_harmony_triggers_once_on_card_play", len(trigger_logs) == 1, trigger_logs)

        for _ in range(2):
            page.evaluate("sendAction('resolve_choice', {index: 0})")
            page.wait_for_timeout(350)
        page.wait_for_function("!window.lastGameState?.pending_choice", timeout=10000)
        final_state = page.evaluate("window.lastGameState")
        final_actor = next(player for player in final_state["players"] if player["id"] == player_id)
        final_trigger_logs = [entry for entry in final_state.get("action_log", []) if "triggered 民族調和" in entry]
        record(
            "two_build_resolutions_do_not_duplicate_trigger",
            len(final_trigger_logs) == 1 and final_actor.get("organization_counts", {}).get("total") == 3,
            {"trigger_logs": final_trigger_logs, "organization_counts": final_actor.get("organization_counts")},
        )
        page.get_by_role("button", name="戰況紀錄", exact=True).click()
        page.wait_for_timeout(300)
        record("battle_log_ui_shows_national_harmony_trigger", "triggered 民族調和 and drew 1 card" in page.locator("body").inner_text())
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
    }
    report = {
        "summary": summary,
        "service": BASE_URL,
        "session": "formal create/join/start/restore; credentials [REDACTED]",
        "checks": checks,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Kazakh Organization Experience B Faction Trigger Validation",
        "",
        f"- Summary: {summary['passed']}/{summary['total']} passed",
        "- Session: formal create/join/start/restore; credentials `[REDACTED]`",
        "",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in checks)
    lines.extend(["", f"- Screenshot: `{SCREENSHOT.relative_to(ROOT)}`"])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
