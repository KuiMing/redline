#!/usr/bin/env python3
"""Browser proof: up to three active era stages render as tabs, not pinned overlays."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8767").rstrip("/")
RECORD_DIR = ROOT / "docs" / "records" / "playtest-flow"
JSON_PATH = RECORD_DIR / "ERA_TABS_EVENT_CARD_LAYOUT_VALIDATION.json"
MD_PATH = RECORD_DIR / "ERA_TABS_EVENT_CARD_LAYOUT_VALIDATION.md"
WIDE_SHOT = RECORD_DIR / "three_era_tabs_clear_of_event_card_1280x720_20260820.png"
NARROW_SHOT = RECORD_DIR / "three_era_tabs_clear_of_event_card_1024x768_20260820.png"
ERA_IDS = ["hong_kong", "kazakh", "manchuria"]


def post_json(path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def make_formal_game() -> tuple[str, str, str]:
    create = post_json("/create")
    join = post_json("/join", {"game_id": create["game_id"], "name": "香港"})
    players = [
        (create["host_id"], "red_army", "北京"),
        (join["player_id"], "hong_kong", "香港城"),
    ]
    for player_id, faction_id, base_name in players:
        chosen = post_json(
            "/choose-faction",
            {
                "game_id": create["game_id"],
                "player_id": player_id,
                "faction_id": faction_id,
                "base_name": base_name,
            },
        )
        if chosen.get("error"):
            raise AssertionError(chosen)
        ready = post_json(
            "/ready",
            {"game_id": create["game_id"], "player_id": player_id, "ready": True},
        )
        if ready.get("error"):
            raise AssertionError(ready)
    started = post_json(
        "/start",
        {"game_id": create["game_id"], "player_id": create["host_id"], "market_mode": "sample_53"},
    )
    if started.get("error"):
        raise AssertionError(started)
    return create["game_id"], join["player_id"], join["resume_token"]


def open_authenticated_game(page, game_id: str, player_id: str, resume_token: str) -> None:
    page.goto(BASE_URL + "/", wait_until="domcontentloaded")
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
    page.goto(BASE_URL + "/?v=three-active-era-tabs", wait_until="domcontentloaded")
    page.wait_for_function(
        "window.lastGameState && window.lastGameState.active_era_details?.length === 3",
        timeout=15000,
    )
    page.wait_for_timeout(750)
    page.evaluate(
        """() => {
          closeEventReveal();
          minimizeEraAchievement();
          document.querySelector('#gameTabs [data-view="map"]')?.click();
        }"""
    )
    page.wait_for_function(
        "getComputedStyle(document.getElementById('eventCardTab')).display !== 'none'",
        timeout=10000,
    )
    page.wait_for_timeout(250)


def inspect_layout(page) -> dict:
    return page.evaluate(
        """() => {
          const toRect = element => {
            if (!element) return null;
            const box = element.getBoundingClientRect();
            return {
              left: box.left,
              top: box.top,
              right: box.right,
              bottom: box.bottom,
              width: box.width,
              height: box.height,
            };
          };
          const tabs = [...document.querySelectorAll('#activeEraTabs .era-stage-tab')].map(tab => ({
            id: tab.dataset.eraId || '',
            text: tab.textContent.trim(),
            title: tab.title,
            rect: toRect(tab),
          }));
          const tabBar = toRect(document.getElementById('gameTabs'));
          const eraGroup = toRect(document.getElementById('activeEraTabs'));
          const event = toRect(document.getElementById('eventCardTab'));
          const advance = toRect(document.getElementById('advanceStepBtn'));
          const overlaps = (a, b) => !!(a && b)
            && a.left < b.right
            && a.right > b.left
            && a.top < b.bottom
            && a.bottom > b.top;
          return {
            tabs,
            tabBar,
            eraGroup,
            event,
            advance,
            viewport: {width: innerWidth, height: innerHeight},
            eventTabOverlap: tabs.some(tab => overlaps(tab.rect, event)),
            oldPinnedNoticeCount: document.querySelectorAll('#eraPinnedNotice .era-pin-card').length,
            oldPinnedNoticeDisplay: (() => {
              const notice = document.getElementById('eraPinnedNotice');
              return notice ? getComputedStyle(notice).display : 'absent';
            })(),
            duplicateHudPillCount: document.querySelectorAll('.hud-era-pill').length,
          };
        }"""
    )


def layout_passes(data: dict) -> bool:
    tabs = data.get("tabs") or []
    tab_bar = data.get("tabBar")
    era_group = data.get("eraGroup")
    event = data.get("event")
    advance = data.get("advance")
    if len(tabs) != 3 or not tab_bar or not era_group or not event or not advance:
        return False
    return bool(
        [tab["id"] for tab in tabs] == ERA_IDS
        and all(tab["rect"]["left"] >= tab_bar["left"] and tab["rect"]["right"] <= tab_bar["right"] for tab in tabs)
        and era_group["right"] <= advance["left"] - 8
        and not data.get("eventTabOverlap")
        and event["left"] >= tab_bar["left"]
        and event["right"] <= tab_bar["right"]
        and event["top"] >= tab_bar["top"]
        and event["bottom"] <= tab_bar["bottom"]
        and data.get("oldPinnedNoticeCount") == 0
        and data.get("oldPinnedNoticeDisplay") in {"none", "absent"}
        and data.get("duplicateHudPillCount") == 0
    )


def verify_each_tab_opens_its_era(page) -> dict:
    results = []
    for era_id in ERA_IDS:
        tab = page.locator(f'#activeEraTabs .era-stage-tab[data-era-id="{era_id}"]')
        expected = tab.locator('.era-stage-tab-name').inner_text()
        tab.click()
        page.locator("#eraAchievementModal").wait_for(state="visible", timeout=5000)
        title = page.locator("#eraAchievementTitle").inner_text()
        results.append({"eraId": era_id, "tab": expected, "modalTitle": title, "matched": expected in title})
        page.evaluate("minimizeEraAchievement()")
    return {"results": results, "passed": all(item["matched"] for item in results)}


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    game_id, player_id, resume_token = make_formal_game()
    setup = post_json(
        "/test/setup-era-event-layout-proof",
        {"game_id": game_id, "era_ids": ERA_IDS, "event_name": "歲月靜好"},
    )
    if not setup.get("success"):
        raise AssertionError(setup)

    console_errors: list[str] = []
    checks: list[dict] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        open_authenticated_game(page, game_id, player_id, resume_token)

        wide = inspect_layout(page)
        wide_passed = layout_passes(wide)
        checks.append({"name": "three_active_eras_render_as_tabs_at_1280x720", "passed": wide_passed, "details": wide})
        opened = verify_each_tab_opens_its_era(page) if wide_passed else {"results": [], "passed": False, "reason": "era tabs are not available"}
        checks.append({"name": "each_era_tab_opens_its_matching_full_explanation", "passed": opened["passed"], "details": opened})
        page.screenshot(path=str(WIDE_SHOT), full_page=True)

        page.set_viewport_size({"width": 1024, "height": 768})
        page.wait_for_timeout(300)
        narrow = inspect_layout(page)
        checks.append({"name": "three_active_eras_render_as_tabs_at_1024x768", "passed": layout_passes(narrow), "details": narrow})
        page.screenshot(path=str(NARROW_SHOT), full_page=True)

        checks.append({"name": "browser_console_has_no_errors", "passed": not console_errors, "details": console_errors})
        browser.close()

    summary = {
        "total": len(checks),
        "passed": sum(1 for item in checks if item["passed"]),
        "failed": sum(1 for item in checks if not item["passed"]),
    }
    report = {
        "summary": summary,
        "checks": checks,
        "screenshots": [str(WIDE_SHOT.relative_to(ROOT)), str(NARROW_SHOT.relative_to(ROOT))],
    }
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Active Era Tabs and Event Card Layout Validation",
        "",
        f"Summary: {summary['passed']}/{summary['total']} passed",
        "",
        f"- Wide screenshot: `{WIDE_SHOT.relative_to(ROOT)}`",
        f"- Narrow screenshot: `{NARROW_SHOT.relative_to(ROOT)}`",
        "",
    ]
    for item in checks:
        lines.append(f"- {'PASS' if item['passed'] else 'FAIL'}: {item['name']}")
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
