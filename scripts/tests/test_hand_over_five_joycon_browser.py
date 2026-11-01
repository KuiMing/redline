"""手牌超過可視張數（8 張）時，桌面模式 Joy-Con 方向導航、捲動與 X／Y 對應實際焦點卡的 Browser（Playwright／Chromium）regression。

伺服器是真的 uvicorn（server.main:app，ENABLE_TEST_ROUTES=true，隨機埠，測試結束即關閉；harness 與
test_propagandist_joycon_browser 共用）。牌局由 /test/setup-remove-to-purchase＋/test/set-hand 準備（行動階段）。
Joy-Con 是 mock bridge WebSocket（舊版 frame 協定，不是實體硬體）；遊戲操作只透過 controller frame，trusted pointer 計數為 0。
產品只保留桌面模式，所以這裡只測桌面模式。

根因：手牌每次 render 都整列重建（每一份伺服器 state 與地圖 iframe 的 redline-map-state 同步都會觸發），
桌面控制器以 sigOf 重新綁定焦點；手牌卡 div 沒有位置資訊，同名手牌的 sig 完全相同，所以第 6 張之後的
同名卡（例如第 7 張「追隨者」與第 1 張同名）一次重繪就被綁回第一張、#hand 也被捲回最左邊，
之後的 A／X／Y 都作用在前段那張卡上。卡牌 preview 關閉後的焦點記憶同樣只靠 sig，一樣會跳回前段。
"""
from __future__ import annotations

import time

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    BITS, app_url, browser, dismiss_modals, me, open_game, pad, settle, stick, wait_until,
)

KEYS = {**BITS, "X": (0, 0x02)}
# 第 7、8 張與第 1、2 張同名；第 6 張（資助者）只出現一次。1280×720 的手牌區放得下 6 張，第 7、8 張超出可視區。
HAND = ["追隨者", "樂捐者", "宣傳家", "思想家", "歐洲奧援", "資助者", "追隨者", "樂捐者"]

FOCUS = """(() => {
  const h = document.getElementById('hand');
  const hr = h.getBoundingClientRect();
  const cards = [...h.querySelectorAll('.card[data-card-zone="hand"]')];
  const focused = cards.filter(c => c.classList.contains('rl-pad-focus'));
  const el = focused[0] || null;
  const r = el ? el.getBoundingClientRect() : null;
  const s = window.RedlineController.getState();
  return {
    count: cards.length, focusedCount: focused.length,
    index: el ? cards.indexOf(el) : null, cardIndex: el ? el.dataset.cardIndex ?? null : null, name: el ? el.dataset.cardName : null,
    sig: s.focusSig, kind: s.focusKind, scope: s.scope, scrollLeft: h.scrollLeft,
    inside: !!r && r.left >= hr.left - 1 && r.right <= hr.right + 1,
    clipped: cards.map(c => { const cr = c.getBoundingClientRect(); return cr.right > hr.right + 1 || cr.left < hr.left - 1; }),
  };
})()"""


def press(page, name, hold=0.12, after=0.4):
    index, mask = KEYS[name]
    buttons = [0, 0]
    buttons[index] = mask
    page.evaluate(f"window.__padSend(0, 0, {buttons[0]}, {buttons[1]})")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def focus(page):
    return page.evaluate(FOCUS)


def sig_index(state):
    """桌面焦點 sig：DIV||hand|<名稱>||<手牌位置>|...；回傳位置（字串）。"""
    parts = (state["sig"] or "").split("|")
    return parts[5] if len(parts) > 5 and parts[2] == "hand" else None


def hand(page):
    return list(me(page)["hand"])


def resources(page):
    r = me(page).get("resources") or {}
    return (int(r.get("money", 0)), int(r.get("propaganda", 0)))


def spy_plays(page):
    page.evaluate("""(() => {
      if (window.__plays) return;
      window.__plays = [];
      const original = window.playHandCard;
      window.playHandCard = (...args) => { window.__plays.push(args.slice(0, 3)); return original(...args); };
    })()""")


def plays(page):
    return page.evaluate("window.__plays")


def assert_identity(st, index):
    """焦點卡的穩定識別：卡牌 div 的 data-card-index 與控制器 sig 都是它的伺服器手牌位置。"""
    assert st["cardIndex"] == str(index) and sig_index(st) == str(index), (index, st)


def assert_focus(page, index, names):
    st = focus(page)
    assert st["kind"] == "dom" and st["focusedCount"] == 1, st
    assert st["index"] == index and st["name"] == names[index], (index, st)
    assert_identity(st, index)
    assert st["inside"], ("focused card must be scrolled fully into the hand container", st)
    return st


def focus_first_card(page):
    dismiss_modals(page)
    settle(page, "desktop")
    if not pad(page)["padActive"]:
        press(page, "A")  # 第一下只放焦點（指揮中心預設＝第一張手牌）
    settle(page, "desktop")
    return assert_focus(page, 0, HAND)


def walk_to(page, target, names):
    """只用搖桿左右逐張移到 target；每一步都必須正好移動一張。"""
    for _ in range(len(names)):
        current = focus(page)["index"]
        if current == target:
            return assert_focus(page, target, names)
        stick(page, "right" if target > current else "left")
        assert focus(page)["index"] == current + (1 if target > current else -1), (current, focus(page))
    return assert_focus(page, target, names)


def rerender_via_render(page):
    """與每一份伺服器 state 相同的 render()（ws.onmessage 也是呼叫它）：整列重建手牌。"""
    page.evaluate("render(window.lastGameState)")


def rerender_via_map_sync(page):
    """地圖 iframe 的 state 同步路徑（window message：redline-map-state → render）。"""
    page.evaluate("window.postMessage({ type: 'redline-map-state', state: window.lastGameState }, window.location.origin)")


def test_stick_reaches_every_card_beyond_five_and_back(browser, app_url):
    page = open_game(browser, app_url, "desktop", HAND)
    try:
        st = focus_first_card(page)
        assert st["count"] == 8 and st["scrollLeft"] == 0, st
        # 前提：第 7、8 張被手牌容器裁掉（overflow），但仍必須在 controller 焦點集合內（以下靠搖桿可到達證明）。
        assert st["clipped"][6] and st["clipped"][7], st

        scroll = [st["scrollLeft"]]
        for k in range(1, 8):
            stick(page, "right")
            st = assert_focus(page, k, HAND)
            scroll.append(st["scrollLeft"])
        assert scroll[6] > scroll[5] and scroll[7] > scroll[6], ("hand container must scroll for cards 7 and 8", scroll)
        stick(page, "right")  # 最後一張再往右：不循環、不跳區
        assert_focus(page, 7, HAND)

        for k in range(6, -1, -1):
            stick(page, "left")
            assert_focus(page, k, HAND)
        assert focus(page)["scrollLeft"] == 0, focus(page)
        assert page.evaluate("window.__trustedPointer") == 0, "game was operated with the mouse"
    finally:
        page.context.close()


def test_focus_on_late_duplicate_card_survives_rerender_and_preview(browser, app_url):
    page = open_game(browser, app_url, "desktop", HAND)
    try:
        focus_first_card(page)
        st = walk_to(page, 6, HAND)  # 第 7 張「追隨者」，與第 1 張同名
        scrolled = st["scrollLeft"]
        assert scrolled > 0, st

        for rerender in (rerender_via_render, rerender_via_map_sync, rerender_via_render):
            rerender(page)
            time.sleep(0.3)
            settle(page, "desktop")
            st = assert_focus(page, 6, HAND)
            assert st["scrollLeft"] == scrolled, ("re-render must keep the hand scroll position", scrolled, st)

        # 重繪後、reconcile（80ms）之前立刻輸入：方向仍從實際焦點卡出發。
        rerender_via_render(page)
        stick(page, "right")
        assert_focus(page, 7, HAND)
        rerender_via_render(page)
        stick(page, "left")
        assert_focus(page, 6, HAND)

        # A＝既有卡牌預覽；B 關閉後焦點記憶回到同一張（第 7 張），不是同名的第 1 張。
        settle(page, "desktop")
        press(page, "A")
        assert wait_until(lambda: pad(page)["scope"] == "cardPreviewModal", timeout=3), pad(page)
        assert "追隨者" in (page.evaluate("document.getElementById('cardPreviewModal').getAttribute('aria-label')") or "")
        rerender_via_render(page)  # 預覽開著時又來一份 state
        time.sleep(0.3)
        settle(page, "desktop")
        press(page, "B")
        assert wait_until(lambda: pad(page)["scope"] == "page", timeout=3), pad(page)
        settle(page, "desktop")
        assert_focus(page, 6, HAND)
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()


def test_x_and_y_act_on_the_actually_focused_late_card(browser, app_url):
    page = open_game(browser, app_url, "desktop", HAND)
    try:
        focus_first_card(page)
        spy_plays(page)

        # 第 7 張（同名於第 1 張）：重繪後 X → 既有「資源」鈕，data-card-index 6；伺服器移除的是第 7 張。
        walk_to(page, 6, HAND)
        rerender_via_render(page)
        time.sleep(0.3)
        settle(page, "desktop")
        assert "X 資源" in page.evaluate("document.getElementById('padHint')?.textContent || ''")
        press(page, "X", after=0.2)
        assert wait_until(lambda: len(hand(page)) == 7, timeout=5), (hand(page), pad(page))
        assert plays(page) == [[6, "追隨者", "resource"]], plays(page)
        after_first = HAND[:6] + HAND[7:]
        assert hand(page) == after_first, hand(page)

        # 第 6 張（資助者，在第 5 張之後）：X 作用在它上面（+2 資金），第 5 張（歐洲奧援）不受影響、不開棄置確認。
        time.sleep(0.4)
        settle(page, "desktop")
        walk_to(page, 5, after_first)
        money, propaganda = resources(page)
        press(page, "X", after=0.2)
        assert wait_until(lambda: "資助者" not in hand(page), timeout=5), (hand(page), pad(page))
        assert plays(page)[-1] == [5, "資助者", "resource"], plays(page)
        assert resources(page) == (money + 2, propaganda), resources(page)
        after_second = after_first[:5] + after_first[6:]
        assert hand(page) == after_second and "歐洲奧援" in hand(page), hand(page)
        assert page.evaluate("(() => { const m = document.getElementById('lrConfirmModal'); return !!m && m.style.display !== 'none'; })()") is False

        # 最後一張（第 6 張「樂捐者」，與第 2 張同名）：Y → 既有「行動」鈕，index 5，不是第 2 張的 index 1。
        time.sleep(0.4)
        settle(page, "desktop")
        walk_to(page, 5, after_second)
        rerender_via_map_sync(page)
        time.sleep(0.3)
        settle(page, "desktop")
        assert_focus(page, 5, after_second)
        press(page, "Y", after=0.3)
        assert wait_until(lambda: len(plays(page)) == 3, timeout=3), plays(page)
        assert plays(page)[-1] == [5, "樂捐者", "action"], plays(page)
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()
