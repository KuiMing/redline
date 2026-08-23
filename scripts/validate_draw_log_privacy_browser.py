#!/usr/bin/env python3
"""正式雙觀看者 Browser proof：抽牌牌名只對抽牌玩家可見。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/playtest-flow/draw-log-privacy"
JSON_PATH = OUT / "DRAW_LOG_PRIVACY_BROWSER_VALIDATION.json"
MD_PATH = OUT / "DRAW_LOG_PRIVACY_BROWSER_VALIDATION.md"
RED_SCREENSHOT = OUT / "red_view_draw_count_without_card_names_20260823.png"
OWNER_SCREENSHOT = OUT / "kazakh_view_own_draw_card_names_20260823.png"
OBSERVER_SCREENSHOT = OUT / "observer_view_draw_count_without_card_names_20260823.png"
PRIVATE_NAMES = ("樂捐者", "追隨者")
PUBLIC_TEXT = "哈薩克 因時代關卡效果抽了 2 張牌"


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def projected_player(state: dict, player_name: str) -> dict:
    return next(player for player in state.get("players", []) if player.get("name") == player_name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-draw-privacy-proof")
    if not setup.get("success"):
        raise AssertionError(setup)

    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    def open_view(browser, player_id: str):
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={player_id}&v=draw-log-privacy-20260823",
            wait_until="domcontentloaded",
        )
        page.wait_for_function("window.lastGameState && Array.isArray(window.lastGameState.action_log)", timeout=15000)
        page.evaluate("closeEventReveal?.()")
        return page

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        red_page = open_view(browser, setup["red_player_id"])
        owner_page = open_view(browser, setup["kazakh_player_id"])
        observer_page = open_view(browser, setup["observer_player_id"])

        triggered = post_json("/test/trigger-draw-privacy-proof", {"game_id": setup["game_id"]})
        if not triggered.get("success"):
            raise AssertionError(triggered)
        for page in (red_page, owner_page, observer_page):
            page.wait_for_function("window.lastGameState?.action_log?.length === 1", timeout=15000)
        red_page.wait_for_function("getComputedStyle(document.getElementById('peerActionNotice')).display === 'flex'", timeout=10000)
        observer_page.wait_for_function("getComputedStyle(document.getElementById('peerActionNotice')).display === 'flex'", timeout=10000)
        red_page.wait_for_timeout(400)
        observer_page.wait_for_timeout(400)

        red_state = red_page.evaluate("window.lastGameState")
        owner_state = owner_page.evaluate("window.lastGameState")
        observer_state = observer_page.evaluate("window.lastGameState")
        red_log = red_state["action_log"][-1]
        owner_log = owner_state["action_log"][-1]
        observer_log = observer_state["action_log"][-1]

        record(
            "drawing_player_sees_exact_card_names",
            all(name in owner_log for name in PRIVATE_NAMES),
            {"owner_log": owner_log},
        )
        record(
            "red_army_log_sees_count_without_card_names",
            PUBLIC_TEXT in red_log and all(name not in red_log for name in PRIVATE_NAMES),
            {"red_log": red_log},
        )
        record(
            "third_player_log_sees_count_without_card_names",
            PUBLIC_TEXT in observer_log and all(name not in observer_log for name in PRIVATE_NAMES),
            {"observer_log": observer_log},
        )

        red_notice = red_page.locator("#peerActionNoticeText").inner_text()
        observer_notice = observer_page.locator("#peerActionNoticeText").inner_text()
        owner_notice_display = owner_page.locator("#peerActionNotice").evaluate("element => getComputedStyle(element).display")
        record(
            "red_army_peer_notice_does_not_leak_card_names",
            PUBLIC_TEXT in red_notice and all(name not in red_notice for name in PRIVATE_NAMES),
            {"notice": red_notice},
        )
        record(
            "third_player_peer_notice_does_not_leak_card_names",
            PUBLIC_TEXT in observer_notice and all(name not in observer_notice for name in PRIVATE_NAMES),
            {"notice": observer_notice},
        )
        record(
            "drawing_players_own_turn_has_no_peer_overlay",
            owner_notice_display == "none",
            {"display": owner_notice_display},
        )

        red_kazakh_hand = projected_player(red_state, "哈薩克").get("hand", [])
        owner_hand = projected_player(owner_state, "哈薩克").get("hand", [])
        observer_kazakh_hand = projected_player(observer_state, "哈薩克").get("hand", [])
        record(
            "private_hand_projection_matches_log_privacy",
            red_kazakh_hand == ["未知手牌", "未知手牌"]
            and observer_kazakh_hand == ["未知手牌", "未知手牌"]
            and set(owner_hand) == set(PRIVATE_NAMES),
            {
                "red_view": red_kazakh_hand,
                "owner_view": owner_hand,
                "observer_view": observer_kazakh_hand,
            },
        )

        red_page.screenshot(path=str(RED_SCREENSHOT), full_page=True)
        observer_page.screenshot(path=str(OBSERVER_SCREENSHOT), full_page=True)
        owner_page.evaluate("setActiveGameView('log')")
        owner_page.wait_for_function("document.getElementById('logView')?.classList.contains('active')")
        owner_page.screenshot(path=str(OWNER_SCREENSHOT), full_page=True)
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
        "scenario": "三位玩家；哈薩克因時代關卡抽 2 張；憑證與識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [
            str(RED_SCREENSHOT.relative_to(ROOT)),
            str(OWNER_SCREENSHOT.relative_to(ROOT)),
            str(OBSERVER_SCREENSHOT.relative_to(ROOT)),
        ],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 抽牌紀錄觀看者隱私 Browser 驗證",
        "",
        f"Summary: **{summary['passed']}/{summary['total']} passed**",
        "",
        "- 哈薩克本人可看見自己抽到的牌名。",
        "- 紅軍與第三位玩家只看見抽牌張數。",
        "- Proof 中的憑證與識別碼均為 `[REDACTED]`。",
        "",
    ]
    for check in checks:
        lines.extend([
            f"## {'PASS' if check['passed'] else 'FAIL'} — {check['name']}",
            "",
            "```json",
            json.dumps(check["details"], ensure_ascii=False, indent=2),
            "```",
            "",
        ])
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
