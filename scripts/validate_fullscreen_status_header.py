#!/usr/bin/env python3
"""Browser proof：狀態列整合提示／重新開始，並將非卡牌介面延展至全畫面。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/fullscreen-status-header"
JSON_PATH = OUT / "FULLSCREEN_STATUS_HEADER_VALIDATION.json"
MD_PATH = OUT / "FULLSCREEN_STATUS_HEADER_VALIDATION.md"
SHOT_1280 = OUT / "fullscreen_status_header_1280x720_20260823.png"
SHOT_1024 = OUT / "fullscreen_status_header_1024x768_20260823.png"


def post_json(path: str) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-red-army-abilities-proof")
    checks: list[dict] = []
    errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=fullscreen-status-header-20260823",
            wait_until="networkidle",
        )
        page.wait_for_function("window.lastGameState && document.querySelectorAll('#purchaseStatic .card').length > 0", timeout=15000)
        page.evaluate("closeEventReveal?.()")
        page.wait_for_function(
            "[...document.querySelectorAll('.playable-card-art-image')].every(image => image.complete && image.naturalWidth > 0)",
            timeout=15000,
        )
        page.evaluate("document.fonts?.ready")
        page.wait_for_timeout(300)

        geometry = page.evaluate(
            """() => {
              const rect = element => {
                const box = element.getBoundingClientRect();
                return {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height};
              };
              const meta = document.getElementById('phaseActionMeta');
              const restart = document.getElementById('emergencyNewGameBtn');
              const hud = document.getElementById('hud');
              const shell = document.getElementById('gameShell');
              const grid = document.getElementById('commandGrid');
              const staticCard = document.querySelector('#purchaseStatic .card');
              const randomCard = document.querySelector('#purchaseRandom .card');
              const handCard = document.querySelector('#hand .card');
              const metaStyle = getComputedStyle(meta);
              const restartStyle = getComputedStyle(restart);
              return {
                topBarExists: !!document.getElementById('topBar'),
                hud: rect(hud), meta: rect(meta), restart: rect(restart), shell: rect(shell), grid: rect(grid),
                restartParent: restart.parentElement?.id || '',
                metaParent: meta.parentElement?.id || '',
                restartText: restart.textContent.trim(),
                restartHref: restart.getAttribute('href'),
                metaText: meta.textContent.trim(),
                metaColor: metaStyle.color,
                restartColor: restartStyle.color,
                restartBackground: restartStyle.backgroundColor,
                tabFont: parseFloat(getComputedStyle(document.querySelector('.game-tab')).fontSize),
                panelTitleFont: parseFloat(getComputedStyle(document.querySelector('.panel-title')).fontSize),
                staticCard: staticCard ? rect(staticCard) : null,
                randomCard: randomCard ? rect(randomCard) : null,
                handCard: handCard ? rect(handCard) : null,
                documentScroll: {width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight},
              };
            }"""
        )
        record("restart_label_and_route_are_preserved", geometry["restartText"] == "重新開始" and geometry["restartHref"] == "/new-game", {"text": geometry["restartText"], "href": geometry["restartHref"]})
        record("obsolete_top_row_is_removed", not geometry["topBarExists"] and geometry["hud"]["top"] <= 1, {"topBarExists": geometry["topBarExists"], "hud": geometry["hud"]})
        same_row = abs((geometry["meta"]["top"] + geometry["meta"]["bottom"]) / 2 - (geometry["restart"]["top"] + geometry["restart"]["bottom"]) / 2) <= 2
        record(
            "gold_phase_hint_is_left_of_restart_in_status_row",
            geometry["metaParent"] == geometry["restartParent"] == "hudStatusActions"
            and geometry["meta"]["right"] <= geometry["restart"]["left"]
            and same_row
            and geometry["metaColor"] in {"rgb(251, 191, 36)", "rgb(253, 230, 138)"},
            {key: geometry[key] for key in ["meta", "restart", "metaParent", "restartParent", "metaColor", "metaText"]},
        )
        before = page.evaluate("getComputedStyle(document.getElementById('emergencyNewGameBtn')).color")
        page.locator("#emergencyNewGameBtn").hover()
        page.wait_for_timeout(100)
        after = page.evaluate("getComputedStyle(document.getElementById('emergencyNewGameBtn')).color")
        record("restart_is_dim_until_hover", before != after, {"before": before, "after": after})
        page.mouse.move(640, 360)

        record(
            "game_shell_and_command_grid_extend_to_stage_bottom",
            geometry["shell"]["top"] <= geometry["hud"]["bottom"] + 10
            and geometry["shell"]["bottom"] >= 719
            and geometry["grid"]["bottom"] >= 707,
            {"hud": geometry["hud"], "shell": geometry["shell"], "grid": geometry["grid"]},
        )
        card_sizes = {
            "static": geometry["staticCard"], "random": geometry["randomCard"], "hand": geometry["handCard"]
        }
        record(
            "card_dimensions_remain_unchanged",
            geometry["staticCard"] is not None
            and abs(geometry["staticCard"]["width"] - 220) <= 1
            and abs(geometry["staticCard"]["height"] - 270) <= 1
            and abs(geometry["randomCard"]["width"] - 220) <= 1
            and abs(geometry["randomCard"]["height"] - 270) <= 1
            and (geometry["handCard"] is None or (abs(geometry["handCard"]["width"] - 220) <= 1 and abs(geometry["handCard"]["height"] - 318) <= 1)),
            card_sizes,
        )
        record("non_card_ui_fonts_are_slightly_larger", geometry["tabFont"] >= 13.5 and geometry["panelTitleFont"] >= 12.8, {"tabFont": geometry["tabFont"], "panelTitleFont": geometry["panelTitleFont"]})

        view_panels = {}
        for view_name, panel_selector in [
            ("map", "#mapPanel"),
            ("log", "#logViewPanel"),
            ("myFaction", "#myFactionView .personal-info-panel"),
        ]:
            page.locator(f'.game-tab[data-view="{view_name}"]').click()
            page.wait_for_timeout(150)
            view_panels[view_name] = page.locator(panel_selector).evaluate(
                """element => {
                  const box = element.getBoundingClientRect();
                  return {left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height};
                }"""
            )
        record(
            "map_log_and_personal_views_extend_with_the_shell",
            all(panel["left"] >= 0 and panel["right"] <= 1280 and panel["bottom"] >= 707 and panel["bottom"] <= 720 for panel in view_panels.values()),
            view_panels,
        )
        page.locator('.game-tab[data-view="command"]').click()
        page.wait_for_timeout(150)
        page.screenshot(path=str(SHOT_1280), full_page=True)

        page.set_viewport_size({"width": 1024, "height": 768})
        page.wait_for_timeout(300)
        narrow = page.evaluate(
            """() => {
              const ids = ['hud', 'phaseActionMeta', 'emergencyNewGameBtn', 'gameShell', 'commandGrid'];
              const rects = Object.fromEntries(ids.map(id => {
                const box = document.getElementById(id).getBoundingClientRect();
                return [id, {left: box.left, top: box.top, right: box.right, bottom: box.bottom}];
              }));
              return {rects, scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight};
            }"""
        )
        record(
            "narrow_view_has_no_clipping_or_page_scroll",
            all(value["left"] >= -0.5 and value["right"] <= 1024.5 and value["top"] >= -0.5 and value["bottom"] <= 768.5 for value in narrow["rects"].values())
            and narrow["scrollWidth"] <= 1024 and narrow["scrollHeight"] <= 768,
            narrow,
        )
        page.screenshot(path=str(SHOT_1024), full_page=True)
        browser.close()

    record("browser_console_has_no_errors", not errors, errors)
    summary = {"total": len(checks), "passed": sum(1 for check in checks if check["passed"]), "failed": sum(1 for check in checks if not check["passed"])}
    report = {
        "summary": summary,
        "service": BASE_URL,
        "scenario": "紅軍行動階段；識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [str(SHOT_1280.relative_to(ROOT)), str(SHOT_1024.relative_to(ROOT))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text("\n".join([
        "# 全畫面狀態列整合 Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
