#!/usr/bin/env python3
"""Browser proof: 2026-08-09 playtest bug — the faction-action modal for 澳門／改革開放派／
自由派／民族祭儀各族 used to force itself back open (`display: flex`) on EVERY render while
in the player's action phase, regardless of what the player was doing. Once the ability had
been used for the turn, this meant an unrelated action (e.g. playing a hand card as a
resource) would keep re-triggering the "本回合已發動陣營能力" popup on top of the screen.
Fix: these factions now use the same small non-blocking panel pattern as 紅軍 instead of an
unconditionally forced centered modal; the modal only opens on an explicit "發動" click.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "http://127.0.0.1:8000"
RECORD_DIR = ROOT / "docs" / "records" / "faction-ui" / "modal-not-forced"
JSON_PATH = RECORD_DIR / "FACTION_ACTION_MODAL_NOT_FORCED_VALIDATION.json"
MD_PATH = RECORD_DIR / "FACTION_ACTION_MODAL_NOT_FORCED_VALIDATION.md"


def modal_is_visible(page) -> bool:
    return page.evaluate(
        "() => { const el = document.getElementById('factionActionModal'); "
        "return el && getComputedStyle(el).display !== 'none'; }"
    )


def dismiss_startup_overlays(page) -> None:
    # 每次 test-setup 都會釘一個「歲月靜好」事件，前端會自動彈出事件放大檢視
    # （#eventRevealModal），蓋住畫面攔截點擊；跟這支驗證要測的陣營能力 modal 無關，
    # 先關掉才能點到手牌按鈕（沿用既有 validator 慣用的關閉手法）。刻意不動
    # #factionActionModal 本身——那正是這支驗證要檢查的對象，不能先幫它關掉。
    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
    page.wait_for_timeout(200)


def run_case_already_used_does_not_reopen_on_unrelated_action(faction_id: str) -> Dict[str, Any]:
    setup = requests.post(
        f"{BASE_URL}/test/setup-faction-action-used-proof",
        json={"faction_id": faction_id, "faction_action_used": True},
        timeout=10,
    ).json()
    failures: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until="networkidle")
        page.wait_for_function("() => Boolean(window.lastGameState)")
        page.wait_for_timeout(500)
        dismiss_startup_overlays(page)

        if modal_is_visible(page):
            failures.append("modal force-open on initial load despite faction_action_used=True")

        page.locator('.hand-card-action-btn[data-card-mode="resource"]').first.click()
        page.wait_for_timeout(800)
        screenshot = RECORD_DIR / f"{faction_id}-after-unrelated-resource-click.png"
        page.screenshot(path=str(screenshot))

        if modal_is_visible(page):
            failures.append("modal re-opened after clicking an unrelated hand card's 資源 button")
        body_text = page.locator("body").inner_text()
        if "本回合已發動陣營能力" in body_text:
            failures.append("'本回合已發動陣營能力' message shown despite the action being unrelated")
        hud_text = page.locator("#hud").inner_text()
        if "手牌 0" not in hud_text:
            failures.append(f"resource action did not actually go through: {hud_text!r}")

        browser.close()

    return {
        "name": f"{faction_id}_already_used_modal_does_not_reopen",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
    }


def run_case_not_used_shows_panel_not_modal(faction_id: str, expected_button_text: str) -> Dict[str, Any]:
    setup = requests.post(
        f"{BASE_URL}/test/setup-faction-action-used-proof",
        json={"faction_id": faction_id, "faction_action_used": False},
        timeout=10,
    ).json()
    failures: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until="networkidle")
        page.wait_for_function("() => Boolean(window.lastGameState)")
        page.wait_for_timeout(500)
        dismiss_startup_overlays(page)
        screenshot = RECORD_DIR / f"{faction_id}-not-used-panel.png"
        page.screenshot(path=str(screenshot))

        if modal_is_visible(page):
            failures.append("modal force-open before the player has activated the ability")
        panel_text = page.locator("#factionActionPanel").inner_text()
        if expected_button_text not in panel_text:
            failures.append(f"panel missing expected activate button {expected_button_text!r}: {panel_text!r}")

        browser.close()

    return {
        "name": f"{faction_id}_not_used_shows_panel_not_modal",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        run_case_not_used_shows_panel_not_modal("aomen", "發動 賭徒耳語"),
        run_case_already_used_does_not_reopen_on_unrelated_action("aomen"),
        run_case_already_used_does_not_reopen_on_unrelated_action("reform_opening"),
        run_case_not_used_shows_panel_not_modal("liberals", "發動 立場試探"),
        run_case_already_used_does_not_reopen_on_unrelated_action("zhuang"),
    ]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Faction Action Modal Not Forced — Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 澳門／改革開放派／自由派／民族祭儀各族的陣營能力面板改用小面板（比照紅軍既有作法），",
        "  不再無條件強制彈出置中 modal；本回合已發動後，不相關操作（例如打出手牌拿資源）不會",
        "  再把「本回合已發動陣營能力」的彈窗重新蓋回畫面。",
        "",
    ]
    for r in results:
        lines.append(f"## {r['name']} — {r['status']}")
        lines.append("")
        lines.append(f"- screenshot: `{r['screenshot']}`")
        if r["failures"]:
            lines.append(f"- failures: {r['failures']}")
        lines.append("")
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"{summary['passed']} passed / {summary['failed']} failed")
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
