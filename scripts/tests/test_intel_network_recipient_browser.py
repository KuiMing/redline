"""情報網 A 內鬥放置對象（1 至 3 位其他玩家）多選 picker 的 Browser（Playwright／Chromium）regression。

伺服器是真的 uvicorn（server.main:app，ENABLE_TEST_ROUTES=true，隨機埠；fixture 沿用 test_propagandist_joycon_browser），
真實的 index.html／app.js／controller_*.js。牌局由 /test/setup-intel-network-proof 準備（viewer＝自由派、手上 1 張情報網；
enemyA＝紅軍、enemyB、enemyC）。結果一律以伺服器權威 state（棄牌堆、手牌、pending choice）判斷。

本輪事件固定為無效果的歲月靜好（pin_noop_event）：Game() 初始化會隨機抽事件，偶爾抽到任務事件（如 紅軍權貴出逃）時，
前端首次 render 會自動打開全螢幕事件揭示 #eventRevealModal 擋住手牌點擊。固定事件後揭示每次都會出現，
各測試先用該輸入方式的既有 UI 語意關閉它（滑鼠點、觸控點、Joy-Con B），確認隱藏後才開始操作。

Joy-Con 是 mock bridge v2 WebSocket（synthetic frame，不是實體 Joy-Con）：roster 宣告本分頁擁有右手 OWNED。
未授權輸入＝本分頁沒有擁有的 FOREIGN 手把 frame，以及 v2 模式下的無身份舊版 frame；兩者都必須完全不影響畫面與伺服器。
（roster 只列 OWNED：起始畫面導覽在清單有兩支有訊號的手把時會刻意 release、不猜，那是既有行為，不在此測試範圍。）
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
import requests

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    MOCK_BRIDGE, app_url, browser, pad, settle, wait_until,
)

OWNED = "R24801-0a1b2c3d"
FOREIGN = "R24802-0badf00d"
UNTYPED = "untyped"
KEYS = {"A": (0, 0x08), "B": (0, 0x04), "Y": (0, 0x01)}
# controller_core.stickDirection：bridge 的 y > 0 是「下」。
STICK = {"right": (1, 0), "left": (-1, 0), "up": (0, -1), "down": (0, 1)}
OPTION_A = "在至多3位玩家棄牌堆各放入1張內鬥"
PICKER_KEY = "intel_network_internal_conflict_targets"

# bridge v2：第一筆訊息是 roster（本分頁擁有 OWNED），之後每 33ms 重送最後一筆 frame（帶 controller 身份；UNTYPED＝舊版無身份 frame）。
MOCK_BRIDGE_V2 = MOCK_BRIDGE.replace(
    "window.__padLast = [0, 0, 0, 0];",
    "window.__padLast = [0, 0, 0, 0, '__OWNED__'];",
).replace(
    "const [x, y, b0, b1] = window.__padLast;\n    live.onmessage({ data: JSON.stringify({ x, y, buttons: [b0, b1] }) });",
    "const [x, y, b0, b1, id] = window.__padLast;\n"
    "    if (!live.__roster) { live.__roster = true; live.onmessage({ data: JSON.stringify({ type: 'roster', v: 2, owned: '__OWNED__', "
    "controllers: [{ id: '__OWNED__', side: 'right', status: 'active', owner: 'you' }] }) }); }\n"
    "    live.onmessage({ data: JSON.stringify(id === 'untyped' ? { x, y, buttons: [b0, b1] }\n"
    "      : { type: 'frame', v: 2, controller: id, side: 'right', epoch: 1, x, y, buttons: [b0, b1] }) });",
).replace(
    "window.__padSend = (x, y, b0, b1) => { window.__padLast = [x, y, b0, b1]; return emit(); };",
    "window.__padSend = (x, y, b0, b1, id) => { window.__padLast = [x, y, b0, b1, id || '__OWNED__']; return emit(); };",
).replace("__OWNED__", OWNED).replace("__FOREIGN__", FOREIGN)
assert MOCK_BRIDGE_V2.count("type: 'roster'") == 1 and "window.__padLast = [x, y, b0, b1, id" in MOCK_BRIDGE_V2


def _evidence_dir(request):
    raw = request.config.getoption("--redline-evidence-dir") or os.environ.get("REDLINE_EVIDENCE_DIR")
    return Path(raw) if raw else None


def shot(request, page, name):
    target = _evidence_dir(request)
    if target:
        target.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target / f"intel-network-recipient-{name}.png"))


# ------------------------------------------------------------------ controller input（只送 bridge frame）

def send(page, x=0, y=0, b0=0, b1=0, controller=OWNED):
    page.evaluate(f"window.__padSend({x}, {y}, {b0}, {b1}, {json.dumps(controller)})")


def press(page, name, controller=OWNED, hold=0.12, after=0.45):
    index, mask = KEYS[name]
    buttons = [0, 0]
    buttons[index] = mask
    send(page, 0, 0, buttons[0], buttons[1], controller)
    time.sleep(hold)
    send(page, controller=controller)
    time.sleep(after)


def stick(page, direction, controller=OWNED, hold=0.15, after=0.4):
    x, y = STICK[direction]
    send(page, x, y, controller=controller)
    time.sleep(hold)
    send(page, controller=controller)
    time.sleep(after)


# ------------------------------------------------------------------ state helpers

def state(page):
    return page.evaluate("window.lastGameState")


def pending(page):
    return page.evaluate("window.lastGameState.pending_choice || null")


def discards(page):
    return {p["name"]: list(p["discard_pile"]) for p in state(page)["players"]}


def my_hand(page):
    return page.evaluate("(window.lastGameState.players || []).find(p => p.id === playerId).hand")


def picker_buttons(page):
    return page.evaluate("""[...document.querySelectorAll('#choiceModal .multi-target-choice')].map(b => ({
      name: b.textContent.trim(), pressed: b.getAttribute('aria-pressed') === 'true',
      selectedClass: b.classList.contains('divide-target-selected'), focus: b.classList.contains('rl-pad-focus') }))""")


def selected_names(page):
    return [b["name"] for b in picker_buttons(page) if b["pressed"]]


def confirm_state(page):
    return page.evaluate("""(() => { const b = document.getElementById('choiceMultiTargetConfirm');
      return b ? { text: b.textContent.trim(), disabled: b.disabled, focus: b.classList.contains('rl-pad-focus') } : null; })()""")


def focused_text(page):
    return page.evaluate("document.querySelector('.rl-pad-focus')?.textContent.trim() || null")


def focus_is_visible(page):
    """焦點框真的畫出來：.rl-pad-focus 在可見元素上且 outline 非 none。"""
    return page.evaluate("""(() => { const el = document.querySelector('.rl-pad-focus'); if (!el) return false;
      const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 3; })()""")


def picker_open(page):
    return page.evaluate("""(() => { const m = document.getElementById('choiceModal');
      return !!m && getComputedStyle(m).display !== 'none' && !!m.querySelector('.multi-target-choice'); })()""")


def event_reveal_open(page):
    return page.evaluate("""(() => { const m = document.getElementById('eventRevealModal');
      return !!m && getComputedStyle(m).display !== 'none'; })()""")


def acknowledge_event_reveal(page, via):
    """等開局的事件揭示出現（固定為歲月靜好），用該輸入方式的既有 UI 語意關閉，確認隱藏且不會被狀態推送重新打開。"""
    assert wait_until(lambda: event_reveal_open(page)), "event reveal did not open for the pinned round event"
    assert page.evaluate("document.getElementById('eventRevealModal').getAttribute('aria-label')") == "歲月靜好 放大檢視"
    if via == "mouse":
        page.click("#eventRevealModal")  # overlay onclick＝closeEventReveal（「點擊任意地方關閉」）
    elif via == "touch":
        page.tap("#eventRevealModal")
    elif via == "controller":
        assert wait_until(lambda: pad(page)["scope"] == "eventRevealModal"), pad(page)
        settle(page, "desktop")
        if not pad(page)["padActive"]:
            press(page, "B")  # 控制器第一次有效操作只放焦點、不執行：揭示必須仍開著
            assert pad(page)["padActive"] and event_reveal_open(page), pad(page)
            settle(page, "desktop")
        press(page, "B")  # MODAL_SCOPES：eventRevealModal 的 B＝點 overlay 本身
    else:
        raise AssertionError(via)
    assert wait_until(lambda: not event_reveal_open(page)), "event reveal still open after acknowledgement"
    page.evaluate("render(window.lastGameState)")  # 同一回合同一事件：重繪不能再打開揭示
    assert not event_reveal_open(page)
    assert pending(page) is None, pending(page)


def setup_game(page, app_url, via, **payload):
    setup = requests.post(app_url + "/test/setup-intel-network-proof",
                          json={"viewer_faction": "liberals", "pin_noop_event": True, **payload}, timeout=10).json()
    assert setup.get("success") and setup.get("player_id"), setup
    assert setup["state"]["current_event"]["name"] == "歲月靜好", setup["state"].get("current_event")
    page.evaluate(f"gameId = {json.dumps(setup['game_id'])}; playerId = {json.dumps(setup['player_id'])}; connect();")
    page.wait_for_function("window.lastGameState && (window.lastGameState.players || []).length > 0")
    if via == "controller":
        page.wait_for_function("window.RedlineController.getState().status === 'connected'")
    acknowledge_event_reveal(page, via)
    assert my_hand(page) == ["情報網"]


def open_game(browser, app_url, bridge=None):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    if bridge:
        ctx.add_init_script(bridge)
    else:
        ctx.add_init_script("window.__trustedPointer = 0;")
    page = ctx.new_page()
    page.goto(app_url + "/?display=desktop")
    setup_game(page, app_url, "controller" if bridge else "mouse",
               viewer_base="香港城", viewer_organizations={"香港城": 1},
               enemy_a_faction="red_army", enemy_a_base="北京", enemy_a_organizations={"北京": 1})
    return page


def assert_untouched(page):
    assert discards(page) == {"viewer": ["情報網"], "enemyA": [], "enemyB": [], "enemyC": []}


def open_picker_with_mouse(page):
    page.click('#hand .card[data-card-name="情報網"] .hand-card-action-btn[data-card-mode="action"]')
    wait_until(lambda: (pending(page) or {}).get("choice_key") == "choose_one")
    page.click(f'#choiceModalCards button:has-text("{OPTION_A}")')
    assert wait_until(lambda: (pending(page) or {}).get("choice_key") == PICKER_KEY and picker_open(page)), pending(page)


# ------------------------------------------------------------------ mouse／touch

def test_mouse_picker_selects_only_chosen_recipients(browser, app_url, request):
    page = open_game(browser, app_url)
    try:
        open_picker_with_mouse(page)
        assert page.evaluate("document.getElementById('choiceModalTitle').textContent") == "情報網"
        assert page.evaluate("document.getElementById('choiceModalDesc').textContent") == \
            "情報網：選擇 1 至 3 位其他玩家，各在其棄牌堆放入 1 張內鬥。"
        # 紅軍（enemyA）也是合法對象；不含自己。
        assert [b["name"] for b in picker_buttons(page)] == ["enemyA", "enemyB", "enemyC"]
        assert selected_names(page) == []
        assert confirm_state(page) == {"text": "確認選擇（0／3）", "disabled": True, "focus": False}
        assert page.evaluate("getComputedStyle(document.getElementById('closeChoiceModal')).display") != "none"
        # 選 A 當下伺服器沒有放任何內鬥。
        assert_untouched(page)

        page.click('#choiceModal .multi-target-choice:has-text("enemyA")')
        page.click('#choiceModal .multi-target-choice:has-text("enemyB")')
        page.click('#choiceModal .multi-target-choice:has-text("enemyB")')  # 再點一次＝取消勾選
        page.click('#choiceModal .multi-target-choice:has-text("enemyC")')
        assert selected_names(page) == ["enemyA", "enemyC"]
        assert all(b["selectedClass"] == b["pressed"] for b in picker_buttons(page))
        assert confirm_state(page)["text"] == "確認選擇（2／3）" and not confirm_state(page)["disabled"]

        # 狀態推送重繪 modal 時保留同一個 choice 的勾選。
        page.evaluate("render(window.lastGameState)")
        assert selected_names(page) == ["enemyA", "enemyC"]
        assert_untouched(page)
        shot(request, page, "mouse-two-selected")

        page.click("#choiceMultiTargetConfirm")
        assert wait_until(lambda: pending(page) is None)
        assert discards(page) == {"viewer": ["情報網"], "enemyA": ["內鬥"], "enemyB": [], "enemyC": ["內鬥"]}
        assert not picker_open(page)
        log = state(page).get("action_log") or []
        assert [line.split("] ", 1)[1] for line in log[-4:]] == [
            "viewer played 情報網", "viewer resolved choose_one option 0",
            "enemyA gained 1 card(s): 內鬥", "enemyC gained 1 card(s): 內鬥",
        ]
    finally:
        page.context.close()


def test_mouse_max_three_cap_and_cancel_rolls_back(browser, app_url):
    page = open_game(browser, app_url)
    try:
        open_picker_with_mouse(page)
        for name in ("enemyA", "enemyB", "enemyC"):
            page.click(f'#choiceModal .multi-target-choice:has-text("{name}")')
        assert selected_names(page) == ["enemyA", "enemyB", "enemyC"]
        assert confirm_state(page)["text"] == "確認選擇（3／3）"
        page.click("#closeChoiceModal")  # 取消＝整張牌退回手牌（與 B 選項的瓦解目標取消相同）
        assert wait_until(lambda: pending(page) is None)
        assert my_hand(page) == ["情報網"]
        assert discards(page) == {"viewer": [], "enemyA": [], "enemyB": [], "enemyC": []}
        assert not picker_open(page)
    finally:
        page.context.close()


def test_touch_tap_selects_and_confirms(browser, app_url):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720}, has_touch=True)
    page = ctx.new_page()
    try:
        page.goto(app_url + "/?display=desktop")
        setup_game(page, app_url, "touch")
        page.tap('#hand .card[data-card-name="情報網"] .hand-card-action-btn[data-card-mode="action"]')
        wait_until(lambda: (pending(page) or {}).get("choice_key") == "choose_one")
        page.tap(f'#choiceModalCards button:has-text("{OPTION_A}")')
        assert wait_until(lambda: picker_open(page))
        page.tap('#choiceModal .multi-target-choice:has-text("enemyB")')
        page.tap("#choiceMultiTargetConfirm")
        assert wait_until(lambda: pending(page) is None)
        assert discards(page) == {"viewer": ["情報網"], "enemyA": [], "enemyB": ["內鬥"], "enemyC": []}
    finally:
        ctx.close()


# ------------------------------------------------------------------ Joy-Con（bridge v2，本分頁擁有 OWNED）

def open_picker_with_controller(page, hold_a_into_picker=False):
    """只用 controller：關閉事件揭示後焦點回到手牌情報網 → Y 行動 → 選項 modal 預設焦點在 A 選項 → A 選擇。"""
    settle(page, "desktop")
    # open_game 已用 B 關閉事件揭示（控制器已啟用）；焦點還原到頁面預設＝手牌情報網，不需要再「第一下放焦點」。
    assert pad(page)["padActive"] and pad(page)["scope"] == "page", pad(page)
    assert wait_until(lambda: (pad(page)["focusSig"] or "").startswith("DIV||hand|情報網")), pad(page)
    settle(page, "desktop")
    press(page, "Y")
    assert wait_until(lambda: (pending(page) or {}).get("choice_key") == "choose_one")
    assert wait_until(lambda: pad(page)["scope"] == "choiceModal")
    settle(page, "desktop")
    assert wait_until(lambda: focused_text(page) == OPTION_A), focused_text(page)
    assert focus_is_visible(page)
    if hold_a_into_picker:
        index, mask = KEYS["A"]
        send(page, 0, 0, mask, 0)  # 按下 A 不放：選擇 A 選項後 picker 出現時 A 仍按住
        assert wait_until(lambda: (pending(page) or {}).get("choice_key") == PICKER_KEY and picker_open(page))
        time.sleep(1.2)  # 按住期間 frame 每 33ms 重送
        assert selected_names(page) == [], "held A must not toggle a recipient in the newly opened picker"
        assert (pending(page) or {}).get("choice_key") == PICKER_KEY
        send(page)  # 放開
        time.sleep(0.5)
        assert selected_names(page) == []
    else:
        press(page, "A")
        assert wait_until(lambda: (pending(page) or {}).get("choice_key") == PICKER_KEY and picker_open(page))
    assert wait_until(lambda: pad(page)["scope"] == "choiceModal")
    settle(page, "desktop")
    assert_untouched(page)


def test_joycon_selects_two_recipients_with_visible_focus_and_held_a_safety(browser, app_url, request):
    page = open_game(browser, app_url, MOCK_BRIDGE_V2)
    try:
        open_picker_with_controller(page, hold_a_into_picker=True)
        # 預設焦點：第一位對象（確認鈕停用時不可聚焦）。
        assert wait_until(lambda: focused_text(page) == "enemyA"), focused_text(page)
        assert focus_is_visible(page)
        press(page, "A")
        assert selected_names(page) == ["enemyA"]
        stick(page, "right")
        assert focused_text(page) == "enemyB" and focus_is_visible(page)
        stick(page, "right")
        assert focused_text(page) == "enemyC"
        press(page, "A")
        assert selected_names(page) == ["enemyA", "enemyC"]
        stick(page, "left")
        press(page, "A")  # 勾選 enemyB
        press(page, "A")  # 再按一次取消 enemyB
        assert selected_names(page) == ["enemyA", "enemyC"]
        shot(request, page, "joycon-two-selected")
        assert_untouched(page)
        stick(page, "down")
        assert confirm_state(page) == {"text": "確認選擇（2／3）", "disabled": False, "focus": True}, focused_text(page)
        assert focus_is_visible(page)
        press(page, "A")
        assert wait_until(lambda: pending(page) is None)
        assert discards(page) == {"viewer": ["情報網"], "enemyA": ["內鬥"], "enemyB": [], "enemyC": ["內鬥"]}
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()


def test_joycon_b_backs_out_with_full_rollback_and_never_submits(browser, app_url):
    page = open_game(browser, app_url, MOCK_BRIDGE_V2)
    try:
        open_picker_with_controller(page)
        assert wait_until(lambda: focused_text(page) == "enemyA")
        press(page, "A")
        assert selected_names(page) == ["enemyA"]
        press(page, "B")  # B＝既有「取消」：伺服器 cancel_choice，整張牌退回手牌，不放任何內鬥
        assert wait_until(lambda: pending(page) is None)
        assert not picker_open(page)
        assert my_hand(page) == ["情報網"]
        assert discards(page) == {"viewer": [], "enemyA": [], "enemyB": [], "enemyC": []}
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()


def test_joycon_cannot_confirm_empty_selection(browser, app_url):
    page = open_game(browser, app_url, MOCK_BRIDGE_V2)
    try:
        open_picker_with_controller(page)
        assert wait_until(lambda: focused_text(page) == "enemyA")
        stick(page, "down")  # 確認鈕停用（0 位）→ 不可聚焦；焦點只會落在可用控制上
        assert not confirm_state(page)["focus"]
        assert confirm_state(page)["disabled"] is True
        assert focused_text(page) in {"enemyA", "enemyB", "enemyC", "取消"}
        assert (pending(page) or {}).get("choice_key") == PICKER_KEY
        assert_untouched(page)
    finally:
        page.context.close()


def test_unauthorized_controller_frames_are_ignored_in_picker(browser, app_url):
    page = open_game(browser, app_url, MOCK_BRIDGE_V2)
    try:
        open_picker_with_controller(page)
        assert wait_until(lambda: focused_text(page) == "enemyA")
        before_focus = pad(page)["focusSig"]
        before_choice = pending(page)
        # 本分頁沒有擁有的 FOREIGN 與無身份舊版 frame：A、方向、B 都不能改焦點、勾選、送出或取消。
        for controller in (FOREIGN, UNTYPED):
            press(page, "A", controller=controller)
            stick(page, "right", controller=controller)
            press(page, "A", controller=controller)
            press(page, "B", controller=controller)
        send(page)  # 回到 OWNED 的中立 frame
        time.sleep(0.4)
        assert selected_names(page) == []
        assert pad(page)["focusSig"] == before_focus
        assert picker_open(page)
        assert pending(page)["choice_id"] == before_choice["choice_id"]
        assert_untouched(page)
        # 擁有者的 A 照常運作。
        settle(page, "desktop")
        press(page, "A")
        assert selected_names(page) == ["enemyA"]
    finally:
        page.context.close()
