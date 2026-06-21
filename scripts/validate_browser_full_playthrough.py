import json
import re
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE = Path(__file__).resolve().parent.parent
RECORD_DIR = BASE / "docs" / "records" / "full-playthrough"
BASE_URL = "http://127.0.0.1:8765"

FACTION_PLAN = [
    ("A", "紅軍"),
    ("B", "臺灣"),
    ("C", "香港"),
    ("D", "蒙古"),
]

STATIC_COSTS = {
    0: {"name": "宣傳家", "money": 0, "propaganda": 3},
    1: {"name": "思想家", "money": 0, "propaganda": 5},
    2: {"name": "資助者", "money": 2, "propaganda": 1},
    3: {"name": "資本家", "money": 3, "propaganda": 2},
}

BUY_ATTEMPTS = set()


def now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_rules_fingerprint():
    rules = BASE / "rules.md"
    data = rules.read_bytes()
    return {"path": str(rules), "sha256": hashlib.sha256(data).hexdigest(), "lines": len(data.decode("utf-8").splitlines())}


def wait_render(page):
    page.wait_for_function("window.lastGameState !== undefined", timeout=15000)
    page.wait_for_timeout(120)


def js_state(page):
    try:
        return page.evaluate("window.lastGameState || null")
    except Exception:
        return None


def visible_enabled_count(page, selector):
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


def click_first_enabled(page, selector, timeout=1200):
    loc = page.locator(selector)
    count = loc.count()
    for i in range(count):
        item = loc.nth(i)
        try:
            if item.is_visible(timeout=200) and item.is_enabled(timeout=200):
                item.click(timeout=timeout)
                page.wait_for_timeout(180)
                return True
        except Exception:
            continue
    return False


def setup_faction(page, label, trace):
    page.get_by_role("button", name=label, exact=True).click()
    page.wait_for_timeout(300)
    if page.locator("#factionVariantList button:visible").count():
        page.locator("#factionVariantList button:visible").first.click()
        page.wait_for_timeout(300)
    for _ in range(5):
        visible = page.locator("#factionConfirmBar").evaluate("e=>getComputedStyle(e).display") == "block"
        enabled = not page.locator("#confirmFactionBtn").evaluate("e=>e.disabled")
        if visible and enabled:
            break
        buttons = page.locator("#factionBaseList button:visible")
        cnt = buttons.count()
        if cnt == 0:
            break
        first_text = buttons.nth(0).inner_text()
        idx = 1 if cnt > 1 and first_text.startswith("←") else 0
        buttons.nth(idx).click()
        page.wait_for_timeout(350)
    info = page.locator("#factionPickerInfo").inner_text()
    trace.append({"step": "choose_faction", "label": label, "info": info})
    page.click("#confirmFactionBtn")
    page.wait_for_timeout(500)


def setup_lobby(browser, trace, screenshot_dir):
    pages = {}
    console_errors = []
    for name, _ in FACTION_PLAN:
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda msg, n=name: console_errors.append({"player": n, "type": msg.type, "text": msg.text}) if msg.type in {"error", "warning"} else None)
        page.on("pageerror", lambda exc, n=name: console_errors.append({"player": n, "type": "pageerror", "text": str(exc)}))
        page.goto(BASE_URL + "/", wait_until="domcontentloaded")
        page.fill("#playerName", name)
        pages[name] = page

    host = pages["A"]
    host.click("#createRoomBtn")
    host.wait_for_selector("#factionPicker", state="visible", timeout=15000)
    room_id = host.eval_on_selector("#roomId", "e=>e.value")
    trace.append({"step": "create_room", "room_id": room_id})

    for name in ["B", "C", "D"]:
        page = pages[name]
        page.fill("#roomId", room_id)
        page.click("#joinRoomBtn")
        page.wait_for_selector("#factionPicker", state="visible", timeout=15000)
        trace.append({"step": "join_room", "player": name})

    for name, label in FACTION_PLAN:
        setup_faction(pages[name], label, trace)

    for name, page in pages.items():
        page.click("#toggleReadyBtn")
        page.wait_for_timeout(350)
        trace.append({"step": "ready", "player": name})

    host.wait_for_function("!document.querySelector('#startGameBtn').disabled", timeout=15000)
    host.screenshot(path=screenshot_dir / "01_lobby_ready.png", full_page=True)
    host.click("#startGameBtn")
    trace.append({"step": "start_game_clicked"})

    for name, page in pages.items():
        page.wait_for_selector("#gameShell", state="visible", timeout=20000)
        wait_render(page)
        trace.append({"step": "game_shell_visible", "player": name, "state": summarize_state(js_state(page))})
    return pages, room_id, console_errors


def summarize_state(state):
    if not state:
        return None
    return {
        "turn": state.get("turn"),
        "turn_phase": state.get("turn_phase"),
        "game_phase": state.get("game_phase"),
        "current_player": state.get("current_player"),
        "winner": state.get("winner"),
        "pending_choice": summarize_choice(state.get("pending_choice")),
    }


def summarize_choice(choice):
    if not choice:
        return None
    return {k: choice.get(k) for k in ["type", "choice_key", "player_id", "source", "step", "count", "min", "max"] if k in choice}


def page_for_current_player(pages, state):
    current = state.get("current_player")
    if current in pages:
        return pages[current]
    if current == "host" and "A" in pages:
        return pages["A"]
    # Player names in this scripted run are host/B/C/D at runtime because
    # /create reserves the host before the lobby name field is submitted.
    return next(iter(pages.values()))


def page_for_player_id(pages, state, player_id):
    for p in state.get("players", []):
        if p.get("id") == player_id:
            runtime_name = p.get("name")
            if runtime_name in pages:
                return pages[runtime_name]
            if runtime_name == "host" and "A" in pages:
                return pages["A"]
    return None


def handle_modal_or_pending(pages, state, trace):
    choice = state.get("pending_choice") if state else None
    target_page = None
    if choice and choice.get("player_id"):
        target_page = page_for_player_id(pages, state, choice.get("player_id"))
    if not target_page:
        target_page = page_for_current_player(pages, state)

    # Event/era build choices are intentionally handled on the strategic map UI
    # instead of a modal. Select the first highlighted town in the iframe, then
    # click the map panel's direct-build button.
    if choice and choice.get("choice_key") in {"event_build_organization", "era_red_build_near_target"}:
        towns = choice.get("towns") or []
        first = next((entry for entry in towns if entry.get("town")), None)
        if first:
            town = first["town"]
            try:
                target_page.get_by_role("button", name="戰略地圖", exact=True).click(timeout=1200)
            except Exception:
                pass
            try:
                frame_el = target_page.locator("#strategicMapFrame").element_handle(timeout=5000)
                frame = frame_el.content_frame() if frame_el else None
                if frame:
                    frame.wait_for_function("window.lastGameState && typeof window.selectTownForCurrentMapAction === 'function'", timeout=8000)
                    payload = {
                        "mode": "support-targets",
                        "choiceKey": choice.get("choice_key"),
                        "sourceName": choice.get("source_name") or choice.get("choice_key") or "建立組織",
                        "prompt": choice.get("prompt") or "事件卡效果：請在戰略地圖選擇可建立組織的城鎮。",
                        "towns": [
                            {"town": entry.get("town"), "label": entry.get("label") or entry.get("town"), "index": idx}
                            for idx, entry in enumerate(towns)
                            if entry.get("town")
                        ],
                    }
                    frame.evaluate("payload => window.applySupportChoiceHighlight && window.applySupportChoiceHighlight(payload)", payload)
                    frame.evaluate("town => window.selectTownForCurrentMapAction(town, {autoFocus:false})", town)
                    frame.wait_for_function("!document.querySelector('#directBuildBtn').disabled", timeout=3000)
                    frame.locator("#directBuildBtn").click(timeout=3000)
                    target_page.wait_for_timeout(250)
                    trace.append({"step": "resolve_event_build_on_map_ui", "choice": summarize_choice(choice), "town": town})
                    return True
            except Exception as exc:
                trace.append({"step": "event_build_map_ui_failed", "choice": summarize_choice(choice), "town": town, "error": str(exc)})

    # General pending-choice modal.
    if choice:
        for selector in [
            "#choiceModal .choice-card-grid button:visible:not(#closeChoiceModal)",
            "#choiceModal button:visible:not(#closeChoiceModal)",
            "#factionActionModalChoices button:visible",
        ]:
            if click_first_enabled(target_page, selector):
                trace.append({"step": "resolve_pending_choice_ui", "choice": summarize_choice(choice), "selector": selector})
                return True
        # Last resort: close/skip only when UI exposes close as resolve/skip for this choice.
        if click_first_enabled(target_page, "#closeChoiceModal:visible"):
            trace.append({"step": "close_pending_choice_modal", "choice": summarize_choice(choice)})
            return True
        trace.append({"step": "pending_choice_unresolved", "choice": summarize_choice(choice)})
        return False

    # Informational achievement/effect modals can obscure the action UI; close or shrink them
    # using the visible UI control, then continue the playthrough.
    for page_name, page in pages.items():
        for text in ["縮到右上角", "關閉", "知道了", "確認"]:
            try:
                btn = page.get_by_role("button", name=text, exact=True)
                if btn.count() and btn.first.is_visible(timeout=150) and btn.first.is_enabled(timeout=150):
                    btn.first.click(timeout=1000)
                    page.wait_for_timeout(180)
                    trace.append({"step": "close_info_modal_ui", "player_page": page_name, "button": text})
                    return True
            except Exception:
                pass

    # Target selection modal from card effects / red army actions.
    for page_name, page in pages.items():
        if click_first_enabled(page, "#factionActionModalChoices button:visible"):
            trace.append({"step": "resolve_target_modal_ui", "player_page": page_name})
            return True
    return False


def current_me(state):
    current = state.get("current_player")
    for p in state.get("players", []):
        if p.get("name") == current:
            return p
    return None


def can_afford(player, cost):
    resources = player.get("resources") or {}
    return (resources.get("money") or 0) >= cost.get("money", 0) and (resources.get("propaganda") or 0) >= cost.get("propaganda", 0)


def try_buy(page, state, trace):
    player = current_me(state)
    if not player:
        return False
    resources = player.get("resources") or {}
    phase_key = (state.get("turn"), state.get("current_player"), resources.get("money") or 0, resources.get("propaganda") or 0, len(player.get("hand") or []))
    if phase_key in BUY_ATTEMPTS:
        return False
    # Prefer affordable static cards, then a random support/common slot if enough mixed resources.
    for idx, cost in STATIC_COSTS.items():
        supply = (state.get("static_purchase_supply") or {}).get(cost["name"], 1)
        if supply and can_afford(player, cost):
            buttons = page.locator(".purchase-card-buy-btn")
            if buttons.count() > idx:
                BUY_ATTEMPTS.add(phase_key)
                buttons.nth(idx).click()
                page.wait_for_timeout(250)
                trace.append({"step": "buy_card_ui", "index": idx, "card": cost["name"], "turn": state.get("turn"), "player": state.get("current_player")})
                return True
    if (resources.get("money") or 0) >= 1 and (resources.get("propaganda") or 0) >= 2:
        buttons = page.locator(".purchase-card-buy-btn")
        if buttons.count() > 6:
            BUY_ATTEMPTS.add(phase_key)
            buttons.nth(6).click()
            page.wait_for_timeout(250)
            trace.append({"step": "buy_random_card_ui", "index": 6, "turn": state.get("turn"), "player": state.get("current_player")})
            return True
    return False


def play_action_phase(page, state, trace):
    player = current_me(state)
    if not player:
        return
    try:
        page.get_by_role("button", name="指揮中心", exact=True).click(timeout=800)
        page.wait_for_timeout(100)
    except Exception:
        pass
    turn = int(state.get("turn") or 0)
    name = state.get("current_player")

    # Red Army ability UI coverage before purchase transition.
    if click_first_enabled(page, "#redArmyAbilityBtn:visible:not([disabled])"):
        page.wait_for_timeout(250)
        click_first_enabled(page, "#factionActionModalChoices button:visible")
        trace.append({"step": "red_army_ability_ui", "turn": turn, "player": name})
        return

    # Use one action card periodically; otherwise resource-play cards to progress purchases.
    if turn % 3 == 1:
        if click_first_enabled(page, ".hand-card-action-btn[data-card-mode='action']:visible:not([disabled])"):
            trace.append({"step": "play_card_action_ui", "turn": turn, "player": name})
            return

    if click_first_enabled(page, ".hand-card-action-btn[data-card-mode='resource']:visible:not([disabled])"):
        trace.append({"step": "play_card_resource_ui", "turn": turn, "player": name})
        return

    if click_first_enabled(page, ".hand-card-action-btn[data-card-mode='action']:visible:not([disabled])"):
        trace.append({"step": "play_card_action_fallback_ui", "turn": turn, "player": name})
        return

    if try_buy(page, state, trace):
        return

    if click_first_enabled(page, "#advanceStepBtn:visible:not([disabled])"):
        trace.append({"step": "advance_from_action_ui", "turn": turn, "player": name})
        return


def advance_phase(page, state, trace):
    state_summary = summarize_state(state) or {}
    if click_first_enabled(page, "#advanceStepBtn:visible:not([disabled])"):
        trace.append({"step": "advance_phase_ui", **state_summary})
        return True
    trace.append({"step": "advance_button_unavailable", **state_summary})
    return False


def run_playthrough(max_steps=1800):
    stamp = now_stamp()
    screenshot_dir = RECORD_DIR / stamp
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    trace = [{"step": "rules_loaded", "rules": read_rules_fingerprint()}]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pages, room_id, console_errors = setup_lobby(browser, trace, screenshot_dir)
        pages["B"].screenshot(path=screenshot_dir / "02_game_start_current_player.png", full_page=True)

        last_key = None
        stagnant = 0
        final_state = None
        for step in range(1, max_steps + 1):
            # Pick any page with state; states are broadcast to all connected pages.
            state = js_state(next(iter(pages.values())))
            if not state:
                time.sleep(0.2)
                continue
            final_state = state
            key = json.dumps(summarize_state(state), sort_keys=True, ensure_ascii=False)
            stagnant = stagnant + 1 if key == last_key else 0
            last_key = key

            if step in {20, 120, 240, 360}:
                page_for_current_player(pages, state).screenshot(path=screenshot_dir / f"{step:03d}_progress.png", full_page=True)

            if state.get("game_phase") == "finished" or state.get("winner"):
                trace.append({"step": "finished_detected", "iteration": step, "state": summarize_state(state)})
                break

            if handle_modal_or_pending(pages, state, trace):
                continue

            page = page_for_current_player(pages, state)
            phase = str(state.get("turn_phase") or "").lower()
            if phase == "action":
                play_action_phase(page, state, trace)
            else:
                advance_phase(page, state, trace)

            # Avoid endless loops on a non-changing state.
            if stagnant > 30:
                trace.append({"step": "stagnant_state_break", "iteration": step, "state": summarize_state(state)})
                break

        if final_state:
            page_for_current_player(pages, final_state).screenshot(path=screenshot_dir / "99_final_state.png", full_page=True)
        browser.close()

    result = {
        "passed": bool(final_state and final_state.get("game_phase") == "finished" and final_state.get("winner")) and not [e for e in console_errors if e.get("type") in {"error", "pageerror"}],
        "room_id": room_id,
        "screenshots": [str(p) for p in sorted(screenshot_dir.glob("*.png"))],
        "trace": trace,
        "final_state_summary": summarize_state(final_state),
        "final_state": final_state,
        "console_errors": console_errors,
    }
    json_path = RECORD_DIR / f"BROWSER_FULL_PLAYTHROUGH_{stamp}.json"
    md_path = RECORD_DIR / f"BROWSER_FULL_PLAYTHROUGH_{stamp}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    important = [item for item in trace if item["step"] in {"create_room", "choose_faction", "ready", "start_game_clicked", "finished_detected", "stagnant_state_break", "pending_choice_unresolved", "advance_button_unavailable"}]
    lines = [
        "# Browser Full Playthrough Validation",
        "",
        f"- passed: {result['passed']}",
        f"- room_id: {room_id}",
        f"- final_state_summary: {result['final_state_summary']}",
        f"- console_error_count: {len([e for e in console_errors if e.get('type') in {'error', 'pageerror'}])}",
        "",
        "## Important trace",
    ]
    for item in important[-80:]:
        lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
    lines.append("")
    lines.append("## Screenshots")
    for path in result["screenshots"]:
        lines.append(f"- {path}")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"passed": result["passed"], "json": str(json_path), "md": str(md_path), "screenshots": result["screenshots"], "final_state_summary": result["final_state_summary"], "console_errors": console_errors[-10:]}, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run_playthrough()
