#!/usr/bin/env python3
"""Joy-Con／搖桿控制的瀏覽器 E2E（真實頁面 + mock bridge WebSocket）。

不碰實體 Joy-Con：以 add_init_script 取代 `ws://127.0.0.1:8000/ws` 的 WebSocket，
由測試注入 {x, y, buttons:[b0,b1]} frame；其餘連線（遊戲 / 地圖）仍走真實 WebSocket。
驗證：預設不連線、焦點與高對比標示、A click、B cancel、modal 優先權、卡牌 A 預覽／B 選擇／手牌 X 資源／Y 行動、
購買卡 Y（未選擇或買不起時 fail closed，不自動選擇）、實機 Capture（b1 0x40）危險確認、斷線重連不誤觸、
地圖目標焦點、非法目標 fail-closed、iframe 訊息來源驗證、SL 聚焦選單（統治者／陣營區域分組只來自目前合法建立目標，
移動來源／目的地 fail closed；A 只移焦點且開啟後 250ms 內被擋；從非預設焦點 B／×／SL 精確還原；背景鍵 scope lock 含正向對照；
從指揮中心選定；協定整合：ok:false／錯的 req／不合 schema／snapshot 先於 ok:true／1000ms 逾時邊界；缺 snapshot／逾時／
候選消失／無目標／canonical 分組資料不合法 fail closed 且不開始執行冷卻；選單開著時 Y 不穿透，選定後 Y 走既有建立流程）、
ZR 戰略地圖縮放循環（min→…→max→min、每下一級、中心／焦點／選取／預備移動／遊戲狀態不變、Leaflet min／max；iframe `zoom`＋唯一 req，
對上的 ok:true 才記錄成功；缺 req／錯的 req／不合 schema／ok:false／逾時／逾時後／重複的回覆、modal、iframe 隱藏或不在、等待中離開地圖或停用、
停用、斷線、重連中、stale、重連時按住、非地圖分頁一律 fail closed）。
（購買卡 B→Y 成功、地圖 Y 建立見客廳驗證的 scenario_physical_shortcuts）

執行（會自動啟動隔離 server，不會碰 8100）：
  uv run python scripts/validate/validate_joycon_controller.py
或指定已啟動的 server：REDLINE_BASE_URL=http://127.0.0.1:8793 uv run python ...
輸出：/tmp/redline-joycon-proof/（截圖與 JSON；不要 commit）
"""

import json
import math
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("REDLINE_JOYCON_PROOF_DIR", "/tmp/redline-joycon-proof"))
BRIDGE_URL = "ws://127.0.0.1:8000/ws"
# CAPTURE＝實機訊號：只接右 Joy-Con 2 時實體 Capture 鍵送出 buttons:[0,64]（b1 0x40，上游 `c`）。
BIT = {"A": (0, 0x08), "B": (0, 0x04), "X": (0, 0x02), "Y": (0, 0x01), "R": (0, 0x40), "SR": (0, 0x10), "PLUS": (1, 0x02),
       "CAPTURE": (1, 0x40), "SL": (0, 0x20), "ZR": (0, 0x80), "STICK": (1, 0x04), "HOME": (1, 0x10)}
MAP_TOWNS = json.loads((ROOT / "data" / "map.json").read_text(encoding="utf-8"))["towns"]

# SL 聚焦選單的可見狀態（只讀 DOM）：分區、每個選項的 key／名稱／城鎮數、目前焦點是否在選單內。
FOCUS_MENU_JS = """() => { const m = document.getElementById('lrFocusMenu');
  const open = !!m && getComputedStyle(m).display !== 'none' && m.getClientRects().length > 0;
  const f = document.querySelector('.rl-pad-focus');
  return { open, title: open ? (document.getElementById('lrFocusMenuTitle')?.textContent || '') : '',
    sections: open ? [...m.querySelectorAll('[data-focus-section]')].map(s => ({ kind: s.dataset.focusSection,
      title: (s.querySelector('.lr-focus-section-title')?.textContent || '').trim(),
      groups: [...s.querySelectorAll('.lr-focus-option')].map(o => ({ key: o.dataset.key, name: o.dataset.name, count: Number(o.dataset.count) })) })) : [],
    focusKey: f ? (f.dataset.key || null) : null, focusInMenu: !!f && !!m && m.contains(f),
    firstKey: open ? (m.querySelector('.lr-focus-option')?.dataset.key || null) : null }; }"""
# 每區：城鎮數多者在前，同數依 zh-Hant 名稱。
FOCUS_MENU_ORDER_OK_JS = """(sections) => { const zh = new Intl.Collator('zh-Hant');
  return sections.length > 0 && sections.every(s => s.groups.every((g, i) => i === 0 || s.groups[i - 1].count > g.count
    || (s.groups[i - 1].count === g.count && zh.compare(s.groups[i - 1].name, g.name) <= 0))); }"""
FOCUS_MENU_OPEN_JS = "(() => { const m = document.getElementById('lrFocusMenu'); return !!m && getComputedStyle(m).display !== 'none'; })()"
FOCUS_MENU_CLOSED_JS = f"!{FOCUS_MENU_OPEN_JS}"
# 清單順序（pending choice＝依城鎮名稱 zh-Hant）的第一個城鎮。
FIRST_IN_LIST_ORDER_JS = "(towns) => [...towns].sort(new Intl.Collator('zh-Hant').compare)[0]"
# 記錄 parent 送往 iframe 的所有指令（照常轉送）：證明 SL 選單只送 snapshot／focus／clearFocus，不送 act／activate／button／cancel。
CMD_LOG_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow;
  window.__cmdLog = window.__cmdLog || [];
  if (!w.__cmdLogOrig) {
    w.__cmdLogOrig = w.postMessage;
    w.postMessage = function (msg, ...rest) {
      if (msg && msg.type === 'redline-controller-command') window.__cmdLog.push({ cmd: msg.cmd, town: msg.town || null, id: msg.id || null, req: msg.req || null });
      return w.__cmdLogOrig.call(this, msg, ...rest);
    };
  }
  return window.__cmdLog.length; }"""
EXECUTING_MAP_CMDS = ("act", "activate", "button", "cancel")
MOVER_ORGS_JS = """() => Object.values(document.getElementById('strategicMapFrame').contentWindow.lastGameState?.map?.towns || {})
  .flat().filter(e => e.player === 'mover').reduce((n, e) => n + (e.count || 0), 0)"""
# iframe 權威資料在「選定瞬間」改變：直接改 supportChoiceHighlight（不觸發推送），讓下一份 snapshot 才反映。
VANISH_JS = """(gone) => { window.__hlBackup = supportChoiceHighlight;
  supportChoiceHighlight = { ...supportChoiceHighlight, towns: supportChoiceHighlight.towns.filter(t => !gone.includes(t.town)) };
  return supportChoiceHighlight.towns.length; }"""
DROP_TO_MAP_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; if (w.__slDropKeep) return false;
  w.__slDropKeep = w.postMessage; w.postMessage = function () {}; return true; }"""
RESTORE_TO_MAP_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; if (!w.__slDropKeep) return false;
  w.postMessage = w.__slDropKeep; delete w.__slDropKeep; return true; }"""
# 協定整合測試的 shim：parent 送往 iframe 的指令改為「記錄但不送達」（含送出時間），回覆改由測試在 iframe 內偽造
# （以 iframe realm 的函式 postMessage，event.source／origin 與真實回覆相同，parent 的來源驗證照常通過）。
HOLD_MAP_CMDS_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; if (w.__slHoldKeep) return false;
  window.__slHeld = []; w.__slHoldKeep = w.postMessage;
  w.postMessage = function (msg) { if (msg && msg.type === 'redline-controller-command')
    window.__slHeld.push({ cmd: msg.cmd, req: msg.req ?? null, at: performance.now(), abs: performance.timeOrigin + performance.now() }); };
  return true; }"""
RELEASE_MAP_CMDS_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; if (!w.__slHoldKeep) return false;
  w.postMessage = w.__slHoldKeep; delete w.__slHoldKeep; return true; }"""
# iframe 端（mframe.evaluate）：安裝回覆器。steps＝[{kind:'result'|'snapshot'|'raw', ok, req, at（相對 parent 送出時間的 ms）, msg}]；
# snapshot＝以權威資料重算（__redlineControllerAdapter.snapshot(req)），raw＝原樣送出（例如不合 schema 的 snapshot）。
INSTALL_RESPONDER_JS = """() => { window.__slRespond = (abs, steps) => { for (const s of steps) {
    const wait = Math.max(0, abs + s.at - (performance.timeOrigin + performance.now()));
    setTimeout(() => {
      const msg = s.kind === 'result' ? { type: 'redline-controller-result', v: 1, cmd: 'snapshot', req: s.req, ok: s.ok, reason: s.ok ? null : 'test-refused', via: null }
        : s.kind === 'snapshot' ? window.__redlineControllerAdapter.snapshot(s.req) : s.msg;
      window.parent.postMessage(msg, location.origin);
    }, wait);
  } return true; }; return true; }"""
# parent 端：取最後一個被攔下的 snapshot 請求，交給 iframe 回覆器排程（req 由 steps 的 reqOffset 決定）；同時記錄每則回覆到達 parent 的時間。
RESPOND_TO_HELD_JS = """(steps) => { const held = (window.__slHeld || []).filter(c => c.cmd === 'snapshot' && c.req).pop();
  if (!held) return null;
  window.__slArrivals = [];
  const watch = e => { const d = e.data; if (d && (d.type === 'redline-controller-result' || d.type === 'redline-controller-map-snapshot'))
    window.__slArrivals.push({ type: d.type === 'redline-controller-result' ? 'result' : 'snapshot', req: d.req ?? null, ok: d.ok ?? null, ms: performance.now() - held.at }); };
  window.removeEventListener('message', window.__slWatch || (() => {})); window.__slWatch = watch; window.addEventListener('message', watch);
  const w = document.getElementById('strategicMapFrame').contentWindow;
  w.__slRespond(held.abs, steps.map(s => ({ ...s, req: s.kind === 'raw' ? null : held.req + (s.reqOffset || 0) })));
  return held; }"""
# 遊戲在任何 pending choice 期間都會停用的既有控制（結束行動、陣營能力、手牌資源／行動）：測試把它暫時設為可用，
# 讓「選單關閉時這個鍵確實會執行」可被觀察；對它的 click 在 document capture 階段計數並攔下（既有 handler 不會執行、不送出任何動作）。
INSTRUMENT_JS = """(specs) => { const P = window.__probe = window.__probe || { counts: {}, saved: [], listener: null };
  if (!P.listener) { P.listener = e => { const hit = P.saved.find(s => s.el === e.target || s.el.contains(e.target)); if (!hit) return;
      P.counts[hit.name] += 1; e.stopImmediatePropagation(); e.preventDefault(); };
    document.addEventListener('click', P.listener, true); }
  return specs.map(spec => { const el = document.querySelector(spec.selector); if (!el) return false;
    P.saved.push({ name: spec.name, el, disabled: el.disabled, display: el.style.display, aria: el.getAttribute('aria-disabled') });
    P.counts[spec.name] = 0; el.disabled = false; el.removeAttribute('aria-disabled'); if (spec.show) el.style.display = 'inline-flex';
    return true; }); }"""
UNINSTRUMENT_JS = """() => { const P = window.__probe; if (!P) return false;
  for (const s of P.saved.reverse()) { s.el.disabled = s.disabled; s.el.style.display = s.display;
    if (s.aria === null) s.el.removeAttribute('aria-disabled'); else s.el.setAttribute('aria-disabled', s.aria); }
  document.removeEventListener('click', P.listener, true); delete window.__probe; return true; }"""
PROBE_COUNTS_JS = "() => ({ ...(window.__probe?.counts || {}) })"
# 頁面內按 SL 開啟選單；搖桿焦點一落在第一個選項就立即（同一個 task）按 A：此時距開啟不到 250ms，必須被執行冷卻擋下。
FAST_A_JS = """async () => { window.__padSend(0, 0, 0x20, 0); window.__padSend(0, 0, 0, 0);
  const t0 = performance.now();
  while (performance.now() - t0 < 3000) {
    const m = document.getElementById('lrFocusMenu'); const f = document.querySelector('#lrFocusMenu .lr-focus-option.rl-pad-focus');
    if (m && m.style.display === 'flex' && f) { const st = RedlineController.getState(); const g = st.livingRoom || st.shortcuts || {};
      const gap = performance.now() - g.activatedAt; const sends = (window.__cmdLog || []).length;
      window.__padSend(0, 0, 0x08, 0); window.__padSend(0, 0, 0, 0);
      return { gap, key: f.dataset.key, sends }; }
    await new Promise(r => setTimeout(r, 4)); }
  return null; }"""
# iframe 的 canonical 地圖資料（/map-data）：把某個合法城鎮的分組欄位改成不合法（測試後還原）。
CORRUPT_GROUP_JS = """([town, field, value]) => { const t = byName.get(town); if (!t) return false;
  window.__slMeta = window.__slMeta || []; window.__slMeta.push([town, field, Object.prototype.hasOwnProperty.call(t, field), t[field]]);
  if (value === null) delete t[field]; else t[field] = value; return true; }"""
RESTORE_GROUP_JS = """() => { for (const [town, field, had, value] of (window.__slMeta || []).reverse()) { const t = byName.get(town);
  if (had) t[field] = value; else delete t[field]; } delete window.__slMeta; refreshDirectBuildUi(); return true; }"""
# controller 的唯讀狀態（兩種顯示模式）：執行冷卻時間與最後一個專用鍵指令。
GUARD_JS = "() => { const st = RedlineController.getState(); const g = st.livingRoom || st.shortcuts || {}; return { activatedAt: g.activatedAt ?? null, lastCommand: g.lastCommand || null, mapRequest: g.mapRequest || null, menuRequest: g.focusMenuRequest || null }; }"
SNAPSHOT_CMDS_JS = "(n) => (window.__cmdLog || []).slice(n).filter(c => c.cmd === 'snapshot')"

# ---- ZR 戰略地圖縮放循環（兩種顯示模式共用的驗證工具） ----
# 循環範圍（產品端 RedlineControllerCore.MAP_ZOOM_CYCLE，驗證端獨立寫一份）；實際範圍＝它與 Leaflet getMinZoom／getMaxZoom 的交集。
ZR_CYCLE = (2, 10)
# iframe realm：Leaflet 視角與地圖互動狀態（只讀）。maxZoom＝Infinity 時回傳 null。
ZR_VIEW_JS = """() => { const c = map.getCenter(); const max = map.getMaxZoom();
  return { zoom: map.getZoom(), lat: c.lat, lng: c.lng, minZoom: map.getMinZoom(), maxZoom: Number.isFinite(max) ? max : null,
    selected: selectedTown ?? null, pending: pendingMoveTarget ? JSON.stringify(pendingMoveTarget) : null,
    moves: JSON.stringify((selectedMoveTargets || []).map(t => t.town)),
    highlight: supportChoiceHighlight ? JSON.stringify((supportChoiceHighlight.towns || []).map(t => t.town)) : null,
    labels: [...document.querySelectorAll('.pad-focus-label')].map(l => l.textContent) }; }"""
# iframe realm：測試設置用（直接以 Leaflet API 設定層級，不是產品路徑）。
ZR_SET_ZOOM_JS = "(z) => { map.setView(map.getCenter(), z, { animate: false }); return map.getZoom(); }"
# parent：controller 狀態（兩種顯示模式）＋遊戲狀態雜湊（任何 state 改變都會反映）。
ZR_STATE_JS = """() => { const st = RedlineController.getState(); const g = st.livingRoom || st.shortcuts || {};
  const s = JSON.stringify(window.lastGameState || null); let h = 0; for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) | 0;
  return { status: st.status, padActive: st.padActive, focusKind: st.focusKind, focusTown: st.focusTown, focusSig: st.focusSig, scope: st.scope,
    helpOpen: st.helpOpen, view: document.querySelector('.game-tab.active')?.dataset.view || null,
    activatedAt: g.activatedAt ?? null, processing: !!g.processing, mapRequest: g.mapRequest || null, lastMapAck: g.lastMapAck || null,
    lastCommand: g.lastCommand || null, sends: window.__spy ? window.__spy.sendAction : null, stateHash: h,
    hint: document.getElementById('padHint')?.textContent || '', barStatus: document.getElementById('lrBarStatus')?.textContent || '' }; }"""
# parent：記錄 iframe 的 zoom 回覆（監聽在 controller 之後註冊：看到回覆時 controller 已經處理完）。
ZR_RESULTS_JS = """() => { if (!window.__zrResults) { window.__zrResults = [];
    window.addEventListener('message', e => { const d = e.data;
      if (d && d.type === 'redline-controller-result' && d.cmd === 'zoom') window.__zrResults.push({ req: d.req ?? null, ok: d.ok, reason: d.reason ?? null }); }); }
  return window.__zrResults.length; }"""
ZR_SENT_JS = "() => (window.__cmdLog || []).filter(c => c.cmd === 'zoom').map(c => c.req)"
# parent：攔下（不送達）parent 送往 iframe 的 zoom 指令，保留原訊息；ZR_DELIVER_JS 之後可以照原樣送達（其他指令照常）。
ZR_HOLD_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; if (w.__zrHoldKeep) return false;
  window.__zrHeld = []; w.__zrHoldKeep = w.postMessage;
  w.postMessage = function (msg, ...rest) {
    if (msg && msg.type === 'redline-controller-command' && msg.cmd === 'zoom') { window.__zrHeld.push({ msg, req: msg.req ?? null, at: performance.now() }); return; }
    return w.__zrHoldKeep.call(this, msg, ...rest); };
  return true; }"""
ZR_DELIVER_JS = """(i) => { const w = document.getElementById('strategicMapFrame').contentWindow; const h = window.__zrHeld[i];
  w.__zrHoldKeep.call(w, h.msg, location.origin); return h.req; }"""
ZR_RELEASE_JS = """() => { const w = document.getElementById('strategicMapFrame').contentWindow; if (!w.__zrHoldKeep) return false;
  w.postMessage = w.__zrHoldKeep; delete w.__zrHoldKeep; return true; }"""
# iframe realm：偽造 zoom 回覆（以 iframe 的 window.parent.postMessage 送出，parent 的來源驗證照常通過）；r 原樣合併（可缺 req）。
ZR_FORGE_JS = """(r) => { window.parent.postMessage(Object.assign({ type: 'redline-controller-result', v: 1, cmd: 'zoom', reason: null, via: null }, r),
  location.origin); return true; }"""


def zr_next(view):
    """驗證端獨立計算：Leaflet min／max 與 ZR_CYCLE 的交集內，min → min+1 → … → max → min。"""
    lo = max(math.ceil(view["minZoom"]), ZR_CYCLE[0])
    hi = ZR_CYCLE[1] if view["maxZoom"] is None else min(math.floor(view["maxZoom"]), ZR_CYCLE[1])
    z = view["zoom"]
    return lo if z >= hi - 1e-6 or z < lo - 1e-6 else min(hi, math.floor(z + 1e-6) + 1)


def same_center(a, b):
    return abs(a["lat"] - b["lat"]) < 1e-9 and abs(a["lng"] - b["lng"]) < 1e-9


def expected_focus_groups(towns):
    """伺服器 pending choice 的合法城鎮 × canonical data/map.json 的統治者／陣營區域 → {kind: {name: set(towns)}}（獨立計算）。"""
    out = {"ruler": {}, "camp": {}}
    for town in set(towns):
        for kind in ("ruler", "camp"):
            for name in set(MAP_TOWNS[town].get(kind) or []):
                out[kind].setdefault(name, set()).add(town)
    return out


def menu_counts(menu):
    return {s["kind"]: {g["name"]: g["count"] for g in s["groups"]} for s in menu["sections"]}

MOCK_WS = """
(() => {
  const RealWS = window.WebSocket;
  window.__mockBridges = [];
  window.__bridgeAttempts = 0;
  class MockBridge {
    constructor(url) {
      this.url = url; this.readyState = 0; this.onopen = this.onmessage = this.onclose = this.onerror = null;
      window.__bridgeAttempts += 1;
      window.__mockBridges.push(this);
      // __bridgeRefuse：bridge 沒開（連線中 → 關閉 → error）；__bridgeHold：停在連線中，直到 __bridgeOpenHeld()。預設皆關閉。
      if (window.__bridgeRefuse) { setTimeout(() => { if (this.readyState === 0) { this.readyState = 3; this.onclose && this.onclose({}); } }, 0); return; }
      if (window.__bridgeHold) return;
      setTimeout(() => { if (this.readyState === 0) { this.readyState = 1; this.onopen && this.onopen({}); } }, 20);
    }
    send() {}
    close() { if (this.readyState === 3) return; this.readyState = 3; setTimeout(() => this.onclose && this.onclose({}), 0); }
  }
  window.WebSocket = function (url, protocols) {
    if (String(url) === 'ws://127.0.0.1:8000/ws') return new MockBridge(url);
    return protocols === undefined ? new RealWS(url) : new RealWS(url, protocols);
  };
  Object.assign(window.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
  // 真實 bridge 以 30Hz 持續送出目前狀態；mock 以 heartbeat 重現（stale 測試時關閉）。
  window.__padLast = [0, 0, 0, 0];
  window.__padHeartbeat = true;
  const emit = () => {
    const live = window.__mockBridges.filter(b => b.readyState === 1).pop();
    if (!live || !live.onmessage) return false;
    const [x, y, b0, b1] = window.__padLast;
    live.onmessage({ data: JSON.stringify({ x, y, buttons: [b0, b1] }) });
    return true;
  };
  window.__padSend = (x, y, b0, b1) => { window.__padLast = [x, y, b0, b1]; return emit(); };
  setInterval(() => { if (window.__padHeartbeat) emit(); }, 33);
  window.__padClose = () => { const live = window.__mockBridges.filter(b => b.readyState === 1).pop(); if (live) live.close(); };
  window.__bridgeRefuse = false;
  window.__bridgeHold = false;
  window.__bridgeOpenHeld = () => {
    const held = window.__mockBridges.filter(b => b.readyState === 0).pop();
    if (!held) return false;
    held.readyState = 1;
    held.onopen && held.onopen({});
    return true;
  };
})();
"""

SPY = """
() => {
  window.__spy = { sendAction: 0, cancelChoice: 0 };
  const orig = window.sendAction;
  if (typeof orig === 'function') window.sendAction = function (...a) { window.__spy.sendAction += 1; if (a[0] === 'cancel_choice') window.__spy.cancelChoice += 1; return orig.apply(this, a); };
}
"""


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server():
    port = free_port()
    env = {**os.environ, "ENABLE_TEST_ROUTES": "true"}
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/static/controller_core.js", timeout=1)
            return proc, base
        except Exception:
            time.sleep(0.3)
    proc.terminate()
    raise SystemExit("isolated server did not start")


def post_json(base, path, payload=None):
    req = urllib.request.Request(base + path, data=json.dumps(payload or {}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


class Pad:
    def __init__(self, page):
        self.page = page

    def frame(self, x=0.0, y=0.0, held=()):
        b = [0, 0]
        for name in held:
            i, m = BIT[name]
            b[i] |= m
        return self.page.evaluate("([x, y, b0, b1]) => window.__padSend(x, y, b0, b1)", [x, y, b[0], b[1]])

    def neutral(self):
        self.frame()
        self.page.wait_for_timeout(30)

    def tap(self, name):
        self.frame(held=[name])
        self.page.wait_for_timeout(30)
        self.neutral()
        self.page.wait_for_timeout(120)

    def push(self, direction):
        x, y = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[direction]
        self.frame(x, y)
        self.page.wait_for_timeout(30)
        self.neutral()
        self.page.wait_for_timeout(120)


def focus_info(page):
    return page.evaluate(
        """() => {
          const el = document.querySelector('.rl-pad-focus');
          if (!el) return null;
          const cs = getComputedStyle(el);
          const after = getComputedStyle(el, '::after');
          const peer = [...document.querySelectorAll('.card')].find((card) => card !== el && !card.classList.contains('rl-pad-focus'));
          const peerCs = peer ? getComputedStyle(peer) : null;
          return { id: el.id, tag: el.tagName, text: (el.textContent || '').trim().slice(0, 30),
                   outlineWidth: parseFloat(cs.outlineWidth), outlineColor: cs.outlineColor,
                   boxShadow: cs.boxShadow, overlayBackground: after.backgroundColor,
                   peerOutlineWidth: peerCs ? parseFloat(peerCs.outlineWidth) : null,
                   peerBoxShadow: peerCs ? peerCs.boxShadow : null,
                   inModal: !!el.closest('.modal-overlay'), modalId: el.closest('.modal-overlay')?.id || null,
                   cls: el.className };
        }"""
    )


FOCUS_KEY_JS = """(sel) => {
  const el = document.querySelector('.rl-pad-focus');
  if (!el) return null;
  const host = el.closest('[data-card-name]');
  const base = [el.tagName, el.id, host ? host.dataset.cardZone + ':' + host.dataset.cardName : '', el.dataset.cardMode || '',
                el.dataset.view || '', (el.textContent || '').trim().slice(0, 12)].join('|');
  const same = [...document.querySelectorAll('.rl-pad-focus, *')].filter(n => n.matches && n.matches(el.tagName.toLowerCase()) &&
    [n.tagName, n.id, (n.closest('[data-card-name]') ? n.closest('[data-card-name]').dataset.cardZone + ':' + n.closest('[data-card-name]').dataset.cardName : ''),
     n.dataset.cardMode || '', n.dataset.view || '', (n.textContent || '').trim().slice(0, 12)].join('|') === base);
  const target = sel ? document.querySelector(sel) : null;
  // 只有焦點正好在 selector 本身才算命中：卡牌內部控制（例如手牌的資源／行動鈕）不算命中整張卡牌。
  return { key: base + '#' + [...new Set(same)].indexOf(el), hit: !!target && target === el };
}"""

_NAV_GRAPHS = {}


def focus_dom_toward(pad, page, selector, steps=400):
    """用真正的搖桿方向輸入把焦點移到 selector 本身（卡牌內部控制不算）。

    確定性做法：以實際輸入逐步探索「焦點節點 ×4 方向」的轉移圖（每一步都是真實 frame），
    用已知邊在節點間移動，再對最近的未探索方向推一次，直到目標命中。邊以實際觀察覆寫，
    因此捲動造成的偏移不會讓圖失真；節點用穩定 key（標籤／卡牌／模式）識別。
    不直接設定 .rl-pad-focus、不呼叫產品 action。
    """
    graph = _NAV_GRAPHS.setdefault(id(page), {})
    dirs = ["right", "down", "left", "up"]

    def observe():
        return page.evaluate(FOCUS_KEY_JS, selector)

    cur = observe()
    if cur is None:
        return False
    tried, reset_used = set(), False  # 本次呼叫已推過但沒有移動的 (節點, 方向)；不寫入跨呼叫快取（受捲動位置影響）
    for _ in range(steps):
        if cur["hit"]:
            return True
        # BFS：從 cur 找到最近且有未探索方向的節點
        start = cur["key"]
        prev, queue, goal = {start: None}, [start], None
        while queue:
            node = queue.pop(0)
            if any(d not in graph.get(node, {}) and (node, d) not in tried for d in dirs):
                goal = node
                break
            for d in dirs:
                nxt = graph.get(node, {}).get(d)
                if nxt is not None and nxt not in prev:
                    prev[nxt] = (node, d)
                    queue.append(nxt)
        if goal is None:
            if reset_used:
                return False
            graph.clear()
            tried.clear()
            reset_used = True
            continue
        path, node = [], goal
        while prev[node] is not None:
            node, d = prev[node][0], prev[node][1]
            path.append(d)
        step = path[-1] if path else next(d for d in dirs if d not in graph.get(goal, {}) and (goal, d) not in tried)
        pad.push(step)
        nxt = observe()
        if nxt is None:
            return False
        if nxt["key"] == cur["key"]:
            tried.add((cur["key"], step))
            graph.get(cur["key"], {}).pop(step, None)
        else:
            graph.setdefault(cur["key"], {})[step] = nxt["key"]
        cur = nxt
    return bool(cur and cur["hit"])


def focus_town_toward(pad, page, mframe, town, steps=60):
    """用真正的搖桿方向輸入把地圖焦點移到 town；座標取自 iframe snapshot。"""
    for _ in range(steps):
        cur = page.evaluate("RedlineController.getState().focusTown")
        if cur == town:
            return True
        snap = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
        pos = {t["town"]: (t["x"], t["y"]) for t in snap["targets"]}
        if town not in pos or cur not in pos:
            return False
        dx, dy = pos[town][0] - pos[cur][0], pos[town][1] - pos[cur][1]
        pad.push(("right" if dx > 0 else "left") if abs(dx) > abs(dy) else ("down" if dy > 0 else "up"))
    return page.evaluate("RedlineController.getState().focusTown") == town


def enable_controller(page):
    page.click("#padToggleBtn")
    page.check("#padEnableChk")
    page.wait_for_function("window.RedlineController.getState().status === 'connected'", timeout=5000)
    page.click("#padToggleBtn")


def scenario_desktop_focus_menu(page, pad, base, record):
    """12. 桌面模式 SL 聚焦選單：組織經驗甲（無視距離於己方發展空間建立）→ 大量合法建立目標，依統治者／陣營區域快速聚焦。"""
    setup = post_json(base, "/test/setup-move-confirmation-proof",
                      {"mover_faction": "taiwan_green", "mover_base": "新竹", "mover_town": "臺北", "moves_left": 5})
    hand = post_json(base, "/test/set-hand", {"game_id": setup["game_id"], "player_id": setup["player_id"],
                                              "cards": ["組織經驗甲", "追隨者", "追隨者"], "turn_phase": "action"})
    page.goto(base + setup["url"], wait_until="networkidle")
    page.wait_for_selector("#gameShell", state="visible", timeout=15000)
    page.evaluate("() => window.closeEventReveal && closeEventReveal()")
    page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
    page.evaluate(SPY)
    _NAV_GRAPHS.clear()
    hint = lambda: page.evaluate("document.getElementById('padHint').textContent")
    menu = lambda: page.evaluate(FOCUS_MENU_JS)
    st = lambda: page.evaluate("RedlineController.getState()")
    view = lambda: page.evaluate("document.querySelector('.game-tab.active').dataset.view")
    guard = lambda: page.evaluate(GUARD_JS)
    focus_town = lambda: st()["focusTown"]
    confirm_open = lambda: page.evaluate("document.getElementById('lrConfirmModal')?.style.display === 'flex'")

    def wait(js, arg=None, timeout=3000):
        try:
            page.wait_for_function(js, arg=arg, timeout=timeout, polling=20)
            return True
        except Exception:
            return False

    def request_done(timeout=2500):
        """聚焦選單請求與地圖等待都已結束（開啟、fail closed 或逾時）。"""
        return wait(f"(() => {{ const g = ({GUARD_JS})(); return !g.menuRequest && !g.mapRequest; }})()", timeout=timeout)

    def sl_fails_closed(reason):
        """SL → 送出新的 snapshot 請求 → 請求結束後選單沒開、提示顯示短原因、250ms 執行冷卻沒有開始。"""
        a0, n = guard()["activatedAt"], page.evaluate("(window.__cmdLog || []).length")
        pad.tap("SL")
        done = request_done()
        page.wait_for_timeout(60)
        m, h, a1 = menu(), hint(), guard()["activatedAt"]
        asked = len(page.evaluate(SNAPSHOT_CMDS_JS, n)) == 1
        return done and asked and not m["open"] and reason in h and a1 == a0, {"open": m["open"], "hint": h, "asked": asked, "activatedAt": [a0, a1]}

    pad.neutral()
    pad.tap("A")  # 第一次有效操作只放焦點
    # (a) 地圖從未載入（沒有任何 iframe snapshot）→ fail closed＋短原因，不開選單
    pad.tap("SL")
    page.wait_for_timeout(150)
    m0, h0 = menu(), hint()
    record("desktop_SL_without_map_snapshot_fails_closed_with_short_reason",
           hand.get("success") and not m0["open"] and "地圖尚未載入" in h0 and page.evaluate("__spy.sendAction") == 0, [m0, h0])

    # (a2) 移動 scope：可行動來源與已選來源的合法目的地都不是建立目標 → fail closed（目前沒有可聚焦的地圖目標），不開始執行冷卻
    pad.tap("R")  # 既有區段環 → 戰略地圖（還沒有 pending choice）
    on_move = wait("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=10000) and wait(
        "(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && !!s.focusTown; })()", timeout=10000)
    page.wait_for_timeout(600)
    mframe = next(f for f in page.frames if "leaflet_game_map" in f.url)
    page.evaluate(CMD_LOG_JS)

    def fwait(js, timeout=3000):
        try:
            mframe.wait_for_function(js, timeout=timeout, polling=20)
            return True
        except Exception:
            return False

    move_scope = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
    src = sl_fails_closed("目前沒有可聚焦的地圖目標")
    src_town = focus_town()
    page.wait_for_timeout(1900)  # 前一個提示過期
    pad.tap("A")  # 既有地圖 A：選取焦點來源 → 伺服器合法目的地
    picked_src = fwait("() => selectedTown !== null")
    page.wait_for_timeout(400)
    dest_scope = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
    dst = sl_fails_closed("目前沒有可聚焦的地圖目標")
    pad.tap("B")  # 既有取消選取
    unselected = fwait("() => selectedTown === null")
    record("desktop_SL_on_move_sources_and_destinations_fails_closed_without_cooldown",
           on_move and move_scope["scope"] == "move" and any(t["role"] == "origin" for t in move_scope["targets"]) and src[0]
           and picked_src and dest_scope["selected"] == src_town and any(t["role"] == "move" for t in dest_scope["targets"]) and dst[0]
           and unselected and page.evaluate("__spy.sendAction") == 0, [src[1], dst[1], src_town, dest_scope.get("selected")])
    page.wait_for_timeout(400)
    pad.tap("SR")  # 既有區段環 → 回指揮中心
    wait("document.querySelector('.game-tab.active').dataset.view === 'command'", timeout=5000)
    page.wait_for_timeout(400)

    BUILD = '#hand .card[data-card-zone="hand"][data-card-name="組織經驗甲"]'
    reached_card = focus_dom_toward(pad, page, BUILD)
    pad.tap("Y")  # 手牌 Y＝既有「行動」→ 伺服器 pending choice（無視距離建立）→ 戰略地圖
    on_map = wait("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=20000)
    page.wait_for_function("document.getElementById('strategicMapFrame').contentWindow.lastGameState", timeout=20000)
    wait("(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && !!s.focusTown; })()", timeout=10000)
    page.wait_for_timeout(700)
    legal = page.evaluate("(window.lastGameState.pending_choice?.towns || []).map(t => t.town)")
    expected = expected_focus_groups(legal)
    want_counts = {k: {n: len(v) for n, v in g.items()} for k, g in expected.items()}
    t0 = focus_town()
    hl_focus = mframe.evaluate("supportChoiceHighlight?.focusTown || null")
    mframe.evaluate(INSTALL_RESPONDER_JS)
    # 基準在打出組織經驗甲（既有 play_card 送出一次）之後取：之後選單的任何操作都不得再送出遊戲動作。
    sel0, orgs0, sends0 = mframe.evaluate("selectedTown"), page.evaluate(MOVER_ORGS_JS), page.evaluate("__spy.sendAction")
    map_hint = hint()

    def executing_since(n):
        return [c for c in page.evaluate("window.__cmdLog")[n:] if c["cmd"] in EXECUTING_MAP_CMDS]

    def no_side_effects(n):
        return (page.evaluate("__spy.sendAction") == sends0 and not executing_since(n) and mframe.evaluate("selectedTown") == sel0
                and page.evaluate(MOVER_ORGS_JS) == orgs0)

    def open_menu():
        pad.tap("SL")
        ok = wait(FOCUS_MENU_OPEN_JS, timeout=3000)
        page.wait_for_timeout(300)  # 開啟算一次執行：250ms 內的 A 會被擋
        return ok

    def at_town(t):
        return wait("(t) => { const s = RedlineController.getState(); return s.focusKind === 'map' && s.focusTown === t; }", t)

    # (b) SL 開啟：兩區、只列含合法建立目標的項目、城鎮數與獨立計算一致、確定性排序、焦點在第一個選項；真的開啟才開始執行冷卻
    n0 = page.evaluate("window.__cmdLog.length")
    a_pre = guard()["activatedAt"]
    opened = open_menu()
    m1 = menu()
    a_open = guard()["activatedAt"]
    page.screenshot(path=str(OUT / "11_desktop_focus_menu.png"))
    record("desktop_SL_opens_focus_menu_grouped_by_ruler_and_region_from_legal_build_targets_only",
           reached_card and on_map and opened and len(set(legal)) >= 20 and [s["kind"] for s in m1["sections"]] == ["ruler", "camp"]
           and [s["title"] for s in m1["sections"]] == ["統治者", "陣營區域"] and menu_counts(m1) == want_counts
           and all(g["count"] >= 1 for s in m1["sections"] for g in s["groups"]) and f"可建立組織 {len(set(legal))} 個" in m1["title"]
           and "SL" in map_hint and a_open is not None and (a_pre is None or a_open > a_pre) and no_side_effects(n0),
           [len(legal), m1, want_counts, map_hint, a_pre, a_open])
    record("desktop_focus_menu_order_is_count_then_name_and_focus_starts_on_first_option",
           page.evaluate(FOCUS_MENU_ORDER_OK_JS, m1["sections"]) and m1["focusInMenu"] and m1["focusKey"] == m1["firstKey"], m1)
    pad.tap("B")
    wait(FOCUS_MENU_CLOSED_JS)
    at_town(t0)

    # (c) 開啟後 250ms 內的 A（焦點一落到選項就按）：被執行冷卻擋下，不送選定請求、不移焦點；冷卻過後同一個 A 才選定
    page.wait_for_timeout(400)
    fast = page.evaluate(FAST_A_JS)
    page.wait_for_timeout(300)
    mf, g_fast = menu(), guard()
    picks_fast = page.evaluate(SNAPSHOT_CMDS_JS, fast["sends"]) if fast else ["?"]
    if mf["open"]:
        pad.tap("A")  # 只在選單開著時按（否則 A 會落在地圖城鎮上）
    picked = mf["open"] and wait(FOCUS_MENU_CLOSED_JS) and wait("RedlineController.getState().focusKind === 'map'")
    picks_late = page.evaluate(SNAPSHOT_CMDS_JS, fast["sends"]) if fast else []
    page.wait_for_timeout(300)
    record("desktop_focus_menu_A_within_250ms_of_opening_is_ignored_then_accepted",
           bool(fast) and fast["gap"] < 250 and mf["open"] and mf["focusInMenu"] and mf["focusKey"] == fast["key"] and not picks_fast
           and (g_fast["lastCommand"] or {}).get("cmd") == "focusMenuPick" and (g_fast["lastCommand"] or {}).get("result") == "activation-cooldown"
           and picked and len(picks_late) == 1 and no_side_effects(n0), [fast, mf["open"], g_fast, picks_fast, picks_late])

    # (d) scope lock＋正向對照：每個鍵先在選單開著時按（不得有任何效果），B 關閉並確認焦點回到原處後，
    #     在完全相同的情境再按一次，證明它在選單關閉時確實會執行。
    def lock_probe(key, observe, restore, undo=None):
        page.wait_for_timeout(320)
        before = observe()
        opened_ = open_menu()
        pad.tap(key)
        page.wait_for_timeout(100)
        s = menu()
        during = observe()
        locked = opened_ and s["open"] and s["focusInMenu"] and during == before
        pad.tap("B")
        back = wait(FOCUS_MENU_CLOSED_JS) and restore()
        page.wait_for_timeout(320)  # 開啟時的 250ms 執行冷卻已過
        pad.tap(key)
        page.wait_for_timeout(150)
        after = observe()
        if undo:
            undo()
        return {"key": key, "locked": locked, "executed": back and after != before, "before": before, "during": during, "after": after}

    # (d1) 地圖城鎮焦點：方向鍵（真實情境）
    tA = focus_town()
    page.wait_for_timeout(320)
    d_open = open_menu()
    k_open, n_focus = menu()["focusKey"], len([c for c in page.evaluate("window.__cmdLog") if c["cmd"] == "focus"])
    pad.push("right")
    pad.push("down")
    s_d = menu()
    map_focus_sent = len([c for c in page.evaluate("window.__cmdLog") if c["cmd"] == "focus"]) - n_focus
    pad.tap("B")
    d_back = wait(FOCUS_MENU_CLOSED_JS) and at_town(tA)
    page.wait_for_timeout(200)
    for d in ["right", "down", "left", "up"]:
        pad.push(d)
        if focus_town() != tA:
            break
    dpad = {"key": "dpad", "locked": d_open and s_d["open"] and s_d["focusInMenu"] and s_d["focusKey"] != k_open and map_focus_sent == 0,
            "executed": d_back and focus_town() not in (tA, None), "before": tA, "during": s_d["focusKey"], "after": focus_town()}
    # R／SR：指揮中心（必選地圖目標時其他分頁沒有可聚焦內容，R／SR 只回戰略地圖）→ 真實情境。
    # 選單關閉後焦點不得殘留在隱藏的選項上（沒有可還原的內容 → 不放焦點）。
    CARD = '#hand .card[data-card-zone="hand"][data-card-name="追隨者"]'

    def to_command():
        page.click("button.game-tab[data-view='command']")  # 測試設置：滑鼠切回指揮中心
        ok = wait("document.querySelector('.game-tab.active').dataset.view === 'command'")
        page.wait_for_timeout(300)
        return ok

    def nothing_left_in_menu():
        return wait("(() => !document.querySelector('#lrFocusMenu .rl-pad-focus') && RedlineController.getState().focusKind !== 'dom')()")

    on_command = to_command()
    r = lock_probe("R", view, nothing_left_in_menu, undo=to_command)
    sr = lock_probe("SR", view, nothing_left_in_menu, undo=to_command)
    # 未綁定的鍵（桌面模式 STICK／HOME 不產生任何動作）與 ZR（指揮中心＝no-op）：選單開著時同樣不穿透（地圖層級也不變）
    unbound = page.evaluate("['STICK', 'HOME'].map(b => RedlineControllerCore.logicalAction({ type: 'press', button: b }))")
    obs_all = lambda: [view(), st()["helpOpen"], confirm_open(), mframe.evaluate("map.getZoom()")]
    unbound_probes = []
    for key in ["ZR", "STICK", "HOME"]:
        before = obs_all()
        opened_ = open_menu()
        pad.tap(key)
        s = menu()
        unbound_probes.append([key, opened_ and s["open"] and s["focusInMenu"] and obs_all() == before])
        pad.tap("B")
        unbound_probes[-1].append(wait(FOCUS_MENU_CLOSED_JS) and nothing_left_in_menu())
    # X／Y（手牌資源／行動）：只有焦點在手牌上才會執行，但必選地圖目標時其他分頁沒有內容、遊戲也停用手牌按鈕。
    # 正向對照因此暫時解除 parent 的必選鎖旗標（iframe 的建立目標不變，選單照常開啟）並啟用該張手牌的按鈕
    # （click 在 capture 階段計數並攔下，不送出任何動作）；測試後還原。
    page.evaluate("() => { window.__slChoiceLock = lastSupportChoiceMapHighlightPayload; lastSupportChoiceMapHighlightPayload = null; }")
    page.wait_for_timeout(200)
    pad.push("down")  # 必選鎖解除後指揮中心才有內容：放焦點
    on_card = focus_dom_toward(pad, page, CARD)

    def card_back():
        return wait("(sel) => { const f = document.querySelector('.rl-pad-focus'); return !!f && f === document.querySelector(sel); }", CARD)

    page.evaluate(INSTRUMENT_JS, [{"name": "resource", "selector": CARD + ' .hand-card-action-btn[data-card-mode="resource"]'},
                                  {"name": "action", "selector": CARD + ' .hand-card-action-btn[data-card-mode="action"]'}])
    count = lambda name: (lambda: page.evaluate(PROBE_COUNTS_JS).get(name, 0))
    x = lock_probe("X", count("resource"), card_back)
    y = lock_probe("Y", count("action"), card_back)
    page.evaluate(UNINSTRUMENT_JS)
    page.evaluate("() => { lastSupportChoiceMapHighlightPayload = window.__slChoiceLock; delete window.__slChoiceLock; }")
    # Capture／PLUS（地圖城鎮焦點）：pending choice 期間遊戲停用結束行動與陣營能力 → 暫時啟用（click 一律攔下）
    page.wait_for_timeout(300)
    pad.tap("R")  # 必選地圖目標：R 回戰略地圖
    wait("document.querySelector('.game-tab.active').dataset.view === 'map'")
    wait("(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && !!s.focusTown; })()")
    page.wait_for_timeout(400)
    # ZR（地圖城鎮焦點，真實；必選地圖目標時也會縮放）：選單開著時地圖層級不變，關閉後同一個 ZR 放大一級（或由最大回到最小）
    tZ = focus_town()
    zr = lock_probe("ZR", lambda: mframe.evaluate("map.getZoom()"), lambda: at_town(tZ))
    page.evaluate(INSTRUMENT_JS, [{"name": "advance", "selector": "#advanceStepBtn"},
                                  {"name": "ability", "selector": "#redArmyAbilityBtn", "show": True}])
    tB = focus_town()
    cap = lock_probe("CAPTURE", confirm_open, lambda: at_town(tB),
                     undo=lambda: (pad.tap("B"), wait("document.getElementById('lrConfirmModal')?.style.display !== 'flex'")))
    tC = focus_town()
    plus = lock_probe("PLUS", count("ability"), lambda: at_town(tC))  # 最後做：PLUS 執行後有 1.5 秒處理中鎖
    page.evaluate(UNINSTRUMENT_JS)
    real = [dpad, r, sr, zr]
    instrumented = [x, y, cap, plus]
    record("desktop_focus_menu_scope_lock_real_contexts_dpad_R_SR_ZR_blocked_open_and_executed_closed",
           on_command and all(p["locked"] and p["executed"] for p in real) and no_side_effects(n0), real)
    record("desktop_focus_menu_scope_lock_instrumented_X_Y_capture_plus_blocked_open_and_executed_closed",
           on_card and all(p["locked"] and p["executed"] for p in instrumented) and no_side_effects(n0), [on_card, instrumented])
    record("desktop_focus_menu_scope_lock_unbound_STICK_HOME_and_off_map_ZR_never_pass_through",
           unbound == [None, None] and all(ok and closed for _, ok, closed in unbound_probes) and no_side_effects(n0), [unbound, unbound_probes])

    # (e) SL 再按／B／滑鼠 × 取消：從非預設焦點開啟，關閉後焦點精確回到該城鎮（不是重新放預設）；不執行任何操作
    page.wait_for_timeout(400)
    avoid = {t0, hl_focus, None}
    for d in ["right", "down", "left", "up", "right", "down"]:
        if focus_town() not in avoid:
            break
        pad.push(d)
    t_nd = focus_town()
    restores = {}
    for how in ["SL", "B", "mouse"]:
        open_menu()
        if how == "mouse":
            page.click("#lrFocusMenuClose")
        else:
            pad.tap(how)
        restores[how] = wait(FOCUS_MENU_CLOSED_JS) and at_town(t_nd)
        page.wait_for_timeout(150)
    record("desktop_focus_menu_SL_again_B_and_mouse_close_restore_the_exact_non_default_focus",
           t_nd not in avoid and all(restores.values()) and st()["focusKind"] == "map" and no_side_effects(n0), [t_nd, sorted(a for a in avoid if a), restores])

    # (f) A 選取不含目前焦點的統治者分組 → 關閉，焦點移到該分組清單順序第一個合法城鎮；不選取、不建立；成功移焦點才開始執行冷卻
    rulers = m1["sections"][0]["groups"]
    g1 = next((g for g in rulers[1:] if t_nd not in expected["ruler"][g["name"]] and g["count"] >= 2), None) \
        or next((g for g in rulers if t_nd not in expected["ruler"][g["name"]]), None)
    want1 = page.evaluate(FIRST_IN_LIST_ORDER_JS, sorted(expected["ruler"][g1["name"]])) if g1 else None
    open_menu()
    reached1 = bool(g1) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g1["key"]}"]')
    page.wait_for_timeout(320)
    a_pick0 = guard()["activatedAt"]
    pad.tap("A")
    moved = wait(FOCUS_MENU_CLOSED_JS) and at_town(want1)
    a_pick1 = guard()["activatedAt"]
    page.wait_for_timeout(300)
    labels1 = mframe.evaluate("[...document.querySelectorAll('.pad-focus-label')].map(l => l.textContent)")
    page.screenshot(path=str(OUT / "12_desktop_focus_menu_pick.png"))
    record("desktop_focus_menu_A_moves_focus_to_first_legal_town_of_group_without_action",
           reached1 and moved and st()["focusKind"] == "map" and view() == "map" and labels1 == [want1]
           and a_pick1 is not None and a_pick0 is not None and a_pick1 > a_pick0 and no_side_effects(n0),
           [g1, want1, st()["focusTown"], labels1, executing_since(n0), a_pick0, a_pick1])

    # (g) 選定分組包含目前焦點 → 焦點保留（不跳到該分組第一個）
    t1 = focus_town()
    firsts = {g["key"]: page.evaluate(FIRST_IN_LIST_ORDER_JS, sorted(expected[g["key"].split(":", 1)[0]][g["name"]]))
              for s in m1["sections"] for g in s["groups"] if t1 in expected[s["kind"]][g["name"]]}
    g2key = next((k for k, first in firsts.items() if first != t1), None)
    open_menu()
    reached2 = bool(g2key) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g2key}"]')
    page.wait_for_timeout(320)
    pad.tap("A")
    kept = wait(FOCUS_MENU_CLOSED_JS) and at_town(t1)
    page.wait_for_timeout(300)
    record("desktop_focus_menu_keeps_current_focus_when_it_belongs_to_the_chosen_group",
           reached2 and kept and st()["focusTown"] == t1 and firsts.get(g2key) != t1 and no_side_effects(n0), [t1, g2key, firsts])

    # (h) 從指揮中心（非地圖分頁）開選單並選定 → 經既有分頁切到戰略地圖，焦點落在該分組第一個合法城鎮；不執行
    page.click("button.game-tab[data-view='command']")  # 測試設置：滑鼠切到指揮中心
    wait("document.querySelector('.game-tab.active').dataset.view === 'command'")
    page.wait_for_timeout(400)
    g4 = next((g for g in rulers[1:] if t1 not in expected["ruler"][g["name"]]), None)
    want4 = page.evaluate(FIRST_IN_LIST_ORDER_JS, sorted(expected["ruler"][g4["name"]])) if g4 else None
    from_cmd = open_menu()
    reached4 = bool(g4) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g4["key"]}"]')
    page.wait_for_timeout(320)
    n4 = page.evaluate("window.__cmdLog.length")
    pad.tap("A")
    switched = (wait(FOCUS_MENU_CLOSED_JS) and wait("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=5000)
                and at_town(want4))
    page.wait_for_timeout(300)
    record("desktop_focus_menu_from_command_view_switches_to_map_via_existing_tab_and_focuses_town",
           from_cmd and reached4 and switched and st()["focusKind"] == "map" and not executing_since(n4) and no_side_effects(n0),
           [g4, want4, st()["focusTown"], view(), executing_since(n4)])

    # (i) 候選在選定瞬間消失 → fail closed：選單刷新、不移焦點到消失的城鎮、不執行
    t1 = focus_town()
    g3 = next((g for g in reversed(rulers) if t1 not in expected["ruler"][g["name"]]), None)
    gone = sorted(expected["ruler"][g3["name"]]) if g3 else []
    open_menu()
    reached3 = bool(g3) and focus_dom_toward(pad, page, f'#lrFocusMenu .lr-focus-option[data-key="{g3["key"]}"]')
    page.wait_for_timeout(320)
    n3 = page.evaluate("window.__cmdLog.length")
    left = mframe.evaluate(VANISH_JS, gone)
    pad.tap("A")
    refreshed = wait("(k) => !document.querySelector(`#lrFocusMenu .lr-focus-option[data-key=\"${k}\"]`)", g3["key"] if g3 else "")
    page.wait_for_timeout(200)
    m3, h3 = menu(), hint()
    focused_gone = [c for c in page.evaluate("window.__cmdLog")[n3:] if c["cmd"] == "focus" and c["town"] in gone]
    mframe.evaluate("() => applySupportChoiceHighlight(window.__hlBackup)")
    back = wait("(k) => !!document.querySelector(`#lrFocusMenu .lr-focus-option[data-key=\"${k}\"]`)", g3["key"] if g3 else "")
    pad.tap("B")
    restored3 = wait(FOCUS_MENU_CLOSED_JS) and at_town(t1)
    record("desktop_focus_menu_candidates_vanishing_at_selection_fail_closed_and_menu_refreshes",
           reached3 and left == len(set(legal)) - len(gone) and refreshed and m3["open"] and m3["focusInMenu"]
           and "此範圍已沒有合法目標" in h3 and not focused_gone and back and restored3 and no_side_effects(n0),
           [g3, left, m3, h3, focused_gone, back, restored3])

    # (j) 協定整合：parent 送往 iframe 的 snapshot 請求被攔下，回覆由 iframe 偽造（來源驗證照常）；
    #     ok:false、錯的 req、不合 schema、snapshot 先於 ok:true、逾時邊界都必須 fail closed，且 fail closed 不開始執行冷卻。
    MALFORMED = {"type": "redline-controller-map-snapshot", "v": 1, "seq": 999999, "scope": "choice", "targets": "bad", "buttons": []}

    def protocol_case(steps, expect_open, text, total_ms=1500):
        page.wait_for_timeout(1900)  # 前一個提示過期
        page.evaluate(HOLD_MAP_CMDS_JS)
        a0, f0 = guard()["activatedAt"], focus_town()
        pad.tap("SL")
        held = page.evaluate(RESPOND_TO_HELD_JS, steps)
        shown = wait("(t) => document.getElementById('padHint').textContent.includes(t)", text, timeout=total_ms) if text else True
        if held:
            wait(f"(ms) => performance.now() - (window.__slHeld || []).filter(c => c.cmd === 'snapshot').pop().at > ms", total_ms, timeout=total_ms + 500)
        out = {"held": held, "open": menu()["open"], "text": shown, "hint": hint(), "arrivals": page.evaluate("window.__slArrivals || []"),
               "activatedAt": [a0, guard()["activatedAt"]], "menuRequest": guard()["menuRequest"]}
        page.evaluate(RELEASE_MAP_CMDS_JS)
        if out["open"]:
            pad.tap("B")
            wait(FOCUS_MENU_CLOSED_JS)
        mframe.evaluate("() => refreshDirectBuildUi()")  # 權威推送：讓 parent 的地圖 snapshot 與焦點回到正常
        page.wait_for_timeout(300)
        at_town(f0)
        out["ok"] = (bool(held) and out["open"] == expect_open and shown and out["menuRequest"] is None
                     and (out["activatedAt"][1] != out["activatedAt"][0] if expect_open else out["activatedAt"][1] == out["activatedAt"][0]))
        return out

    cases = {
        "ok_false": protocol_case([{"kind": "result", "ok": False, "at": 0}, {"kind": "snapshot", "at": 5}], False, "此操作目前不可用"),
        "wrong_req": protocol_case([{"kind": "result", "ok": True, "at": 0}, {"kind": "snapshot", "reqOffset": 7, "at": 5}], False, "地圖沒有回應"),
        "malformed": protocol_case([{"kind": "result", "ok": True, "at": 0}, {"kind": "raw", "msg": MALFORMED, "at": 5}], False, "地圖資料不足"),
        "snapshot_before_ack": protocol_case([{"kind": "snapshot", "at": 0}, {"kind": "result", "ok": True, "at": 5}], False, "地圖沒有回應"),
        "in_time_850ms": protocol_case([{"kind": "result", "ok": True, "at": 850}, {"kind": "snapshot", "at": 860}], True, None),
        "ack_900ms_snapshot_1010ms": protocol_case([{"kind": "result", "ok": True, "at": 900}, {"kind": "snapshot", "at": 1010}], False, "地圖沒有回應"),
        "both_late_1010ms": protocol_case([{"kind": "result", "ok": True, "at": 1010}, {"kind": "snapshot", "at": 1015}], False, "地圖沒有回應"),
    }
    late_snap = [a["ms"] for a in cases["ack_900ms_snapshot_1010ms"]["arrivals"] if a["type"] == "snapshot"]
    late_ack = [a["ms"] for a in cases["ack_900ms_snapshot_1010ms"]["arrivals"] if a["type"] == "result"]
    timely = [a["ms"] for a in cases["in_time_850ms"]["arrivals"]]
    record("desktop_focus_menu_rejects_ok_false_wrong_req_malformed_and_snapshot_before_ack_without_cooldown",
           all(cases[k]["ok"] for k in ("ok_false", "wrong_req", "malformed", "snapshot_before_ack")) and no_side_effects(n0),
           {k: cases[k] for k in ("ok_false", "wrong_req", "malformed", "snapshot_before_ack")})
    record("desktop_focus_menu_timeout_boundary_snapshot_at_or_after_1000ms_never_opens",
           all(cases[k]["ok"] for k in ("in_time_850ms", "ack_900ms_snapshot_1010ms", "both_late_1010ms"))
           and timely and max(timely) < 1000 and late_ack and late_ack[0] < 1000 and late_snap and late_snap[0] >= 1000 and no_side_effects(n0),
           {k: cases[k] for k in ("in_time_850ms", "ack_900ms_snapshot_1010ms", "both_late_1010ms")})

    # (k) iframe 完全沒有回應（stale）：期間到達的一般推送（沒有對應 req）不得開選單；1 秒逾時 fail closed
    page.wait_for_timeout(1900)
    t1 = focus_town()
    page.evaluate(DROP_TO_MAP_JS)
    pad.tap("SL")
    mframe.evaluate("() => refreshDirectBuildUi()")  # iframe 照常推送一份不帶 req 的 snapshot
    page.wait_for_timeout(300)
    mid = menu()["open"]
    expired = wait("RedlineController.getState().shortcuts?.mapRequest === null", timeout=2500)
    page.wait_for_timeout(150)
    h4, end = hint(), menu()["open"]
    page.evaluate(RESTORE_TO_MAP_JS)
    record("desktop_focus_menu_stale_snapshot_request_fails_closed_even_when_routine_snapshots_arrive",
           not mid and expired and not end and "地圖沒有回應" in h4 and st()["focusTown"] == t1 and no_side_effects(n0), [mid, expired, end, h4])

    # (l) canonical 分組資料不合法（任一合法目標缺 camp、ruler 為空、camp 含非字串）→ iframe 不宣告 groupMeta → fail closed
    meta_cases = []
    for field, value in [("camp", None), ("ruler", []), ("camp", ["臺灣", 3])]:
        page.wait_for_timeout(1900)
        mframe.evaluate(CORRUPT_GROUP_JS, [legal[0], field, value])
        meta_snap = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
        ok, detail = sl_fails_closed("地圖資料不足")
        mframe.evaluate(RESTORE_GROUP_JS)
        meta_cases.append([field, value, ok and "groupMeta" not in meta_snap and all("ruler" not in t for t in meta_snap["targets"]), detail])
    record("desktop_focus_menu_invalid_canonical_group_data_on_any_target_fails_closed",
           all(c[2] for c in meta_cases) and no_side_effects(n0), meta_cases)

    # (m) 沒有合法目標（篩選把城鎮全部藏起來）→ fail closed＋短原因
    page.wait_for_timeout(1900)
    mframe.evaluate("() => { document.getElementById('searchBox').value = '不存在的城鎮'; renderMap(); }")
    none = sl_fails_closed("目前沒有可聚焦的地圖目標")
    mframe.evaluate("() => { document.getElementById('searchBox').value = ''; renderMap(); refreshDirectBuildUi(); }")
    record("desktop_focus_menu_no_legal_targets_fails_closed_with_reason", none[0], none[1])

    # (n) 選定的城鎮仍走既有地圖操作：選單開著時 Y 不穿透（不送 act）；B 關閉後同一個 Y → iframe act（unique req、directBuildBtn）
    #     → 對上 req 的 ok:true → 伺服器建立
    page.wait_for_timeout(1900)
    t1 = focus_town()
    na = page.evaluate("window.__cmdLog.length")
    y_open = open_menu()
    pad.tap("Y")
    page.wait_for_timeout(300)
    y_blocked = menu()["open"] and not [c for c in page.evaluate("window.__cmdLog")[na:] if c["cmd"] == "act"]
    pad.tap("B")
    y_back = wait(FOCUS_MENU_CLOSED_JS) and at_town(t1)
    page.wait_for_timeout(320)
    at_t1 = page.evaluate("(t) => (document.getElementById('strategicMapFrame').contentWindow.lastGameState.map.towns[t] || []).filter(e => e.player === 'mover').length", t1)
    page.evaluate("""() => { window.__slResults = []; window.addEventListener('message', e => {
      if (e.data && e.data.type === 'redline-controller-result' && e.data.cmd === 'act') window.__slResults.push(e.data); }); }""")
    pad.tap("Y")
    built = wait(f"(document.getElementById('strategicMapFrame').contentWindow.lastGameState.map.towns[{json.dumps(t1)}] || []).filter(e => e.player === 'mover').length > {at_t1}", timeout=8000)
    acts = [c for c in page.evaluate("window.__cmdLog")[na:] if c["cmd"] == "act"]
    results = page.evaluate("window.__slResults")
    ack = (st().get("shortcuts") or {}).get("lastMapAck") or {}
    record("desktop_SL_focused_town_Y_is_locked_while_open_then_builds_via_existing_req_ack_path",
           y_open and y_blocked and y_back and built and len(acts) == 1 and acts[0]["town"] == t1 and acts[0]["id"] == "directBuildBtn"
           and isinstance(acts[0]["req"], int) and len(results) == 1 and results[0]["req"] == acts[0]["req"] and results[0]["ok"] is True
           and ack.get("outcome") == "success" and ack.get("req") == acts[0]["req"], [t1, y_blocked, acts, results, ack])


def scenario_desktop_zr_zoom(page, pad, base, record):
    """13. 桌面模式 ZR：戰略地圖每按一次放大一級，最大後回到最小；只在地圖 scope，iframe `zoom`＋唯一 req，對上的 ok:true 才算成功。"""
    setup = post_json(base, "/test/setup-move-confirmation-proof",
                      {"mover_faction": "taiwan_green", "mover_base": "新竹", "mover_town": "臺北", "moves_left": 5})
    page.goto(base + setup["url"], wait_until="networkidle")
    page.wait_for_selector("#gameShell", state="visible", timeout=15000)
    page.evaluate("() => window.closeEventReveal && closeEventReveal()")
    if not page.evaluate("RedlineController.getState().enabled"):
        enable_controller(page)
    page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
    page.evaluate(SPY)
    _NAV_GRAPHS.clear()
    st = lambda: page.evaluate(ZR_STATE_JS)
    QUIET = ["focusKind", "focusTown", "focusSig", "helpOpen", "view", "activatedAt", "processing", "mapRequest", "lastMapAck",
             "lastCommand", "sends", "stateHash"]
    quiet = lambda s: {k: s[k] for k in QUIET}

    def wait(js, arg=None, timeout=3000):
        try:
            page.wait_for_function(js, arg=arg, timeout=timeout, polling=20)
            return True
        except Exception:
            return False

    # (a) 非地圖：第一下 ZR 不放焦點；放好焦點後 ZR 也完全 no-op（不切說明、不送任何地圖指令、不記錄任何指令）
    pad.neutral()
    s0 = st()
    pad.tap("ZR")
    s1 = st()
    record("desktop_ZR_first_input_off_map_is_a_full_noop",
           s0["view"] == "command" and not s1["padActive"] and s1["focusKind"] is None and quiet(s1) == quiet(s0)
           and page.evaluate("!document.querySelector('.rl-pad-focus')"), [s0, s1])
    pad.tap("A")  # 第一次有效操作只放焦點
    page.wait_for_timeout(200)
    b0, k0 = st(), page.evaluate(FOCUS_KEY_JS, None)
    pad.tap("ZR")
    page.wait_for_timeout(150)
    b1, k1 = st(), page.evaluate(FOCUS_KEY_JS, None)
    record("desktop_ZR_on_command_page_is_a_full_noop", b0["padActive"] and b0["focusKind"] == "dom" and quiet(b1) == quiet(b0) and k1 == k0,
           [b0, b1, k0, k1])

    # (b) 戰略地圖：範圍來自 Leaflet min／max 與循環常數
    pad.tap("R")
    on_map = wait("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=10000)
    page.wait_for_function("document.getElementById('strategicMapFrame').contentWindow.lastGameState", timeout=20000)
    on_map = on_map and wait("(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && !!s.focusTown; })()", timeout=10000)
    page.wait_for_timeout(800)
    mframe = next(f for f in page.frames if "leaflet_game_map" in f.url)
    view = lambda: mframe.evaluate(ZR_VIEW_JS)
    page.evaluate(CMD_LOG_JS)
    page.evaluate(ZR_RESULTS_JS)
    results = lambda: page.evaluate("window.__zrResults")
    sent = lambda: page.evaluate(ZR_SENT_JS)
    v_start = view()
    cycle = page.evaluate("RedlineControllerCore.MAP_ZOOM_CYCLE")
    hint = st()["hint"]
    record("desktop_ZR_cycle_range_is_leaflet_min_max_intersected_with_the_cycle_constant",
           on_map and cycle == {"min": ZR_CYCLE[0], "max": ZR_CYCLE[1]} and v_start["minZoom"] == 0 and v_start["maxZoom"] is None
           and "ZR 放大地圖（循環）" in hint, [cycle, v_start, hint])

    def zr_once(timeout=2000):
        n = len(results())
        pad.tap("ZR")
        return wait(f"window.__zrResults.length > {n}", timeout=timeout)

    # (c) 完整循環：從最小層級連按，min → … → max → min；每一下只前進一級、中心與焦點／選取／遊戲狀態都不變
    mframe.evaluate(ZR_SET_ZOOM_JS, ZR_CYCLE[0])  # 測試設置：從循環最小層級開始
    page.wait_for_timeout(300)
    base_v, base_s = view(), st()
    n_sent, n_res = len(sent()), len(results())
    steps = []
    for _ in range(ZR_CYCLE[1] - ZR_CYCLE[0] + 1):
        before = st()
        got = zr_once()
        after_v, after_s = view(), st()
        steps.append({"got": got, "zoom": after_v["zoom"], "center": same_center(base_v, after_v), "ack": after_s["lastMapAck"],
                      "a0": before["activatedAt"], "a1": after_s["activatedAt"], "processing": after_s["processing"],
                      "pending": after_s["mapRequest"], "focus": after_s["focusTown"], "labels": after_v["labels"],
                      "selected": after_v["selected"], "sends": after_s["sends"], "hash": after_s["stateHash"]})
    reqs, res = sent()[n_sent:], results()[n_res:]
    expected = list(range(ZR_CYCLE[0] + 1, ZR_CYCLE[1] + 1)) + [ZR_CYCLE[0]]
    page.screenshot(path=str(OUT / "13_desktop_zr_zoom_cycle.png"))
    record("desktop_ZR_cycles_min_to_max_then_back_to_min_one_level_per_press",
           base_v["zoom"] == ZR_CYCLE[0] and [s["zoom"] for s in steps] == expected and all(s["got"] for s in steps)
           and len(reqs) == len(expected) and len(set(reqs)) == len(reqs) and reqs == sorted(reqs) and all(isinstance(r, int) for r in reqs)
           and [r["req"] for r in res] == reqs and all(r["ok"] is True for r in res), [[s["zoom"] for s in steps], reqs, res])
    record("desktop_ZR_keeps_center_focus_town_selection_and_game_state",
           all(s["center"] and s["focus"] == base_s["focusTown"] and s["labels"] == base_v["labels"] and s["selected"] is None
               and s["sends"] == base_s["sends"] and s["hash"] == base_s["stateHash"] for s in steps)
           and base_s["focusKind"] == "map" and len(base_v["labels"]) == 1, [base_s, base_v, steps[:2]])
    record("desktop_ZR_matching_ok_true_ack_records_success_and_cooldown_but_no_processing_lock",
           all((s["ack"] or {}).get("outcome") == "success" and (s["ack"] or {}).get("req") == reqs[i] and s["ack"].get("lock") is False
               and s["a1"] is not None and s["a1"] != s["a0"] and not s["processing"] and s["pending"] is None for i, s in enumerate(steps)),
           steps)

    # (d) 邊界：最小 → 下一級、一般層級 → 下一級、最大 → 最小；滑鼠縮放到循環之外 → 最小
    levels = []
    for z in [ZR_CYCLE[0], 6, ZR_CYCLE[1], 13]:
        mframe.evaluate(ZR_SET_ZOOM_JS, z)
        page.wait_for_timeout(150)
        v0 = view()
        zr_once()
        v1 = view()
        levels.append([v0["zoom"], v1["zoom"], zr_next(v0), same_center(v0, v1)])
    record("desktop_ZR_min_middle_max_and_out_of_cycle_levels",
           [lv[:2] for lv in levels] == [[2, 3], [6, 7], [10, 2], [13, 2]] and all(lv[1] == lv[2] and lv[3] for lv in levels), levels)
    # (e) 地圖若設了更窄的 Leaflet min／max，循環跟著 Leaflet（測試設置後還原）
    mframe.evaluate("() => { map.setMinZoom(3); map.setMaxZoom(6); }")
    mframe.evaluate(ZR_SET_ZOOM_JS, 6)
    page.wait_for_timeout(150)
    tight = []
    for _ in range(2):
        zr_once()
        tight.append(view()["zoom"])
    mframe.evaluate("() => { map.setMinZoom(undefined); map.setMaxZoom(undefined); }")
    record("desktop_ZR_follows_tighter_leaflet_min_max", tight == [3, 4] and view()["maxZoom"] is None, tight)

    # (e2) 第一下就執行：停用再啟用（padActive=false、焦點清掉）後，戰略地圖上的第一下 ZR 直接放大一級，不放焦點、不改 padActive
    page.evaluate("() => RedlineController.setEnabled(false)")
    page.evaluate("() => RedlineController.setEnabled(true)")
    wait("RedlineController.getState().status === 'connected'", timeout=8000)
    pad.neutral()
    page.wait_for_timeout(300)
    f0, fv0 = st(), view()
    first_ok = zr_once()
    f1, fv1 = st(), view()
    record("desktop_ZR_first_press_on_the_map_zooms_immediately_without_placing_focus",
           not f0["padActive"] and f0["focusKind"] is None and f0["scope"] == "map" and first_ok and fv1["zoom"] == zr_next(fv0)
           and same_center(fv0, fv1) and not f1["padActive"] and f1["focusKind"] is None and f1["focusTown"] is None
           and fv1["labels"] == fv0["labels"] == [] and page.evaluate("!document.querySelector('.rl-pad-focus')")
           and (f1["lastMapAck"] or {}).get("outcome") == "success", [f0, f1, fv0, fv1])
    pad.tap("A")  # 之後的流程需要地圖焦點：第一下 A 只放焦點
    wait("(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && !!s.focusTown; })()", timeout=8000)

    # (f) 選取來源／預備移動時縮放：選取、合法目的地、預備移動、焦點城鎮都不變（之後 B 走既有取消）
    mframe.evaluate(ZR_SET_ZOOM_JS, 6)
    page.wait_for_timeout(300)
    snap = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
    origins = [t["town"] for t in snap["targets"] if t["role"] == "origin"]
    origin = mframe.evaluate("(names) => names.find(n => { const o = movementOptionsForTown(n); return o.road.length + o.rail.length > 0; })", origins)
    reached = bool(origin) and focus_town_toward(pad, page, mframe, origin)

    def fwait(js, arg=None, timeout=3000):
        try:
            mframe.wait_for_function(js, arg=arg, timeout=timeout, polling=20)
            return True
        except Exception:
            return False

    pad.tap("A")
    picked = fwait("(t) => selectedTown === t", origin)
    page.wait_for_timeout(500)  # 既有選取的 fitBounds 動畫結束
    v_sel, s_sel = view(), st()
    zr_once()
    v_sel2, s_sel2 = view(), st()
    dest = next((t["town"] for t in mframe.evaluate("window.__redlineControllerAdapter.snapshot()")["targets"] if t["role"] == "move"), None)
    armed = bool(dest) and focus_town_toward(pad, page, mframe, dest)
    pad.tap("A")
    fwait("() => !!pendingMoveTarget")
    page.wait_for_timeout(400)
    v_arm, s_arm = view(), st()
    zr_once()
    v_arm2, s_arm2 = view(), st()
    pad.tap("B")
    cancelled = fwait("() => selectedTown === null")
    record("desktop_ZR_keeps_selected_origin_legal_moves_pending_move_and_focus",
           reached and picked and v_sel2["zoom"] == zr_next(v_sel) and same_center(v_sel, v_sel2)
           and [v_sel2[k] for k in ("selected", "moves", "pending", "labels")] == [v_sel[k] for k in ("selected", "moves", "pending", "labels")]
           and s_sel2["focusTown"] == s_sel["focusTown"] and armed and v_arm["pending"] is not None
           and v_arm2["zoom"] == zr_next(v_arm) and same_center(v_arm, v_arm2)
           and [v_arm2[k] for k in ("selected", "moves", "pending", "labels")] == [v_arm[k] for k in ("selected", "moves", "pending", "labels")]
           and s_arm2["focusTown"] == s_arm["focusTown"] == dest and s_arm2["sends"] == s_sel["sends"] and cancelled,
           [origin, dest, v_sel, v_sel2, v_arm, v_arm2])

    # (g) 送出到確認之間什麼都不記錄；等待中再按 ZR 不重送；對上的 ok:true 到了才記錄成功與冷卻
    page.wait_for_timeout(1900)  # 前一個提示過期
    page.evaluate(ZR_HOLD_JS)
    p0, pv0 = st(), view()
    pad.tap("ZR")
    held1, p1, pv1 = page.evaluate("window.__zrHeld.length"), st(), view()
    pad.tap("ZR")
    held2, p2 = page.evaluate("window.__zrHeld.length"), st()
    req = page.evaluate(ZR_DELIVER_JS, 0)
    acked = wait(f"window.__zrResults.some(r => r.req === {req})")
    p3, pv3 = st(), view()
    record("desktop_ZR_records_nothing_before_the_matching_ack_and_never_sends_twice_while_pending",
           held1 == 1 and held2 == 1 and (p1["mapRequest"] or {}).get("req") == req and p1["mapRequest"]["cmd"] == "zoom"
           and p1["activatedAt"] == p0["activatedAt"] and p1["lastMapAck"] == p0["lastMapAck"] and pv1["zoom"] == pv0["zoom"]
           and (p2["lastCommand"] or {}).get("result") == "map-pending" and acked and (p3["lastMapAck"] or {}).get("req") == req
           and p3["lastMapAck"]["outcome"] == "success" and p3["activatedAt"] != p0["activatedAt"] and pv3["zoom"] == zr_next(pv0),
           [held1, held2, p1, p2, p3, pv0["zoom"], pv3["zoom"]])

    # (h) 協定 fail closed（指令攔下不送達、回覆由 iframe 偽造）：ok:false、缺 req、錯的 req、不合 schema、逾時、逾時後才到的回覆
    def forged(reply, expect, text, late=False):
        page.wait_for_timeout(1900)
        a, v0 = st(), view()
        n = page.evaluate("window.__zrHeld.length")
        pad.tap("ZR")
        held = page.evaluate("window.__zrHeld")[n:]
        r = held[0]["req"] if held else None
        if reply is not None and not late and r is not None:
            mframe.evaluate(ZR_FORGE_JS, {k: (r + v if k == "req" else v) for k, v in reply.items()})
        done = wait("RedlineController.getState().shortcuts?.mapRequest === null", timeout=2500)
        page.wait_for_timeout(60)
        b = st()
        if late:
            mframe.evaluate(ZR_FORGE_JS, {"req": r, "ok": True})
            wait(f"window.__zrResults.some(x => x.req === {r if r else -1} && x.ok === true)")
            page.wait_for_timeout(60)
        c, v1 = st(), view()
        ok = (len(held) == 1 and done and (b["lastMapAck"] or {}).get("req") == r and b["lastMapAck"]["outcome"] == expect
              and c["lastMapAck"] == b["lastMapAck"] and c["activatedAt"] == a["activatedAt"] and not c["processing"]
              and v1["zoom"] == v0["zoom"] and text in b["hint"])
        return {"ok": ok, "req": r, "ack": c["lastMapAck"], "hint": b["hint"], "zoom": [v0["zoom"], v1["zoom"]], "a": [a["activatedAt"], c["activatedAt"]]}

    cases = {
        "ok_false": forged({"req": 0, "ok": False, "reason": "test-refused"}, "failed", "地圖目前無法縮放"),
        "missing_req": forged({"ok": True}, "timeout", "地圖沒有回應"),
        "wrong_req": forged({"req": 1000, "ok": True}, "timeout", "地圖沒有回應"),
        "malformed": forged({"req": 0, "ok": "yes"}, "timeout", "地圖沒有回應"),
        "timeout": forged(None, "timeout", "地圖沒有回應"),
        "late_after_timeout": forged({}, "timeout", "地圖沒有回應", late=True),
    }
    page.evaluate(ZR_RELEASE_JS)
    record("desktop_ZR_fails_closed_on_ok_false_missing_wrong_malformed_timeout_and_late_ack",
           all(c["ok"] for c in cases.values()), cases)
    # 重複的確認：真實成功後同一個 req 再來一次 ok:true → stale，什麼都不再記錄
    page.wait_for_timeout(400)
    zr_once()
    d0, dv0 = st(), view()
    mframe.evaluate(ZR_FORGE_JS, {"req": d0["lastMapAck"]["req"], "ok": True})
    wait(f"window.__zrResults.filter(r => r.req === {d0['lastMapAck']['req']}).length >= 2")
    page.wait_for_timeout(60)
    d1, dv1 = st(), view()
    record("desktop_ZR_duplicate_ack_after_success_is_ignored",
           d0["lastMapAck"]["outcome"] == "success" and d1["lastMapAck"] == d0["lastMapAck"] and d1["activatedAt"] == d0["activatedAt"]
           and dv1["zoom"] == dv0["zoom"], [d0, d1])
    # iframe 端：缺 req 的 zoom 指令與不是 parent 的來源一律不執行、不回覆
    page.wait_for_timeout(300)
    i0, n0 = view(), len(results())
    page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.postMessage({ type: 'redline-controller-command', v: 1, cmd: 'zoom' }, location.origin)")
    # 自己送給自己：用 iframe 原本的原生 postMessage（CMD_LOG_JS 存在 __cmdLogOrig）；它的包裝函式屬於 parent realm，
    # 經由包裝函式送出時 source 會變成 parent，就不是「非 parent 來源」了。
    mframe.evaluate("() => (window.__cmdLogOrig || window.postMessage).call(window, { type: 'redline-controller-command', v: 1, cmd: 'zoom', req: 990001 }, location.origin)")
    page.wait_for_timeout(400)
    record("desktop_iframe_rejects_zoom_without_req_or_from_a_non_parent_source",
           view()["zoom"] == i0["zoom"] and len(results()) == n0, [i0["zoom"], view()["zoom"], results()[n0:]])

    # (i) 情境 fail closed：modal、iframe 隱藏或不在、等待中離開地圖／停用、停用、斷線（error／重連中）、stale、重連時按住 ZR
    def silent(label, act, undo=None):
        page.wait_for_timeout(300)
        a, v0, n = st(), view(), len(sent())
        act()
        page.wait_for_timeout(250)
        b, v1 = st(), view()
        if undo:
            undo()
        return {"label": label, "ok": len(sent()) == n and v1["zoom"] == v0["zoom"] and b["activatedAt"] == a["activatedAt"]
                and b["lastMapAck"] == a["lastMapAck"], "zoom": [v0["zoom"], v1["zoom"]], "sent": len(sent()) - n}

    ctx_cases = []
    pad.tap("CAPTURE")  # 既有結束行動 → 危險確認 modal（預設返回）
    modal_open = wait("document.getElementById('lrConfirmModal')?.style.display === 'flex'")
    ctx_cases.append(silent("confirm_modal", lambda: pad.tap("ZR")))
    still_open = page.evaluate("document.getElementById('lrConfirmModal')?.style.display === 'flex' && document.querySelector('.rl-pad-focus')?.id === 'lrConfirmCancelBtn'")
    pad.tap("B")
    wait("document.getElementById('lrConfirmModal')?.style.display !== 'flex'")
    ctx_cases.append(silent("hidden_iframe", lambda: (page.evaluate("document.getElementById('strategicMapFrame').style.display = 'none'"),
                                                      page.wait_for_timeout(150), pad.tap("ZR")),
                            lambda: page.evaluate("document.getElementById('strategicMapFrame').style.display = ''")))
    ctx_cases.append(silent("detached_iframe", lambda: (page.evaluate("document.getElementById('strategicMapFrame').id = 'strategicMapFrameDetached'"),
                                                        pad.tap("ZR")),
                            lambda: page.evaluate("document.getElementById('strategicMapFrameDetached').id = 'strategicMapFrame'")))
    page.wait_for_timeout(400)
    # iframe 端：容器不可見時直接收到 zoom → ok:false（map-hidden），不縮放
    page.evaluate("document.getElementById('strategicMapFrame').style.display = 'none'")
    h0, hn = view(), len(results())
    page.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.postMessage({ type: 'redline-controller-command', v: 1, cmd: 'zoom', req: 990002 }, location.origin)")
    hidden_reply = wait(f"window.__zrResults.length > {hn}")
    hidden_res = results()[hn:]
    page.evaluate("document.getElementById('strategicMapFrame').style.display = ''")
    page.wait_for_timeout(300)
    record("desktop_iframe_fails_closed_when_the_map_container_is_hidden",
           hidden_reply and hidden_res[:1] == [{"req": 990002, "ok": False, "reason": "map-hidden"}] and view()["zoom"] == h0["zoom"], hidden_res)

    # 等待中狀態改變：離開戰略地圖或停用後才到的 ok:true → 視為 ok:false（不記錄成功或冷卻）
    def changed(label, change, restore):
        page.wait_for_timeout(1900)
        page.evaluate(ZR_HOLD_JS)
        a, v0 = st(), view()
        n = page.evaluate("window.__zrHeld.length")
        pad.tap("ZR")
        held = page.evaluate("window.__zrHeld")[n:]
        r = held[0]["req"] if held else None
        change()
        mframe.evaluate(ZR_FORGE_JS, {"req": r, "ok": True})
        wait(f"window.__zrResults.some(x => x.req === {r if r else -1})")
        page.wait_for_timeout(60)
        b = st()
        page.evaluate(ZR_RELEASE_JS)
        restore()
        return {"label": label, "ok": len(held) == 1 and (b["lastMapAck"] or {}).get("req") == r and b["lastMapAck"]["outcome"] == "failed"
                and b["activatedAt"] == a["activatedAt"] and not b["processing"] and view()["zoom"] == v0["zoom"], "ack": b["lastMapAck"]}

    def back_to_map():
        pad.tap("R")
        wait("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=5000)
        wait("(() => { const s = RedlineController.getState(); return s.focusKind === 'map' && !!s.focusTown; })()", timeout=8000)
        page.wait_for_timeout(300)

    def re_enable():
        page.evaluate("() => RedlineController.setEnabled(true)")
        wait("RedlineController.getState().status === 'connected'", timeout=8000)
        pad.neutral()
        pad.tap("A")  # 重新啟用後第一下只放焦點
        wait("RedlineController.getState().focusKind === 'map'", timeout=5000)

    left = changed("left_map_while_pending", lambda: page.click("button.game-tab[data-view='command']"), back_to_map)
    disabled = changed("disabled_while_pending", lambda: page.evaluate("() => RedlineController.setEnabled(false)"), re_enable)
    ZR_FRAME = "() => RedlineController.feed({ x: 0, y: 0, buttons: [0x80, 0] }) || RedlineController.feed({ x: 0, y: 0, buttons: [0, 0] })"
    ctx_cases.append(silent("disabled", lambda: (page.evaluate("() => RedlineController.setEnabled(false)"), page.evaluate(ZR_FRAME),
                                                 page.evaluate("window.__padSend(0, 0, 0x80, 0)"), page.evaluate("window.__padSend(0, 0, 0, 0)")),
                            re_enable))
    # 斷線（error）與重連中（connecting）：bridge 停在連線中，期間的 ZR 一律丟棄
    page.evaluate("window.__bridgeHold = true; window.__padHeartbeat = false")
    page.evaluate("window.__padClose()")
    wait("RedlineController.getState().status === 'error'", timeout=3000)
    ctx_cases.append(silent("disconnected_error", lambda: page.evaluate(ZR_FRAME)))
    connecting = wait("RedlineController.getState().status === 'connecting'", timeout=5000)
    ctx_cases.append(silent("reconnecting", lambda: (page.evaluate(ZR_FRAME), page.evaluate("window.__padSend(0, 0, 0x80, 0)"))))
    page.evaluate("window.__bridgeHold = false; window.__padLast = [0, 0, 0, 0]; window.__bridgeOpenHeld(); window.__padHeartbeat = true")
    wait("RedlineController.getState().status === 'connected'", timeout=5000)
    pad.neutral()
    # stale：公開 feed() 丟棄；目前 bridge 的 ZR frame 只當 recover baseline
    page.evaluate("window.__padHeartbeat = false")
    stale = wait("RedlineController.getState().status === 'stale'", timeout=5000)
    ctx_cases.append(silent("stale", lambda: (page.evaluate(ZR_FRAME), page.evaluate("window.__padSend(0, 0, 0x80, 0)"))))
    page.evaluate("window.__padSend(0, 0, 0, 0); window.__padHeartbeat = true")
    wait("RedlineController.getState().status === 'connected'", timeout=3000)
    pad.neutral()
    # 重連時 ZR 已按住：第一筆只當 baseline
    page.evaluate("window.__padHeartbeat = false")
    page.evaluate("window.__padClose()")
    wait("RedlineController.getState().status !== 'connected'", timeout=3000)
    ctx_cases.append(silent("reconnect_with_ZR_held", lambda: (page.evaluate("window.__padLast = [0, 0, 0x80, 0]; window.__padHeartbeat = true"),
                                                               wait("RedlineController.getState().status === 'connected'", timeout=8000),
                                                               page.wait_for_timeout(500))))
    pad.neutral()
    # 正向對照：同一個頁面恢復後 ZR 照常前進一級
    page.wait_for_timeout(300)
    pv_a = view()
    resumed = zr_once()
    pv_b = view()
    record("desktop_ZR_fails_closed_in_modal_hidden_or_missing_iframe_disabled_disconnected_reconnecting_and_stale",
           modal_open and still_open and connecting and stale and all(c["ok"] for c in ctx_cases)
           and resumed and pv_b["zoom"] == zr_next(pv_a), [ctx_cases, pv_a["zoom"], pv_b["zoom"]])
    record("desktop_ZR_ack_after_leaving_the_map_or_disabling_is_treated_as_failed", left["ok"] and disabled["ok"], [left, disabled])

    # (j) 其他分頁：戰況紀錄的 ZR 也完全 no-op
    pad.tap("R")
    wait("document.querySelector('.game-tab.active').dataset.view === 'log'", timeout=5000)
    page.wait_for_timeout(300)
    g0 = st()
    pad.tap("ZR")
    page.wait_for_timeout(200)
    g1 = st()
    record("desktop_ZR_on_log_view_is_a_full_noop", g0["view"] == "log" and quiet(g1) == quiet(g0), [g0, g1])
    pad_note = page.evaluate("document.querySelector('#padPanel .pad-note:not([id])')?.textContent || ''")
    record("desktop_settings_help_documents_ZR", "ZR（戰略地圖）：放大一級，到最大後再按回到最小" in pad_note, pad_note)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks, console_errors = [], []

    def record(name, ok, detail=None):
        checks.append({"name": name, "passed": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))

    server = None
    base = os.environ.get("REDLINE_BASE_URL", "").rstrip("/")
    if not base:
        server, base = start_server()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            context.add_init_script(MOCK_WS)
            page = context.new_page()
            page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errors.append(str(e)))
            pad = Pad(page)

            # ---------- 1. 預設不連線、不接管焦點 ----------
            setup = post_json(base, "/test/setup-move-confirmation-proof",
                              {"mover_faction": "taiwan_green", "mover_base": "新竹", "mover_town": "臺北", "moves_left": 5})
            page.goto(base + setup["url"], wait_until="networkidle")
            page.wait_for_selector("#gameShell", state="visible", timeout=15000)
            page.evaluate("() => window.closeEventReveal && closeEventReveal()")
            page.wait_for_timeout(300)
            attempts = page.evaluate("window.__bridgeAttempts")
            record("default_off_no_bridge_connection", attempts == 0 and page.evaluate("RedlineController.getState().enabled") is False, attempts)
            record("default_off_no_focus_ring", focus_info(page) is None)
            record("feed_ignored_while_disabled", page.evaluate("RedlineController.feed({x:1,y:0,buttons:[8,0]})") is None
                   and focus_info(page) is None)
            hud_h = page.evaluate("document.getElementById('hud').getBoundingClientRect().height")

            # ---------- 2. 啟用、URL 驗證與持久化 ----------
            page.click("#padToggleBtn")
            page.fill("#padUrlInput", "ws://evil.example/ws")
            page.click("#padSaveBtn")
            record("non_loopback_url_rejected", page.is_visible("#padUrlError"))
            page.fill("#padUrlInput", BRIDGE_URL)
            page.click("#padSaveBtn")
            page.check("#padEnableChk")
            page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=5000)
            stored = page.evaluate("JSON.parse(localStorage.getItem('redline.controller.v1'))")
            record("settings_persisted", stored == {"enabled": True, "url": BRIDGE_URL}, stored)
            page.click("#padToggleBtn")
            page.evaluate(SPY)

            # ---------- 3. 焦點：第一次輸入只放焦點、不點擊 ----------
            pad.neutral()
            pad.tap("A")
            f1 = focus_info(page)
            record("first_press_places_focus_without_click", f1 is not None and page.evaluate("__spy.sendAction") == 0, f1)
            record(
                "card_focus_uses_yellow_16_percent_overlay_without_ring_or_glow",
                bool(f1)
                and "card" in f1["cls"]
                and f1["outlineWidth"] == f1["peerOutlineWidth"]
                and f1["boxShadow"] == f1["peerBoxShadow"]
                and f1["overlayBackground"] == "rgba(255, 216, 61, 0.16)",
                f1,
            )
            # 以元素為單位計數（起手牌是隨機抽的，可能有多張同名、同文字的手牌）
            focus_key = lambda: (page.evaluate(FOCUS_KEY_JS, None) or {}).get("key")
            seen = {focus_key()}
            for d in ["right", "right", "down", "left", "down"]:
                pad.push(d)
                if focus_info(page):
                    seen.add(focus_key())
            record("stick_moves_focus_between_controls", len(seen - {None}) >= 3, sorted(k for k in seen if k))
            record("hud_height_unchanged", abs(page.evaluate("document.getElementById('hud').getBoundingClientRect().height") - hud_h) < 1)
            page.screenshot(path=str(OUT / "01_command_focus.png"))

            # ---------- 4. 六個全域區段只由 R／SR 切換：方向鍵碰不到分頁與結束行動（class 與原生焦點皆然） ----------
            page.evaluate("""() => { window.__clicks = []; document.addEventListener('click', e => window.__clicks.push(e.target.id || e.target.className), true); }""")
            on_section = """() => { const ex = el => !!el && el !== document.body && !!el.closest
                && (!!el.closest('#gameTabs .game-tab') || !!el.closest('#turnActionButtons'));
              return ex(document.querySelector('.rl-pad-focus')) || ex(document.activeElement)
                || [...document.querySelectorAll('#gameTabs .game-tab, #turnActionButtons button')].some(t => t.matches(':focus') || t.matches(':focus-visible')); }"""
            tab_hits = []
            for d in ["up"] * 6 + ["left"] * 3 + ["right"] * 8 + ["up"] * 2:
                pad.push(d)
                if page.evaluate(on_section):
                    tab_hits.append([d, focus_info(page)])
            record("dpad_never_reaches_section_tabs_or_end_step", not tab_hits, tab_hits[:3])
            view_is = lambda v: page.wait_for_function(f"document.querySelector('.game-tab.active').dataset.view === '{v}'", timeout=3000)
            pad.tap("R")  # 指揮中心 → 戰略地圖
            view_is("map")
            pad.tap("R")  # 戰略地圖 → 戰況紀錄
            view_is("log")
            page.wait_for_timeout(250)
            record("R_reaches_log_section_without_tab_focus",
                   page.evaluate("document.getElementById('logView').classList.contains('active')") and not page.evaluate(on_section), focus_info(page))
            pad.tap("R")
            page.wait_for_timeout(300)
            record("R_cycles_to_next_tab", page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "myFaction")
            pad.tap("SR")
            page.wait_for_timeout(200)
            record("SR_cycles_to_previous_tab", page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "log")
            pad.tap("SR")
            pad.tap("SR")
            page.wait_for_timeout(300)
            record("SR_SR_returns_to_command", page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "command"
                   and not page.evaluate(on_section))

            # PLUS：只發動「唯一一個」可用的既有陣營能力；沒有或不只一個時不做事（不會觸發結束步驟）
            abilities = page.evaluate("""[...document.querySelectorAll('#factionActionButtons button, #redArmyAbilityBtn')]
              .filter(b => b.getClientRects().length && !b.disabled && b.getAttribute('aria-disabled') !== 'true').map(b => b.textContent.trim())""")
            page.evaluate("""() => { window.__abilityClicks = 0; for (const el of document.querySelectorAll('#factionActionButtons, #redArmyAbilityBtn'))
              el.addEventListener('click', () => { window.__abilityClicks += 1; }, true); }""")
            before = page.evaluate("__spy.sendAction")
            advance_before = page.evaluate("(window.__clicks || []).filter(c => c === 'advanceStepBtn').length")
            pad.tap("PLUS")
            page.wait_for_timeout(300)
            clicks = page.evaluate("window.__abilityClicks")
            no_advance = page.evaluate("(window.__clicks || []).filter(c => c === 'advanceStepBtn').length") == advance_before
            record("plus_runs_only_the_single_usable_faction_ability",
                   no_advance and ((clicks == 1) if len(abilities) == 1 else (clicks == 0 and page.evaluate("__spy.sendAction") == before)),
                   [abilities, clicks, no_advance])
            for _ in range(3):  # 能力若開了既有選擇視窗，用既有關閉收起，讓後面的流程從一般頁面開始
                if not page.evaluate("[...document.querySelectorAll('.modal-overlay')].some(m => getComputedStyle(m).display !== 'none' && m.getClientRects().length)"):
                    break
                pad.tap("B")
                page.wait_for_timeout(250)

            # ---------- 5. B 在沒有取消時不做事 ----------
            before = page.evaluate("[__spy.sendAction, __spy.cancelChoice]")
            pad.tap("B")
            record("B_noop_without_cancel", page.evaluate("[__spy.sendAction, __spy.cancelChoice]") == before)

            # ---------- 6. Modal 優先權 ----------
            page.evaluate("""() => { const s = structuredClone(window.lastGameState); s.turn_phase = 'end'; window.lastGameState = s; playHandCard(0, '領導', 'resource'); }""")
            page.wait_for_function("document.getElementById('unavailableActionModal').style.display === 'flex'", timeout=3000)
            page.wait_for_timeout(200)
            pad.push("down")
            f = focus_info(page)
            record("modal_takes_focus", bool(f) and f["modalId"] == "unavailableActionModal", f)
            outside = False
            for d in ["up", "left", "right", "down", "down", "left", "up", "up"]:
                pad.push(d)
                f = focus_info(page)
                outside = outside or not (f and f["modalId"] == "unavailableActionModal")
            record("modal_scope_blocks_background_navigation", not outside)
            record("R_ignored_inside_modal", (pad.tap("R"), page.evaluate("document.querySelector('.game-tab.active').dataset.view"))[1] == "command")
            page.screenshot(path=str(OUT / "02_modal_priority.png"))
            before = page.evaluate("__spy.sendAction")
            pad.tap("B")
            page.wait_for_timeout(200)
            record("B_closes_modal_via_existing_close_button", page.evaluate("document.getElementById('unavailableActionModal').style.display") == "none"
                   and page.evaluate("__spy.sendAction") == before)
            record("modal_close_returns_focus_to_page", (focus_info(page) or {}).get("inModal") is False, focus_info(page))

            # ---------- 7. 斷線 / 重連：held 按鈕不會自動觸發 ----------
            # 連線中斷時玩家剛好按住 A+R；重連後第一筆就是「已按住」→ 只能當 baseline，不可觸發。
            clicks_before = page.evaluate("__spy.sendAction")
            page.evaluate("window.__padHeartbeat = false")
            page.evaluate("window.__padClose()")
            page.wait_for_function("RedlineController.getState().status !== 'connected'", timeout=3000)
            held_cleared = page.evaluate("Object.values(RedlineController.getState().held).every(v => !v)")
            page.evaluate("window.__padLast = [0, 0, 0x48, 0]; window.__padHeartbeat = true")
            page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
            page.wait_for_timeout(500)
            record("disconnect_clears_held_and_reconnects", held_cleared)
            record("reconnect_held_buttons_do_not_fire",
                   page.evaluate("__spy.sendAction") == clicks_before
                   and page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "command")
            pad.neutral()  # 放開後才重新武裝
            page.wait_for_timeout(100)
            # stale：停止送 frame
            page.evaluate("window.__padHeartbeat = false")
            page.wait_for_function("RedlineController.getState().status === 'stale'", timeout=5000)
            record("stale_input_detected", True)
            page.evaluate("window.__padHeartbeat = true")
            pad.neutral()
            page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=3000)

            # ---------- 8. 地圖：來源 / 目的地焦點、A、B、fail-closed ----------
            pad.tap("R")  # command → map
            page.wait_for_function("document.querySelector('.game-tab.active').dataset.view === 'map'", timeout=5000)
            page.wait_for_function("document.getElementById('strategicMapFrame').contentWindow.lastGameState", timeout=20000)
            page.wait_for_timeout(1500)
            mframe = next(f for f in page.frames if "leaflet_game_map" in f.url)
            page.wait_for_function("RedlineController.getState().focusKind === 'map'", timeout=8000)
            state = page.evaluate("RedlineController.getState()")
            record("map_context_detected", state["scope"] == "map", state)
            snap = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
            record("map_snapshot_initially_only_origins", snap["scope"] == "move" and snap["targets"]
                   and all(t["role"] == "origin" for t in snap["targets"]), snap)
            origins = [t["town"] for t in snap["targets"]]
            origin = mframe.evaluate("(names) => names.find(n => { const o = movementOptionsForTown(n); return o.road.length + o.rail.length > 0; })", origins)
            record("map_has_origin_with_server_legal_moves", origin is not None, origins)
            # 以真實搖桿方向把焦點移到來源，A 選取
            reached = focus_town_toward(pad, page, mframe, origin)
            record("map_stick_focuses_origin_town", reached, page.evaluate("RedlineController.getState()"))
            ring = mframe.evaluate("document.querySelectorAll('.pad-focus-label').length")
            record("map_focus_ring_rendered_on_target", ring == 1, ring)
            page.screenshot(path=str(OUT / "03_map_focus.png"))

            # 非法目標 fail-closed：非候選城鎮的 activate 不得有任何作用
            illegal = mframe.evaluate("""() => { const ok = window.__redlineControllerAdapter.snapshot().targets.map(t => t.town); return [...byName.keys()].find(n => !ok.includes(n)); }""")
            def post_cmd(**cmd):
                page.evaluate("""(c) => document.getElementById('strategicMapFrame').contentWindow.postMessage(
                  Object.assign({type:'redline-controller-command', v:1}, c), location.origin)""", cmd)
                page.wait_for_timeout(300)
            post_cmd(cmd="activate", town=illegal)
            record("map_illegal_target_activate_is_rejected", mframe.evaluate("selectedTown") is None, illegal)
            post_cmd(cmd="focus", town=illegal)
            record("map_illegal_target_focus_is_rejected", page.evaluate("RedlineController.getState().focusTown") == origin)
            # 來源驗證：iframe 自己 postMessage（source 不是 parent）必須被忽略
            mframe.evaluate("(town) => window.postMessage({type:'redline-controller-command', v:1, cmd:'activate', town}, location.origin)", origin)
            page.wait_for_timeout(300)
            record("map_message_from_non_parent_source_ignored", mframe.evaluate("selectedTown") is None)
            post_cmd(cmd="button", id="advanceStepBtn")
            record("map_non_whitelisted_button_rejected", mframe.evaluate("selectedTown") is None and page.evaluate("__spy.sendAction") == 0)

            pad.tap("A")
            page.wait_for_timeout(700)
            record("map_A_selects_origin_via_existing_click_path", mframe.evaluate("selectedTown") == origin, mframe.evaluate("selectedTown"))
            snap2 = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
            moves = [t["town"] for t in snap2["targets"] if t["role"] == "move"]
            legal = mframe.evaluate("selectedMoveTargets.map(t => t.town)")
            record("map_move_targets_equal_server_legal_moves", bool(moves) and sorted(moves) == sorted(set(legal)), [moves[:4], legal[:4]])
            record("map_B_available_after_selection", snap2["canCancel"] is True)
            dest = moves[0] if moves else None
            if dest:
                record("map_stick_focuses_legal_destination", focus_town_toward(pad, page, mframe, dest))
                page.screenshot(path=str(OUT / "04_map_move_target_focus.png"))
                before = page.evaluate("__spy.sendAction")
                pad.tap("A")
                page.wait_for_timeout(500)
                pending = mframe.evaluate("pendingMoveTarget")
                confirm_enabled = mframe.evaluate("!document.getElementById('confirmMoveBtn').disabled")
                record("map_A_on_destination_arms_confirm_without_executing",
                       bool(pending) and pending["to"] == dest and confirm_enabled and page.evaluate("__spy.sendAction") == before, [pending, confirm_enabled])
                snap3 = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
                record("map_confirm_button_offered_from_existing_ui", any(b["id"] == "confirmMoveBtn" for b in snap3["buttons"]), snap3["buttons"])
            pad.tap("B")
            page.wait_for_timeout(500)
            record("map_B_cancels_selection_via_existing_flow", mframe.evaluate("selectedTown") is None)
            before = page.evaluate("__spy.cancelChoice")
            pad.tap("B")
            record("map_B_noop_when_nothing_to_cancel", page.evaluate("__spy.cancelChoice") == before and mframe.evaluate("selectedTown") is None)

            # ---------- 9. pending choice：地圖目標 + 取消瓦解 ----------
            setup2 = post_json(base, "/test/setup-dissolve-cancel-single-target")
            page.goto(base + setup2["url"], wait_until="networkidle")
            page.wait_for_selector("#gameShell", state="visible", timeout=15000)
            page.evaluate("() => window.closeEventReveal && closeEventReveal()")
            page.wait_for_timeout(300)
            page.evaluate(SPY)
            page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
            page.click("button.game-tab[data-view=\"map\"]")
            page.wait_for_function("document.getElementById('strategicMapFrame').contentWindow.lastGameState", timeout=20000)
            page.wait_for_timeout(2500)
            mframe = next(f for f in page.frames if "leaflet_game_map" in f.url)
            pad.neutral()
            pad.tap("X")
            page.wait_for_timeout(500)
            snap3 = mframe.evaluate("window.__redlineControllerAdapter.snapshot()")
            record("choice_scope_targets_match_pending_choice", snap3["scope"] == "choice" and snap3["targets"]
                   and all(t["role"] == "choice" for t in snap3["targets"]), snap3)
            highlight = mframe.evaluate("(supportChoiceHighlight?.towns || []).map(t => t.town)")
            record("choice_targets_equal_server_candidates", sorted(t["town"] for t in snap3["targets"]) == sorted(highlight), [highlight])
            before_view = page.evaluate("document.querySelector('.game-tab.active').dataset.view")
            pad.tap("R")
            record("required_choice_blocks_tab_switching", page.evaluate("document.querySelector('.game-tab.active').dataset.view") == before_view)
            record("required_choice_blocks_turn_buttons",
                   page.evaluate("""() => { const el = document.querySelector('.rl-pad-focus'); return !el || !el.closest('#turnActionButtons'); }"""))
            tgt = snap3["targets"][0]["town"]
            page.evaluate("""(town) => document.getElementById('strategicMapFrame').contentWindow.postMessage(
              {type:'redline-controller-command', v:1, cmd:'activate', town}, location.origin)""", tgt)
            page.wait_for_timeout(600)
            record("choice_A_selects_candidate_via_existing_click", mframe.evaluate("selectedTown") == tgt)
            page.screenshot(path=str(OUT / "05_choice_map_focus.png"))
            cancel_visible = mframe.evaluate("(() => { const b = document.getElementById('cancelDissolveChoiceBtn'); return b.style.display !== 'none' && !b.disabled; })()")
            pad.tap("B")
            page.wait_for_timeout(300)
            # B: 先取消（取消瓦解按鈕可見時走既有取消流程；否則只取消選取）
            page.wait_for_timeout(800)
            pending_now = page.evaluate("window.lastGameState && window.lastGameState.pending_choice")
            record("choice_B_uses_existing_cancel_flow", (not cancel_visible) or pending_now is None, [cancel_visible, pending_now])


            # ---------- 10. 卡牌：A 預覽、B 選擇、手牌 X 資源 / Y 行動 ----------
            setup3 = post_json(base, "/test/setup-move-confirmation-proof",
                               {"mover_faction": "taiwan_green", "mover_base": "新竹", "mover_town": "臺北", "moves_left": 5})
            page.goto(base + setup3["url"], wait_until="networkidle")
            page.wait_for_selector("#gameShell", state="visible", timeout=15000)
            page.evaluate("() => window.closeEventReveal && closeEventReveal()")
            page.wait_for_function("RedlineController.getState().status === 'connected'", timeout=8000)
            page.evaluate(SPY)
            page.evaluate("""() => {
              window.__cardSpy = { play: [], preview: [], toggle: 0 };
              const play = window.playHandCard; window.playHandCard = function (...a) { window.__cardSpy.play.push([a[0], a[1], a[2]]); return play.apply(this, a); };
              const prev = window.selectCardDetail; window.selectCardDetail = function (el) { window.__cardSpy.preview.push(el.dataset.cardName + '|' + el.dataset.cardZone); return prev.apply(this, arguments); };
              const tog = window.togglePurchaseSelection; window.togglePurchaseSelection = function (...a) { window.__cardSpy.toggle += 1; return tog.apply(this, a); };
            }""")
            cs = lambda: page.evaluate("JSON.parse(JSON.stringify(window.__cardSpy))")
            sends = lambda: page.evaluate("__spy.sendAction")
            hand_n = lambda: page.evaluate("document.querySelectorAll('#hand .hand-card').length")
            checked = lambda: page.evaluate("[...document.querySelectorAll('.purchase-card-select-button[data-purchase-index]')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.purchaseIndex)")
            preview_open = lambda: page.evaluate("document.getElementById('cardPreviewModal').style.display === 'flex'")
            _NAV_GRAPHS.clear()
            pad.neutral()
            pad.tap("A")  # 第一次只放焦點
            BUY = '.purchase-card-item:has(.purchase-card-select-button[data-purchase-index="0"]:not(:disabled)) > .card[data-card-zone="purchase"]'
            BUY_DISABLED = '.purchase-card-item:has(.purchase-card-select-button[data-purchase-index="4"]:disabled) > .card[data-card-zone="purchase"]'
            # 起手牌是隨機抽的：以「第一張非奧援手牌」為目標，期望值在執行時讀取，不假設牌名。
            HAND = '#hand .hand-card:not([data-card-name*="奧援"])'
            HAND_FOLLOWER = HAND
            hand_name = lambda: page.evaluate(f"document.querySelector('{HAND}')?.dataset.cardName || null")

            # 購買區卡牌：A 只預覽，不選擇、不購買
            record("card_focus_reaches_purchase_card", focus_dom_toward(pad, page, BUY), focus_info(page))
            # 方向鍵只停在整張購買卡牌：選擇按鈕（常設與隨機）不在焦點集合、沒有焦點遮罩
            RAND = '#purchaseRandom .purchase-card-item:has(.purchase-card-select-button[data-purchase-index]:not(:disabled)) > .card[data-card-zone="purchase"]'
            STAT = '#purchaseStatic .purchase-card-item:has(.purchase-card-select-button[data-purchase-index]:not(:disabled)) > .card[data-card-zone="purchase"]'
            probe = """() => { const el = document.querySelector('.rl-pad-focus'); if (!el) return null;
              return { tag: el.tagName, type: el.type || null, host: el.closest('[data-card-zone]')?.dataset.cardZone || null,
                       isCard: el.matches('.card[data-card-zone]'), zone: el.closest('#purchaseStatic') ? 'static' : el.closest('#purchaseRandom') ? 'random' : null }; }"""
            seen_zones, bad = set(), []
            has_random = page.evaluate(f"!!document.querySelector('{RAND}')")
            record("random_purchase_area_has_enabled_card_for_proof", has_random)
            for target in [STAT, RAND]:
                if not page.evaluate(f"!!document.querySelector('{target}')"):
                    continue
                focus_dom_toward(pad, page, target)
                for d in ["down", "right", "up", "left", "right", "right", "down", "left", "up", "up", "left", "down"]:
                    pad.push(d)
                    f = page.evaluate(probe)
                    if f and f["host"] == "purchase":
                        seen_zones.add(f["zone"])
                        if f["tag"] == "INPUT" or not f["isCard"]:
                            bad.append(f)
            record("arrow_focus_never_lands_on_purchase_select_button", not bad, bad[:3])
            record("arrow_focus_stops_on_static_and_random_purchase_cards", {"static", "random"} <= seen_zones, sorted(seen_zones))
            record("purchase_select_buttons_have_no_controller_focus_class",
                   page.evaluate("document.querySelectorAll('.purchase-card-select-button.rl-pad-focus').length") == 0)
            record("focus_back_to_static_purchase_card", focus_dom_toward(pad, page, STAT), focus_info(page))
            rand_idx = page.evaluate(f"document.querySelector('{RAND}')?.closest('.purchase-card-item')?.querySelector('.purchase-card-select-button').dataset.purchaseIndex") if has_random else None
            if rand_idx is not None:
                focus_dom_toward(pad, page, RAND)
                on = page.evaluate(probe)
                pad.tap("B")
                page.wait_for_timeout(250)
                after_on = checked()
                pad.tap("B")
                page.wait_for_timeout(250)
                record("random_card_B_toggles_on_then_off_via_existing_button",
                       bool(on and on["isCard"] and on["zone"] == "random") and after_on == [rand_idx] and checked() == [], [on, after_on, checked()])
                record("focus_back_to_static_purchase_card_again", focus_dom_toward(pad, page, STAT), focus_info(page))
            card_focus_shot = page.evaluate("""() => { const el = document.querySelector('.card.rl-pad-focus');
              const button = el.closest('.purchase-card-item').querySelector('.purchase-card-select-button');
              const overlay = getComputedStyle(el, '::after'), b = getComputedStyle(button);
              return { overlayBackground: overlay.backgroundColor, buttonOutline: parseFloat(b.outlineWidth), buttonOutlineStyle: b.outlineStyle,
                       buttonHasClass: button.classList.contains('rl-pad-focus') }; }""")
            record("purchase_card_has_yellow_overlay_button_does_not",
                   "255, 216, 61" in card_focus_shot["overlayBackground"] and not card_focus_shot["buttonHasClass"]
                   and (card_focus_shot["buttonOutline"] == 0 or card_focus_shot["buttonOutlineStyle"] == "none"), card_focus_shot)
            page.evaluate("document.querySelector('.rl-pad-focus').scrollIntoView({block: 'center'})")
            page.wait_for_timeout(200)
            page.screenshot(path=str(OUT / "09_purchase_card_focus_no_checkbox_ring.png"))

            page.evaluate("() => { window.__cardSpy.toggle = 0; window.__cardSpy.preview = []; window.__cardSpy.play = []; __spy.sendAction = 0; }")
            pad.tap("A")
            page.wait_for_timeout(250)
            c = cs()
            record("card_A_opens_preview_only", preview_open() and c["preview"] == ["%s|purchase" % page.evaluate(f"document.querySelector('{BUY}').dataset.cardName")]
                   and c["toggle"] == 0 and checked() == [] and sends() == 0, [c, checked()])
            page.screenshot(path=str(OUT / "06_card_preview.png"))
            pad.tap("B")  # modal B：既有關閉行為不回歸
            page.wait_for_timeout(250)
            record("modal_B_still_closes_card_preview", not preview_open() and cs()["toggle"] == 0 and checked() == [], [preview_open(), checked()])

            # B 選擇／取消選擇（既有選擇按鈕 + togglePurchaseSelection）
            record("card_focus_returns_to_purchase_card", focus_dom_toward(pad, page, BUY), focus_info(page))
            pad.tap("B")
            page.wait_for_timeout(250)
            record("card_B_checks_purchase_card_via_existing_control", checked() == ["0"] and cs()["toggle"] == 1 and sends() == 0 and not preview_open(), [checked(), cs()])
            pad.tap("A")
            page.wait_for_timeout(200)
            record("card_A_on_checked_card_previews_without_changing_check", preview_open() and checked() == ["0"] and cs()["toggle"] == 1 and sends() == 0)
            pad.tap("B")
            page.wait_for_timeout(200)
            record("card_focus_restored_after_preview", (focus_info(page) or {}).get("inModal") is False and checked() == ["0"], focus_info(page))
            # B 選擇後的 Y＝既有「購買所選」；本 fixture 資源為 0，既有按鈕停用（買不起）→ fail closed，不開確認單、不購買
            buy_disabled = page.evaluate("document.getElementById('openPurchaseConfirmBtn').disabled")
            pad.tap("Y")
            page.wait_for_timeout(250)
            record("purchase_card_Y_fails_closed_when_checked_but_existing_buy_disabled",
                   buy_disabled and page.evaluate("getComputedStyle(document.getElementById('purchaseConfirmModal')).display") == "none"
                   and checked() == ["0"] and cs()["toggle"] == 1 and sends() == 0, [buy_disabled, checked()])
            pad.tap("B")
            page.wait_for_timeout(250)
            record("card_B_toggles_purchase_card_off", checked() == [] and cs()["toggle"] == 2 and sends() == 0, [checked(), cs()])

            # 購買區 X/Y：不得觸發手牌；未選擇時 Y 不會自動選擇、不開確認單、不切換說明（只顯示「先按 B 選擇」）
            pad.tap("X")
            page.wait_for_timeout(200)
            record("purchase_card_X_is_full_noop", cs()["play"] == [] and sends() == 0 and checked() == []
                   and page.evaluate("!!document.querySelector('.rl-pad-focus').closest('[data-card-zone=\"purchase\"]')"), focus_info(page))
            page.wait_for_timeout(300)
            pad.tap("Y")
            page.wait_for_timeout(200)
            record("purchase_card_Y_unchecked_fails_closed_no_auto_check_no_help_toggle", cs()["play"] == [] and sends() == 0 and checked() == []
                   and cs()["toggle"] == 2 and page.evaluate("RedlineController.getState().helpOpen !== true")
                   and page.evaluate("getComputedStyle(document.getElementById('purchaseConfirmModal')).display") == "none"
                   and page.evaluate("!!document.querySelector('.rl-pad-focus').closest('[data-card-zone=\"purchase\"]')")
                   and "先按 B 選擇" in page.evaluate("document.getElementById('padHint').textContent"),
                   [focus_info(page), page.evaluate("document.getElementById('padHint').textContent")])

            # 選擇按鈕仍 enabled 但被頁面狀態隱藏：聚焦卡牌後 B 必須完整 no-op
            record("card_focus_before_hidden_checkbox_case", focus_dom_toward(pad, page, BUY), focus_info(page))
            for variant, hide, restore in [
                ("display_none", "box.style.display = 'none'", "box.style.display = ''"),
                ("button_visibility_hidden", "box.style.visibility = 'hidden'", "box.style.visibility = ''"),
            ]:
                still_enabled = page.evaluate(f"""() => {{ const box = document.querySelector('{BUY}').closest('.purchase-card-item').querySelector('.purchase-card-select-button');
                  {hide}; return !box.disabled && box.getAttribute('aria-disabled') !== 'true'; }}""")
                page.wait_for_timeout(250)
                focus_key = lambda: page.evaluate("(() => { const e = document.querySelector('.rl-pad-focus'); return e ? [e.tagName, e.dataset.cardName || '', e.dataset.cardZone || ''].join('|') : null; })()")
                before = dict(key=focus_key(), toggle=cs()["toggle"], sends=sends(), checked=checked(), help=page.evaluate("RedlineController.getState().helpOpen"), plays=cs()["play"], previews=cs()["preview"])
                hidden = page.evaluate(f"""() => {{ const box = document.querySelector('{BUY}').closest('.purchase-card-item').querySelector('.purchase-card-select-button');
                  return box.getClientRects().length === 0 || getComputedStyle(box).visibility === 'hidden'; }}""")
                pad.tap("B")
                page.wait_for_timeout(250)
                after = dict(key=focus_key(), toggle=cs()["toggle"], sends=sends(), checked=checked(), help=page.evaluate("RedlineController.getState().helpOpen"), plays=cs()["play"], previews=cs()["preview"])
                record(f"card_B_noop_when_enabled_select_button_hidden_{variant}", still_enabled and hidden and before == after and before["key"] is not None and after["checked"] == [],
                       [still_enabled, hidden, before, after])
                page.evaluate(f"""() => {{ const box = document.querySelector('{BUY}').closest('.purchase-card-item').querySelector('.purchase-card-select-button'); {restore}; }}""")
                page.wait_for_timeout(250)
            pad.tap("B")
            page.wait_for_timeout(250)
            record("card_B_toggles_again_after_select_button_restored", checked() == ["0"] and cs()["toggle"] == 3, [checked(), cs()["toggle"]])
            pad.tap("B")
            page.wait_for_timeout(250)
            record("card_B_toggle_off_after_restore", checked() == [] and cs()["toggle"] == 4, [checked(), cs()["toggle"]])

            # 不可選擇（disabled）的卡牌：B fail-closed
            if page.evaluate(f"!!document.querySelector('{BUY_DISABLED}')"):
                page.evaluate("""(sel) => { const c = document.querySelector(sel); c.setAttribute('data-controller-probe', '1'); }""", BUY_DISABLED)
                reached = focus_dom_toward(pad, page, BUY_DISABLED)
                if reached:
                    pad.tap("B")
                    page.wait_for_timeout(200)
                    record("card_B_noop_on_disabled_select_button", checked() == [] and cs()["toggle"] == 4 and sends() == 0, checked())
                else:
                    record("card_B_noop_on_disabled_select_button", False, "cannot focus disabled card")

            # 手牌：A 預覽不使用；非手牌 B 不取消
            record("card_focus_reaches_hand_card", focus_dom_toward(pad, page, HAND), focus_info(page))
            page.screenshot(path=str(OUT / "07_hand_card_focus.png"))
            pad.tap("A")
            page.wait_for_timeout(250)
            record("hand_card_A_previews_without_playing", preview_open() and cs()["play"] == [] and sends() == 0 and hand_n() == 5, cs())
            pad.tap("B")
            page.wait_for_timeout(250)
            record("hand_card_B_noop_without_checkbox", cs()["play"] == [] and sends() == 0 and checked() == [], [cs(), checked()])

            # 手牌 Y = 行動（先用不需目標的追隨者以外的樂捐者以外之卡：這裡直接驗證 mode 與卡牌索引）
            record("card_focus_reaches_follower", focus_dom_toward(pad, page, HAND_FOLLOWER), focus_info(page))
            y_name = hand_name()
            idx = page.evaluate(f"document.querySelector('{HAND_FOLLOWER}').querySelector('[data-card-mode=\"action\"]').dataset.cardIndex")
            page.screenshot(path=str(OUT / "08_hand_focus_with_controls.png"), clip=page.evaluate(
                """() => { const r = document.getElementById('hand').getBoundingClientRect(); return {x: Math.max(0, r.left - 10), y: Math.max(0, r.top - 10), width: Math.min(r.width + 20, innerWidth), height: Math.min(r.height + 20, innerHeight - Math.max(0, r.top - 10))}; }"""))
            before_sends = sends()
            pad.tap("Y")
            page.wait_for_timeout(500)
            c = cs()
            record("hand_Y_plays_card_as_action_via_existing_flow", c["play"] == [[int(idx), y_name, "action"]], c)

            # 手牌 X = 資源（重新取得手牌焦點）
            page.wait_for_timeout(600)
            pad.neutral()
            x_name = hand_name()
            ok = focus_dom_toward(pad, page, HAND)
            record("card_focus_reaches_hand_card_for_resource", ok, focus_info(page))
            n_before = len(cs()["play"])
            hand_before = hand_n()
            pad.tap("X")
            page.wait_for_timeout(500)
            c = cs()
            record("hand_X_plays_card_as_resource_via_existing_flow",
                   len(c["play"]) == n_before + 1 and c["play"][-1][1:] == [x_name, "resource"], c)

            # 手牌按鈕被停用（伺服器權威）→ X/Y fail-closed
            page.evaluate("""() => { document.querySelectorAll('#hand .hand-card-action-btn').forEach(b => { b.disabled = true; b.setAttribute('aria-disabled', 'true'); }); }""")
            page.wait_for_timeout(200)
            if focus_dom_toward(pad, page, '#hand .hand-card'):
                n_before = len(cs()["play"])
                pad.tap("X")
                pad.tap("Y")
                record("hand_X_Y_fail_closed_when_controls_disabled", len(cs()["play"]) == n_before, cs())
            else:
                record("hand_X_Y_fail_closed_when_controls_disabled", False, "cannot focus hand card")

            # ---------- 11. 實機 Capture（b1 0x40）→ 既有結束行動危險確認，預設焦點「返回」；B 取消不送出 ----------
            page.evaluate("() => { window.__advanceSpy = 0; document.getElementById('advanceStepBtn').addEventListener('click', () => { window.__advanceSpy += 1; }, true); }")
            pad.tap("CAPTURE")
            opened = page.evaluate("""() => document.getElementById('lrConfirmModal')?.style.display === 'flex'
              && document.querySelector('.rl-pad-focus')?.id === 'lrConfirmCancelBtn'""")
            page.screenshot(path=str(OUT / "10_physical_capture_confirm_default_back.png"))
            pad.tap("B")
            page.wait_for_timeout(250)
            record("physical_capture_b1_0x40_opens_end_step_confirm_default_back_and_B_cancels",
                   opened and page.evaluate("document.getElementById('lrConfirmModal').style.display") == "none"
                   and page.evaluate("window.__advanceSpy") == 0, [opened, focus_info(page)])

            scenario_desktop_focus_menu(page, pad, base, record)
            scenario_desktop_zr_zoom(page, pad, base, record)

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
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n{report['passed']}/{report['total']} checks passed; proof in {OUT}")
    sys.exit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
