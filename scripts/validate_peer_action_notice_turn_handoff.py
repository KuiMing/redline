#!/usr/bin/env python3
"""Browser proof: peer-action notices close when the viewer's turn begins."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"
RECORD_DIR = ROOT / "docs" / "records" / "playtest-flow" / "peer-action-notice-turn-handoff"
OUT_JSON = RECORD_DIR / "PEER_ACTION_NOTICE_TURN_HANDOFF_VALIDATION.json"


def post_json(path: str, payload: dict[str, object]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json("/test/setup-victory-proof", {})
    console_errors: list[str] = []
    results: list[dict[str, object]] = []

    def record(name: str, ok: bool, detail: dict[str, object]) -> None:
        results.append({"name": name, "ok": bool(ok), "detail": detail})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until="networkidle",
        )
        page.wait_for_function("() => Boolean(window.lastGameState) && typeof renderPeerActionNotice === 'function'")
        page.evaluate(
            """() => {
                if (typeof closeEventReveal === 'function') closeEventReveal();
                document.getElementById('victoryModal').style.display = 'none';
                document.getElementById('victoryBadge').style.display = 'none';
                peerActionNoticeGameId = gameId;
                peerActionNoticeSeenLogLength = 0;
                peerActionNoticeMinimized = false;
                peerActionNoticeHasContent = false;
                closePeerActionNotice(0);
            }"""
        )

        players = setup["state"]["players"]
        green = next(player for player in players if player["id"] == setup["player_id"])
        red = next(player for player in players if player["id"] == setup["red_player_id"])
        peer_state = {
            "players": players,
            "current_player": red["name"],
            "action_log": [f"{red['name']} 使用了 合作談判"],
        }
        page.evaluate("state => renderPeerActionNotice(state)", peer_state)
        opened = page.evaluate(
            """() => ({
                display: getComputedStyle(document.getElementById('peerActionNotice')).display,
                player: document.getElementById('peerActionNoticePlayer').textContent,
                text: document.getElementById('peerActionNoticeText').textContent,
                hasImage: Boolean(document.querySelector('#peerActionNoticeArt img')),
            })"""
        )
        record(
            "peer_action_opens_full_notice",
            opened["display"] == "flex"
            and red["name"] in opened["player"]
            and "合作談判" in opened["text"]
            and opened["hasImage"],
            opened,
        )
        page.wait_for_timeout(400)
        page.screenshot(path=str(RECORD_DIR / "peer_action_notice_before_turn_handoff.png"))

        page.locator("#peerActionNoticeMinimizeBtn").click()
        minimized = page.evaluate(
            """() => ({
                minimized: document.getElementById('peerActionNotice').classList.contains('peer-action-notice-minimized'),
                display: getComputedStyle(document.getElementById('peerActionNotice')).display,
            })"""
        )
        record("notice_can_be_minimized_before_handoff", minimized["minimized"] and minimized["display"] == "flex", minimized)

        own_turn_state = {
            **peer_state,
            "current_player": green["name"],
            "action_log": [*peer_state["action_log"], f"{red['name']} 結束回合"],
        }
        page.evaluate("state => renderPeerActionNotice(state)", own_turn_state)
        closed_minimized = page.evaluate(
            """() => ({
                display: getComputedStyle(document.getElementById('peerActionNotice')).display,
                minimized: document.getElementById('peerActionNotice').classList.contains('peer-action-notice-minimized'),
                hasContent: peerActionNoticeHasContent,
                seen: peerActionNoticeSeenLogLength,
            })"""
        )
        record(
            "own_turn_closes_minimized_notice_and_consumes_log",
            closed_minimized["display"] == "none"
            and not closed_minimized["minimized"]
            and not closed_minimized["hasContent"]
            and closed_minimized["seen"] == 2,
            closed_minimized,
        )
        page.screenshot(path=str(RECORD_DIR / "peer_action_notice_after_turn_handoff.png"))

        page.evaluate("state => renderPeerActionNotice(state)", {**own_turn_state, "current_player": red["name"]})
        stale_hidden = page.evaluate("() => getComputedStyle(document.getElementById('peerActionNotice')).display")
        record("consumed_notice_does_not_replay_after_turn_moves_on", stale_hidden == "none", {"display": stale_hidden})

        fresh_peer_state = {
            **peer_state,
            "action_log": [*own_turn_state["action_log"], f"{red['name']} 使用了 分神"],
        }
        page.evaluate("state => renderPeerActionNotice(state)", fresh_peer_state)
        fresh_display = page.evaluate("() => getComputedStyle(document.getElementById('peerActionNotice')).display")
        record("later_fresh_peer_action_still_opens_notice", fresh_display == "flex", {"display": fresh_display})

        page.evaluate("state => renderPeerActionNotice(state)", {**fresh_peer_state, "current_player": green["name"]})
        full_closed = page.evaluate("() => getComputedStyle(document.getElementById('peerActionNotice')).display")
        record("own_turn_also_closes_full_size_notice", full_closed == "none", {"display": full_closed})

        browser.close()

    record("browser_console_has_no_errors", not console_errors, {"errors": console_errors})
    payload = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["ok"]),
            "failed": sum(1 for result in results if not result["ok"]),
        },
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
