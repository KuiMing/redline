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

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000")
RECORD_DIR = BASE / "docs" / "records" / "action-cards"
BUILD_CARDS = {
    "宣傳家": {"builds": 1, "moves": 1},
    "思想家": {"builds": 1, "moves": 3},
    "組織經驗丙": {"builds": 1, "moves": 0},
    "組織經驗乙": {"builds": 2, "moves": 0},
    "組織經驗甲": {"builds": 1, "moves": 0},
}


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
        sock = socket.socket()
        sock.settimeout(0.5)
        try:
            sock.connect((host, port))
            sock.close()
            return proc
        except OSError:
            sock.close()
            time.sleep(0.25)
    raise RuntimeError(f"server did not start on {BASE_URL}")


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))


def make_formal_game():
    create = post_json("/create")
    game_id = create["game_id"]
    host_id = create["host_id"]
    players = [
        ("host", host_id, "red_army", "北京"),
        ("hk", post_json("/join", {"game_id": game_id, "name": "hk"})["player_id"], "hong_kong", "香港城"),
        ("tibet", post_json("/join", {"game_id": game_id, "name": "tibet"})["player_id"], "tibet_dharamsala", "達蘭薩拉"),
        ("uyghur", post_json("/join", {"game_id": game_id, "name": "uyghur"})["player_id"], "uyghur_munich", "慕尼黑"),
    ]
    for name, pid, faction_id, base_name in players:
        result = post_json("/choose-faction", {
            "game_id": game_id,
            "player_id": pid,
            "faction_id": faction_id,
            "base_name": base_name,
        })
        if result.get("error"):
            raise AssertionError(f"choose {name}: {result}")
        ready = post_json("/ready", {"game_id": game_id, "player_id": pid, "ready": True})
        if ready.get("error"):
            raise AssertionError(f"ready {name}: {ready}")
    start = post_json("/start", {"game_id": game_id, "player_id": host_id, "market_mode": "sample_53"})
    if start.get("error"):
        raise AssertionError(start)
    return game_id, {name: pid for name, pid, *_ in players}


def wait_state(page):
    page.wait_for_function("window.lastGameState && window.lastGameState.players && window.lastGameState.players.length >= 2", timeout=15000)
    page.wait_for_timeout(300)
    return page.evaluate("window.lastGameState")


def hk_from(state, player_id):
    return next(player for player in state["players"] if player["id"] == player_id)


def org_count(player):
    return sum(int(v or 0) for v in (player.get("orgs") or {}).values())


def strategic_frame(page):
    page.wait_for_selector("#strategicMapFrame[src*='leaflet_game_map']", timeout=15000)
    handle = page.locator("#strategicMapFrame").element_handle(timeout=5000)
    frame = handle.content_frame()
    frame.wait_for_function("window.__selectTownForTest && window.lastGameState", timeout=15000)
    return frame


def choose_build_town_via_map(page, preferred=None):
    frame = strategic_frame(page)
    choice = page.evaluate("window.lastGameState.pending_choice")
    towns = [entry["town"] for entry in choice.get("towns", []) if entry.get("town")]
    if not towns:
        raise AssertionError("pending card build choice has no town list")
    target = preferred if preferred in towns else next((town for town in towns if town != "香港城"), towns[0])
    selected = frame.evaluate("town => window.__selectTownForTest(town)", target)
    if not selected.get("ok"):
        raise AssertionError({"select_failed": selected, "target": target, "towns": towns})
    button_state = frame.locator("#directBuildBtn").evaluate("btn => ({text: btn.textContent, disabled: btn.disabled, title: btn.title || ''})")
    if button_state["disabled"]:
        raise AssertionError({"disabled_effect_build_button": button_state, "target": target, "choice": choice})
    frame.locator("#directBuildBtn").click(timeout=5000)
    page.wait_for_timeout(700)
    return {
        "target": target,
        "select_result": selected,
        "button_state_before_click": button_state,
        "map_hint": frame.locator("#interactionHint").inner_text(timeout=5000),
    }


def validate_card(page, game_id, player_id, card_name, expected, screenshot_dir, stamp):
    prepared = post_json("/test/set-hand", {
        "game_id": game_id,
        "player_id": player_id,
        "cards": [card_name],
        "turn_phase": "action",
        "set_current_player": True,
    })
    if prepared.get("error"):
        raise AssertionError(prepared)
    url = f"{BASE_URL}/?game_id={game_id}&player_id={player_id}&v=card-build-browser-{stamp}-{card_name}"
    page.goto(url, wait_until="domcontentloaded")
    state_before = wait_state(page)
    before_hk = hk_from(state_before, player_id)
    before_orgs = org_count(before_hk)
    action_button = page.locator(".hand-card").filter(has_text=card_name).locator("button[data-card-mode='action']").first
    action_button.wait_for(state="visible", timeout=10000)
    action_disabled_before = action_button.evaluate("btn => btn.disabled")
    action_title_before = action_button.evaluate("btn => btn.title || ''")
    if action_disabled_before:
        raise AssertionError({"card": card_name, "action_disabled_before": True, "title": action_title_before})
    action_button.click(timeout=5000)
    page.wait_for_function("window.lastGameState && window.lastGameState.pending_choice && window.lastGameState.pending_choice.choice_key === 'card_build_organization'", timeout=15000)
    page.wait_for_function("document.querySelector('#strategicMapFrame') && document.querySelector('#strategicMapFrame').src.includes('leaflet_game_map')", timeout=15000)
    state_after_action = page.evaluate("window.lastGameState")
    prompt_screenshot = None
    if card_name == "宣傳家":
        prompt_screenshot = screenshot_dir / "01_propagandist_after_action_map_prompt.png"
        page.screenshot(path=str(prompt_screenshot), full_page=True)
    map_resolutions = []
    for build_index in range(expected["builds"]):
        state = page.evaluate("window.lastGameState")
        choice = state.get("pending_choice") or {}
        if choice.get("choice_key") != "card_build_organization":
            raise AssertionError({"card": card_name, "build_index": build_index, "pending_choice": choice})
        map_resolutions.append(choose_build_town_via_map(page))
        if build_index < expected["builds"] - 1:
            page.wait_for_function("window.lastGameState && window.lastGameState.pending_choice && window.lastGameState.pending_choice.choice_key === 'card_build_organization'", timeout=15000)
    page.wait_for_function("window.lastGameState && !window.lastGameState.pending_choice", timeout=15000)
    final_state = page.evaluate("window.lastGameState")
    final_hk = hk_from(final_state, player_id)
    final_orgs = org_count(final_hk)
    final_screenshot = None
    if card_name == "宣傳家":
        final_screenshot = screenshot_dir / "02_propagandist_after_map_build.png"
        page.screenshot(path=str(final_screenshot), full_page=True)
    ok = (
        state_after_action.get("pending_choice", {}).get("choice_key") == "card_build_organization"
        and len(state_after_action.get("pending_choice", {}).get("towns") or []) > 0
        and final_orgs == before_orgs + expected["builds"]
        and final_hk.get("moves_left") == expected["moves"]
    )
    return {
        "card": card_name,
        "ok": ok,
        "url": url,
        "action_button_before_click": {"disabled": action_disabled_before, "title": action_title_before},
        "pending_choice_after_action": {
            "choice_key": state_after_action.get("pending_choice", {}).get("choice_key"),
            "prompt": state_after_action.get("pending_choice", {}).get("prompt"),
            "town_count": len(state_after_action.get("pending_choice", {}).get("towns") or []),
        },
        "map_resolutions": map_resolutions,
        "before_orgs": before_orgs,
        "final_orgs": final_orgs,
        "expected_final_orgs": before_orgs + expected["builds"],
        "moves_left": final_hk.get("moves_left"),
        "expected_moves": expected["moves"],
        "organizations": final_hk.get("orgs"),
        "action_log_tail": final_state.get("action_log", [])[-8:],
        "screenshots": [str(p.relative_to(BASE)) for p in [prompt_screenshot, final_screenshot] if p],
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = RECORD_DIR / f"card-build-browser-{stamp}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    server_proc = ensure_server()
    reports = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            for card_name, expected in BUILD_CARDS.items():
                game_id, ids = make_formal_game()
                reports.append(validate_card(page, game_id, ids["hk"], card_name, expected, screenshot_dir, stamp))
            browser.close()
    finally:
        if server_proc:
            server_proc.terminate()
    summary = {
        "total": len(reports),
        "passed": sum(1 for item in reports if item["ok"]),
        "failed": sum(1 for item in reports if not item["ok"]),
    }
    output = {"summary": summary, "reports": reports}
    json_path = RECORD_DIR / f"ACTION_CARD_BUILD_BROWSER_{stamp}.json"
    md_path = RECORD_DIR / f"ACTION_CARD_BUILD_BROWSER_{stamp}.md"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = ["# Action Card Build Browser Validation", "", f"Generated: {stamp}", "", f"Summary: {summary['passed']}/{summary['total']} passed", ""]
    for item in reports:
        status = "PASS" if item["ok"] else "FAIL"
        md_lines.extend([f"## {status} — {item['card']}", "", "```json", json.dumps(item, ensure_ascii=False, indent=2), "```", ""])
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(json.dumps({
        "summary": summary,
        "reports": [str(json_path), str(md_path)],
        "screenshots": [str(path) for path in sorted(screenshot_dir.glob("*.png"))],
    }, ensure_ascii=False, indent=2))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
