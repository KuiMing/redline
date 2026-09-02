#!/usr/bin/env python3
"""Browser proof：展現實力由能力擁有者選擇 3 宣傳或 3 資金。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/faction-ui/show-strength-choice"
REPORT = OUT / "SHOW_STRENGTH_CHOICE_VALIDATION.json"
SCREENSHOT = OUT / "show_strength_reward_choice_1280x720_20260824.png"


def setup_case() -> dict:
    request = urllib.request.Request(
        f"{BASE_URL}/test/setup-show-strength-choice-proof",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for choice_label, resource_key in [("獲得 3 點宣傳", "propaganda"), ("獲得 3 點資金", "money")]:
            setup = setup_case()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            console_errors = []
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            page.goto(
                f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
                wait_until="networkidle",
            )
            page.wait_for_function("document.querySelectorAll('#choiceModal .modal-choice-btn').length === 2")
            labels = page.locator("#choiceModal .modal-choice-btn").all_text_contents()
            prompt = page.locator("#choiceModal").inner_text()
            if resource_key == "propaganda":
                page.screenshot(path=str(SCREENSHOT), full_page=True)
            page.locator("#choiceModal .modal-choice-btn", has_text=choice_label).click()
            page.wait_for_function(
                """([playerId, resourceKey]) => {
                  const player = window.lastGameState?.players?.find(item => item.id === playerId);
                  return player?.resources?.[resourceKey] === 3 && !window.lastGameState?.pending_choice;
                }""",
                arg=[setup["player_id"], resource_key],
            )
            resources = page.evaluate(
                """playerId => window.lastGameState.players.find(item => item.id === playerId).resources""",
                setup["player_id"],
            )
            passed = (
                labels == ["獲得 3 點宣傳", "獲得 3 點資金"]
                and "展現實力" in prompt
                and resources[resource_key] == 3
                and resources["money" if resource_key == "propaganda" else "propaganda"] == 0
                and not console_errors
            )
            results.append({
                "choice": choice_label,
                "passed": passed,
                "labels": labels,
                "prompt": prompt,
                "resources": resources,
                "console_errors": console_errors,
            })
            page.close()
        browser.close()

    summary = {
        "total": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "failed": sum(1 for result in results if not result["passed"]),
    }
    REPORT.write_text(json.dumps({"summary": summary, "service": BASE_URL, "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
