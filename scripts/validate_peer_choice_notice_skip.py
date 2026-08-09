#!/usr/bin/env python3
"""Browser proof: 2026-08-09 使用者要求——武裝系列等卡牌會強制對方進入一個必須立即處理的
pending choice（例如選擇要棄掉哪張手牌）時，對方畫面應該直接看到選擇視窗，不該先被「其他
玩家動態」的大型轉播通知疊層蓋住、需要手動縮小通知才能操作。

修法：`static/app.js` `renderPeerActionNotice()` 原本只在 `state.pending_choice.type ===
'reaction_choice'`（取消反應）時才跳過通知；現在只要 `state.pending_choice.player_id` 是
自己，不論 choice 的 type/choice_key 是什麼（包含武裝系列的 `armed_target_discard`），一律
跳過通知直接讓玩家操作。
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
RECORD_DIR = ROOT / "docs" / "records" / "playtest-flow" / "peer-choice-notice-skip"
JSON_PATH = RECORD_DIR / "PEER_CHOICE_NOTICE_SKIP_VALIDATION.json"
MD_PATH = RECORD_DIR / "PEER_CHOICE_NOTICE_SKIP_VALIDATION.md"


def run_case(source_name: str) -> Dict[str, Any]:
    setup = requests.post(
        f"{BASE_URL}/test/setup-peer-choice-notice-proof",
        json={"source_name": source_name},
        timeout=10,
    ).json()
    failures: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors: List[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['viewer_player_id']}",
            wait_until="networkidle",
        )
        page.wait_for_function("() => Boolean(window.lastGameState)")
        page.wait_for_timeout(800)
        # 每次 test-setup 都會釘一個「歲月靜好」事件，前端會自動彈出事件放大檢視，跟這支
        # 驗證要測的通知/選擇視窗無關，先關掉才能看清楚底下的畫面（沿用既有 validator 手法）。
        page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
        page.wait_for_timeout(300)
        screenshot = RECORD_DIR / f"{source_name}-viewer-sees-choice-directly.png"
        page.screenshot(path=str(screenshot))

        peer_notice_visible = page.evaluate(
            "() => { const el = document.getElementById('peerActionNotice'); "
            "return el && getComputedStyle(el).display !== 'none'; }"
        )
        if peer_notice_visible:
            failures.append("peer action notice was shown despite the viewer having a pending choice to resolve")

        body_text = page.locator("body").inner_text()
        if source_name not in body_text or "棄掉任 1 張牌" not in body_text:
            failures.append(f"choice prompt for {source_name} not directly visible: {body_text[:300]!r}")

        if console_errors:
            failures.append(f"console errors: {console_errors}")

        browser.close()

    return {
        "name": f"{source_name}_viewer_goes_straight_to_choice",
        "status": "passed" if not failures else "failed",
        "failures": failures,
        "screenshot": str(screenshot.relative_to(ROOT)),
    }


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results = [
        run_case("武裝小隊"),
        run_case("武裝者"),
        run_case("武裝集團"),
    ]
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] != "passed"),
        "results": results,
    }
    JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Peer Choice Notice Skip — Validation",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['total']} total.",
        "",
        "## Scope",
        "- 對方（有 pending choice 要處理的玩家）畫面應直接顯示選擇視窗，不再被「其他玩家動態」",
        "  通知疊層擋住、需要先手動縮小通知才能操作。涵蓋武裝系列三張卡牌。",
        "",
    ]
    for r in results:
        lines.append(f"## {r['name']} — {r['status']}")
        lines.append("")
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
