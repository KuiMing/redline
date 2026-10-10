#!/usr/bin/env python3
"""客廳大螢幕（living-room）瀏覽器 E2E：真實頁面 + mock bridge，固定按鍵序列（不用 BFS 探索）。

覆蓋：顯示模式切換／桌面不變；方向鍵只在內容資料間（永不落在手牌內按鈕、結束按鈕、六個全域分頁、
購買 checkbox、陣營能力鈕或提示列）；R／SR 只循環六個全域區段（含事件卡／時代關卡說明 modal）且 scope lock 正確；
專用快捷鍵 Capture（結束行動，危險確認、預設返回、防連按）、PLUS（陣營能力）、手牌 B（棄置，危險確認）、
購買卡 Y（既有購買所選 → 購買確認單）、地圖 Y（建立組織／確認移動／瓦解組織，iframe 權威重驗＋req 對應確認）、
按下搖桿（下一個內容區）的成功與 fail-closed（hidden／disabled／detached／條件不足／處理中鎖／iframe 缺席／
逾時／過期回覆／ok:false／權威目標失效，以及失敗後 <250ms 的合法 retry 不受污染）；
卡牌既有語意不退化、處理中鎖、重繪不跨區域、斷線／重連 baseline、PC 滑鼠勾選、720p／1080p／4K 安全區與無遮擋。

所有遊戲動作都經由真實的既有 DOM 控制／click handler 與伺服器；非同步結果以 bounded polling 等待明確條件。

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

# 客廳模式額外用到的按鍵（位元與 static/controller_core.js BUTTON_BITS 相同）
BIT.setdefault("ZR", (0, 0x80))
BIT.setdefault("CAPTURE", (1, 0x20))
BIT.setdefault("STICK", (1, 0x04))

OUT = Path(os.environ.get("REDLINE_LIVING_ROOM_PROOF_DIR", "/private/tmp/redline-living-room-proof"))
HAND = ["追隨者", "樂捐者", "追隨者", "歐洲奧援", "追隨者"]
RESOLUTIONS = [(1280, 720), (1920, 1080), (3840, 2160)]
LR_STATE = "RedlineController.getState().livingRoom"
SIX_SECTIONS = ("view:command", "view:map", "view:log", "view:myFaction", "event", "era:")

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

# forbidden：方向焦點不得落在的既有控制（與 LR.isDirectionalExcluded 同一份清單，由真實 DOM 判斷）
FOCUS_PROBE = """() => { const el = document.querySelector('.rl-pad-focus'); if (!el) return null;
  const forbidden = el.matches('.hand-card-action-btn') || el.id === 'advanceStepBtn' || el.id === 'redArmyAbilityBtn'
    || !!el.closest('#gameTabs') || el.matches('.game-tab') || !!el.closest('#turnActionButtons') || !!el.closest('#lrBar')
    || !!el.closest('#factionActionButtons') || (el.matches('input[type="checkbox"]') && !!el.closest('[data-card-zone]'));
  return { tag: el.tagName, id: el.id || null, type: el.type || null, card: el.matches('.card[data-card-zone]'),
           zone: el.closest('[data-card-zone]')?.dataset.cardZone || null, name: el.dataset.cardName || null,
           town: el.dataset.town || null, inModal: !!el.closest('.modal-overlay'), modal: el.closest('.modal-overlay')?.id || null,
           text: (el.textContent || '').trim().slice(0, 24), forbidden }; }"""

MODALS = """() => [...document.querySelectorAll('.modal-overlay, #victoryArtViewer')]
  .filter(m => getComputedStyle(m).display !== 'none' && m.getClientRects().length > 0).map(m => m.id)"""

SETTLED = """(ignoreProcessing) => { const s = RedlineController.getState().livingRoom; if (!s) return true; const t = performance.now();
  return (s.activatedAt === null || t - s.activatedAt > 270) && (s.redrawAt === null || t - s.redrawAt > 320)
    && (ignoreProcessing || !s.processing) && !s.mapRequest; }"""

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
    fontDu: { hint: fontPx('.lr-hint, .lr-hint-empty'), legend: fontPx('#lrLegend'), zoneLabel: fontPx('#lrZoneLabel'), title: fontPx('#handPanel .panel-title'), hud: fontPx('#hud') },
  };
}"""

TIMED = """async ([buttons, gap]) => {
  const bit = { A: [0x08, 0], B: [0x04, 0], X: [0x02, 0], Y: [0x01, 0], R: [0x40, 0], PLUS: [0, 0x02], CAPTURE: [0, 0x20], STICK: [0, 0x04] };
  for (let i = 0; i < buttons.length; i++) {
    const [b0, b1] = bit[buttons[i]];
    window.__padSend(0, 0, b0, b1);
    window.__padSend(0, 0, 0, 0);
    if (i < buttons.length - 1) await new Promise(r => setTimeout(r, gap));
  }
}"""

# 失敗回覆一到就立刻再按一次（不靠固定 sleep）；回傳兩次按壓的間隔與各階段狀態。
RETRY_AFTER_FAILURE = """async ([b0, b1]) => {
  const st = () => { const s = RedlineController.getState().livingRoom;
    return { activatedAt: s.activatedAt, processing: s.processing, mapRequest: s.mapRequest, lastMapAck: s.lastMapAck, itemKey: s.itemKey }; };
  const press = () => { window.__padSend(0, 0, b0, b1); window.__padSend(0, 0, 0, 0); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const t0 = performance.now();
  press();
  const sent = st();
  while (st().mapRequest && performance.now() - t0 < 900) await sleep(5);
  const failed = st();
  await sleep(20);
  const t1 = performance.now();
  press();
  const t2 = performance.now();
  while (st().mapRequest && performance.now() - t2 < 900) await sleep(5);
  return { sent, failed, ok: st(), gap: t1 - t0 };
}"""

# iframe 端：被要求執行指令時（在 adapter 處理完之後）才恢復按鈕，用來製造「第一次 ok:false、第二次合法」。
ARM_RESTORE = """([id, how]) => {
  const btn = document.getElementById(id);
  const restore = (e) => {
    if (!e.data || e.data.type !== 'redline-controller-command' || e.data.cmd !== 'act') return;
    window.removeEventListener('message', restore);
    window.__restoredFor = e.data.req;
    if (how === 'disabled') btn.disabled = false; else btn.style.display = '';
  };
  window.addEventListener('message', restore);
  if (how === 'disabled') btn.disabled = true; else btn.style.display = 'none';
  return { disabled: btn.disabled, display: btn.style.display, buttons: window.__redlineControllerAdapter.snapshot().buttons.map(b => b.id) };
}"""


class Session:
    """單一頁面的搖桿操作與觀察工具。所有遊戲動作只經由 pad 輸入 → 既有控制。"""

    def __init__(self, page, record):
        self.page = page
        self.pad = Pad(page)
        self.record = record

    def lr(self):
        return self.page.evaluate(LR_STATE)

    def focus(self):
        return self.page.evaluate(FOCUS_PROBE)

    def spy(self):
        return self.page.evaluate("JSON.parse(JSON.stringify(window.__spy))")

    def modals(self):
        return self.page.evaluate(MODALS)

    def view(self):
        return self.page.evaluate("document.querySelector('.game-tab.active')?.dataset.view || null")

    def poll(self, js, arg=None, timeout=5000):
        try:
            self.page.wait_for_function(js, arg=arg, timeout=timeout, polling=20)
            return True
        except Exception:
            return False

    def settle(self, ignore_processing=False, timeout=4000):
        """等到 250ms 執行冷卻、300ms 重繪冷卻、地圖等待與處理中鎖都解除（bounded polling）。"""
        ok = self.poll(SETTLED, ignore_processing, timeout)
        self.page.wait_for_timeout(100)  # 讓 80ms reconcile／50ms render 計時器跑完
        return ok

    def timed(self, buttons, gap_ms):
        self.page.evaluate(TIMED, [list(buttons), gap_ms])
        self.page.wait_for_timeout(150)

    def checked(self):
        return self.page.evaluate("[...document.querySelectorAll('input[data-purchase-index]')].filter(i => i.checked).map(i => i.dataset.purchaseIndex)")

    def hints(self):
        return {h["id"]: h for h in self.lr()["hints"]}

    def goto_zone(self, zone, item=True):
        """用 STICK（下一個內容區）把焦點移到指定內容區；同區時用 A 進入／ZR 退出。"""
        for _ in range(8):
            s = self.lr()
            if s["zone"] == zone:
                if (s["layer"] == "item") == item:
                    return True
                self.settle()
                self.pad.tap("A" if item else "ZR")
                continue
            self.pad.tap("STICK")
        s = self.lr()
        return s["zone"] == zone and (s["layer"] == "item") == item

    def hand(self):
        return self.page.evaluate("[...document.querySelectorAll('#hand .card[data-card-zone=\"hand\"]')].map(c => c.dataset.cardName)")


def new_game(base, hand=HAND, faction="taiwan_green", base_town="新竹", town="臺北"):
    setup = post_json(base, "/test/setup-move-confirmation-proof",
                      {"mover_faction": faction, "mover_base": base_town, "mover_town": town, "moves_left": 5})
    result = post_json(base, "/test/set-hand", {"game_id": setup["game_id"], "player_id": setup["player_id"],
                                                "cards": list(hand), "turn_phase": "action"})
    assert result.get("success"), result
    return setup


def open_page(context, base, url, errors, close_event=True):
    page = context.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base + url, wait_until="networkidle")
    page.wait_for_selector("#gameShell", state="visible", timeout=15000)
    if close_event:
        page.evaluate("() => window.closeEventReveal && closeEventReveal()")
    page.wait_for_timeout(300)
    return page


def map_frame(page):
    return next(fr for fr in page.frames if "leaflet_game_map" in fr.url)


# ======================================================================== 1. desktop
def scenario_desktop(browser, base, record, errors):
    setup = new_game(base)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script(MOCK_WS)
    desk = open_page(ctx, base, setup["url"], errors)
    record("desktop_default_has_no_display_attribute",
           desk.evaluate("document.documentElement.dataset.display === undefined && !document.getElementById('lrBar')"))
    record("desktop_stage_scale_unchanged",
           abs(desk.evaluate("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--stage-scale'))") - min(1280 / 1280, 800 / 720)) < 1e-6)
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
    ctx.close()


# ======================================================================== 2. main living-room flow
def scenario_main(browser, base, record, errors):
    setup = new_game(base)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script(MOCK_WS)
    page = open_page(ctx, base, setup["url"] + "&display=living-room", errors)
    S = Session(page, record)
    pad, lr, focus, spy, checked = S.pad, S.lr, S.focus, S.spy, S.checked
    preview_open = lambda: page.evaluate("document.getElementById('cardPreviewModal').style.display === 'flex'")
    confirm_open = lambda: page.evaluate("document.getElementById('lrConfirmModal').style.display === 'flex'")

    record("url_param_enables_living_room_and_persists",
           page.evaluate("[document.documentElement.dataset.display, localStorage.getItem('redline.display.v1')]") == ["living-room", "living-room"])
    enable_controller(page)
    page.evaluate(SPY)
    page.screenshot(path=str(OUT / "00_main_screen_before_input.png"))

    # ---- 第一次輸入只放區域焦點；內容區只有卡牌 ----
    pad.neutral()
    pad.tap("CAPTURE")
    s = lr()
    record("first_input_even_capture_only_places_zone_focus", s["layer"] == "zone" and s["zone"] == "hand" and spy()["sendAction"] == 0
           and focus() is None and not confirm_open(), s)
    record("content_zones_exclude_status_tabs_map_portal_and_action_bar", s["zones"] == ["static", "random", "hand"], s["zones"])
    bar = page.evaluate("""() => { const bar = document.getElementById('lrBar');
      return { pointer: getComputedStyle(bar).pointerEvents, focusables: bar.querySelectorAll('button, a[href], input, select, textarea, [tabindex], [role="button"]').length,
               keys: [...bar.querySelectorAll('.lr-hint kbd')].map(k => k.textContent) }; }""")
    record("hint_bar_is_not_focusable_and_labels_dedicated_keys", bar["pointer"] == "none" and bar["focusables"] == 0 and "Capture" in bar["keys"], bar)
    page.screenshot(path=str(OUT / "01_zone_focus_hand.png"))

    # ---- 區域層：搖桿只在內容區之間 ----
    seen, bad = [], []
    for d in ["up", "left", "right", "down", "down", "left", "up", "right", "down", "down"]:
        pad.push(d)
        s = lr()
        seen.append(s["zone"])
        if s["layer"] != "zone" or s["zone"] not in s["zones"] or focus() is not None:
            bad.append(s)
    record("zone_layer_stick_only_visits_content_zones", not bad and set(seen) <= {"static", "random", "hand"} and len(set(seen)) >= 2, [seen, bad[:2]])
    pad.tap("B")
    pad.tap("X")
    record("zone_layer_B_and_X_are_noops", lr()["layer"] == "zone" and spy()["sendAction"] == 0 and focus() is None)

    # ---- STICK：下一個內容區（只移焦點），之後 300ms 內的 A 被忽略 ----
    for _ in range(4):
        if lr()["zone"] == "hand":
            break
        pad.push("down")
    pad.tap("A")
    S.settle()
    visited = []
    for _ in range(3):
        pad.tap("STICK")
        s = lr()
        visited.append((s["zone"], s["layer"]))
    record("STICK_cycles_content_zones_focus_only", visited == [("static", "item"), ("random", "item"), ("hand", "item")]
           and spy()["sendAction"] == 0 and spy()["preview"] == 0 and spy()["toggle"] == 0, visited)
    S.timed(["STICK", "A"], 100)
    blocked = lr()
    record("STICK_then_immediate_A_is_ignored_by_redraw_cooldown", blocked["zone"] == "static" and not preview_open()
           and (blocked["lastCommand"] or {}).get("result") == "redraw-cooldown", blocked)

    # ---- 內容層掃描：方向鍵永遠只落在該區的整張卡牌 ----
    sweep_bad = []
    zone_root = {"hand": "#hand", "static": "#purchaseStatic", "random": "#purchaseRandom"}
    for zone in ["hand", "static", "random"]:
        S.goto_zone(zone)
        n = page.evaluate(f"document.querySelectorAll('{zone_root[zone]} .card[data-card-zone]').length")
        for d in ["right"] * (n + 1) + ["down", "up"] + ["left"] * (n + 1):
            pad.push(d)
            f = focus()
            if not f or f["forbidden"] or not f["card"] or lr()["zone"] != zone:
                sweep_bad.append([zone, d, f])
    record("stick_never_lands_on_hand_buttons_end_button_tabs_or_checkboxes", not sweep_bad, sweep_bad[:3])

    # ---- 隨機購買區：A 查看、B 勾選、X no-op、Y 條件不足 fail closed ----
    S.goto_zone("random")
    for _ in range(8):
        pad.push("left")
    S.settle()
    f = focus()
    record("random_zone_first_card_focused", lr()["itemKey"] == "purchase:6" and f and f["card"] and f["zone"] == "purchase", [lr(), f])
    pad.tap("B")
    after_check = checked()
    record("purchase_card_B_toggles_existing_checkbox", after_check == ["6"] and spy()["toggle"] == 1 and spy()["sendAction"] == 0, after_check)
    page.screenshot(path=str(OUT / "02_content_focus_random_card_checked.png"))
    S.settle()
    before = spy()
    pad.tap("X")
    record("purchase_card_X_full_noop", spy() == before and checked() == ["6"] and lr()["itemKey"] == "purchase:6"
           and not page.evaluate("RedlineController.getState().helpOpen"), spy())
    buy_disabled = page.evaluate("document.getElementById('openPurchaseConfirmBtn').disabled")
    pad.tap("Y")
    s = lr()
    record("purchase_Y_fails_closed_when_existing_buy_button_disabled_unaffordable",
           buy_disabled and "purchaseConfirmModal" not in S.modals() and (s["lastCommand"] or {}).get("result") == "noop"
           and spy()["sendAction"] == 0 and checked() == ["6"] and "cardBuy" not in S.hints(), [buy_disabled, s["lastCommand"], s["hints"]])
    pad.tap("A")
    record("purchase_card_A_previews_only", preview_open() and spy()["preview"] == 1 and checked() == ["6"] and spy()["toggle"] == 1)
    pad.tap("B")
    S.poll("document.getElementById('cardPreviewModal').style.display !== 'flex'")
    S.settle()
    record("preview_B_closes_and_focus_returns_to_same_card", not preview_open() and lr()["itemKey"] == "purchase:6" and (focus() or {}).get("card"), [lr(), focus()])
    pad.tap("B")
    record("purchase_card_B_toggles_off", checked() == [] and spy()["toggle"] == 2)
    S.settle()
    pad.tap("Y")
    record("purchase_Y_fails_closed_on_unchecked_card", "purchaseConfirmModal" not in S.modals() and (lr()["lastCommand"] or {}).get("result") == "noop"
           and checked() == [] and spy()["toggle"] == 2, lr()["lastCommand"])
    page.evaluate("document.querySelector('input[data-purchase-index=\"6\"]').style.display = 'none'")
    S.settle()
    pad.tap("B")
    record("purchase_card_B_noop_when_enabled_checkbox_hidden", checked() == [] and spy()["toggle"] == 2)
    page.evaluate("document.querySelector('input[data-purchase-index=\"6\"]').style.display = ''")
    S.settle()
    toggles = spy()["toggle"]
    S.timed(["B", "B"], 120)
    double_b = (checked(), spy()["toggle"] - toggles)
    S.settle()
    pad.tap("B")
    record("cooldown_successful_B_blocks_second_toggle_within_250ms", double_b == (["6"], 1) and checked() == [], [double_b, checked()])
    page.evaluate("document.querySelector('input[data-purchase-index=\"6\"]').style.display = 'none'")
    S.settle()
    toggles = spy()["toggle"]
    page.evaluate("""async () => {
      window.__padSend(0, 0, 0x04, 0); window.__padSend(0, 0, 0, 0);   // B on hidden checkbox → no-op
      document.querySelector('input[data-purchase-index="6"]').style.display = '';
      await new Promise(r => setTimeout(r, 120));
      window.__padSend(0, 0, 0x04, 0); window.__padSend(0, 0, 0, 0);   // legit B 120ms later
    }""")
    S.poll("[...document.querySelectorAll('input[data-purchase-index]')].some(i => i.checked)", timeout=1500)
    record("cooldown_failed_B_does_not_block_next_legit_toggle", checked() == ["6"] and spy()["toggle"] - toggles == 1, [checked(), spy()["toggle"] - toggles])
    S.settle()
    pad.tap("B")
    page.click('input[data-purchase-index="7"]')
    mouse_on = checked()
    page.click('input[data-purchase-index="7"]')
    record("living_room_mouse_checkbox_still_works", mouse_on == ["7"] and checked() == [], mouse_on)

    # ---- ZR 回區域層；常設區停用 checkbox（分神／內鬥）B 與 Y 都 no-op ----
    pad.tap("ZR")
    record("ZR_returns_to_zone_layer_same_zone", lr()["layer"] == "zone" and lr()["zone"] == "random" and focus() is None)
    S.goto_zone("static")
    S.settle()
    toggles_before = spy()["toggle"]
    disabled_idx = page.evaluate("[...document.querySelectorAll('#purchaseStatic .card[data-card-zone=\"purchase\"]')].findIndex(c => c.querySelector('input:disabled'))")
    for _ in range(8):
        pad.push("left")
    for _ in range(disabled_idx):
        pad.push("right")
    S.settle()
    f = focus()
    pad.tap("B")
    S.settle()
    pad.tap("Y")
    record("disabled_checkbox_card_B_and_Y_noop", disabled_idx >= 0 and f and f["card"] and checked() == [] and spy()["toggle"] == toggles_before
           and "purchaseConfirmModal" not in S.modals(), [disabled_idx, f, spy()["toggle"]])

    # ---- 手牌：A 查看、無棄置鈕時 B no-op、X 資源、Y 行動；處理中鎖；重繪規則 ----
    S.goto_zone("hand")
    for _ in range(6):
        pad.push("left")
    record("hand_zone_first_card", lr()["itemKey"] == "hand:0:追隨者", lr())
    pad.push("right")
    record("hand_right_moves_by_index", lr()["itemKey"] == "hand:1:樂捐者", lr())
    hints = S.hints()
    record("hand_hints_mirror_existing_buttons", hints.get("cardAction", {}).get("key") == "Y" and hints.get("cardResource", {}).get("key") == "X"
           and "cardDiscard" not in hints, list(hints))
    page.screenshot(path=str(OUT / "03_content_focus_hand_card.png"))
    S.settle()
    pad.tap("A")
    ok_preview = preview_open() and spy()["play"] == []
    pad.tap("B")
    S.poll("document.getElementById('cardPreviewModal').style.display !== 'flex'")
    S.settle()
    pad.tap("B")
    record("hand_A_previews_B_noop_without_discard_control", ok_preview and not preview_open() and lr()["layer"] == "item"
           and lr()["itemKey"] == "hand:1:樂捐者" and spy()["play"] == [] and spy()["sendAction"] == 0 and not confirm_open(), lr())
    # 處理中鎖：送出到不了伺服器時，Y 後的 X 被擋；逾時後解鎖
    page.evaluate("window.__dropSends = true")
    S.settle()
    pad.tap("Y")
    S.settle(ignore_processing=True)
    pad.tap("X")
    locked = spy()["play"]
    busy = lr()["processing"]
    status = page.evaluate("document.getElementById('lrBarStatus').textContent")
    S.poll(f"!{LR_STATE}.processing", timeout=3000)
    S.settle()
    pad.tap("X")
    record("processing_lock_blocks_second_submit_until_timeout",
           locked == [[1, "樂捐者", "action"]] and busy and "處理中" in status and spy()["play"][-1] == [1, "樂捐者", "resource"],
           [locked, busy, status, spy()["play"]])
    page.evaluate("window.__dropSends = false")
    S.poll(f"!{LR_STATE}.processing", timeout=3000)
    S.settle()
    n_play = len(spy()["play"])
    pad.tap("Y")
    S.poll("document.querySelectorAll('#hand .hand-card').length === 4", timeout=5000)
    S.settle()
    s = lr()
    record("hand_Y_plays_action_via_existing_button", spy()["play"][n_play:] == [[1, "樂捐者", "action"]], spy()["play"])
    record("redraw_keeps_zone_and_index_after_card_removed", s["zone"] == "hand" and s["layer"] == "item" and s["itemKey"] == "hand:1:追隨者", s)
    pad.tap("X")
    S.poll("document.querySelectorAll('#hand .hand-card').length === 3", timeout=5000)
    S.settle()
    record("hand_X_plays_resource_via_existing_button", spy()["play"][-1] == [1, "追隨者", "resource"], spy()["play"][-3:])
    record("redraw_with_duplicate_names_stays_on_same_index", lr()["itemKey"] == "hand:1:歐洲奧援", lr())

    # ---- 手牌 B＝既有「棄置」（一般奧援）：fail-closed 與危險確認 ----
    n_play = len(spy()["play"])
    pad.tap("X")
    record("support_card_X_never_discards", (focus() or {}).get("name") == "歐洲奧援" and len(spy()["play"]) == n_play, [focus(), spy()["play"][-2:]])
    hints = S.hints()
    record("support_card_hint_offers_B_discard_as_danger", hints.get("cardDiscard", {}).get("key") == "B" and hints["cardDiscard"]["danger"]
           and "歐洲奧援" in hints["cardDiscard"]["label"], list(hints.values()))
    DISCARD = "document.querySelector('#hand .card[data-card-name=\"歐洲奧援\"] .hand-card-action-btn[data-card-mode=\"resource\"]')"
    for variant, break_js, restore_js in [
        ("disabled", f"{DISCARD}.disabled = true", f"{DISCARD}.disabled = false"),
        ("hidden", f"{DISCARD}.style.display = 'none'", f"{DISCARD}.style.display = ''"),
        ("detached", f"window.__det = {DISCARD}; window.__detParent = window.__det.parentElement; window.__det.remove()",
         "window.__detParent.insertBefore(window.__det, window.__detParent.firstChild)"),
    ]:
        page.evaluate(break_js)
        S.settle()
        pad.tap("B")
        result = (confirm_open(), len(spy()["play"]) - n_play, spy()["sendAction"])
        page.evaluate(restore_js)
        S.settle()
        record(f"hand_B_discard_fails_closed_when_button_{variant}", result[0] is False and result[1] == 0 and (focus() or {}).get("name") == "歐洲奧援", result)
    sends = spy()["sendAction"]
    S.timed(["B", "A"], 120)
    record("discard_confirm_A_within_250ms_is_ignored", confirm_open() and len(spy()["play"]) == n_play
           and (lr()["lastCommand"] or {}).get("cmd") == "cardDiscard", focus())
    c = lr()["confirm"]
    f = focus()
    record("hand_B_discard_opens_danger_confirm_default_back", confirm_open() and c and c["kind"] == "discard" and c["label"] == "棄置 歐洲奧援"
           and f and f["id"] == "lrConfirmCancelBtn" and len(spy()["play"]) == n_play and spy()["sendAction"] == sends, [c, f])
    page.screenshot(path=str(OUT / "04_hand_discard_confirm_default_back.png"))
    S.settle()
    pad.tap("A")
    S.poll("document.getElementById('lrConfirmModal').style.display === 'none'", timeout=1500)
    record("discard_confirm_A_on_default_back_cancels", not confirm_open() and len(spy()["play"]) == n_play and lr()["itemKey"] == "hand:1:歐洲奧援", lr())
    S.settle()
    pad.tap("B")
    S.settle()
    pad.tap("B")
    S.poll("document.getElementById('lrConfirmModal').style.display === 'none'", timeout=1500)
    record("discard_confirm_B_cancels", not confirm_open() and len(spy()["play"]) == n_play)
    S.settle()
    pad.tap("B")
    page.evaluate(f"{DISCARD}.disabled = true")
    revalidated = S.poll("document.getElementById('lrConfirmModal').style.display === 'none'", timeout=1500)
    page.evaluate(f"{DISCARD}.disabled = false")
    record("discard_confirm_closes_when_button_becomes_invalid", revalidated and len(spy()["play"]) == n_play, lr())
    S.settle()
    pad.tap("B")
    S.settle()
    pad.push("right")
    ok_focus = (focus() or {}).get("id")
    pad.tap("A")
    S.poll("document.querySelectorAll('#hand .hand-card').length === 2", timeout=5000)
    S.settle()
    record("discard_confirm_executes_existing_discard_once", ok_focus == "lrConfirmOkBtn" and spy()["play"][n_play:] == [[1, "歐洲奧援", "resource"]]
           and S.hand() == ["追隨者", "追隨者"], [ok_focus, spy()["play"][n_play:], S.hand()])

    # ---- 重繪：同 key 重綁、手牌清空 → 區域層（不跨區） ----
    key_before = lr()["itemKey"]
    page.evaluate("render(window.lastGameState)")
    S.settle()
    same = lr()["itemKey"] == key_before and page.evaluate("!!document.querySelector('#hand .hand-card.rl-pad-focus')")
    page.evaluate("""() => { const s = structuredClone(window.lastGameState); const me = s.players.find(p => p.id === playerId);
      me.hand = []; me.hand_variants = []; me.hand_action_legality = []; render(s); }""")
    S.settle()
    emptied = lr()
    page.evaluate("render(window.lastGameState)")
    S.settle()
    record("redraw_same_state_rebinds_same_card", same, key_before)
    record("redraw_empty_zone_falls_back_to_a_content_zone_layer", emptied["layer"] == "zone" and emptied["zone"] in ("static", "random"), emptied)

    # ---- Capture：既有結束行動＋危險確認（fail-closed、預設返回、防連按） ----
    sends = spy()["sendAction"]
    S.timed(["CAPTURE", "A", "CAPTURE"], 80)
    c = lr()["confirm"]
    label = page.evaluate("document.getElementById('advanceStepBtn').textContent.trim()")
    f = focus()
    record("capture_opens_end_step_danger_confirm_default_back", confirm_open() and c and c["kind"] == "advance" and c["label"] == label
           and f and f["id"] == "lrConfirmCancelBtn" and spy()["sendAction"] == sends, [c, label, f])
    record("capture_rapid_repeat_keeps_single_confirm_ignores_A_and_sends_nothing", confirm_open() and spy()["sendAction"] == sends
           and S.modals() == ["lrConfirmModal"], S.modals())
    S.settle()
    pad.tap("A")
    S.poll("document.getElementById('lrConfirmModal').style.display === 'none'", timeout=1500)
    record("capture_confirm_A_on_default_back_cancels", not confirm_open() and spy()["sendAction"] == sends)
    S.settle()
    pad.tap("CAPTURE")
    S.settle()
    pad.tap("B")
    S.poll("document.getElementById('lrConfirmModal').style.display === 'none'", timeout=1500)
    record("capture_confirm_B_cancels", not confirm_open() and spy()["sendAction"] == sends)
    ADV = "document.getElementById('advanceStepBtn')"
    for variant, break_js, restore_js in [
        ("disabled", f"{ADV}.disabled = true", f"{ADV}.disabled = false"),
        ("hidden", f"{ADV}.style.visibility = 'hidden'", f"{ADV}.style.visibility = ''"),
        ("detached", f"window.__adv = {ADV}; window.__advParent = window.__adv.parentElement; window.__advNext = window.__adv.nextSibling; window.__adv.remove()",
         "window.__advParent.insertBefore(window.__adv, window.__advNext)"),
    ]:
        page.evaluate(break_js)
        S.settle()
        pad.tap("CAPTURE")
        result = (confirm_open(), spy()["sendAction"] - sends, (lr()["lastCommand"] or {}).get("result"))
        page.evaluate(restore_js)
        S.settle()
        record(f"capture_fails_closed_when_end_button_{variant}", result == (False, 0, "noop"), result)
    pad.tap("CAPTURE")
    page.evaluate(f"{ADV}.textContent = '結束回合'")
    relabeled = S.poll("document.getElementById('lrConfirmModal').style.display === 'none'", timeout=1500)
    page.evaluate(f"{ADV}.textContent = {json.dumps(label)}")
    record("capture_confirm_closes_when_end_step_changes_underneath", relabeled and spy()["sendAction"] == sends, lr())
    S.settle()

    # ---- PLUS：沒有陣營能力（臺灣綠）→ no-op ----
    pad.tap("PLUS")
    record("plus_without_faction_ability_is_noop", (lr()["lastCommand"] or {}).get("result") == "noop" and spy()["sendAction"] == sends
           and not S.modals(), lr()["lastCommand"])

    # ---- 處理中鎖：送出到不了伺服器時，購買卡 Y 與 Capture 都被擋（之後由逾時解鎖） ----
    S.goto_zone("hand")
    for _ in range(4):
        pad.push("left")
    S.settle()
    pad.tap("X")
    S.poll("document.querySelectorAll('#hand .hand-card').length === 1", timeout=5000)
    S.settle()
    page.evaluate("window.__dropSends = true")
    pad.tap("X")
    S.goto_zone("static")
    S.settle(ignore_processing=True)
    pad.tap("Y")
    blocked_buy = (lr()["lastCommand"] or {}).get("result")
    pad.tap("CAPTURE")
    blocked_end = (lr()["lastCommand"] or {}).get("result")
    record("processing_lock_blocks_purchase_Y_and_capture", blocked_buy == "processing" and blocked_end == "processing"
           and "purchaseConfirmModal" not in S.modals() and not confirm_open(), [blocked_buy, blocked_end])
    page.evaluate("window.__dropSends = false")
    S.poll(f"!{LR_STATE}.processing", timeout=3000)
    S.settle()

    # ---- 購買卡 Y 成功：既有「購買所選」→ 既有購買確認單 → 確定購買 ----
    S.goto_zone("hand")
    S.settle()
    pad.tap("X")
    S.poll("document.querySelectorAll('#hand .hand-card').length === 0", timeout=5000)
    S.settle()
    propaganda = page.evaluate("window.lastGameState.players.find(p => p.id === playerId).resources.propaganda")
    cost = page.evaluate("window.lastGameState.purchase_area_costs[0]")
    S.goto_zone("static")
    for _ in range(8):
        pad.push("left")
    S.settle()
    pad.tap("B")
    S.settle()
    buy_ok = page.evaluate("!document.getElementById('openPurchaseConfirmBtn').disabled")
    hints = S.hints()
    record("purchase_fixture_selected_affordable_card", checked() == ["0"] and buy_ok and propaganda >= cost["propaganda"]
           and hints.get("cardBuy", {}).get("key") == "Y", [checked(), buy_ok, propaganda, cost, list(hints)])
    BUY = "document.getElementById('openPurchaseConfirmBtn')"
    for variant, break_js, restore_js in [
        ("hidden", f"{BUY}.style.display = 'none'", f"{BUY}.style.display = ''"),
        ("disabled", f"window.__buyWasDisabled = {BUY}.disabled; {BUY}.disabled = true", f"{BUY}.disabled = window.__buyWasDisabled"),
        ("detached", f"window.__buy = {BUY}; window.__buyParent = window.__buy.parentElement; window.__buyNext = window.__buy.nextSibling; window.__buy.remove()",
         "window.__buyParent.insertBefore(window.__buy, window.__buyNext)"),
    ]:
        page.evaluate(break_js)
        S.settle()
        pad.tap("Y")
        result = ("purchaseConfirmModal" in S.modals(), "buy_cards" in spy()["calls"], (lr()["lastCommand"] or {}).get("result"))
        page.evaluate(restore_js)
        S.settle()
        record(f"purchase_Y_fails_closed_when_buy_button_{variant}", result == (False, False, "noop"), result)
    pad.push("right")
    S.settle()
    pad.tap("Y")
    record("purchase_Y_fails_closed_on_other_unchecked_card_while_selection_exists",
           "purchaseConfirmModal" not in S.modals() and checked() == ["0"] and (lr()["lastCommand"] or {}).get("result") == "noop", lr()["lastCommand"])
    pad.push("left")
    S.settle()
    record("purchase_focus_back_on_checked_card", lr()["itemKey"] == "purchase:0" and checked() == ["0"] and buy_ok
           and page.evaluate(f"!{BUY}.disabled"), lr())
    sends = spy()["sendAction"]
    pad.tap("Y")
    opened = "purchaseConfirmModal" in S.modals()
    record("purchase_Y_opens_existing_purchase_confirm_without_buying", opened and "buy_cards" not in spy()["calls"]
           and (focus() or {}).get("modal") == "purchaseConfirmModal", [S.modals(), focus()])
    page.screenshot(path=str(OUT / "05_purchase_Y_existing_confirm.png"))
    S.settle()
    pad.tap("B")
    S.poll("document.getElementById('purchaseConfirmModal').style.display === 'none'", timeout=1500)
    record("purchase_confirm_B_cancels_without_buying", "purchaseConfirmModal" not in S.modals() and "buy_cards" not in spy()["calls"] and checked() == ["0"])
    S.settle()
    S.timed(["Y", "A"], 120)
    record("purchase_confirm_A_within_250ms_is_ignored", "purchaseConfirmModal" in S.modals() and "buy_cards" not in spy()["calls"])
    S.settle()
    for _ in range(3):
        if (focus() or {}).get("id") == "confirmPurchaseBtn":
            break
        pad.push("left")
    supply_before = page.evaluate("window.lastGameState.static_purchase_supply ? JSON.stringify(window.lastGameState.static_purchase_supply) : null")
    pad.tap("A")
    bought = S.poll(f"window.lastGameState.players.find(p => p.id === playerId).resources.propaganda === {propaganda - cost['propaganda']}", timeout=5000)
    record("purchase_Y_then_existing_confirm_buys_once_via_server", bought and spy()["calls"].count("buy_cards") == 1
           and "purchaseConfirmModal" not in S.modals() and checked() == [],
           [bought, spy()["calls"][-3:], supply_before, page.evaluate("window.lastGameState.players.find(p => p.id === playerId).resources")])
    S.settle()

    # ---- 斷線／重連：重連時按住 A+PLUS+CAPTURE 不觸發 ----
    snapshot_before = (lr()["zone"], lr()["layer"], spy()["sendAction"], confirm_open())
    page.evaluate("window.__padHeartbeat = false")
    page.evaluate("window.__padClose()")
    page.wait_for_function("RedlineController.getState().status !== 'connected'", timeout=3000)
    alert = page.evaluate("document.getElementById('lrBarStatus').dataset.alert")
    page.evaluate("window.__padLast = [0, 0, 0x08, 0x22]; window.__padHeartbeat = true")
    page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
    page.wait_for_timeout(500)
    record("reconnect_with_held_A_PLUS_CAPTURE_fires_nothing", (lr()["zone"], lr()["layer"], spy()["sendAction"], confirm_open()) == snapshot_before
           and alert == "true", [snapshot_before, lr(), alert])
    pad.neutral()
    page.evaluate("window.__padHeartbeat = false")
    page.wait_for_function("RedlineController.getState().status === 'stale'", timeout=5000)
    record("stale_signal_shows_alert_banner", page.evaluate("document.getElementById('lrBarStatus').dataset.alert") == "true"
           and "訊號中斷" in page.evaluate("document.getElementById('lrBarStatus').textContent"))
    page.evaluate("window.__padHeartbeat = true")
    pad.neutral()
    page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=3000)

    # ---- 地圖：R 進入（不落在分頁）→ 兩段式清單 → Y 確認移動；iframe 確認失敗矩陣 ----
    S.settle()
    pad.tap("R")
    page.wait_for_function("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=5000)
    page.wait_for_function("document.getElementById('strategicMapFrame').contentWindow.lastGameState", timeout=20000)
    S.poll(f"{LR_STATE}.mapStage === 'source'", timeout=15000)
    mframe = map_frame(page)
    S.settle()
    record("R_enters_map_list_directly", lr()["zone"] == "maplist" and lr()["layer"] == "item" and lr()["sectionKey"] == "view:map", lr())
    # 250ms 執行冷卻：ZR 回清單區域層後，A 進入清單、120ms 內的第二個 A 不得選取第一個來源
    pad.tap("ZR")
    S.settle()
    S.timed(["A", "A"], 120)
    s2 = lr()
    record("cooldown_enter_map_list_then_rapid_A_does_not_pick_origin",
           s2["zone"] == "maplist" and s2["layer"] == "item" and s2["mapStage"] == "source" and mframe.evaluate("selectedTown") is None
           and (s2["lastCommand"] or {}).get("result") == "activation-cooldown", s2)
    S.settle()
    # 地圖已掛載：ZR×2 回指揮中心，再按 R 立刻 A——落點不是使用者指定，300ms 內的 A 必須被忽略
    pad.tap("ZR")
    pad.tap("ZR")
    S.poll("document.querySelector('.game-tab.active').dataset.view === 'command'", timeout=3000)
    S.settle()
    S.timed(["R", "A"], 150)
    s = lr()
    record("R_to_map_places_list_focus_as_non_user_so_immediate_A_is_ignored",
           S.view() == "map" and s["zone"] == "maplist" and s["layer"] == "item" and mframe.evaluate("selectedTown") is None
           and (s["lastCommand"] or {}).get("result") == "redraw-cooldown", s)
    S.settle()
    for _ in range(len(lr()["mapRows"]) + 1):
        pad.push("up")
    S.settle()
    snap = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
    origins = sorted(t["town"] for t in snap["targets"] if t["role"] == "origin")
    record("map_list_source_stage_lists_authoritative_origins", sorted(lr()["mapRows"]) == origins and origins, [lr()["mapRows"], origins])
    origin = mframe.evaluate("(names) => names.find(n => { const o = movementOptionsForTown(n); return o.road.length + o.rail.length > 0; })", lr()["mapRows"])
    idx = lr()["mapRows"].index(origin)
    for _ in range(idx):
        pad.push("down")
    S.settle()
    record("map_list_focus_drives_iframe_focus_ring", (S.focus() or {}).get("town") == origin
           and mframe.evaluate("document.querySelectorAll('.pad-focus-label').length") == 1, S.focus())
    acts = dict(zip(lr()["mapRows"], lr()["mapActs"]))
    pad.tap("Y")
    record("map_Y_on_source_without_action_fails_closed", acts.get(origin) is None and lr()["mapRequest"] is None
           and mframe.evaluate("selectedTown") is None and (lr()["lastCommand"] or {}).get("result") == "noop", [acts, lr()["lastCommand"]])
    S.settle()
    pad.tap("A")
    S.poll(f"{LR_STATE}.mapStage === 'destination'", timeout=5000)
    S.settle()
    legal = sorted(set(mframe.evaluate("selectedMoveTargets.map(t => t.town)")))
    record("map_destination_rows_equal_server_legal_moves_and_carry_move_action",
           lr()["mapSelected"] == origin and sorted(lr()["mapRows"]) == legal and legal and all(a == "move" for a in lr()["mapActs"]), [lr()["mapRows"], legal, lr()["mapActs"]])
    dest = lr()["mapRows"][0]
    hints = S.hints()
    record("map_hint_shows_Y_move_label", hints.get("mapAct", {}).get("key") == "Y" and f"{origin}→{dest}" in hints["mapAct"]["label"], list(hints.values()))
    page.screenshot(path=str(OUT / "06_map_list_destination_Y_move.png"))
    # B 走既有「取消選取」回到來源清單；換段後焦點回到第一列，再固定往下 idx 次回到同一個來源
    pad.tap("B")
    S.poll(f"{LR_STATE}.mapStage === 'source'", timeout=5000)
    S.settle()
    record("map_B_cancels_source_via_existing_flow_and_resets_to_first_row", mframe.evaluate("selectedTown") is None
           and lr()["layer"] == "item" and (S.focus() or {}).get("town") == lr()["mapRows"][0], [lr(), S.focus()])
    for _ in range(idx):
        pad.push("down")
    pad.tap("A")
    S.poll(f"{LR_STATE}.mapStage === 'destination'", timeout=5000)
    S.settle()
    record("map_destination_stage_restored", lr()["mapSelected"] == origin and lr()["mapRows"][0] == dest and (S.focus() or {}).get("town") == dest, lr())

    # (a) 沒有 iframe：送不出去 → 立即 fail closed
    before = lr()
    page.evaluate("document.getElementById('strategicMapFrame').id = 'strategicMapFrameDetached'")
    pad.tap("Y")
    no_frame = lr()
    page.evaluate("document.getElementById('strategicMapFrameDetached').id = 'strategicMapFrame'")
    record("map_Y_no_iframe_fails_closed_without_cooldown_or_lock",
           (no_frame["lastMapAck"] or {}).get("outcome") == "no-frame" and no_frame["activatedAt"] == before["activatedAt"]
           and not no_frame["processing"] and no_frame["mapRequest"] is None and mframe.evaluate("pendingMoveTarget") is None, no_frame)
    S.settle()
    # (b) iframe 收不到：等待期間第二個 Y 不重送；過期／偽造 req 的回覆被忽略；逾時 fail closed；逾時後才到的成功＝stale
    page.evaluate("""() => { const w = document.getElementById('strategicMapFrame').contentWindow;
      w.__dropped = []; w.__origPostMessage = w.postMessage; w.postMessage = function (msg) { w.__dropped.push(msg); }; }""")
    S.timed(["Y", "Y"], 120)
    inflight = lr()
    dropped = page.evaluate("""() => document.getElementById('strategicMapFrame').contentWindow.__dropped
      .filter(m => m.req).map(m => ({ cmd: m.cmd, id: m.id || null, town: m.town || null, req: m.req }))""")
    record("map_Y_in_flight_blocks_duplicate_send",
           len(dropped) == 1 and dropped[0]["cmd"] == "act" and dropped[0]["id"] == "confirmMoveBtn" and dropped[0]["town"] == dest
           and bool(inflight["mapRequest"]) and inflight["mapRequest"]["req"] == dropped[0]["req"] and inflight["activatedAt"] == before["activatedAt"]
           and not inflight["processing"], [dropped, inflight])
    req = dropped[0]["req"] if dropped else 1
    # 監聽在 controller 之後註冊：看到這筆回覆時 controller 已經處理完（不靠固定等待）
    page.evaluate("""() => { window.__seenReqs = [];
      window.addEventListener('message', e => { if (e.data && e.data.type === 'redline-controller-result') window.__seenReqs.push(e.data.req); }); }""")
    mframe.evaluate("""(req) => window.parent.postMessage({ type: 'redline-controller-result', v: 1, cmd: 'act', req: req + 1000,
      ok: true, reason: null, via: 'confirmMoveBtn' }, location.origin)""", req)
    S.poll("(r) => window.__seenReqs.includes(r)", req + 1000, timeout=2000)
    forged = lr()
    record("map_Y_mismatched_req_result_is_ignored_and_keeps_waiting", forged["mapRequest"] and forged["mapRequest"]["req"] == req
           and forged["activatedAt"] == before["activatedAt"] and not forged["processing"], forged)
    S.poll(f"{LR_STATE}.mapRequest === null", timeout=2500)
    timed_out = lr()
    record("map_Y_timeout_fails_closed_without_cooldown_or_lock",
           (timed_out["lastMapAck"] or {}).get("outcome") == "timeout" and timed_out["lastMapAck"]["req"] == req
           and timed_out["activatedAt"] == before["activatedAt"] and not timed_out["processing"], timed_out)
    mframe.evaluate("""(req) => window.parent.postMessage({ type: 'redline-controller-result', v: 1, cmd: 'act', req,
      ok: true, reason: null, via: 'confirmMoveBtn' }, location.origin)""", req)
    S.poll("(r) => window.__seenReqs.includes(r)", req, timeout=2000)
    late = lr()
    page.evaluate("""() => { const w = document.getElementById('strategicMapFrame').contentWindow;
      w.postMessage = w.__origPostMessage; delete w.__origPostMessage; }""")
    record("map_Y_late_success_after_timeout_is_stale_and_ignored",
           late["lastMapAck"] == timed_out["lastMapAck"] and late["activatedAt"] == before["activatedAt"] and not late["processing"]
           and mframe.evaluate("pendingMove") is None, late)
    S.settle()
    # (c) iframe 直接重驗：非目標城鎮與動作不符一律 ok:false，不點任何按鈕
    probes = page.evaluate("""async ([dest, illegal]) => {
      const out = [];
      const frame = document.getElementById('strategicMapFrame');
      const listen = new Promise(resolve => {
        const seen = [];
        window.addEventListener('message', function on(e) {
          if (!e.data || e.data.type !== 'redline-controller-result' || !e.data.req || e.data.req < 900000) return;
          seen.push({ req: e.data.req, ok: e.data.ok, reason: e.data.reason });
          if (seen.length === 2) { window.removeEventListener('message', on); resolve(seen); }
        });
      });
      frame.contentWindow.postMessage({ type: 'redline-controller-command', v: 1, cmd: 'act', town: dest, id: 'directBuildBtn', req: 900001 }, location.origin);
      frame.contentWindow.postMessage({ type: 'redline-controller-command', v: 1, cmd: 'act', town: illegal, id: 'confirmMoveBtn', req: 900002 }, location.origin);
      return await Promise.race([listen, new Promise(r => setTimeout(() => r(null), 2000))]);
    }""", [dest, mframe.evaluate("(ok) => [...byName.keys()].find(n => !ok.includes(n))", lr()["mapRows"] + [origin])])
    record("iframe_revalidates_act_action_mismatch_and_non_target",
           probes and sorted((p["req"], p["ok"], p["reason"]) for p in probes) == [(900001, False, "action-mismatch"), (900002, False, "not-a-target")]
           and mframe.evaluate("pendingMove") is None and lr()["mapRequest"] is None, probes)
    # (d) 權威目標失效（parent 清單仍顯示，但 iframe 的合法目的地已不含它）→ ok:false
    mframe.evaluate("(dest) => { window.__savedTargets = selectedMoveTargets.slice(); selectedMoveTargets = selectedMoveTargets.filter(t => t.town !== dest); }", dest)
    S.settle()
    pad.tap("Y")
    S.poll(f"{LR_STATE}.mapRequest === null", timeout=2500)
    stale_target = lr()
    mframe.evaluate("() => { selectedMoveTargets = window.__savedTargets; map.fire('moveend'); }")
    record("map_Y_fails_closed_when_authoritative_target_disappeared",
           (stale_target["lastMapAck"] or {}).get("outcome") == "failed" and stale_target["lastMapAck"].get("reason") == "not-a-target"
           and stale_target["activatedAt"] == before["activatedAt"] and not stale_target["processing"] and mframe.evaluate("pendingMove") is None,
           stale_target)
    S.poll(f"{LR_STATE}.mapRows[0] === {json.dumps(dest)}", timeout=3000)
    S.settle()
    for _ in range(len(lr()["mapRows"]) + 1):
        pad.push("up")
    S.settle()
    # (e) A 只預備；按鈕在 iframe 內失效 → ok:false；失敗後 <250ms 的合法 Y 不受污染 → 成功（冷卻＋處理中鎖）→ 伺服器移動
    pad.tap("A")
    S.poll(f"!!{LR_STATE}.mapPending", timeout=5000)
    S.settle()
    pending = mframe.evaluate("pendingMoveTarget")
    record("map_A_on_destination_only_arms_confirm", pending and pending["to"] == dest and mframe.evaluate("pendingMove") is None
           and lr()["mapPending"]["to"] == dest, [pending, lr()["mapPending"]])
    map_geo = page.evaluate("""() => {
      const bar = document.getElementById('lrBar').getBoundingClientRect();
      const view = document.getElementById('mapView').getBoundingClientRect();
      const panel = document.getElementById('lrMapPanel').getBoundingClientRect();
      const footer = document.getElementById('lrMapFooter'); const f = footer.getBoundingClientRect();
      const hit = document.elementFromPoint((f.left + f.right) / 2, (f.top + f.bottom) / 2);
      return { viewAboveBar: view.bottom <= bar.top + 1, panelAboveBar: panel.bottom <= bar.top + 1,
               footerVisible: !!hit && footer.contains(hit), footer: footer.textContent };
    }""")
    record("map_view_and_target_panel_not_covered_by_hint_bar",
           map_geo["viewAboveBar"] and map_geo["panelAboveBar"] and map_geo["footerVisible"] and "已預備" in map_geo["footer"], map_geo)
    before = lr()
    page.evaluate("""() => { window.__mapResults = [];
      window.addEventListener('message', e => { if (e.data && e.data.type === 'redline-controller-result' && e.data.req && e.data.req < 900000) window.__mapResults.push(e.data); }); }""")
    pre = mframe.evaluate(ARM_RESTORE, ["confirmMoveBtn", "disabled"])
    seq = page.evaluate(RETRY_AFTER_FAILURE, [0x01, 0])
    seq["pre"] = pre
    seq["results"] = page.evaluate("window.__mapResults || []")
    sent, failed, acked = seq["sent"], seq["failed"], seq["ok"]
    results = seq["results"]
    first = results[0] if results else {}
    second = results[1] if len(results) > 1 else {}
    sent_req = (sent.get("mapRequest") or {}).get("req")
    record("map_Y_ok_false_when_button_invalid_fails_closed_without_cooldown_or_lock",
           pre.get("disabled") is True and "confirmMoveBtn" not in (pre.get("buttons") or []) and sent_req is not None
           and first.get("req") == sent_req and first.get("ok") is False and first.get("reason") == "button-unavailable"
           and sent.get("activatedAt") == before["activatedAt"] and not sent.get("processing")
           and (failed.get("lastMapAck") or {}).get("outcome") == "failed" and failed.get("activatedAt") == before["activatedAt"]
           and not failed.get("processing"), seq)
    record("map_Y_failure_does_not_block_next_legal_retry_within_250ms",
           isinstance(seq.get("gap"), (int, float)) and seq["gap"] < 250 and (acked.get("lastMapAck") or {}).get("outcome") == "success"
           and (acked.get("lastMapAck") or {}).get("req") not in (None, sent_req) and second.get("ok") is True, seq)
    record("map_Y_success_records_cooldown_and_processing_lock", (acked.get("lastMapAck") or {}).get("lock") is True
           and acked.get("activatedAt") is not None and acked.get("activatedAt") != before["activatedAt"] and acked.get("mapRequest") is None, seq)
    moved = S.poll(f"(() => {{ const t = document.getElementById('strategicMapFrame').contentWindow.lastGameState?.map?.towns?.[{json.dumps(dest)}] || []; return t.some(e => e.player === 'mover'); }})()", timeout=8000)
    record("map_Y_move_executes_via_existing_confirm_button_and_server", moved, dest)
    S.settle()
    record("map_list_focus_stays_in_list_after_move", lr()["zone"] == "maplist", lr())
    pad.tap("ZR")
    S.settle()
    pad.tap("ZR")
    page.wait_for_function("document.querySelector('.game-tab.active').dataset.view === 'command'", timeout=5000)
    S.settle()
    record("ZR_twice_on_map_returns_to_command_content_zone", lr()["zone"] in ("static", "random", "hand") and lr()["layer"] == "zone", lr())

    # ---- Capture 執行：向右到「確認」→ A 只送出一次 ----
    pad.tap("CAPTURE")
    S.settle()
    pad.push("right")
    ok_focus = (focus() or {}).get("id")
    page.screenshot(path=str(OUT / "07_capture_confirm_focus_ok.png"))
    n_send = spy()["sendAction"]
    before_advance = page.evaluate("({ phase: window.lastGameState.turn_phase, current: window.lastGameState.current_player })")
    pad.tap("A")
    pad.tap("A")
    pad.tap("CAPTURE")
    pad.tap("A")
    left = S.poll("(b) => { const s = window.lastGameState; return !!s && (s.turn_phase !== b.phase || s.current_player !== b.current); }",
                  before_advance, timeout=8000)
    calls = spy()["calls"][n_send:]
    record("capture_confirm_executes_existing_end_step_exactly_once", ok_focus == "lrConfirmOkBtn" and calls == ["advance"], [ok_focus, calls])
    record("advance_reached_server_and_left_pre_action_player_phase", left, page.evaluate("({ phase: window.lastGameState.turn_phase, current: window.lastGameState.current_player })"))
    record("synthetic_input_events_never_generated", page.evaluate("window.__synthetic") == 0, page.evaluate("window.__synthetic"))

    # ---- 三種代表解析度：安全區、無 overflow、無遮擋 ----
    for _ in range(3):
        if not S.modals():
            break
        pad.tap("B")
        S.poll(f"({MODALS})().length === 0", timeout=1000)
    S.settle()
    S.goto_zone("hand")
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
    ctx.close()


# ======================================================================== 3. R / SR global sections
def scenario_sections(browser, base, record, errors):
    setup = post_json(base, "/test/setup-era-notification-proof", {"era_id": "mongolia", "via_lifecycle": True})
    assert setup.get("success"), setup
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script(MOCK_WS)
    page = open_page(ctx, base, setup["url"] + "&display=living-room", errors, close_event=False)
    S = Session(page, record)
    pad, lr = S.pad, S.lr
    enable_controller(page)
    page.evaluate(SPY)
    S.poll("!!document.querySelector('#activeEraTabs .era-stage-tab') && getComputedStyle(document.getElementById('eventCardTab')).display !== 'none'", timeout=5000)
    pad.neutral()
    for _ in range(6):
        if not S.modals():
            break
        pad.tap("B")
        S.settle()
    pad.tap("A")
    S.settle()
    stops = page.evaluate("""() => [...document.querySelectorAll('#gameTabs .game-tab')].filter(t => t.getClientRects().length && !t.disabled)
      .map(t => t.dataset.view ? 'view:' + t.dataset.view : t.id === 'eventCardTab' ? 'event' : 'era:' + t.dataset.eraId)""")
    record("section_fixture_has_all_six_sections", stops[:5] == ["view:command", "view:map", "view:log", "view:myFaction", "event"]
           and len(stops) == 6 and stops[5].startswith("era:") and not S.modals() and S.view() == "command", [stops, S.modals()])
    visited, bad = [], []
    expected = stops[1:] + stops[:2]
    for want in expected:
        pad.tap("R")
        ok = S.poll(f"{LR_STATE}.sectionKey === {json.dumps(want)}", timeout=3000)
        S.settle()
        s, modals, view, f = lr(), S.modals(), S.view(), S.focus()
        visited.append([s["sectionKey"], view, modals])
        modal_ok = (modals == ["eventRevealModal"]) if want == "event" else (modals == ["eraAchievementModal"]) if want.startswith("era:") else (modals == [])
        view_ok = want.startswith("view:") is False or view == want[5:]
        if not ok or not modal_ok or not view_ok or (f and f["forbidden"]):
            bad.append([want, s["sectionKey"], view, modals, f])
    record("R_cycles_exactly_the_six_global_sections_in_tab_order", not bad and all(v[0].startswith(SIX_SECTIONS) for v in visited), [visited, bad])
    page.screenshot(path=str(OUT / "09_sections_after_R_cycle.png"))
    # SR：反向（從戰略地圖往回 → 指揮中心 → 時代關卡 → 事件卡 → 我的陣營）
    back, bad = [], []
    for want in [stops[0], stops[5], stops[4], stops[3]]:
        pad.tap("SR")
        ok = S.poll(f"{LR_STATE}.sectionKey === {json.dumps(want)}", timeout=3000)
        S.settle()
        back.append([lr()["sectionKey"], S.view(), S.modals()])
        if not ok:
            bad.append(want)
    record("SR_cycles_backwards_through_section_modals", not bad and back[-1][1] == "myFaction" and back[-1][2] == [], back)
    record("section_ring_never_sends_game_actions", S.spy()["sendAction"] == 0, S.spy()["calls"])
    # 只有兩個唯讀說明 modal 允許 R／SR 前進；其他 modal 維持 scope lock
    page.evaluate("showActionMessageModal('測試', '其他 modal 必須維持 scope lock')")
    S.settle()
    pad.tap("R")
    pad.tap("SR")
    locked = (S.view(), S.modals())
    pad.tap("B")
    S.poll("document.getElementById('unavailableActionModal').style.display === 'none'", timeout=1500)
    record("other_modals_keep_scope_lock_for_R_SR", locked == ("myFaction", ["unavailableActionModal"]) and not S.modals(), locked)
    # 方向鍵不會落在分頁：我的陣營內容區掃描
    S.settle()
    bad = []
    for d in ["up", "up", "left", "right", "down", "down", "left", "right"]:
        pad.push(d)
        f = S.focus()
        if f and f["forbidden"]:
            bad.append(f)
    record("stick_in_other_views_never_lands_on_section_tabs", not bad, bad[:3])
    ctx.close()


# ======================================================================== 4. PLUS faction ability
def scenario_faction(browser, base, record, errors):
    # 單張手牌：既有「賭徒耳語」只有一張時直接墊底（不另開選牌），流程一次完成。
    setup = new_game(base, ["追隨者"], faction="aomen", base_town="澳門", town="澳門")
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script(MOCK_WS)
    page = open_page(ctx, base, setup["url"] + "&display=living-room", errors)
    S = Session(page, record)
    pad, lr = S.pad, S.lr
    enable_controller(page)
    page.evaluate(SPY)
    pad.neutral()
    pad.tap("A")
    S.settle()
    ability = page.evaluate("[...document.querySelectorAll('#factionActionButtons button')].map(b => b.textContent.trim())")
    hints = S.hints()
    record("faction_ability_mirrored_by_PLUS_hint_and_kept_out_of_directional_zones",
           ability == ["發動 賭徒耳語"] and hints.get("factionAbility", {}).get("key") == "+" and "faction" not in lr()["zones"], [ability, list(hints), lr()["zones"]])
    BTN = "document.querySelector('#factionActionButtons button')"
    for variant, break_js, restore_js in [
        ("hidden", f"{BTN}.style.display = 'none'", f"{BTN}.style.display = ''"),
        ("disabled", f"{BTN}.disabled = true", f"{BTN}.disabled = false"),
        ("detached", f"window.__fab = {BTN}; window.__fabParent = window.__fab.parentElement; window.__fab.remove()",
         "window.__fabParent.appendChild(window.__fab)"),
        ("ambiguous", f"window.__fabClone = {BTN}.cloneNode(true); {BTN}.parentElement.appendChild(window.__fabClone)", "window.__fabClone.remove()"),
    ]:
        page.evaluate(break_js)
        S.settle()
        pad.tap("PLUS")
        result = (S.modals(), S.spy()["sendAction"], (lr()["lastCommand"] or {}).get("result"))
        page.evaluate(restore_js)
        S.settle()
        record(f"plus_fails_closed_when_ability_button_{variant}", result == ([], 0, "noop"), result)
    # 處理中鎖：送出到不了伺服器時 PLUS 被擋
    page.evaluate("window.__dropSends = true")
    S.goto_zone("hand")
    S.settle()
    pad.tap("X")
    S.settle(ignore_processing=True)
    pad.tap("PLUS")
    blocked = (lr()["lastCommand"] or {}).get("result")
    page.evaluate("window.__dropSends = false")
    S.poll(f"!{LR_STATE}.processing", timeout=3000)
    S.settle()
    record("plus_blocked_by_processing_lock", blocked == "processing" and not S.modals(), blocked)
    # 其他 modal 內：PLUS 不作用
    page.evaluate("showActionMessageModal('測試', 'modal 內 PLUS 不作用')")
    S.settle()
    sends = S.spy()["sendAction"]
    pad.tap("PLUS")
    in_modal = S.modals()
    pad.tap("B")
    S.poll("document.getElementById('unavailableActionModal').style.display === 'none'", timeout=1500)
    record("plus_inside_other_modal_is_ignored", in_modal == ["unavailableActionModal"] and S.spy()["sendAction"] == sends, in_modal)
    S.settle()
    # 成功：PLUS → 既有「發動 賭徒耳語」→ 既有猜奇偶視窗（不送出、不上鎖）；視窗內 250ms 冷卻
    sends = S.spy()["sendAction"]
    S.timed(["PLUS", "A"], 100)
    s = lr()
    title = page.evaluate("document.getElementById('factionActionModalTitle').textContent")
    record("plus_opens_existing_gambler_whisper_flow_and_ignores_rapid_A", S.modals() == ["factionActionModal"] and title == "賭徒耳語"
           and S.spy()["sendAction"] == sends and not s["processing"] and s["activatedAt"] is not None, [S.modals(), title, s["lastCommand"]])
    page.screenshot(path=str(OUT / "10_plus_gambler_whisper.png"))
    S.settle()
    pad.tap("B")
    S.poll("document.getElementById('factionActionModal').style.display === 'none'", timeout=1500)
    record("faction_modal_B_closes_via_existing_close", not S.modals() and S.spy()["sendAction"] == sends)
    S.settle()
    pad.tap("PLUS")
    S.settle()
    for _ in range(4):
        if "猜奇數" in ((S.focus() or {}).get("text") or ""):
            break
        pad.push("left")
    pad.tap("A")
    used = S.poll("!!window.lastGameState.faction_action_used", timeout=5000)
    S.settle()
    calls = S.spy()["calls"][sends:]
    record("plus_flow_sends_existing_faction_action_once", used and calls == ["faction_action"], calls)
    for _ in range(3):
        if not S.modals():
            break
        pad.tap("B")
        S.settle()
    pad.tap("PLUS")
    record("plus_after_ability_used_is_noop", (lr()["lastCommand"] or {}).get("result") == "noop" and S.spy()["calls"][sends:] == ["faction_action"]
           and "factionAbility" not in S.hints(), lr()["lastCommand"])
    # 玩家動態：縮小在左下角的對手通知是內容區（展開鈕），A 走既有展開、B 走既有縮小；不上處理中鎖
    page.evaluate("""() => { peerActionNoticeMinimized = true; document.getElementById('peerActionNotice').style.display = 'flex';
      applyPeerActionNoticeMinimizedState(); }""")
    S.settle()
    reached = S.goto_zone("activity")
    f = S.focus()
    S.settle()
    pad.tap("A")
    expanded = S.poll("!document.getElementById('peerActionNotice').classList.contains('peer-action-notice-minimized')", timeout=1500)
    busy = lr()["processing"]
    S.settle()
    pad.tap("B")
    minimized = S.poll("document.getElementById('peerActionNotice').classList.contains('peer-action-notice-minimized')", timeout=1500)
    record("activity_zone_peer_notice_expand_and_minimize_via_existing_controls",
           reached and "activity" in lr()["zones"] and f and f["id"] == "peerActionNoticeMinimizeBtn" and not f["forbidden"]
           and expanded and not busy and minimized and S.spy()["calls"][sends:] == ["faction_action"], [reached, f, expanded, busy, minimized])
    page.evaluate("closePeerActionNotice()")
    ctx.close()


# ======================================================================== 5. map Y build (pending choice + scope lock)
def scenario_build(browser, base, record, errors):
    setup = new_game(base, ["組織經驗丙", "追隨者", "追隨者"])
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script(MOCK_WS)
    page = open_page(ctx, base, setup["url"] + "&display=living-room", errors)
    S = Session(page, record)
    pad, lr = S.pad, S.lr
    enable_controller(page)
    page.evaluate(SPY)
    pad.neutral()
    pad.tap("A")
    S.settle()
    pad.tap("A")
    S.settle()
    record("build_fixture_focus_on_build_card", lr()["itemKey"] == "hand:0:組織經驗丙", lr())
    pad.tap("Y")
    entered = S.poll(f"document.querySelector('.game-tab.active').dataset.view === 'map' && {LR_STATE}.mapStage === 'choice'", timeout=20000)
    S.settle()
    s = lr()
    record("build_card_Y_opens_map_choice_with_build_actions", entered and s["mapRows"] and all(a == "build" for a in s["mapActs"]), s)
    mframe = map_frame(page)
    # scope lock：必選地圖目標時 R/SR/ZR 不離開地圖；STICK 留在清單；Capture 的既有按鈕停用 → fail closed
    pad.tap("R")
    pad.tap("SR")
    pad.tap("ZR")
    pad.tap("STICK")
    pad.tap("CAPTURE")
    s = lr()
    record("map_choice_scope_lock_keeps_R_SR_ZR_STICK_on_map_and_capture_fails_closed",
           S.view() == "map" and s["zone"] == "maplist" and not s["confirmOpen"] and S.spy()["calls"].count("advance") == 0, s)
    # 用滑鼠切回指揮中心：沒有任何內容區；STICK no-op；R 只能回地圖
    page.click("button.game-tab[data-view='command']")
    S.poll(f"{LR_STATE}.view === 'command'", timeout=3000)
    S.settle()
    s = lr()
    pad.tap("STICK")
    stick = lr()
    pad.tap("SR")
    back = S.poll(f"document.querySelector('.game-tab.active').dataset.view === 'map' && {LR_STATE}.zone === 'maplist'", timeout=5000)
    record("choice_lock_command_view_has_no_content_zones_and_R_SR_only_return_to_map",
           s["zones"] == [] and stick["zone"] is None and stick["layer"] == "zone" and back and lr()["sectionKey"] == "view:map", [s, stick, lr()])
    S.settle()
    town = (S.focus() or {}).get("town")
    hints = S.hints()
    record("map_hint_shows_Y_build_label_for_focused_target", town in lr()["mapRows"] and hints.get("mapAct", {}).get("label") == f"建立組織 {town}",
           [town, list(hints.values())])
    page.screenshot(path=str(OUT / "11_map_choice_Y_build.png"))
    # 沒有 iframe → fail closed
    page.evaluate("document.getElementById('strategicMapFrame').id = 'strategicMapFrameDetached'")
    pad.tap("Y")
    no_frame = lr()
    page.evaluate("document.getElementById('strategicMapFrameDetached').id = 'strategicMapFrame'")
    record("map_Y_build_no_iframe_fails_closed", (no_frame["lastMapAck"] or {}).get("outcome") == "no-frame" and not no_frame["processing"], no_frame)
    S.settle()
    # A 選取候選 → 既有「建立組織」在 iframe 內被停用 → ok:false；失敗後 <250ms 的合法 Y → 成功並由伺服器建立
    pad.tap("A")
    S.poll(f"{LR_STATE}.mapSelected === {json.dumps(town)}", timeout=5000)
    S.settle()
    orgs_before = mframe.evaluate("(t) => (lastGameState.map.towns[t] || []).filter(e => e.player === 'mover').length", town)
    page.evaluate("""() => { window.__mapResults = [];
      window.addEventListener('message', e => { if (e.data && e.data.type === 'redline-controller-result' && e.data.req) window.__mapResults.push(e.data); }); }""")
    pre = mframe.evaluate(ARM_RESTORE, ["directBuildBtn", "disabled"])
    seq = page.evaluate(RETRY_AFTER_FAILURE, [0x01, 0])
    results = page.evaluate("window.__mapResults || []")
    record("map_Y_build_ok_false_then_retry_within_250ms_succeeds",
           pre.get("disabled") is True and len(results) >= 2 and results[0].get("ok") is False and results[0].get("reason") == "button-unavailable"
           and results[1].get("ok") is True and results[1].get("via") == "directBuildBtn" and seq["gap"] < 250
           and (seq["failed"].get("lastMapAck") or {}).get("outcome") == "failed" and not seq["failed"].get("processing")
           and (seq["ok"].get("lastMapAck") or {}).get("outcome") == "success" and (seq["ok"].get("lastMapAck") or {}).get("lock") is True,
           [pre, results, seq])
    built = S.poll(f"(() => {{ const t = document.getElementById('strategicMapFrame').contentWindow.lastGameState?.map?.towns?.[{json.dumps(town)}] || []; return t.filter(e => e.player === 'mover').length > {orgs_before}; }})()", timeout=8000)
    record("map_Y_build_executes_existing_build_button_via_server", built and "build" not in S.spy()["calls"], [town, S.spy()["calls"]])
    ctx.close()


# ======================================================================== 6. map Y dissolve
def scenario_dissolve(browser, base, record, errors):
    setup = post_json(base, "/test/setup-dissolve-cancel-single-target")
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script(MOCK_WS)
    page = open_page(ctx, base, setup["url"] + "&display=living-room", errors)
    S = Session(page, record)
    pad, lr = S.pad, S.lr
    enable_controller(page)
    page.evaluate(SPY)
    pad.neutral()
    pad.tap("A")
    entered = S.poll(f"document.querySelector('.game-tab.active').dataset.view === 'map' && {LR_STATE}.mapStage === 'choice'", timeout=20000)
    S.settle()
    if lr()["zone"] != "maplist" or lr()["layer"] != "item":
        pad.tap("A")
        S.settle()
    s = lr()
    hints = S.hints()
    record("dissolve_choice_list_rows_carry_dissolve_action_and_hints", entered and s["mapRows"] == ["天津"] and s["mapActs"] == ["dissolve"]
           and hints.get("mapAct", {}).get("label") == "瓦解組織 天津" and hints.get("mapCancel", {}).get("key") == "B", [s, list(hints.values())])
    mframe = map_frame(page)
    page.screenshot(path=str(OUT / "12_map_choice_Y_dissolve.png"))
    # iframe 收不到 → 逾時 fail closed（不瓦解、不上鎖）
    page.evaluate("""() => { const w = document.getElementById('strategicMapFrame').contentWindow;
      w.__origPostMessage = w.postMessage; w.postMessage = function () {}; }""")
    pad.tap("Y")
    S.poll(f"{LR_STATE}.mapRequest === null", timeout=2500)
    timed_out = lr()
    page.evaluate("() => { const w = document.getElementById('strategicMapFrame').contentWindow; w.postMessage = w.__origPostMessage; }")
    still = mframe.evaluate("(lastGameState.map.towns['天津'] || []).length")
    record("map_Y_dissolve_timeout_fails_closed", (timed_out["lastMapAck"] or {}).get("outcome") == "timeout" and not timed_out["processing"]
           and still > 0, timed_out)
    S.settle()
    # 既有「瓦解組織」被隱藏 → ok:false；失敗後 <250ms 的合法 Y → 成功並由伺服器瓦解
    page.evaluate("""() => { window.__mapResults = [];
      window.addEventListener('message', e => { if (e.data && e.data.type === 'redline-controller-result' && e.data.req) window.__mapResults.push(e.data); }); }""")
    pad.tap("A")
    S.poll(f"{LR_STATE}.mapSelected === '天津'", timeout=5000)
    S.settle()
    pre = mframe.evaluate(ARM_RESTORE, ["dissolveBtn", "hidden"])
    seq = page.evaluate(RETRY_AFTER_FAILURE, [0x01, 0])
    results = [r for r in page.evaluate("window.__mapResults || []") if r.get("cmd") == "act"]
    record("map_Y_dissolve_ok_false_when_hidden_then_retry_within_250ms_succeeds",
           pre.get("display") == "none" and len(results) >= 2 and results[0].get("ok") is False and results[0].get("reason") == "button-unavailable"
           and results[1].get("ok") is True and results[1].get("via") == "dissolveBtn" and seq["gap"] < 250
           and (seq["ok"].get("lastMapAck") or {}).get("outcome") == "success", [pre, results, seq])
    gone = S.poll("(document.getElementById('strategicMapFrame').contentWindow.lastGameState.map.towns['天津'] || []).length === 0", timeout=8000)
    record("map_Y_dissolve_executes_existing_dissolve_button_via_server", gone and not page.evaluate("!!window.lastGameState.pending_choice"), gone)
    ctx.close()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks, console_errors = [], []

    def record(name, ok, detail=None):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {json.dumps(detail, ensure_ascii=False, default=str)[:700]}"), flush=True)

    server = None
    base = os.environ.get("REDLINE_BASE_URL", "").rstrip("/")
    if not base:
        server, base = start_server()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            for scenario in (scenario_desktop, scenario_main, scenario_sections, scenario_faction, scenario_build, scenario_dissolve):
                try:
                    scenario(browser, base, record, console_errors)
                except Exception as exc:  # 讓單一情境的意外中斷以 FAIL 呈現，其餘情境照跑
                    record(f"{scenario.__name__}_completed_without_exception", False, repr(exc))
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
