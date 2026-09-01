#!/usr/bin/env python3
"""Browser proof：HUD 長階段提示可在 hover／鍵盤 focus 時顯示完整說明。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/phase-guidance-hover-full-text"
REPORT_JSON = OUT / "PHASE_GUIDANCE_HOVER_FULL_TEXT_VALIDATION.json"
REPORT_MD = OUT / "PHASE_GUIDANCE_HOVER_FULL_TEXT_VALIDATION.md"
LONG_TEXT = "烏魯木齊七五事件：探聽東突厥的現況；回合結束時至少有 1 個己方組織在牆內。成功：免費在己方組織 1 格內建立 1 個組織。失敗：被紅軍隨機棄掉 1 張手牌。"


def intersects(a: dict, b: dict) -> bool:
    return not (a["right"] <= b["left"] or a["left"] >= b["right"] or a["bottom"] <= b["top"] or a["top"] >= b["bottom"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(f"{BASE_URL}/?v=phase-guidance-hover-full-text-proof", wait_until="domcontentloaded")
        page.wait_for_function("typeof setPhaseActionMeta === 'function'")

        screenshots: list[str] = []
        for width, height in ((1280, 720), (1024, 768)):
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate(
                """text => {
                  document.getElementById('lobby').style.display = 'none';
                  const hud = document.getElementById('hud');
                  hud.style.display = 'flex';
                  document.getElementById('hudMainRow').innerHTML = '<span class="hud-chip hud-chip-primary">回合 6</span><span class="hud-chip">當前玩家 滿洲</span><span class="hud-chip hud-chip-resource">資金 0</span><span class="hud-chip hud-chip-resource">宣傳 0</span>';
                  setPhaseActionMeta(text);
                }""",
                LONG_TEXT,
            )
            page.wait_for_timeout(150)
            meta = page.locator("#phaseActionMeta")
            wrap = page.locator("#phaseActionMetaWrap")
            tooltip = page.locator("#phaseActionMetaTooltip")
            restart = page.locator("#emergencyNewGameBtn")
            dimensions = meta.evaluate("el => ({clientWidth:el.clientWidth, scrollWidth:el.scrollWidth, text:el.textContent, tabIndex:el.tabIndex})")
            record(f"long_text_is_visually_truncated_{width}x{height}", dimensions["scrollWidth"] > dimensions["clientWidth"] and dimensions["text"] == LONG_TEXT, dimensions)
            record(f"overflow_state_is_enabled_{width}x{height}", "is-overflowing" in (wrap.get_attribute("class") or "") and dimensions["tabIndex"] == 0, {"class": wrap.get_attribute("class"), **dimensions})

            meta.hover()
            page.wait_for_timeout(100)
            tooltip_state = tooltip.evaluate(
                """el => {
                  const r=el.getBoundingClientRect();
                  return {text:el.textContent, display:getComputedStyle(el).display, ariaHidden:el.getAttribute('aria-hidden'), rect:{left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
                }"""
            )
            restart_rect = restart.evaluate("el => {const r=el.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom}}")
            viewport_rect = {"left": 0, "top": 0, "right": width, "bottom": height}
            visible_and_complete = tooltip_state["display"] == "block" and tooltip_state["text"] == LONG_TEXT and tooltip_state["ariaHidden"] == "false"
            record(f"hover_shows_complete_text_{width}x{height}", visible_and_complete, tooltip_state)
            tooltip_inside = tooltip_state["rect"]["left"] >= viewport_rect["left"] and tooltip_state["rect"]["right"] <= viewport_rect["right"] and tooltip_state["rect"]["top"] >= viewport_rect["top"] and tooltip_state["rect"]["bottom"] <= viewport_rect["bottom"]
            record(f"tooltip_is_inside_view_and_avoids_restart_{width}x{height}", tooltip_inside and not intersects(tooltip_state["rect"], restart_rect), {"tooltip": tooltip_state["rect"], "restart": restart_rect, "viewport": viewport_rect})

            meta.focus()
            page.wait_for_timeout(80)
            focus_display = tooltip.evaluate("el => getComputedStyle(el).display")
            record(f"keyboard_focus_also_shows_tooltip_{width}x{height}", focus_display == "block", focus_display)
            screenshot = OUT / f"phase_guidance_hover_full_text_{width}x{height}_20260823.png"
            page.screenshot(path=str(screenshot), full_page=True)
            screenshots.append(str(screenshot.relative_to(ROOT)))

        page.evaluate("setPhaseActionMeta('目前：行動｜下一步：結束行動')")
        page.wait_for_timeout(100)
        short_state = page.evaluate(
            """() => ({
              overflowing:document.getElementById('phaseActionMetaWrap').classList.contains('is-overflowing'),
              tabIndex:document.getElementById('phaseActionMeta').tabIndex,
              ariaHidden:document.getElementById('phaseActionMetaTooltip').getAttribute('aria-hidden'),
            })"""
        )
        record("short_text_does_not_open_unneeded_tooltip", not short_state["overflowing"] and short_state["tabIndex"] == -1 and short_state["ariaHidden"] == "true", short_state)
        record("browser_console_has_no_errors", not console_errors, console_errors)
        browser.close()

    summary = {"total": len(checks), "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks)}
    report = {"summary": summary, "base_url": BASE_URL, "long_text": LONG_TEXT, "checks": checks, "screenshots": screenshots}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 金色階段提示完整 hover 說明驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
