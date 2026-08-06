#!/usr/bin/env python3
"""Browser proof for peer-action notice localization, handoff, and capped-log longevity."""

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
                peerActionNoticeLogSnapshot = [];
                peerActionNoticeMinimized = false;
                peerActionNoticeHasContent = false;
                closePeerActionNotice();
            }"""
        )

        players = setup["state"]["players"]
        green = next(player for player in players if player["id"] == setup["player_id"])
        red = next(player for player in players if player["id"] == setup["red_player_id"])
        peer_state = {
            "players": players,
            "current_player": red["name"],
            "action_log": [f"{red['name']} played 合作談判"],
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
            and opened["text"] == f"{red['name']} 使用了合作談判"
            and not any(word in opened["text"].lower() for word in ("played", "triggered", "drew", "gained"))
            and opened["hasImage"],
            opened,
        )

        translation_matrix = page.evaluate(
            """() => {
                const actor = { name: 'RED' };
                const playerNames = ['RED', 'GREEN'];
                const cases = [
                    ['RED played 合作談判', 'RED 使用了合作談判'],
                    ['RED triggered 統戰部 and drew 2 card(s)', 'RED 發動統戰部並抽了2張牌'],
                    ['RED built organization in 北京', 'RED 在北京建立了組織'],
                    ['RED moved 1 organization from 北京 to 天津 via road', 'RED 經由道路將1個組織從北京移到天津'],
                    ['RED bought 思想家', 'RED 購買了思想家'],
                    ['RED used 分神 to force GREEN to discard 追隨者', 'RED 使用分神迫使GREEN棄掉追隨者'],
                    ['RED reacted with 產業滲透 to cancel 合作談判', 'RED 打出產業滲透取消合作談判'],
                    ["RED's 合作談判 was canceled by reaction", 'RED 的合作談判被反應卡取消'],
                    ['RED may use 行動預告 before drawing new hand', 'RED 可在補充新手牌前使用行動預告'],
                    ['RED triggered 民主陣線 and gained a removed card proxy', 'RED 完成了一項行動'],
                    ['RED performed obscure backend action', 'RED 完成了一項行動'],
                ];
                return cases.map(([raw, expected]) => {
                    const actual = localizePeerActionNoticeText({ actor, text: raw, playerNames });
                    const residual = actual.replaceAll('RED', '').replaceAll('GREEN', '');
                    return { raw, expected, actual, noEnglish: !/[A-Za-z]{3,}/.test(residual), ok: actual === expected };
                });
            }"""
        )
        record(
            "peer_action_english_patterns_are_localized_to_traditional_chinese",
            all(item["ok"] and item["noEnglish"] for item in translation_matrix),
            {"cases": translation_matrix},
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
                snapshotLength: peerActionNoticeLogSnapshot.length,
            })"""
        )
        record(
            "own_turn_closes_minimized_notice_and_consumes_log",
            closed_minimized["display"] == "none"
            and not closed_minimized["minimized"]
            and not closed_minimized["hasContent"]
            and closed_minimized["snapshotLength"] == 2,
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

        capped_window = page.evaluate(
            """({ players, greenName, redName }) => {
                const overlay = document.getElementById('peerActionNotice');
                let logs = Array.from({ length: 100 }, (_, index) => `[Turn ${index + 1}] 系統紀錄 ${index + 1}`);
                renderPeerActionNotice({ players, current_player: greenName, action_log: logs });

                logs = [...logs.slice(1), `[Turn 101] ${redName} played 分神`];
                renderPeerActionNotice({ players, current_player: redName, action_log: logs });
                const firstSlide = {
                    display: getComputedStyle(overlay).display,
                    text: document.getElementById('peerActionNoticeText').textContent,
                    snapshotLength: peerActionNoticeLogSnapshot.length,
                };

                closePeerActionNotice();
                renderPeerActionNotice({ players, current_player: redName, action_log: logs });
                const identicalReplayDisplay = getComputedStyle(overlay).display;

                const misses = [];
                const texts = [];
                for (let index = 0; index < 30; index++) {
                    closePeerActionNotice();
                    const cardName = index % 2 ? '合作談判' : '分神';
                    logs = [...logs.slice(1), `[Turn ${102 + index}] ${redName} played ${cardName}`];
                    renderPeerActionNotice({ players, current_player: redName, action_log: logs });
                    const display = getComputedStyle(overlay).display;
                    const text = document.getElementById('peerActionNoticeText').textContent;
                    if (display !== 'flex') misses.push({ index, display, text });
                    texts.push(text);
                }
                return {
                    firstSlide,
                    identicalReplayDisplay,
                    misses,
                    finalText: texts.at(-1),
                    finalSnapshotLength: peerActionNoticeLogSnapshot.length,
                };
            }""",
            {"players": players, "greenName": green["name"], "redName": red["name"]},
        )
        record(
            "capped_100_entry_log_detects_same_length_sliding_window",
            capped_window["firstSlide"]["display"] == "flex"
            and capped_window["firstSlide"]["text"] == f"{red['name']} 使用了分神"
            and capped_window["firstSlide"]["snapshotLength"] == 100,
            capped_window["firstSlide"],
        )
        record(
            "identical_capped_log_state_does_not_replay_notice",
            capped_window["identicalReplayDisplay"] == "none",
            {"display": capped_window["identicalReplayDisplay"]},
        )
        record(
            "peer_notice_survives_30_consecutive_capped_log_slides",
            not capped_window["misses"]
            and capped_window["finalSnapshotLength"] == 100
            and capped_window["finalText"] == f"{red['name']} 使用了合作談判",
            capped_window,
        )

        page.set_viewport_size({"width": 390, "height": 844})
        mobile_state = page.evaluate(
            """({ players, greenName, redName }) => {
                const baseline = Array.from({ length: 100 }, (_, index) => `[Turn ${index + 201}] 系統紀錄 ${index + 201}`);
                renderPeerActionNotice({ players, current_player: greenName, action_log: baseline });
                const logs = [...baseline.slice(1), `[Turn 301] ${redName} played 合作談判`];
                renderPeerActionNotice({ players, current_player: redName, action_log: logs });
                return { snapshotLength: peerActionNoticeLogSnapshot.length };
            }""",
            {"players": players, "greenName": green["name"], "redName": red["name"]},
        )
        page.wait_for_timeout(400)
        mobile_notice = page.evaluate(
            """() => {
                const overlay = document.getElementById('peerActionNotice');
                const card = overlay.querySelector('.peer-action-notice-card');
                const image = overlay.querySelector('img');
                const rect = card.getBoundingClientRect();
                return {
                    display: getComputedStyle(overlay).display,
                    text: document.getElementById('peerActionNoticeText').textContent,
                    imageLoaded: Boolean(image && image.complete && image.naturalWidth > 0),
                    withinViewport: rect.left >= 0 && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight,
                };
            }"""
        )
        record(
            "mobile_capped_log_notice_is_visible_with_loaded_card_art",
            mobile_state["snapshotLength"] == 100
            and mobile_notice["display"] == "flex"
            and mobile_notice["text"] == f"{red['name']} 使用了合作談判"
            and mobile_notice["imageLoaded"]
            and mobile_notice["withinViewport"],
            {**mobile_state, **mobile_notice},
        )
        page.screenshot(path=str(RECORD_DIR / "peer_action_notice_capped_log_mobile.png"))

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
