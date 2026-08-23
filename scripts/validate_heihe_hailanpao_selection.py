#!/usr/bin/env python3
"""Browser proof：海蘭泡與黑河的近距離標籤可分辨，點海蘭泡會選中海蘭泡。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/map-ui/heihe-hailanpao-selection"
REPORT_JSON = OUT / "HEIHE_HAILANPAO_SELECTION_VALIDATION.json"
REPORT_MD = OUT / "HEIHE_HAILANPAO_SELECTION_VALIDATION.md"
SCREENSHOT = OUT / "hailanpao_selected_1280x720_20260823.png"
SCREENSHOT_1024 = OUT / "hailanpao_selected_1024x768_20260823.png"


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
        page.goto(f"{BASE_URL}/static/leaflet_game_map.html?v=heihe-hailanpao-selection-proof", wait_until="domcontentloaded")
        page.wait_for_function("window.__redlinePlayableMap && window.__mapDebugStateForTest", timeout=15000)
        page.evaluate("void window.__redlinePlayableMap.setView([50.2529, 127.5308], 6, {animate:false})")
        page.wait_for_function("[...document.querySelectorAll('.town-label')].some(el => el.textContent.trim() === '海蘭泡')", timeout=15000)
        page.wait_for_timeout(500)

        geometry = page.evaluate(
            """() => {
              const labels = {};
              for (const el of document.querySelectorAll('.town-label')) {
                const name = String(el.textContent || '').trim();
                if (!['黑河', '海蘭泡'].includes(name)) continue;
                const r = el.getBoundingClientRect();
                labels[name] = {
                  left:r.left, top:r.top, right:r.right, bottom:r.bottom,
                  width:r.width, height:r.height,
                  pointerEvents:getComputedStyle(el).pointerEvents,
                  classes:[...el.classList],
                };
              }
              const a = labels['黑河'];
              const b = labels['海蘭泡'];
              const markers = {};
              window.__redlinePlayableMap.eachLayer(layer => {
                const content = String(layer.getPopup?.()?.getContent?.() || '');
                const name = ['黑河', '海蘭泡'].find(candidate => content.includes(`<div class="name">${candidate}</div>`));
                if (!name || !layer.getLatLng) return;
                const point = window.__redlinePlayableMap.latLngToContainerPoint(layer.getLatLng());
                const mapRect = window.__redlinePlayableMap.getContainer().getBoundingClientRect();
                markers[name] = {x:mapRect.left + point.x, y:mapRect.top + point.y};
              });
              const markerDistance = markers['黑河'] && markers['海蘭泡']
                ? Math.hypot(markers['黑河'].x-markers['海蘭泡'].x, markers['黑河'].y-markers['海蘭泡'].y)
                : null;
              const overlapWidth = a && b ? Math.max(0, Math.min(a.right,b.right)-Math.max(a.left,b.left)) : null;
              const overlapHeight = a && b ? Math.max(0, Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)) : null;
              return {labels, markers, markerDistance, overlapArea: overlapWidth == null || overlapHeight == null ? null : overlapWidth * overlapHeight};
            }"""
        )
        record("both_labels_are_visible", set(geometry["labels"]) == {"黑河", "海蘭泡"}, geometry)
        record("nearby_labels_do_not_overlap", geometry["overlapArea"] == 0, geometry)
        record("nearby_markers_have_distinct_click_targets", (geometry.get("markerDistance") or 0) >= 20, geometry)

        hailan_marker = geometry.get("markers", {}).get("海蘭泡") or {}
        if hailan_marker:
            page.mouse.click(hailan_marker["x"], hailan_marker["y"])
            page.wait_for_timeout(300)
        marker_selected = page.evaluate(
            """() => ({
              selectedTown: window.__mapDebugStateForTest?.()?.selectedTown || null,
              infoText: document.getElementById('info')?.innerText || '',
            })"""
        )
        record(
            "clicking_hailanpao_marker_selects_hailanpao",
            marker_selected["selectedTown"] == "海蘭泡" and marker_selected["infoText"].strip().startswith("海蘭泡"),
            marker_selected,
        )

        page.evaluate("void window.__redlinePlayableMap.setView([50.2529, 127.5308], 6, {animate:false})")
        page.wait_for_timeout(350)
        hailan = page.evaluate(
            """() => {
              const el = [...document.querySelectorAll('.town-label')].find(node => node.textContent.trim() === '海蘭泡');
              if (!el) return null;
              const r = el.getBoundingClientRect();
              return {left:r.left, top:r.top, width:r.width, height:r.height};
            }"""
        ) or {}
        if hailan:
            page.mouse.click(hailan["left"] + hailan["width"] / 2, hailan["top"] + hailan["height"] / 2)
            page.wait_for_timeout(300)
        selected = page.evaluate(
            """() => ({
              selectedTown: window.__mapDebugStateForTest?.()?.selectedTown || null,
              infoText: document.getElementById('info')?.innerText || '',
            })"""
        )
        record(
            "clicking_hailanpao_label_selects_hailanpao",
            selected["selectedTown"] == "海蘭泡" and selected["infoText"].strip().startswith("海蘭泡"),
            selected,
        )
        page.evaluate("void window.__redlinePlayableMap.setView([50.2529, 127.5308], 6, {animate:false})")
        page.wait_for_timeout(350)
        page.locator("#info").scroll_into_view_if_needed()
        page.screenshot(path=str(SCREENSHOT), full_page=True)

        page.set_viewport_size({"width": 1024, "height": 768})
        page.evaluate("void window.__redlinePlayableMap.setView([50.2529, 127.5308], 6, {animate:false})")
        page.wait_for_timeout(350)
        page.locator("#info").scroll_into_view_if_needed()
        compact = page.evaluate(
            """() => {
              const boxes = {};
              for (const el of document.querySelectorAll('.town-label')) {
                const name = el.textContent.trim();
                if (!['黑河', '海蘭泡'].includes(name)) continue;
                const r = el.getBoundingClientRect();
                boxes[name] = {left:r.left, top:r.top, right:r.right, bottom:r.bottom};
              }
              const a=boxes['黑河'], b=boxes['海蘭泡'];
              const overlap = a && b ? Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)) : null;
              return {selectedTown:window.__mapDebugStateForTest?.()?.selectedTown || null, boxes, overlap};
            }"""
        )
        record("compact_view_keeps_hailanpao_selected_and_labels_separate", compact["selectedTown"] == "海蘭泡" and compact["overlap"] == 0, compact)
        page.screenshot(path=str(SCREENSHOT_1024), full_page=True)
        record("browser_console_has_no_errors", not console_errors, console_errors)
        browser.close()

    summary = {"total": len(checks), "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks)}
    report = {"summary": summary, "base_url": BASE_URL, "checks": checks, "screenshots": [str(SCREENSHOT.relative_to(ROOT)), str(SCREENSHOT_1024.relative_to(ROOT))]}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 黑河／海蘭泡地圖選取驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
