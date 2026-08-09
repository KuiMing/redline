#!/usr/bin/env python3
"""Browser proof: 2026-08-09 使用者追加回饋 —— 指揮中心／戰略地圖分頁上方本來就有的時代
關卡提示列（`.hud-era-row` / `.hud-era-pill`）比右上角釘選卡片更顯眼、更直覺，應該直接點
這裡看完整說明；四人局最多可能同時有 3 個時代關卡生效，每個提示要各自對應自己的時代。

過程中另外發現一個更深層、與這次改動無關但被這次一起抓到的既有 layout bug：
`#phaseActionBar` 用寫死的 `top: 90px` 絕對定位，只夠容納單行 HUD；一旦 `.hud-era-row`
出現（任何時代關卡生效中，不限本次的 3 個一起觸發），HUD 多長出一行，`#phaseActionBar`
仍疊在原本的固定高度上，直接蓋住時代關卡提示列——畫面上「好像」有東西、實際上完全點
不到。這正是使用者「所以我要點擊哪裡才看得到說明？」會感到困惑的根本原因。已改成每次
重繪都依 HUD 實際量到的高度動態推算 `#phaseActionBar` 的位置。
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
RECORD_DIR = ROOT / "docs" / "records" / "era-restrict-ignore-distance"
JSON_PATH = RECORD_DIR / "ERA_HUD_ROW_CLICKABLE_VALIDATION.json"
MD_PATH = RECORD_DIR / "ERA_HUD_ROW_CLICKABLE_VALIDATION.md"


def dismiss_startup_overlays(page) -> None:
    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
    page.wait_for_timeout(200)


def run_three_simultaneous_eras() -> Dict[str, Any]:
    """四人局情境的代表案例：3 個時代關卡同時生效，HUD 列出 3 個各自可點的提示。"""
    setup = requests.post(
        f"{BASE_URL}/test/setup-era-restrict-ignore-distance-proof",
        json={"era": "rebels", "extra_eras": ["kazakh", "manchuria"]},
        timeout=10,
    ).json()
    failures: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until="networkidle")
        page.wait_for_function("() => Boolean(window.lastGameState)")
        dismiss_startup_overlays(page)
        page.evaluate("() => { const el = document.getElementById('eraAchievementModal'); if (el) el.style.display = 'none'; }")
        page.wait_for_timeout(500)
        screenshot = RECORD_DIR / "hud-row-three-eras.png"
        page.screenshot(path=str(screenshot))

        pill_texts = page.locator(".hud-era-pill").all_inner_texts()
        if len(pill_texts) != 3:
            failures.append(f"expected 3 pills, got {len(pill_texts)}: {pill_texts}")

        # 不能只看 DOM 存在，要確認畫面上真的沒有東西蓋在上面（elementFromPoint 命中的
        # 是 pill 本身，不是別的元素）——這是這次抓到的實際 bug 的核心斷言。
        overlap_probe = page.evaluate(
            """() => {
              const pill = document.querySelector('.hud-era-pill');
              const rect = pill.getBoundingClientRect();
              const cx = rect.left + rect.width / 2;
              const cy = rect.top + rect.height / 2;
              const topEl = document.elementFromPoint(cx, cy);
              return { isPillOnTop: topEl === pill, topElId: topEl ? topEl.id : null, topElClass: topEl ? topEl.className : null };
            }"""
        )
        if not overlap_probe["isPillOnTop"]:
            failures.append(f"another element paints over the era pill: {overlap_probe}")

        # 分別點擊哈薩克與滿洲的提示（不是預設彈出的反賊），確認各自對應正確的時代。
        page.evaluate("""() => {
          const btn = Array.from(document.querySelectorAll('.hud-era-pill')).find(b => b.textContent.includes('哈薩克'));
          if (btn) btn.click();
        }""")
        page.wait_for_timeout(400)
        kazakh_title = page.locator("#eraAchievementTitle").inner_text()
        if "哈薩克" not in kazakh_title:
            failures.append(f"clicking 哈薩克 pill did not open 哈薩克 modal: {kazakh_title!r}")

        page.evaluate("() => { if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement(); }")
        page.wait_for_timeout(300)
        page.evaluate("""() => {
          const btn = Array.from(document.querySelectorAll('.hud-era-pill')).find(b => b.textContent.includes('滿洲'));
          if (btn) btn.click();
        }""")
        page.wait_for_timeout(400)
        manchuria_title = page.locator("#eraAchievementTitle").inner_text()
        if "滿洲" not in manchuria_title:
            failures.append(f"clicking 滿洲 pill did not open 滿洲 modal: {manchuria_title!r}")

        browser.close()

    return {
        "name": "three_simultaneous_eras_hud_row_each_independently_clickable",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
    }


def run_single_era_no_overlap() -> Dict[str, Any]:
    """基準情境（只有 1 個時代關卡）：確認 phaseActionBar 動態定位沒有引入新的重疊。"""
    setup = requests.post(
        f"{BASE_URL}/test/setup-era-restrict-ignore-distance-proof",
        json={"era": "rebels"},
        timeout=10,
    ).json()
    failures: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until="networkidle")
        page.wait_for_function("() => Boolean(window.lastGameState)")
        dismiss_startup_overlays(page)
        page.evaluate("() => { const el = document.getElementById('eraAchievementModal'); if (el) el.style.display = 'none'; }")
        page.wait_for_timeout(500)

        advance_btn_visible = page.evaluate(
            """() => {
              const btn = document.getElementById('advanceStepBtn');
              if (!btn) return false;
              const rect = btn.getBoundingClientRect();
              const topEl = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
              return topEl === btn || btn.contains(topEl);
            }"""
        )
        if not advance_btn_visible:
            failures.append("結束目前步驟 button is covered/unreachable with only 1 active era")

        browser.close()

    return {
        "name": "single_era_phase_action_bar_still_reachable",
        "status": "passed" if not failures else "failed",
        "failures": failures,
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_three_simultaneous_eras(), run_single_era_no_overlap()]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Era HUD Row Clickable — Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 指揮中心／戰略地圖分頁上方的時代關卡提示列（`.hud-era-pill`）改為可點擊，",
        "  點擊直接叫出該時代的完整說明；四人局最多 3 個時代關卡同時生效時，各自獨立可點。",
        "- 連帶修正 `#phaseActionBar` 寫死 `top:90px` 蓋住多行 HUD 的既有 layout bug。",
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
