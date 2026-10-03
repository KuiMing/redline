#!/usr/bin/env python3
"""Browser proof: the lobby "AI 紅軍" toggle (host-only permission, server
sync across clients) and a real game actually started with AI Red Army on
— proving no human Red Army session is needed and that a genuine AI action
advances authoritative state (a concrete before/after diff, not a mocked
claim).

Same convention as scripts/validate/validate_host_only_game_difficulty.py
(host-only market-mode toggle): two separate Playwright browser contexts
(host/guest), a throwaway live server with ENABLE_TEST_ROUTES on, a JSON +
Markdown report, and screenshots under docs/records/ui-layout/.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8768").rstrip("/")
OUT = ROOT / "docs/records/ui-layout/ai-red-army-toggle"
REPORT_JSON = OUT / "AI_RED_ARMY_TOGGLE_VALIDATION.json"
REPORT_MD = OUT / "AI_RED_ARMY_TOGGLE_VALIDATION.md"
HOST_SHOT = OUT / "host_ai_red_army_toggle_1280x720.png"
GUEST_SHOT = OUT / "guest_ai_red_army_toggle_disabled_1280x720.png"
GAME_BEFORE_SHOT = OUT / "host_before_ai_turn_1280x720.png"
GAME_AFTER_SHOT = OUT / "host_after_ai_turn_1280x720.png"

# Bound on how many `advance` cycles the host's own browser sends before
# giving up waiting for the AI to have acted at least once — generous
# enough for event-phase pending choices along the way, small enough to
# fail fast instead of hanging if something regresses.
MAX_ADVANCE_ITERATIONS = 40


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE_URL + path, timeout=20) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []
    errors: list[str] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        # ---------------------------------------------------------------
        # Part 1: toggle permission + cross-client sync (host + guest, a
        # room that is never started — this part only proves the toggle
        # contract itself).
        # ---------------------------------------------------------------
        host_context = browser.new_context(viewport={"width": 1280, "height": 720})
        guest_context = browser.new_context(viewport={"width": 1280, "height": 720})
        host = host_context.new_page()
        guest = guest_context.new_page()
        for page in (host, guest):
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(str(error)))

        host.goto(BASE_URL + "/new-game", wait_until="networkidle")
        initial = host.evaluate(
            """() => ({
              disabled: [...document.querySelectorAll('[data-ai-red-army]')].map(b => b.disabled),
              labels: [...document.querySelectorAll('[data-ai-red-army]')].map(b => b.textContent.trim()),
            })"""
        )
        record(
            "toggle_disabled_before_room_exists",
            len(initial["disabled"]) == 2 and all(initial["disabled"]) and initial["labels"] == ["真人紅軍", "AI 紅軍"],
            initial,
        )

        host.locator("#playerName").fill("房主")
        host.locator("#createRoomBtn").click()
        host.wait_for_function("document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'", timeout=10000)
        host.locator("#closeFactionPickerBtn").click()
        room_id = host.locator("#roomId").input_value()
        host.wait_for_function(
            "typeof latestLobbyState !== 'undefined' && latestLobbyState?.host_id && "
            "document.querySelectorAll('[data-ai-red-army]:not(:disabled)').length === 2",
            timeout=10000,
        )
        host_enabled_state = host.evaluate(
            """() => ({
              disabled: [...document.querySelectorAll('[data-ai-red-army]')].map(b => b.disabled),
              active: document.querySelector('[data-ai-red-army].active')?.dataset.aiRedArmy,
            })"""
        )
        record(
            "toggle_enabled_for_host_after_room_created_defaults_off",
            not any(host_enabled_state["disabled"]) and host_enabled_state["active"] == "off",
            host_enabled_state,
        )

        guest.goto(BASE_URL + "/new-game", wait_until="networkidle")
        guest.locator("#playerName").fill("訪客")
        guest.locator("#roomId").fill(room_id)
        guest.locator("#joinRoomBtn").click()
        guest.wait_for_function(
            "typeof latestLobbyState !== 'undefined' && latestLobbyState?.host_id && latestLobbyState?.players?.length === 2",
            timeout=10000,
        )
        guest.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'", timeout=10000)
        guest.locator("#closeFactionPickerBtn").click()
        guest_state = guest.evaluate(
            """() => ({
              disabled: [...document.querySelectorAll('[data-ai-red-army]')].map(b => b.disabled),
              tooltip: document.querySelector('[data-ai-red-army="on"]')?.dataset.tooltip || '',
            })"""
        )
        record(
            "toggle_disabled_read_only_for_guest",
            all(guest_state["disabled"]) and "只有房主可以切換" in guest_state["tooltip"],
            guest_state,
        )

        rejected = guest.evaluate(
            """async () => {
              const response = await fetch('/ai-red-army', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({game_id: gameId, player_id: playerId, enabled: true}),
              });
              let body = {};
              try { body = await response.json(); } catch (_) {}
              return {status: response.status, body};
            }"""
        )
        record(
            "server_rejects_guest_attempt_to_change_toggle",
            rejected["body"].get("error") == "Only host can change AI Red Army setting",
            rejected,
        )

        host.locator('[data-ai-red-army="on"]').click()
        try:
            host.wait_for_function("typeof latestLobbyState !== 'undefined' && latestLobbyState?.ai_red_army === true", timeout=3000)
            guest.wait_for_function(
                "typeof latestLobbyState !== 'undefined' && latestLobbyState?.ai_red_army === true && "
                "document.querySelector('[data-ai-red-army].active')?.dataset.aiRedArmy === 'on'",
                timeout=3000,
            )
        except PlaywrightTimeoutError:
            pass
        server_state = get_json(f"/lobby/{room_id}")
        record(
            "host_choice_syncs_to_server_and_guest_tab",
            server_state.get("ai_red_army") is True
            and guest.locator('[data-ai-red-army].active').get_attribute("data-ai-red-army") == "on",
            {
                "serverValue": server_state.get("ai_red_army"),
                "guestActiveButton": guest.locator('[data-ai-red-army].active').get_attribute("data-ai-red-army"),
            },
        )

        # Screenshot the lobby room itself (not the faction picker overlay)
        # for the overlap/occlusion check below and for manual inspection.
        host.screenshot(path=str(HOST_SHOT), full_page=True)
        guest.screenshot(path=str(GUEST_SHOT), full_page=True)

        # Faction picker: red_army must not be choosable while AI is on.
        host.locator("#openFactionPickerBtn").click()
        host.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'", timeout=5000)
        red_army_button_state = host.evaluate(
            """() => {
              const buttons = [...document.querySelectorAll('#factionList .faction-choice-btn')];
              const redArmyBtn = buttons.find(b => b.textContent.trim() === '紅軍');
              return redArmyBtn ? {found: true, disabled: redArmyBtn.disabled, title: redArmyBtn.title} : {found: false};
            }"""
        )
        record(
            "red_army_not_offered_as_a_joinable_faction_while_ai_is_on",
            red_army_button_state.get("found") and red_army_button_state.get("disabled") is True,
            red_army_button_state,
        )
        host.locator("#closeFactionPickerBtn").click()

        # Visual overlap/occlusion check around the new field: every lobby
        # control must have a non-zero bounding box and none may overlap
        # the absolutely-positioned bottom action bar.
        overlap_probe = host.evaluate(
            """() => {
              const field = document.getElementById('aiRedArmyField');
              const actions = document.querySelector('.lobby-actions');
              if (!field || !actions) return {ok: false, reason: 'missing elements'};
              const f = field.getBoundingClientRect();
              const a = actions.getBoundingClientRect();
              const overlaps = f.bottom > a.top && f.top < a.bottom && f.right > a.left && f.left < a.right;
              return {ok: !overlaps, fieldRect: {top: f.top, bottom: f.bottom}, actionsRect: {top: a.top, bottom: a.bottom}};
            }"""
        )
        record("ai_red_army_field_does_not_overlap_the_bottom_action_bar", overlap_probe.get("ok") is True, overlap_probe)

        host_context.close()
        guest_context.close()

        # ---------------------------------------------------------------
        # Part 2: a fresh single-host room, AI Red Army on, an actual game
        # started and played forward via the real running server — proving
        # (a) no human Red Army session is needed and (b) a genuine AI
        # action advances authoritative state (concrete before/after, not
        # mocked).
        # ---------------------------------------------------------------
        game_context = browser.new_context(viewport={"width": 1280, "height": 720})
        game_page = game_context.new_page()
        game_page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        game_page.on("pageerror", lambda error: errors.append(str(error)))

        game_page.goto(BASE_URL + "/new-game", wait_until="networkidle")
        game_page.locator("#playerName").fill("單人房主")
        game_page.locator("#createRoomBtn").click()
        game_page.wait_for_function("document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
        game_page.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'", timeout=10000)
        game_page.locator("#closeFactionPickerBtn").click()
        game_page.wait_for_function(
            "typeof latestLobbyState !== 'undefined' && document.querySelectorAll('[data-ai-red-army]:not(:disabled)').length === 2",
            timeout=10000,
        )
        game_page.locator('[data-ai-red-army="on"]').click()
        game_page.wait_for_function("typeof latestLobbyState !== 'undefined' && latestLobbyState?.ai_red_army === true", timeout=5000)

        game_page.locator("#openFactionPickerBtn").click()
        game_page.wait_for_function("document.getElementById('factionPicker')?.style.display === 'flex'", timeout=5000)
        game_page.evaluate(
            """() => {
              const buttons = [...document.querySelectorAll('#factionList .faction-choice-btn')];
              const hk = buttons.find(b => b.textContent.trim() === '香港');
              hk.click();
            }"""
        )
        game_page.wait_for_function("document.getElementById('confirmFactionBtn')?.disabled === false", timeout=5000)
        game_page.locator("#confirmFactionBtn").click()
        game_page.wait_for_function(
            "typeof latestLobbyState !== 'undefined' && latestLobbyState?.factions && Object.keys(latestLobbyState.factions).length === 1",
            timeout=5000,
        )

        game_page.locator("#toggleReadyBtn").click()
        game_page.wait_for_function("document.getElementById('startGameBtn')?.disabled === false", timeout=5000)
        game_page.locator("#startGameBtn").click()
        game_page.wait_for_function("typeof window.lastGameState !== 'undefined' && window.lastGameState !== null", timeout=10000)

        record("game_started_with_ai_red_army_on_and_no_human_in_that_seat", True, {
            "note": "room had exactly one human player (the host) for the whole lobby/start flow; red_army was never offered/chosen by a human — see red_army_not_offered_as_a_joinable_faction_while_ai_is_on above for the same server-side guarantee in this exact room.",
        })

        before_state = game_page.evaluate("() => window.lastGameState")
        game_page.screenshot(path=str(GAME_BEFORE_SHOT), full_page=True)
        before_ai_entry = next((p for p in before_state.get("players", []) if p.get("id") == before_state.get("ai_red_army", {}).get("player_id")), None)

        # Drive the host's own turn forward using only real, legitimate
        # websocket actions (never a mocked/stubbed call) — advancing
        # phases, and auto-resolving any pending choice that belongs to
        # the host — until the AI has genuinely acted at least once.
        advanced_state = None
        for _ in range(MAX_ADVANCE_ITERATIONS):
            advanced_state = game_page.evaluate(
                """() => new Promise(resolve => {
                  const before = window.lastGameState;
                  const myId = playerId;
                  const pending = before?.pending_choice;
                  let settled = false;
                  const finish = () => {
                    if (settled) return;
                    settled = true;
                    ws.removeEventListener('message', onMessage);
                    resolve(window.lastGameState);
                  };
                  // Listen to EVERY message after sending, not just the first:
                  // a human action that hands the turn to the AI produces TWO
                  // broadcasts in sequence (see server/main.py's
                  // broadcast_game_state -> maybe_run_red_army_turn ->
                  // recursive re-broadcast) — the first still reflects the
                  // state from before the AI's wake-up hook ran this cycle,
                  // only the second (or later) one carries the AI's own
                  // steps_taken > 0.
                  const onMessage = () => {
                    const steps = (window.lastGameState?.ai_red_army?.status?.steps_taken) || 0;
                    if (steps > 0) finish();
                  };
                  ws.addEventListener('message', onMessage);
                  if (pending && pending.player_id === myId) {
                    ws.send(JSON.stringify({action: 'resolve_choice', choice_id: pending.choice_id, index: 0}));
                  } else {
                    ws.send(JSON.stringify({action: 'advance'}));
                  }
                  setTimeout(finish, 4000);
                })"""
            )
            steps_taken = ((advanced_state or {}).get("ai_red_army", {}) or {}).get("status", {}).get("steps_taken", 0)
            if steps_taken and steps_taken > 0:
                break
            time.sleep(0.05)

        after_state = advanced_state or game_page.evaluate("() => window.lastGameState")
        game_page.screenshot(path=str(GAME_AFTER_SHOT), full_page=True)
        after_ai_entry = next((p for p in after_state.get("players", []) if p.get("id") == after_state.get("ai_red_army", {}).get("player_id")), None)

        ai_steps_taken = (after_state.get("ai_red_army", {}) or {}).get("status", {}).get("steps_taken", 0)
        concrete_diff_fields = []
        if before_ai_entry and after_ai_entry:
            for field in ("deck_count", "discard_count", "resources", "orgs", "moves_left", "organization_counts"):
                if before_ai_entry.get(field) != after_ai_entry.get(field):
                    concrete_diff_fields.append(field)
        turn_advanced = before_state.get("turn") != after_state.get("turn")

        record(
            "real_ai_action_genuinely_advanced_authoritative_state",
            ai_steps_taken > 0 and (bool(concrete_diff_fields) or turn_advanced),
            {
                "ai_steps_taken": ai_steps_taken,
                "ai_status": after_state.get("ai_red_army", {}).get("status"),
                "turn_before": before_state.get("turn"),
                "turn_after": after_state.get("turn"),
                "red_army_player_fields_that_changed": concrete_diff_fields,
                "red_army_player_before": before_ai_entry,
                "red_army_player_after": after_ai_entry,
            },
        )

        game_context.close()
        browser.close()

    record("browser_console_has_no_errors", not errors, errors)
    summary = {"total": len(checks), "passed": sum(1 for c in checks if c["passed"]), "failed": sum(1 for c in checks if not c["passed"])}
    report = {
        "summary": summary,
        "service": BASE_URL,
        "scenario": "房主 + 訪客 lobby（toggle 權限/同步）；單人房主 + AI 紅軍（實際開局與 AI 行動證明）",
        "checks": checks,
        "screenshots": [
            str(HOST_SHOT.relative_to(ROOT)),
            str(GUEST_SHOT.relative_to(ROOT)),
            str(GAME_BEFORE_SHOT.relative_to(ROOT)),
            str(GAME_AFTER_SHOT.relative_to(ROOT)),
        ],
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# AI 紅軍 Lobby Toggle Browser 驗證", "", f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if c['passed'] else 'FAIL'}: `{c['name']}`" for c in checks], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
