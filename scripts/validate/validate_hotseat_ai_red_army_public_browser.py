#!/usr/bin/env python3
"""正式 Browser proof：客廳輪流模式公開顯示 AI 紅軍行動（整段期間 current player 都是 red_army）。

伺服器在這個 process 內啟動（可直接讀權威 Game 狀態），兩位真人席位＋AI 紅軍，由瀏覽器分頁（客廳輪流，
已確認 P1 席位）顯示。真人席位的回合由各自的 WebSocket 推進；AI 紅軍由伺服器 runtime 行動（3 秒節奏不改）。

新規則：視窗顯示的整段期間（含紅軍回合結束後的等待確認）current player 仍是 red_army。伺服器在確認
（知道了／A）或逾時前不會推進到下一位；確認後才輪到下一位並進入交接。驗收一律讀權威狀態——Game 物件的
current_player()／awaiting 狀態、以及伺服器經 WebSocket 傳來的 state.current_player／ai_red_army.awaiting_ack——
不是只看畫面快照或前端快取。
1. 視窗開著的每一次取樣：Game.current_player()、WebSocket state.current_player 都是紅軍，且為 red_army 陣營。
2. 紅軍回合結束時，伺服器停在 awaiting_ack（current player 仍是紅軍）；視窗標題「回合結束」，等待期間持續取樣仍是紅軍。
3. 第一次等待由桌面分頁按「知道了」確認：確認前權威 current player 是紅軍，確認後才換到下一位並出現交接。
4. 第二次等待不確認：伺服器約 10 秒逾時後才推進；等待期間權威 current player 一直是紅軍。
5. 視窗開著時「玩家動態」通知沒有顯示；單席位（非客廳輪流）分頁照舊顯示玩家動態。
6. 規則結算與下一位玩家流程正確；桌面與客廳（?display=living-room）1280×720 視窗完整置中。
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from playwright.sync_api import sync_playwright
from websockets.sync.client import connect as ws_connect

from server import main as server_main
import server.red_army_ai_runtime as ai_runtime

OUT = ROOT / "docs/records/hot-seat/ai-red-army-public-action-20261020"
REPORT_JSON = ROOT / "docs/records/hot-seat/AI_RED_ARMY_PUBLIC_ACTION_VALIDATION.json"
REPORT_MD = ROOT / "docs/records/hot-seat/AI_RED_ARMY_PUBLIC_ACTION_VALIDATION.md"
HOTSEAT_STORE_KEY = "redline.hotseat.v1"
HOTSEAT_SESSION_KEY = "redline.hotseat.session.v1"
MAX_ROUNDS = 600
HUMAN_FACTIONS = ("hong_kong", "taiwan_green")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def post(base: str, path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


class Seat:
    """一個真人席位的 WebSocket（只用來推進該席位的回合；顯示由瀏覽器分頁負責）。"""

    def __init__(self, base: str, game_id: str, player_id: str, token: str, name: str):
        self.player_id, self.name = player_id, name
        self.state: dict = {}
        self.ws = ws_connect(
            base.replace("http", "ws", 1) + f"/ws/{game_id}/{player_id}", subprotocols=[token], open_timeout=10,
        )
        self.drain(1.0)

    def drain(self, timeout: float = 0.05) -> None:
        while True:
            try:
                message = self.ws.recv(timeout=timeout)
            except TimeoutError:
                return
            except Exception:
                return
            data = json.loads(message)
            if isinstance(data, dict) and "players" in data:
                self.state = data
            timeout = 0.02

    def send(self, payload: dict) -> dict:
        self.ws.send(json.dumps(payload, ensure_ascii=False))
        self.drain(0.6)
        return self.state


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(server_main.app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise SystemExit("伺服器未啟動")

    checks: list[dict] = []
    evidence: dict = {}

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    # ---------------------------------------------------------------- 大廳（HTTP）：兩位真人＋AI 紅軍
    created = post(base, "/create", {"name": "P1", "device_id": "hs-ai-p1"})
    game_id = created["game_id"]
    p1 = {"player_id": created["host_id"], "token": created["resume_token"], "name": "P1"}
    joined = post(base, "/join", {"game_id": game_id, "name": "P2", "device_id": "hs-ai-p2"})
    p2 = {"player_id": joined["player_id"], "token": joined["resume_token"], "name": "P2"}
    assert post(base, "/ai-red-army", {"game_id": game_id, "player_id": p1["player_id"], "resume_token": p1["token"], "enabled": True}).get("success")
    for seat, faction in zip((p1, p2), HUMAN_FACTIONS):
        assert post(base, "/choose-faction", {"game_id": game_id, "player_id": seat["player_id"], "resume_token": seat["token"], "faction_id": faction}).get("success")
        assert post(base, "/ready", {"game_id": game_id, "player_id": seat["player_id"], "resume_token": seat["token"], "ready": True}).get("success")
    started = post(base, "/start", {"game_id": game_id, "player_id": p1["player_id"], "resume_token": p1["token"]})
    assert started.get("success"), started
    game = server_main.manager.get_game(game_id)
    ai_id = game.ai_red_army_player_id
    ai_player = next(p for p in game.players if p.id == ai_id)

    seats = [Seat(base, game_id, s["player_id"], s["token"], s["name"]) for s in (p1, p2)]
    seat_by_id = {s.player_id: s for s in seats}

    # ---------------------------------------------------------------- 瀏覽器：客廳輪流，P1 為已確認席位
    store = {
        "v": 1, "enabled": True,
        "games": {game_id: {"seats": [
            {"player_id": s["player_id"], "resume_token": s["token"], "name": s["name"], "controller": None, "auto_name": False}
            for s in (p1, p2)
        ]}},
    }
    session = {"gameId": game_id, "active": p1["player_id"], "unlocked": True}
    init_script = (
        f"try {{ localStorage.setItem({json.dumps(HOTSEAT_STORE_KEY)}, {json.dumps(json.dumps(store))});"
        f" if (!sessionStorage.getItem({json.dumps(HOTSEAT_SESSION_KEY)})) sessionStorage.setItem({json.dumps(HOTSEAT_SESSION_KEY)}, {json.dumps(json.dumps(session))}); }} catch (e) {{}}"
    )

    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        pages = {}
        for mode, query in (("desktop", ""), ("living-room", "?display=living-room")):
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            context.add_init_script(init_script)
            page = context.new_page()
            page.on("console", lambda m, mode=mode: console_errors.append(f"[{mode}] {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e, mode=mode: console_errors.append(f"[{mode}] {e}"))
            page.goto(base + "/" + query, wait_until="domcontentloaded")
            page.wait_for_function("() => window.lastGameState && window.RedlineHotSeat", timeout=20000)
            pages[mode] = page

        # 對照：同一場遊戲、沒有客廳輪流設定的單席位分頁（P2）。AI 行動時它仍照舊顯示「玩家動態」通知，不出現公開視窗。
        single_ctx = browser.new_context(viewport={"width": 1280, "height": 720})
        single = single_ctx.new_page()
        single.on("console", lambda m: console_errors.append(f"[single] {m.text}") if m.type == "error" else None)
        single.on("pageerror", lambda e: console_errors.append(f"[single] {e}"))
        single.goto(f"{base}/?game_id={game_id}&player_id={p2['player_id']}&resume_token={p2['token']}", wait_until="domcontentloaded")
        single.wait_for_function("() => window.lastGameState", timeout=20000)
        single_notices: list[dict] = []

        def hs_state(page) -> dict:
            return page.evaluate("() => window.RedlineHotSeat.getState()")

        def actor_name(state: dict) -> str:
            return state.get("current_player", "")

        order = [p.name for p in game.players]
        evidence["player_order"] = order
        evidence["ai_player_name"] = ai_player.name

        # 真人席位推進：base_selection／pending_choice／advance
        def human_step(seat: Seat) -> str | None:
            seat.drain()
            state = seat.state
            if not state:
                return None
            if state.get("game_phase") == "base_selection":
                choices = (state.get("pending_base_choices") or {}).get(seat.player_id)
                if choices:
                    labels = choices.get("labels") or []
                    label = labels[0]
                    resolved = (choices.get("resolved") or {}).get(label) or [label]
                    reply = seat.send({"action": "set_base", "town": resolved[0], "label": label})
                    return f"set_base:{label}:{reply.get('error') or 'ok'}"
                return None
            pending = state.get("pending_choice")
            if pending and pending.get("player_id") == seat.player_id:
                reply = seat.send({"action": "resolve_choice", "choice_id": pending.get("choice_id"), "index": 0})
                return f"resolve_choice:{reply.get('error') or 'ok'}"
            if actor_name(state) == seat.name and not pending and state.get("turn_phase") is not None:
                reply = seat.send({"action": "advance"})
                return f"advance:{reply.get('error') or 'ok'}"
            return None

        snapshots = []            # 視窗開著（行動中）的取樣
        red_current_polls = []    # 紅軍是 current player（沒有真人 pending choice）的每次輪詢
        shots_taken = {"desktop": False, "living-room": False}
        holds = []                # 每次「回合結束等待確認」的權威證據
        handoff_followup = None
        flow_log: list[dict] = []
        ai_window_seen = False
        red_name = ai_player.name
        order_index = order.index(red_name)

        def page_state(page) -> dict:
            return page.evaluate("() => window.lastGameState")

        def authority(page=None) -> dict:
            """權威取樣：伺服器 Game 物件（同一個 process）＋ WebSocket 傳給瀏覽器的 state（不是 DOM 或快取）。"""
            ack = game.ai_red_army_ack
            out = {
                "server_current_player": game.current_player().name,
                "server_current_faction": game.current_player().faction_id,
                "server_turn": game.turn,
                "server_awaiting_ack": bool(ack and not ack.get("released")),
            }
            if page is not None:
                st = page_state(page)
                out["ws_state_current_player"] = st.get("current_player")
                out["ws_state_awaiting_ack"] = (st.get("ai_red_army") or {}).get("awaiting_ack")
                out["ws_state_turn"] = st.get("turn")
            return out

        def sample_hold_until_released(mode: str, max_seconds: float) -> dict:
            """等待期間持續取樣權威 current player；mode=click 時先取樣約 1.2 秒再由桌面分頁按「知道了」。"""
            started = time.time()
            samples, clicked_at = [], None
            while time.time() - started < max_seconds:
                a = authority(pages["desktop"])
                hs_d = hs_state(pages["desktop"])
                a.update({"t": round(time.time() - started, 2), "view": hs_d["view"], "window_open": hs_d["aiPublic"]["open"],
                          "ended": hs_d["aiPublic"]["ended"]})
                samples.append(a)
                if not a["server_awaiting_ack"]:
                    break
                if mode == "click" and clicked_at is None and time.time() - started >= 1.2:
                    clicked_at = round(time.time() - started, 2)
                    samples[-1]["clicked_know_button"] = True
                    pages["desktop"].locator("#hotseatAiDismiss").click()
                time.sleep(0.15)
            return {"mode": mode, "samples": samples, "clicked_at": clicked_at, "elapsed": round(time.time() - started, 2)}

        for round_no in range(MAX_ROUNDS):
            pstate = page_state(pages["desktop"])
            hs = hs_state(pages["desktop"])
            view, ai_info = hs["view"], hs["aiPublic"]
            notice = single.evaluate("""() => ({display: getComputedStyle(document.getElementById('peerActionNotice')).display,
              player: document.getElementById('peerActionNoticePlayer')?.textContent || '',
              text: document.getElementById('peerActionNoticeText')?.textContent || '',
              hotseatMask: document.documentElement.dataset.hotseat || null,
              aiWindow: !!document.querySelector('#hotseatAiPublic:not([hidden])')})""")
            if notice["display"] != "none" and "AI 紅軍" in notice["player"]:
                single_notices.append(notice)
            auth = authority(pages["desktop"])
            human_pending = bool((pstate.get("pending_choice") or {}).get("player_id"))

            if auth["server_current_player"] == red_name and not human_pending:
                red_current_polls.append({
                    "t": round(time.time(), 2), **auth, "view": view, "window_open": ai_info["open"], "ended": ai_info["ended"],
                })

            if ai_info["open"] and not ai_info["ended"]:
                ai_window_seen = True
                snap = {
                    **auth, "t": round(time.time(), 2), "view": view, "actor": hs["actor"],
                    "steps": ai_info["steps"], "text": ai_info["text"],
                    "peer_notice_display": pages["desktop"].evaluate(
                        "() => getComputedStyle(document.getElementById('peerActionNotice')).display"),
                    "peer_notice_text": pages["desktop"].evaluate(
                        "() => document.getElementById('peerActionNoticeText')?.textContent || ''"),
                    "mask_title": pages["desktop"].evaluate("() => document.getElementById('hotseatAiTitle')?.textContent || ''"),
                    "dismiss_hidden": pages["desktop"].evaluate("() => document.getElementById('hotseatAiDismiss').hidden"),
                }
                if not snapshots or snapshots[-1]["text"] != snap["text"]:
                    snapshots.append(snap)
                if ai_info["steps"] >= 3:
                    for mode, page in pages.items():
                        if not shots_taken[mode]:
                            hs_mode = hs_state(page)
                            if hs_mode["aiPublic"]["open"] and not hs_mode["aiPublic"]["ended"] and hs_mode["aiPublic"]["steps"] >= 3:
                                page.screenshot(path=str(OUT / f"ai_public_window_red_army_current_{mode}_1280x720.png"))
                                shots_taken[mode] = True
                                evidence[f"authority_at_shot_{mode}"] = authority(page)
                                evidence[f"geometry_{mode}"] = page.evaluate("""() => {
                                  const r = document.getElementById('hotseatAiPublic').getBoundingClientRect();
                                  const steps = document.getElementById('hotseatAiSteps');
                                  return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height,
                                          viewport: [innerWidth, innerHeight], stepsClipped: steps.scrollHeight > steps.clientHeight,
                                          fontSize: getComputedStyle(document.querySelector('#hotseatAiSteps .hs-ai-line')).fontSize};
                                }""")
                time.sleep(0.25)
                continue  # 紅軍行動中：不推進任何真人，只觀察

            if auth["server_awaiting_ack"] and ai_info["open"]:
                # 回合結束，伺服器停在 awaiting_ack：權威 current player 仍是紅軍。
                mode = "click" if not holds else "timeout"
                before = {
                    **auth, "view": view, "title": pages["desktop"].evaluate("() => document.getElementById('hotseatAiTitle').textContent"),
                    "dismiss_visible": pages["desktop"].evaluate("() => !document.getElementById('hotseatAiDismiss').hidden"),
                    "peer_notice_display": pages["desktop"].evaluate("() => getComputedStyle(document.getElementById('peerActionNotice')).display"),
                    "living_room": {**authority(pages["living-room"]), **hs_state(pages["living-room"])["aiPublic"]},
                    "ai_status": dict(game.ai_red_army_status or {}),
                }
                if mode == "click":
                    pages["desktop"].screenshot(path=str(OUT / "ai_public_window_red_army_turn_ended_awaiting_ack_desktop_1280x720.png"))
                    pages["living-room"].screenshot(path=str(OUT / "ai_public_window_red_army_turn_ended_awaiting_ack_living-room_1280x720.png"))
                result = sample_hold_until_released(mode, 15.0)
                time.sleep(0.4)
                after_auth = authority(pages["desktop"])
                hs_after = hs_state(pages["desktop"])
                hold = {"before": before, **result, "after": {
                    **after_auth, "view": hs_after["view"], "actor": hs_after["actor"], "window_open": hs_after["aiPublic"]["open"],
                    "living_room_window_open": hs_state(pages["living-room"])["aiPublic"]["open"],
                    "expected_next_player": order[(order_index + 1) % len(order)],
                }}
                if mode == "click":
                    pages["desktop"].screenshot(path=str(OUT / "handoff_after_ack_1280x720.png"))
                holds.append(hold)
                if mode == "click":
                    actor = hs_after["actor"] or {}
                    nxt = next((s for s in seats if s.player_id == actor.get("playerId")), None)
                    if nxt is not None:
                        reply = None
                        for _ in range(8):
                            reply = human_step(nxt)
                            if reply:
                                break
                            time.sleep(0.25)
                        nxt.drain()
                        handoff_followup = {"next_player": nxt.name, "step": reply, "actor_kind": actor.get("kind")}
                if len(holds) >= 2 and all(shots_taken.values()):
                    break
                continue

            # 其餘時間（紅軍不是目前行動者、視窗沒開）才推進真人席位
            for seat in seats:
                step = human_step(seat)
                if step:
                    flow_log.append({"t": round(time.time(), 2), "seat": seat.name, "step": step})
            if pstate.get("winner"):
                break
            time.sleep(0.25)

        state = page_state(pages["desktop"])
        evidence["ai_snapshots"] = snapshots
        evidence["final_ai_status"] = dict(game.ai_red_army_status or {})
        evidence["final_report"] = game.ai_red_army_public_report
        evidence["flow_log_tail"] = flow_log[-12:]
        evidence["server_action_log_tail"] = list(game.action_log[-14:])
        evidence["single_seat_notices"] = single_notices[:3]
        evidence["red_current_polls"] = red_current_polls
        evidence["holds"] = holds
        evidence["handoff_followup"] = handoff_followup
        evidence["console_errors"] = console_errors
        browser.close()

    for seat in seats:
        try:
            seat.ws.close()
        except Exception:
            pass
    server.should_exit = True

    # ---------------------------------------------------------------- 判定
    def is_red(sample: dict) -> bool:
        return (sample["server_current_player"] == red_name and sample["server_current_faction"] == "red_army"
                and sample.get("ws_state_current_player", red_name) == red_name)

    first_with_steps = next((s for s in snapshots if s["steps"] >= 1), None)
    record("ai_public_window_opens_while_ai_red_army_acts", ai_window_seen and bool(snapshots), {
        "snapshots": len(snapshots), "first": first_with_steps and first_with_steps["text"][:240],
    })
    record("authority_current_player_is_red_army_whenever_the_window_is_open_acting", bool(snapshots) and all(
        is_red(s) and (s["actor"] or {}).get("name") == red_name and s["view"] == "waiting" for s in snapshots
    ), [{k: s[k] for k in ("server_current_player", "server_current_faction", "ws_state_current_player", "view")} for s in snapshots[:3]])
    record("window_is_open_from_the_first_poll_where_red_army_is_current_without_switching_to_next_player",
           bool(red_current_polls) and all(
               p["view"] == "waiting" and p["window_open"] for p in red_current_polls
           ), {"polls": len(red_current_polls), "bad": [p for p in red_current_polls if p["view"] != "waiting" or not p["window_open"]][:3]})
    record("window_summarises_public_actions_and_resources", bool(first_with_steps) and any(
        ("資源變化" in s["text"] or "目前資金" in s["text"]) for s in snapshots
    ) and any(any(word in s["text"] for word in ("資源", "購買", "使用", "組織", "事件", "移動", "抽")) for s in snapshots), {
        "texts": [s["text"][:300] for s in snapshots[:4]],
    })
    record("window_titles_ai_red_army_while_acting", all("AI 紅軍行動中" in s["mask_title"] for s in snapshots)
           and all(s["dismiss_hidden"] for s in snapshots), [s["mask_title"] for s in snapshots[:3]])
    record("no_raw_english_log_in_window", all(
        not __import__("re").search(r"[A-Za-z]{3,}", s["text"]) for s in snapshots
    ), [s["text"][:200] for s in snapshots if __import__("re").search(r"[A-Za-z]{3,}", s["text"])][:2])
    record("player_activity_notice_not_shown_beside_public_window", all(
        s["peer_notice_display"] == "none" and not s["peer_notice_text"].strip() for s in snapshots
    ), [{"display": s["peer_notice_display"], "text": s["peer_notice_text"]} for s in snapshots[:3]])
    all_lines = [
        line for step in ((evidence.get("final_report") or {}).get("steps") or []) for line in step.get("lines", [])
    ]
    record("non_hotseat_single_seat_view_still_uses_player_activity_notice", bool(single_notices)
           and all(n["hotseatMask"] is None and not n["aiWindow"] for n in single_notices), single_notices[:2])
    record("public_report_comes_from_the_game_log", bool(all_lines) and any("AI 紅軍" in line for line in all_lines),
           {"lines": all_lines[:10]})

    click_hold = next((h for h in holds if h["mode"] == "click"), None)
    timeout_hold = next((h for h in holds if h["mode"] == "timeout"), None)

    def hold_ok(h: dict | None) -> bool:
        if not h:
            return False
        b = h["before"]
        return (b["server_awaiting_ack"] and is_red(b) and b["ws_state_awaiting_ack"] is not None
                and b["title"].endswith("回合結束") and b["dismiss_visible"] and b["view"] == "waiting"
                and b["peer_notice_display"] == "none"
                # 整段等待的每一次取樣，權威 current player 都仍是紅軍（Game 物件與 WebSocket state）
                and all(is_red(x) for x in h["samples"] if x["server_awaiting_ack"])
                and sum(1 for x in h["samples"] if x["server_awaiting_ack"]) >= 3)

    record("red_army_stays_authoritative_current_player_while_awaiting_ack_after_turn_end_click_case",
           hold_ok(click_hold) and click_hold["clicked_at"] is not None, click_hold and {
               "before": click_hold["before"], "awaiting_samples": sum(1 for x in click_hold["samples"] if x["server_awaiting_ack"]),
               "clicked_at": click_hold["clicked_at"]})
    # 確認後必須離開 AI 等待狀態並交給下一位。若回合邊界先產生下一位的必要 pending_choice，
    # Game.current_player() 會暫留前一位，但權威 actor 已是下一位；這只允許在視窗已關閉之後。
    click_after = click_hold["after"] if click_hold else None
    click_before = click_hold["before"] if click_hold else None
    direct_next = bool(click_after) and (
        click_after["server_current_player"] == click_after["expected_next_player"]
        and click_after["ws_state_current_player"] == click_after["expected_next_player"]
    )
    pending_next = bool(click_after) and (
        click_after["view"] == "handoff"
        and (click_after.get("actor") or {}).get("kind") == "pending_choice"
        and (click_after.get("actor") or {}).get("name") == click_after["expected_next_player"]
    )
    record("next_player_only_after_ack_click_then_handoff_and_window_closed", bool(click_after)
           and (direct_next or pending_next)
           and not click_after["server_awaiting_ack"] and click_after["view"] == "handoff"
           and click_after["window_open"] is False and click_after["living_room_window_open"] is False
           and bool(click_before) and click_before["living_room"]["ended"] is True and is_red(click_before["living_room"]),
           click_hold and click_hold["after"])
    record("timeout_case_server_waits_about_ten_seconds_with_red_army_current_then_advances",
           hold_ok(timeout_hold) and timeout_hold["clicked_at"] is None and 9.0 <= timeout_hold["elapsed"] <= 13.0
           and timeout_hold["after"]["server_current_player"] == timeout_hold["after"]["expected_next_player"]
           and not timeout_hold["after"]["server_awaiting_ack"],
           timeout_hold and {"elapsed": timeout_hold["elapsed"], "after": timeout_hold["after"]})
    record("rules_flow_continues_after_ai_turn", bool(click_hold and handoff_followup)
           and ((handoff_followup["actor_kind"] == "current_player"
                 and click_hold["after"]["actor"]["name"] == click_hold["after"]["expected_next_player"])
                or (handoff_followup["actor_kind"] == "pending_choice" and click_hold["after"]["actor"]["name"] != red_name))
           and click_hold["before"]["ai_status"].get("state") == "idle"
           and str(handoff_followup["step"]).endswith(":ok"), {
        "ai_status": click_hold and click_hold["before"]["ai_status"], "followup": handoff_followup,
        "next_actor": click_hold and click_hold["after"]["actor"],
    })
    record("window_geometry_centered_and_unclipped_in_both_display_modes", all(
        shots_taken.values()) and all(
        evidence.get(f"geometry_{mode}") is not None
        and 0 <= evidence[f"geometry_{mode}"]["left"] and evidence[f"geometry_{mode}"]["right"] <= 1280
        and 0 <= evidence[f"geometry_{mode}"]["top"] and evidence[f"geometry_{mode}"]["bottom"] <= 720
        and abs((evidence[f"geometry_{mode}"]["left"] + evidence[f"geometry_{mode}"]["right"]) / 2 - 640) <= 1.5
        and abs((evidence[f"geometry_{mode}"]["top"] + evidence[f"geometry_{mode}"]["bottom"]) / 2 - 360) <= 1.5
        for mode in ("desktop", "living-room")
    ), {mode: evidence.get(f"geometry_{mode}") for mode in ("desktop", "living-room")})
    record("browser_console_has_no_errors", not console_errors, console_errors)

    summary = {"total": len(checks), "passed": sum(1 for c in checks if c["passed"])}
    summary["failed"] = summary["total"] - summary["passed"]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "scenario": "兩位真人本機席位（客廳輪流）＋AI 紅軍；視窗顯示整段期間（含回合結束等待確認）權威 current player 都是 red_army；確認或逾時後伺服器才推進到下一位",
        "checks": checks,
        "evidence": evidence,
        "screenshots": sorted(str(p.relative_to(ROOT)) for p in OUT.glob("*.png")),
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    REPORT_MD.write_text("\n".join([
        "# 客廳輪流：AI 紅軍公開行動 Browser 驗證", "",
        f"Summary: **{summary['passed']}/{summary['total']} passed**", "",
        *[f"- {'PASS' if c['passed'] else 'FAIL'}: `{c['name']}`" for c in checks], "",
        "截圖：", *[f"- `{p}`" for p in report["screenshots"]], "",
    ]), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        for c in checks:
            if not c["passed"]:
                print("FAIL", c["name"], json.dumps(c["details"], ensure_ascii=False, default=str)[:600])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
