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
    hk_join = post_json("/join", {"game_id": game_id, "name": "hk"})
    tibet_join = post_json("/join", {"game_id": game_id, "name": "tibet"})
    uyghur_join = post_json("/join", {"game_id": game_id, "name": "uyghur"})
    players = [
        ("host", host_id, create["resume_token"], "red_army", "北京"),
        ("hk", hk_join["player_id"], hk_join["resume_token"], "hong_kong", "香港城"),
        ("tibet", tibet_join["player_id"], tibet_join["resume_token"], "tibet_dharamsala", "達蘭薩拉"),
        ("uyghur", uyghur_join["player_id"], uyghur_join["resume_token"], "uyghur_munich", "慕尼黑"),
    ]
    for name, pid, _token, faction_id, base_name in players:
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
    return (
        game_id,
        {name: pid for name, pid, *_ in players},
        {name: token for name, _pid, token, *_ in players},
    )


def open_authenticated_game(page, game_id, player_id, resume_token, player_name, cache_key):
    page.goto(BASE_URL + "/", wait_until="domcontentloaded")
    page.evaluate(
        """session => {
            localStorage.setItem('redline.sessions.v1', JSON.stringify({
                [session.game_id]: {
                    game_id: session.game_id,
                    player_id: session.player_id,
                    resume_token: session.resume_token,
                    name: session.name,
                    saved_at: Date.now(),
                },
            }));
        }""",
        {
            "game_id": game_id,
            "player_id": player_id,
            "resume_token": resume_token,
            "name": player_name,
        },
    )
    url = f"{BASE_URL}/?v={cache_key}"
    page.goto(url, wait_until="domcontentloaded")
    return url


def wait_state(page):
    page.wait_for_function("window.lastGameState && window.lastGameState.players && window.lastGameState.players.length >= 2", timeout=15000)
    page.wait_for_timeout(300)
    event_reveal = page.locator("#eventRevealModal")
    if event_reveal.is_visible():
        event_reveal.click(position={"x": 5, "y": 5})
        event_reveal.wait_for(state="hidden", timeout=5000)
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


def validate_card(page, game_id, player_id, resume_token, card_name, expected, screenshot_dir, stamp):
    prepared = post_json("/test/set-hand", {
        "game_id": game_id,
        "player_id": player_id,
        "cards": [card_name],
        "turn_phase": "action",
        "set_current_player": True,
    })
    if prepared.get("error"):
        raise AssertionError(prepared)
    url = open_authenticated_game(
        page,
        game_id,
        player_id,
        resume_token,
        "hk",
        f"card-build-browser-{stamp}-{card_name}",
    )
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


def validate_no_legal_build_state(page, game_id, player_id, resume_token, screenshot_dir, stamp):
    card_names = list(BUILD_CARDS)
    prepared = post_json("/test/set-hand", {
        "game_id": game_id,
        "player_id": player_id,
        "cards": card_names,
        "turn_phase": "action",
        "set_current_player": True,
        "restrict_build": True,
    })
    if prepared.get("error"):
        raise AssertionError(prepared)
    url = open_authenticated_game(
        page,
        game_id,
        player_id,
        resume_token,
        "hk",
        f"no-legal-build-{stamp}",
    )
    state = wait_state(page)
    me = hk_from(state, player_id)
    button_checks = []
    for index, card_name in enumerate(card_names):
        card_el = page.locator(".hand-card").filter(has_text=card_name).first
        action_button = card_el.locator("button[data-card-mode='action']")
        resource_button = card_el.locator("button[data-card-mode='resource']")
        action_button.wait_for(state="visible", timeout=10000)
        legality = (me.get("hand_action_legality") or [])[index]
        button_checks.append({
            "card": card_name,
            "action_disabled": action_button.is_disabled(),
            "action_text": action_button.inner_text(),
            "action_title": action_button.get_attribute("title") or "",
            "resource_enabled": resource_button.is_enabled(),
            "legality": legality,
        })
    upper_screenshot = screenshot_dir / "03_no_legal_build_cards_disabled_upper.png"
    page.screenshot(path=str(upper_screenshot), full_page=True)
    last_card = page.locator(".hand-card").filter(has_text=card_names[-1]).first
    last_card.scroll_into_view_if_needed()
    page.wait_for_timeout(200)
    lower_screenshot = screenshot_dir / "04_no_legal_build_cards_disabled_lower.png"
    page.screenshot(path=str(lower_screenshot), full_page=True)
    expected_reason = "目前沒有城鎮可以建立組織。"
    ok = all(
        item["action_disabled"]
        and item["action_text"] == "無城鎮可建立"
        and item["action_title"] == expected_reason
        and item["resource_enabled"]
        and item["legality"] == {
            "playable": False,
            "reason": expected_reason,
            "no_legal_build_town": True,
        }
        for item in button_checks
    )
    return {
        "card": "全部建立組織行動卡（無合法城鎮）",
        "ok": ok,
        "url": url,
        "button_checks": button_checks,
        "hand_unchanged": me.get("hand") == card_names,
        "screenshots": [str(path.relative_to(BASE)) for path in (upper_screenshot, lower_screenshot)],
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = RECORD_DIR / f"card-build-browser-{stamp}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    server_proc = ensure_server()
    reports = []
    console_errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            for card_name, expected in BUILD_CARDS.items():
                game_id, ids, tokens = make_formal_game()
                reports.append(validate_card(page, game_id, ids["hk"], tokens["hk"], card_name, expected, screenshot_dir, stamp))
            game_id, ids, tokens = make_formal_game()
            reports.append(validate_no_legal_build_state(page, game_id, ids["hk"], tokens["hk"], screenshot_dir, stamp))
            browser.close()
    finally:
        if server_proc:
            server_proc.terminate()
    summary = {
        "total": len(reports),
        "passed": sum(1 for item in reports if item["ok"]),
        "failed": sum(1 for item in reports if not item["ok"]),
        "console_error_count": len(console_errors),
    }
    output = {"summary": summary, "reports": reports, "console_errors": console_errors}
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
        "console_errors": console_errors,
    }, ensure_ascii=False, indent=2))
    if summary["failed"] or console_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
