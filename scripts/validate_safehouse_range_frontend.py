#!/usr/bin/env python3
"""Browser proof: 2026-08-09 playtest bug — 安全屋 卡面「建立牆內組織時，可建立組織距離
額外增加1格」只該對牆內（ruler 含紅軍）目標生效；先前 `static/app.js` 的「支援建立」側欄
與 `static/leaflet_game_map_logic.js` 地圖點擊建組織高亮，兩處都用寫死的 2 步 BFS，不分
牆內牆外一律放寬，導致從臺北出發時連宜蘭/金門/馬祖等牆外城鎮都被錯誤列為建立目標
（玩家一開始選城鎮就看到一堆超出正常距離的候選，形同「一開始就能發動」）。

修法：兩處都改成只有牆內目標吃到 2 步距離，牆外目標維持基礎 1 步，比照後端
`Game._is_inside_wall_town()`／`build_organization_with_support()` 早已正確的邏輯。
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
RECORD_DIR = ROOT / "docs" / "records" / "safehouse"
JSON_PATH = RECORD_DIR / "SAFEHOUSE_RANGE_FRONTEND_VALIDATION.json"
MD_PATH = RECORD_DIR / "SAFEHOUSE_RANGE_FRONTEND_VALIDATION.md"

# 從臺北出發：1 步鄰居（牆外，一定合法）＋已知的 2 步牆外城鎮（修正前才會誤出現）。
EXPECTED_ONE_STEP = {"基隆", "新北", "桃園"}
ILLEGAL_TWO_STEP_OUTSIDE_WALL = {"宜蘭", "新竹", "沖繩", "金門", "馬祖"}


def run_support_panel_case() -> Dict[str, Any]:
    setup = requests.post(f"{BASE_URL}/test/setup-safehouse-range-proof", json={"base": "臺北"}, timeout=10).json()
    failures: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until="networkidle")
        page.wait_for_function("() => Boolean(window.lastGameState)")
        page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
          const btns = Array.from(document.querySelectorAll('#buildSupportOrigins button'));
          const btn = btns.find(b => b.textContent.trim() === '臺北');
          if (btn) btn.click();
        }""")
        page.wait_for_timeout(500)
        screenshot = RECORD_DIR / "support-panel-taipei-targets.png"
        page.screenshot(path=str(screenshot))

        targets = set(page.locator("#buildSupportTargets button").all_inner_texts())
        if targets != EXPECTED_ONE_STEP:
            failures.append(f"support panel targets mismatch: got {sorted(targets)}, expected {sorted(EXPECTED_ONE_STEP)}")
        leaked = targets & ILLEGAL_TWO_STEP_OUTSIDE_WALL
        if leaked:
            failures.append(f"support panel leaked outside-wall 2-step towns: {sorted(leaked)}")

        browser.close()

    return {
        "name": "support_panel_taipei_outside_wall_targets_capped_at_1_step",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
    }


def run_map_build_options_case() -> Dict[str, Any]:
    setup = requests.post(f"{BASE_URL}/test/setup-safehouse-range-proof", json={"base": "臺北"}, timeout=10).json()
    failures: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until="networkidle")
        page.wait_for_function("() => Boolean(window.lastGameState)")
        page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
        page.wait_for_timeout(500)
        page.evaluate("""() => {
          const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === '戰略地圖');
          if (btn) btn.click();
        }""")
        page.wait_for_timeout(1500)
        frame = next((f for f in page.frames if "leaflet_game_map" in (f.url or "")), None)
        if frame is None:
            failures.append("map iframe not found")
        else:
            frame.wait_for_function(
                "() => typeof buildOptionsForTown === 'function' && !!MAP_DATA", timeout=10000
            )
            result = frame.evaluate("() => buildOptionsForTown('臺北')")
            targets = set(result or [])
            if targets != EXPECTED_ONE_STEP:
                failures.append(f"map buildOptionsForTown mismatch: got {sorted(targets)}, expected {sorted(EXPECTED_ONE_STEP)}")
            leaked = targets & ILLEGAL_TWO_STEP_OUTSIDE_WALL
            if leaked:
                failures.append(f"map buildOptionsForTown leaked outside-wall 2-step towns: {sorted(leaked)}")

        browser.close()

    return {
        "name": "map_build_options_taipei_outside_wall_targets_capped_at_1_step",
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_support_panel_case(), run_map_build_options_case()]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Safehouse Range Frontend — Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 安全屋的 +1 建立距離只該對牆內目標生效；從臺北出發，牆外只到 1 步（基隆/新北/桃園），",
        "  宜蘭/新竹/沖繩/金門/馬祖等牆外 2 步城鎮不該出現在建立目標清單。涵蓋 `支援建立` 側欄與",
        "  戰略地圖點擊建組織高亮兩處獨立的前端實作。",
        "",
    ]
    for r in results:
        lines.append(f"## {r['name']} — {r['status']}")
        lines.append("")
        if r.get("screenshot"):
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
