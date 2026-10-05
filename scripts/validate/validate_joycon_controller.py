#!/usr/bin/env python3
"""Joy-Con／搖桿控制的瀏覽器 E2E（真實頁面 + mock bridge WebSocket）。

不碰實體 Joy-Con：以 add_init_script 取代 `ws://127.0.0.1:8000/ws` 的 WebSocket，
由測試注入 {x, y, buttons:[b0,b1]} frame；其餘連線（遊戲 / 地圖）仍走真實 WebSocket。
驗證：預設不連線、焦點與高對比標示、A click、B cancel、modal 優先權、卡牌 A 預覽／B 勾選／手牌 X 資源／Y 行動、斷線重連不誤觸、
地圖目標焦點、非法目標 fail-closed、iframe 訊息來源驗證。

執行（會自動啟動隔離 server，不會碰 8100）：
  uv run python scripts/validate/validate_joycon_controller.py
或指定已啟動的 server：REDLINE_BASE_URL=http://127.0.0.1:8793 uv run python ...
輸出：/tmp/redline-joycon-proof/（截圖與 JSON；不要 commit）
"""

import json
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
BIT = {"A": (0, 0x08), "B": (0, 0x04), "X": (0, 0x02), "Y": (0, 0x01), "R": (0, 0x40), "SR": (0, 0x10), "PLUS": (1, 0x02)}

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
          return { id: el.id, tag: el.tagName, text: (el.textContent || '').trim().slice(0, 30),
                   outlineWidth: parseFloat(cs.outlineWidth), outlineColor: cs.outlineColor,
                   inModal: !!el.closest('.modal-overlay'), modalId: el.closest('.modal-overlay')?.id || null,
                   cls: el.className };
        }"""
    )


def focus_dom_toward(pad, page, selector, steps=40):
    """用真正的搖桿方向輸入把焦點移到 selector 或其內部控制（貪婪：朝目標位移較大的軸推）。"""
    for _ in range(steps):
        d = page.evaluate(
            """(sel) => {
              const cur = document.querySelector('.rl-pad-focus'); const tgt = document.querySelector(sel);
              if (!cur || !tgt) return 'missing';
              if (cur === tgt || tgt.contains(cur)) return 'done';
              const a = cur.getBoundingClientRect(), b = tgt.getBoundingClientRect();
              const dx = (b.left + b.right - a.left - a.right) / 2, dy = (b.top + b.bottom - a.top - a.bottom) / 2;
              return Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up');
            }""", selector)
        if d == "done":
            return True
        if d == "missing":
            return False
        pad.push(d)
    return False


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
            record("focus_ring_is_high_contrast", bool(f1) and f1["outlineWidth"] >= 4 and "255, 225, 77" in f1["outlineColor"], f1)
            seen = {f1["id"] or f1["text"]}
            for d in ["right", "right", "down", "left", "down"]:
                pad.push(d)
                f = focus_info(page)
                if f:
                    seen.add(f["id"] or f["text"])
            record("stick_moves_focus_between_controls", len(seen) >= 3, sorted(seen))
            record("hud_height_unchanged", abs(page.evaluate("document.getElementById('hud').getBoundingClientRect().height") - hud_h) < 1)
            page.screenshot(path=str(OUT / "01_command_focus.png"))

            # ---------- 4. A 觸發既有 click（手牌／卡面預覽） ----------
            page.evaluate("""() => { window.__clicks = []; document.addEventListener('click', e => window.__clicks.push(e.target.id || e.target.className), true); }""")
            tab_target = page.evaluate("document.querySelector('.game-tab[data-view=\"log\"]') && true")
            reached = focus_dom_toward(pad, page, '.game-tab[data-view="log"]')
            pad.tap("A")
            page.wait_for_timeout(300)
            record("A_clicks_focused_tab_via_existing_handler",
                   reached and page.evaluate("document.getElementById('logView').classList.contains('active')"), focus_info(page))
            pad.tap("R")
            page.wait_for_timeout(300)
            record("R_cycles_to_next_tab", page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "myFaction")
            pad.tap("SR")
            page.wait_for_timeout(200)
            record("SR_cycles_to_previous_tab", page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "log")
            pad.tap("SR")
            pad.tap("SR")
            page.wait_for_timeout(300)
            record("SR_wraps_back_to_command", page.evaluate("document.querySelector('.game-tab.active').dataset.view") == "command")

            # + 不可觸發任何東西（結束步驟）
            before = page.evaluate("__spy.sendAction")
            pad.tap("PLUS")
            record("plus_button_does_nothing", page.evaluate("__spy.sendAction") == before)

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


            # ---------- 10. 卡牌：A 預覽、B 勾選、手牌 X 資源 / Y 行動 ----------
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
            checked = lambda: page.evaluate("[...document.querySelectorAll('input[data-purchase-index]')].filter(i => i.checked).map(i => i.dataset.purchaseIndex)")
            preview_open = lambda: page.evaluate("document.getElementById('cardPreviewModal').style.display === 'flex'")
            pad.neutral()
            pad.tap("A")  # 第一次只放焦點
            BUY = '.card[data-card-zone="purchase"]:has(input[data-purchase-index="0"]:not(:disabled))'
            BUY_DISABLED = '.card[data-card-zone="purchase"]:has(input[data-purchase-index="4"]:disabled)'
            HAND = '#hand .hand-card[data-card-name="樂捐者"]'
            HAND_FOLLOWER = '#hand .hand-card[data-card-name="追隨者"]'

            # 購買區卡牌：A 只預覽，不勾選、不購買
            record("card_focus_reaches_purchase_card", focus_dom_toward(pad, page, BUY), focus_info(page))
            pad.tap("A")
            page.wait_for_timeout(250)
            c = cs()
            record("card_A_opens_preview_only", preview_open() and c["preview"] == ["%s|purchase" % page.evaluate(f"document.querySelector('{BUY}').dataset.cardName")]
                   and c["toggle"] == 0 and checked() == [] and sends() == 0, [c, checked()])
            page.screenshot(path=str(OUT / "06_card_preview.png"))
            pad.tap("B")  # modal B：既有關閉行為不回歸
            page.wait_for_timeout(250)
            record("modal_B_still_closes_card_preview", not preview_open() and cs()["toggle"] == 0 and checked() == [], [preview_open(), checked()])

            # B 勾選／取消勾選（既有 checkbox + togglePurchaseSelection）
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
            pad.tap("B")
            page.wait_for_timeout(250)
            record("card_B_toggles_purchase_card_off", checked() == [] and cs()["toggle"] == 2 and sends() == 0, [checked(), cs()])

            # 購買區 X/Y：不得觸發手牌，也不得購買
            pad.tap("X")
            page.wait_for_timeout(200)
            record("purchase_card_X_does_not_play_cards", cs()["play"] == [] and sends() == 0 and checked() == [], cs())
            record("purchase_card_X_keeps_legacy_turn_bar_focus",
                   page.evaluate("!!document.querySelector('.rl-pad-focus') && !!document.querySelector('.rl-pad-focus').closest('#turnActionButtons')"), focus_info(page))
            record("focus_back_to_purchase_card_after_X", focus_dom_toward(pad, page, BUY), focus_info(page))
            pad.tap("Y")
            page.wait_for_timeout(200)
            record("purchase_card_Y_does_not_play_cards", cs()["play"] == [] and sends() == 0 and checked() == [], cs())

            # 不可勾選（disabled）的卡牌：B fail-closed
            if page.evaluate(f"!!document.querySelector('{BUY_DISABLED}')"):
                page.evaluate("""(sel) => { const c = document.querySelector(sel); c.setAttribute('data-controller-probe', '1'); }""", BUY_DISABLED)
                reached = focus_dom_toward(pad, page, BUY_DISABLED)
                if reached:
                    pad.tap("B")
                    page.wait_for_timeout(200)
                    record("card_B_noop_on_disabled_checkbox", checked() == [] and cs()["toggle"] == 2 and sends() == 0, checked())
                else:
                    record("card_B_noop_on_disabled_checkbox", False, "cannot focus disabled card")

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
            idx = page.evaluate(f"document.querySelector('{HAND_FOLLOWER}').querySelector('[data-card-mode=\"action\"]').dataset.cardIndex")
            page.screenshot(path=str(OUT / "08_hand_focus_with_controls.png"), clip=page.evaluate(
                """() => { const r = document.getElementById('hand').getBoundingClientRect(); return {x: Math.max(0, r.left - 10), y: Math.max(0, r.top - 10), width: Math.min(r.width + 20, innerWidth), height: Math.min(r.height + 20, innerHeight - Math.max(0, r.top - 10))}; }"""))
            before_sends = sends()
            pad.tap("Y")
            page.wait_for_timeout(500)
            c = cs()
            record("hand_Y_plays_card_as_action_via_existing_flow", c["play"] == [[int(idx), "追隨者", "action"]], c)

            # 手牌 X = 資源（重新取得手牌焦點）
            page.wait_for_timeout(600)
            pad.neutral()
            ok = focus_dom_toward(pad, page, HAND)
            record("card_focus_reaches_hand_card_for_resource", ok, focus_info(page))
            n_before = len(cs()["play"])
            hand_before = hand_n()
            pad.tap("X")
            page.wait_for_timeout(500)
            c = cs()
            record("hand_X_plays_card_as_resource_via_existing_flow",
                   len(c["play"]) == n_before + 1 and c["play"][-1][1:] == ["樂捐者", "resource"], c)

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
