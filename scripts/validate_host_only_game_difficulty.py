#!/usr/bin/env python3
"""Browser proof：遊戲難易度文案、卡牌數量 tooltip 與房主專屬切換。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/host-only-game-difficulty"
REPORT_JSON = OUT / "HOST_ONLY_GAME_DIFFICULTY_VALIDATION.json"
REPORT_MD = OUT / "HOST_ONLY_GAME_DIFFICULTY_VALIDATION.md"
HOST_SHOT = OUT / "host_game_difficulty_1280x720_20260823.png"
GUEST_SHOT = OUT / "guest_game_difficulty_disabled_1280x720_20260823.png"


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE_URL + path, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        host_context = browser.new_context(viewport={"width": 1280, "height": 720})
        guest_context = browser.new_context(viewport={"width": 1280, "height": 720})
        host = host_context.new_page()
        guest = guest_context.new_page()
        for page in (host, guest):
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))

        host.goto(BASE_URL + "/new-game", wait_until="networkidle")
        initial = host.evaluate(
            """() => ({
              subtitle: document.querySelector('.lobby-subtitle')?.textContent.trim(),
              label: document.querySelector('#difficultyField > span')?.textContent.trim(),
              aria: document.querySelector('.lobby-market-toggle')?.getAttribute('aria-label'),
              labels: [...document.querySelectorAll('.lobby-market-option')].map(button => button.textContent.trim()),
              disabled: [...document.querySelectorAll('.lobby-market-option')].map(button => button.disabled),
            })"""
        )
        record(
            "difficulty_copy_replaces_card_mode_copy",
            initial["label"] == "遊戲難易度"
            and initial["aria"] == "遊戲難易度"
            and initial["labels"] == ["簡單模式", "一般模式"]
            and "選擇遊戲難易度" in (initial["subtitle"] or ""),
            initial,
        )
        record("difficulty_is_locked_before_room_creation", all(initial["disabled"]), initial["disabled"])

        host.locator("#playerName").fill("房主")
        host.locator("#createRoomBtn").click()
        host.wait_for_function("document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'", timeout=10000)
        host.locator("#closeFactionPickerBtn").click()
        room_id = host.locator("#roomId").input_value()
        host.wait_for_function("typeof latestLobbyState !== 'undefined' && latestLobbyState?.host_id && document.querySelectorAll('.lobby-market-option:not(:disabled)').length === 2", timeout=10000)
        host_state = host.evaluate(
            """() => ({
              disabled: [...document.querySelectorAll('.lobby-market-option')].map(button => button.disabled),
              active: document.querySelector('.lobby-market-option.active')?.dataset.marketMode,
            })"""
        )
        record("host_can_change_difficulty_after_creating_room", not any(host_state["disabled"]) and host_state["active"] == "sample_53", host_state)

        tooltip_results = []
        for selector, expected_parts in [
            ('[data-market-mode="sample_53"]', ["共53張", "奧援卡18張", "一般卡35張"]),
            ('[data-market-mode="all_cards"]', ["共245張", "奧援64張", "指揮68張", "組織11張"]),
        ]:
            button = host.locator(selector)
            button.hover()
            host.wait_for_timeout(120)
            tooltip_results.append(button.evaluate(
                """button => ({
                  text: button.dataset.tooltip || '',
                  pseudoContent: getComputedStyle(button, '::after').content,
                  pseudoOpacity: getComputedStyle(button, '::after').opacity,
                })"""
            ))
            tooltip_results[-1]["expected"] = expected_parts
        record(
            "hover_tooltips_explain_card_type_counts",
            all(all(part in result["text"] for part in result["expected"]) and float(result["pseudoOpacity"]) >= 0.95 for result in tooltip_results),
            tooltip_results,
        )

        guest.goto(BASE_URL + "/new-game", wait_until="networkidle")
        guest.locator("#playerName").fill("訪客")
        guest.locator("#roomId").fill(room_id)
        guest.locator("#joinRoomBtn").click()
        guest.wait_for_function("typeof latestLobbyState !== 'undefined' && latestLobbyState?.host_id && latestLobbyState?.players?.length === 2", timeout=10000)
        guest.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'", timeout=10000)
        guest.locator("#closeFactionPickerBtn").click()
        guest_state = guest.evaluate(
            """() => ({
              disabled: [...document.querySelectorAll('.lobby-market-option')].map(button => button.disabled),
              active: document.querySelector('.lobby-market-option.active')?.dataset.marketMode,
              tooltip: document.querySelector('[data-market-mode="all_cards"]')?.dataset.tooltip || '',
            })"""
        )
        record(
            "non_host_difficulty_buttons_are_disabled",
            all(guest_state["disabled"]) and "只有房主可以切換" in guest_state["tooltip"],
            guest_state,
        )

        rejected = guest.evaluate(
            """async () => {
              const response = await fetch('/market-mode', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({game_id: gameId, player_id: playerId, market_mode: 'all_cards'}),
              });
              let body = {};
              try { body = await response.json(); } catch (_) {}
              return {status: response.status, body};
            }"""
        )
        record(
            "server_rejects_non_host_difficulty_change",
            rejected["body"].get("error") == "Only host can change game difficulty",
            rejected,
        )

        host.locator('[data-market-mode="all_cards"]').click()
        try:
            host.wait_for_function("typeof latestLobbyState !== 'undefined' && latestLobbyState?.market_mode === 'all_cards'", timeout=3000)
            guest.wait_for_function("typeof latestLobbyState !== 'undefined' && latestLobbyState?.market_mode === 'all_cards' && document.querySelector('.lobby-market-option.active')?.dataset.marketMode === 'all_cards'", timeout=3000)
        except PlaywrightTimeoutError:
            pass
        server_state = get_json(f"/lobby/{room_id}")
        record(
            "host_choice_syncs_to_server_and_guest",
            server_state.get("market_mode") == "all_cards"
            and guest.locator('.lobby-market-option.active').get_attribute("data-market-mode") == "all_cards",
            {"serverMode": server_state.get("market_mode"), "guestMode": guest.locator('.lobby-market-option.active').get_attribute("data-market-mode")},
        )

        host.screenshot(path=str(HOST_SHOT), full_page=True)
        guest.screenshot(path=str(GUEST_SHOT), full_page=True)
        browser.close()

    record("browser_console_has_no_errors", not errors, errors)
    summary = {"total": len(checks), "passed": sum(1 for check in checks if check["passed"]), "failed": sum(1 for check in checks if not check["passed"])}
    report = {
        "summary": summary,
        "service": BASE_URL,
        "scenario": "房主與訪客 lobby；識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [str(HOST_SHOT.relative_to(ROOT)), str(GUEST_SHOT.relative_to(ROOT))],
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 房主專屬遊戲難易度 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
