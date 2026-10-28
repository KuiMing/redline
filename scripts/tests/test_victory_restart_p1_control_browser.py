"""遊戲結束／重新開始：Joy-Con 控制權一律回到 P1 — Browser（Playwright／Chromium）regression。

2026-10-27 playtest：遊戲結束時控制權留在結束當下操作的席位（例如 P2），勝利畫面與遊戲選單由那一支操作；
P2 觸發「重新開始」後，新的開始流程又要求重新配對手把。
根因：static/hotseat_core.js decide() 在 finished 時把 seat 設成「目前連線的席位」（claimTarget／allowsInput 都跟著它），
而 /new-game 不保留本局的配對（開始畫面有多支手把時 fail closed、不猜）。
修正：finished → seat＝P1（本機席位表第一席＝既有座位順序）；離開時記下依座位順序的配對，新的開始流程只把導覽交給 P1、
選 Joy-Con 時直接帶入 P1～Pn。

伺服器是同一 process 的真 uvicorn；Joy-Con 是真的 bridge app＋fixture 封包（synthetic，**不是實體 Joy-Con**）。
遊戲結束以測試替身觸發：目前行動席位自己的遊戲連線送出 advance，這一次 advance 直接把遊戲標成結束（指定勝利者），
伺服器照常廣播權威 state。判斷一律看 bridge 擁有權、伺服器狀態與實際 DOM（computed style、activeElement、.rl-pad-focus）。
"""
from __future__ import annotations

import json
import time

import pytest
import requests

playwright_sync = pytest.importorskip("playwright.sync_api")

from hotseat_table_harness import (  # noqa: E402,F401  (server_url 是 pytest fixture)
    BITS, HotSeatTable, hold, nav, press, release, server_url, shot, stays, wait_until,
)
from server.game import GamePhase  # noqa: E402
from test_start_flow_browser import FakeJoyCons, nav_to  # noqa: E402

P1_PORT, P2_PORT, P3_PORT = 24801, 24803, 24800  # P1／P2 左 Joy-Con、P3 右 Joy-Con
FACTIONS = ("taiwan_green", "hong_kong", "red_army")


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


def finish_on_next_advance(table, winner_name):
    """測試替身：下一次 advance（任何目前行動席位）把遊戲標成結束並指定勝利者；伺服器照常廣播。"""
    game = table.game

    def advance_turn_phase():
        game.game_phase = GamePhase.FINISHED
        game.winner = winner_name
        game.co_winners = []
        game.log(f"[test] {winner_name} 獲勝（測試替身）")
        return {"success": True}

    game.advance_turn_phase = advance_turn_phase


def open_at(table, active):
    """分頁顯示 active 席位（交接後 open）；一般流程的事件揭示用該席 B 關掉。"""
    table.pin_noop_event()
    table.set_turn(active)
    table.open(active)
    table.hand_to(active)
    port = table.by_name[active]["port"]
    assert wait_until(lambda: table.shown("eventRevealModal"), 8.0)
    for _ in range(3):
        if not table.shown("eventRevealModal"):
            break
        press(table.fake, port, "B")
    assert wait_until(lambda: not table.shown("eventRevealModal"), 4.0)


def focus_text(page):
    return page.evaluate("() => { const a = document.activeElement; return a && a !== document.body ? (a.id || a.textContent.trim()) : null; }")


def dismiss_leftover_preview(table):
    """結束前按住的 A 在該席焦點的手牌上打開了卡牌預覽（遊戲中的合法操作）：結束後只有 P1 能關掉它。"""
    if not table.shown("cardPreviewModal"):
        return
    press(table.fake, P2_PORT, "B")
    assert table.shown("cardPreviewModal"), "P2 的 B 不能操作"
    press(table.fake, P1_PORT, "B")
    assert wait_until(lambda: not table.shown("cardPreviewModal"), 3.0)
    assert table.shown("victoryModal")


def safe(fn, default=None):
    try:
        return fn()
    except Exception:  # 整頁重新載入中
        return default


def p1_controls_finished_table(table):
    """結束後：畫面以 P1 自己的 token 連線（不是 P2 的連線被 P1 操作）、bridge 擁有權在 P1 的 Joy-Con、勝利畫面開著。"""
    p1 = table.by_name["P1"]

    def ready():
        st = safe(table.hs, {}) or {}
        return (st.get("view") == "open" and (st.get("actor") or {}).get("kind") == "finished"
                and st.get("handoffSeat") == p1["player_id"] and st.get("displayedSeat") == p1["player_id"])

    assert wait_until(ready, 20.0), safe(table.hs)
    assert table.page.evaluate("() => window.RedlineSession.current().playerId") == p1["player_id"]
    assert wait_until(lambda: safe(table.owned) == p1["controller"], 15.0), safe(table.ctl)
    assert wait_until(lambda: safe(lambda: table.shown("victoryModal")), 8.0)
    assert not table.shown("eventRevealModal"), "結束後的重新載入不可在勝利畫面上自動揭示事件卡"


@pytest.mark.parametrize("winner,active", [("P1", "P1"), ("P2", "P2"), ("P3", "P2"), ("P3", "P3")],
                         ids=["p1-wins-p1-active", "p2-wins-p2-active", "p3-wins-p2-active", "p3-wins-p3-active"])
def test_finish_moves_control_to_p1_with_release_gate_and_others_cannot_operate(server_url, browser, joycons, request, winner, active):
    table = HotSeatTable(server_url, browser, joycons, factions=FACTIONS, ports=(P1_PORT, P2_PORT, P3_PORT), device=f"vic-{winner}-{active}")
    try:
        open_at(table, active)
        aport = table.by_name[active]["port"]
        finish_on_next_advance(table, winner)
        # 結束的那一下：目前操作席位的 A 仍按著。
        hold(joycons, aport, "A")
        table.socks[active].send({"action": "advance"})
        assert table.game.winner == winner
        p1_controls_finished_table(table)
        assert table.page.evaluate("() => document.getElementById('victoryTitle').textContent").find(winner) >= 0
        if active == "P1":
            # 同一支（P1）結束時仍按住 A：放開前勝利畫面不接受任何輸入（按住 A 時再按 B 也被擋下）。
            assert table.hs()["finishGate"] == ["A"], table.hs()
            overlays = (table.shown("cardPreviewModal"), table.shown("victoryModal"), focus_text(table.page))
            joycons.held[aport] = [BITS["L"]["A"], BITS["L"]["B"]]
            time.sleep(0.3)
            joycons.held[aport] = [BITS["L"]["A"]]
            time.sleep(0.3)
            assert (table.shown("cardPreviewModal"), table.shown("victoryModal"), focus_text(table.page)) == overlays
            assert table.hs()["finishGate"] == ["A"]
        assert stays(lambda: table.page.url.endswith("/") and table.shown("victoryModal"), 1.0), "held A penetrated"
        release(joycons, aport)
        dismiss_leftover_preview(table)
        before = (table.ctl()["focusSig"], focus_text(table.page))
        # 非 P1 的手把（含結束時操作的 P2／P3）都不能操作勝利畫面或打開遊戲選單。
        for name in ("P2", "P3"):
            port = table.by_name[name]["port"]
            press(joycons, port, "A")
            press(joycons, port, "B")
            if port != P3_PORT:
                nav(joycons, port, "right")
                hold(joycons, port, "STICK")
                time.sleep(2.4)
                release(joycons, port)
        assert table.shown("victoryModal") and table.page.url.endswith("/")
        assert (table.ctl()["focusSig"], focus_text(table.page)) == before
        assert table.ctl()["gameMenu"]["level"] is None
        assert table.owned() == table.by_name["P1"]["controller"]
        # P1：方向焦點在勝利畫面兩個按鈕間移動（第一下只放焦點），A＝檢視最終盤面。
        assert nav_to(table.page, joycons, P1_PORT, "#victoryRestartBtn"), focus_text(table.page)
        assert nav_to(table.page, joycons, P1_PORT, "#victoryMinimizeBtn"), focus_text(table.page)
        if winner == "P2" and active == "P2":
            shot(request, table.page, "victory-p1-controls")
        press(joycons, P1_PORT, "A")
        assert wait_until(lambda: not table.shown("victoryModal"), 4.0)
        # 遊戲選單（按住搖桿 2 秒）：只有 P1 能開；P2 按住不會開。
        hold(joycons, P2_PORT, "STICK")
        time.sleep(2.4)
        release(joycons, P2_PORT)
        assert table.ctl()["gameMenu"]["level"] is None
        hold(joycons, P1_PORT, "STICK")
        assert wait_until(lambda: table.ctl()["gameMenu"]["level"] == "menu", 4.0), table.ctl()["gameMenu"]
        release(joycons, P1_PORT)
        press(joycons, P2_PORT, "B")
        assert table.ctl()["gameMenu"]["level"] == "menu", "P2 的 B 不能關掉 P1 的遊戲選單"
        press(joycons, P1_PORT, "B")
        assert wait_until(lambda: table.ctl()["gameMenu"]["level"] is None, 3.0)
        assert table.errors == [], table.errors
    finally:
        table.close()


def test_ai_red_army_win_with_p2_active_also_returns_control_to_p1(server_url, browser, joycons):
    """AI 紅軍房間（2 位真人＋AI）：AI 獲勝、P2 正在操作 → P1 控制。"""
    table = HotSeatTable(server_url, browser, joycons, factions=("taiwan_green", "hong_kong"), ports=(P1_PORT, P2_PORT),
                         device="vic-ai", ai_red_army=True)
    try:
        red = next(p for p in table.game.players if p.id == table.game.ai_red_army_player_id)
        open_at(table, "P2")
        finish_on_next_advance(table, red.name)
        table.socks["P2"].send({"action": "advance"})
        p1_controls_finished_table(table)
        press(joycons, P2_PORT, "A")
        assert table.shown("victoryModal")
        assert nav_to(table.page, joycons, P1_PORT, "#victoryMinimizeBtn"), focus_text(table.page)
        assert table.errors == [], table.errors
    finally:
        table.close()


# ------------------------------------------------------------------ 重新開始：沿用配對、P1 控制新的開始流程

def start_state(page):
    return page.evaluate("() => window.RedlineStartFlow && window.RedlineStartFlow.getState()")


def wait_restarted_entry(table, timeout=20.0):
    """/new-game → 起始畫面：沿用的配對（P1～P3）、導覽只給 P1。"""
    page = table.page
    page.wait_for_url("**/", timeout=int(timeout * 1000))
    assert wait_until(lambda: (start_state(page) or {}).get("step") == "entry", timeout), start_state(page)
    controllers = [s["controller"] for s in table.seats]
    assert start_state(page)["carry"]["controllers"] == controllers
    p1 = table.by_name["P1"]["controller"]
    assert wait_until(lambda: table.owned() == p1 and table.ctl()["status"] == "connected", 15.0), table.ctl()
    assert table.ctl()["startNav"]["preferred"] == p1


def p1_drives_restarted_flow(table, request=None, shot_name=None):
    page, fake = table.page, table.fake
    p1 = table.by_name["P1"]["controller"]
    # P2 不能搶焦點：它的方向／A 都不會到主連線。
    before = focus_text(page)
    nav(fake, P2_PORT, "down")
    press(fake, P2_PORT, "A")
    assert focus_text(page) == before and start_state(page)["step"] == "entry"
    assert table.owned() == p1
    # P1：第一下只放焦點，移到「建立真人紅軍」，A 進入設定；操作方式直接是 Joy-Con，P1～P3 已帶入（不必 SL＋SR）。
    assert nav_to(page, fake, P1_PORT, "#sfCreateHuman"), focus_text(page)
    press(fake, P1_PORT, "A")
    assert wait_until(lambda: start_state(page)["step"] == "setup", 5.0), start_state(page)
    sf = start_state(page)
    controllers = [s["controller"] for s in table.seats]
    assert sf["draft"]["controlMode"] == "joycon"
    assert sf["paired"] == controllers, sf
    assert page.evaluate("() => [...document.querySelectorAll('#sfSlots .sf-slot')].map(s => s.dataset.paired)") == ["true"] * 3 + ["false"]
    assert wait_until(lambda: table.owned() == p1, 15.0), table.ctl()
    # P2 的 A 不能完成配對。
    press(fake, P2_PORT, "A")
    assert start_state(page)["step"] == "setup"
    # P1 的 A＝完成配對 → 背景建房、依配對順序配置 P1～P3 並綁定同一批手把 → 逐棒大廳由 P1 開始。
    press(fake, P1_PORT, "A")
    page.wait_for_selector("#factionPicker", state="visible", timeout=30000)
    gid = page.evaluate("() => window.RedlineSession.current().gameId")
    assert gid and gid != table.gid
    store = page.evaluate("() => JSON.parse(localStorage.getItem('redline.hotseat.v1'))")
    seats = store["games"][gid]["seats"]
    assert [s["controller"] for s in seats] == controllers, seats
    lobby = requests.get(f"{table.base}/lobby/{gid}", timeout=10).json()
    assert [p[0] for p in lobby["players"]] == [s["player_id"] for s in seats], "伺服器座位順序＝配對順序"
    assert [p[1] for p in lobby["players"]] == ["P1", "P2", "P3"]
    assert lobby["control_mode"] == "joycon" and lobby["joycon_count"] == 3
    assert page.evaluate("() => window.RedlineSession.current().playerId") == seats[0]["player_id"]
    assert wait_until(lambda: table.owned() == p1, 15.0), table.ctl()
    page.wait_for_function("(() => { const a = document.activeElement; return !!a && !!a.closest('#factionList'); })()", timeout=15000)
    if request is not None and shot_name:
        shot(request, page, shot_name)
    # 逐棒大廳：P2 不能切換席位或搶焦點。
    focus_before = focus_text(page)
    press(fake, P2_PORT, "A")
    nav(fake, P2_PORT, "down")
    assert stays(lambda: page.evaluate("() => window.RedlineSession.current().playerId") == seats[0]["player_id"], 1.0)
    assert focus_text(page) == focus_before
    assert page.evaluate("() => sessionStorage.getItem('redline.startflow.carryover.v1')") is None, "建房後不再沿用"


def test_p1_restarts_from_victory_with_held_a_and_pairings_are_retained(server_url, browser, joycons, request):
    """P2 獲勝、P2 正在操作；P1 在勝利畫面按「重新開始」並按住 A 穿過整頁導向：新頁面不穿透，P1 控制新的開始流程。"""
    table = HotSeatTable(server_url, browser, joycons, factions=FACTIONS, ports=(P1_PORT, P2_PORT, P3_PORT), device="restart-victory")
    try:
        open_at(table, "P2")
        finish_on_next_advance(table, "P2")
        table.socks["P2"].send({"action": "advance"})
        p1_controls_finished_table(table)
        assert nav_to(table.page, joycons, P1_PORT, "#victoryRestartBtn"), focus_text(table.page)
        hold(joycons, P1_PORT, "A")  # 按下＝點既有「重新開始」連結；不放開
        wait_restarted_entry(table)
        assert stays(lambda: start_state(table.page)["step"] == "entry" and focus_text(table.page) in (None, "sfTitle"), 1.5), \
            (start_state(table.page), focus_text(table.page))
        release(joycons, P1_PORT)
        assert start_state(table.page)["step"] == "entry"
        shot(request, table.page, "restart-entry-p1-controls")
        p1_drives_restarted_flow(table, request, "restarted-lobby-p1-controls")
        assert table.errors == [], table.errors
    finally:
        table.close()


@pytest.mark.parametrize("variant", ["p2-confirms-in-progress", "p2-opened-confirm-then-game-finished"])
def test_restart_initiated_from_p2_input_restores_p1_without_re_pairing(server_url, browser, joycons, variant):
    table = HotSeatTable(server_url, browser, joycons, factions=FACTIONS, ports=(P1_PORT, P2_PORT, P3_PORT), device=f"restart-{variant}")
    try:
        open_at(table, "P2")
        page = table.page
        # P2（目前操作中）按住搖桿 2 秒開遊戲選單 → 重新開始 → 第二層確認。
        hold(joycons, P2_PORT, "STICK")
        assert wait_until(lambda: table.ctl()["gameMenu"]["level"] == "menu", 4.0), table.ctl()["gameMenu"]
        release(joycons, P2_PORT)
        assert nav_to(page, joycons, P2_PORT, "#gameMenuRestartBtn"), focus_text(page)
        press(joycons, P2_PORT, "A")
        assert wait_until(lambda: table.ctl()["gameMenu"]["level"] == "confirm", 3.0)
        if variant == "p2-confirms-in-progress":
            hold(joycons, P2_PORT, "A")  # P2 確認重新開始，A 按住穿過導向
        else:
            # P2 的確認畫面還開著時遊戲結束：整頁以 P1 的 token 重新連線（P2 開的確認畫面一併丟棄，P2 的 A 不能完成它）；
            # P1 從勝利畫面的既有「重新開始」離開。
            finish_on_next_advance(table, "P2")
            table.socks["P2"].send({"action": "advance"})
            p1_controls_finished_table(table)
            assert table.ctl()["gameMenu"]["level"] is None
            press(joycons, P2_PORT, "A")
            assert table.page.url.endswith("/") and table.shown("victoryModal")
            assert nav_to(page, joycons, P1_PORT, "#victoryRestartBtn"), focus_text(page)
            hold(joycons, P1_PORT, "A")
        wait_restarted_entry(table)
        assert stays(lambda: start_state(page)["step"] == "entry", 1.2)
        release(joycons, P2_PORT)
        release(joycons, P1_PORT)
        p1_drives_restarted_flow(table)
        assert table.errors == [], table.errors
    finally:
        table.close()


def test_fresh_unrelated_table_still_uses_normal_pairing(server_url, browser, joycons):
    """沒有經過本局的重新開始（新的分頁直接開 /new-game）：沒有沿用的配對，開始畫面多支手把照舊 fail closed、選 Joy-Con 要 SL＋SR。"""
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    ctx.add_init_script(f"localStorage.setItem('redline.controller.v1', JSON.stringify({{enabled: true, url: '{joycons.url}'}}));")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(server_url + "/new-game")
        page.wait_for_function("() => window.RedlineStartFlow && window.RedlineStartFlow.getState().step === 'entry'", timeout=15000)
        sf = page.evaluate("() => window.RedlineStartFlow.getState()")
        assert sf["carry"] is None
        page.wait_for_function("() => (window.RedlineController.getState().controller.roster || []).filter(c => c.status === 'active').length >= 3",
                               timeout=15000)
        assert stays(lambda: page.evaluate("() => window.RedlineController.getState().controller.owned") is None, 1.5), \
            json.dumps({k: v for k, v in page.evaluate("() => window.RedlineController.getState()").items() if k in ("controller", "startNav")})
        page.click("#sfCreateHuman")
        page.click('[data-sf-control="joycon"]')
        assert page.evaluate("() => window.RedlineStartFlow.getState().paired") == []
        assert errors == [], errors
    finally:
        ctx.close()
