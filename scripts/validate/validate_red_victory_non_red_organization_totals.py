#!/usr/bin/env python3
"""Formal Browser proof for Red victory narrative organization totals."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8767").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "playtest-flow"
JSON_PATH = RECORD_DIR / "RED_VICTORY_NON_RED_ORGANIZATION_TOTALS_VALIDATION.json"
MD_PATH = RECORD_DIR / "RED_VICTORY_NON_RED_ORGANIZATION_TOTALS_VALIDATION.md"
ANTI_SHOT = RECORD_DIR / "red_victory_non_red_totals_anti_view_20260822.png"
RED_SHOT = RECORD_DIR / "red_victory_non_red_totals_red_view_20260822.png"


def post_json(path: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload or {}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def make_formal_game() -> tuple[dict, dict]:
    create = post_json("/create")
    join = post_json("/join", {"game_id": create["game_id"], "name": "臺灣"})
    for player_id, faction_id, base_name in [
        (create["host_id"], "red_army", "北京"),
        (join["player_id"], "taiwan_green", "臺北"),
    ]:
        chosen = post_json(
            "/choose-faction",
            {"game_id": create["game_id"], "player_id": player_id, "faction_id": faction_id, "base_name": base_name},
        )
        if chosen.get("error"):
            raise AssertionError(chosen)
        ready = post_json("/ready", {"game_id": create["game_id"], "player_id": player_id, "ready": True})
        if ready.get("error"):
            raise AssertionError(ready)
    started = post_json(
        "/start",
        {"game_id": create["game_id"], "player_id": create["host_id"], "market_mode": "sample_53"},
    )
    if started.get("error"):
        raise AssertionError(started)
    return (
        {"game_id": create["game_id"], "player_id": create["host_id"], "resume_token": create["resume_token"], "name": "紅軍"},
        {"game_id": create["game_id"], "player_id": join["player_id"], "resume_token": join["resume_token"], "name": "臺灣"},
    )


def open_session(page, session: dict) -> None:
    page.goto(BASE_URL + "/", wait_until="domcontentloaded")
    page.evaluate(
        """session => localStorage.setItem('redline.sessions.v1', JSON.stringify({
          [session.game_id]: {
            game_id: session.game_id,
            player_id: session.player_id,
            resume_token: session.resume_token,
            name: session.name,
            saved_at: Date.now(),
          },
        }))""",
        session,
    )
    page.goto(BASE_URL + "/?v=red-victory-non-red-orgs", wait_until="domcontentloaded")
    page.wait_for_function("window.lastGameState?.game_phase === 'main'", timeout=15000)


def render_scenario(page, red_id: str, taiwan_id: str, *, winner: str = "red_army", co_winners=None, zero_non_red=False) -> dict:
    return page.evaluate(
        """payload => {
          if (typeof closeEventReveal === 'function') closeEventReveal();
          if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
          document.getElementById('closeFactionActionModal')?.click();
          const nonRedInside = payload.zero_non_red ? 0 : 3;
          const nonRedOutside = payload.zero_non_red ? 0 : 4;
          const hongKongInside = payload.zero_non_red ? 0 : 2;
          const hongKongOutside = payload.zero_non_red ? 0 : 1;
          const state = {
            turn: 21,
            winner: payload.winner,
            co_winners: payload.co_winners || [],
            players: [
              {
                id: payload.red_id, name: '紅軍', faction: 'red_army',
                organization_counts: {total: 22, inside_wall: 14, outside_wall: 8},
                resources: {money: 0, propaganda: 0}, hand: [], deck_count: 0, discard_count: 0,
              },
              {
                id: payload.taiwan_id, name: '臺灣', faction: 'taiwan_green',
                organization_counts: {total: nonRedInside + nonRedOutside, inside_wall: nonRedInside, outside_wall: nonRedOutside},
                resources: {money: 0, propaganda: 0}, hand: [], deck_count: 0, discard_count: 0,
              },
              {
                id: 'synthetic-hong-kong', name: '香港', faction: 'hong_kong',
                organization_counts: {total: hongKongInside + hongKongOutside, inside_wall: hongKongInside, outside_wall: hongKongOutside},
                resources: {money: 0, propaganda: 0}, hand: [], deck_count: 0, discard_count: 0,
              },
            ],
          };
          victoryModalDismissedFor = null;
          renderVictoryModal(state);
          return {
            title: document.getElementById('victoryEndingTitle')?.textContent || '',
            body: document.getElementById('victoryEndingBody')?.textContent || '',
            coWinners: document.getElementById('victoryCoWinners')?.textContent || '',
            summary: document.getElementById('victorySummary')?.textContent || '',
          };
        }""",
        {
            "red_id": red_id,
            "taiwan_id": taiwan_id,
            "winner": winner,
            "co_winners": co_winners or [],
            "zero_non_red": zero_non_red,
        },
    )


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    red_session, taiwan_session = make_formal_game()
    checks: list[dict] = []
    console_errors: list[str] = []

    def record(name: str, passed: bool, details=None) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        anti_page = browser.new_page(viewport={"width": 1440, "height": 900})
        anti_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        anti_page.on("pageerror", lambda error: console_errors.append(str(error)))
        open_session(anti_page, taiwan_session)

        anti_view = render_scenario(
            anti_page,
            red_session["player_id"],
            taiwan_session["player_id"],
        )
        record(
            "anti_view_red_narrative_counts_only_non_red_organizations",
            "牆內組織僅剩 5 個" in anti_view["body"]
            and "5 個殘部倉皇退守牆外" in anti_view["body"]
            and "19 個" not in anti_view["body"]
            and "13 個" not in anti_view["body"],
            anti_view,
        )
        record(
            "summary_keeps_real_per_player_organization_counts",
            all(fragment in anti_view["summary"] for fragment in ["紅軍", "14", "8", "臺灣", "3", "4", "香港", "2", "1"]),
            anti_view["summary"],
        )
        co_view = render_scenario(
            anti_page,
            red_session["player_id"],
            taiwan_session["player_id"],
            co_winners=["香港"],
        )
        record(
            "co_winner_display_does_not_change_non_red_filter",
            "共同勝利者：香港" in co_view["coWinners"]
            and "牆內組織僅剩 5 個" in co_view["body"]
            and "5 個殘部倉皇退守牆外" in co_view["body"],
            co_view,
        )
        zero_view = render_scenario(
            anti_page,
            red_session["player_id"],
            taiwan_session["player_id"],
            zero_non_red=True,
        )
        record(
            "zero_non_red_organizations_render_as_zero",
            "牆內組織僅剩 0 個" in zero_view["body"] and "0 個殘部倉皇退守牆外" in zero_view["body"],
            zero_view,
        )
        non_red_win = render_scenario(
            anti_page,
            red_session["player_id"],
            taiwan_session["player_id"],
            winner="臺灣",
        )
        record(
            "non_red_winner_counts_only_primary_winner",
            "牆內 3 個組織" in non_red_win["body"]
            and "牆外 4 個" in non_red_win["body"]
            and "牆內 19 個組織" not in non_red_win["body"]
            and "牆外 13 個" not in non_red_win["body"],
            non_red_win,
        )
        render_scenario(anti_page, red_session["player_id"], taiwan_session["player_id"])
        anti_page.screenshot(path=str(ANTI_SHOT), full_page=True)

        red_page = browser.new_page(viewport={"width": 1440, "height": 900})
        red_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        red_page.on("pageerror", lambda error: console_errors.append(str(error)))
        open_session(red_page, red_session)
        red_view = render_scenario(
            red_page,
            red_session["player_id"],
            taiwan_session["player_id"],
        )
        record(
            "red_view_triumph_narrative_also_counts_only_non_red_organizations",
            "牆內 5 個組織與牆外 5 個據點" in red_view["body"]
            and "19 個" not in red_view["body"]
            and "13 個" not in red_view["body"],
            red_view,
        )
        red_page.screenshot(path=str(RED_SHOT), full_page=True)
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
        "session": "formal create/join/start/restore; credentials [REDACTED]",
        "checks": checks,
        "screenshots": [str(ANTI_SHOT.relative_to(ROOT)), str(RED_SHOT.relative_to(ROOT))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Red Victory Non-Red Organization Totals Validation",
        "",
        f"- Summary: {summary['passed']}/{summary['total']} passed",
        "- Session: formal create/join/start/restore; credentials `[REDACTED]`",
        "",
    ]
    lines.extend(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']}" for check in checks)
    lines.extend(["", f"- Anti view: `{ANTI_SHOT.relative_to(ROOT)}`", f"- Red view: `{RED_SHOT.relative_to(ROOT)}`"])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
