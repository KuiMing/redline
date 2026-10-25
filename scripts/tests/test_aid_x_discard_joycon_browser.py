"""Joy-Con 手牌 X：一般奧援＝既有「棄置」（危險確認）；其他手牌＝資源；B 不再棄置。Browser（Playwright／Chromium）regression。

伺服器是真的 uvicorn（server.main:app，ENABLE_TEST_ROUTES=true，隨機埠，測試結束即關閉；harness 與
test_propagandist_joycon_browser 共用）。牌局由 /test/setup-remove-to-purchase＋/test/set-hand 準備（行動階段）。
Joy-Con 是 mock bridge WebSocket；遊戲操作只透過 controller frame，trusted pointer 計數為 0。
棄置是否發生以伺服器權威 state（手牌、資源）判斷：確認單開著／取消時手牌與資源都不變；另以包住既有 playHandCard
的紀錄確認控制器實際點了哪一顆既有按鈕（只記錄後照常呼叫原函式，不改送出流程）。
注意：/test/set-hand 對奧援卡名建立的是 command 型測試牌（不是 canonical support 牌），所以這裡不驗伺服器的奧援結算，
只驗控制器路由與「確認前不送出」。
"""
from __future__ import annotations

import time

import pytest

from test_propagandist_joycon_browser import (  # noqa: F401  (app_url／browser 是 pytest fixture)
    BITS, app_url, browser, dismiss_modals, me, open_game, pad, settle, stick, wait_until,
)

KEYS = {**BITS, "X": (0, 0x02), "R": (0, 0x40)}
AID = "歐洲奧援"


def press(page, name, hold=0.12, after=0.4):
    index, mask = KEYS[name]
    buttons = [0, 0]
    buttons[index] = mask
    page.evaluate(f"window.__padSend(0, 0, {buttons[0]}, {buttons[1]})")
    time.sleep(hold)
    page.evaluate("window.__padSend(0, 0, 0, 0)")
    time.sleep(after)


def spy_plays(page):
    page.evaluate("""(() => {
      if (window.__plays) return;
      window.__plays = [];
      const original = window.playHandCard;
      window.playHandCard = (...args) => { window.__plays.push(args.slice(0, 3)); return original(...args); };
    })()""")


def plays(page):
    return page.evaluate("window.__plays")


def resources(page):
    r = me(page).get("resources") or {}
    return (int(r.get("money", 0)), int(r.get("propaganda", 0)))


def hand(page):
    return list(me(page)["hand"])


def confirm_open(page):
    return page.evaluate("(() => { const m = document.getElementById('lrConfirmModal'); return !!m && m.style.display !== 'none'; })()")


def confirm_title(page):
    return page.evaluate("document.getElementById('lrConfirmTitle')?.textContent || ''")


def focused_button(page):
    return page.evaluate("document.querySelector('.rl-pad-focus')?.id || null")


def focused_card(page, display):
    s = pad(page)
    if display == "living-room":
        key = s["livingRoom"]["itemKey"] or ""
        return key.split(":", 2)[2] if key.startswith("hand:") else None
    sig = s["focusSig"] or ""
    return sig.split("|")[3] if sig.startswith("DIV||hand|") else None


def hint(page, display):
    if display == "living-room":
        return page.evaluate("document.getElementById('lrLegend')?.textContent || ''")
    return page.evaluate("document.getElementById('padHint')?.textContent || ''")


def focus_hand(page, display, name):
    """只用 controller：第一下放焦點（手牌第一張），客廳模式再按 A 進入手牌區。"""
    dismiss_modals(page)
    settle(page, display)
    if not pad(page)["padActive"]:
        press(page, "A")
    if display == "living-room":
        assert pad(page)["livingRoom"]["zone"] == "hand", pad(page)["livingRoom"]
        if pad(page)["livingRoom"]["layer"] == "zone":
            press(page, "A")
    assert focused_card(page, display) == name, pad(page)
    settle(page, display)


def handle_modal_settle(page, display):
    settle(page, display)
    time.sleep(0.3)  # 確認單開啟／關閉後的 250ms 執行冷卻


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_x_on_support_card_opens_confirm_and_only_confirm_discards(browser, app_url, display):
    page = open_game(browser, app_url, display, [AID, "資助者"])
    try:
        focus_hand(page, display, AID)
        spy_plays(page)
        assert page.evaluate(
            f"document.querySelector('#hand .card[data-card-name=\"{AID}\"] .hand-card-action-btn[data-card-mode=\"resource\"]').textContent.trim()"
        ) == "棄置"
        before_hand, before_res = hand(page), resources(page)
        text = hint(page, display)
        assert "棄置" in text and "X" in text and "X 資源" not in text and "B 棄置" not in text, text
        if display == "living-room":
            hints = {h["id"]: h for h in pad(page)["livingRoom"]["hints"]}
            assert hints["cardDiscard"]["key"] == "X" and hints["cardDiscard"]["danger"], hints
            assert AID in hints["cardDiscard"]["label"] and "cardResource" not in hints, hints
            assert not any(h["key"] == "B" and "棄置" in h["label"] for h in hints.values()), hints

        # B 不再是棄置快捷鍵：不開確認單、不棄牌、焦點留在原卡。
        press(page, "B")
        time.sleep(0.5)
        assert not confirm_open(page)
        assert hand(page) == before_hand and resources(page) == before_res and plays(page) == []
        assert focused_card(page, display) == AID, pad(page)

        # X → 危險確認單（預設焦點＝返回），確認前不棄牌。
        settle(page, display)
        press(page, "X")
        assert wait_until(lambda: confirm_open(page), timeout=3), pad(page)
        assert confirm_title(page) == f"確認：棄置 {AID}", confirm_title(page)
        assert wait_until(lambda: focused_button(page) == "lrConfirmCancelBtn", timeout=3), pad(page)
        time.sleep(0.6)
        assert hand(page) == before_hand and resources(page) == before_res and plays(page) == []

        # modal scope：確認單開著時 X／R 不作用（不換分頁、不再送任何東西）。
        handle_modal_settle(page, display)
        press(page, "X")
        press(page, "R")
        assert confirm_open(page) and pad(page)["scope"] == "lrConfirmModal", pad(page)
        assert page.evaluate("document.querySelector('.game-tab.active')?.dataset.view") == "command"
        assert hand(page) == before_hand and resources(page) == before_res and plays(page) == []

        # 取消一：B（既有「返回」）。
        handle_modal_settle(page, display)
        press(page, "B")
        assert wait_until(lambda: not confirm_open(page), timeout=3)
        time.sleep(0.5)
        assert hand(page) == before_hand and resources(page) == before_res and plays(page) == []

        # 取消二：預設焦點「返回」上按 A。
        handle_modal_settle(page, display)
        assert focused_card(page, display) == AID, pad(page)
        press(page, "X")
        assert wait_until(lambda: confirm_open(page), timeout=3)
        handle_modal_settle(page, display)
        press(page, "A")
        assert wait_until(lambda: not confirm_open(page), timeout=3)
        time.sleep(0.5)
        assert hand(page) == before_hand and resources(page) == before_res and plays(page) == []

        # 確認：右移到「確認」再按 A → 既有「棄置」鈕 → 伺服器棄牌（不獲得資源）。
        handle_modal_settle(page, display)
        assert focused_card(page, display) == AID, pad(page)
        press(page, "X")
        assert wait_until(lambda: confirm_open(page), timeout=3)
        handle_modal_settle(page, display)
        stick(page, "right")
        assert focused_button(page) == "lrConfirmOkBtn", pad(page)
        handle_modal_settle(page, display)
        press(page, "A", after=0.2)
        assert wait_until(lambda: AID not in hand(page), timeout=5), (hand(page), pad(page))
        assert not confirm_open(page)
        assert hand(page) == ["資助者"] and resources(page) == before_res, (hand(page), resources(page))
        assert plays(page) == [[0, AID, "resource"]], plays(page)  # 確認後才點一次既有「棄置」鈕（data-card-mode=resource）
        assert page.evaluate("window.__trustedPointer") == 0, "game was operated with the mouse"
    finally:
        page.context.close()


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_x_on_ordinary_card_still_uses_resource(browser, app_url, display):
    page = open_game(browser, app_url, display, ["資助者", AID])
    try:
        focus_hand(page, display, "資助者")
        spy_plays(page)
        text = hint(page, display)
        assert "X 資源" in text and "棄置" not in text, text
        money, propaganda = resources(page)
        press(page, "X", after=0.2)
        assert wait_until(lambda: "資助者" not in hand(page), timeout=5), (hand(page), pad(page))
        assert not confirm_open(page)
        assert resources(page) == (money + 2, propaganda), resources(page)
        assert hand(page) == [AID] and plays(page) == [[0, "資助者", "resource"]], plays(page)
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_red_army_support_is_never_routed_to_discard(browser, app_url, display):
    page = open_game(browser, app_url, display, ["紅軍奧援", "資助者"])
    try:
        focus_hand(page, display, "紅軍奧援")
        spy_plays(page)
        label = page.evaluate(
            "document.querySelector('#hand .card[data-card-name=\"紅軍奧援\"] .hand-card-action-btn[data-card-mode=\"resource\"]').textContent.trim()"
        )
        assert label == "資源", label
        text = hint(page, display)
        assert "棄置" not in text and "X 資源" in text, text
        if display == "living-room":
            assert "cardDiscard" not in {h["id"] for h in pad(page)["livingRoom"]["hints"]}
        press(page, "X", after=0.2)
        time.sleep(1.0)
        assert not confirm_open(page), "紅軍奧援 must never open the discard confirm"
        # X＝既有「資源」鈕（紅軍奧援的 resource 位標示「資源」），不走棄置確認；結算由伺服器依合法性決定。
        assert plays(page) == [[0, "紅軍奧援", "resource"]], plays(page)
        if display == "living-room":
            assert (pad(page)["livingRoom"]["lastCommand"] or {}).get("cmd") == "cardMode", pad(page)["livingRoom"]
        assert page.evaluate("window.__trustedPointer") == 0
    finally:
        page.context.close()


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
def test_help_and_legends_never_advertise_b_discard(browser, app_url, display):
    page = open_game(browser, app_url, display, [AID])
    try:
        focus_hand(page, display, AID)
        texts = page.evaluate(
            "[...document.querySelectorAll('#padPanel .pad-note, #lrHelp, #lrLegend, #lrHints, #padHint')].map(e => e.textContent).join('\\n')"
        )
        for banned in ("B 棄置", "B ⚠ 棄置", "奧援手牌＝棄置（⚠ 需確認）；地圖"):
            assert banned not in texts, (banned, texts)
        assert "一般奧援" in texts, texts
    finally:
        page.context.close()


@pytest.mark.parametrize("display", ["desktop"])  # 產品只保留桌面模式
@pytest.mark.parametrize("variant", ["disabled", "hidden"])
def test_x_fails_closed_when_discard_control_is_not_usable(browser, app_url, display, variant):
    """既有「棄置」鈕停用／隱藏：X 不開確認單、不改走資源、不送出（canonical 控制可見且啟用才算）。"""
    page = open_game(browser, app_url, display, [AID])
    try:
        focus_hand(page, display, AID)
        spy_plays(page)
        btn = f"document.querySelector('#hand .card[data-card-name=\"{AID}\"] .hand-card-action-btn[data-card-mode=\"resource\"]')"
        page.evaluate(f"{btn}.disabled = true" if variant == "disabled" else f"{btn}.style.display = 'none'")
        settle(page, display)
        before_hand, before_res = hand(page), resources(page)
        press(page, "X")
        time.sleep(0.6)
        assert not confirm_open(page) and plays(page) == [], (plays(page), pad(page))
        assert hand(page) == before_hand and resources(page) == before_res
    finally:
        page.context.close()
