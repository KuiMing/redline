#!/usr/bin/env python3
"""客廳大螢幕（living-room）P0 瀏覽器 E2E：真實頁面 + mock bridge，固定按鍵序列（不用 BFS 探索）。

覆蓋：顯示模式切換／桌面不變、區域層與內容層、動作列只聚合可見啟用的既有控制、PLUS／ZR 只移焦點、
卡牌語意不退化（購買卡 A/B/X/Y、手牌 A/B/X/Y、checkbox 不進焦點）、處理中鎖、重繪不跨區域也不落在危險操作、
危險確認單預設返回、斷線／重連 baseline、PC 滑鼠勾選 checkbox、地圖兩段式清單（來源→合法目的地→明確確認）、
地圖 iframe 執行確認（沒有 iframe／逾時／過期回覆／ok:false 皆 fail closed，只有 ok:true 記錄冷卻與處理中鎖）、
720p／1080p／4K 三種解析度的安全區、無 overflow 與無遮擋，並輸出截圖。

執行（自動啟動隔離 server，不碰 8100／8200）：
  uv run python scripts/validate/validate_living_room_controller.py
輸出：$REDLINE_LIVING_ROOM_PROOF_DIR（預設 /private/tmp/redline-living-room-proof/；不要 commit）
"""

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_joycon_controller import BIT, MOCK_WS, Pad, enable_controller, post_json, start_server  # noqa: E402

BIT.setdefault("ZR", (0, 0x80))  # 客廳模式額外用到 ZR（bridge S2B1 b0 0x80）

OUT = Path(os.environ.get("REDLINE_LIVING_ROOM_PROOF_DIR", "/private/tmp/redline-living-room-proof"))
HAND = ["追隨者", "樂捐者", "追隨者", "歐洲奧援", "追隨者"]
RESOLUTIONS = [(1280, 720), (1920, 1080), (3840, 2160)]
LR_STATE = "RedlineController.getState().livingRoom"

SPY = """
() => {
  window.__spy = { sendAction: 0, calls: [], play: [], toggle: 0, preview: 0 };
  window.__dropSends = false;
  const send = window.sendAction;
  window.sendAction = function (...a) { window.__spy.sendAction += 1; window.__spy.calls.push(a[0]); if (window.__dropSends) return; return send.apply(this, a); };
  const play = window.playHandCard;
  window.playHandCard = function (...a) { window.__spy.play.push([a[0], a[1], a[2]]); return play.apply(this, a); };
  const tog = window.togglePurchaseSelection;
  window.togglePurchaseSelection = function (...a) { window.__spy.toggle += 1; return tog.apply(this, a); };
  const prev = window.selectCardDetail;
  window.selectCardDetail = function (...a) { window.__spy.preview += 1; return prev.apply(this, a); };
  window.__synthetic = 0;
  for (const type of ['mousedown', 'mouseup', 'pointerdown', 'keydown', 'keyup']) {
    document.addEventListener(type, e => { if (!e.isTrusted) window.__synthetic += 1; }, true);
  }
}
"""

FOCUS_PROBE = """() => { const el = document.querySelector('.rl-pad-focus'); if (!el) return null;
  return { tag: el.tagName, id: el.id || null, type: el.type || null, card: el.matches('.card[data-card-zone]'),
           zone: el.closest('[data-card-zone]')?.dataset.cardZone || null, name: el.dataset.cardName || null,
           slot: el.dataset.slotId || null, town: el.dataset.town || null, inModal: !!el.closest('.modal-overlay') }; }"""

GEOMETRY = """() => {
  const vw = innerWidth, vh = innerHeight;
  const stage = document.getElementById('designStage').getBoundingClientRect();
  const scale = stage.width / 1280;
  const r = id => { const e = document.getElementById(id); if (!e) return null; const b = e.getBoundingClientRect(); return { left: b.left, top: b.top, right: b.right, bottom: b.bottom }; };
  const view = document.querySelector('.game-view.active').getBoundingClientRect();
  const bar = r('lrBar');
  const fontPx = sel => { const e = document.querySelector(sel); return e ? parseFloat(getComputedStyle(e).fontSize) : null; };
  const focus = document.querySelector('.rl-pad-focus');
  let focusHit = null;
  if (focus) {
    const b = focus.getBoundingClientRect();
    const hit = document.elementFromPoint((b.left + b.right) / 2, Math.min(b.bottom - 4, (b.top + b.bottom) / 2));
    focusHit = !!hit && (focus === hit || focus.contains(hit));
  }
  const tabs = document.getElementById('gameTabs');
  return {
    vw, vh, scale,
    margins: { left: stage.left / vw, right: (vw - stage.right) / vw, top: stage.top / vh, bottom: (vh - stage.bottom) / vh },
    docOverflowX: document.documentElement.scrollWidth > vw, docOverflowY: document.documentElement.scrollHeight > vh,
    barInsideStage: !!bar && bar.left >= stage.left - 1 && bar.right <= stage.right + 1 && bar.bottom <= stage.bottom + 1,
    viewAboveBar: !!bar && view.bottom <= bar.top + 1,
    tabsOverflow: tabs.scrollWidth > tabs.clientWidth + 1,
    hudChipsSingleLine: [...document.querySelectorAll('#hudMainRow .hud-chip')].every(c => c.getBoundingClientRect().height / scale <= 40),
    focusHit,
    fontDu: { slot: fontPx('.lr-slot, .lr-slot-empty'), legend: fontPx('#lrLegend'), zoneLabel: fontPx('#lrZoneLabel'), title: fontPx('#handPanel .panel-title'), hud: fontPx('#hud') },
  };
}"""


def timed_presses(page, buttons, gap_ms):
    """在頁面內以固定間隔送出完整按下／放開（與 bridge 同一路徑），用來決定性地驗證 250ms 執行冷卻。"""
    page.evaluate("""async ([buttons, gap]) => {
      const bit = { A: [0x08, 0], B: [0x04, 0], X: [0x02, 0], Y: [0x01, 0] };
      for (let i = 0; i < buttons.length; i++) {
        const [b0, b1] = bit[buttons[i]];
        window.__padSend(0, 0, b0, b1);
        window.__padSend(0, 0, 0, 0);
        if (i < buttons.length - 1) await new Promise(r => setTimeout(r, gap));
      }
    }""", [list(buttons), gap_ms])
    page.wait_for_timeout(150)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks, console_errors = [], []

    def record(name, ok, detail=None):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {json.dumps(detail, ensure_ascii=False, default=str)[:600]}"))

    server = None
    base = os.environ.get("REDLINE_BASE_URL", "").rstrip("/")
    if not base:
        server, base = start_server()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)

            def new_game():
                setup = post_json(base, "/test/setup-move-confirmation-proof",
                                  {"mover_faction": "taiwan_green", "mover_base": "新竹", "mover_town": "臺北", "moves_left": 5})
                hand = post_json(base, "/test/set-hand", {"game_id": setup["game_id"], "player_id": setup["player_id"],
                                                          "cards": HAND, "turn_phase": "action"})
                assert hand.get("success"), hand
                return setup

            def open_page(context, url):
                page = context.new_page()
                page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: console_errors.append(str(e)))
                page.goto(base + url, wait_until="networkidle")
                page.wait_for_selector("#gameShell", state="visible", timeout=15000)
                page.evaluate("() => window.closeEventReveal && closeEventReveal()")
                page.wait_for_timeout(300)
                return page

            # ================= 1. 桌面模式預設不變；設定面板切換顯示模式 =================
            setup = new_game()
            desk_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            desk_ctx.add_init_script(MOCK_WS)
            desk = open_page(desk_ctx, setup["url"])
            record("desktop_default_has_no_display_attribute",
                   desk.evaluate("document.documentElement.dataset.display === undefined && !document.getElementById('lrBar')"))
            record("desktop_stage_scale_unchanged",
                   abs(desk.evaluate("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale'))") - min(1280 / 1280, 800 / 720)) < 1e-6)
            # PC 滑鼠：原生 checkbox 照常勾選／取消（既有 handler）
            box = 'input[data-purchase-index="6"]'
            desk.click(box)
            first = desk.evaluate(f"document.querySelector('{box}').checked")
            desk.click(box)
            record("desktop_mouse_checkbox_toggles_via_existing_handler", first is True and desk.evaluate(f"document.querySelector('{box}').checked") is False)
            desk.click("#padToggleBtn")
            desk.select_option("#padDisplaySelect", "living-room")
            desk.wait_for_timeout(300)
            on = desk.evaluate("[document.documentElement.dataset.display, localStorage.getItem('redline.display.v1'), !document.getElementById('lrBar').hidden]")
            desk.select_option("#padDisplaySelect", "desktop")
            desk.wait_for_timeout(300)
            off = desk.evaluate("[document.documentElement.dataset.display || null, localStorage.getItem('redline.display.v1'), document.getElementById('lrBar').hidden]")
            record("settings_switch_toggles_mode_and_persists", on == ["living-room", "living-room", True] and off == [None, "desktop", True], [on, off])
            desk_ctx.close()

            # ================= 2. 客廳模式主流程 =================
            setup = new_game()
            ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
            ctx.add_init_script(MOCK_WS)
            page = open_page(ctx, setup["url"] + "&display=living-room")
            pad = Pad(page)
            lr = lambda: page.evaluate(LR_STATE)
            focus = lambda: page.evaluate(FOCUS_PROBE)
            spy = lambda: page.evaluate("JSON.parse(JSON.stringify(window.__spy))")
            checked = lambda: page.evaluate("[...document.querySelectorAll('input[data-purchase-index]')].filter(i => i.checked).map(i => i.dataset.purchaseIndex)")
            preview_open = lambda: page.evaluate("document.getElementById('cardPreviewModal').style.display === 'flex'")

            def wait_idle(ms=380):
                page.wait_for_timeout(ms)  # 大於 300ms 重繪冷卻

            record("url_param_enables_living_room_and_persists",
                   page.evaluate("[document.documentElement.dataset.display, localStorage.getItem('redline.display.v1')]") == ["living-room", "living-room"])
            enable_controller(page)
            page.evaluate(SPY)
            page.screenshot(path=str(OUT / "00_main_screen_before_input.png"))

            # ---- 第一次輸入只放區域焦點 ----
            pad.neutral()
            pad.tap("A")
            s = lr()
            record("first_input_places_zone_focus_only", s["layer"] == "zone" and s["zone"] == "hand" and spy()["sendAction"] == 0 and focus() is None, s)
            page.screenshot(path=str(OUT / "01_zone_focus_hand.png"))

            # ---- 區域層：R/SR 環、搖桿在區域間 ----
            pad.tap("R")
            r1 = lr()["zone"]
            pad.tap("SR")
            record("R_SR_cycle_zone_ring_without_entering", r1 == "map" and lr()["zone"] == "hand" and lr()["layer"] == "zone"
                   and page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "command", r1)
            pad.push("up")
            up_zone = lr()["zone"]
            pad.push("left")
            left_zone = lr()["zone"]
            pad.push("right")
            record("stick_moves_between_market_zones", up_zone in ("static", "random") and left_zone == "static" and lr()["zone"] == "random"
                   and lr()["layer"] == "zone", [up_zone, left_zone, lr()["zone"]])
            pad.tap("B")
            record("B_noop_on_zone_layer", lr()["layer"] == "zone" and lr()["zone"] == "random" and spy()["sendAction"] == 0)

            # ---- 內容層：隨機購買區 ----
            pad.tap("A")
            f = focus()
            record("A_enters_zone_first_card", lr()["layer"] == "item" and f and f["card"] and f["zone"] == "purchase" and lr()["itemKey"] == "purchase:6", [lr(), f])
            bad = []
            for d in ["right", "right", "down", "right", "up", "right", "right", "left", "left", "left", "left", "left"]:
                pad.push(d)
                p = focus()
                if not p or p["tag"] == "INPUT" or not p["card"] or lr()["zone"] != "random":
                    bad.append(p)
            record("semantic_nav_stays_in_zone_never_on_checkbox", not bad and lr()["itemKey"] == "purchase:6", bad[:3])
            pad.tap("B")
            page.wait_for_timeout(250)
            after_check = checked()
            slots = [x["id"] for x in lr()["slots"]]
            record("purchase_card_B_toggles_existing_checkbox", after_check == ["6"] and spy()["toggle"] == 1 and spy()["sendAction"] == 0, after_check)
            expected = page.evaluate("""() => ['openPurchaseConfirmBtn','clearPurchaseSelectionBtn','topdeckRightBtn','redArmyAbilityBtn','advanceStepBtn']
              .filter(id => { const e = document.getElementById(id); if (!e) return false; const r = e.getBoundingClientRect();
                return r.width > 0 && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden' && !e.disabled && e.getAttribute('aria-disabled') !== 'true'; })""")
            # 資金 0 時「購買所選」既有按鈕是 disabled → 動作列不得出現；「清除」可用 → 必須出現。
            buy_disabled = page.evaluate("document.getElementById('openPurchaseConfirmBtn').disabled")
            record("action_bar_mirrors_exactly_visible_enabled_controls",
                   slots == expected and "clearPurchaseSelectionBtn" in slots and ("openPurchaseConfirmBtn" in slots) == (not buy_disabled), [slots, expected, buy_disabled])
            page.screenshot(path=str(OUT / "02_content_focus_random_card_checked.png"))
            before = spy()
            pad.tap("X")
            pad.tap("Y")
            record("purchase_card_X_Y_full_noop", spy()["play"] == before["play"] and spy()["sendAction"] == 0 and checked() == ["6"]
                   and lr()["itemKey"] == "purchase:6" and not page.evaluate("RedlineController.getState().helpOpen"), spy())
            pad.tap("A")
            page.wait_for_timeout(250)
            record("purchase_card_A_previews_only", preview_open() and spy()["preview"] == 1 and checked() == ["6"] and spy()["toggle"] == 1)
            pad.tap("B")
            page.wait_for_timeout(300)
            record("preview_B_closes_and_focus_returns_to_same_card", not preview_open() and lr()["itemKey"] == "purchase:6" and (focus() or {}).get("card"), [lr(), focus()])
            pad.tap("B")
            page.wait_for_timeout(250)
            record("purchase_card_B_toggles_off", checked() == [] and spy()["toggle"] == 2)
            # enabled 但被隱藏的 checkbox：B 完全 no-op
            page.evaluate("document.querySelector('input[data-purchase-index=\"6\"]').style.display = 'none'")
            wait_idle()
            pad.tap("B")
            page.wait_for_timeout(250)
            record("purchase_card_B_noop_when_enabled_checkbox_hidden", checked() == [] and spy()["toggle"] == 2)
            page.evaluate("document.querySelector('input[data-purchase-index=\"6\"]').style.display = ''")
            wait_idle()
            # 250ms 執行冷卻：成功的 B 勾選後 120ms 內再按 B 不得把勾選取消；失敗（隱藏 checkbox）的 B 不啟動冷卻。
            toggles = spy()["toggle"]
            timed_presses(page, ["B", "B"], 120)
            double_b = (checked(), spy()["toggle"] - toggles)
            wait_idle()
            pad.tap("B")
            page.wait_for_timeout(250)
            record("cooldown_successful_B_blocks_second_toggle_within_250ms", double_b == (["6"], 1) and checked() == [],
                   [double_b, checked()])
            page.evaluate("document.querySelector('input[data-purchase-index=\"6\"]').style.display = 'none'")
            wait_idle()
            toggles = spy()["toggle"]
            page.evaluate("""async () => {
              window.__padSend(0, 0, 0x04, 0); window.__padSend(0, 0, 0, 0);   // B on hidden checkbox → no-op
              document.querySelector('input[data-purchase-index="6"]').style.display = '';
              await new Promise(r => setTimeout(r, 120));
              window.__padSend(0, 0, 0x04, 0); window.__padSend(0, 0, 0, 0);   // legit B 120ms later
            }""")
            page.wait_for_timeout(250)
            record("cooldown_failed_B_does_not_block_next_legit_toggle", checked() == ["6"] and spy()["toggle"] - toggles == 1,
                   [checked(), spy()["toggle"] - toggles])
            wait_idle()
            pad.tap("B")
            page.wait_for_timeout(250)
            # TV 模式下滑鼠仍可直接勾選原生 checkbox
            page.click('input[data-purchase-index="7"]')
            page.wait_for_timeout(250)
            mouse_on = checked()
            page.click('input[data-purchase-index="7"]')
            page.wait_for_timeout(250)
            record("living_room_mouse_checkbox_still_works", mouse_on == ["7"] and checked() == [], mouse_on)

            # ---- ZR 回區域層；常設區停用 checkbox（分神／內鬥）B no-op ----
            pad.tap("ZR")
            record("ZR_returns_to_zone_layer_same_zone", lr()["layer"] == "zone" and lr()["zone"] == "random" and focus() is None)
            pad.push("left")
            pad.tap("A")
            wait_idle()  # 進入區域本身會啟動 250ms 執行冷卻
            toggles_before = spy()["toggle"]
            disabled_idx = page.evaluate("[...document.querySelectorAll('#purchaseStatic .card[data-card-zone=\"purchase\"]')].findIndex(c => c.querySelector('input:disabled'))")
            for _ in range(disabled_idx):
                pad.push("right")
            f = focus()
            pad.tap("B")
            page.wait_for_timeout(250)
            record("disabled_checkbox_card_B_noop", disabled_idx >= 0 and f and f["card"] and checked() == [] and spy()["toggle"] == toggles_before,
                   [disabled_idx, f, toggles_before, spy()["toggle"]])
            pad.tap("ZR")

            # ---- 手牌：A 查看、B no-op、X 資源、Y 行動；處理中鎖；重繪規則 ----
            for _ in range(4):
                if lr()["zone"] == "hand":
                    break
                pad.tap("R")
            pad.tap("A")
            record("hand_zone_enter_first_card", lr()["itemKey"] == "hand:0:追隨者", lr())
            pad.push("right")
            record("hand_right_moves_by_index", lr()["itemKey"] == "hand:1:樂捐者", lr())
            page.screenshot(path=str(OUT / "03_content_focus_hand_card.png"))
            pad.tap("A")
            page.wait_for_timeout(250)
            ok_preview = preview_open() and spy()["play"] == []
            pad.tap("B")
            page.wait_for_timeout(250)
            pad.tap("B")
            page.wait_for_timeout(250)
            record("hand_A_previews_B_noop_stays_in_item_layer", ok_preview and not preview_open() and lr()["layer"] == "item"
                   and lr()["itemKey"] == "hand:1:樂捐者" and spy()["play"] == [] and spy()["sendAction"] == 0, lr())
            # 處理中鎖：讓送出不到伺服器（沒有新 state），Y 後立刻 X 不得再送出；逾時後解鎖。
            page.evaluate("window.__dropSends = true")
            pad.tap("Y")
            page.wait_for_timeout(300)  # 超過 250ms 執行冷卻：此時擋下 X 的只會是處理中鎖
            pad.tap("X")
            locked = spy()["play"]
            busy = lr()["processing"]
            status = page.evaluate("document.getElementById('lrBarStatus').textContent")
            page.wait_for_timeout(1700)
            pad.tap("X")
            record("processing_lock_blocks_second_submit_until_timeout",
                   locked == [[1, "樂捐者", "action"]] and busy and "處理中" in status and spy()["play"][-1] == [1, "樂捐者", "resource"],
                   [locked, busy, status, spy()["play"]])
            page.evaluate("window.__dropSends = false")
            page.wait_for_timeout(1600)  # 上一次（被丟棄的）送出鎖逾時
            # 真實送出：Y 行動 → 伺服器 state → 手牌重繪；焦點留在手牌同索引，不跨區、不落在動作列
            n_play = len(spy()["play"])
            hand_before = page.evaluate("document.querySelectorAll('#hand .hand-card').length")
            pad.tap("Y")
            page.wait_for_function(f"document.querySelectorAll('#hand .hand-card').length === {hand_before - 1}", timeout=5000)
            wait_idle(500)
            s = lr()
            record("hand_Y_plays_action_via_existing_button", spy()["play"][n_play:] == [[1, "樂捐者", "action"]], spy()["play"])
            record("redraw_keeps_zone_and_index_after_card_removed", s["zone"] == "hand" and s["layer"] == "item"
                   and s["itemKey"] == "hand:1:追隨者" and not s["processing"], s)
            pad.tap("X")
            page.wait_for_timeout(500)
            record("hand_X_plays_resource_via_existing_button", spy()["play"][-1] == [1, "追隨者", "resource"], spy()["play"][-3:])
            wait_idle(500)
            # 手牌 [追隨者, 歐洲奧援, 追隨者]：同位置換成別張 → 焦點留在索引 1，不會跳去另一張同名追隨者
            record("redraw_with_duplicate_names_stays_on_same_index", lr()["itemKey"] == "hand:1:歐洲奧援", lr())
            # 一般奧援：X 是「棄置」→ fail-closed；動作列出現需確認的「棄置」格
            for _ in range(4):
                if (focus() or {}).get("name") == "歐洲奧援":
                    break
                pad.push("right")
            n_play = len(spy()["play"])
            pad.tap("X")
            slots_now = lr()["slots"]
            record("support_card_X_never_discards", (focus() or {}).get("name") == "歐洲奧援" and len(spy()["play"]) == n_play, [focus(), spy()["play"][-2:]])
            record("action_bar_offers_discard_as_danger_slot", any(x["id"] == "handDiscard" and x["danger"] and "歐洲奧援" in x["label"] for x in slots_now), slots_now)
            # 重繪：同一份 state 重新 render → 同 key；移除焦點卡 → 同索引；手牌清空 → 回區域層（非動作列）
            key_before = lr()["itemKey"]
            page.evaluate("render(window.lastGameState)")
            wait_idle()
            same = lr()["itemKey"] == key_before and page.evaluate("!!document.querySelector('#hand .hand-card.rl-pad-focus')")
            page.evaluate("""() => { const s = structuredClone(window.lastGameState); const me = s.players.find(p => p.id === playerId);
              me.hand = []; me.hand_variants = []; me.hand_action_legality = []; render(s); }""")
            wait_idle()
            emptied = lr()
            page.evaluate("render(window.lastGameState)")
            wait_idle()
            record("redraw_same_state_rebinds_same_card", same, key_before)
            record("redraw_empty_zone_falls_back_to_zone_layer_not_action_bar", emptied["layer"] == "zone" and emptied["zone"] not in ("actionbar", None), emptied)

            # ---- PLUS：只聚焦動作列；動作列消失的格不會把焦點推到危險操作 ----
            n_send = spy()["sendAction"]
            pad.tap("PLUS")
            s = lr()
            record("PLUS_focuses_action_bar_without_executing", s["zone"] == "actionbar" and s["layer"] == "item" and spy()["sendAction"] == n_send
                   and not s["confirmOpen"], s)
            page.screenshot(path=str(OUT / "04_action_bar_focus.png"))
            # 勾一張購買卡讓動作列出現「清除」，焦點放在「清除」後由滑鼠清除選取：
            # 該格消失、同索引落在危險格（棄置／結束）→ 必須回動作列的區域層，而不是停在危險操作。
            page.click('input[data-purchase-index="6"]')
            wait_idle()
            pad.tap("PLUS")
            for _ in range(len(lr()["slots"])):
                if lr()["itemKey"] == "slot:clearPurchaseSelectionBtn":
                    break
                pad.push("right")
            on_clear = lr()["itemKey"]
            record("action_bar_buy_label_shows_selected_count_when_present",
                   all("1 張" in x["label"] for x in lr()["slots"] if x["id"] == "openPurchaseConfirmBtn"), lr()["slots"])
            page.click("#clearPurchaseSelectionBtn")
            wait_idle(500)
            s = lr()
            record("vanished_slot_never_lands_on_danger", on_clear == "slot:clearPurchaseSelectionBtn" and s["zone"] == "actionbar"
                   and s["layer"] == "zone" and focus() is None, [on_clear, s])
            # 250ms 執行冷卻：A 進入動作列後 120ms 內的第二個 A 不得執行剛聚焦的第一格（「清除」）
            page.click('input[data-purchase-index="6"]')
            wait_idle()
            timed_presses(page, ["A", "A"], 120)
            entered = lr()
            record("cooldown_enter_action_bar_then_rapid_A_does_not_execute_first_slot",
                   entered["layer"] == "item" and entered["itemKey"] == "slot:clearPurchaseSelectionBtn" and checked() == ["6"], [entered, checked()])
            wait_idle()
            pad.tap("A")
            page.wait_for_timeout(300)
            record("cooldown_then_deliberate_A_executes_slot", checked() == [], checked())
            wait_idle()
            pad.tap("ZR")

            # ---- 斷線／重連：重連時按住 A+PLUS 不觸發 ----
            snapshot_before = (lr()["zone"], lr()["layer"], spy()["sendAction"])
            page.evaluate("window.__padHeartbeat = false")
            page.evaluate("window.__padClose()")
            page.wait_for_function("RedlineController.getState().status !== 'connected'", timeout=3000)
            alert = page.evaluate("document.getElementById('lrBarStatus').dataset.alert")
            page.evaluate("window.__padLast = [0, 0, 0x08, 0x02]; window.__padHeartbeat = true")
            page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
            page.wait_for_timeout(500)
            record("reconnect_with_held_A_PLUS_fires_nothing", (lr()["zone"], lr()["layer"], spy()["sendAction"]) == snapshot_before and alert == "true",
                   [snapshot_before, lr(), alert])
            pad.neutral()
            page.evaluate("window.__padHeartbeat = false")
            page.wait_for_function("RedlineController.getState().status === 'stale'", timeout=5000)
            record("stale_signal_shows_alert_banner", page.evaluate("document.getElementById('lrBarStatus').dataset.alert") == "true"
                   and "訊號中斷" in page.evaluate("document.getElementById('lrBarStatus').textContent"))
            page.evaluate("window.__padHeartbeat = true")
            pad.neutral()
            page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=3000)

            # ---- 地圖：兩段式清單（來源 → 合法目的地 → 明確確認） ----
            for _ in range(8):
                if lr()["zone"] == "map":
                    break
                pad.tap("R")
            pad.tap("A")
            page.wait_for_function("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=5000)
            page.wait_for_function("document.getElementById('strategicMapFrame').contentWindow.lastGameState", timeout=20000)
            page.wait_for_function(f"{LR_STATE}.mapStage === 'source'", timeout=15000)
            wait_idle(800)
            mframe = next(fr for fr in page.frames if "leaflet_game_map" in fr.url)
            snap = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
            s = lr()
            origins = sorted(t["town"] for t in snap["targets"] if t["role"] == "origin")
            record("map_portal_enters_list_on_source_stage", s["zone"] == "maplist" and s["layer"] == "item" and sorted(s["mapRows"]) == origins and origins, [s, origins])
            # 250ms 執行冷卻：ZR 回清單區域層後，A 進入清單、120ms 內的第二個 A 不得選取第一個來源
            pad.tap("ZR")
            wait_idle()
            timed_presses(page, ["A", "A"], 120)
            page.wait_for_timeout(300)
            s2 = lr()
            record("cooldown_enter_map_list_then_rapid_A_does_not_pick_origin",
                   s2["zone"] == "maplist" and s2["layer"] == "item" and s2["mapStage"] == "source"
                   and (focus() or {}).get("town") == s2["mapRows"][0] and mframe.evaluate("selectedTown") is None, [s2, focus()])
            wait_idle()
            origin = mframe.evaluate("(names) => names.find(n => { const o = movementOptionsForTown(n); return o.road.length + o.rail.length > 0; })", s["mapRows"])
            idx = s["mapRows"].index(origin)
            for _ in range(idx):
                pad.push("down")
            record("map_list_focus_drives_iframe_focus_ring", page.evaluate("RedlineController.getState().livingRoom.mapRows")[idx] == origin
                   and (focus() or {}).get("town") == origin and mframe.evaluate("document.querySelectorAll('.pad-focus-label').length") == 1, focus())
            page.screenshot(path=str(OUT / "05_map_list_source.png"))
            pad.tap("A")
            page.wait_for_function(f"{LR_STATE}.mapStage === 'destination'", timeout=5000)
            wait_idle()
            s = lr()
            legal = sorted(set(mframe.evaluate("selectedMoveTargets.map(t => t.town)")))
            record("map_destination_rows_equal_server_legal_moves", s["mapSelected"] == origin and sorted(s["mapRows"]) == legal and legal, [s["mapRows"], legal])
            pad.tap("B")
            page.wait_for_function(f"{LR_STATE}.mapStage === 'source'", timeout=5000)
            record("map_B_cancels_source_via_existing_flow", mframe.evaluate("selectedTown") is None and lr()["layer"] == "item")
            wait_idle()
            # 清單換段後焦點回到第一列：固定往下 idx 次回到同一個來源
            record("map_stage_change_resets_to_first_row", (focus() or {}).get("town") == lr()["mapRows"][0], focus())
            for _ in range(idx):
                pad.push("down")
            pad.tap("A")
            page.wait_for_function(f"{LR_STATE}.mapStage === 'destination'", timeout=5000)
            wait_idle()
            dest = lr()["mapRows"][0]
            pad.tap("A")
            page.wait_for_function(f"!!{LR_STATE}.mapPending", timeout=5000)
            wait_idle()
            s = lr()
            pending = mframe.evaluate("pendingMoveTarget")
            record("map_A_on_destination_only_arms_confirm", pending and pending["to"] == dest and mframe.evaluate("pendingMove") is None
                   and s["mapPending"]["to"] == dest and s["layer"] == "item" and s["zone"] == "maplist", [pending, s])
            confirm_slot = next((x for x in s["slots"] if x["id"] == "confirmMoveBtn"), None)
            record("action_bar_shows_explicit_move_confirm", bool(confirm_slot) and f"{origin}→{dest}" in confirm_slot["label"], s["slots"])
            map_geo = page.evaluate("""() => {
              const bar = document.getElementById('lrBar').getBoundingClientRect();
              const view = document.getElementById('mapView').getBoundingClientRect();
              const panel = document.getElementById('lrMapPanel').getBoundingClientRect();
              const footer = document.getElementById('lrMapFooter'); const f = footer.getBoundingClientRect();
              const hit = document.elementFromPoint((f.left + f.right) / 2, (f.top + f.bottom) / 2);
              return { viewAboveBar: view.bottom <= bar.top + 1, panelAboveBar: panel.bottom <= bar.top + 1,
                       footerVisible: !!hit && footer.contains(hit), footer: footer.textContent };
            }""")
            record("map_view_and_target_panel_not_covered_by_action_bar",
                   map_geo["viewAboveBar"] and map_geo["panelAboveBar"] and map_geo["footerVisible"] and "已預備" in map_geo["footer"], map_geo)
            page.screenshot(path=str(OUT / "06_map_list_destination_pending.png"))
            pad.tap("PLUS")
            record("PLUS_on_map_focuses_confirm_slot", lr()["itemKey"] == "slot:confirmMoveBtn" and mframe.evaluate("pendingMove") is None, lr())
            wait_idle()

            # ---- 地圖 iframe 執行確認（req 對應）：只有 iframe 重驗後回覆 ok:true 才記錄 250ms 冷卻／處理中鎖 ----
            # (a) 沒有 iframe：指令送不出去 → 立即 fail closed
            before = lr()
            page.evaluate("document.getElementById('strategicMapFrame').id = 'strategicMapFrameDetached'")
            pad.tap("A")
            no_frame = lr()
            page.evaluate("document.getElementById('strategicMapFrameDetached').id = 'strategicMapFrame'")
            record("map_ack_no_iframe_fails_closed_without_cooldown_or_lock",
                   (no_frame["lastMapAck"] or {}).get("outcome") == "no-frame" and no_frame["activatedAt"] == before["activatedAt"]
                   and not no_frame["processing"] and no_frame["mapRequest"] is None and no_frame["itemKey"] == "slot:confirmMoveBtn"
                   and mframe.evaluate("pendingMove") is None, [before, no_frame])
            wait_idle()

            # (b) iframe 收不到指令：等待確認期間第二個 A 不重送；逾時後 fail closed；逾時後才到的成功回覆＝stale，忽略
            page.evaluate("""() => { const w = document.getElementById('strategicMapFrame').contentWindow;
              w.__dropped = []; w.__origPostMessage = w.postMessage;
              w.postMessage = function (msg) { w.__dropped.push(msg); }; }""")
            timed_presses(page, ["A", "A"], 120)
            inflight = lr()
            dropped = page.evaluate("""() => document.getElementById('strategicMapFrame').contentWindow.__dropped
              .filter(m => m.req).map(m => ({ cmd: m.cmd, id: m.id || null, req: m.req }))""")
            record("map_ack_in_flight_blocks_duplicate_send",
                   len(dropped) == 1 and dropped[0]["id"] == "confirmMoveBtn" and bool(inflight["mapRequest"])
                   and inflight["mapRequest"]["req"] == dropped[0]["req"] and inflight["activatedAt"] == before["activatedAt"]
                   and not inflight["processing"], [dropped, inflight])
            page.wait_for_timeout(1100)
            timed_out = lr()
            record("map_ack_timeout_fails_closed_without_cooldown_or_lock",
                   timed_out["mapRequest"] is None and (timed_out["lastMapAck"] or {}).get("outcome") == "timeout"
                   and dropped and timed_out["lastMapAck"]["req"] == dropped[0]["req"]
                   and timed_out["activatedAt"] == before["activatedAt"] and not timed_out["processing"], timed_out)
            # 由 iframe 自己的 realm 送出（source 通過驗證），只有 req 已過期
            mframe.evaluate("""(req) => window.parent.postMessage({ type: 'redline-controller-result', v: 1, cmd: 'button', req,
              ok: true, reason: null, via: 'confirmMoveBtn' }, location.origin)""", dropped[0]["req"] if dropped else 1)
            page.wait_for_timeout(150)
            late = lr()
            page.evaluate("""() => { const w = document.getElementById('strategicMapFrame').contentWindow;
              w.postMessage = w.__origPostMessage; delete w.__origPostMessage; }""")
            record("map_ack_late_success_after_timeout_is_stale_and_ignored",
                   late["lastMapAck"] == timed_out["lastMapAck"] and late["activatedAt"] == before["activatedAt"]
                   and not late["processing"] and mframe.evaluate("pendingMove") is None, late)
            wait_idle()

            # (c) iframe 重驗失敗（確認鈕在 iframe 內被停用）→ ok:false；iframe 隨後恢復按鈕。
            #     120ms 後（250ms 冷卻內）的合法 A 不得被擋下：這次 ok:true，才記錄冷卻並上處理中鎖，移動送出。
            before = lr()
            page.evaluate("""() => { window.__mapResults = [];
              window.addEventListener('message', e => { if (e.data && e.data.type === 'redline-controller-result' && e.data.req) window.__mapResults.push(e.data); }); }""")
            pre = mframe.evaluate("""() => {
              const btn = document.getElementById('confirmMoveBtn');
              const restore = (e) => {
                if (!e.data || e.data.type !== 'redline-controller-command' || e.data.cmd !== 'button') return;
                window.removeEventListener('message', restore);
                window.__restoredFor = e.data.req;
                btn.disabled = false;
                map.fire('moveend');
              };
              window.addEventListener('message', restore);
              btn.disabled = true;
              return { disabled: btn.disabled, buttons: window.__redlineControllerAdapter.snapshot().buttons.map(b => b.id) };
            }""")
            # 失敗回覆一到就立刻按下一個 A（不靠固定 sleep），gap 必須 < 250ms
            seq = page.evaluate("""async () => {
              const st = () => { const s = RedlineController.getState().livingRoom;
                return { activatedAt: s.activatedAt, processing: s.processing, mapRequest: s.mapRequest, lastMapAck: s.lastMapAck, itemKey: s.itemKey }; };
              const press = () => { window.__padSend(0, 0, 0x08, 0); window.__padSend(0, 0, 0, 0); };
              const sleep = ms => new Promise(r => setTimeout(r, ms));
              const t0 = performance.now();
              press();
              const sent = st();
              while (st().mapRequest && performance.now() - t0 < 200) await sleep(5);
              const failed = st();
              await sleep(20);
              const t1 = performance.now();
              press();
              const t2 = performance.now();
              while (st().mapRequest && performance.now() - t2 < 500) await sleep(5);
              return { sent, failed, ok: st(), gap: t1 - t0 };
            }""")
            sent, failed, acked = seq["sent"], seq["failed"], seq["ok"]
            seq["pre"] = pre
            seq["results"] = page.evaluate("window.__mapResults || []")
            seq["restoredFor"] = mframe.evaluate("window.__restoredFor || null")
            # 缺資料時讓檢查以 FAIL＋detail 呈現，而不是 KeyError／TypeError 中斷整個 validator
            results = seq["results"] or []
            first = results[0] if len(results) > 0 else {}
            second = results[1] if len(results) > 1 else {}
            sent_req = (sent.get("mapRequest") or {}).get("req")
            failed_ack = failed.get("lastMapAck") or {}
            acked_ack = acked.get("lastMapAck") or {}
            record("map_ack_ok_false_fails_closed_without_cooldown_or_lock",
                   (pre or {}).get("disabled") is True and "confirmMoveBtn" not in ((pre or {}).get("buttons") or [])
                   and sent_req is not None and first.get("req") == sent_req
                   and first.get("ok") is False and first.get("reason") == "button-unavailable"
                   and sent.get("activatedAt") == before["activatedAt"] and not sent.get("processing")
                   and failed_ack.get("req") == sent_req and failed_ack.get("outcome") == "failed"
                   and failed.get("mapRequest") is None
                   and failed.get("activatedAt") == before["activatedAt"] and not failed.get("processing"), seq)
            record("map_ack_failure_does_not_block_next_legal_action_within_250ms",
                   isinstance(seq.get("gap"), (int, float)) and seq["gap"] < 250
                   and sent_req is not None and acked_ack.get("outcome") == "success"
                   and acked_ack.get("req") is not None and acked_ack.get("req") != sent_req
                   and second.get("req") == acked_ack.get("req") and second.get("ok") is True, seq)
            record("map_ack_success_records_cooldown_and_processing_lock",
                   (acked["lastMapAck"] or {}).get("lock") is True and acked["activatedAt"] is not None
                   and acked["activatedAt"] != before["activatedAt"] and acked["mapRequest"] is None, seq)
            page.wait_for_function(
                f"(() => {{ const t = document.getElementById('strategicMapFrame').contentWindow.lastGameState?.map?.towns?.['{dest}'] || []; return t.some(e => e.player === 'mover'); }})()",
                timeout=8000)
            record("map_move_executes_only_after_explicit_confirm", True)
            wait_idle(600)
            s = lr()
            # 確認格隨 state 消失；同索引是「結束行動」（危險）→ 必須退到動作列區域層
            record("after_confirm_vanished_slot_falls_back_to_zone_layer", s["zone"] == "actionbar" and s["layer"] == "zone" and focus() is None, s)
            pad.tap("ZR")
            page.wait_for_function("document.querySelector('.game-tab.active').dataset.view === 'command'", timeout=5000)
            wait_idle()
            record("ZR_on_map_zone_layer_returns_to_command_map_zone", lr()["zone"] == "map" and lr()["layer"] == "zone", lr())

            # ---- 危險操作：結束行動確認單，預設返回 ----
            pad.tap("PLUS")
            for _ in range(len(lr()["slots"])):
                if lr()["itemKey"] == "slot:advanceStepBtn":
                    break
                pad.push("right")
            n_send = spy()["sendAction"]
            # A 開啟確認單；120ms 後（焦點已在「返回」）的第二個 A 屬於 250ms 冷卻內 → 必須被忽略，確認單仍開著
            timed_presses(page, ["A", "A"], 120)
            page.wait_for_timeout(150)
            record("cooldown_modal_A_within_250ms_after_open_is_ignored",
                   page.evaluate("document.getElementById('lrConfirmModal').style.display") == "flex"
                   and (focus() or {}).get("id") == "lrConfirmCancelBtn" and spy()["sendAction"] == n_send, focus())
            f = focus()
            record("danger_confirm_opens_with_cancel_focused", page.evaluate("document.getElementById('lrConfirmModal').style.display") == "flex"
                   and f and f["id"] == "lrConfirmCancelBtn" and spy()["sendAction"] == n_send, f)
            page.screenshot(path=str(OUT / "07_danger_confirm_default_cancel.png"))
            pad.tap("A")
            page.wait_for_timeout(300)
            record("danger_confirm_A_on_default_cancels", page.evaluate("document.getElementById('lrConfirmModal').style.display") == "none"
                   and spy()["sendAction"] == n_send and lr()["itemKey"] == "slot:advanceStepBtn", lr())
            pad.tap("A")
            page.wait_for_timeout(300)
            pad.tap("B")
            page.wait_for_timeout(300)
            record("danger_confirm_B_cancels", page.evaluate("document.getElementById('lrConfirmModal').style.display") == "none" and spy()["sendAction"] == n_send)
            pad.tap("A")
            page.wait_for_timeout(300)
            pad.push("right")
            ok_focus = (focus() or {}).get("id")
            # 送出前的權威狀態（動態讀取，不寫死玩家名稱）
            before_advance = page.evaluate("({ phase: window.lastGameState.turn_phase, current: window.lastGameState.current_player })")
            pad.tap("A")
            pad.tap("A")
            pad.tap("A")
            page.wait_for_timeout(800)
            calls = spy()["calls"][n_send:]
            record("danger_confirm_executes_once_after_explicit_confirm", ok_focus == "lrConfirmOkBtn" and calls == ["advance"], [ok_focus, calls])
            # 下一位玩家可能同樣在 action 階段，所以只驗證「送出前那位玩家的那個階段」已結束：
            # 階段改變，或目前玩家已不是送出前的玩家。
            try:
                page.wait_for_function(
                    """(b) => { const s = window.lastGameState; return !!s && (s.turn_phase !== b.phase || s.current_player !== b.current); }""",
                    arg=before_advance, timeout=8000)
                left = True
            except Exception:
                left = False
            record("advance_reached_server_and_left_pre_action_player_phase", left, page.evaluate(
                """(b) => ({ before: b, phase: window.lastGameState.turn_phase, turn: window.lastGameState.turn, current: window.lastGameState.current_player,
                    phaseChanged: window.lastGameState.turn_phase !== b.phase, playerChanged: window.lastGameState.current_player !== b.current,
                    log: (window.lastGameState.action_log || []).slice(-4),
                    error: window.lastGameState.error || null, btn: document.getElementById('advanceStepBtn').textContent,
                    pending: window.lastGameState.pending_choice ? window.lastGameState.pending_choice.choice_key : null,
                    modals: [...document.querySelectorAll('.modal-overlay')].filter(m => m.style.display === 'flex').map(m => m.id),
                    wsState: typeof ws !== 'undefined' && ws ? ws.readyState : null })""", before_advance))
            record("synthetic_input_events_never_generated", page.evaluate("window.__synthetic") == 0, page.evaluate("window.__synthetic"))

            # ---- 三種代表解析度：安全區、無 overflow、無遮擋 ----
            # 換對手回合可能跳出事件揭示：用搖桿 B（既有關閉）收掉
            for _ in range(3):
                if not page.evaluate("[...document.querySelectorAll('.modal-overlay')].some(m => m.style.display === 'flex')"):
                    break
                pad.tap("B")
                page.wait_for_timeout(300)
            wait_idle()
            pad.tap("ZR")
            for _ in range(8):
                if lr()["zone"] == "hand":
                    break
                pad.tap("R")
            pad.tap("A")
            for (w, h) in RESOLUTIONS:
                page.set_viewport_size({"width": w, "height": h})
                page.wait_for_timeout(600)
                pad.push("left")
                pad.push("right")
                g = page.evaluate(GEOMETRY)
                m = g["margins"]
                fonts = g["fontDu"]
                ok = (min(m.values()) >= 0.045 and not g["docOverflowX"] and not g["docOverflowY"] and g["barInsideStage"]
                      and g["viewAboveBar"] and not g["tabsOverflow"] and g["hudChipsSingleLine"] and g["focusHit"] is True
                      and all(v is not None and v >= 16 for v in fonts.values()))
                record(f"resolution_{w}x{h}_safe_area_no_overflow_no_occlusion", ok, g)
                page.screenshot(path=str(OUT / f"08_resolution_{w}x{h}.png"))
            browser.close()
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except Exception:
                server.kill()

    fatal = [e for e in console_errors if "favicon" not in e and "Failed to load resource" not in e and "net::ERR" not in e]
    record("no_page_console_errors", not fatal, fatal[:5])
    report = {"passed": sum(c["passed"] for c in checks), "total": len(checks), "checks": checks, "console_errors": console_errors[:20]}
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"\n{report['passed']}/{report['total']} checks passed; proof in {OUT}")
    sys.exit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
