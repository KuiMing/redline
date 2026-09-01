#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "support-cards" / "red-support-action-art"
REPORT_JSON = RECORD_DIR / "RED_SUPPORT_ACTION_ART_BROWSER_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "red_support_action_card_ui.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-support-proof", {"support_name": "紅軍奧援", "tier": 1})
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, ok: bool, detail=None) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until="networkidle",
        )
        page.locator("#gameShell").wait_for(state="visible", timeout=15000)
        page.evaluate(
            """() => {
              document.getElementById('closeFactionActionModal')?.click();
              if (typeof closeEventReveal === 'function') closeEventReveal();
              if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
            }"""
        )
        card = page.locator("#hand .hand-card").filter(has=page.locator("[data-card-name='紅軍奧援']"))
        card.wait_for(state="visible", timeout=10000)
        image = card.locator(".playable-card-art-image")
        image.wait_for(state="visible", timeout=10000)
        page.wait_for_function(
            "() => [...document.querySelectorAll('#hand .playable-card-art-image')].some(img => img.alt.includes('紅軍奧援') && img.complete && img.naturalWidth === 1100 && img.naturalHeight === 1350)",
            timeout=10000,
        )
        metrics = image.evaluate(
            """img => {
              const imageRect = img.getBoundingClientRect();
              const faceRect = img.closest('.card-art-face')?.getBoundingClientRect();
              const buttons = [...img.closest('.hand-card').querySelectorAll('.hand-card-action-btn')]
                .map(button => ({text: button.textContent.trim(), mode: button.dataset.cardMode}));
              return {
                src: img.currentSrc,
                naturalWidth: img.naturalWidth,
                naturalHeight: img.naturalHeight,
                renderedWidth: imageRect.width,
                renderedHeight: imageRect.height,
                contained: !!faceRect
                  && imageRect.left >= faceRect.left - 1
                  && imageRect.top >= faceRect.top - 1
                  && imageRect.right <= faceRect.right + 1
                  && imageRect.bottom <= faceRect.bottom + 1,
                buttons,
              };
            }"""
        )
        record(
            "red_support_uses_cache_busted_action_layout_art",
            "17_%E7%B4%85%E8%BB%8D%E5%A5%A7%E6%8F%B4_%E8%B5%B7%E5%A7%8B%E7%89%8C.png" in metrics["src"]
            and "action-card-layout-20260811" in metrics["src"],
            {"src": metrics["src"]},
        )
        record(
            "red_support_art_has_canonical_full_resolution",
            metrics["naturalWidth"] == 1100 and metrics["naturalHeight"] == 1350,
            metrics,
        )
        record(
            "red_support_art_is_fully_contained_in_hand_card",
            metrics["renderedWidth"] > 0 and metrics["renderedHeight"] > 0 and metrics["contained"],
            metrics,
        )
        record(
            "red_support_keeps_resource_and_action_modes",
            metrics["buttons"] == [
                {"text": "資源", "mode": "resource"},
                {"text": "行動", "mode": "action"},
            ],
            metrics["buttons"],
        )
        card.scroll_into_view_if_needed()
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "status": "passed" if all(check["ok"] for check in checks) else "failed",
        "checks_passed": sum(1 for check in checks if check["ok"]),
        "checks_total": len(checks),
        "checks": checks,
        "console_errors": console_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "checks_passed": report["checks_passed"],
        "checks_total": report["checks_total"],
    }, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
