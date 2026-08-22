#!/usr/bin/env python3
"""Live-service Browser proof for active-era tabs using a formal restored session.

This validator does not require a test setup endpoint on the running backend. It waits
for the formal WebSocket state, then renders a deterministic three-era client scenario
through the deployed production render functions.
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

import validate_era_tabs_event_card_layout as base

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "playtest-flow"
JSON_PATH = RECORD_DIR / "LIVE_ERA_TABS_FORMAL_SESSION_VALIDATION.json"
MD_PATH = RECORD_DIR / "LIVE_ERA_TABS_FORMAL_SESSION_VALIDATION.md"
WIDE_SHOT = RECORD_DIR / "live_three_era_tabs_1280x720_20260822.png"
NARROW_SHOT = RECORD_DIR / "live_three_era_tabs_1024x768_20260822.png"


def open_formal_session(page, game_id: str, player_id: str, resume_token: str) -> None:
    page.goto(base.BASE_URL + "/", wait_until="domcontentloaded")
    page.evaluate(
        """session => {
          localStorage.setItem('redline.sessions.v1', JSON.stringify({
            [session.game_id]: {
              game_id: session.game_id,
              player_id: session.player_id,
              resume_token: session.resume_token,
              name: '香港',
              saved_at: Date.now(),
            },
          }));
        }""",
        {"game_id": game_id, "player_id": player_id, "resume_token": resume_token},
    )
    page.goto(base.BASE_URL + "/?v=live-era-tabs-formal-session-20260822", wait_until="domcontentloaded")
    page.wait_for_function("window.lastGameState && window.lastGameState.game_phase === 'main'", timeout=15000)
    page.wait_for_timeout(1000)


def install_three_era_scenario(page) -> None:
    page.evaluate(
        """() => {
          const state = structuredClone(window.lastGameState);
          const eras = [
            {
              id: 'hong_kong', name: '[香港]香港人被自殺', summary_text: '香港時代關卡',
              trigger_text: '香港條件已達成', success_text: '香港紅色壓制', fail_text: '香港革命反撲',
              duration_text: '持續 2 回合', remaining: 2, duration: {type: 'turns', value: 2}, effects: {},
            },
            {
              id: 'kazakh', name: '[哈薩克]伊塔事件', summary_text: '哈薩克時代關卡',
              trigger_text: '哈薩克條件已達成', success_text: '哈薩克紅色壓制', fail_text: '哈薩克革命反撲',
              duration_text: '持續至遊戲結束', remaining: null, duration: {type: 'permanent'}, effects: {},
            },
            {
              id: 'manchuria', name: '[滿洲]滿洲地方派系凝聚', summary_text: '滿洲時代關卡',
              trigger_text: '滿洲條件已達成', success_text: '滿洲紅色壓制', fail_text: '滿洲革命反撲',
              duration_text: '持續 1 回合', remaining: 1, duration: {type: 'turns', value: 1}, effects: {},
            },
          ];
          state.active_era_details = eras;
          state.active_eras = eras.map(item => item.id);
          state.era_notification = structuredClone(eras[0]);
          state.current_event = {
            id: 'quiet_times', name: '歲月靜好', type: 'idle', trigger: {}, success: {}, failure: {}, effect: {},
            progress: {count: 0, required: 0, succeeded: true, settled: true, status: 'idle'},
            status: 'idle', result_text: '本次事件無效果', trigger_text: '無', success_text: '無',
            failure_text: '無', effect_text: '無',
          };
          window.lastGameState = state;
          renderCurrentEvent(state);
          closeEventReveal();
          renderEraAchievement(state);
          minimizeEraAchievement();
          document.querySelector('#gameTabs [data-view="map"]')?.click();
        }"""
    )
    page.wait_for_function("document.querySelectorAll('#activeEraTabs .era-stage-tab').length === 3", timeout=5000)
    page.wait_for_function(
        "document.querySelector('#eventCardPanel .event-card-art-image')?.naturalWidth === 1350",
        timeout=10000,
    )


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    game_id, player_id, resume_token = base.make_formal_game()
    console_errors: list[str] = []
    checks: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        open_formal_session(page, game_id, player_id, resume_token)
        install_three_era_scenario(page)

        wide = base.inspect_layout(page)
        wide_passed = base.layout_passes(wide)
        checks.append({"name": "live_service_three_tabs_at_1280x720", "passed": wide_passed, "details": wide})
        opened = base.verify_each_tab_opens_its_era(page) if wide_passed else {"results": [], "passed": False}
        checks.append({"name": "live_service_each_tab_opens_matching_era", "passed": opened["passed"], "details": opened})
        page.screenshot(path=str(WIDE_SHOT), full_page=True)

        page.set_viewport_size({"width": 1024, "height": 768})
        page.wait_for_timeout(300)
        install_three_era_scenario(page)
        narrow = base.inspect_layout(page)
        checks.append({"name": "live_service_three_tabs_at_1024x768", "passed": base.layout_passes(narrow), "details": narrow})
        page.screenshot(path=str(NARROW_SHOT), full_page=True)
        checks.append({"name": "live_service_console_has_no_errors", "passed": not console_errors, "details": console_errors})
        browser.close()

    summary = {
        "total": len(checks),
        "passed": sum(1 for item in checks if item["passed"]),
        "failed": sum(1 for item in checks if not item["passed"]),
    }
    report = {
        "summary": summary,
        "service": base.BASE_URL,
        "session": "formal create/join/start/restore; credentials [REDACTED]",
        "checks": checks,
        "screenshots": [str(WIDE_SHOT.relative_to(ROOT)), str(NARROW_SHOT.relative_to(ROOT))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Live Active Era Tabs Formal Session Validation",
        "",
        f"- Service: `{base.BASE_URL}`",
        "- Session: formal create/join/start/restore; credentials `[REDACTED]`",
        f"- Summary: {summary['passed']}/{summary['total']} passed",
        "",
    ]
    lines.extend(f"- {'PASS' if item['passed'] else 'FAIL'}: {item['name']}" for item in checks)
    lines.extend(["", f"- Wide screenshot: `{WIDE_SHOT.relative_to(ROOT)}`", f"- Narrow screenshot: `{NARROW_SHOT.relative_to(ROOT)}`"])
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
