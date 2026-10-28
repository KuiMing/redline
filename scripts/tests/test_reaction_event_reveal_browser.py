"""取消反應（爆料黑幕／產業滲透／情報網）不可自動揭示事件卡 — Browser（Playwright／Chromium）regression。

2026-10-27 playtest：對手的卡牌或陣營能力觸發取消反應時，前端先自動打開資訊用的事件卡揭示 #eventRevealModal，
擋在可操作的取消反應視窗上（MODAL_SCOPES 中 eventRevealModal 高於 choiceModal，Joy-Con 焦點也被它拿走）。
根因：揭示只以記憶體中的事件 key 判斷，客廳輪流換席位整頁重新載入後，反應者的分頁與反應結束後交回行動者的分頁
都把同一張事件卡當新事件再揭示。修正見 static/event_reveal_core.js。

伺服器是同一 process 的真 uvicorn（取消反應逾時拉長，結果一定來自玩家輸入）；Joy-Con 是真的 bridge app＋fixture 封包
（synthetic，**不是實體 Joy-Con**）。每一步以伺服器權威狀態與實際 DOM（computed style、.rl-pad-focus、elementFromPoint）判斷。
"""
from __future__ import annotations

import time

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")

from hotseat_table_harness import (  # noqa: E402,F401  (server_url 是 pytest fixture)
    HotSeatTable, nav, press, server_url, shot, stays, wait_until,
)
from test_start_flow_browser import FakeJoyCons  # noqa: E402

P1_PORT, P2_PORT = 24801, 24803  # 兩支左 Joy-Con（fixture A／B／左搖桿）
# card：P1（臺灣）打出行動卡「領導」，P2（真人紅軍）手上有取消牌。ability：P2（紅軍）發動「統戰部」，P1 手上有取消牌。
CASES = [
    ("card", "爆料黑幕", "decline"),
    ("card", "產業滲透", "cancel"),
    ("card", "情報網", "cancel"),
    ("ability", "爆料黑幕", "cancel"),
    ("ability", "產業滲透", "decline"),
    ("ability", "情報網", "decline"),
]


@pytest.fixture(scope="module")
def joycons(server_url):
    fake = FakeJoyCons(server_url)
    yield fake
    fake.close()


@pytest.fixture(scope="module")
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - environment without Chromium
            pytest.skip(f"chromium unavailable: {exc}")
        yield b
        b.close()


def reveal_displayed(table):
    """#eventRevealModal 的 computed display（不是只被交接遮罩蓋住）。"""
    return table.page.evaluate("() => getComputedStyle(document.getElementById('eventRevealModal')).display !== 'none'")


def reaction_buttons(table):
    return table.page.evaluate("""() => [...document.querySelectorAll('#choiceModal .reaction-choice-actions button')].map(b => ({
      text: b.textContent.trim(), focus: b.classList.contains('rl-pad-focus'),
      onTop: (() => { const r = b.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return !!hit && (hit === b || b.contains(hit)); })() }))""")


def reaction_prompt_open(table):
    return table.shown("choiceModal") and bool(reaction_buttons(table))


def acknowledge_normal_reveal(table, port):
    """一般流程（沒有反應）：開局揭示照常出現；用該席自己的 Joy-Con B 關閉（第一下只放焦點）。"""
    assert wait_until(lambda: table.shown("eventRevealModal"), 10.0), "normal event reveal did not open"
    assert table.page.evaluate("() => document.getElementById('eventRevealModal').getAttribute('aria-label')") == "歲月靜好 放大檢視"
    for _ in range(3):
        if not table.shown("eventRevealModal"):
            break
        press(table.fake, port, "B")
    assert wait_until(lambda: not table.shown("eventRevealModal"), 5.0)


def scenario(table, path, card):
    """回傳 (actor, reactor, trigger)。"""
    actor, reactor = ("P1", "P2") if path == "card" else ("P2", "P1")
    table.pin_noop_event()
    table.set_turn(actor)
    a, r = table.player(actor), table.player(reactor)
    a.hand = [table.card("領導")] if path == "card" else []
    a.deck.draw_pile = [table.card("領導")]
    r.hand = [table.card(card)]
    r.deck.draw_pile = [table.card("領導")]
    r.deck.discard_pile = []
    if path == "card":
        trigger = {"action": "play_card", "index": 0, "mode": "action"}
    else:
        trigger = {"action": "faction_action", "name": "統戰部"}
    return actor, reactor, trigger


CARD_IDS = {"爆料黑幕": "exposure", "產業滲透": "infiltration", "情報網": "intel"}


@pytest.mark.parametrize("path,card,outcome", CASES, ids=[f"{p}-{CARD_IDS[c]}-{o}" for p, c, o in CASES])
def test_reaction_prompt_is_the_only_auto_modal_and_event_reveal_never_follows(server_url, browser, joycons, request, path, card, outcome):
    table = HotSeatTable(server_url, browser, joycons, factions=("taiwan_green", "red_army"), ports=(P1_PORT, P2_PORT),
                         device=f"rx-{path}-{outcome}")
    try:
        actor, reactor, trigger = scenario(table, path, card)
        aport, rport = table.by_name[actor]["port"], table.by_name[reactor]["port"]
        reactor_pid = table.by_name[reactor]["player_id"]
        table.open(actor)
        table.hand_to(actor)
        # 不相關的一般流程：行動者自己的回合開始，事件揭示照常自動出現（保留既有行為）。
        acknowledge_normal_reveal(table, aport)

        # 行動者觸發可取消的卡牌／陣營能力（行動者自己的遊戲連線）。
        table.socks[actor].send(trigger)
        choice = table.game.pending_choice or {}
        assert choice.get("type") == "reaction_choice" and choice.get("player_id") == reactor_pid, choice
        assert [c["name"] for c in choice.get("cards") or []] == [card]
        # 行動者分頁：交接給反應者；揭示在遮罩下也不可被打開。
        table.wait_handoff(reactor)
        assert stays(lambda: not reveal_displayed(table), 1.0)

        # 反應者用自己的 Joy-Con 接手（整頁重新載入成反應者）。
        table.hand_to(reactor)
        assert wait_until(lambda: reaction_prompt_open(table), 10.0), "reaction prompt did not open"
        # 唯一的自動 modal：揭示在整段期間都沒有出現（不是延後）。
        assert stays(lambda: not reveal_displayed(table) and reaction_prompt_open(table), 2.0)
        table.page.evaluate("() => render(window.lastGameState)")  # 同一狀態重繪也不揭示
        assert stays(lambda: not reveal_displayed(table), 0.6)
        buttons = reaction_buttons(table)
        assert [b["text"] for b in buttons] == ["是", "否"], buttons
        assert all(b["onTop"] for b in buttons), f"reaction buttons covered by another overlay: {buttons}"  # 滑鼠可直接點到
        assert table.page.evaluate("() => document.getElementById('choiceModalTitle')?.textContent || document.querySelector('#choiceModal .modal-title-text')?.textContent || ''").find(card) >= 0
        st = table.ctl()
        assert st["scope"] == "choiceModal", st["scope"]
        assert table.owned() == table.by_name[reactor]["controller"]
        # 行動者的 Joy-Con 不能代替反應者操作。
        press(joycons, aport, "A")
        assert (table.game.pending_choice or {}).get("type") == "reaction_choice"
        # 反應者 Joy-Con：第一下只放焦點，落在反應視窗（是）；B 不能關掉必答的反應視窗。
        press(joycons, rport, "B")
        assert wait_until(lambda: any(b["focus"] for b in reaction_buttons(table)), 3.0), reaction_buttons(table)
        assert [b["text"] for b in reaction_buttons(table) if b["focus"]] == ["是"]
        press(joycons, rport, "B")
        assert reaction_prompt_open(table) and (table.game.pending_choice or {}).get("type") == "reaction_choice"
        nav(joycons, rport, "right")
        assert [b["text"] for b in reaction_buttons(table) if b["focus"]] == ["否"]
        nav(joycons, rport, "left")
        assert [b["text"] for b in reaction_buttons(table) if b["focus"]] == ["是"]
        if path == "card" and card == "爆料黑幕":
            shot(request, table.page, "reaction-prompt-no-event-reveal")  # canonical：反應視窗可見、事件揭示不存在
        assert not reveal_displayed(table)

        if outcome == "decline":
            nav(joycons, rport, "right")
        press(joycons, rport, "A")
        assert wait_until(lambda: not table.game.pending_choice, 5.0), table.game.pending_choice
        log = "\n".join(table.game.action_log[-12:])
        r = table.player(reactor)
        if outcome == "cancel":
            assert f"reacted with {card} to cancel" in log, log
            assert [c.name for c in r.hand] == [], "取消牌已打出"
        else:
            assert "reacted with" not in log, log
            assert [c.name for c in r.hand] == [card], "不取消：取消牌留在手上"
        # 反應結束：反應者分頁不補開揭示。
        assert stays(lambda: not reveal_displayed(table), 1.0)

        # 交回行動者（整頁重新載入成行動者）：同一次觸發，揭示不可在之後出現。
        table.hand_to(actor)
        assert stays(lambda: not reveal_displayed(table), 2.5)
        table.page.evaluate("() => render(window.lastGameState)")
        assert stays(lambda: not reveal_displayed(table), 0.6)
        assert table.ctl()["scope"] != "eventRevealModal"
        # 事件卡仍可手動查看（既有事件卡分頁），關閉後也不會再自動出現。
        table.page.click("#eventCardTab")
        assert wait_until(lambda: table.shown("eventRevealModal"), 3.0)
        table.page.click("#eventRevealModal")
        assert wait_until(lambda: not table.shown("eventRevealModal"), 3.0)
        assert table.errors == [], table.errors
    finally:
        table.close()


def test_unrelated_next_turn_reveal_still_auto_opens_after_a_reaction(server_url, browser, joycons):
    """觸發範圍只限那一次：行動者結束回合、換到下一位（同一張事件卡）時，既有的自動揭示照常出現。"""
    table = HotSeatTable(server_url, browser, joycons, factions=("taiwan_green", "red_army"), ports=(P1_PORT, P2_PORT), device="rx-next")
    try:
        actor, reactor, trigger = scenario(table, "card", "情報網")
        table.open(actor)
        table.hand_to(actor)
        acknowledge_normal_reveal(table, P1_PORT)
        table.socks[actor].send(trigger)
        table.hand_to(reactor)
        assert wait_until(lambda: reaction_prompt_open(table), 10.0)
        assert not reveal_displayed(table)
        press(joycons, P2_PORT, "B")  # 第一下只放焦點
        nav(joycons, P2_PORT, "right")
        press(joycons, P2_PORT, "A")  # 否
        assert wait_until(lambda: not table.game.pending_choice, 5.0)
        table.hand_to(actor)
        assert stays(lambda: not reveal_displayed(table), 1.5)
        # P1 結束回合（自己的連線）：輪到 P2（同一回合、同一張事件卡）→ 交接後照既有行為自動揭示。
        sock = table.socks[actor]
        for _ in range(12):
            if table.game.current_player().id != table.by_name[actor]["player_id"]:
                break
            pending = table.game.pending_choice or {}
            if pending.get("player_id") == table.by_name[actor]["player_id"]:
                sock.send({"action": "resolve_choice", "choice_id": pending.get("choice_id"), "index": 0})
            else:
                sock.send({"action": "advance"})
            time.sleep(0.2)
        assert table.game.current_player().id == table.by_name[reactor]["player_id"]
        table.hand_to(reactor)
        acknowledge_normal_reveal(table, P2_PORT)
        assert table.errors == [], table.errors
    finally:
        table.close()


def test_private_seat_stale_reveal_closes_when_reaction_arrives_and_prompt_gets_focus(server_url, browser, joycons):
    """單席位分頁（不是客廳輪流）：反應者剛連線時事件揭示照常開著；反應視窗一出現，揭示立即關閉、反應視窗取得 Joy-Con 焦點。"""
    table = HotSeatTable(server_url, browser, joycons, factions=("taiwan_green", "red_army"), ports=(P1_PORT, P2_PORT), device="rx-solo")
    try:
        actor, reactor, trigger = scenario(table, "card", "產業滲透")
        seat = table.by_name[reactor]
        ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        errors = []
        ctx.add_init_script(
            f"localStorage.setItem('redline.controller.v1', JSON.stringify({{enabled: true, url: '{joycons.url}'}}));"
            f"sessionStorage.setItem('redline.controller.claim.v1', JSON.stringify({{mode: 'id', id: '{seat['controller']}'}}));")
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(server_url + "/")
        page.evaluate(f"() => {{ gameId = '{table.gid}'; playerId = '{seat['player_id']}'; resumeToken = '{seat['token']}'; window.RedlineStartFlow.hide(); connect(); }}")
        page.wait_for_function("() => window.lastGameState && (window.lastGameState.players || []).length > 0")
        table.page = page
        assert wait_until(lambda: table.shown("eventRevealModal"), 8.0), "private seat: normal reveal on connect"
        assert wait_until(lambda: table.owned() == seat["controller"], 10.0), table.ctl()
        table.socks[actor].send(trigger)
        assert wait_until(lambda: reaction_prompt_open(table), 8.0)
        assert stays(lambda: not reveal_displayed(table) and reaction_prompt_open(table), 1.5)
        assert table.ctl()["scope"] == "choiceModal"
        press(joycons, P2_PORT, "A")  # 第一下只放焦點：落在「是」，不送出
        assert [b["text"] for b in reaction_buttons(table) if b["focus"]] == ["是"]
        assert (table.game.pending_choice or {}).get("type") == "reaction_choice"
        press(joycons, P2_PORT, "A")  # 是＝取消
        assert wait_until(lambda: not table.game.pending_choice, 5.0)
        assert "reacted with 產業滲透 to cancel" in "\n".join(table.game.action_log[-8:])
        assert stays(lambda: not reveal_displayed(table), 1.0)
        assert errors == [], errors
        ctx.close()
    finally:
        table.page = None
        table.close()
