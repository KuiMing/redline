#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000")
RECORD_DIR = BASE / "docs/records/event-cards"
JSON_PATH = RECORD_DIR / "EVENT_CARD_ZOOM_PREVIEW_VALIDATION.json"
MD_PATH = RECORD_DIR / "EVENT_CARD_ZOOM_PREVIEW_VALIDATION.md"
OPEN_SHOT = RECORD_DIR / "event_card_zoom_preview_open.png"
PINNED_SHOT = RECORD_DIR / "event_card_zoom_preview_pinned.png"


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def check(checks: list[dict], name: str, passed: bool, details) -> None:
    checks.append({"name": name, "passed": bool(passed), "details": details})


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    html = (BASE / "static/index.html").read_text(encoding="utf-8")
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    css = (BASE / "static/style.css").read_text(encoding="utf-8")
    check(checks, "dedicated_event_reveal_overlay_exists", 'id="eventRevealModal"' in html and 'id="eventRevealCard"' in html, "event reveal DOM")
    check(checks, "plain_text_only_no_art_asset_binding", "eventRevealCard" in js and "card-art" not in js[js.find("function eventCardMarkup"):js.find("function minimizeEraAchievement")], "event renderer does not reference generated art")
    check(checks, "zoom_animation_and_cache_bust_exist", "@keyframes event-card-zoom-in" in css and "event-zoom-20260726" in html, "zoom keyframes + CSS/JS cache bust")

    setup = post_json("/test/setup-event-card-proof", {"event_name": "香港抗暴之戰", "current_event_active": True})
    url = f"{BASE_URL}{setup['url']}&v=event-card-zoom-preview"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        console_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_function("window.lastGameState && window.lastGameState.current_event", timeout=15000)
        page.locator("#eventRevealModal").wait_for(state="visible", timeout=8000)
        page.wait_for_timeout(450)

        open_state = page.evaluate("""() => {
          const overlay = document.getElementById('eventRevealModal');
          const card = document.getElementById('eventRevealCard');
          const rect = card.getBoundingClientRect();
          return {
            overlayDisplay: getComputedStyle(overlay).display,
            animationName: getComputedStyle(card).animationName,
            text: card.innerText,
            imageCount: card.querySelectorAll('img, picture, svg image').length,
            centerDelta: {
              x: Math.abs((rect.left + rect.width / 2) - window.innerWidth / 2),
              y: Math.abs((rect.top + rect.height / 2) - window.innerHeight / 2),
            },
            cardRect: {left: rect.left, top: rect.top, width: rect.width, height: rect.height},
          };
        }""")
        page.screenshot(path=str(OPEN_SHOT), full_page=True)
        check(
            checks,
            "turn_start_auto_opens_centered_zoom_preview",
            open_state["overlayDisplay"] == "flex"
            and open_state["animationName"] == "event-card-zoom-in"
            and open_state["centerDelta"]["x"] < 2
            and open_state["centerDelta"]["y"] < 2,
            open_state,
        )
        check(
            checks,
            "expanded_preview_shows_current_plain_text_event",
            all(text in open_state["text"] for text in ["本回合事件", "香港抗暴之戰", "任務條件", "成功獎勵", "失敗／紅軍效果", "點擊任意地方關閉"])
            and open_state["imageCount"] == 0,
            {"text": open_state["text"], "imageCount": open_state["imageCount"]},
        )

        # Clicking the enlarged card itself must dismiss because the user requested click-anywhere dismissal.
        page.locator("#eventRevealCard").click(position={"x": 20, "y": 20})
        page.wait_for_function("getComputedStyle(document.getElementById('eventRevealModal')).display === 'none'")
        page.evaluate("render(window.lastGameState)")
        page.wait_for_timeout(180)
        still_closed = page.evaluate("getComputedStyle(document.getElementById('eventRevealModal')).display")
        check(checks, "click_anywhere_closes_without_same_turn_reopen", still_closed == "none", {"displayAfterRerender": still_closed})

        # This fixture uses the liberals faction, whose existing optional ability modal may be
        # waiting underneath the event reveal. Dismiss it through the shipped Cancel control
        # before proving the pinned top-right card interaction.
        faction_modal = page.locator("#factionActionModal")
        if faction_modal.is_visible():
            page.locator("#closeFactionActionModal").click()
            faction_modal.wait_for(state="hidden")

        panel = page.locator("#eventCardPanel")
        panel.wait_for(state="visible")
        panel_state = page.evaluate("""() => {
          const panel = document.getElementById('eventCardPanel');
          return {role: panel.getAttribute('role'), tabindex: panel.getAttribute('tabindex'), text: panel.innerText};
        }""")
        page.screenshot(path=str(PINNED_SHOT), full_page=True)
        panel.click()
        page.locator("#eventRevealModal").wait_for(state="visible")
        reopened = page.evaluate("""() => ({
          display: getComputedStyle(document.getElementById('eventRevealModal')).display,
          animation: getComputedStyle(document.getElementById('eventRevealCard')).animationName,
          text: document.getElementById('eventRevealCard').innerText,
        })""")
        check(
            checks,
            "top_right_event_panel_reopens_preview",
            panel_state["role"] == "button"
            and panel_state["tabindex"] == "0"
            and "點擊放大查看" in panel_state["text"]
            and reopened["display"] == "flex"
            and reopened["animation"] == "event-card-zoom-in"
            and "香港抗暴之戰" in reopened["text"],
            {"panel": panel_state, "reopened": reopened},
        )

        page.keyboard.press("Escape")
        page.wait_for_function("getComputedStyle(document.getElementById('eventRevealModal')).display === 'none'")
        check(checks, "escape_also_closes_preview", True, "Escape closed the overlay")
        check(checks, "browser_console_has_no_errors", not console_errors, console_errors)
        browser.close()

    summary = {
        "total": len(checks),
        "passed": sum(1 for item in checks if item["passed"]),
        "failed": sum(1 for item in checks if not item["passed"]),
    }
    report = {
        "summary": summary,
        "base_url": BASE_URL,
        "event": setup.get("event_name"),
        "checks": checks,
        "screenshots": [str(OPEN_SHOT.relative_to(BASE)), str(PINNED_SHOT.relative_to(BASE))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Event Card Zoom Preview Validation",
        "",
        f"Summary: {summary['passed']}/{summary['total']} passed",
        "",
        f"- Open screenshot: `{OPEN_SHOT.relative_to(BASE)}`",
        f"- Pinned screenshot: `{PINNED_SHOT.relative_to(BASE)}`",
        "",
    ]
    for item in checks:
        lines.extend([f"## {'PASS' if item['passed'] else 'FAIL'} — {item['name']}", "", "```json", json.dumps(item["details"], ensure_ascii=False, indent=2), "```", ""])
    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
