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
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8765")
RECORD_DIR = BASE / "docs" / "records" / "purchase"
EXPECTED_AFTER_SETUP = {
    "宣傳家": 10,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20,
}
EXPECTED_AFTER_BUY = dict(EXPECTED_AFTER_SETUP, 宣傳家=9)


def ensure_server():
    host = "127.0.0.1"
    port = int(BASE_URL.rsplit(":", 1)[-1]) if BASE_URL.startswith("http://127.0.0.1:") else 8765
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
    raise RuntimeError("server did not start on " + BASE_URL)


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def make_formal_4p_game():
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
        chosen = post_json("/choose-faction", {
            "game_id": game_id,
            "player_id": pid,
            "faction_id": faction_id,
            "base_name": base_name,
        })
        if chosen.get("error"):
            raise AssertionError(f"choose {name}: {chosen['error']}")
        ready = post_json("/ready", {"game_id": game_id, "player_id": pid, "ready": True})
        if ready.get("error"):
            raise AssertionError(f"ready {name}: {ready['error']}")
    started = post_json("/start", {"game_id": game_id, "player_id": host_id, "market_mode": "sample_53"})
    if started.get("error"):
        raise AssertionError(started["error"])
    return game_id, {name: pid for name, pid, *_ in players}


def wait_state(page):
    page.wait_for_function("window.lastGameState && window.lastGameState.players && document.querySelectorAll('#purchaseStatic .card').length === 6", timeout=15000)
    page.wait_for_timeout(350)
    return page.evaluate("window.lastGameState")


def static_ui_counts(page):
    return page.locator("#purchaseStatic .card").evaluate_all("""els => Object.fromEntries(els.map(el => {
  const lines = el.innerText.split(String.fromCharCode(10)).map(s => s.trim()).filter(Boolean);
  const name = lines[0];
  const countLine = lines.find(line => line.startsWith('剩 ')) || '';
  return [name, Number.parseInt(countLine.replace('剩 ', ''), 10)];
}))""")


def click_advance(page):
    page.locator("#advanceStepBtn").click(timeout=5000)
    page.wait_for_timeout(500)
    return page.evaluate("window.lastGameState")


def play_follower_resource(page):
    page.locator(".hand-card").filter(has_text="追隨者").locator("button[data-card-mode='resource']").first.click(timeout=5000)
    page.wait_for_timeout(350)
    return page.evaluate("window.lastGameState")


def buy_static(page, card_name):
    page.locator("#purchaseStatic .card").filter(has_text=card_name).locator(".purchase-card-buy-btn").first.click(timeout=5000)
    page.wait_for_timeout(600)
    return page.evaluate("window.lastGameState")


def assert_equal(checks, name, actual, expected, extra=None):
    checks.append({
        "name": name,
        "passed": actual == expected,
        "details": {"actual": actual, "expected": expected, **(extra or {})},
    })


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_dir = RECORD_DIR / f"static-purchase-ui-{stamp}"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    checks = []
    server_proc = ensure_server()
    try:
        game_id, ids = make_formal_4p_game()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            host_url = f"{BASE_URL}/?game_id={game_id}&player_id={ids['host']}&v=static-ui-browser-{stamp}"
            page.goto(host_url, wait_until="domcontentloaded")
            host_state = wait_state(page)
            host_counts = static_ui_counts(page)
            host_shot = screenshot_dir / "01_host_formal_start_static_counts.png"
            page.screenshot(path=str(host_shot), full_page=True)
            assert_equal(checks, "formal_start_host_ui_static_counts_not_one", host_counts, EXPECTED_AFTER_SETUP, {
                "url": host_url,
                "state_static_purchase_supply": host_state.get("static_purchase_supply"),
                "screenshot": str(host_shot.relative_to(BASE)),
            })

            hk_url = f"{BASE_URL}/?game_id={game_id}&player_id={ids['hk']}&v=static-ui-browser-{stamp}"
            page.goto(hk_url, wait_until="domcontentloaded")
            hk_state = wait_state(page)
            hk_counts = static_ui_counts(page)
            hk_start_shot = screenshot_dir / "02_hk_formal_start_static_counts.png"
            page.screenshot(path=str(hk_start_shot), full_page=True)
            assert_equal(checks, "formal_start_current_player_ui_static_counts_not_one", hk_counts, EXPECTED_AFTER_SETUP, {
                "url": hk_url,
                "state_static_purchase_supply": hk_state.get("static_purchase_supply"),
                "screenshot": str(hk_start_shot.relative_to(BASE)),
            })

            prepared = post_json("/test/set-hand", {
                "game_id": game_id,
                "player_id": ids["hk"],
                "cards": ["追隨者", "追隨者", "追隨者"],
                "turn_phase": "action",
                "set_current_player": True,
            })
            if prepared.get("error"):
                raise AssertionError(prepared["error"])
            page.goto(hk_url + "&prepared_purchase=1", wait_until="domcontentloaded")
            wait_state(page)
            for _ in range(3):
                play_follower_resource(page)
            purchase_phase_state = click_advance(page)
            if purchase_phase_state.get("turn_phase") != "end":
                raise AssertionError(f"expected purchase phase after action, got {purchase_phase_state.get('turn_phase')}")
            bought_state = buy_static(page, "宣傳家")
            after_buy_counts = static_ui_counts(page)
            buy_shot = screenshot_dir / "03_after_buy_propagandist_static_count_decrements.png"
            page.screenshot(path=str(buy_shot), full_page=True)
            hk = next(pl for pl in bought_state["players"] if pl["id"] == ids["hk"])
            assert_equal(checks, "after_buy_ui_static_count_decrements_and_card_stays", after_buy_counts, EXPECTED_AFTER_BUY, {
                "state_static_purchase_supply": bought_state.get("static_purchase_supply"),
                "hk_resources": hk.get("resources"),
                "hk_discard_tail": hk.get("discard_pile", [])[-5:],
                "action_log_tail": bought_state.get("action_log", [])[-6:],
                "screenshot": str(buy_shot.relative_to(BASE)),
            })
            browser.close()
    finally:
        if server_proc:
            server_proc.terminate()

    summary = {"total": len(checks), "passed": sum(1 for c in checks if c["passed"]), "failed": sum(1 for c in checks if not c["passed"])}
    report = {"summary": summary, "checks": checks}
    json_path = RECORD_DIR / f"STATIC_PURCHASE_UI_BROWSER_{stamp}.json"
    md_path = RECORD_DIR / f"STATIC_PURCHASE_UI_BROWSER_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_lines = ["# Static Purchase UI Browser Validation", "", f"Generated: {stamp}", "", f"Summary: {summary['passed']}/{summary['total']} passed", ""]
    for item in checks:
        status = "PASS" if item["passed"] else "FAIL"
        md_lines += [f"## {status} — {item['name']}", "", "```json", json.dumps(item["details"], ensure_ascii=False, indent=2), "```", ""]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(json.dumps({"summary": summary, "reports": [str(json_path), str(md_path)], "screenshots": [str(p) for p in sorted(screenshot_dir.glob('*.png'))]}, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
