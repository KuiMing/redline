#!/usr/bin/env python3
"""客廳大螢幕（living-room）瀏覽器 E2E：真實頁面 + mock bridge，固定按鍵序列（不用 BFS 探索）。

覆蓋：顯示模式切換／桌面不變；方向鍵只在內容資料間（永不落在手牌內按鈕、結束按鈕、六個全域分頁、
購買 checkbox、陣營能力鈕或提示列）；R／SR 只循環六個全域區段（含事件卡／時代關卡說明 modal）且 scope lock 正確，
落點須為該區段內容或實際存在的地圖焦點（必須真的靜止並重驗，落點元素本身須為合法方向候選；只有確實沒有候選的區段
才允許無焦點，且 iframe 不得殘留地圖焦點標籤）；
專用快捷鍵 Capture（結束行動，危險確認、預設返回、防連按；注入實機 b1 0x40，上游 b1 0x20 另驗相容）、PLUS（陣營能力）、
手牌 B（棄置，危險確認）、購買卡 B 勾選 → Y（既有購買所選 → 購買確認單；不自動勾選）、
地圖 Y（建立組織／確認移動／瓦解組織，iframe 權威重驗＋req 對應確認；含非第一列 A 選取後的 Y 與桌面模式）、
SL 聚焦選單（統治者／陣營區域分組只來自目前合法建立目標，瓦解的 pending choice fail closed；A 只移焦點、開啟後 250ms 內被擋，
可從其他分頁切到戰略地圖；從非預設列 B／×／SL 精確還原；背景鍵 scope lock 含正向對照；選定時已選城鎮改變、一般推送只觸發
req 綁定刷新、斷線／停用與晚到回覆、缺 snapshot／逾時／候選消失 fail closed；55 吋可讀字級；選單開著時 Y 不穿透，選定後 Y 走既有建立流程）、
按下搖桿（下一個內容區）的成功與 fail-closed（hidden／disabled／detached／條件不足／處理中鎖／iframe 缺席／
逾時／過期回覆／ok:false／權威目標失效，以及失敗後 <250ms 的合法 retry 不受污染）；
卡牌既有語意不退化、處理中鎖、重繪不跨區域（含重繪後 reconcile 前的輸入 fail closed）、斷線／重連 baseline、PC 滑鼠勾選、
720p／1080p／4K 安全區與無遮擋；連線狀態 fail-closed（error／connecting／stale／off 時 feed() 不執行、提示列清空，
重連與 stale 恢復的第一筆只當 baseline，桌面模式語意不變）。

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
from validate_joycon_controller import (  # noqa: E402
    BIT, CMD_LOG_JS, DROP_TO_MAP_JS, EXECUTING_MAP_CMDS, FAST_A_JS, FIRST_IN_LIST_ORDER_JS, FOCUS_MENU_CLOSED_JS, FOCUS_MENU_JS,
    FOCUS_MENU_OPEN_JS, FOCUS_MENU_ORDER_OK_JS, GUARD_JS, HOLD_MAP_CMDS_JS, INSTALL_RESPONDER_JS, INSTRUMENT_JS, MOCK_WS,
    MOVER_ORGS_JS, PROBE_COUNTS_JS, RELEASE_MAP_CMDS_JS, RESPOND_TO_HELD_JS, RESTORE_TO_MAP_JS, SNAPSHOT_CMDS_JS, UNINSTRUMENT_JS,
    VANISH_JS, Pad, enable_controller, expected_focus_groups, focus_dom_toward, focus_town_toward, menu_counts, post_json, start_server,
)

# 客廳模式額外用到的按鍵（位元與 static/controller_core.js BUTTON_BITS 相同）。CAPTURE 一律用實機訊號：只接右 Joy-Con 2 時
# 實體 Capture 鍵送出 buttons:[0,64]（b1 0x40，上游 `c`）；上游 `capture`（b1 0x20）以 CAPTURE_COMPAT 另外驗證仍相容。
BIT.setdefault("ZR", (0, 0x80))
BIT["CAPTURE"] = (1, 0x40)
BIT["CAPTURE_COMPAT"] = (1, 0x20)
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
# 搖桿永遠不可聚焦的既有控制（兩種顯示模式相同；滑鼠照常可用）：六個全域區段、回合列（結束行動／紅軍能力）、
# 手牌卡內資源／行動／棄置、陣營能力發動鈕、按鍵提示列、卡牌勾選框。
EXCLUDED_SEL = ('#gameTabs .game-tab, #turnActionButtons button, .hand-card-action-btn, #factionActionButtons button, '
                '#lrBar, #lrBar *, [data-card-zone] input[type="checkbox"]')
# 與 static/controller_ui.js FOCUSABLE 同一份候選 selector（驗證端用來獨立重算區段內容，不讀 controller 的焦點集合）。
FOCUSABLE_SEL = ('button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], '
                 '[tabindex]:not([tabindex="-1"]), .card[data-card-zone]')

# 以 .rl-pad-focus 與「原生」焦點一起判斷：document.activeElement、:focus、:focus-visible 也不得落在排除的控制上。
FOCUS_PROBE = """() => { const el = document.querySelector('.rl-pad-focus'); if (!el) return null;
  const EX = """ + json.dumps(EXCLUDED_SEL) + """;
  const active = document.activeElement;
  const nativeForbidden = !!active && active !== document.body && !!active.matches && active.matches(EX);
  const ringForbidden = [...document.querySelectorAll(EX)].some(c => c.matches(':focus') || c.matches(':focus-visible') || c.classList.contains('rl-pad-focus'));
  const forbidden = el.matches(EX) || el.id === 'advanceStepBtn' || el.id === 'redArmyAbilityBtn'
    || !!el.closest('#gameTabs') || el.matches('.game-tab') || !!el.closest('#turnActionButtons') || !!el.closest('#lrBar')
    || !!el.closest('#factionActionButtons') || (el.matches('input[type="checkbox"]') && !!el.closest('[data-card-zone]'))
    || nativeForbidden || ringForbidden;
  return { tag: el.tagName, id: el.id || null, type: el.type || null, card: el.matches('.card[data-card-zone]'),
           zone: el.closest('[data-card-zone]')?.dataset.cardZone || null, name: el.dataset.cardName || null,
           town: el.dataset.town || null, inModal: !!el.closest('.modal-overlay'), modal: el.closest('.modal-overlay')?.id || null,
           text: (el.textContent || '').trim().slice(0, 24), forbidden }; }"""

MODALS = """() => [...document.querySelectorAll('.modal-overlay, #victoryArtViewer')]
  .filter(m => getComputedStyle(m).display !== 'none' && m.getClientRects().length > 0).map(m => m.id)"""

SETTLED = """(ignoreProcessing) => { const st = RedlineController.getState(); const s = st.livingRoom; if (!s) return !st.reconcilePending;
  const t = performance.now();
  return (s.activatedAt === null || t - s.activatedAt > 270) && (s.redrawAt === null || t - s.redrawAt > 320)
    && (ignoreProcessing || !s.processing) && !s.mapRequest && !s.reconcilePending; }"""

# SETTLED 必須連續成立 holdMs 才算靜止：iframe snapshot 往返後才排的 reconcile 也會被等到（不靠固定 sleep 猜計時器跑完沒）。
QUIESCENT = """async ([ignoreProcessing, holdMs, timeoutMs]) => {
  const settled = """ + SETTLED + """;
  const t0 = performance.now();
  let since = null;
  while (performance.now() - t0 < timeoutMs) {
    const now = performance.now();
    if (settled(ignoreProcessing)) { if (since === null) since = now; if (now - since >= holdMs) return true; }
    else since = null;
    await new Promise(r => setTimeout(r, 10));
  }
  return false;
}"""

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
  const bit = { A: [0x08, 0], B: [0x04, 0], X: [0x02, 0], Y: [0x01, 0], R: [0x40, 0], PLUS: [0, 0x02], CAPTURE: [0, 0x40], STICK: [0, 0x04] };
  for (let i = 0; i < buttons.length; i++) {
    const [b0, b1] = bit[buttons[i]];
    window.__padSend(0, 0, b0, b1);
    window.__padSend(0, 0, 0, 0);
    if (i < buttons.length - 1) await new Promise(r => setTimeout(r, gap));
  }
}"""

# 失敗回覆一到就立刻再按一次（不靠固定 sleep）；回傳兩次按壓的間隔與各階段狀態（客廳模式 livingRoom，桌面模式 shortcuts）。
RETRY_AFTER_FAILURE = """async ([b0, b1]) => {
  const st = () => { const g = RedlineController.getState(); const s = g.livingRoom || g.shortcuts || {};
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

# 手牌清空的重繪。render 完成後再等一個 microtask：MutationObserver 已排好 80ms reconcile 但計時器一定還沒跑
# （同一段 script 內，與機器快慢無關），此時讀到的是重繪前的舊焦點；press 有給就在這個窗口內按下。
EMPTY_HAND = """async (press) => {
  const lrs = () => RedlineController.getState().livingRoom;
  const s = structuredClone(window.lastGameState); const me = s.players.find(p => p.id === playerId);
  me.hand = []; me.hand_variants = []; me.hand_action_legality = [];
  await render(s);
  await Promise.resolve();
  const p = lrs();
  const pre = { zone: p.zone, layer: p.layer, itemKey: p.itemKey, zones: p.zones, reconcilePending: p.reconcilePending,
                stale: p.zone === 'hand' && p.layer === 'item' && !p.zones.includes('hand') && p.reconcilePending };
  if (!press) return { pre };
  window.__padSend(0, 0, press[0], press[1]);
  window.__padSend(0, 0, 0, 0);
  const a = lrs();
  return { pre, after: { zone: a.zone, layer: a.layer, zones: a.zones, helpOpen: RedlineController.getState().helpOpen,
    focus: !!document.querySelector('.rl-pad-focus'), confirm: a.confirmOpen,
    preview: document.getElementById('cardPreviewModal').style.display === 'flex' } };
}"""

# 連線狀態 fail-closed：以公開 RedlineController.feed()（與 bridge 訊息同一個入口）注入 neutral → 按鍵／方向 → neutral。
FEED_BURST = """(frames) => {
  const statuses = [];
  for (const [x, y, b0, b1] of frames) {
    RedlineController.feed({ x: 0, y: 0, buttons: [0, 0] });
    RedlineController.feed({ x, y, buttons: [b0, b1] });
    RedlineController.feed({ x: 0, y: 0, buttons: [0, 0] });
    statuses.push(RedlineController.getState().status);
  }
  return statuses;
}"""

# 快捷鍵／焦點／執行痕跡的快照（桌面模式 livingRoom 為 null）。
CONTROLLER_SNAPSHOT = """() => { const st = RedlineController.getState(); const lr = st.livingRoom;
  return { status: st.status, padActive: st.padActive, helpOpen: st.helpOpen, focusSig: st.focusSig,
    zone: lr ? lr.zone : null, layer: lr ? lr.layer : null, itemKey: lr ? lr.itemKey : null,
    lastCommand: lr ? lr.lastCommand : null, confirmOpen: lr ? lr.confirmOpen : null,
    hints: lr ? lr.hints.map(h => h.id) : null,
    domHints: [...document.querySelectorAll('#lrHints .lr-hint')].map(h => h.dataset.hintId),
    tab: document.querySelector('.game-tab.active')?.dataset.view || null,
    modals: [...document.querySelectorAll('.modal-overlay')].filter(m => getComputedStyle(m).display !== 'none' && m.getClientRects().length > 0).map(m => m.id),
    spy: { send: __spy.sendAction, play: __spy.play.length, toggle: __spy.toggle, preview: __spy.preview } }; }"""

# 不變式（不論有沒有 .rl-pad-focus）：排除的控制不得有控制器焦點 class、不得是 document.activeElement、
# 不得符合 :focus／:focus-visible。另回報目前的區段與 modal，供 R／SR 檢查使用。
INVARIANT = """(EX) => {
  const d = el => el ? [el.tagName, el.id || '', String(el.className || '').slice(0, 32), (el.textContent || '').trim().slice(0, 10)].join('|') : null;
  const excluded = [...document.querySelectorAll(EX)];
  const f = document.querySelector('.rl-pad-focus');
  const a = document.activeElement;
  const bad = [];
  if (f && f.matches(EX)) bad.push('rl-pad-focus:' + d(f));
  if (a && a !== document.body && a.matches && a.matches(EX)) bad.push('activeElement:' + d(a));
  for (const el of excluded) {
    if (el.matches(':focus')) bad.push('focus:' + d(el));
    if (el.matches(':focus-visible')) bad.push('focus-visible:' + d(el));
    if (el !== f && el.classList.contains('rl-pad-focus')) bad.push('class:' + d(el));
  }
  const modal = [...document.querySelectorAll('.modal-overlay')].find(m => getComputedStyle(m).display !== 'none' && m.getClientRects().length > 0);
  return { bad: [...new Set(bad)], padFocus: d(f), wholeHand: !!f && f.matches('.card[data-card-zone="hand"]'),
           inView: !!f && !!f.closest('.game-view.active'), view: document.querySelector('.game-tab.active')?.dataset.view || null,
           modal: modal ? modal.id : null,
           era: typeof eraAchievementViewId !== 'undefined' && eraAchievementViewId != null ? String(eraAchievementViewId) : null };
}"""

# 手動建立「原生焦點停在排除控制上」的既有狀態（例如滑鼠點過、或舊版控制器留下的 focus）。
SEED_FOCUS = """(sel) => { const el = document.querySelector(sel); if (!el) return null; el.focus(); return document.activeElement === el; }"""

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


def press_bits(name):
    """單一按鍵的 bridge button bytes [b0, b1]（給在頁面內同步送出的 __padSend 用）。"""
    b = [0, 0]
    i, mask = BIT[name]
    b[i] |= mask
    return b


def burst_frames():
    """所有會產生動作的按鍵與四個方向（每筆之前／之後都會補 neutral）。"""
    keys = ["X", "Y", "B", "A", "PLUS", "CAPTURE", "R", "SR", "ZR", "STICK"]
    return [[0, 0, *press_bits(k)] for k in keys] + [[1, 0, 0, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, -1, 0, 0]]


def unchanged(before, after):
    """除了連線狀態以外，焦點、提示、modal、分頁與所有執行痕跡都沒變。"""
    return {k: v for k, v in before.items() if k != "status"} == {k: v for k, v in after.items() if k != "status"}


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
        """等到 250ms 執行冷卻、300ms 重繪冷卻、地圖等待、處理中鎖與待跑的 reconcile／render 都解除，
        並連續維持 100ms（bounded polling）。"""
        return self.page.evaluate(QUIESCENT, [ignore_processing, 100, timeout])

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
    # 取樣：等 render 完成，再以 settle（沒有待跑的 80ms reconcile／50ms render 且連續靜止）為條件讀取，不靠固定時間。
    pre_empty = page.evaluate(EMPTY_HAND, None)["pre"]
    S.settle()
    emptied = lr()
    emptied_focus = focus()
    page.evaluate("render(window.lastGameState)")
    S.settle()
    record("redraw_same_state_rebinds_same_card", same, key_before)
    record("redraw_empty_zone_falls_back_to_a_content_zone_layer",
           emptied["layer"] == "zone" and emptied["zone"] in ("static", "random")
           and emptied["zone"] in emptied["zones"] and "hand" not in emptied["zones"] and not emptied["reconcilePending"]
           and emptied_focus is None, [pre_empty, emptied, emptied_focus])

    # ---- 重繪後、reconcile 跑完前的輸入：fail closed（獨立 coverage） ----
    # 舊焦點仍指向已消失的手牌時按下 X／B／Y／A：一律以當下 DOM 重新解析，只把焦點放到既有內容區的區域層，
    # 不打出、不棄置、不預覽、不送出、不開確認或說明。窗口由 EMPTY_HAND 在同一段 script 內確定（與機器快慢無關）。
    pre_reconcile_runs = []
    for key in ("X", "B", "Y", "A"):
        entered = S.goto_zone("hand")
        S.settle()
        base_spy = spy()
        out = page.evaluate(EMPTY_HAND, press_bits(key))
        S.settle()
        after_spy = spy()
        pre_reconcile_runs.append({
            "key": key, "entered": entered, **out,
            "play": len(after_spy["play"]) - len(base_spy["play"]), "send": after_spy["sendAction"] - base_spy["sendAction"],
            "preview": after_spy["preview"] - base_spy["preview"]})
        page.evaluate("render(window.lastGameState)")
        S.settle()
    record("redraw_pre_reconcile_input_fails_closed",
           all(r["entered"] and r["pre"]["stale"] and r["play"] == 0 and r["send"] == 0 and r["preview"] == 0
               and r["after"]["layer"] == "zone" and r["after"]["zone"] in ("static", "random") and r["after"]["zone"] in r["after"]["zones"]
               and not r["after"]["focus"] and not r["after"]["confirm"] and not r["after"]["preview"] and not r["after"]["helpOpen"]
               for r in pre_reconcile_runs), pre_reconcile_runs)

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
    # 焦點卡仍是勾選狀態，但勾選框在當下失效（售完／停用、被隱藏）：不再是有效勾選 → Y fail closed（既有「購買所選」仍可用也一樣）
    BOX0 = "document.querySelector('input[data-purchase-index=\"0\"]')"
    for variant, break_js, restore_js in [
        ("checkbox_disabled", f"{BOX0}.disabled = true", f"{BOX0}.disabled = false"),
        ("checkbox_hidden", f"{BOX0}.style.display = 'none'", f"{BOX0}.style.display = ''"),
    ]:
        page.evaluate(break_js)
        S.settle()
        still = (page.evaluate(f"{BOX0}.checked"), page.evaluate(f"!{BUY}.disabled"))
        pad.tap("Y")
        result = ("purchaseConfirmModal" in S.modals(), "buy_cards" in spy()["calls"], (lr()["lastCommand"] or {}).get("result"), checked())
        page.evaluate(restore_js)
        if result[0]:  # 回歸時誤開的確認單用既有關閉收起，避免後續檢查連鎖失敗
            page.evaluate("closePurchaseConfirmModal()")
        S.settle()
        record(f"purchase_Y_fails_closed_when_checked_card_{variant}", still == (True, True) and result == (False, False, "noop", ["0"]), [still, result])
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
    page.evaluate("window.__padLast = [0, 0, 0x08, 0x62]; window.__padHeartbeat = true")  # A + PLUS + 兩個 Capture 位元
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
    # SL 聚焦選單只服務建立組織：瓦解的 pending choice → fail closed（不開選單、提示列沒有 SL、不送任何動作）
    sends = S.spy()["sendAction"]
    pad.tap("SL")
    done = S.poll(f"!{LR_STATE}.focusMenuRequest && !{LR_STATE}.mapRequest", timeout=2500)
    dis_menu, dis_status = page.evaluate(FOCUS_MENU_JS), page.evaluate("document.getElementById('lrBarStatus').textContent")
    record("dissolve_choice_SL_focus_menu_fails_closed_no_build_targets",
           done and not dis_menu["open"] and "目前沒有可聚焦的地圖目標" in dis_status and "focusMenu" not in hints
           and S.spy()["sendAction"] == sends and lr()["mapSelected"] == s["mapSelected"], [dis_menu["open"], dis_status, list(hints)])
    S.settle()
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


# ======================================================================== 7. 連線狀態 fail-closed
def scenario_connection(browser, base, record, errors):
    """快捷鍵只在 bridge 已連線時鏡射／執行：error、connecting、stale、off 一律 fail closed；重連後第一筆只當 baseline。"""
    x0, x1 = press_bits("X")
    setup = new_game(base)
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script(MOCK_WS)
    page = open_page(ctx, base, setup["url"] + "&display=living-room", errors)
    enable_controller(page)
    page.evaluate(SPY)
    S = Session(page, record)
    snap = lambda: page.evaluate(CONTROLLER_SNAPSHOT)
    S.pad.neutral()
    S.pad.tap("A")
    S.goto_zone("hand")
    S.settle()
    live = snap()

    # ---- error：bridge 關閉且重連被拒 ----
    page.evaluate("window.__bridgeRefuse = true; window.__padHeartbeat = false; window.__padClose()")
    page.wait_for_function("RedlineController.getState().status === 'error'", timeout=3000)
    before = snap()
    statuses = page.evaluate(FEED_BURST, burst_frames())
    S.settle(ignore_processing=True)
    after = snap()
    record("connection_error_hides_shortcut_hints",
           live["status"] == "connected" and "cardResource" in live["hints"] and live["padActive"]
           and before["hints"] == [] and before["domHints"] == [], [live, before])
    record("connection_error_feed_never_dispatches",
           unchanged(before, after) and set(statuses) <= {"error", "connecting"}, [before, after, statuses])

    # ---- connecting：socket 尚未開啟 ----
    page.evaluate("window.__bridgeRefuse = false; window.__bridgeHold = true; RedlineController.setEnabled(true)")
    page.wait_for_function("RedlineController.getState().status === 'connecting'", timeout=3000)
    before = snap()
    statuses = page.evaluate(FEED_BURST, burst_frames())
    S.settle(ignore_processing=True)
    after = snap()
    record("connection_connecting_hides_hints_and_feed_never_dispatches",
           before["status"] == "connecting" and before["padActive"] and before["hints"] == [] and before["domHints"] == []
           and unchanged(before, after) and set(statuses) == {"connecting"}, [before, after, statuses])

    # ---- 重連：斷線期間按住的 X 在第一筆 frame 只當 baseline；放開後的合法按壓才執行 ----
    plays = before["spy"]["play"]
    page.evaluate(f"window.__padLast = [0, 0, {x0}, {x1}]; window.__padHeartbeat = true; window.__bridgeHold = false; window.__bridgeOpenHeld()")
    page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=3000)
    baseline_seen = S.poll("RedlineController.getState().held.X === true", timeout=2000)
    S.settle()
    held = snap()
    record("connection_reconnect_first_frame_is_baseline_only",
           baseline_seen and held["status"] == "connected" and held["spy"]["play"] == plays and held["spy"]["send"] == before["spy"]["send"]
           and held["modals"] == [] and not held["confirmOpen"], held)
    S.pad.neutral()
    S.settle()
    hints_back = snap()
    S.pad.tap("X")
    acted = S.poll(f"__spy.play.length === {plays + 1}", timeout=3000)
    played = S.spy()["play"][plays:]
    record("connection_reconnect_legal_frame_acts_and_hints_return",
           "cardResource" in hints_back["hints"] and "cardResource" in hints_back["domHints"] and acted
           and len(played) == 1 and played[0][2] == "resource", [hints_back["hints"], played])

    # ---- stale：socket 還在但 bridge 停止送 frame；公開 feed() 不能把它救回 connected ----
    S.settle()
    pre_stale = snap()
    page.evaluate("window.__padHeartbeat = false")
    page.wait_for_function("RedlineController.getState().status === 'stale'", timeout=5000)
    before = snap()
    statuses = page.evaluate(FEED_BURST, burst_frames())
    S.settle(ignore_processing=True)
    after = snap()
    record("connection_stale_hides_hints_and_public_feed_cannot_revive",
           pre_stale["hints"] and before["hints"] == [] and before["domHints"] == []
           and unchanged(before, after) and set(statuses) == {"stale"} and after["status"] == "stale", [pre_stale["hints"], before, after, statuses])

    # ---- stale 恢復：只有 bridge 自己的 frame 能恢復，且第一筆（按住 X）只當 baseline ----
    plays = after["spy"]["play"]
    page.evaluate(f"window.__padLast = [0, 0, {x0}, {x1}]; window.__padHeartbeat = true")
    page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=3000)
    baseline_seen = S.poll("RedlineController.getState().held.X === true", timeout=2000)
    S.settle()
    held = snap()
    S.pad.neutral()
    S.settle()
    hints_back = snap()
    S.pad.tap("X")
    acted = S.poll(f"__spy.play.length === {plays + 1}", timeout=3000)
    record("connection_stale_recovery_first_frame_is_baseline_then_acts",
           baseline_seen and held["spy"]["play"] == plays and "cardResource" in hints_back["hints"] and acted, [held, hints_back["hints"]])

    # ---- off：停用控制器 ----
    S.settle()
    page.evaluate("RedlineController.setEnabled(false)")
    page.wait_for_function("RedlineController.getState().status === 'off'", timeout=3000)
    before = snap()
    statuses = page.evaluate(FEED_BURST, burst_frames())
    S.settle(ignore_processing=True)
    after = snap()
    record("connection_off_feed_never_dispatches_and_hints_hidden",
           before["hints"] == [] and before["domHints"] == [] and unchanged(before, after) and set(statuses) == {"off"}, [before, after, statuses])
    ctx.close()

    # ---- 桌面模式：同一個入口 fail closed；重連後既有語意不變（padActive 保留，合法 R 直接切分頁） ----
    setup = new_game(base)
    dctx = browser.new_context(viewport={"width": 1280, "height": 800})
    dctx.add_init_script(MOCK_WS)
    desk = open_page(dctx, base, setup["url"], errors)
    enable_controller(desk)
    desk.evaluate(SPY)
    D = Session(desk, record)
    dsnap = lambda: desk.evaluate(CONTROLLER_SNAPSHOT)
    D.pad.neutral()
    D.pad.tap("A")
    desk.evaluate("window.__bridgeRefuse = true; window.__padHeartbeat = false; window.__padClose()")
    desk.wait_for_function("RedlineController.getState().status === 'error'", timeout=3000)
    before = dsnap()
    statuses = desk.evaluate(FEED_BURST, burst_frames())
    desk.wait_for_timeout(200)  # 負向檢查：留時間讓任何誤觸的 click／modal 生效
    after = dsnap()
    record("connection_desktop_error_feed_never_dispatches",
           before["padActive"] and before["tab"] == "command" and unchanged(before, after) and set(statuses) <= {"error", "connecting"},
           [before, after, statuses])
    desk.evaluate("window.__bridgeRefuse = false; window.__padLast = [0, 0, 0, 0]; window.__padHeartbeat = true; RedlineController.setEnabled(true)")
    desk.wait_for_function("RedlineController.getState().status === 'connected'", timeout=3000)
    D.pad.neutral()
    D.pad.tap("R")
    switched = D.poll("document.querySelector('.game-tab.active')?.dataset.view === 'map'", timeout=3000)
    record("connection_desktop_reconnect_keeps_existing_semantics",
           switched and dsnap()["padActive"] and dsnap()["spy"]["send"] == before["spy"]["send"], dsnap())
    dctx.close()


# ======================================================================== 8. 方向焦點排除（桌面＋客廳兩種顯示模式）
SECTION_KEYS_JS = """() => [...document.querySelectorAll('#gameTabs .game-tab')].filter(t => t.getClientRects().length && !t.disabled)
  .map(t => t.dataset.view ? 'view:' + t.dataset.view : t.id === 'eventCardTab' ? 'event' : 'era:' + t.dataset.eraId)"""
HAND_CARD = '#hand .card[data-card-zone="hand"]'
SEEDS = {"section": '#gameTabs .game-tab[data-view="command"]', "handAction": '#hand .hand-card-action-btn[data-card-mode="action"]',
         "endStep": '#advanceStepBtn'}
CHOICE_LOCKED_JS = "typeof lastSupportChoiceMapHighlightPayload !== 'undefined' && !!lastSupportChoiceMapHighlightPayload"


def section_reached(want):
    if want == "event":
        return "document.getElementById('eventRevealModal').style.display === 'flex'"
    if want.startswith("era:"):
        return "getComputedStyle(document.getElementById('eraAchievementModal')).display !== 'none'"
    return (f"document.querySelector('.game-tab.active')?.dataset.view === {json.dumps(want[5:])}"
            " && getComputedStyle(document.getElementById('eventRevealModal')).display === 'none'"
            " && getComputedStyle(document.getElementById('eraAchievementModal')).display === 'none'")


# R／SR 的目標容器：分頁＝.game-view.active（且分頁列的 active 正是該分頁）；事件卡／時代關卡＝對應的說明 modal。
SECTION_TARGET_JS = """(want) => {
  if (want === 'event') return document.getElementById('eventRevealModal');
  if (want.startsWith('era:')) return document.getElementById('eraAchievementModal');
  return document.querySelector('.game-tab.active')?.dataset.view === want.slice(5) ? document.querySelector('.game-view.active') : null; }"""
SHOWN_JS = """(el) => !!el && el.isConnected && el.getClientRects().length > 0
  && getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden'"""

# 合法的方向焦點候選：與 controller_ui.js collectDom／Core.isFocusableCandidate 相同的規則，由驗證端獨立重寫——
# 符合 FOCUSABLE、不是 SKIP_IDS（與紅軍能力鈕）、可見且有尺寸、未 disabled／aria-disabled、不在 [inert] 內、
# 沒有 data-controller-skip，且自己與祖先都不是排除的控制（closest(EX) 與分頁列／回合列／陣營能力／提示列）。
# 區段內容普查與落點元素本身的重驗共用這一份。
ELIGIBLE_JS = """(el, EX, FOCUSABLE) => { if (!el || el.nodeType !== 1 || !el.matches(FOCUSABLE)) return false;
  const r = el.getBoundingClientRect();
  return (""" + SHOWN_JS + """)(el) && r.width > 0 && r.height > 0 && !el.disabled && el.getAttribute('aria-disabled') !== 'true'
    && !el.closest('[inert]') && !el.hasAttribute('data-controller-skip')
    && el.id !== 'emergencyNewGameBtn' && el.id !== 'padToggleBtn' && el.id !== 'redArmyAbilityBtn'
    && !el.closest(EX) && !el.closest('#gameTabs, #turnActionButtons, #factionActionButtons, #lrBar'); }"""

# 區段切換後的落點（不是分頁本身，也不能是「沒有焦點」：changeSection() 會先清掉焦點、focusKind 設為 null 再延遲 reconcile）。
# 只有兩種情況算落點：
# 1. 唯一的 .rl-pad-focus 在目標分頁內容或目標說明 modal 內，可見、不是排除的控制，且本身就是合法的方向焦點候選（ELIGIBLE_JS）；
# 2. focusKind === 'map' 且地圖焦點真的存在：iframe 畫著該城鎮的焦點標籤（或 parent 畫著地圖按鈕外框），且仍是 adapter snapshot 的目標。
LANDED_JS = """([want, EX, FOCUSABLE]) => { const st = RedlineController.getState(); const f = document.querySelector('.rl-pad-focus');
  const shown = """ + SHOWN_JS + """;
  const eligible = """ + ELIGIBLE_JS + """;
  const target = (""" + SECTION_TARGET_JS + """)(want);
  if (!shown(target)) return false;
  if (st.focusKind === 'dom') {
    return !!f && document.querySelectorAll('.rl-pad-focus').length === 1 && target.contains(f) && shown(f) && !f.matches(EX)
      && eligible(f, EX, FOCUSABLE);
  }
  if (st.focusKind !== 'map' || want !== 'view:map' || st.scope !== 'map' || f) return false;
  try {
    const fr = document.getElementById('strategicMapFrame');
    const snap = fr.contentWindow.__redlineControllerAdapter.snapshot();
    if (st.focusTown) {
      return st.focusSig === 'town:' + st.focusTown && snap.targets.some(t => t.town === st.focusTown)
        && [...fr.contentDocument.querySelectorAll('.pad-focus-label')].some(l => l.textContent === st.focusTown);
    }
    const ring = document.getElementById('padButtonRing');
    return snap.buttons.some(b => st.focusSig === 'button:' + b.id) && !!ring && !ring.hidden && shown(ring);
  } catch (e) { return false; } }"""

# 驗證端獨立重算目標區段的方向焦點候選（ELIGIBLE_JS：與 controller_ui.js 相同的 FOCUSABLE／SKIP_IDS／可見／啟用／inert 規則，
# 再扣掉排除的控制）；戰略地圖則數 iframe adapter snapshot 的目標與按鈕。
# focusless：parent 沒有 .rl-pad-focus、沒有地圖焦點或按鈕外框，而且 iframe 內沒有任何 .pad-focus-label——clearFocus 是非同步
# postMessage，S.settle() 不能證明 iframe 已處理，所以直接數 iframe DOM（讀不到就當作有焦點，fail closed）。
SECTION_CONTENT_JS = """([want, EX, FOCUSABLE]) => { const st = RedlineController.getState();
  const shown = """ + SHOWN_JS + """;
  const eligible = """ + ELIGIBLE_JS + """;
  const target = (""" + SECTION_TARGET_JS + """)(want);
  let count = null;
  if (shown(target)) {
    if (want === 'view:map') {
      try { const s = document.getElementById('strategicMapFrame').contentWindow.__redlineControllerAdapter.snapshot(); count = s.targets.length + s.buttons.length; }
      catch (e) { count = null; }
    } else {
      count = [...target.querySelectorAll(FOCUSABLE)].filter(el => eligible(el, EX, FOCUSABLE)).length;
    }
  }
  const ring = document.getElementById('padButtonRing');
  const fr = document.getElementById('strategicMapFrame');
  let mapFocusLabels = 0;
  if (fr) { try { mapFocusLabels = fr.contentDocument.querySelectorAll('.pad-focus-label').length; } catch (e) { mapFocusLabels = null; } }
  return { count, mapFocusLabels, focusless: !document.querySelector('.rl-pad-focus') && st.focusKind === null && st.focusSig === null
    && st.focusTown === null && (!ring || ring.hidden) && mapFocusLabels === 0 }; }"""

# 回歸用：同一段 script 內按下 R／SR 並立即判斷（changeSection() 已清掉焦點，延遲的 reconcile 一定還沒跑）。
PRESS_THEN_PROBE = """([b0, b1, want, EX, FOCUSABLE]) => {
  window.__padSend(0, 0, b0, b1);
  window.__padSend(0, 0, 0, 0);
  const st = RedlineController.getState();
  return { view: document.querySelector('.game-tab.active')?.dataset.view || null, focusKind: st.focusKind,
           padFocus: !!document.querySelector('.rl-pad-focus'), landed: (""" + LANDED_JS + """)([want, EX, FOCUSABLE]),
           content: (""" + SECTION_CONTENT_JS + """)([want, EX, FOCUSABLE]) }; }"""

# 回歸用：模擬「區段 reconcile 壞掉」——只丟掉 controller 排的 80ms／160ms reconcile 計時器，其他計時器照常。
DROP_RECONCILE_JS = """() => { if (window.__realSetTimeout) return false;
  const real = window.setTimeout;
  window.__realSetTimeout = real;
  window.__droppedReconcile = 0;
  window.setTimeout = function (fn, ms, ...rest) {
    if (typeof fn === 'function' && (ms === 80 || ms === 160) && /reconcile\\(/.test(String(fn))) { window.__droppedReconcile += 1; return 0; }
    return real.call(window, fn, ms, ...rest);
  };
  return true; }"""
RESTORE_RECONCILE_JS = """() => { if (window.__realSetTimeout) { window.setTimeout = window.__realSetTimeout; delete window.__realSetTimeout; }
  return window.__droppedReconcile || 0; }"""

# 回歸用：經由真實的地圖協定（parent → iframe 'clearFocus'）讓 iframe 失去焦點；parent 端仍是 focusKind === 'map'。
MAP_DROP_FOCUS_JS = """() => { const fr = document.getElementById('strategicMapFrame');
  fr.contentWindow.postMessage({ type: 'redline-controller-command', v: RedlineControllerCore.MAP_MESSAGE_VERSION, cmd: 'clearFocus' }, location.origin);
  return RedlineController.getState().focusTown; }"""
MAP_FOCUS_LABELS_JS = "[...document.getElementById('strategicMapFrame').contentDocument.querySelectorAll('.pad-focus-label')].map(l => l.textContent)"

# 回歸用：丟掉 parent 送往 iframe 的所有地圖指令（與主情境 (b) 相同的作法）；之後的 clearFocus 到不了 iframe，焦點標籤殘留。
MAP_DROP_COMMANDS_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; if (w.__origPostMessage) return false;
  w.__origPostMessage = w.postMessage; w.__droppedCmds = []; w.postMessage = function (msg) { w.__droppedCmds.push(msg && msg.cmd); };
  return true; }"""
MAP_RESTORE_COMMANDS_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; const dropped = w.__droppedCmds || [];
  if (w.__origPostMessage) { w.postMessage = w.__origPostMessage; delete w.__origPostMessage; } delete w.__droppedCmds;
  return dropped; }"""
PARENT_FOCUSLESS_JS = """() => { const st = RedlineController.getState(); const ring = document.getElementById('padButtonRing');
  return [st.focusKind, st.focusSig, !!document.querySelector('.rl-pad-focus'), !ring || ring.hidden]; }"""

# 回歸用：每 15ms 切換一個沒有樣式的 class，MutationObserver 讓 controller 一直有待跑的 reconcile，S.settle() 必定逾時；
# 焦點本身保持合法（同一個項目的 reconcile 只會重綁原位）。
CHURN_START_JS = """() => { if (window.__settleChurn) return false;
  window.__settleChurn = setInterval(() => document.getElementById('handPanel').classList.toggle('lr-settle-churn-probe'), 15);
  return true; }"""
CHURN_STOP_JS = """() => { clearInterval(window.__settleChurn); delete window.__settleChurn;
  document.getElementById('handPanel').classList.remove('lr-settle-churn-probe'); return true; }"""

# 回歸用：把真實落點的 .rl-pad-focus 改成非法候選（呼叫前先丟掉 reconcile 計時器，controller 不會把它修好）。
# stale＝失去候選身分（整張卡沒了 data-card-zone）；nested-excluded＝類別移到排除控制（手牌「資源」鈕）內的 [role=button]。
ILLEGAL_FOCUS_JS = """([how, FOCUSABLE]) => { const f = document.querySelector('.rl-pad-focus'); if (!f) return null;
  const s = window.__illegalFocus = { how, el: f };
  if (how === 'stale') { s.prev = f.getAttribute('data-card-zone'); f.removeAttribute('data-card-zone'); }
  else if (how === 'disabled') { s.prev = f.disabled; f.disabled = true; }
  else if (how === 'aria-disabled') { s.prev = f.getAttribute('aria-disabled'); f.setAttribute('aria-disabled', 'true'); }
  else if (how === 'inert') { s.host = f.parentElement; s.host.inert = true; }
  else if (how === 'skipped') f.setAttribute('data-controller-skip', '');
  else if (how === 'nested-excluded') {
    const btn = [...f.querySelectorAll('.hand-card-action-btn')].find(b => b.getClientRects().length > 0);
    if (!btn) return { how, ok: false };
    s.probe = document.createElement('span');
    s.probe.setAttribute('role', 'button');
    s.probe.textContent = '巢狀';
    btn.appendChild(s.probe);
    f.classList.remove('rl-pad-focus');
    s.probe.classList.add('rl-pad-focus');
  }
  const now = document.querySelector('.rl-pad-focus');
  return { how, ok: !!now && document.querySelectorAll('.rl-pad-focus').length === 1 && (how !== 'stale' || !now.matches(FOCUSABLE)),
           tag: now ? now.tagName : null, cls: now ? String(now.className).slice(0, 48) : null }; }"""
ILLEGAL_REVERT_JS = """() => { const s = window.__illegalFocus; if (!s) return false; const f = s.el;
  if (s.how === 'stale') f.setAttribute('data-card-zone', s.prev);
  else if (s.how === 'disabled') f.disabled = s.prev;
  else if (s.how === 'aria-disabled') { if (s.prev === null) f.removeAttribute('aria-disabled'); else f.setAttribute('aria-disabled', s.prev); }
  else if (s.how === 'inert') s.host.inert = false;
  else if (s.how === 'skipped') f.removeAttribute('data-controller-skip');
  else if (s.how === 'nested-excluded' && s.probe) { s.probe.remove(); f.classList.add('rl-pad-focus'); }
  delete window.__illegalFocus;
  return document.querySelector('.rl-pad-focus') === f; }"""


def section_landing(S, want):
    """R／SR 之後的落點：先 bounded poll，S.settle() 必須真的靜止（逾時即失敗），之後再重驗一次，三者都要成立。
    目標區段經驗證端獨立重算確實沒有任何方向焦點候選時（分頁不是方向焦點），才改為要求「完全沒有焦點」
    （含 iframe 沒有殘留的地圖焦點標籤），同樣必須靜止。"""
    polled = S.poll(LANDED_JS, [want, EXCLUDED_SEL, FOCUSABLE_SEL], timeout=2000)
    quiescent = S.settle() is True
    settled = S.page.evaluate(LANDED_JS, [want, EXCLUDED_SEL, FOCUSABLE_SEL])
    content = S.page.evaluate(SECTION_CONTENT_JS, [want, EXCLUDED_SEL, FOCUSABLE_SEL])
    if content["count"] == 0:
        return {"mode": "empty", "ok": quiescent and content["focusless"], "quiescent": quiescent, "content": content}
    return {"mode": "landed", "ok": quiescent and polled and settled, "quiescent": quiescent, "polled": polled, "settled": settled,
            "content": content}


def section_landing_hardening_regressions(page, S, record):
    """回歸（先失敗）：靜止逾時、verified-empty 時 iframe 殘留的地圖焦點標籤、以及本身不是合法方向候選的
    .rl-pad-focus，都不得算落點；每一項前後都要有真實落點被接受（判定不是永遠 false）。起點：指揮中心。"""
    def go(key, want):
        S.pad.tap(key)
        return S.poll(section_reached(want), timeout=4000)

    h = {}
    # E. iframe 殘留焦點標籤：戰略地圖取得真實地圖焦點後，丟掉送往 iframe 的指令再 R → 戰況紀錄 → 我的陣營（verified-empty）。
    #    parent 已無焦點，但 clearFocus 沒到 iframe，標籤仍畫著。
    h["to_map"] = go("R", "view:map")
    h["map"] = section_landing(S, "view:map")
    h["map_labels"] = page.evaluate(MAP_FOCUS_LABELS_JS)
    h["drop_installed"] = page.evaluate(MAP_DROP_COMMANDS_JS)
    try:
        h["to_log"] = go("R", "view:log")
        S.settle()
        h["to_my"] = go("R", "view:myFaction")
        h["residual"] = section_landing(S, "view:myFaction")
        h["residual_parent"] = page.evaluate(PARENT_FOCUSLESS_JS)
        h["residual_labels"] = page.evaluate(MAP_FOCUS_LABELS_JS)
    finally:
        h["dropped_cmds"] = page.evaluate(MAP_RESTORE_COMMANDS_JS)
    page.evaluate(MAP_DROP_FOCUS_JS)
    h["residual_cleared"] = S.poll(f"({MAP_FOCUS_LABELS_JS}).length === 0", timeout=2000)
    h["empty_ok"] = section_landing(S, "view:myFaction")
    record("desktop_section_landing_empty_rejects_iframe_residual_focus_label",
           h["to_map"] and h["map"]["mode"] == "landed" and h["map"]["ok"] and len(h["map_labels"]) == 1 and h["drop_installed"]
           and h["to_log"] and h["to_my"] and "clearFocus" in h["dropped_cmds"]
           and h["residual_parent"] == [None, None, False, True] and h["residual_labels"] == h["map_labels"]
           and h["residual"]["mode"] == "empty" and not h["residual"]["ok"] and h["residual"]["content"].get("mapFocusLabels") == 1
           and h["residual_cleared"] and h["empty_ok"]["mode"] == "empty" and h["empty_ok"]["ok"]
           and h["empty_ok"]["content"].get("mapFocusLabels") == 0, h)

    # F. 靜止逾時：焦點狀態本身合法（verified-empty 的我的陣營／真實落點的戰況紀錄），但 controller 一直沒有靜止。
    page.evaluate(CHURN_START_JS)
    try:
        h["churn_settle_empty"] = S.settle(timeout=800)
        h["empty_churn"] = section_landing(S, "view:myFaction")
    finally:
        page.evaluate(CHURN_STOP_JS)
    h["empty_after"] = section_landing(S, "view:myFaction")
    h["to_log_back"] = go("SR", "view:log")
    h["log"] = section_landing(S, "view:log")
    page.evaluate(CHURN_START_JS)
    try:
        h["churn_settle_landed"] = S.settle(timeout=800)
        h["landed_churn"] = section_landing(S, "view:log")
    finally:
        page.evaluate(CHURN_STOP_JS)
    h["log_after"] = section_landing(S, "view:log")
    record("desktop_section_landing_rejects_settle_timeout_in_both_modes",
           h["churn_settle_empty"] is False and h["empty_churn"]["mode"] == "empty" and h["empty_churn"]["content"]["focusless"]
           and h["empty_churn"].get("quiescent") is False and not h["empty_churn"]["ok"]
           and h["empty_after"]["mode"] == "empty" and h["empty_after"]["ok"]
           and h["to_log_back"] and h["log"]["mode"] == "landed" and h["log"]["ok"]
           and h["churn_settle_landed"] is False and h["landed_churn"]["mode"] == "landed" and h["landed_churn"]["polled"]
           and h["landed_churn"]["settled"] and h["landed_churn"].get("quiescent") is False and not h["landed_churn"]["ok"]
           and h["log_after"]["ok"],
           {k: h[k] for k in ("churn_settle_empty", "empty_churn", "empty_after", "to_log_back", "log", "churn_settle_landed",
                              "landed_churn", "log_after")})

    # G. 非法的 .rl-pad-focus：從真實落點出發，丟掉 reconcile 計時器後把焦點元素改成非法候選。戰況紀錄落在真正的
    #    <button>（disabled）；指揮中心落在整張手牌（stale／aria-disabled／inert／skipped／nested-excluded）。
    def illegal(how, want):
        case = {"how": how, "before": section_landing(S, want)}
        page.evaluate(DROP_RECONCILE_JS)
        try:
            case["applied"] = page.evaluate(ILLEGAL_FOCUS_JS, [how, FOCUSABLE_SEL])
            case["landing"] = section_landing(S, want)
        finally:
            case["reverted"] = page.evaluate(ILLEGAL_REVERT_JS)
            page.evaluate(RESTORE_RECONCILE_JS)
        return case

    cases = [illegal("disabled", "view:log")]
    h["to_map_again"] = go("SR", "view:map")
    S.settle()
    h["to_command"] = go("SR", "view:command")
    for how in ("stale", "aria-disabled", "inert", "skipped", "nested-excluded"):
        cases.append(illegal(how, "view:command"))
    h["command_after"] = section_landing(S, "view:command")
    record("desktop_section_landing_rejects_illegal_focused_dom",
           [c["how"] for c in cases] == ["disabled", "stale", "aria-disabled", "inert", "skipped", "nested-excluded"]
           and h["to_map_again"] and h["to_command"]
           and all(c["before"]["mode"] == "landed" and c["before"]["ok"] and (c["applied"] or {}).get("ok")
                   and c["landing"]["mode"] == "landed" and not c["landing"]["ok"] and c["landing"].get("quiescent") is True
                   and c["landing"]["polled"] is False and c["landing"]["settled"] is False and c["reverted"] for c in cases)
           and h["command_after"]["mode"] == "landed" and h["command_after"]["ok"],
           [cases, h["to_map_again"], h["to_command"], h["command_after"]])


def scenario_directional_exclusions(browser, base, record, errors):
    """使用者截圖是桌面模式：兩種顯示模式下方向鍵都只在內容；六個全域區段只由 R／SR；結束行動只由 Capture；
    卡內按鈕由整張手牌的 X／Y／B 鏡射；原生焦點（activeElement／:focus／:focus-visible）也不得停在這些控制上。"""
    def opener(width, height, url, close_event=True):
        ctx = browser.new_context(viewport={"width": width, "height": height})
        ctx.add_init_script(MOCK_WS)
        page = open_page(ctx, base, url, errors, close_event=close_event)
        enable_controller(page)
        page.evaluate(SPY)
        return ctx, page, Session(page, record)

    def checker(page, prefix):
        violations = []

        def check(label):
            v = page.evaluate(INVARIANT, EXCLUDED_SEL)
            if v["bad"]:
                violations.append([f"{prefix}:{label}", v["bad"], v["padFocus"]])
            return v
        return violations, check

    def step(page, S, name):
        if name in ("redraw",):
            page.evaluate("render(window.lastGameState)")
        elif name == "reconcile":
            page.evaluate("document.getElementById('handPanel').classList.toggle('lr-reconcile-probe')")
        elif name in ("up", "down", "left", "right"):
            S.pad.push(name)
        else:
            S.pad.tap(name)

    # ---- 桌面模式：第一下、方向鍵掃描 ----
    setup = new_game(base)
    ctx, page, S = opener(1280, 800, setup["url"])
    pad = S.pad
    violations, check = checker(page, "desktop")
    pad.neutral()
    pad.tap("A")
    first = check("first-press")
    record("desktop_first_press_lands_on_whole_hand_card", first["wholeHand"] and not violations and S.spy()["sendAction"] == 0, first)
    hand_seen = set()
    for d in ["up"] * 4 + ["left"] * 6 + ["right"] * 10 + ["down"] * 8 + ["up"] * 12 + ["left"] * 4 + ["down"] * 6 + ["right"] * 6 + ["up"] * 8:
        pad.push(d)
        v = check(f"dpad-{d}")
        if v["wholeHand"]:
            hand_seen.add(v["padFocus"])
    record("desktop_dpad_never_focuses_sections_end_step_or_card_internal_controls",
           not violations and len(hand_seen) >= 2, [violations[:4], sorted(hand_seen)])

    # ---- 桌面模式：原生焦點先停在排除控制上，再做方向／X／Y／B／no-op／A 預覽＋B 關閉／重繪／reconcile ----
    violations.clear()
    seeded, plays = [], []
    # A 開預覽 modal、下一步 B 關閉（modal 開著時不移焦點）。
    for seed, name in [("handAction", "X"), ("section", "Y"), ("endStep", "B"), ("handAction", "ZR"), ("section", "right"),
                       ("endStep", "left"), ("section", "A"), ("handAction", "B"), ("endStep", "redraw"), ("section", "reconcile")]:
        if not S.modals() and not page.evaluate(INVARIANT, EXCLUDED_SEL)["wholeHand"]:
            focus_dom_toward(pad, page, HAND_CARD)
        S.settle()
        n_play, n_hand = len(S.spy()["play"]), page.evaluate(f"document.querySelectorAll('{HAND_CARD}').length")
        seeded.append(page.evaluate(SEED_FOCUS, SEEDS[seed]))
        step(page, S, name)
        if name not in ("redraw", "reconcile"):
            check(f"{seed}+{name}")  # 搖桿輸入：在 dispatch 內同步放掉；重繪／reconcile 在 settle 後檢查
        if name in ("X", "Y"):
            S.poll(f"__spy.play.length === {n_play + 1}", timeout=3000)
            plays.append(S.spy()["play"][n_play:])
            S.poll(f"document.querySelectorAll('{HAND_CARD}').length === {n_hand - 1}", timeout=5000)
        S.settle()
        check(f"{seed}+{name}+settled")
    record("desktop_native_focus_released_after_dpad_shortcuts_modal_redraw_and_reconcile",
           all(seeded) and not violations and [p[0][2] for p in plays if p] == ["resource", "action"] and S.modals() == [],
           [seeded, violations[:4], plays, S.modals()])

    # ---- 桌面模式：滑鼠照常可用（分頁切換、手牌按鈕），之後的搖桿輸入不留下原生焦點 ----
    violations.clear()
    page.click('#gameTabs .game-tab[data-view="log"]')
    mouse_log = S.poll("document.querySelector('.game-tab.active')?.dataset.view === 'log'", timeout=2000)
    page.click('#gameTabs .game-tab[data-view="command"]')
    mouse_cmd = S.poll("document.querySelector('.game-tab.active')?.dataset.view === 'command'", timeout=2000)
    pad.push("down")
    check("after-mouse-tab+dpad")
    n_play = len(S.spy()["play"])
    page.evaluate("""() => { const b = [...document.querySelectorAll('#hand .hand-card-action-btn[data-card-mode="resource"]')]
      .find(x => x.textContent.trim() === '資源' && !x.disabled); if (b) b.setAttribute('data-lr-mouse-probe', '1'); }""")
    page.click('[data-lr-mouse-probe="1"]')
    mouse_play = S.poll(f"__spy.play.length === {n_play + 1} && __spy.play[{n_play}][2] === 'resource'", timeout=3000)
    S.settle()
    pad.push("right")
    check("after-mouse-button+dpad")
    record("desktop_mouse_still_switches_sections_and_plays_hand_buttons",
           mouse_log and mouse_cmd and mouse_play and not violations, [mouse_log, mouse_cmd, mouse_play, violations[:3]])

    # ---- 桌面模式：Capture → 既有結束行動（危險確認、預設返回）；結束行動本身不是方向焦點 ----
    violations.clear()
    S.settle()
    page.evaluate(SEED_FOCUS, SEEDS["endStep"])
    sends = S.spy()["calls"].count("advance")
    pad.tap("CAPTURE")
    opened = S.poll("document.getElementById('lrConfirmModal')?.style.display === 'flex' && document.querySelector('.rl-pad-focus')?.id === 'lrConfirmCancelBtn'", timeout=2000)
    check("capture-open")
    pad.tap("B")
    closed = S.poll("document.getElementById('lrConfirmModal')?.style.display === 'none'", timeout=2000)
    check("capture-B")
    no_send = S.spy()["calls"].count("advance") == sends
    pad.tap("CAPTURE")
    S.poll("document.getElementById('lrConfirmModal')?.style.display === 'flex'", timeout=2000)
    pad.push("right")
    ok_focus = page.evaluate("document.querySelector('.rl-pad-focus')?.id || null")
    pad.tap("A")
    executed = S.poll(f"__spy.calls.filter(c => c === 'advance').length === {sends + 1}", timeout=3000)
    check("capture-executed")
    record("desktop_capture_runs_existing_end_step_via_danger_confirm_default_back",
           opened and closed and no_send and ok_focus == "lrConfirmOkBtn" and executed and not violations,
           [opened, closed, no_send, ok_focus, executed, violations[:3]])
    ctx.close()

    # ---- 桌面模式：PLUS → 唯一可用的既有陣營能力（賭徒耳語） ----
    setup = new_game(base, ["追隨者"], faction="aomen", base_town="澳門", town="澳門")
    ctx, page, S = opener(1280, 800, setup["url"])
    violations, check = checker(page, "desktop-plus")
    S.pad.neutral()
    S.pad.tap("A")
    usable_abilities = page.evaluate("[...document.querySelectorAll('#factionActionButtons button')].filter(b => b.getClientRects().length && !b.disabled).map(b => b.textContent.trim())")
    page.evaluate("() => { window.__abilityClicks = 0; document.getElementById('factionActionButtons').addEventListener('click', () => { window.__abilityClicks += 1; }, true); }")
    for d in ["up", "left", "down", "down", "right", "up"]:
        S.pad.push(d)
        check(f"dpad-{d}")
    S.pad.tap("PLUS")
    clicked = S.poll("window.__abilityClicks === 1", timeout=3000)
    S.settle()
    check("plus")
    record("desktop_plus_runs_single_usable_faction_ability",
           len(usable_abilities) == 1 and clicked and page.evaluate("window.__abilityClicks") == 1 and not violations,
           [usable_abilities, page.evaluate("window.__abilityClicks"), violations[:3]])
    ctx.close()

    # ---- 桌面模式：R／SR 正反兩個方向走完六個全域區段，分頁不留任何焦點 ----
    setup = post_json(base, "/test/setup-era-notification-proof", {"era_id": "mongolia", "via_lifecycle": True})
    ctx, page, S = opener(1280, 800, setup["url"], close_event=False)
    violations, check = checker(page, "desktop-sections")
    S.poll("!!document.querySelector('#activeEraTabs .era-stage-tab') && getComputedStyle(document.getElementById('eventCardTab')).display !== 'none'", timeout=5000)
    S.pad.neutral()
    for _ in range(6):
        if not S.modals():
            break
        S.pad.tap("B")
        S.settle()
    if not page.evaluate("RedlineController.getState().padActive"):
        S.pad.push("down")
    stops = page.evaluate(SECTION_KEYS_JS)
    fixture_ok = (stops[:5] == ["view:command", "view:map", "view:log", "view:myFaction", "event"] and len(stops) == 6
                  and stops[5].startswith("era:") and not S.modals() and S.view() == "command")
    visited, bad = [], []
    for key, want in [("R", w) for w in stops[1:] + stops[:2]] + [("SR", w) for w in [stops[0], stops[5], stops[4], stops[3], stops[2]]]:
        S.pad.tap(key)
        reached = S.poll(section_reached(want), timeout=4000)
        landing = section_landing(S, want)
        v = check(f"{key}->{want}")
        visited.append([key, want, v["view"], v["modal"], landing["mode"]])
        if not reached or not landing["ok"]:
            bad.append([key, want, reached, landing, v])
    # 本 fixture 只有「我的陣營」（純文字）與事件卡說明 modal（點擊任意地方關閉）沒有方向焦點候選；其他四站一定要落點。
    empty = {w for _, w, _, _, mode in visited if mode == "empty"}
    record("desktop_R_SR_traverse_all_six_sections_both_directions_without_tab_focus",
           fixture_ok and not bad and not violations and empty <= {"view:myFaction", "event"}, [stops, visited, bad[:3], violations[:3]])

    # ---- 回歸（先失敗）：區段切換後「沒有焦點」不得算落點 ----
    # 舊判定接受 `!f && focusKind !== 'dom'` 與任何 focusKind === 'map'，下面三種狀態都會被誤判為已落點。
    reg = {}
    # A. 真實的 reconcile 前窗口：戰況紀錄 SR → 戰略地圖，同一段 script 內立即判斷；之後真的 reconcile 完要能落點（判定不是永遠 false）。
    pre = reg["pre"] = page.evaluate(PRESS_THEN_PROBE, [*press_bits("SR"), "view:map", EXCLUDED_SEL, FOCUSABLE_SEL])
    reg["pre_then"] = section_landing(S, "view:map")
    # B. 地圖焦點不存在：經由真實地圖協定讓 iframe 清掉焦點，parent 仍是 focusKind === 'map'。
    reg["map_town"] = page.evaluate(MAP_DROP_FOCUS_JS)
    reg["map_cleared"] = S.poll(f"({MAP_FOCUS_LABELS_JS}).length === 0", timeout=2000)
    reg["map_state"] = page.evaluate("[RedlineController.getState().focusKind, RedlineController.getState().focusSig]")
    reg["map_lost"] = section_landing(S, "view:map")
    # C. 區段 reconcile 壞掉：丟掉 controller 的 reconcile 計時器後 SR → 指揮中心（有手牌內容），靜止後仍沒有焦點；
    #    原生焦點不變式（activeElement／:focus／:focus-visible／.rl-pad-focus）此時沒有違規，只有落點判定擋得住。
    try:
        page.evaluate(DROP_RECONCILE_JS)
        S.pad.tap("SR")
        reg["broken_reached"] = S.poll(section_reached("view:command"), timeout=4000)
        reg["broken"] = section_landing(S, "view:command")
        reg["broken_invariant_bad"] = check("broken-reconcile")["bad"]
    finally:
        reg["dropped"] = page.evaluate(RESTORE_RECONCILE_JS)
    record("desktop_section_landing_rejects_focusless_post_section_states",
           pre["view"] == "map" and pre["focusKind"] is None and not pre["padFocus"] and not pre["landed"]
           and reg["pre_then"]["mode"] == "landed" and reg["pre_then"]["ok"]
           and bool(reg["map_town"]) and reg["map_cleared"] and reg["map_state"][0] == "map"
           and reg["map_lost"]["mode"] == "landed" and not reg["map_lost"]["ok"]
           and reg["dropped"] > 0 and reg["broken_reached"] and reg["broken"]["mode"] == "landed" and not reg["broken"]["ok"]
           and reg["broken"]["content"]["focusless"] and not reg["broken_invariant_bad"],
           reg)
    # ---- 回歸（先失敗）：靜止逾時、iframe 殘留焦點標籤、非法的 .rl-pad-focus 都不得算落點 ----
    section_landing_hardening_regressions(page, S, record)
    ctx.close()

    # ---- 桌面模式：必選地圖目標時 R／SR 只回戰略地圖；方向鍵在其他分頁也碰不到分頁與回合列 ----
    setup = new_game(base, ["組織經驗丙", "追隨者", "追隨者"])
    ctx, page, S = opener(1280, 800, setup["url"])
    violations, check = checker(page, "desktop-choice")
    S.pad.neutral()
    S.pad.tap("A")
    on_build = page.evaluate("document.querySelector('.rl-pad-focus')?.dataset.cardName || null")
    S.pad.tap("Y")
    locked = S.poll(f"document.querySelector('.game-tab.active').dataset.view === 'map' && {CHOICE_LOCKED_JS}", timeout=20000)
    S.pad.tap("R")
    S.pad.tap("SR")
    stayed = S.view() == "map"
    check("choice-R-SR-on-map")
    page.click('#gameTabs .game-tab[data-view="command"]')
    S.poll("document.querySelector('.game-tab.active').dataset.view === 'command'", timeout=2000)
    for d in ["up", "up", "left", "right", "down", "right", "up"]:
        S.pad.push(d)
        check(f"choice-dpad-{d}")
    S.pad.tap("R")
    back = S.poll("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=3000)
    check("choice-R-back")
    record("desktop_choice_lock_R_SR_only_return_to_map_and_dpad_never_reaches_tabs",
           on_build == "組織經驗丙" and locked and stayed and back and not violations, [on_build, locked, stayed, back, violations[:3]])
    ctx.close()

    # ---- 客廳模式：原生焦點先停在排除控制上，再做方向／X／Y／B／no-op／STICK／R／SR／A 預覽＋B 關閉／重繪／reconcile ----
    setup = new_game(base)
    ctx, page, S = opener(1920, 1080, setup["url"] + "&display=living-room")
    violations, check = checker(page, "living-room")
    S.pad.neutral()
    S.pad.tap("A")
    seeded, plays = [], []
    # A 開預覽、CAPTURE 開危險確認：下一步 B 關閉（modal 開著時不移焦點）；R 到戰略地圖後 SR 回指揮中心（只種分頁焦點）。
    for seed, name in [("section", "right"), ("handAction", "X"), ("endStep", "Y"), ("section", "B"), ("handAction", "ZR"),
                       ("endStep", "STICK"), ("handAction", "A"), ("section", "B"), ("handAction", "redraw"),
                       ("section", "reconcile"), ("endStep", "CAPTURE"), ("section", "B"), ("section", "R"), ("section", "SR")]:
        if not S.modals() and S.view() == "command":
            S.goto_zone("hand")
        S.settle()
        n_play = len(S.spy()["play"])
        seeded.append(page.evaluate(SEED_FOCUS, SEEDS[seed]))
        step(page, S, name)
        if name not in ("redraw", "reconcile"):
            check(f"{seed}+{name}")  # 搖桿輸入：在 dispatch 內同步放掉；重繪／reconcile 在 settle 後檢查
        if name in ("X", "Y"):
            S.poll(f"__spy.play.length === {n_play + 1}", timeout=3000)
            plays.append(S.spy()["play"][n_play:])
        S.settle()
        check(f"{seed}+{name}+settled")
    record("living_room_native_focus_released_after_dpad_shortcuts_sections_modal_redraw_and_reconcile",
           all(seeded) and not violations and [p[0][2] for p in plays if p] == ["resource", "action"] and S.modals() == [],
           [seeded, violations[:4], plays, S.modals()])

    # ---- 客廳模式：滑鼠照常可用 ----
    violations.clear()
    page.click('#gameTabs .game-tab[data-view="log"]')
    mouse_log = S.poll("document.querySelector('.game-tab.active')?.dataset.view === 'log'", timeout=2000)
    page.click('#gameTabs .game-tab[data-view="command"]')
    mouse_cmd = S.poll("document.querySelector('.game-tab.active')?.dataset.view === 'command'", timeout=2000)
    S.settle()
    S.pad.push("down")
    check("after-mouse-tab+dpad")
    n_play = len(S.spy()["play"])
    page.evaluate("""() => { const b = [...document.querySelectorAll('#hand .hand-card-action-btn[data-card-mode="resource"]')]
      .find(x => x.textContent.trim() === '資源' && !x.disabled); if (b) b.setAttribute('data-lr-mouse-probe', '1'); }""")
    page.click('[data-lr-mouse-probe="1"]')
    mouse_play = S.poll(f"__spy.play.length === {n_play + 1} && __spy.play[{n_play}][2] === 'resource'", timeout=3000)
    S.settle()
    S.pad.push("right")
    check("after-mouse-button+dpad")
    record("living_room_mouse_still_switches_sections_and_plays_hand_buttons",
           mouse_log and mouse_cmd and mouse_play and not violations, [mouse_log, mouse_cmd, mouse_play, violations[:3]])

    # ---- 切換顯示模式不會把舊焦點留在（或還原到）分頁／結束行動／手牌按鈕 ----
    violations.clear()
    results = []
    for seed, mode in [("section", "desktop"), ("handAction", "living-room"), ("endStep", "desktop"), ("section", "living-room")]:
        S.settle()
        ok_seed = page.evaluate(SEED_FOCUS, SEEDS[seed])
        page.evaluate(f"window.RedlineDisplayMode.set({json.dumps(mode)})")
        S.poll(f"(document.documentElement.dataset.display || 'desktop') === {json.dumps(mode)}", timeout=2000)
        check(f"{seed}->{mode}")
        S.pad.push("down")
        S.settle()
        v = check(f"{seed}->{mode}+dpad")
        results.append([seed, mode, ok_seed, v["padFocus"]])
    record("mode_switch_never_restores_stale_section_end_step_or_card_button_focus",
           all(r[2] for r in results) and not violations, [results, violations[:4]])
    ctx.close()


# ======================================================================== 9. 實機專用鍵：Capture／購買卡 B→Y／地圖 Y（兩種顯示模式）
# 使用者實測（只接右 Joy-Con 2）：Capture 送出 buttons:[0,64]；聚焦購買卡 → B 勾選 → Y 要開既有購買確認單；
# 聚焦（必要時 A 選取）可建立組織的城鎮 → Y 要以既有「建立組織」建立。舊驗證的盲點：Capture 只注入上游 b1 0x20；
# 購買卡 Y 與地圖 Y 只在客廳模式驗證（桌面模式兩者都是 no-op／說明）；地圖只測第一列，而 A 選取後焦點被重設回第一列，剛好看不出來。
CONFIRM_BACK_JS = ("document.getElementById('lrConfirmModal')?.style.display === 'flex'"
                   " && document.querySelector('.rl-pad-focus')?.id === 'lrConfirmCancelBtn'")
CONFIRM_CLOSED_JS = "document.getElementById('lrConfirmModal')?.style.display !== 'flex'"

# 記錄 parent 送往 iframe 的帶 req 指令與 iframe 的回覆（照常轉送，不攔截）；監聽在 controller 之後註冊，看到回覆時 controller 已處理完。
ACT_LOG_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow;
  window.__actLog = { sent: [], results: [] };
  if (!w.__actLogOrig) {
    w.__actLogOrig = w.postMessage;
    w.postMessage = function (msg, ...rest) {
      if (msg && msg.type === 'redline-controller-command' && msg.req) window.__actLog.sent.push({ cmd: msg.cmd, town: msg.town || null, id: msg.id || null, req: msg.req });
      return w.__actLogOrig.call(this, msg, ...rest);
    };
    window.addEventListener('message', e => { const d = e.data;
      if (d && d.type === 'redline-controller-result' && d.req) window.__actLog.results.push({ cmd: d.cmd, req: d.req, ok: d.ok, via: d.via, reason: d.reason }); });
  }
  return true; }"""
ORGS_AT_JS = """(t) => (document.getElementById('strategicMapFrame').contentWindow.lastGameState?.map?.towns?.[t] || [])
  .filter(e => e.player === 'mover').reduce((n, e) => n + (e.count || 0), 0)"""
PURCHASE_STATE_JS = """() => { const f = document.querySelector('.rl-pad-focus');
  return { checked: [...document.querySelectorAll('input[data-purchase-index]')].filter(i => i.checked).map(i => i.dataset.purchaseIndex),
    modal: getComputedStyle(document.getElementById('purchaseConfirmModal')).display !== 'none',
    buyDisabled: document.getElementById('openPurchaseConfirmBtn').disabled,
    focusCard: f?.closest('.card[data-card-zone="purchase"]')?.querySelector('input[data-purchase-index]')?.dataset.purchaseIndex ?? null,
    focusInModal: !!f?.closest('#purchaseConfirmModal'), focusId: f?.id || null,
    buys: __spy.calls.filter(c => c === 'buy_cards').length, toggles: __spy.toggle, helpOpen: RedlineController.getState().helpOpen }; }"""


def scenario_physical_shortcuts(browser, base, record, errors):
    def opener(width, height, url):
        ctx = browser.new_context(viewport={"width": width, "height": height})
        ctx.add_init_script(MOCK_WS)
        page = open_page(ctx, base, url, errors)
        enable_controller(page)
        page.evaluate(SPY)
        S = Session(page, record)
        S.pad.neutral()
        S.pad.tap("A")  # 第一次有效操作只放焦點
        S.settle()
        return ctx, page, S

    advances = lambda S: S.spy()["calls"].count("advance")

    # ---- 桌面模式 Capture：實機 b1 0x40 → 既有結束行動危險確認（預設返回）；上游 0x20 仍相容；重連時按住不觸發 ----
    ctx, page, S = opener(1280, 800, new_game(base)["url"])
    sends = advances(S)
    S.pad.tap("CAPTURE_COMPAT")
    compat = S.poll(CONFIRM_BACK_JS, timeout=2000)
    S.pad.tap("B")
    S.poll(CONFIRM_CLOSED_JS, timeout=2000)
    S.settle()
    S.pad.tap("CAPTURE")
    opened = S.poll(CONFIRM_BACK_JS, timeout=2000)
    S.settle()
    S.pad.tap("A")  # 預設焦點「返回」→ 只關閉
    back_closed = S.poll(CONFIRM_CLOSED_JS, timeout=2000) and advances(S) == sends
    S.settle()
    page.evaluate("window.__padHeartbeat = false; window.__padClose()")
    page.wait_for_function("RedlineController.getState().status !== 'connected'", timeout=3000)
    page.evaluate("window.__padLast = [0, 0, 0, 0x40]; window.__padHeartbeat = true")
    page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
    page.wait_for_timeout(500)
    held_silent = page.evaluate(CONFIRM_CLOSED_JS) and advances(S) == sends
    S.pad.neutral()
    S.settle()
    S.pad.tap("CAPTURE")
    reopened = S.poll(CONFIRM_BACK_JS, timeout=2000)
    S.settle()
    S.pad.push("right")
    ok_focus = page.evaluate("document.querySelector('.rl-pad-focus')?.id || null")
    S.pad.tap("A")
    executed = S.poll(f"__spy.calls.filter(c => c === 'advance').length === {sends + 1}", timeout=3000)
    record("desktop_physical_capture_b1_0x40_opens_end_step_confirm_default_back_and_executes_once",
           compat and opened and back_closed and held_silent and reopened and ok_focus == "lrConfirmOkBtn" and executed
           and advances(S) == sends + 1,
           [compat, opened, back_closed, held_silent, reopened, ok_focus, executed, advances(S) - sends])
    ctx.close()

    # ---- 客廳模式 Capture：實機 b1 0x40 → 同一張確認單（預設返回）；上游 0x20 仍相容 ----
    ctx, page, S = opener(1920, 1080, new_game(base)["url"] + "&display=living-room")
    sends = advances(S)
    S.pad.tap("CAPTURE")
    lr_open = S.poll(CONFIRM_BACK_JS, timeout=2000)
    c = S.lr()["confirm"]
    S.settle()
    S.pad.tap("B")
    lr_closed = S.poll(CONFIRM_CLOSED_JS, timeout=2000)
    S.settle()
    S.pad.tap("CAPTURE_COMPAT")
    lr_compat = S.poll(CONFIRM_BACK_JS, timeout=2000)
    S.settle()
    S.pad.tap("B")
    S.poll(CONFIRM_CLOSED_JS, timeout=2000)
    record("living_room_physical_capture_b1_0x40_opens_end_step_confirm_default_back",
           lr_open and c and c["kind"] == "advance" and lr_closed and lr_compat and advances(S) == sends, [lr_open, c, lr_closed, lr_compat])
    ctx.close()

    # ---- 桌面模式購買卡：聚焦 → B 勾選 → Y 開既有購買確認單；Y 不會自動勾選，沒有有效勾選即 fail closed ----
    ctx, page, S = opener(1280, 800, new_game(base, ["追隨者"] * 4)["url"])
    # 前置（滑鼠走既有「資源」按鈕）：4 宣傳 → 宣傳家（#0，3 宣傳）買得起；加上思想家（#1，5 宣傳）就超過。
    for n in range(4, 0, -1):
        page.click('#hand .hand-card-action-btn[data-card-mode="resource"]')
        S.poll(f"document.querySelectorAll('#hand .hand-card').length === {n - 1}", timeout=5000)
    S.settle()
    propaganda = page.evaluate("window.lastGameState.players.find(p => p.id === playerId).resources.propaganda")
    card = lambda i: f'.card[data-card-zone="purchase"]:has(input[data-purchase-index="{i}"])'
    ps = lambda: page.evaluate(PURCHASE_STATE_JS)
    steps = {}
    modal_open = "getComputedStyle(document.getElementById('purchaseConfirmModal')).display !== 'none'"
    # 先驗 fail closed（未勾選、勾選的是別張、合計買不起），最後才走成功路徑
    steps["reach0"] = focus_dom_toward(S.pad, page, card(0))
    S.settle()
    S.pad.tap("Y")
    S.settle()
    steps["y_unchecked"] = ps()
    S.pad.tap("B")
    S.settle()
    steps["b_checked"] = ps()
    steps["reach1"] = focus_dom_toward(S.pad, page, card(1))
    S.settle()
    S.pad.tap("Y")
    S.settle()
    steps["y_other_unchecked"] = ps()
    S.pad.tap("B")
    S.settle()
    S.pad.tap("Y")
    S.settle()
    steps["y_unaffordable"] = ps()
    S.pad.tap("B")
    S.settle()
    steps["reach0_again"] = focus_dom_toward(S.pad, page, card(0))
    S.settle()
    # 仍勾選、但勾選框當下失效（停用／隱藏）→ 不是有效勾選，Y fail closed
    box0 = "document.querySelector('input[data-purchase-index=\"0\"]')"
    for variant, brk, rst in [("disabled", f"{box0}.disabled = true", f"{box0}.disabled = false"),
                              ("hidden", f"{box0}.style.display = 'none'", f"{box0}.style.display = ''")]:
        page.evaluate(brk)
        S.settle()
        S.pad.tap("Y")
        S.settle()
        steps[f"y_box_{variant}"] = ps()
        page.evaluate(rst)
        S.settle()
    S.pad.tap("Y")
    S.poll(modal_open, timeout=2000)
    S.settle()
    steps["y_opened"] = ps()
    page.screenshot(path=str(OUT / "20_desktop_purchase_B_then_Y_confirm.png"))
    S.pad.tap("B")
    S.poll(f"!({modal_open})", timeout=2000)
    S.settle()
    steps["modal_B"] = ps()
    S.pad.tap("Y")
    S.poll(modal_open, timeout=2000)
    S.settle()
    for _ in range(4):
        if page.evaluate("document.querySelector('.rl-pad-focus')?.id") == "confirmPurchaseBtn":
            break
        S.pad.push("right" if _ < 2 else "left")
    S.pad.tap("A")
    bought = S.poll(f"window.lastGameState.players.find(p => p.id === playerId).resources.propaganda === {propaganda - 3}", timeout=5000)
    S.settle()
    steps["bought"] = ps()
    y0, b0, op, mb = steps["y_unchecked"], steps["b_checked"], steps["y_opened"], steps["modal_B"]
    yo, yu, fin = steps["y_other_unchecked"], steps["y_unaffordable"], steps["bought"]
    record("desktop_purchase_Y_fails_closed_without_valid_checked_card_and_never_auto_checks",
           steps["reach0"] and propaganda == 4 and y0["checked"] == [] and not y0["modal"] and y0["toggles"] == 0 and y0["focusCard"] == "0"
           and y0["helpOpen"] is not True and b0["checked"] == ["0"] and not b0["buyDisabled"]
           and steps["reach1"] and yo["checked"] == ["0"] and not yo["modal"] and yo["focusCard"] == "1" and yo["toggles"] == b0["toggles"]
           and yu["checked"] == ["0", "1"] and yu["buyDisabled"] and not yu["modal"] and yu["buys"] == 0
           and all(steps[k]["checked"] == ["0"] and not steps[k]["buyDisabled"] and not steps[k]["modal"] and steps[k]["focusCard"] == "0"
                   for k in ("y_box_disabled", "y_box_hidden")), steps)
    record("desktop_purchase_focus_B_check_then_Y_opens_existing_confirm_without_buying",
           steps["reach0_again"] and op["focusCard"] is None and op["modal"] and op["focusInModal"] and op["checked"] == ["0"] and op["buys"] == 0
           and not mb["modal"] and mb["checked"] == ["0"] and mb["buys"] == 0 and mb["focusCard"] == "0", steps)
    record("desktop_purchase_B_Y_then_existing_confirm_buys_once_via_server",
           bought and fin["buys"] == 1 and fin["checked"] == [] and not fin["modal"], steps)
    ctx.close()

    # ---- 桌面模式地圖：聚焦合法建立目標 → A 選取 → Y 走 iframe 既有「建立組織」，對上 req 的 ok:true，伺服器真的建立 ----
    ctx, page, S = opener(1280, 800, new_game(base, ["組織經驗丙", "追隨者", "追隨者"])["url"])
    on_build = page.evaluate("document.querySelector('.rl-pad-focus')?.dataset.cardName || null")
    S.pad.tap("Y")  # 手牌 Y＝既有「行動」→ 伺服器 pending choice → 戰略地圖
    locked = S.poll(f"document.querySelector('.game-tab.active').dataset.view === 'map' && {CHOICE_LOCKED_JS}", timeout=20000)
    page.wait_for_function("document.getElementById('strategicMapFrame').contentWindow.lastGameState", timeout=20000)
    mframe = map_frame(page)
    S.poll("(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && !!s.focusTown; })()", timeout=8000)
    S.settle()
    snap = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
    targets = sorted(t["town"] for t in snap["targets"] if t.get("act") == "build")
    start = page.evaluate("RedlineController.getState().focusTown")
    town = next((t for t in targets if t != start), None)
    reached = bool(town) and focus_town_toward(S.pad, page, mframe, town)
    S.settle()
    S.pad.tap("A")  # 既有選取流程（marker click）
    try:  # selectedTown 是 iframe 的 top-level let，不在 window 上：在 iframe 內等
        mframe.wait_for_function("(t) => selectedTown === t", arg=town, timeout=5000, polling=20)
        selected = True
    except Exception:
        selected = False
    S.settle()
    before = {t: page.evaluate(ORGS_AT_JS, t) for t in targets}
    page.evaluate(ACT_LOG_JS)
    help_before = page.evaluate("RedlineController.getState().helpOpen")
    hint = page.evaluate("document.getElementById('padHint').textContent")
    sc = lambda: page.evaluate("RedlineController.getState().shortcuts || {}")
    base_sc = sc()
    # (a) iframe 收不到指令 → 1 秒逾時 fail closed：不建立、不上鎖、不記冷卻
    page.evaluate("""() => { const w = document.getElementById('strategicMapFrame').contentWindow;
      w.__dropKeep = w.postMessage; w.postMessage = function () {}; }""")
    S.pad.tap("Y")
    in_flight = sc()
    S.poll("RedlineController.getState().shortcuts?.mapRequest === null", timeout=2500)
    timed_out = sc()
    page.evaluate("""() => { const w = document.getElementById('strategicMapFrame').contentWindow;
      w.postMessage = w.__dropKeep; delete w.__dropKeep; }""")
    S.settle()
    # (b) iframe 內既有「建立組織」在執行當下停用 → ok:false；失敗後 <250ms 的合法 Y 不受污染 → ok:true → 伺服器建立
    pre = mframe.evaluate(ARM_RESTORE, ["directBuildBtn", "disabled"])
    seq = page.evaluate(RETRY_AFTER_FAILURE, [0x01, 0])
    built = S.poll(f"({ORGS_AT_JS})({json.dumps(town)}) > {before.get(town, 0)}", timeout=8000)
    S.settle()
    log = page.evaluate("JSON.parse(JSON.stringify(window.__actLog))")
    sent = [s for s in log["sent"] if s["cmd"] == "act"]
    res = [r for r in log["results"] if r["cmd"] == "act"]
    others = {t: page.evaluate(ORGS_AT_JS, t) for t in targets if t != town}
    timeout_ack, failed_ack, ok_ack = timed_out.get("lastMapAck") or {}, seq["failed"].get("lastMapAck") or {}, seq["ok"].get("lastMapAck") or {}
    record("desktop_map_Y_fails_closed_on_timeout_and_ok_false_without_lock_or_cooldown",
           f"Y 建立組織 {town}" in hint and (in_flight.get("mapRequest") or {}).get("cmd") == "act"
           and timeout_ack.get("outcome") == "timeout" and timed_out.get("processing") is False
           and "activatedAt" in timed_out and timed_out["activatedAt"] == base_sc.get("activatedAt")
           and pre.get("disabled") is True and len(res) >= 1 and res[0]["ok"] is False and res[0]["reason"] == "button-unavailable"
           and failed_ack.get("outcome") == "failed" and seq["failed"].get("processing") is False
           and seq["failed"].get("activatedAt") == base_sc.get("activatedAt") and seq["gap"] < 250, [hint, in_flight, timed_out, pre, seq, res])
    record("desktop_map_focus_select_then_Y_builds_focused_target_with_matching_ok_ack",
           on_build == "組織經驗丙" and locked and len(targets) >= 2 and reached and selected
           and len(sent) == 2 and all(s["town"] == town and s["id"] == "directBuildBtn" for s in sent)
           and len(res) == 2 and [r["req"] for r in res] == [s["req"] for s in sent] and res[1]["ok"] is True and res[1]["via"] == "directBuildBtn"
           and ok_ack.get("outcome") == "success" and ok_ack.get("req") == sent[1]["req"] and ok_ack.get("lock") is True
           and built and all(others[t] == before[t] for t in others) and "build" not in S.spy()["calls"]
           and page.evaluate("RedlineController.getState().helpOpen") == help_before,
           [on_build, locked, targets, start, town, reached, selected, log, ok_ack, before, others])
    ctx.close()

    # ---- 客廳模式地圖：清單選非第一列的合法建立目標 → A 選取（焦點必須留在該列）→ Y 只在該城鎮建立 ----
    ctx, page, S = opener(1920, 1080, new_game(base, ["組織經驗丙", "追隨者", "追隨者"])["url"] + "&display=living-room")
    S.pad.tap("A")  # 區域層 → 手牌內容層
    S.settle()
    on_build = S.lr()["itemKey"]
    S.pad.tap("Y")
    entered = S.poll(f"document.querySelector('.game-tab.active').dataset.view === 'map' && {LR_STATE}.mapStage === 'choice'", timeout=20000)
    S.settle()
    if S.lr()["zone"] != "maplist" or S.lr()["layer"] != "item":
        S.pad.tap("A")
        S.settle()
    rows = S.lr()["mapRows"]
    acts = S.lr()["mapActs"]
    k = len(rows) - 1
    for _ in range(len(rows) + 1):
        S.pad.push("up")
    for _ in range(k):
        S.pad.push("down")
    S.settle()
    focused = (S.focus() or {}).get("town")
    S.pad.tap("A")
    selected = S.poll(f"{LR_STATE}.mapSelected === {json.dumps(rows[k] if rows else None)}", timeout=5000)
    S.settle()
    after_select = [S.lr()["itemKey"], (S.focus() or {}).get("town"), page.evaluate(f"({MAP_FOCUS_LABELS_JS})")]
    record("living_room_map_A_select_keeps_focus_on_the_selected_choice_row",
           on_build == "hand:0:組織經驗丙" and entered and len(rows) >= 2 and all(a == "build" for a in acts) and focused == rows[k]
           and selected and after_select == [f"town:{rows[k]}", rows[k], [rows[k]]], [on_build, rows, k, focused, selected, after_select])
    before = {t: page.evaluate(ORGS_AT_JS, t) for t in rows}
    page.evaluate(ACT_LOG_JS)
    S.pad.tap("Y")
    acked = S.poll("window.__actLog.results.some(r => r.cmd === 'act')", timeout=3000)
    built = S.poll(f"({ORGS_AT_JS})({json.dumps(rows[k])}) > {before[rows[k]]}", timeout=8000)
    S.settle()
    log = page.evaluate("JSON.parse(JSON.stringify(window.__actLog))")
    sent = [s for s in log["sent"] if s["cmd"] == "act"]
    res = [r for r in log["results"] if r["cmd"] == "act"]
    ack = S.lr()["lastMapAck"] or {}
    others = {t: page.evaluate(ORGS_AT_JS, t) for t in rows if t != rows[k]}
    record("living_room_map_select_non_first_row_then_Y_builds_that_town_with_matching_ok_ack",
           acked and len(sent) == 1 and sent[0]["town"] == rows[k] and sent[0]["id"] == "directBuildBtn"
           and len(res) == 1 and res[0]["req"] == sent[0]["req"] and res[0]["ok"] is True and res[0]["via"] == "directBuildBtn"
           and ack.get("outcome") == "success" and ack.get("req") == sent[0]["req"] and ack.get("lock") is True
           and built and all(others[t] == before[t] for t in others) and "build" not in S.spy()["calls"],
           [rows, k, log, ack, before, others])
    ctx.close()


# 55 吋客廳可讀性：字級以 1280×720 設計單位計（舞台用 transform 縮放，computed font-size 即設計單位，與 GEOMETRY 相同）；
# 選單整塊在舞台內、每個選項都在面板內且未被遮擋、不是頂部窄條。
FOCUS_MENU_GEOMETRY_JS = """() => { const stage = document.getElementById('designStage').getBoundingClientRect(); const scale = stage.width / 1280;
  const glass = document.querySelector('#lrFocusMenu .lr-focus-glass').getBoundingClientRect();
  const du = el => el ? parseFloat(getComputedStyle(el).fontSize) : null;
  const opts = [...document.querySelectorAll('#lrFocusMenu .lr-focus-option')];
  const inside = r => r.left >= glass.left - 1 && r.right <= glass.right + 1 && r.top >= glass.top - 1 && r.bottom <= glass.bottom + 1;
  const hit = o => { const r = o.getBoundingClientRect(); const e = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
    return !!e && (e === o || o.contains(e)); };
  return { nameDu: du(document.querySelector('#lrFocusMenu .lr-focus-name')), countDu: du(document.querySelector('#lrFocusMenu .lr-focus-count')),
    titleDu: du(document.getElementById('lrFocusMenuTitle')),
    glassInStage: glass.left >= stage.left - 1 && glass.right <= stage.right + 1 && glass.top >= stage.top - 1 && glass.bottom <= stage.bottom + 1,
    optionsInside: opts.length > 0 && opts.every(o => inside(o.getBoundingClientRect())), optionsUnobscured: opts.length > 0 && opts.every(hit),
    notTopStrip: (glass.top - stage.top) / scale > 24 && glass.height / scale > 160,
    hudDu: document.getElementById('hud').getBoundingClientRect().height / scale, tabsDu: document.getElementById('gameTabs').getBoundingClientRect().height / scale }; }"""
BARS_DU_JS = """() => { const scale = document.getElementById('designStage').getBoundingClientRect().width / 1280;
  return { hudDu: document.getElementById('hud').getBoundingClientRect().height / scale,
           tabsDu: document.getElementById('gameTabs').getBoundingClientRect().height / scale }; }"""


def scenario_focus_menu(browser, base, record, errors):
    """客廳模式 SL 聚焦選單：組織經驗甲 → 大量合法建立目標；依統治者／陣營區域把清單焦點快速移到合法城鎮。"""
    setup = new_game(base, ["組織經驗甲", "追隨者", "追隨者"])
    ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
    ctx.add_init_script(MOCK_WS)
    page = open_page(ctx, base, setup["url"] + "&display=living-room", errors)
    S = Session(page, record)
    pad, lr = S.pad, S.lr
    enable_controller(page)
    page.evaluate(SPY)
    menu = lambda: page.evaluate(FOCUS_MENU_JS)
    status = lambda: page.evaluate("document.getElementById('lrBarStatus').textContent")
    guard = lambda: page.evaluate(GUARD_JS)
    help_shown = lambda: page.evaluate("document.getElementById('lrHelp')?.hidden === false")
    pad.neutral()
    pad.tap("A")  # 第一次有效操作只放焦點（區域層）
    S.settle()
    # 地圖從未載入 → fail closed＋短原因（提示列狀態欄）
    pad.tap("SL")
    page.wait_for_timeout(150)
    m0, s0 = menu(), status()
    record("living_room_SL_without_map_snapshot_fails_closed_with_short_reason", not m0["open"] and "地圖尚未載入" in s0, [m0, s0])
    S.settle()
    pad.tap("A")  # 區域層 → 手牌內容層
    S.settle()
    on_build = lr()["itemKey"]
    pad.tap("Y")  # 既有「行動」→ 伺服器 pending choice → 戰略地圖清單
    entered = S.poll(f"document.querySelector('.game-tab.active').dataset.view === 'map' && {LR_STATE}.mapStage === 'choice'", timeout=20000)
    S.settle()
    if lr()["zone"] != "maplist" or lr()["layer"] != "item":
        pad.tap("A")
        S.settle()
    mframe = map_frame(page)
    legal = page.evaluate("(window.lastGameState.pending_choice?.towns || []).map(t => t.town)")
    expected = expected_focus_groups(legal)
    want_counts = {k: {n: len(v) for n, v in g.items()} for k, g in expected.items()}
    t0 = (S.focus() or {}).get("town")
    page.evaluate(CMD_LOG_JS)
    mframe.evaluate(INSTALL_RESPONDER_JS)
    # 基準在打出組織經驗甲（既有 play_card 送出一次）之後取：之後選單的任何操作都不得再送出遊戲動作。
    sel0, orgs0, sends0 = lr()["mapSelected"], page.evaluate(MOVER_ORGS_JS), S.spy()["sendAction"]
    hint_ids = [h["id"] for h in lr()["hints"]]
    geo0 = page.evaluate(BARS_DU_JS)

    def executing_since(n):
        return [c for c in page.evaluate("window.__cmdLog")[n:] if c["cmd"] in EXECUTING_MAP_CMDS]

    def no_side_effects(n):
        return (S.spy()["sendAction"] == sends0 and not executing_since(n) and lr()["mapSelected"] == sel0
                and page.evaluate(MOVER_ORGS_JS) == orgs0)

    def open_menu():
        pad.tap("SL")
        ok = S.poll(FOCUS_MENU_OPEN_JS, timeout=3000)
        page.wait_for_timeout(300)  # 開啟算一次執行：250ms 內的 A 會被擋
        return ok

    def on_row(town):
        return S.poll(f"(() => {{ const s = {LR_STATE}; return s.zone === 'maplist' && s.layer === 'item' && s.itemKey === {json.dumps('town:' + str(town))}"
                      f" && document.querySelector('.rl-pad-focus')?.dataset.town === {json.dumps(town)}; }})()", timeout=3000)

    def row_town():
        key = lr()["itemKey"] or ""
        return key.split(":", 1)[1] if key.startswith("town:") else None

    n0 = page.evaluate("window.__cmdLog.length")
    a_pre = guard()["activatedAt"]
    opened = open_menu()
    m1 = menu()
    a_open = guard()["activatedAt"]
    geo = page.evaluate(FOCUS_MENU_GEOMETRY_JS)
    legend = page.evaluate("document.getElementById('lrLegend').textContent")
    page.screenshot(path=str(OUT / "30_living_room_focus_menu.png"))
    record("living_room_SL_opens_focus_menu_grouped_by_ruler_and_region_from_legal_build_targets_only",
           on_build == "hand:0:組織經驗甲" and entered and opened and len(set(legal)) >= 20 and "focusMenu" in hint_ids
           and [s["kind"] for s in m1["sections"]] == ["ruler", "camp"] and [s["title"] for s in m1["sections"]] == ["統治者", "陣營區域"]
           and menu_counts(m1) == want_counts and f"可建立組織 {len(set(legal))} 個" in m1["title"]
           and page.evaluate(FOCUS_MENU_ORDER_OK_JS, m1["sections"]) and m1["focusInMenu"] and m1["focusKey"] == m1["firstKey"]
           and "A 聚焦" in legend and a_open is not None and (a_pre is None or a_open > a_pre) and no_side_effects(n0),
           [on_build, entered, hint_ids, m1, want_counts, legend, a_pre, a_open])
    record("living_room_focus_menu_is_readable_on_55_inch_and_adds_no_top_strip",
           geo["nameDu"] >= 20 and geo["countDu"] >= 16 and geo["titleDu"] >= 24 and geo["glassInStage"] and geo["optionsInside"]
           and geo["optionsUnobscured"] and geo["notTopStrip"] and abs(geo["hudDu"] - geo0["hudDu"]) < 0.5
           and abs(geo["tabsDu"] - geo0["tabsDu"]) < 0.5, [geo, geo0])
    pad.tap("B")
    S.poll(FOCUS_MENU_CLOSED_JS)
    on_row(t0)
    S.settle()

    # 開啟後 250ms 內的 A（焦點一落到選項就按）：被執行冷卻擋下，不送選定請求；冷卻過後同一個 A 才選定並移焦點
    fast = page.evaluate(FAST_A_JS)
    page.wait_for_timeout(300)
    mf = menu()
    picks_fast = page.evaluate(SNAPSHOT_CMDS_JS, fast["sends"]) if fast else ["?"]
    if mf["open"]:
        pad.tap("A")  # 只在選單開著時按（否則 A 會落在清單列上）
    picked = mf["open"] and S.poll(FOCUS_MENU_CLOSED_JS) and S.poll(f"{LR_STATE}.zone === 'maplist' && {LR_STATE}.layer === 'item'")
    picks_late = page.evaluate(SNAPSHOT_CMDS_JS, fast["sends"]) if fast else []
    S.settle()
    record("living_room_focus_menu_A_within_250ms_of_opening_is_ignored_then_accepted",
           bool(fast) and fast["gap"] < 250 and mf["open"] and mf["focusInMenu"] and mf["focusKey"] == fast["key"] and not picks_fast
           and picked and len(picks_late) == 1 and no_side_effects(n0), [fast, mf["open"], picks_fast, picks_late])

    # scope lock＋正向對照：每個鍵先在選單開著時按（不得有任何效果），B 關閉並確認焦點回到原處後，
    # 在完全相同的情境再按一次，證明它在選單關閉時確實會執行。
    def lock_probe(key, observe, restore, undo=None):
        S.settle()
        before = observe()
        opened_ = open_menu()
        pad.tap(key)
        page.wait_for_timeout(100)
        s = menu()
        during = observe()
        locked = opened_ and s["open"] and s["focusInMenu"] and during == before and not lr()["confirmOpen"]
        pad.tap("B")
        back = S.poll(FOCUS_MENU_CLOSED_JS) and restore()
        S.settle()
        pad.tap(key)
        page.wait_for_timeout(150)
        after = observe()
        if undo:
            undo()
        return {"key": key, "locked": locked, "executed": back and after != before, "before": before, "during": during, "after": after}

    def at_zone_layer():
        return S.poll(f"{LR_STATE}.zone === 'maplist' && {LR_STATE}.layer === 'zone'")

    def to_log():
        page.click("button.game-tab[data-view='log']")  # 測試設置：滑鼠切到戰況紀錄（必選目標時沒有內容區）
        ok = S.poll("document.querySelector('.game-tab.active').dataset.view === 'log'")
        S.settle()
        return ok

    def nothing_left_in_menu():
        return S.poll("!document.querySelector('#lrFocusMenu .rl-pad-focus')")

    # 清單列（真實）：方向鍵
    t_row = row_town()
    S.settle()
    d_open = open_menu()
    k_open, n_focus = menu()["focusKey"], len([c for c in page.evaluate("window.__cmdLog") if c["cmd"] == "focus"])
    pad.push("right")
    pad.push("down")
    s_d = menu()
    map_focus_sent = len([c for c in page.evaluate("window.__cmdLog") if c["cmd"] == "focus"]) - n_focus
    pad.tap("B")
    d_back = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(t_row)
    S.settle()
    pad.push("down")
    dpad = {"key": "dpad", "locked": d_open and s_d["open"] and s_d["focusInMenu"] and s_d["focusKey"] != k_open and map_focus_sent == 0,
            "executed": d_back and row_town() not in (t_row, None), "before": t_row, "during": s_d["focusKey"], "after": row_town()}
    # Capture／PLUS（清單列）：pending choice 期間遊戲停用結束行動與陣營能力 → 暫時啟用（click 一律攔下）
    page.evaluate(INSTRUMENT_JS, [{"name": "advance", "selector": "#advanceStepBtn"},
                                  {"name": "ability", "selector": "#redArmyAbilityBtn", "show": True}])
    t_cap = row_town()
    cap = lock_probe("CAPTURE", lambda: lr()["confirmOpen"], lambda: on_row(t_cap),
                     undo=lambda: (pad.tap("B"), S.poll(f"!{LR_STATE}.confirmOpen")))
    t_plus = row_town()
    plus = lock_probe("PLUS", lambda: page.evaluate(PROBE_COUNTS_JS).get("ability", 0), lambda: on_row(t_plus))  # 之後有 1.5 秒處理中鎖
    page.evaluate(UNINSTRUMENT_JS)
    # HOME（兩種顯示模式都未綁定）：選單開著時同樣不穿透
    S.settle()
    home_before = [S.view(), lr()["itemKey"], help_shown()]
    home_open = open_menu()
    pad.tap("HOME")
    s_home = menu()
    home_ok = home_open and s_home["open"] and s_home["focusInMenu"] and [S.view(), lr()["itemKey"], help_shown()] == home_before
    pad.tap("B")
    home_ok = home_ok and S.poll(FOCUS_MENU_CLOSED_JS) and on_row(home_before[1].split(":", 1)[1])
    # 戰況紀錄（真實；必選目標時沒有內容區）：R／SR 回戰略地圖（Y 在清單列上＝建立組織，見最後一項）
    on_log = to_log()
    r = lock_probe("R", S.view, nothing_left_in_menu, undo=to_log)
    sr = lock_probe("SR", S.view, nothing_left_in_menu)
    # 地圖清單的區域層（真實）：停用後重新啟用搖桿控制，第一下只放焦點並落在區域層；Y＝說明、STICK＝進入清單
    S.settle()
    page.evaluate("() => RedlineController.setEnabled(false)")  # 與設定面板「啟用搖桿控制」同一個函式
    page.evaluate("() => RedlineController.setEnabled(true)")
    S.poll("RedlineController.getState().status === 'connected'", timeout=8000)
    pad.neutral()
    pad.tap("A")
    S.settle()
    in_zone = at_zone_layer()
    y_help = lock_probe("Y", help_shown, at_zone_layer, undo=lambda: (pad.tap("Y"), S.poll("document.getElementById('lrHelp')?.hidden !== false")))
    stick = lock_probe("STICK", lambda: lr()["layer"], at_zone_layer)
    # ZR（清單列→區域層）與 X（手牌資源）：只在必選鎖之外才會執行 → 暫時解除 parent 的必選鎖旗標（iframe 的建立目標不變，
    # 選單照常開啟），X 另外暫時啟用該張手牌的「資源」（click 在 capture 階段計數並攔下，不送出任何動作）；測試後還原。
    S.settle()
    t_zr = row_town()
    page.evaluate("() => { window.__slChoiceLock = lastSupportChoiceMapHighlightPayload; lastSupportChoiceMapHighlightPayload = null; }")
    zr = lock_probe("ZR", lambda: lr()["layer"], lambda: on_row(t_zr))
    page.click("button.game-tab[data-view='command']")
    S.poll("document.querySelector('.game-tab.active').dataset.view === 'command'")
    S.settle()
    on_hand = S.goto_zone("hand", item=True)
    hand_key = lr()["itemKey"]
    page.evaluate(INSTRUMENT_JS, [{"name": "resource", "selector": '#hand .card[data-card-zone="hand"][data-card-name="追隨者"] .hand-card-action-btn[data-card-mode="resource"]'}])
    x = lock_probe("X", lambda: page.evaluate(PROBE_COUNTS_JS).get("resource", 0),
                   lambda: S.poll(f"{LR_STATE}.zone === 'hand' && {LR_STATE}.layer === 'item' && {LR_STATE}.itemKey === {json.dumps(hand_key)}"))
    page.evaluate(UNINSTRUMENT_JS)
    page.evaluate("() => { lastSupportChoiceMapHighlightPayload = window.__slChoiceLock; delete window.__slChoiceLock; }")
    S.settle()
    pad.tap("R")  # 必選地圖目標：R 回戰略地圖
    S.poll("document.querySelector('.game-tab.active').dataset.view === 'map'")
    S.settle()
    if lr()["layer"] != "item":
        pad.tap("A")
        S.settle()
    real = [dpad, r, sr, y_help, stick]
    lifted = [zr, x]
    instrumented = [cap, plus]
    record("living_room_focus_menu_scope_lock_real_contexts_dpad_R_SR_Y_STICK_blocked_open_and_executed_closed",
           on_log and in_zone and all(p["locked"] and p["executed"] for p in real) and home_ok and no_side_effects(n0), [real, home_ok])
    record("living_room_focus_menu_scope_lock_outside_choice_lock_ZR_X_and_instrumented_capture_plus_blocked_open_and_executed_closed",
           on_hand and all(p["locked"] and p["executed"] for p in lifted + instrumented) and no_side_effects(n0), [on_hand, lifted, instrumented])

    # SL 再按／B／滑鼠 × 取消：從非預設的清單列開啟，關閉後精確回到該列（不是重新放第一列）
    S.settle()
    rows = lr()["mapRows"]
    for _ in range(4):
        if row_town() not in (rows[0], t0):
            break
        pad.push("down")
        S.settle()
    t_nd = row_town()
    restores = {}
    for how in ["SL", "B", "mouse"]:
        S.settle()
        open_menu()
        if how == "mouse":
            page.click("#lrFocusMenuClose")
        else:
            pad.tap(how)
        restores[how] = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(t_nd)
    S.settle()
    record("living_room_focus_menu_SL_again_B_and_mouse_close_restore_the_exact_non_default_row",
           t_nd not in (rows[0], t0, None) and all(restores.values()) and no_side_effects(n0), [t_nd, rows[0], t0, restores, lr()["itemKey"]])

    # A 選陣營區域（不含目前焦點）→ 清單焦點移到該區清單順序第一個合法城鎮；不選取、不建立；成功移焦點才開始執行冷卻
    camps = m1["sections"][1]["groups"]
    g1 = next((g for g in camps if t_nd not in expected["camp"][g["name"]] and g["count"] >= 2), None)
    want1 = page.evaluate(FIRST_IN_LIST_ORDER_JS, sorted(expected["camp"][g1["name"]])) if g1 else None
    open_menu()
    reached1 = bool(g1) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g1["key"]}"]')
    page.wait_for_timeout(320)
    a_pick0 = guard()["activatedAt"]
    pad.tap("A")
    moved = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(want1)
    a_pick1 = guard()["activatedAt"]
    S.settle()
    labels1 = mframe.evaluate("[...document.querySelectorAll('.pad-focus-label')].map(l => l.textContent)")
    page.screenshot(path=str(OUT / "31_living_room_focus_menu_pick.png"))
    record("living_room_focus_menu_A_moves_list_focus_to_first_legal_town_of_group_without_action",
           reached1 and moved and labels1 == [want1] and want1 in lr()["mapRows"] and a_pick0 is not None and a_pick1 is not None
           and a_pick1 > a_pick0 and no_side_effects(n0), [g1, want1, lr()["itemKey"], labels1, executing_since(n0), a_pick0, a_pick1])

    # 從其他分頁（指揮中心；必選目標時沒有內容區）開選單 → A 經既有分頁切換回戰略地圖並聚焦該城鎮
    page.click("button.game-tab[data-view='command']")
    S.poll(f"{LR_STATE}.view === 'command'", timeout=3000)
    S.settle()
    cmd_zones = lr()["zones"]
    rulers = m1["sections"][0]["groups"]
    g2 = next((g for g in rulers[1:] if want1 not in expected["ruler"][g["name"]]), None)
    want2 = page.evaluate(FIRST_IN_LIST_ORDER_JS, sorted(expected["ruler"][g2["name"]])) if g2 else None
    from_cmd = open_menu()
    reached2 = bool(g2) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g2["key"]}"]')
    page.wait_for_timeout(320)
    pad.tap("A")
    switched = S.poll(FOCUS_MENU_CLOSED_JS) and S.poll("document.querySelector('.game-tab.active').dataset.view === 'map'") and on_row(want2)
    S.settle()
    record("living_room_focus_menu_from_command_view_switches_to_map_via_existing_tab_and_focuses_town",
           cmd_zones == [] and from_cmd and reached2 and switched and lr()["sectionKey"] == "view:map" and no_side_effects(n0),
           [cmd_zones, g2, want2, lr()["itemKey"], lr()["sectionKey"]])

    # 選定分組包含目前焦點 → 保留目前焦點
    t2 = want2
    firsts = {g["key"]: page.evaluate(FIRST_IN_LIST_ORDER_JS, sorted(expected[s["kind"]][g["name"]]))
              for s in m1["sections"] for g in s["groups"] if t2 in expected[s["kind"]][g["name"]]}
    g3key = next((k for k, first in firsts.items() if first != t2), None)
    open_menu()
    reached3 = bool(g3key) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g3key}"]')
    page.wait_for_timeout(320)
    pad.tap("A")
    kept = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(t2)
    S.settle()
    record("living_room_focus_menu_keeps_current_focus_when_it_belongs_to_the_chosen_group",
           reached3 and kept and no_side_effects(n0), [t2, g3key, firsts, lr()["itemKey"]])

    # 開啟後 pending choice 的已選城鎮改變（iframe 權威資料改了、尚未推送）→ 選定時 fail closed：刷新選單、不移焦點
    sel_to = next(t for t in sorted(set(legal)) if t != t2)
    open_menu()
    n_dr = page.evaluate("window.__cmdLog.length")
    mframe.evaluate("(t) => { window.__slSelBackup = selectedTown; selectedTown = t; }", sel_to)
    pad.tap("A")
    drift_flash = S.poll("document.getElementById('lrBarStatus').textContent.includes('地圖狀態已改變')", timeout=2500)
    m_dr = menu()
    drift_focus = [c for c in page.evaluate("window.__cmdLog")[n_dr:] if c["cmd"] == "focus"]
    drift_shown = page.evaluate(f"{LR_STATE}.focusMenu")
    mframe.evaluate("() => { selectedTown = window.__slSelBackup; delete window.__slSelBackup; refreshDirectBuildUi(); }")
    S.poll(f"{LR_STATE}.focusMenu && {LR_STATE}.focusMenu.selected === null", timeout=2500)
    pad.tap("B")
    drift_back = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(t2)
    S.settle()
    record("living_room_focus_menu_pick_fails_closed_when_the_pending_choice_selection_changed_since_open",
           drift_flash and m_dr["open"] and m_dr["focusInMenu"] and not drift_focus and (drift_shown or {}).get("selected") == sel_to
           and drift_back and lr()["mapSelected"] == sel0 and no_side_effects(n0), [sel_to, m_dr["open"], drift_focus, drift_shown, drift_back])

    # 選單開著時的一般推送（不帶 req、內容過期）不直接更新選單：只觸發一次新的 req 綁定 snapshot 請求，畫面以那份回覆為準
    g_v = next((g for g in reversed(rulers) if t2 not in expected["ruler"][g["name"]]), None)
    gone_v = sorted(expected["ruler"][g_v["name"]]) if g_v else []
    open_menu()
    n_rf = page.evaluate("window.__cmdLog.length")
    stale_push = mframe.evaluate("() => window.__redlineControllerAdapter.snapshot()")  # 消失前的內容（不帶 req）
    mframe.evaluate(VANISH_JS, gone_v)  # 權威資料改變，但不推送
    mframe.evaluate("(m) => window.parent.postMessage(m, location.origin)", stale_push)
    refreshed_rf = S.poll("(k) => !document.querySelector(`#lrFocusMenu .lr-focus-option[data-key=\"${k}\"]`)", g_v["key"] if g_v else "")
    asked_rf = page.evaluate(SNAPSHOT_CMDS_JS, n_rf)
    S.poll("!!document.querySelector('#lrFocusMenu .rl-pad-focus')")  # 選項重建後 reconcile 把焦點放回選單內
    m_rf = menu()
    mframe.evaluate("() => applySupportChoiceHighlight(window.__hlBackup)")  # 既有推送 → 再一次 req 綁定刷新
    back_rf = S.poll("(k) => !!document.querySelector(`#lrFocusMenu .lr-focus-option[data-key=\"${k}\"]`)", g_v["key"] if g_v else "")
    asked_rf2 = page.evaluate(SNAPSHOT_CMDS_JS, n_rf)
    pad.tap("B")
    rf_closed = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(t2)
    S.settle()
    record("living_room_focus_menu_refreshes_only_from_request_bound_snapshots_not_from_routine_pushes",
           bool(g_v) and "req" not in stale_push and all(t in {x["town"] for x in stale_push["targets"]} for t in gone_v)
           and refreshed_rf and len(asked_rf) >= 1 and all(isinstance(c["req"], int) for c in asked_rf) and m_rf["open"] and m_rf["focusInMenu"]
           and back_rf and len(asked_rf2) > len(asked_rf) and rf_closed and no_side_effects(n0),
           {"group": g_v, "refreshed": refreshed_rf, "asked": asked_rf, "asked_after_restore": asked_rf2, "open": m_rf["open"],
            "focusInMenu": m_rf["focusInMenu"], "back": back_rf, "closed": rf_closed})

    # 候選在選定瞬間消失 → fail closed：選單刷新、焦點不移到消失的城鎮
    g4 = next((g for g in reversed(rulers) if t2 not in expected["ruler"][g["name"]]), None)
    gone = sorted(expected["ruler"][g4["name"]]) if g4 else []
    open_menu()
    reached4 = bool(g4) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g4["key"]}"]')
    page.wait_for_timeout(320)
    n4 = page.evaluate("window.__cmdLog.length")
    left = mframe.evaluate(VANISH_JS, gone)
    pad.tap("A")
    refreshed = S.poll("(k) => !document.querySelector(`#lrFocusMenu .lr-focus-option[data-key=\"${k}\"]`)", g4["key"] if g4 else "")
    s4, m4 = status(), menu()
    focused_gone = [c for c in page.evaluate("window.__cmdLog")[n4:] if c["cmd"] == "focus" and c["town"] in gone]
    mframe.evaluate("() => applySupportChoiceHighlight(window.__hlBackup)")
    back = S.poll("(k) => !!document.querySelector(`#lrFocusMenu .lr-focus-option[data-key=\"${k}\"]`)", g4["key"] if g4 else "")
    pad.tap("B")
    restored = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(t2)
    S.settle()
    record("living_room_focus_menu_candidates_vanishing_at_selection_fail_closed_and_menu_refreshes",
           reached4 and left == len(set(legal)) - len(gone) and refreshed and m4["open"] and m4["focusInMenu"]
           and "此範圍已沒有合法目標" in s4 and not focused_gone and back and restored and no_side_effects(n0),
           [g4, left, m4, s4, focused_gone, back, restored])

    # bridge 斷線／控制器停用：開著的選單關閉、等待中的開啟請求作廢，晚到的 ok:true＋同一個 req 的 snapshot 不會再開啟
    connected = "RedlineController.getState().status === 'connected'"
    open_menu()
    page.evaluate("() => window.__padClose()")
    dc_closed = S.poll(FOCUS_MENU_CLOSED_JS, timeout=2000)
    dc_reconnected = S.poll(connected, timeout=8000)
    pad.neutral()
    page.wait_for_timeout(300)
    dc_still = not menu()["open"]
    S.settle()
    page.evaluate(HOLD_MAP_CMDS_JS)
    pad.tap("SL")
    pending_req = guard()["menuRequest"]
    page.evaluate("() => window.__padClose()")
    S.poll(f"!({connected})", timeout=2000)
    cleared = guard()["menuRequest"] is None
    held = page.evaluate(RESPOND_TO_HELD_JS, [{"kind": "result", "ok": True, "at": 0}, {"kind": "snapshot", "at": 5}])
    page.wait_for_timeout(400)
    late_open = menu()["open"]
    late_arrivals = page.evaluate("window.__slArrivals || []")
    page.evaluate(RELEASE_MAP_CMDS_JS)
    S.poll(connected, timeout=8000)
    pad.neutral()
    page.wait_for_timeout(300)
    S.settle()
    late_still = not menu()["open"]
    open_menu()
    page.evaluate("() => RedlineController.setEnabled(false)")  # 與設定面板「啟用搖桿控制」取消勾選同一個函式
    off_closed = S.poll(FOCUS_MENU_CLOSED_JS, timeout=2000) and not page.evaluate("RedlineController.getState().padActive")
    page.evaluate("() => RedlineController.setEnabled(true)")
    S.poll(connected, timeout=8000)
    pad.neutral()
    pad.tap("A")  # 重新啟用後第一下只放焦點
    S.settle()
    if lr()["layer"] != "item":
        pad.tap("A")
        S.settle()
    record("living_room_focus_menu_closes_on_disconnect_or_disable_and_late_replies_never_open_it",
           dc_closed and dc_reconnected and dc_still and bool(pending_req) and cleared and bool(held)
           and [a["type"] for a in late_arrivals if held and a["req"] == held["req"]] == ["result", "snapshot"] and not late_open and late_still and off_closed
           and not menu()["open"] and no_side_effects(n0),
           [dc_closed, dc_reconnected, dc_still, pending_req, cleared, late_arrivals, late_open, late_still, off_closed])

    # iframe 沒有回應：期間的一般推送不得開選單；1 秒逾時 fail closed
    t2 = row_town()
    page.evaluate(DROP_TO_MAP_JS)
    pad.tap("SL")
    mframe.evaluate("() => refreshDirectBuildUi()")
    page.wait_for_timeout(300)
    mid = menu()["open"]
    expired = S.poll(f"{LR_STATE}.mapRequest === null", timeout=2500)
    s5, end = status(), menu()["open"]
    page.evaluate(RESTORE_TO_MAP_JS)
    S.settle()
    record("living_room_focus_menu_stale_snapshot_request_fails_closed",
           not mid and expired and not end and "地圖沒有回應" in s5 and lr()["itemKey"] == f"town:{t2}" and no_side_effects(n0), [mid, expired, end, s5])

    # 選定的城鎮仍走既有地圖操作：選單開著時 Y 不穿透；B 關閉後同一個 Y → iframe act（unique req）→ 對上 req 的 ok:true → 伺服器建立
    S.settle(ignore_processing=False, timeout=4000)
    na = page.evaluate("window.__cmdLog.length")
    y_open = open_menu()
    pad.tap("Y")
    page.wait_for_timeout(300)
    y_blocked = menu()["open"] and not [c for c in page.evaluate("window.__cmdLog")[na:] if c["cmd"] == "act"]
    pad.tap("B")
    y_back = S.poll(FOCUS_MENU_CLOSED_JS) and on_row(t2)
    S.settle()
    at_t2 = page.evaluate(ORGS_AT_JS, t2)
    page.evaluate("""() => { window.__slResults = []; window.addEventListener('message', e => {
      if (e.data && e.data.type === 'redline-controller-result' && e.data.cmd === 'act') window.__slResults.push(e.data); }); }""")
    pad.tap("Y")
    built = S.poll(f"({ORGS_AT_JS})({json.dumps(t2)}) > {at_t2}", timeout=8000)
    S.settle(ignore_processing=True)
    acts = [c for c in page.evaluate("window.__cmdLog")[na:] if c["cmd"] == "act"]
    results = page.evaluate("window.__slResults")
    ack = lr()["lastMapAck"] or {}
    record("living_room_SL_focused_town_Y_is_locked_while_open_then_builds_via_existing_req_ack_path",
           y_open and y_blocked and y_back and built and len(acts) == 1 and acts[0]["town"] == t2 and acts[0]["id"] == "directBuildBtn"
           and len(results) == 1 and results[0]["req"] == acts[0]["req"] and results[0]["ok"] is True and ack.get("outcome") == "success"
           and ack.get("req") == acts[0]["req"] and "build" not in S.spy()["calls"], [t2, y_blocked, acts, results, ack])
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
            for scenario in (scenario_desktop, scenario_main, scenario_sections, scenario_faction, scenario_build, scenario_dissolve,
                             scenario_connection, scenario_directional_exclusions, scenario_physical_shortcuts, scenario_focus_menu):
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
