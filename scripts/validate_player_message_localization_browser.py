#!/usr/bin/env python3
"""Official-browser proof for player-visible zh-TW error localization."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000")
RECORD_DIR = BASE / "docs" / "records" / "player-message-localization"


def ensure_server():
    if not BASE_URL.startswith("http://127.0.0.1:"):
        return None
    host = "127.0.0.1"
    port = int(BASE_URL.rsplit(":", 1)[-1])
    sock = socket.socket()
    sock.settimeout(0.5)
    try:
        sock.connect((host, port))
        return None
    except OSError:
        pass
    finally:
        sock.close()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.main:app", "--host", host, "--port", str(port)],
        cwd=str(BASE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/server-info", timeout=1):
                return proc
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"server did not start on {BASE_URL}")


def post_json(path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))


def check(results: list[dict], name: str, passed: bool, detail: str) -> None:
    results.append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        raise AssertionError(f"{name}: {detail}")


def chromium_launch_options() -> dict:
    options: dict = {"headless": True}
    cache_root = Path.home() / "Library" / "Caches" / "ms-playwright"
    candidates = sorted(
        cache_root.glob("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"),
        reverse=True,
    )
    if candidates:
        options["executable_path"] = str(candidates[0])
    return options


def main() -> int:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    server = ensure_server()
    results: list[dict] = []
    console_errors: list[str] = []
    dialogs: list[str] = []
    lobby_shot = RECORD_DIR / "player-message-lobby-zh-tw.png"
    range_shot = RECORD_DIR / "player-message-range-error-zh-tw.png"
    map_shot = RECORD_DIR / "player-message-map-error-zh-tw.png"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**chromium_launch_options())
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            # REST/lobby boundary: a real missing room must render zh-TW in the official status UI.
            page.goto(BASE_URL + "/", wait_until="domcontentloaded")
            page.locator("#roomId").fill("missing-room-for-zh-tw-proof")
            page.locator("#playerName").fill("驗證玩家")
            page.locator("#joinRoomBtn").click()
            status = page.locator("#lobbyStatusHint")
            status.wait_for(state="visible", timeout=5000)
            page.wait_for_function(
                "document.getElementById('lobbyStatusHint')?.textContent?.includes('找不到遊戲房間')",
                timeout=5000,
            )
            lobby_text = status.inner_text().strip()
            check(results, "lobby_missing_game_is_zh_tw", lobby_text == "找不到遊戲房間。", lobby_text)
            check(results, "lobby_missing_game_has_no_raw_english", "Game not found" not in page.locator("body").inner_text(), lobby_text)
            page.screenshot(path=str(lobby_shot), full_page=True)

            # WebSocket/game boundary: reproduce the reported range rejection through a real spy card.
            setup = post_json("/test/setup-spy-proof", {
                "card_name": "派遣間諜",
                "player_name": "viewer",
                "enemy_name": "target",
                "orgs": {"北京": 1},
                "enemy_orgs": {"香港城": 1},
            })
            check(results, "range_setup_created", bool(setup.get("success")), "已建立 2 人 deterministic range fixture")
            prepared = post_json("/test/set-hand", {
                "game_id": setup["game_id"],
                "player_id": setup["player_id"],
                "cards": ["武裝者"],
                "turn_phase": "action",
                "set_current_player": True,
            })
            check(results, "range_card_prepared", prepared.get("hand") == ["武裝者"], "行動玩家手牌已固定為武裝者")

            def dismiss_dialog(dialog):
                dialogs.append(dialog.message)
                dialog.dismiss()

            page.on("dialog", dismiss_dialog)
            game_url = f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}"
            page.goto(game_url, wait_until="domcontentloaded")
            page.wait_for_function("window.lastGameState && window.lastGameState.players", timeout=15000)
            event_reveal = page.locator("#eventRevealModal")
            if event_reveal.is_visible():
                page.evaluate("typeof closeEventReveal === 'function' && closeEventReveal()")
            page.locator(".game-tab[data-view='map']").click()
            map_frame = page.frame_locator("#strategicMapFrame")
            map_frame.locator("#interactionHint").wait_for(state="visible", timeout=15000)
            page.locator(".game-tab[data-view='command']").click()
            action_button = page.locator(".hand-card").filter(has_text="武裝者").locator("button[data-card-mode='action']").first
            action_button.wait_for(state="visible", timeout=10000)
            action_button.click()
            page.wait_for_timeout(1500)
            range_notice = page.locator("#phaseActionNotice").inner_text().strip()
            runtime_error = page.evaluate("window.lastGameState?.error || ''")
            check(
                results,
                "reported_range_error_is_zh_tw",
                range_notice == "目標玩家在範圍內沒有組織。",
                json.dumps({"notice": range_notice, "dialogs": dialogs, "runtime_error": runtime_error}, ensure_ascii=False),
            )
            check(results, "reported_range_dialog_is_zh_tw", bool(dialogs) and dialogs[-1] == "目標玩家在範圍內沒有組織。", json.dumps(dialogs, ensure_ascii=False))
            body_text = page.locator("body").inner_text()
            check(results, "reported_range_error_has_no_raw_english", "Target player has no organization within range" not in body_text, range_notice)
            page.screenshot(path=str(range_shot), full_page=True)
            page.locator(".game-tab[data-view='map']").click()
            map_hint = map_frame.locator("#interactionHint")
            map_hint.wait_for(state="visible", timeout=5000)
            map_text = map_hint.inner_text().strip()
            check(results, "map_range_error_is_zh_tw", "目標玩家在範圍內沒有組織。" in map_text, map_text)
            check(results, "map_range_error_has_no_raw_english", "Target player has no organization within range" not in map_text, map_text)
            map_hint.scroll_into_view_if_needed()
            page.wait_for_timeout(150)
            page.screenshot(path=str(map_shot), full_page=True)
            browser.close()

        check(results, "browser_console_has_no_errors", not console_errors, json.dumps(console_errors, ensure_ascii=False))
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()

    report = {
        "status": "passed",
        "generated_at": datetime.now().astimezone().isoformat(),
        "base_url": BASE_URL,
        "checks_passed": sum(1 for result in results if result["passed"]),
        "checks_total": len(results),
        "results": results,
        "dialogs": dialogs,
        "console_errors": console_errors,
        "screenshots": [
            str(lobby_shot.relative_to(BASE)),
            str(range_shot.relative_to(BASE)),
            str(map_shot.relative_to(BASE)),
        ],
    }
    json_path = RECORD_DIR / "PLAYER_MESSAGE_LOCALIZATION_BROWSER_VALIDATION.json"
    md_path = RECORD_DIR / "PLAYER_MESSAGE_LOCALIZATION_BROWSER_VALIDATION.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_lines = [
        "# 玩家提示繁體中文化 Browser Validation",
        "",
        f"- 結果：**{report['checks_passed']}/{report['checks_total']} passed**",
        f"- 正式端點：`{BASE_URL}`",
        "- 情境：不存在房間的 REST error、武裝者範圍外目標的 WebSocket error。",
        "",
        "| 檢查 | 結果 | 證據 |",
        "|---|---:|---|",
    ]
    for result in results:
        md_lines.append(f"| `{result['name']}` | {'PASS' if result['passed'] else 'FAIL'} | {result['detail'].replace('|', '／')} |")
    md_lines += [
        "",
        "## Screenshots",
        "",
        f"- `{lobby_shot.relative_to(BASE)}`",
        f"- `{range_shot.relative_to(BASE)}`",
        f"- `{map_shot.relative_to(BASE)}`",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
