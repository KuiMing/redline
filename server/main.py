from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from server.game import TurnPhase
from server.card_presentation import (
    ACTION_CSV_PATH,
    CARD_PRESENTATION_CATALOG,
    SUPPORT_CSV_PATH,
    load_card_presentation_catalog,
)
from server.faction_presentation import (
    build_faction_presentation,
    canonical_inside_wall_towns,
    faction_base_options,
    faction_base_resolved,
    faction_category,
    semantic_base_pool,
)
from server.game_manager import manager
from server.lobby_routes import (
    choose_faction,
    create_room,
    join_game,
    lobby,
    lobby_bases,
    lobby_factions,
    lobby_hosts,
    lobby_market_mode,
    lobby_player_credentials,
    lobby_ready,
    lobby_state,
    resume_game,
    set_lobby_market_mode,
    set_ready,
    start_game,
    router as lobby_router,
    _required_faction_for_player,
)
from server.map_data_routes import (
    get_map_data,
    get_map_geo_coordinates,
    get_town_coordinates,
    map_test,
    router as map_data_router,
)
from server.test_routes.registry import register_test_routes
from server.test_routes.runtime import GameSetupRuntime
import os
import asyncio
import secrets

ENABLE_TEST_ROUTES = os.getenv("ENABLE_TEST_ROUTES", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(map_data_router)
app.include_router(lobby_router)

REACTION_RESPONSE_TIMEOUT_SECONDS = 10
reaction_timeout_tasks = {}


async def broadcast_game_state(game_id, game, last_action_result=None):
    dead_connections = []
    for pid, sockets in list(manager.connections.get(game_id, {}).items()):
        state = game.state(pid)
        if last_action_result:
            if last_action_result.get("pending_choice"):
                state["pending_choice"] = game.state(pid).get("pending_choice")
            else:
                state["last_action_result"] = last_action_result
        for ws in list(sockets):
            try:
                await ws.send_json(state)
            except Exception as exc:
                # 一條父頁或地圖連線失效時，只移除該連線。其他連線繼續接收盤面。
                print("WS BROADCAST ERROR:", pid, exc)
                dead_connections.append((pid, ws))
    for pid, ws in dead_connections:
        manager.remove_connection(game_id, pid, ws)


def schedule_reaction_timeout(game_id, game):
    choice = getattr(game, "pending_choice", None) or {}
    if choice.get("type") != "reaction_choice":
        task = reaction_timeout_tasks.pop(game_id, None)
        if task:
            task.cancel()
        return

    token = (
        choice.get("player_id"),
        choice.get("acting_player_id"),
        choice.get("played_card_name"),
        id(choice.get("played_card")),
    )
    old_task = reaction_timeout_tasks.pop(game_id, None)
    if old_task:
        old_task.cancel()

    async def _auto_skip_reaction():
        try:
            await asyncio.sleep(REACTION_RESPONSE_TIMEOUT_SECONDS)
            active_game = manager.get_game(game_id)
            if active_game is not game:
                return
            active_game = game
            active_choice = getattr(active_game, "pending_choice", None) or {}
            active_token = (
                active_choice.get("player_id"),
                active_choice.get("acting_player_id"),
                active_choice.get("played_card_name"),
                id(active_choice.get("played_card")),
            )
            if active_choice.get("type") != "reaction_choice" or active_token != token:
                return
            reacting_player_id = active_choice.get("player_id")
            active_game.log(f"{active_choice.get('played_card_name', 'card')} cancel reaction timed out after {REACTION_RESPONSE_TIMEOUT_SECONDS} seconds; treated as no cancel")
            result = active_game.resolve_pending_choice(reacting_player_id, 0)
            await broadcast_game_state(game_id, active_game, result if isinstance(result, dict) else None)
        except asyncio.CancelledError:
            return
        finally:
            if reaction_timeout_tasks.get(game_id) is asyncio.current_task():
                reaction_timeout_tasks.pop(game_id, None)

    reaction_timeout_tasks[game_id] = asyncio.create_task(_auto_skip_reaction())

_load_card_presentation_catalog = load_card_presentation_catalog


@app.get('/card-presentation')
def card_presentation():
    return {'cards': CARD_PRESENTATION_CATALOG}


@app.get("/server-info")
def server_info(request: Request):
    """回報這次請求實際連線用的網址，供 lobby 顯示「其他玩家連線網址」。

    優先直接採用這次 HTTP 請求本身的 Host（反向代理常見的
    X-Forwarded-Host / X-Forwarded-Proto 優先，其次 request.headers['host']）
    ——而不是靠伺服器自己猜區網 IP。猜測法（UDP connect 技巧，不實際發包、只取
    路由後的本機位址）在直接跑 `uv run` 於主機上時沒問題，但在 Docker（container
    自己的橋接網路 IP，跟主機真正的區網 IP 是兩回事）、或部署到 Render 這類
    PaaS（網域名稱，猜 IP 完全沒有意義）都會給出連不到的位址；「這次請求本來
    就是怎麼連過來的」在這些情境下永遠是對的。
    只有 Host 明顯是 loopback（127.0.0.1／localhost，例如開發者在主機本地
    直接開瀏覽器檢查）且沒有反向代理標頭時，才退回舊的 UDP 探測法——這種情況
    下 Host header 對「該給其他玩家什麼網址」沒有意義，但探測法在裸機環境還是
    能正確測到本機區網 IP（在容器裡就測不到主機的區網 IP，只能測到容器自己的
    橋接位址，所以不在容器情境下使用這個 fallback）。
    """
    from ipaddress import ip_address
    from urllib.parse import urlsplit

    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    host_header = forwarded_host or request.headers.get("host")
    scheme = forwarded_proto or request.url.scheme

    hostname = None
    port = None
    if host_header:
        split = urlsplit(f"//{host_header}")
        hostname = split.hostname
        port = split.port

    if hostname in (None, "127.0.0.1", "localhost", "::1", "0.0.0.0") and not forwarded_host:
        import socket as _socket
        try:
            probe = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            try:
                probe.connect(("8.8.8.8", 80))
                candidate = probe.getsockname()[0]
                if candidate and not candidate.startswith("127."):
                    hostname = candidate
            finally:
                probe.close()
        except OSError:
            pass

    hostname_is_ip = False
    if hostname:
        try:
            ip_address(hostname)
            hostname_is_ip = True
        except ValueError:
            pass

    if port is None and not forwarded_host and (
        hostname_is_ip or hostname in {"localhost", "0.0.0.0"}
    ):
        # 只有直接連到 IP（或本機開發用 hostname）時，才補上伺服器實際監聽的 port。
        # 網域沒有明講 port 時，代表對外使用 scheme 的預設 port；不能把容器內部的
        # 8000 加到 Render 等公開網址後面。反向代理提供的 host 也一律以原值為準。
        server_scope = request.scope.get("server") or (None, None)
        port = server_scope[1] or (request.url.port or 8000)

    default_port = 443 if scheme == "https" else 80
    base_url = None
    if hostname:
        display_hostname = f"[{hostname}]" if ":" in hostname else hostname
        base_url = (
            f"{scheme}://{display_hostname}"
            if port in (None, default_port)
            else f"{scheme}://{display_hostname}:{port}"
        )

    return {"base_url": base_url, "lan_ip": hostname, "port": port}


@app.get("/factions")
def list_factions():
    return build_faction_presentation()


@app.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    supplied_token = websocket.headers.get("sec-websocket-protocol", "").split(",", 1)[0].strip()
    await websocket.accept(subprotocol=supplied_token or None)

    credential = lobby_player_credentials.get(game_id, {}).get(player_id)
    if credential:
        if not supplied_token or not secrets.compare_digest(
            supplied_token, str(credential.get("resume_token") or "")
        ):
            await websocket.send_json({"error": "Resume authentication failed"})
            await websocket.close(code=1008)
            return

    manager.register_connection(game_id, player_id, websocket)

    game = manager.get_game(game_id)

    if not game:
        await websocket.send_json({"error": "Game not ready"})
        return

    # Send initial state
    await websocket.send_json(game.state(player_id))

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "set_base":
                result = game.set_base_choice(player_id, data.get("town"), data.get("label"))
                if result and result.get("error"):
                    error_state = dict(game.state(player_id))
                    error_state["error"] = result.get("error")
                    await websocket.send_json(error_state)
                    continue
                await broadcast_game_state(game_id, game)
                continue

            bypass_turn_check = action in {"relocate_base", "keep_hong_kong_base"}
            if action == "resolve_choice":
                pending_choice = getattr(game, "pending_choice", None) or {}
                bypass_turn_check = pending_choice.get("player_id") == player_id

            current_player = game.current_player()
            if current_player is not None and current_player.id != player_id and not bypass_turn_check:
                debug_state = dict(game.state(player_id))
                debug_state["error"] = "Not your turn"
                debug_state["_debug_turn_gate"] = {
                    "action": action,
                    "player_id": player_id,
                    "current_player_id": current_player.id,
                    "current_player_name": getattr(current_player, "name", None),
                    "bypass_turn_check": bypass_turn_check,
                }
                await websocket.send_json(debug_state)
                continue

            result = {"success": True}

            if action == "advance":
                result = game.advance_turn_phase()
            elif action == "use_topdeck_right":
                result = game.use_pending_topdeck_right()
            elif action == "play_card":
                result = game.play_card(data.get("index"), mode=data.get("mode"), target_player_id=data.get("target_player_id"))
            elif action == "buy_card":
                result = game.buy_card(data.get("index"))
            elif action == "buy_cards":
                result = game.buy_cards(data.get("indices"))
            elif action == "set_base":
                result = game.set_base_choice(player_id, data.get("town"))
            elif action == "build":
                # 建立組織一律走 build_organization()：它會先把玩家目前的待決建立選擇
                # （卡牌／奧援／事件／年代效果產生的 pending choice）在該城鎮上結算。
                # 舊的 `from` 分支會呼叫 build_organization_with_support()，等於給玩家一個
                # 「不用出牌、每回合免費指定起點跨距離建組織」的動作；回合流程（
                # data/turn_flow.v1.1.json 行動階段）並沒有這種動作，它只是安全屋被誤做成
                # 主動按鈕時的後端入口，已隨前端面板一併移除。
                result = game.build_organization(data.get("town"))
            elif action == "move":
                result = game.move_organization(
                    data.get("from"),
                    data.get("to"),
                    data.get("mode", "road")
                )
            elif action == "dissolve":
                defender_name = data.get("defender")
                town = data.get("town")
                defender = next((p for p in game.players if p.name == defender_name or p.id == defender_name), None)
                if not defender:
                    result = {"error": "Defender not found"}
                else:
                    result = game.dissolve_organization(game.current_player(), defender, town, source="faction_action")
            elif action == "faction_action":
                actor = game.current_player()
                action_phase = str(getattr(game, "turn_phase", "")).lower()
                if getattr(actor, "faction_id", None) == "red_army" and action_phase in {"turnphase.event", "event"}:
                    game.turn_phase = TurnPhase.ACTION
                    result = game._activated_faction_action(
                        actor,
                        data.get("name"),
                        guess=data.get("guess"),
                        target_player_id=data.get("target_player_id"),
                    )
                    if not (result and result.get("error")):
                        game.turn_phase = TurnPhase.EVENT
                else:
                    result = game._activated_faction_action(
                        actor,
                        data.get("name"),
                        guess=data.get("guess"),
                        target_player_id=data.get("target_player_id"),
                    )
            elif action == "relocate_base":
                result = game.relocate_hong_kong_base(player_id, data.get("town"))
            elif action == "keep_hong_kong_base":
                result = game.keep_hong_kong_base(player_id)
            elif action == "resolve_choice":
                result = game.resolve_pending_choice(player_id, data.get("index"))
            elif action == "cancel_choice":
                result = game.cancel_pending_choice(player_id)

            if result and result.get("error"):
                error_state = dict(game.state(player_id))
                error_state["error"] = result.get("error")
                await websocket.send_json(error_state)
                continue

            # Broadcast updated state
            action_result = result if isinstance(result, dict) and not result.get("result") else (result.get("result") if isinstance(result, dict) else None)
            schedule_reaction_timeout(game_id, game)
            await broadcast_game_state(game_id, game, action_result)

    except Exception as e:
        print("WS ERROR:", e)
        manager.remove_connection(game_id, player_id, websocket)


@app.get("/")
def index():
    return FileResponse(
        "static/index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


@app.get("/new-game")
def new_game_entry():
    response = RedirectResponse(url="/?new_game=1", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    return response


def _test_runtime_provider():
    return GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )


def _test_manager_provider():
    return manager


def _test_broadcaster_provider():
    return broadcast_game_state


# /test/* routes let a caller directly mutate live game state. They must
# stay off by default in production; local/dev/CI runs opt in explicitly.
# When enabled, register_test_routes mounts each sub-router directly onto
# `app` (unchanged from before this gate existed) so route nesting/order
# stays exactly as scripts/tests/*_test_route.py already assert. When
# disabled, sub-routers are mounted onto a throwaway APIRouter instead so
# the bound test_setup_* callables below still exist for direct in-process
# calls, without ever becoming HTTP-reachable on `app`.
_test_routes = register_test_routes(
    app=app if ENABLE_TEST_ROUTES else APIRouter(),
    runtime_provider=_test_runtime_provider,
    manager_provider=_test_manager_provider,
    broadcaster_provider=_test_broadcaster_provider,
)

# Re-export every bound test_setup_* / test_set_hand callable as a module
# global: several scripts/tests/*_test_route.py files call these directly
# (main.test_setup_x(...)) instead of only via HTTP, for backward
# compatibility with the pre-registry inline-route era. Kept unconditional
# regardless of ENABLE_TEST_ROUTES since it is a direct in-process call, not
# an HTTP-reachable surface.
globals().update(vars(_test_routes))
