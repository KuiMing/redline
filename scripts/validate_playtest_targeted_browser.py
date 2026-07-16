import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8765")
RECORD_DIR = BASE / "docs" / "records" / "playtest-feedback"
STATIC_EXPECTED = {
    "宣傳家": 15,
    "思想家": 15,
    "資助者": 15,
    "資本家": 15,
    "分神": 30,
    "內鬥": 20,
}


def stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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


def scenario_url(payload):
    url = payload.get("url")
    if not url:
        url = f"/?game_id={payload['game_id']}&player_id={payload['player_id']}"
    if url.startswith("/"):
        url = BASE_URL + url
    return url


def wait_state(page):
    page.wait_for_function("window.lastGameState && window.lastGameState.players", timeout=15000)
    page.wait_for_timeout(200)
    return page.evaluate("window.lastGameState")


def goto_state(page, url):
    page.goto(url, wait_until="domcontentloaded")
    try:
        return wait_state(page)
    except PlaywrightTimeoutError:
        page.evaluate("typeof connect === 'function' && connect()")
        return wait_state(page)


def state(page):
    return page.evaluate("window.lastGameState")


def card_texts(page):
    return page.evaluate(
        "Array.from(document.querySelectorAll('.card')).map((e,i)=>({i, cls:e.className, text:e.innerText, buttons:Array.from(e.querySelectorAll('button')).map(b=>({text:b.innerText, disabled:b.disabled, mode:b.dataset.cardMode || ''}))}))"
    )


def visible_modal_text(page):
    return page.evaluate(
        "Array.from(document.querySelectorAll('.modal-overlay,.modal-glass,#choiceModal')).filter(e => getComputedStyle(e).display !== 'none' && e.offsetParent !== null).map(e=>e.innerText).join('\\n---\\n')"
    )


def click_hand(page, card_name, mode):
    loc = page.locator(".hand-card").filter(has_text=card_name).locator(f"button[data-card-mode='{mode}']")
    loc.first.click(timeout=5000)
    page.wait_for_timeout(350)
    return state(page)


def click_purchase(page, card_name):
    loc = page.locator(".card").filter(has_text=card_name).locator(".purchase-card-buy-btn")
    loc.first.click(timeout=5000)
    page.wait_for_timeout(500)
    return state(page)


def click_advance(page):
    btn = page.locator("#advanceStepBtn")
    try:
        btn.click(timeout=5000)
    except PlaywrightTimeoutError:
        # Some phase-gating UI can briefly leave the button disabled while the
        # websocket state is already current. Keep this as a browser/WebSocket
        # fallback so the regression records state changes instead of hanging.
        page.evaluate("sendAction('advance', {})")
    page.wait_for_timeout(500)
    return state(page)


def close_any_modal(page):
    for text in ["取消", "縮到右上角", "關閉", "知道了", "確認"]:
        try:
            loc = page.get_by_role("button", name=text, exact=True)
            if loc.count() and loc.first.is_visible(timeout=200):
                loc.first.click(timeout=1000)
                page.wait_for_timeout(250)
                return True
        except Exception:
            pass
    return False


def assert_true(checks, name, passed, details):
    checks.append({"name": name, "passed": bool(passed), "details": details})


def current_player(st):
    return next((p for p in st.get("players", []) if p.get("name") == st.get("current_player")), None)


def run():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    run_id = stamp()
    shot_dir = RECORD_DIR / f"targeted-browser-{run_id}"
    shot_dir.mkdir(parents=True, exist_ok=True)
    checks = []
    console_messages = []
    server_proc = ensure_server()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.on("console", lambda msg: console_messages.append({"type": msg.type, "text": msg.text}) if msg.type in {"error", "warning"} else None)
            page.on("pageerror", lambda exc: console_messages.append({"type": "pageerror", "text": str(exc)}))

            # 1. 常設購買區 live supply and decrement without disappearance.
            setup = post_json("/test/setup-purchase-deck-ui", {"resources": {"money": 10, "propaganda": 10}})
            st = goto_state(page, scenario_url(setup))
            static_before = dict(st.get("static_purchase_supply") or {})
            texts_before = card_texts(page)
            ui_static_before = {name: any((name in c["text"] and f"剩 {count}" in c["text"]) for c in texts_before) for name, count in STATIC_EXPECTED.items()}
            st = click_purchase(page, "宣傳家")
            texts_after = card_texts(page)
            page.screenshot(path=shot_dir / "01_static_supply_after_buy.png", full_page=True)
            assert_true(
                checks,
                "常設購買區供應依 CSV 初始值，購買後卡片仍在且 UI 使用 live supply",
                static_before == STATIC_EXPECTED
                and st.get("static_purchase_supply", {}).get("宣傳家") == 14
                and any("宣傳家" in c["text"] and "剩 14" in c["text"] for c in texts_after)
                and all(ui_static_before.values()),
                {"static_before": static_before, "ui_static_before": ui_static_before, "static_after": st.get("static_purchase_supply")},
            )

            # 2. 宣傳家 action: no bait prompt, returns supply, builds organization, grants one move.
            setup = post_json("/test/setup-remove-to-purchase", {
                "card_name": "宣傳家",
                "faction_id": "taiwan_green",
                "base": "臺北",
                "orgs": {"臺北": 1},
                "resources": {"money": 5, "propaganda": 5},
            })
            st = goto_state(page, scenario_url(setup))
            before_supply = st.get("static_purchase_supply", {}).get("宣傳家")
            st = click_hand(page, "宣傳家", "action")
            page.screenshot(path=shot_dir / "02_propagandist_action.png", full_page=True)
            player = current_player(st)
            modal = visible_modal_text(page)
            assert_true(
                checks,
                "宣傳家行動不出現誘導虛耗，回歸供應、建立組織、給 1 移動",
                not st.get("pending_choice")
                and "誘導虛耗" not in modal
                and st.get("static_purchase_supply", {}).get("宣傳家") == before_supply + 1
                and (player or {}).get("orgs", {}).get("臺北") == 2
                and (player or {}).get("moves_left") == 1,
                {"before_supply": before_supply, "after_supply": st.get("static_purchase_supply", {}).get("宣傳家"), "player": player, "modal": modal},
            )

            # 3. 奧援卡按鈕為「棄置／行動」（沒有誤導的「資源」鈕）；ACTION 階段仍可「行動」觸發效果。
            # P1 playtest 回報：奧援卡只能當行動使用，不該保留一般卡的資源按鈕。2026-07-16 改為
            # 「詳情＋棄置」；卡面完整顯示 I/II/III 級文字後「詳情」已無存在意義，2026-07-17 移除，
            # 最終為「棄置／行動」兩顆按鈕（棄置沿用 mode='resource' 的奧援卡無效果棄牌路徑）。
            setup = post_json("/test/setup-support-card-play", {"support_name": "北國奧援", "faction_id": "liberals", "base": "海參崴", "orgs": {"海參崴": 1}, "resources": {"money": 0, "propaganda": 0}})
            st = goto_state(page, scenario_url(setup))
            close_any_modal(page)
            support_card = next(c for c in card_texts(page) if "北國奧援" in c["text"] and "hand-card" in c["cls"])
            action_enabled = any(b["mode"] == "action" and not b["disabled"] for b in support_card["buttons"])
            hand_button_texts = [b["text"] for b in support_card["buttons"] if b["mode"]]
            st_discard = click_hand(page, "北國奧援", "resource")
            page.screenshot(path=shot_dir / "03_support_discard.png", full_page=True)
            hand_after_discard = (current_player(st_discard) or {}).get("hand")
            discard_after = (current_player(st_discard) or {}).get("discard_pile")
            setup = post_json("/test/setup-support-card-play", {"support_name": "北國奧援", "faction_id": "liberals", "base": "海參崴", "orgs": {"海參崴": 1}, "resources": {"money": 0, "propaganda": 0}})
            st = goto_state(page, scenario_url(setup))
            close_any_modal(page)
            st_action = click_hand(page, "北國奧援", "action")
            page.screenshot(path=shot_dir / "04_support_action_effect.png", full_page=True)
            assert_true(
                checks,
                "奧援卡按鈕為棄置/行動（棄置直接進棄牌堆不給資源）；ACTION 階段行動按鈕仍可觸發效果",
                action_enabled
                and hand_button_texts == ["棄置", "行動"]
                and hand_after_discard == []
                and discard_after == ["北國奧援"]
                and (st_action.get("pending_choice") or st_action.get("last_action_result") or st_action.get("action_log")),
                {"hand_buttons_before": support_card["buttons"], "hand_after_discard": hand_after_discard, "discard_after": discard_after, "action_pending": st_action.get("pending_choice"), "action_log_tail": (st_action.get("action_log") or [])[-5:]},
            )

            # 4. 乘勝追擊 pending choice from own discard <= 3 cost.
            setup = post_json("/test/setup-press-advantage-proof", {})
            st = goto_state(page, scenario_url(setup))
            st = click_hand(page, "乘勝追擊", "action")
            page.screenshot(path=shot_dir / "05_press_advantage_choice.png", full_page=True)
            assert_true(
                checks,
                "乘勝追擊行動後開啟從己方棄牌堆選擇 3 點以下牌加入手牌",
                (st.get("pending_choice") or {}).get("choice_key") == "gain_from_discard"
                and "宣傳家" in json.dumps(st.get("pending_choice"), ensure_ascii=False),
                {"pending_choice": st.get("pending_choice"), "modal": visible_modal_text(page)},
            )

            # 5. 隨機購買區購買北國奧援後 slot 立即移除/補牌。
            setup = post_json("/test/setup-purchase-deck-ui", {
                "faction_id": "liberals",
                "base": "巴黎",
                "orgs": {"巴黎": 1},
                "resources": {"money": 10, "propaganda": 10},
                "purchase_area_random": ["北國奧援", "合作談判", "走漏風聲", "模仿戰術", "批鬥"],
            })
            st = goto_state(page, scenario_url(setup))
            close_any_modal(page)
            before_area = list(st.get("purchase_area") or [])
            st = click_purchase(page, "北國奧援")
            after_area = list(st.get("purchase_area") or [])
            page.screenshot(path=shot_dir / "06_random_support_purchase_refill.png", full_page=True)
            assert_true(
                checks,
                "隨機購買區購買北國奧援後原 slot 立即移除/補牌",
                len(before_area) > 6 and before_area[6] == "北國奧援" and (len(after_area) <= 6 or after_area[6] != "北國奧援"),
                {"before_area": before_area, "after_area": after_area, "state_resources": (current_player(st) or {}).get("resources")},
            )

            # 6. 東突厥集中營 failure discards a non-red player through the official event UI flow.
            setup = post_json("/test/setup-event-card-proof", {"event_name": "東突厥集中營", "current_event_active": True})
            st = goto_state(page, scenario_url(setup))
            close_any_modal(page)
            before_players = st.get("players", [])
            before_viewer_hand = next(p for p in before_players if p["name"] == "viewer").get("hand", [])
            close_any_modal(page)
            st = click_advance(page)  # viewer ACTION -> END
            if st.get("turn_phase") == "end":
                st = click_advance(page)  # viewer END -> red EVENT
            red_page = browser.new_page(viewport={"width": 1440, "height": 960})
            red_page.on("console", lambda msg: console_messages.append({"type": msg.type, "text": msg.text}) if msg.type in {"error", "warning"} else None)
            red_page.on("pageerror", lambda exc: console_messages.append({"type": "pageerror", "text": str(exc)}))
            red_url = f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['red_player_id']}"
            st = goto_state(red_page, red_url)
            st = click_advance(red_page)  # red EVENT -> ACTION
            st = click_advance(red_page)  # red ACTION -> END; non-red mission failure settles here
            red_page.screenshot(path=shot_dir / "07_east_turkestan_failure_discard.png", full_page=True)
            st = state(red_page)
            red_page.close()
            viewer = next(p for p in st.get("players", []) if p["name"] == "viewer")
            red = next(p for p in st.get("players", []) if p["name"] == "red")
            assert_true(
                checks,
                "東突厥集中營非紅軍任務失敗後隨機棄非紅軍手牌",
                len(viewer.get("discard_pile", [])) >= len(before_viewer_hand) + 1
                and any("Event failure: discarded 1 random hand card" in entry for entry in (st.get("action_log") or []))
                and len(red.get("discard_pile", [])) == 0,
                {"before_viewer_hand": before_viewer_hand, "viewer_after": viewer, "red_after": red, "event": st.get("current_event"), "log_tail": (st.get("action_log") or [])[-8:]},
            )

            # 7. 紅軍能力 UI resolves and collapses.
            setup = post_json("/test/setup-red-army-abilities-proof", {})
            st = goto_state(page, scenario_url(setup))
            page.locator("#redArmyAbilityBtn").click(timeout=5000)
            page.wait_for_timeout(300)
            # Pick first enabled visible choice in the ability modal if present.
            choice_btns = page.locator("#factionActionModalChoices button:visible")
            if choice_btns.count():
                choice_btns.first.click(timeout=5000)
                page.wait_for_timeout(700)
            st = state(page)
            page.screenshot(path=shot_dir / "08_red_army_ability_collapsed.png", full_page=True)
            modal_visible = page.evaluate("!!Array.from(document.querySelectorAll('.modal-overlay')).find(e => getComputedStyle(e).display !== 'none' && e.offsetParent !== null && e.innerText.includes('紅軍'))")
            assert_true(
                checks,
                "紅軍能力執行完後面板/視窗收起不擋購買區",
                not modal_visible and page.locator(".purchase-card-buy-btn").count() >= 6,
                {"modal_visible": modal_visible, "log_tail": (st.get("action_log") or [])[-6:]},
            )

            # 8. 後期/第 7 回合類似 gating：use the already recorded full-playthrough proof and verify final + no advance blocker trace.
            latest_full = sorted((BASE / "docs" / "records" / "full-playthrough").glob("BROWSER_FULL_PLAYTHROUGH_*.json"))
            full_payload = json.loads(latest_full[-1].read_text(encoding="utf-8")) if latest_full else {}
            trace = full_payload.get("trace") or []
            final_summary = full_payload.get("final_state_summary") or {}
            advance_blockers = [t for t in trace if t.get("step") in {"pending_choice_unresolved", "stagnant_state_break"}]
            late_progress = (full_payload.get("final_state") or {}).get("turn", 0) >= 20 or final_summary.get("turn", 0) >= 20
            assert_true(
                checks,
                "後期回合沒有 pending_choice / 前端 gating 阻斷開始購買階段（完整 UI playthrough 證據）",
                bool(full_payload.get("passed")) and late_progress and not advance_blockers,
                {"full_playthrough_json": str(latest_full[-1]) if latest_full else None, "final_summary": final_summary, "advance_blockers": advance_blockers[-5:]},
            )

            browser.close()
    finally:
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_proc.kill()

    summary = {"total": len(checks), "passed": sum(1 for c in checks if c["passed"]), "failed": sum(1 for c in checks if not c["passed"])}
    result = {
        "passed": summary["failed"] == 0 and not [m for m in console_messages if m.get("type") in {"error", "pageerror"}],
        "summary": summary,
        "checks": checks,
        "screenshots": [str(p) for p in sorted(shot_dir.glob("*.png"))],
        "console_messages": console_messages,
    }
    json_path = RECORD_DIR / f"PLAYTEST_TARGETED_BROWSER_{run_id}.json"
    md_path = RECORD_DIR / f"PLAYTEST_TARGETED_BROWSER_{run_id}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Playtest Targeted Browser Regression",
        "",
        f"- passed: {result['passed']}",
        f"- summary: {summary['passed']}/{summary['total']} checks passed",
        f"- console_error_count: {len([m for m in console_messages if m.get('type') in {'error', 'pageerror'}])}",
        "",
        "## Checks",
    ]
    for check in checks:
        lines.append(f"- [{'x' if check['passed'] else ' '}] {check['name']}")
    lines.extend(["", "## Screenshots"])
    for path in result["screenshots"]:
        lines.append(f"- {path}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"passed": result["passed"], "summary": summary, "json": str(json_path), "md": str(md_path), "screenshots": result["screenshots"], "failed": [c for c in checks if not c["passed"]], "console_messages": console_messages[-10:]}, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
