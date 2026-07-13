#!/usr/bin/env python3
"""Validate that the map shows a buildable-town count that matches the highlighted set.

Loads the standalone Leaflet map, injects a build-organisation choice highlight (as the
main app does via a `redline-choice-highlight` postMessage), and asserts the interaction
hint reports "可建立城鎮：N 個" where N equals the number of orange highlight markers
actually rendered. Also checks a non-build target choice reports "可選目標：N 個".
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "records" / "map-ui"
URL = "http://127.0.0.1:8000/static/leaflet_game_map.html"

BUILD_TOWNS = ["臺北", "基隆", "新北", "桃園", "宜蘭"]        # 5 towns
TARGET_TOWNS = ["高雄", "臺南", "屏東"]                       # 3 towns


def inject_and_read(page, choice_key, towns, source_name, prompt):
    return page.evaluate(
        """
        async ({choiceKey, towns, sourceName, prompt}) => {
          const payload = {
            mode: 'support-targets',
            choiceKey,
            sourceName,
            prompt,
            towns: towns.map((t, i) => ({ town: t, label: t, index: i })),
          };
          window.dispatchEvent(new MessageEvent('message', { data: { type: 'redline-choice-highlight', payload } }));
          await new Promise(r => setTimeout(r, 200));
          // Count orange choice-highlight markers on the map.
          let orange = 0;
          window.__redlinePlayableMap.eachLayer(layer => {
            if (layer instanceof L.CircleMarker && layer.options) {
              const c = layer.options.color;
              if (c === '#f97316' || c === '#facc15') orange += 1;
            }
          });
          return {
            hint: document.getElementById('interactionHint')?.textContent || '',
            orangeMarkers: orange,
          };
        }
        """,
        {"choiceKey": choice_key, "towns": towns, "sourceName": source_name, "prompt": prompt},
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(400)

        build = inject_and_read(page, "card_build_organization", BUILD_TOWNS, "宣傳家", "請選擇要建立組織的城鎮。")
        # Each buildable town renders exactly one orange outer ring (the inner marker is
        # off-white), so the orange-ring count is the clickable/buildable town count.
        record(
            "build_choice_shows_buildable_count_matching_towns",
            f"可建立城鎮：{len(BUILD_TOWNS)} 個" in build["hint"],
            {"hint": build["hint"], "expected": len(BUILD_TOWNS)},
        )
        record(
            "build_count_matches_rendered_orange_markers",
            build["orangeMarkers"] == len(BUILD_TOWNS),
            {"orangeMarkers": build["orangeMarkers"], "towns": len(BUILD_TOWNS)},
        )

        target = inject_and_read(page, "support_interaction", TARGET_TOWNS, "天方奧援", "請選擇要瓦解的目標。")
        record(
            "non_build_target_choice_shows_target_count",
            f"可選目標：{len(TARGET_TOWNS)} 個" in target["hint"] and "可建立城鎮" not in target["hint"],
            {"hint": target["hint"], "expected": len(TARGET_TOWNS)},
        )

        page.screenshot(path=str(OUT_DIR / "BUILDABLE_TOWN_COUNT_VALIDATION.png"), full_page=True)
        browser.close()

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
    }
    payload = {"summary": summary, "results": results}
    (OUT_DIR / "BUILDABLE_TOWN_COUNT_VALIDATION.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "BUILDABLE_TOWN_COUNT_VALIDATION.md").write_text(
        "# Buildable town count validation\n\n"
        "可重跑指令：`python3 scripts/validate_buildable_town_count.py`\n\n"
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}\n\n"
        "## Results\n\n"
        + "\n".join(
            f"- {'PASS' if r['ok'] else 'FAIL'} {r['name']}: {json.dumps(r['detail'], ensure_ascii=False)}"
            for r in results
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
