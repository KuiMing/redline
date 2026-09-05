#!/usr/bin/env python3
import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
OUT = ROOT / "docs" / "records" / "ui-layout" / "no-top-notice-bar"
REPORT_JSON = OUT / "NO_TOP_NOTICE_BAR_VALIDATION.json"
RED_BASELINE_JSON = OUT / "NO_TOP_NOTICE_BAR_RED_BASELINE.json"
REPORT_MD = OUT / "NO_TOP_NOTICE_BAR_VALIDATION.md"
SCREENSHOT = OUT / "no_top_notice_bar_prompt_1280x720.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-faction-action-used-proof",
        {"faction_id": "aomen", "faction_action_used": True, "resource_card_name": "領導"},
    )
    checks = []
    console_errors = []
    dialogs = []

    def record(name: str, passed: bool, details=None) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.on("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.dismiss()))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}&v=no-top-notice-bar-20260905",
            wait_until="networkidle",
        )
        page.wait_for_function("window.lastGameState && document.getElementById('gameShell')")
        page.evaluate("closeEventReveal?.()")
        page.wait_for_timeout(150)

        absent = page.evaluate(
            "!document.getElementById('phaseActionBar') && !document.getElementById('phaseActionControls') && !document.getElementById('phaseActionNotice')"
        )
        record("top_notice_bar_dom_is_removed", absent)

        page.evaluate(
            """() => {
              const state = structuredClone(window.lastGameState);
              state.turn_phase = 'end';
              window.lastGameState = state;
              playHandCard(0, '領導', 'resource');
            }"""
        )
        invalid_play = page.evaluate(
            """() => ({
              visible: document.getElementById('unavailableActionModal')?.style.display === 'flex',
              title: document.getElementById('unavailableActionTitle')?.textContent.trim() || '',
              message: document.getElementById('unavailableActionMessage')?.textContent.trim() || '',
            })"""
        )
        record(
            "invalid_phase_card_play_uses_prompt_modal",
            invalid_play["visible"]
            and invalid_play["title"] == "無法打出手牌"
            and "行動階段已結束" in invalid_play["message"],
            invalid_play,
        )
        page.evaluate("closeUnavailableActionModal()")

        page.evaluate(
            """() => renderBusinessNetworkResult({
              pending_choice: null,
              last_action_result: {
                chosen_card: '交通經驗乙',
                purchase_index: 7,
                zone_label: '購買區槽位 8',
              },
            })"""
        )
        business = page.evaluate(
            """() => ({
              visible: document.getElementById('unavailableActionModal')?.style.display === 'flex',
              title: document.getElementById('unavailableActionTitle')?.textContent.trim() || '',
              message: document.getElementById('unavailableActionMessage')?.textContent.trim() || '',
            })"""
        )
        record(
            "business_network_result_uses_prompt_modal",
            business["visible"]
            and business["title"] == "企業人脈結果"
            and "交通經驗乙" in business["message"]
            and "槽位 8" in business["message"],
            business,
        )
        page.evaluate("closeUnavailableActionModal()")

        unrelated_purchase_index = page.evaluate(
            """() => {
              const result = renderBusinessNetworkResult({
                pending_choice: null,
                last_action_result: {purchase_index: 6, event_name: '貿易戰加劇'},
              });
              return {
                resultType: result.type,
                modalHidden: document.getElementById('unavailableActionModal')?.style.display === 'none',
              };
            }"""
        )
        record(
            "unrelated_purchase_index_is_not_business_network_result",
            unrelated_purchase_index["resultType"] == "idle" and unrelated_purchase_index["modalHidden"],
            unrelated_purchase_index,
        )

        generic_error = page.evaluate(
            """async () => {
              const state = structuredClone(window.lastGameState);
              state.error = 'This action is not available now';
              window.__noTopNoticeErrorState = state;
              await render(state);
              return {
                visible: document.getElementById('unavailableActionModal')?.style.display === 'flex',
                title: document.getElementById('unavailableActionTitle')?.textContent.trim() || '',
                message: document.getElementById('unavailableActionMessage')?.textContent.trim() || '',
              };
            }"""
        )
        record(
            "generic_player_error_uses_prompt_modal",
            generic_error["visible"]
            and generic_error["title"] == "操作提示"
            and bool(generic_error["message"]),
            generic_error,
        )
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        page.evaluate("closeUnavailableActionModal()")
        page.evaluate("render(window.__noTopNoticeErrorState)")
        page.wait_for_timeout(120)
        record(
            "closed_error_prompt_does_not_reopen_for_same_state",
            page.evaluate("document.getElementById('unavailableActionModal')?.style.display === 'none'"),
        )
        retry_attempt = page.evaluate(
            """async () => {
              if (typeof outboundActionSequence !== 'number') {
                return {sequenceAdvanced: false, sentCount: 0, modalVisible: false};
              }
              const originalSocket = ws;
              const sent = [];
              const before = outboundActionSequence;
              ws = {readyState: WebSocket.OPEN, send: message => sent.push(message)};
              sendAction('__no_top_notice_retry__');
              ws = originalSocket;
              await render(window.__noTopNoticeErrorState);
              return {
                sequenceAdvanced: outboundActionSequence === before + 1,
                sentCount: sent.length,
                modalVisible: document.getElementById('unavailableActionModal')?.style.display === 'flex',
              };
            }"""
        )
        page.wait_for_timeout(120)
        record(
            "new_action_attempt_can_show_same_error_again",
            retry_attempt["sequenceAdvanced"]
            and retry_attempt["sentCount"] == 1
            and retry_attempt["modalVisible"],
            retry_attempt,
        )
        page.evaluate("closeUnavailableActionModal()")

        queued_attempt = page.evaluate(
            """() => {
              if (typeof outboundActionSequence !== 'number') {
                return {
                  queuedOnce: false,
                  sequenceAdvancedOnce: false,
                  queueRestored: false,
                  sentCount: 0,
                };
              }
              const originalSocket = ws;
              const queuedBefore = pendingOutboundActions.length;
              const sequenceBefore = outboundActionSequence;
              const sent = [];
              ws = {readyState: WebSocket.CONNECTING};
              sendAction('__no_top_notice_queued__', {proof: true});
              const queuedAfterSend = pendingOutboundActions.length;
              const sequenceAfterSend = outboundActionSequence;
              ws = {readyState: WebSocket.OPEN, send: message => sent.push(message)};
              flushPendingOutboundActions();
              const result = {
                queuedOnce: queuedAfterSend === queuedBefore + 1,
                sequenceAdvancedOnce: sequenceAfterSend === sequenceBefore + 1
                  && outboundActionSequence === sequenceAfterSend,
                queueRestored: pendingOutboundActions.length === queuedBefore,
                sentCount: sent.length,
              };
              ws = originalSocket;
              return result;
            }"""
        )
        record(
            "queued_action_is_counted_once_across_flush",
            queued_attempt["queuedOnce"]
            and queued_attempt["sequenceAdvancedOnce"]
            and queued_attempt["queueRestored"]
            and queued_attempt["sentCount"] == 1,
            queued_attempt,
        )

        base_wait = page.evaluate(
            """async () => {
              const state = structuredClone(window.lastGameState);
              state.error = null;
              state.game_phase = 'base_selection';
              state.pending_base_choices = {};
              await render(state);
              return {
                meta: document.getElementById('phaseActionMeta')?.textContent.trim() || '',
                modalHidden: document.getElementById('unavailableActionModal')?.style.display === 'none',
                topNoticeBarAbsent: !document.getElementById('phaseActionBar')
                  && !document.getElementById('phaseActionNotice'),
              };
            }"""
        )
        record(
            "base_selection_wait_uses_phase_meta_not_notification",
            base_wait["meta"] == "等待其他玩家選擇根據地"
            and base_wait["modalHidden"]
            and base_wait["topNoticeBarAbsent"],
            base_wait,
        )

        for width, height in ((1280, 720), (1024, 768)):
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(100)
            layout = page.evaluate(
                """() => {
                  const hud = document.getElementById('hud').getBoundingClientRect();
                  const shell = document.getElementById('gameShell').getBoundingClientRect();
                  return {hudBottom:hud.bottom, shellTop:shell.top, topNoticeBarAbsent:!document.getElementById('phaseActionBar') && !document.getElementById('phaseActionNotice')};
                }"""
            )
            scale = width / 1280
            record(
                f"layout_has_no_secondary_row_{width}x{height}",
                layout["topNoticeBarAbsent"] and layout["shellTop"] <= layout["hudBottom"] + 10 * scale,
                layout,
            )

        browser.close()

    record("no_native_browser_dialogs", not dialogs, dialogs)
    record("browser_console_has_no_errors", not console_errors, console_errors)
    summary = {
        "total": len(checks),
        "passed": sum(check["passed"] for check in checks),
        "failed": sum(not check["passed"] for check in checks),
    }
    red_baseline = None
    if RED_BASELINE_JSON.exists() and os.environ.get("REDLINE_SKIP_RED_REFERENCE") != "1":
        baseline = json.loads(RED_BASELINE_JSON.read_text(encoding="utf-8"))
        red_baseline = {
            "summary": baseline.get("summary", {}),
            "failed_checks": [check["name"] for check in baseline.get("checks", []) if not check.get("passed")],
            "record": str(RED_BASELINE_JSON.relative_to(ROOT)),
        }
    report = {
        "summary": summary,
        "red_baseline": red_baseline,
        "service": BASE_URL,
        "checks": checks,
        "screenshots": [str(SCREENSHOT.relative_to(ROOT))],
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    red_lines = []
    if red_baseline:
        red_summary = red_baseline["summary"]
        red_lines = [
            f"RED baseline: **{red_summary.get('passed', 0)}/{red_summary.get('total', 0)} passed**",
            f"RED evidence: `{red_baseline['record']}`",
            "",
        ]
    REPORT_MD.write_text(
        "\n".join(
            [
                "# 移除頂部窄條通知 Browser 驗證",
                "",
                f"Summary: **{summary['passed']}/{summary['total']} passed**",
                "",
                *red_lines,
                *[f"- {'PASS' if check['passed'] else 'FAIL'} `{check['name']}`" for check in checks],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
