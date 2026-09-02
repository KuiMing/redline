#!/usr/bin/env python3
"""Browser proof：勝利摘要放大文字並在短／長／多人內容下保持完整。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/victory-summary-text-density"
REPORT_JSON = OUT / "VICTORY_SUMMARY_TEXT_DENSITY_VALIDATION.json"
REPORT_MD = OUT / "VICTORY_SUMMARY_TEXT_DENSITY_VALIDATION.md"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-victory-proof", {"winner_name": "GREEN", "co_winners": []})
    checks: list[dict] = []
    console_errors: list[str] = []
    screenshots: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=victory-summary-density-proof", wait_until="networkidle")
        page.wait_for_function("window.lastGameState && typeof renderVictoryModal === 'function'", timeout=15000)
        page.evaluate("closeEventReveal?.()")

        scenarios = ("two_player", "long_copy", "many_players")
        for width, height in ((1280, 720), (1024, 768)):
            page.set_viewport_size({"width": width, "height": height})
            for scenario in scenarios:
                page.evaluate(
                    """scenario => {
                      victoryModalDismissedFor = null;
                      const state = structuredClone(window.lastGameState);
                      const winner = state.players.find(player => player.name === 'GREEN') || state.players[0];
                      winner.faction = 'manchuria';
                      state.winner = winner.name;
                      state.co_winners = [];
                      if (scenario === 'long_copy') {
                        winner.faction = 'rebel';
                        state.winner = winner.name;
                      }
                      if (scenario === 'many_players') {
                        const factions = ['hong_kong','uyghur','tibet','mongol'];
                        factions.forEach((faction, index) => {
                          state.players.push({
                            ...structuredClone(winner),
                            id:`synthetic-${index}`,
                            name:`玩家${index + 3}`,
                            faction,
                            resources:{money:index + 1, propaganda:index + 2},
                            orgs:{},
                            organization_counts:{total:index + 2, inside_wall:index, outside_wall:2},
                          });
                        });
                      }
                      renderVictoryModal(state);
                      closeEventReveal?.();
                    }""",
                    scenario,
                )
                page.wait_for_function("document.getElementById('victoryModal')?.style.display === 'flex'")
                page.wait_for_timeout(180)
                measurement = page.evaluate(
                    """() => {
                      const rect = el => { const r=el.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height}; };
                      const glass=document.querySelector('.victory-glass');
                      const title=document.getElementById('victoryTitle');
                      const subtitle=document.getElementById('victorySubtitle');
                      const endingTitle=document.getElementById('victoryEndingTitle');
                      const endingBody=document.getElementById('victoryEndingBody');
                      const summary=document.getElementById('victorySummary');
                      const rows=[...document.querySelectorAll('.victory-summary-row:not(.header)')];
                      const header=document.querySelector('.victory-summary-row.header');
                      const button=document.getElementById('victoryMinimizeBtn');
                      const image=document.getElementById('victoryEndingArt');
                      const overlay=document.getElementById('victoryModal');
                      const clippedElements=[title,subtitle,endingTitle,endingBody,header,...rows,button].filter(Boolean).filter(el => { const style=getComputedStyle(el); const clipsX=['hidden','clip'].includes(style.overflowX); const clipsY=['hidden','clip'].includes(style.overflowY); return (clipsX && el.scrollWidth > el.clientWidth + 1) || (clipsY && el.scrollHeight > el.clientHeight + 1); }).map(el => ({id:el.id,className:el.className,text:el.textContent.trim(),client:[el.clientWidth,el.clientHeight],scroll:[el.scrollWidth,el.scrollHeight]}));
                      return {
                        glass:rect(glass), overlay:rect(overlay), image:rect(image), summary:rect(summary), button:rect(button),
                        glassClientHeight:glass.clientHeight, glassScrollHeight:glass.scrollHeight, overflowY:getComputedStyle(glass).overflowY,
                        classes:[...glass.classList], rowCount:rows.length,
                        fonts:{title:parseFloat(getComputedStyle(title).fontSize),subtitle:parseFloat(getComputedStyle(subtitle).fontSize),endingTitle:parseFloat(getComputedStyle(endingTitle).fontSize),endingBody:parseFloat(getComputedStyle(endingBody).fontSize),row:parseFloat(getComputedStyle(rows[0]).fontSize),header:parseFloat(getComputedStyle(header).fontSize),button:parseFloat(getComputedStyle(button).fontSize)},
                        rowHeights:rows.map(row => rect(row).height), clippedElements,
                      };
                    }"""
                )
                scale = measurement["overlay"]["width"] / 1280
                inside = measurement["glass"]["left"] >= measurement["overlay"]["left"] and measurement["glass"]["right"] <= measurement["overlay"]["right"] and measurement["glass"]["top"] >= measurement["overlay"]["top"] and measurement["glass"]["bottom"] <= measurement["overlay"]["bottom"] + 1
                button_inside = measurement["button"]["left"] >= measurement["glass"]["left"] and measurement["button"]["right"] <= measurement["glass"]["right"] and measurement["button"]["top"] >= measurement["glass"]["top"] and measurement["button"]["bottom"] <= measurement["glass"]["bottom"] + 1
                readable = measurement["fonts"]["title"] >= 24 and measurement["fonts"]["subtitle"] >= 14 and measurement["fonts"]["endingTitle"] >= 16 and measurement["fonts"]["endingBody"] >= (13 if scenario == "long_copy" else 14) and measurement["fonts"]["row"] >= (12 if scenario == "many_players" else 14)
                accessible_overflow = measurement["glassScrollHeight"] <= measurement["glassClientHeight"] + 1 or measurement["overflowY"] in {"auto", "scroll"}
                expected_class = (scenario != "many_players" or "victory-summary-many-players" in measurement["classes"]) and (scenario != "long_copy" or "victory-ending-copy-long" in measurement["classes"])
                record(f"{scenario}_{width}x{height}_uses_larger_readable_type", readable, {"fonts": measurement["fonts"], "scale": scale})
                record(f"{scenario}_{width}x{height}_content_stays_available_inside_panel", inside and button_inside and not measurement["clippedElements"] and accessible_overflow and expected_class, measurement)

                if scenario == "two_player":
                    density = measurement["summary"]["height"] / max(1, measurement["glass"]["height"])
                    record(f"two_player_{width}x{height}_summary_uses_panel_height", density >= 0.72 and min(measurement["rowHeights"]) >= 44 * scale - 1, {"density": density, "summary": measurement["summary"], "glass": measurement["glass"], "rowHeights": measurement["rowHeights"], "scale": scale})
                    screenshot = OUT / f"victory_summary_text_density_{width}x{height}_20260823.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    screenshots.append(str(screenshot.relative_to(ROOT)))

        record("browser_console_has_no_errors", not console_errors, console_errors)
        browser.close()

    summary = {"total": len(checks), "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks)}
    report = {"summary": summary, "base_url": BASE_URL, "checks": checks, "screenshots": screenshots, "identifiers": "[REDACTED]"}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 勝利摘要文字與資訊密度驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`" for check in checks], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
