import json
import random
import re
import shutil
import sys
import time
import hashlib
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE = Path(__file__).resolve().parent.parent
RECORD_DIR = BASE / "docs" / "records" / "full-playthrough"
BASE_URL = "http://127.0.0.1:8765"

PLAYER_SLOTS = ["A", "B", "C", "D"]
RED_ARMY_LABEL = "紅軍"


def fetch_faction_category_labels():
    # Read the live lobby category list from the server (server/main.py's
    # /factions route) instead of hardcoding it, so this stays in sync if
    # categories are ever added/renamed/removed there.
    with urllib.request.urlopen(BASE_URL + "/factions", timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [c["label"] for c in data.get("categories", []) if c.get("label")]


def build_random_faction_plan():
    # 紅軍 (Red Army) is the game's fixed opposing power: every match needs
    # exactly one Red Army player for the game to function, so that slot is
    # guaranteed while every player's faction (including which slot plays
    # Red Army) is otherwise randomized each run.
    labels = fetch_faction_category_labels()
    non_red_labels = [label for label in labels if label != RED_ARMY_LABEL]

    slots = list(PLAYER_SLOTS)
    random.shuffle(slots)
    red_slot, other_slots = slots[0], slots[1:]
    other_labels = random.sample(non_red_labels, len(other_slots))

    plan = {red_slot: RED_ARMY_LABEL}
    plan.update(dict(zip(other_slots, other_labels)))
    return [(slot, plan[slot]) for slot in PLAYER_SLOTS]

STATIC_COSTS = {
    0: {"name": "宣傳家", "money": 0, "propaganda": 3},
    1: {"name": "思想家", "money": 0, "propaganda": 5},
    2: {"name": "資助者", "money": 2, "propaganda": 1},
    3: {"name": "資本家", "money": 3, "propaganda": 2},
}

BUY_ATTEMPTS = set()


def now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def prune_previous_runs():
    # Screenshotting every step (see run_playthrough) makes each run ~380-470MB;
    # keep only the latest run on disk instead of accumulating unbounded local
    # history. Wipe everything already in RECORD_DIR before starting a new run.
    if not RECORD_DIR.exists():
        return
    for entry in RECORD_DIR.iterdir():
        if entry.name.startswith('.'):
            continue
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)


def screenshot_step(pages, state, screenshot_dir, seq, trace_entry):
    page = page_for_current_player(pages, state)
    step_name = re.sub(r"[^0-9A-Za-z_]+", "_", str(trace_entry.get("step") or "step"))
    try:
        page.screenshot(path=screenshot_dir / f"{seq:04d}_{step_name}.png", full_page=True)
    except Exception:
        pass


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


def setup_lobby(browser, trace, screenshot_dir, faction_plan):
    pages = {}
    console_errors = []
    for name, _ in faction_plan:
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

    for name, label in faction_plan:
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
    return {k: choice.get(k) for k in ["type", "choice_key", "interaction_kind", "player_id", "source", "step", "count", "min", "max"] if k in choice}


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
    # The per-turn event-card reveal ("目前事件" 放大檢視, #eventRevealModal) is a
    # click-anywhere-to-dismiss overlay with no button inside it at all; app.js only
    # closes it via a click on the overlay or the Escape key (see its keydown
    # handler). It auto-reopens on every new event, on any player's screen, so it
    # can end up covering whatever the bot tries to click next. Dismiss it first,
    # via the same Escape path the app already supports, before anything else.
    for page_name, page in pages.items():
        try:
            overlay = page.locator("#eventRevealModal")
            if overlay.count() and overlay.is_visible(timeout=150):
                page.keyboard.press("Escape")
                page.wait_for_timeout(150)
                trace.append({"step": "close_event_reveal_overlay_ui", "player_page": page_name})
                return True
        except Exception:
            continue

    choice = state.get("pending_choice") if state else None
    target_page = None
    if choice and choice.get("player_id"):
        target_page = page_for_player_id(pages, state, choice.get("player_id"))
    if not target_page:
        target_page = page_for_current_player(pages, state)

    # Build AND dissolve choices are intentionally handled on the strategic map UI
    # instead of a modal (see app.js's isMapBuildChoice/isMapDissolveChoice, which hide
    # #choiceModal entirely for these and highlight targets on the map instead). Select
    # the first highlighted town/target in the iframe, then click the map panel's
    # direct-build or dissolve button. interaction_kind === 'dissolve_organization'
    # covers every dissolve source generically (event/intel-network/era/etc.), matching
    # how the frontend itself dispatches on that field rather than choice_key.
    is_map_build_choice = bool(choice) and choice.get("choice_key") in {"event_build_organization", "era_red_build_near_target", "card_build_organization"}
    is_map_dissolve_choice = bool(choice) and choice.get("interaction_kind") == "dissolve_organization"
    if is_map_build_choice or is_map_dissolve_choice:
        action_kind = "dissolve" if is_map_dissolve_choice else "build"
        button_id = "dissolveBtn" if is_map_dissolve_choice else "directBuildBtn"
        towns = (choice.get("targets") if is_map_dissolve_choice else choice.get("towns")) or []
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
                        "actionKind": action_kind,
                        "choiceKey": choice.get("choice_key"),
                        "sourceName": choice.get("source_name") or choice.get("choice_key") or ("瓦解組織" if is_map_dissolve_choice else "建立組織"),
                        "prompt": choice.get("prompt") or ("請在戰略地圖點選要瓦解的組織。" if is_map_dissolve_choice else "事件卡效果：請在戰略地圖選擇可建立組織的城鎮。"),
                        "towns": [
                            {"town": entry.get("town"), "label": entry.get("label") or entry.get("town"), "index": idx}
                            for idx, entry in enumerate(towns)
                            if entry.get("town")
                        ],
                    }
                    frame.evaluate("payload => window.applySupportChoiceHighlight && window.applySupportChoiceHighlight(payload)", payload)
                    frame.evaluate("town => window.selectTownForCurrentMapAction(town, {autoFocus:false})", town)
                    frame.wait_for_function(f"!document.querySelector('#{button_id}').disabled", timeout=3000)
                    frame.locator(f"#{button_id}").click(timeout=3000)
                    target_page.wait_for_timeout(250)
                    trace.append({"step": "resolve_map_choice_ui", "action_kind": action_kind, "choice": summarize_choice(choice), "town": town})
                    return True
            except Exception as exc:
                trace.append({"step": "map_choice_ui_failed", "action_kind": action_kind, "choice": summarize_choice(choice), "town": town, "error": str(exc)})

    # multi_card_choice needs cards toggled first, then a separate submit button
    # clicked (#choiceModal .modal-choice-btn, disabled until the required count is
    # selected) — see app.js's multi_card_choice renderer. The generic "click first
    # enabled button" fallback below only ever hits the first card's toggle button,
    # which just selects/deselects it forever without ever reaching submit.
    if choice and choice.get("type") == "multi_card_choice":
        try:
            needed = choice.get("count")
            if needed is None:
                needed = choice.get("min") or 1
            card_buttons = target_page.locator("#choiceModal .choice-card-btn-multi")
            total = card_buttons.count()
            selected_count = target_page.locator("#choiceModal .choice-card-btn-multi.selected").count()
            picked = False
            for i in range(total):
                if selected_count >= needed:
                    break
                btn = card_buttons.nth(i)
                classes = btn.get_attribute("class") or ""
                if "selected" in classes.split():
                    continue
                if btn.is_visible(timeout=200) and btn.is_enabled(timeout=200):
                    btn.click(timeout=1200)
                    target_page.wait_for_timeout(120)
                    selected_count += 1
                    picked = True
            submit_btn = target_page.locator("#choiceModal .modal-choice-btn:visible:not([disabled])")
            if submit_btn.count():
                submit_btn.first.click(timeout=1200)
                target_page.wait_for_timeout(180)
                trace.append({"step": "resolve_multi_card_choice_ui", "choice": summarize_choice(choice), "needed": needed})
                return True
            if picked:
                trace.append({"step": "select_multi_card_choice_ui", "choice": summarize_choice(choice), "needed": needed, "selected_count": selected_count})
                return True
        except Exception as exc:
            trace.append({"step": "multi_card_choice_failed", "choice": summarize_choice(choice), "error": str(exc)})

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
    prune_previous_runs()
    stamp = now_stamp()
    screenshot_dir = RECORD_DIR / stamp
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    faction_plan = build_random_faction_plan()
    trace = [
        {"step": "rules_loaded", "rules": read_rules_fingerprint()},
        {"step": "faction_plan", "plan": faction_plan},
    ]
    print(json.dumps({"faction_plan": faction_plan}, ensure_ascii=False))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pages, room_id, console_errors = setup_lobby(browser, trace, screenshot_dir, faction_plan)
        pages["B"].screenshot(path=screenshot_dir / "02_game_start_current_player.png", full_page=True)

        last_key = None
        stagnant = 0
        final_state = None
        action_seq = 0
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

            if state.get("game_phase") == "finished" or state.get("winner"):
                trace.append({"step": "finished_detected", "iteration": step, "state": summarize_state(state)})
                break

            # Screenshot every actual player action/step (not just a handful of fixed
            # checkpoints), keyed off whether the call below actually appended a new
            # trace entry — pure no-ops (nothing clickable this iteration) don't count.
            trace_len_before = len(trace)

            if handle_modal_or_pending(pages, state, trace):
                if len(trace) > trace_len_before:
                    action_seq += 1
                    screenshot_step(pages, state, screenshot_dir, action_seq, trace[-1])
                continue

            page = page_for_current_player(pages, state)
            phase = str(state.get("turn_phase") or "").lower()
            if phase == "action":
                play_action_phase(page, state, trace)
            else:
                advance_phase(page, state, trace)

            if len(trace) > trace_len_before:
                action_seq += 1
                screenshot_step(pages, state, screenshot_dir, action_seq, trace[-1])

            # Avoid endless loops on a non-changing state.
            if stagnant > 30:
                trace.append({"step": "stagnant_state_break", "iteration": step, "state": summarize_state(state)})
                break

        if final_state:
            page_for_current_player(pages, final_state).screenshot(path=screenshot_dir / "99_final_state.png", full_page=True)
        browser.close()

    result = {
        "passed": bool(final_state and final_state.get("game_phase") == "finished" and final_state.get("winner")) and not [e for e in console_errors if e.get("type") in {"error", "pageerror"}],
        "faction_plan": faction_plan,
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

    important = [item for item in trace if item["step"] in {"faction_plan", "create_room", "choose_faction", "ready", "start_game_clicked", "finished_detected", "stagnant_state_break", "pending_choice_unresolved", "advance_button_unavailable"}]
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
    all_screenshots = result["screenshots"]
    lines.append(f"## Screenshots ({len(all_screenshots)} total, one per resolved step)")
    preview_screenshots = all_screenshots[:5] + (["…"] if len(all_screenshots) > 10 else []) + all_screenshots[-5:]
    for path in preview_screenshots:
        lines.append(f"- {path}")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({"passed": result["passed"], "faction_plan": faction_plan, "json": str(json_path), "md": str(md_path), "screenshot_count": len(all_screenshots), "screenshot_dir": str(screenshot_dir), "final_state_summary": result["final_state_summary"], "console_errors": console_errors[-10:]}, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run_playthrough()
