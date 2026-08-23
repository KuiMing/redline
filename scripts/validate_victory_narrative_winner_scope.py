#!/usr/bin/env python3
"""Browser proof：非紅軍勝利敘述只統計主獲勝方；紅軍殘部規則維持不變。"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/playtest-flow/victory-narrative-winner-scope"
JSON_PATH = OUT / "VICTORY_NARRATIVE_WINNER_SCOPE_VALIDATION.json"
MD_PATH = OUT / "VICTORY_NARRATIVE_WINNER_SCOPE_VALIDATION.md"
KAZAKH_SHOT = OUT / "kazakh_winner_only_totals_20260823.png"
RED_ANTI_SHOT = OUT / "red_victory_non_red_remnants_20260823.png"
RED_TRIUMPH_SHOT = OUT / "red_victory_triumph_non_red_totals_20260823.png"
NON_RED_FACTIONS = [
    "taiwan_green",
    "taiwan_blue",
    "hong_kong",
    "uyghur",
    "tibet",
    "manchuria",
    "mongol",
    "kazakh",
    "dian",
]


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-victory-proof", {"winner_name": "檢查者"})
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=victory-winner-scope-20260823",
            wait_until="networkidle",
        )
        page.wait_for_function("window.lastGameState && typeof victoryNarrativeOrganizationTotals === 'function'")
        page.evaluate("closeEventReveal?.()")

        matrix = page.evaluate(
            """factions => factions.map((faction, index) => {
              const winner = {
                id: `winner-${index}`, name: `勝者-${faction}`, faction,
                organization_counts: { total: 19, inside_wall: 3, outside_wall: 16 },
                resources: { money: 4, propaganda: 5 },
              };
              const red = {
                id: `red-${index}`, name: `紅軍-${index}`, faction: 'red_army',
                organization_counts: { total: 5, inside_wall: 2, outside_wall: 3 },
                resources: { money: 0, propaganda: 0 },
              };
              const coWinner = {
                id: `co-${index}`, name: `共同勝利者-${index}`, faction: 'hong_kong',
                organization_counts: { total: 15, inside_wall: 7, outside_wall: 8 },
                resources: { money: 1, propaganda: 2 },
              };
              const players = [winner, red, coWinner];
              const totals = victoryNarrativeOrganizationTotals(players, winner, faction);
              victoryModalDismissedFor = null;
              renderVictoryModal({
                turn: 21,
                winner: winner.name,
                co_winners: [coWinner.name],
                players,
              });
              return {
                faction,
                totals,
                body: document.getElementById('victoryEndingBody')?.textContent || '',
                coWinners: document.getElementById('victoryCoWinners')?.textContent || '',
                summary: document.getElementById('victorySummary')?.textContent || '',
              };
            })""",
            NON_RED_FACTIONS,
        )
        for item in matrix:
            record(
                f"{item['faction']}_narrative_uses_only_primary_winner",
                item["totals"] == {"insideWallTotal": 3, "outsideWallTotal": 16}
                and "共同勝利者" in item["coWinners"]
                and "組織 19" in item["summary"]
                and "組織 5" in item["summary"]
                and "組織 15" in item["summary"],
                item,
            )

        kazakh = next(item for item in matrix if item["faction"] == "kazakh")
        record(
            "kazakh_ui_text_is_3_inside_16_outside_not_aggregate",
            "牆內 3 個組織" in kazakh["body"]
            and "牆外 16 個力量" in kazakh["body"]
            and "牆內 12 個" not in kazakh["body"]
            and "牆外 27 個" not in kazakh["body"],
            {"body": kazakh["body"]},
        )
        page.evaluate(
            """() => {
              const winner = {
                id: 'kazakh-winner', name: '哈薩克', faction: 'kazakh',
                organization_counts: { total: 19, inside_wall: 3, outside_wall: 16 },
                resources: { money: 0, propaganda: 0 },
              };
              const red = {
                id: 'red-player', name: '紅軍', faction: 'red_army',
                organization_counts: { total: 5, inside_wall: 2, outside_wall: 3 },
                resources: { money: 0, propaganda: 0 },
              };
              const coWinner = {
                id: 'co-winner', name: '共同勝利者', faction: 'hong_kong',
                organization_counts: { total: 15, inside_wall: 7, outside_wall: 8 },
                resources: { money: 1, propaganda: 2 },
              };
              victoryModalDismissedFor = null;
              renderVictoryModal({
                turn: 21,
                winner: winner.name,
                co_winners: [coWinner.name],
                players: [winner, red, coWinner],
              });
            }"""
        )
        page.screenshot(path=str(KAZAKH_SHOT), full_page=True)

        red_result = page.evaluate(
            """viewerIsRed => {
              const red = {
                id: viewerIsRed ? window.playerId : 'synthetic-red', name: '紅軍', faction: 'red_army',
                organization_counts: { total: 22, inside_wall: 14, outside_wall: 8 },
                resources: { money: 0, propaganda: 0 },
              };
              const taiwan = {
                id: viewerIsRed ? 'synthetic-taiwan' : window.playerId, name: '臺灣', faction: 'taiwan_green',
                organization_counts: { total: 7, inside_wall: 3, outside_wall: 4 },
                resources: { money: 0, propaganda: 0 },
              };
              const hongKong = {
                id: 'synthetic-hong-kong', name: '香港', faction: 'hong_kong',
                organization_counts: { total: 3, inside_wall: 2, outside_wall: 1 },
                resources: { money: 0, propaganda: 0 },
              };
              const players = [red, taiwan, hongKong];
              const totals = victoryNarrativeOrganizationTotals(players, red, 'red_army');
              victoryModalDismissedFor = null;
              renderVictoryModal({ turn: 21, winner: 'red_army', co_winners: [], players });
              return {
                totals,
                title: document.getElementById('victoryEndingTitle')?.textContent || '',
                body: document.getElementById('victoryEndingBody')?.textContent || '',
                summary: document.getElementById('victorySummary')?.textContent || '',
              };
            }""",
            False,
        )
        record(
            "red_catastrophe_keeps_non_red_remnant_scope",
            red_result["totals"] == {"insideWallTotal": 5, "outsideWallTotal": 5}
            and red_result["title"] == "紅色鐵幕，籠罩天下"
            and "牆內組織僅剩 5 個" in red_result["body"]
            and "5 個殘部" in red_result["body"],
            red_result,
        )
        page.screenshot(path=str(RED_ANTI_SHOT), full_page=True)

        red_page = context.new_page()
        red_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        red_page.on("pageerror", lambda error: console_errors.append(str(error)))
        red_page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['red_player_id']}&v=victory-winner-scope-20260823",
            wait_until="networkidle",
        )
        red_page.wait_for_function("window.lastGameState && typeof victoryNarrativeOrganizationTotals === 'function'")
        red_page.evaluate("closeEventReveal?.()")
        red_view = red_page.evaluate(
            """() => {
              const red = {
                id: playerId, name: '紅軍', faction: 'red_army',
                organization_counts: { total: 22, inside_wall: 14, outside_wall: 8 }, resources: {},
              };
              const taiwan = {
                id: 'taiwan', name: '臺灣', faction: 'taiwan_green',
                organization_counts: { total: 7, inside_wall: 3, outside_wall: 4 }, resources: {},
              };
              const hongKong = {
                id: 'hong-kong', name: '香港', faction: 'hong_kong',
                organization_counts: { total: 3, inside_wall: 2, outside_wall: 1 }, resources: {},
              };
              const players = [red, taiwan, hongKong];
              victoryModalDismissedFor = null;
              renderVictoryModal({ turn: 21, winner: 'red_army', co_winners: [], players });
              return {
                totals: victoryNarrativeOrganizationTotals(players, red, 'red_army'),
                title: document.getElementById('victoryEndingTitle')?.textContent || '',
                body: document.getElementById('victoryEndingBody')?.textContent || '',
              };
            }"""
        )
        record(
            "red_triumph_keeps_same_non_red_totals",
            red_view["totals"] == {"insideWallTotal": 5, "outsideWallTotal": 5}
            and red_view["title"] == "赤旗遍寰宇，天下歸一統"
            and "牆內 5 個組織與牆外 5 個據點" in red_view["body"],
            red_view,
        )
        red_page.screenshot(path=str(RED_TRIUMPH_SHOT), full_page=True)
        browser.close()

    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
    }
    report = {
        "summary": summary,
        "service": BASE_URL,
        "scenario": "9 種非紅軍敘述＋共同勝利者＋紅軍雙視角；識別碼 [REDACTED]",
        "checks": checks,
        "screenshots": [
            str(KAZAKH_SHOT.relative_to(ROOT)),
            str(RED_ANTI_SHOT.relative_to(ROOT)),
            str(RED_TRIUMPH_SHOT.relative_to(ROOT)),
        ],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 勝利敘述主獲勝方統計範圍 Browser 驗證",
        "",
        f"Summary: **{summary['passed']}/{summary['total']} passed**",
        "",
        "- 非紅軍敘述只統計主獲勝方。",
        "- 共同勝利者不會默認加入主獲勝方的敘述數字。",
        "- 紅軍雙視角維持非紅軍殘部統計。",
        "- 識別碼均為 `[REDACTED]`。",
        "",
    ]
    for check in checks:
        lines.append(f"- {'PASS' if check['passed'] else 'FAIL'}: `{check['name']}`")
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
