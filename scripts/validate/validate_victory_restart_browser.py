#!/usr/bin/env python3
"""Browser proof for the victory-screen restart action."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/victory-restart"
REPORT = OUT / "VICTORY_RESTART_BROWSER_VALIDATION.json"
SCREENSHOT = OUT / "victory_restart.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-victory-proof", {"winner": "red_army"})
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail: dict) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=victory-restart-proof",
            wait_until="networkidle",
        )
        page.wait_for_function("document.getElementById('victoryModal')?.style.display === 'flex'")
        page.wait_for_timeout(200)

        layout = page.evaluate(
            """() => {
              const rect = id => {
                const r = document.getElementById(id).getBoundingClientRect();
                return {left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:r.width, height:r.height};
              };
              const restart = document.getElementById('victoryRestartBtn');
              return {
                finalBoard: rect('victoryMinimizeBtn'),
                restart: rect('victoryRestartBtn'),
                restartText: restart.textContent.trim(),
                restartHref: restart.getAttribute('href'),
                restartDisplay: getComputedStyle(restart).display,
                restartDecoration: getComputedStyle(restart).textDecorationLine,
              };
            }"""
        )
        same_row = abs(layout["finalBoard"]["top"] - layout["restart"]["top"]) <= 1
        ordered = layout["restart"]["left"] >= layout["finalBoard"]["right"]
        record(
            "restart_button_is_visible_next_to_final_board_button",
            same_row and ordered and layout["restart"]["width"] > 0 and layout["restart"]["height"] > 0,
            layout,
        )
        record(
            "restart_button_has_expected_label_target_and_button_style",
            layout["restartText"] == "重新開始"
            and layout["restartHref"] == "/new-game"
            and layout["restartDisplay"] == "flex"
            and layout["restartDecoration"] == "none",
            {
                "text": layout["restartText"],
                "href": layout["restartHref"],
                "display": layout["restartDisplay"],
                "text_decoration": layout["restartDecoration"],
            },
        )
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        page.click("#victoryRestartBtn")
        page.wait_for_url(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        destination = {
            "path": page.evaluate("location.pathname"),
            "search": page.evaluate("location.search"),
            "lobby_visible": page.locator("#lobby").is_visible(),
        }
        record(
            "restart_button_opens_a_clean_new_game_lobby",
            destination == {"path": "/", "search": "", "lobby_visible": True},
            destination,
        )
        record("browser_console_has_no_errors", not console_errors, {"errors": console_errors})
        browser.close()

    payload = {
        "status": "passed" if all(item["ok"] for item in checks) else "failed",
        "checks_passed": sum(1 for item in checks if item["ok"]),
        "checks_total": len(checks),
        "checks": checks,
        "console_errors": console_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
        "identifiers": "[REDACTED]",
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("status", "checks_passed", "checks_total")}, ensure_ascii=False))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
