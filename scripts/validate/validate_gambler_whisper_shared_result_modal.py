#!/usr/bin/env python3
"""Browser proof：賭徒耳語結果以相同提示視窗公開給發動者與其他玩家。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/faction-ui/gambler-whisper-shared-result-modal"
JSON_PATH = OUT / "GAMBLER_WHISPER_SHARED_RESULT_MODAL_VALIDATION.json"
RED_BASELINE_JSON_PATH = OUT / "GAMBLER_WHISPER_SHARED_RESULT_MODAL_RED_BASELINE.json"
MD_PATH = OUT / "GAMBLER_WHISPER_SHARED_RESULT_MODAL_VALIDATION.md"
ACTOR_SHOT = OUT / "gambler_whisper_actor_result_modal_1280x720.png"
OBSERVER_SHOT = OUT / "gambler_whisper_observer_result_modal_1280x720.png"
EXPECTED_CARD = "宣傳家"
EXPECTED_MESSAGE_PARTS = (
    "賭徒耳語結果",
    "猜奇數",
    f"翻到 {EXPECTED_CARD}（費用 3）",
    "是奇數",
    "猜中",
    "資金 +3",
    "宣傳 +3",
)


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
    setup = post_json(
        "/test/setup-faction-action-used-proof",
        {
            "faction_id": "aomen",
            "faction_action_used": False,
            "resource_card_name": "追隨者",
            "draw_pile": ["乘勝追擊", EXPECTED_CARD],
        },
    )
    if not setup.get("success"):
        raise AssertionError(setup)
    actor_id = setup["player_id"]
    observer_id = next(player["id"] for player in setup["state"]["players"] if player["id"] != actor_id)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    def open_view(browser, player_id: str):
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={player_id}&v=gambler-whisper-shared-result-modal",
            wait_until="domcontentloaded",
        )
        page.wait_for_function("window.lastGameState && window.lastGameState.game_phase === 'main'", timeout=15000)
        page.evaluate("closeEventReveal?.()")
        return page

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        actor = open_view(browser, actor_id)
        observer = open_view(browser, observer_id)
        for page in (actor, observer):
            page.wait_for_timeout(250)
            page.evaluate("closeEventReveal?.()")
            page.locator("#eventRevealModal").wait_for(state="hidden", timeout=5000)

        actor.locator("#factionActionButtons button", has_text="發動 賭徒耳語").click()
        actor.locator("#factionActionModalChoices button", has_text="猜奇數").click()
        for page in (actor, observer):
            page.wait_for_function("window.lastGameState?.last_action_result?.name === '賭徒耳語'", timeout=10000)
            page.wait_for_timeout(150)

        def view_state(page):
            return page.evaluate(
                """() => ({
                  result: window.lastGameState?.last_action_result || null,
                  modalDisplay: getComputedStyle(document.getElementById('unavailableActionModal')).display,
                  modalTitle: document.getElementById('unavailableActionTitle').textContent,
                  modalMessage: document.getElementById('unavailableActionMessage').textContent,
                  phaseNoticeDisplay: getComputedStyle(document.getElementById('phaseActionNotice')).display,
                  phaseNoticeText: document.getElementById('phaseActionNotice').textContent,
                  peerNoticeDisplay: getComputedStyle(document.getElementById('peerActionNotice')).display,
                  me: window.lastGameState.players.find(player => player.id === playerId),
                })"""
            )

        actor_state = view_state(actor)
        observer_state = view_state(observer)

        def prompt_details(state):
            return {
                "modalDisplay": state["modalDisplay"],
                "modalTitle": state["modalTitle"],
                "modalMessage": state["modalMessage"],
                "phaseNoticeDisplay": state["phaseNoticeDisplay"],
                "phaseNoticeText": state["phaseNoticeText"],
                "peerNoticeDisplay": state["peerNoticeDisplay"],
            }

        record(
            "same_result_reaches_actor_and_observer",
            actor_state["result"] == observer_state["result"]
            and actor_state["result"].get("revealed_card") == EXPECTED_CARD,
            {"actor": actor_state["result"], "observer": observer_state["result"]},
        )
        record(
            "private_bottom_card_is_not_in_public_result",
            "bottom_card" not in actor_state["result"]
            and "bottom_card" not in observer_state["result"],
            {"actor": actor_state["result"], "observer": observer_state["result"]},
        )
        for role, state in (("actor", actor_state), ("observer", observer_state)):
            record(
                f"{role}_sees_result_prompt_modal",
                state["modalDisplay"] == "flex"
                and state["modalTitle"] == "賭徒耳語結果"
                and all(part in state["modalMessage"] for part in EXPECTED_MESSAGE_PARTS),
                prompt_details(state),
            )
        record(
            "actor_and_observer_messages_are_identical",
            bool(actor_state["modalMessage"])
            and actor_state["modalTitle"] == observer_state["modalTitle"]
            and actor_state["modalMessage"] == observer_state["modalMessage"],
            {"actor": actor_state["modalMessage"], "observer": observer_state["modalMessage"]},
        )
        record(
            "result_does_not_use_hud_notice",
            actor_state["phaseNoticeDisplay"] == observer_state["phaseNoticeDisplay"] == "none"
            and not actor_state["phaseNoticeText"]
            and not observer_state["phaseNoticeText"],
            {
                "actor": prompt_details(actor_state),
                "observer": prompt_details(observer_state),
            },
        )
        record(
            "observer_does_not_get_duplicate_peer_action_overlay",
            observer_state["peerNoticeDisplay"] == "none",
            observer_state["peerNoticeDisplay"],
        )
        record(
            "gambler_reward_and_hand_state_are_resolved",
            actor_state["me"]["resources"] == {"money": 3, "propaganda": 3}
            and actor_state["me"]["hand"] == [],
            {
                "resources": actor_state["me"]["resources"],
                "hand": actor_state["me"]["hand"],
            },
        )

        actor.screenshot(path=str(ACTOR_SHOT), full_page=True)
        observer.screenshot(path=str(OBSERVER_SHOT), full_page=True)

        for role, page, selector in (
            ("actor", actor, "#closeUnavailableActionModalIcon"),
            ("observer", observer, "#closeUnavailableActionModalBtn"),
        ):
            close_button = page.locator(selector)
            if close_button.is_visible():
                close_button.click()
            else:
                page.evaluate("closeUnavailableActionModal()")
            page.evaluate("render(window.lastGameState)")
            page.wait_for_timeout(120)
            display = page.locator("#unavailableActionModal").evaluate("element => getComputedStyle(element).display")
            record(f"{role}_dismissal_stays_closed_for_same_result", display == "none", display)

        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {
        "total": len(checks),
        "passed": sum(check["passed"] for check in checks),
        "failed": sum(not check["passed"] for check in checks),
    }
    red_baseline = None
    if RED_BASELINE_JSON_PATH.exists():
        baseline_report = json.loads(RED_BASELINE_JSON_PATH.read_text(encoding="utf-8"))
        red_baseline = {
            "summary": baseline_report.get("summary", {}),
            "failed_checks": [
                check.get("name")
                for check in baseline_report.get("checks", [])
                if not check.get("passed")
            ],
            "record": str(RED_BASELINE_JSON_PATH.relative_to(ROOT)),
        }
    report = {
        "summary": summary,
        "red_baseline": red_baseline,
        "service": BASE_URL,
        "scenario": "澳門發動賭徒耳語；猜奇數；公開翻到宣傳家；識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [str(ACTOR_SHOT.relative_to(ROOT)), str(OBSERVER_SHOT.relative_to(ROOT))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    red_lines = []
    if red_baseline:
        red_summary = red_baseline["summary"]
        red_lines = [
            f"RED baseline: **{red_summary.get('passed', 0)}/{red_summary.get('total', 0)} passed**",
            "",
        ]
    MD_PATH.write_text(
        "\n".join(
            [
                "# 賭徒耳語共享結果提示視窗 Browser 驗證",
                "",
                f"Summary: **{summary['passed']}/{summary['total']} passed**",
                "",
                *red_lines,
                *[f"- {'PASS' if check['passed'] else 'FAIL'} `{check['name']}`" for check in checks],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
