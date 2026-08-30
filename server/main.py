from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game, TurnPhase, GamePhase, STATIC_PURCHASE_CARD_SUPPLY
from server.cards import Card
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
from server.game_manager import GameManager
from server.map_data_routes import (
    get_map_data,
    get_map_geo_coordinates,
    get_town_coordinates,
    map_test,
    router as map_data_router,
)
from server.test_routes.bait_exhaustion_ui import BaitExhaustionUiTestRoutes
from server.test_routes.belt_road_red_turn import BeltRoadRedTurnTestRoutes
from server.test_routes.build_queue import BuildQueueRuntime, BuildQueueTestRoutes
from server.test_routes.build_view_persistence import BuildViewPersistenceTestRoutes
from server.test_routes.business_network_transport import BusinessNetworkTransportTestRoutes
from server.test_routes.card_scenario import CardScenarioTestRoutes
from server.test_routes.ccdi_choice import CcdiChoiceTestRoutes
from server.test_routes.destroyed_red_base_marker import DestroyedRedBaseMarkerTestRoutes
from server.test_routes.discard_reshuffle import DiscardReshuffleTestRoutes
from server.test_routes.discard_topdeck_choice import DiscardTopdeckChoiceTestRoutes
from server.test_routes.draw_privacy import DrawPrivacyTestRoutes
from server.test_routes.elite_defection_discard import EliteDefectionDiscardTestRoutes
from server.test_routes.elite_defection_event import EliteDefectionEventTestRoutes
from server.test_routes.end_turn_topdeck import EndTurnTopdeckTestRoutes
from server.test_routes.enemy_occupancy import EnemyOccupancyTestRoutes
from server.test_routes.era_event_layout import EraEventLayoutTestRoutes
from server.test_routes.era_notification import EraNotificationTestRoutes
from server.test_routes.event_card import EventCardTestRoutes
from server.test_routes.expand_results import ExpandResultsTestRoutes
from server.test_routes.force_base_selection import ForceBaseSelectionTestRoutes
from server.test_routes.hand_preview import HandPreviewRuntime, HandPreviewTestRoutes
from server.test_routes.hong_kong_era_red_discard import HongKongEraRedDiscardTestRoutes
from server.test_routes.hong_kong_safehouse import HongKongSafehouseTestRoutes
from server.test_routes.hu_taiwan_shared import HuTaiwanSharedTestRoutes
from server.test_routes.india_support_purchase import IndiaSupportPurchaseTestRoutes
from server.test_routes.inside_wall import InsideWallTestRoutes
from server.test_routes.intel_network import IntelNetworkTestRoutes
from server.test_routes.intel_network_reaction import IntelNetworkReactionTestRoutes
from server.test_routes.manchuria_era_reorder import ManchuriaEraReorderTestRoutes
from server.test_routes.move_confirmation import MoveConfirmationTestRoutes
from server.test_routes.negotiation import NegotiationTestRoutes
from server.test_routes.npc_inner_build import NpcInnerBuildTestRoutes
from server.test_routes.npc_red_dissolve import NpcRedDissolveTestRoutes
from server.test_routes.pending_choice_board_guard import PendingChoiceBoardGuardTestRoutes
from server.test_routes.planning_lobby_ui import PlanningLobbyUiTestRoutes
from server.test_routes.press_advantage import PressAdvantageTestRoutes
from server.test_routes.purchase_deck_ui import PurchaseDeckUiTestRoutes
from server.test_routes.recruit_talent import RecruitTalentTestRoutes
from server.test_routes.red_army_abilities import RedArmyAbilitiesTestRoutes
from server.test_routes.red_support import RedSupportTestRoutes
from server.test_routes.remove_to_purchase import RemoveToPurchaseTestRoutes
from server.test_routes.runtime import GameSetupRuntime
from server.test_routes.scope_audit import ScopeAuditTestRoutes
from server.test_routes.set_hand import SetHandTestRoutes
from server.test_routes.shared_dissolve import SharedDissolveTestRoutes
from server.test_routes.spy import SpyTestRoutes
from server.test_routes.support import SupportTestRoutes
from server.test_routes.support_card_play import SupportCardPlayTestRoutes
from server.test_routes.taiwan_support import TaiwanSupportTestRoutes
from server.test_routes.tibet_era_red_build import TibetEraRedBuildTestRoutes
from server.test_routes.trade_war_event import TradeWarEventTestRoutes
from server.test_routes.trash_choice_ui import TrashChoiceUiTestRoutes
from server.test_routes.underground_party import UndergroundPartyTestRoutes
from server.test_routes.uyghur_era_red_dissolve import UyghurEraRedDissolveTestRoutes
from server.test_routes.victory import VictoryTestRoutes
import uuid
import asyncio
import secrets
import json
from pathlib import Path

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(map_data_router)

manager = GameManager()
lobby = {}        # {game_id: [(player_id, name)]}
lobby_hosts = {}  # {game_id: host_player_id}
lobby_factions = {}  # {game_id: {player_id: faction_id}}
lobby_bases = {}  # {game_id: {player_id: base_name}}
lobby_ready = {}  # {game_id: {player_id: bool}}
lobby_market_mode = {}  # {game_id: "sample_53" | "all_cards"}
lobby_player_credentials = {}  # {game_id: {player_id: {device_id, resume_token}}}
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


@app.post("/create")
def create_room(payload: dict = None):
    game_id = manager.create_room()
    host_id = str(uuid.uuid4())

    # 建房者的「行動代號」以前被無聲忽略（永遠叫 host）；現在採用前端帶來的名字，
    # 空值才 fallback 成 host（2026-07-18 自動桌測發現，2026-07-19 修正）。
    host_name = str((payload or {}).get("name") or "").strip() or "host"
    lobby[game_id] = [(host_id, host_name)]  # host is immediately in lobby
    lobby_hosts[game_id] = host_id
    lobby_factions[game_id] = {}
    lobby_bases[game_id] = {}
    lobby_ready[game_id] = {host_id: False}
    lobby_market_mode[game_id] = "sample_53"
    device_id = str((payload or {}).get("device_id") or "").strip()
    resume_token = secrets.token_urlsafe(32)
    lobby_player_credentials[game_id] = {
        host_id: {"device_id": device_id, "resume_token": resume_token}
    }

    return {"game_id": game_id, "host_id": host_id, "resume_token": resume_token}


@app.post("/join")
def join_game(payload: dict):
    game_id = payload.get("game_id")
    name = str(payload.get("name") or "").strip()
    requested_player_id = str(payload.get("player_id") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    requested_resume_token = str(payload.get("resume_token") or "").strip()

    if game_id not in lobby:
        return {"error": "Game not found"}

    if not name:
        return {"error": "Name required"}

    credentials = lobby_player_credentials.setdefault(game_id, {})
    if requested_player_id:
        for idx, (pid, _) in enumerate(lobby[game_id]):
            if pid != requested_player_id:
                continue
            credential = credentials.get(pid) or {}
            token_matches = bool(requested_resume_token) and secrets.compare_digest(
                requested_resume_token, str(credential.get("resume_token") or "")
            )
            device_matches = bool(device_id) and device_id == credential.get("device_id")
            if credential and not (token_matches or device_matches):
                return {"error": "Resume authentication failed"}
            lobby[game_id][idx] = (requested_player_id, name)
            lobby_ready.setdefault(game_id, {}).setdefault(requested_player_id, False)
            return {
                "player_id": requested_player_id,
                "resume_token": credential.get("resume_token"),
                "resumed": True,
            }

    if len(lobby[game_id]) >= 4:
        return {"error": "Room full"}

    player_id = str(uuid.uuid4())
    resume_token = secrets.token_urlsafe(32)
    lobby[game_id].append((player_id, name))
    lobby_ready.setdefault(game_id, {})[player_id] = False
    credentials[player_id] = {"device_id": device_id, "resume_token": resume_token}
    return {"player_id": player_id, "resume_token": resume_token, "resumed": False}


@app.post("/resume")
def resume_game(payload: dict):
    game_id = str(payload.get("game_id") or "").strip()
    player_id = str(payload.get("player_id") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    resume_token = str(payload.get("resume_token") or "").strip()
    if game_id not in lobby:
        return {"error": "Game not found"}
    seat = next(((pid, name) for pid, name in lobby[game_id] if pid == player_id), None)
    if seat is None:
        return {"error": "Player not found in lobby"}
    credential = lobby_player_credentials.get(game_id, {}).get(player_id) or {}
    token_matches = bool(resume_token) and secrets.compare_digest(
        resume_token, str(credential.get("resume_token") or "")
    )
    device_matches = bool(device_id) and device_id == credential.get("device_id")
    if not credential or not (token_matches or device_matches):
        return {"error": "Resume authentication failed"}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": player_id,
        "name": seat[1],
        "resume_token": credential.get("resume_token"),
        "started": manager.games.get(game_id) is not None,
        "faction_id": lobby_factions.get(game_id, {}).get(player_id),
        "base": lobby_bases.get(game_id, {}).get(player_id),
    }


def _required_faction_for_player(game_id: str, player_id: str):
    """Return the faction forced by the remaining-seat rule, if any."""
    players = lobby.get(game_id, [])
    chosen = lobby_factions.get(game_id, {})
    has_red_army = any(fid == 'red_army' for fid in chosen.values())
    if len(players) == 4 and not has_red_army and players[-1][0] == player_id:
        return 'red_army'
    return None


@app.post("/market-mode")
def set_lobby_market_mode(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")
    market_mode = payload.get("market_mode")

    if game_id not in lobby:
        return {"error": "Game not found"}
    if lobby_hosts.get(game_id) != player_id:
        return {"error": "Only host can change game difficulty"}
    if manager.games.get(game_id) is not None:
        return {"error": "Game already started"}
    if market_mode not in {"sample_53", "all_cards"}:
        return {"error": "Invalid game difficulty"}

    lobby_market_mode[game_id] = market_mode
    return {"success": True, "market_mode": market_mode}


@app.post("/start")
def start_game(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")
    market_mode = payload.get("market_mode")

    if game_id not in lobby:
        return {"error": "Game not found"}

    if len(lobby[game_id]) < 2:
        return {"error": "Need at least 2 players"}

    if lobby_hosts.get(game_id) != player_id:
        return {"error": "Only host can start"}

    player_list = lobby[game_id]
    ready = lobby_ready.setdefault(game_id, {})
    for pid, _ in player_list:
        ready.setdefault(pid, False)
    if any(not ready.get(pid, False) for pid, _ in player_list):
        return {"error": "All players must be ready before start"}

    if market_mode in {"sample_53", "all_cards"}:
        lobby_market_mode[game_id] = market_mode

    # For test/setup endpoints that already created a live game state,
    # preserve the prepared runtime instead of rebuilding a fresh one.
    if manager.games.get(game_id) is not None:
        return {"success": True, "reused": True}

    chosen = lobby_factions.get(game_id, {})
    if len(chosen) != len(player_list):
        return {"error": "All players must choose factions first"}
    if sum(1 for fid in chosen.values() if fid == 'red_army') != 1:
        return {"error": "必須有且只能有一名玩家選擇紅軍，才能啟動行動"}

    game = Game(player_list, market_mode=lobby_market_mode.get(game_id, "sample_53"))
    # override randomized faction assignment with chosen factions
    chosen_bases = lobby_bases.get(game_id, {})
    for player in game.players:
        if player.id in chosen:
            player.faction_id = chosen[player.id]
    # Rebuild starting decks after lobby faction overrides so faction-specific
    # starter cards such as 紅軍奧援 are assigned to the actual chosen faction.
    game._init_decks()
    game.faction_by_id = {f["id"]: f for f in game.factions}
    game.faction_by_id.update({
        "uyghur_family": {
            "id": "uyghur_family",
            "name": "維吾爾",
            "camp": "uyghur",
            "bases": [
                {"name": "伊斯坦堡", "variant_faction": "uyghur_istanbul"},
                {"name": "慕尼黑", "variant_faction": "uyghur_munich"},
                {"name": "華盛頓", "variant_faction": "uyghur_washington"},
                {"name": "阿拉木圖", "variant_faction": "uyghur_almaty"},
            ],
        },
        "tibet_family": {
            "id": "tibet_family",
            "name": "西藏",
            "camp": "tibet",
            "bases": [
                {"name": "達蘭薩拉", "variant_faction": "tibet_dharamsala"},
                {"name": "德拉敦", "variant_faction": "tibet_dehradun"},
                {"name": "哲古宗", "variant_faction": "tibet_chogu"},
            ],
        },
    })
    chosen_base_names = [base for player_id, base in chosen_bases.items() if player_id in {p.id for p in game.players} and base]
    duplicate_bases = sorted({base for base in chosen_base_names if chosen_base_names.count(base) > 1})
    if duplicate_bases:
        return {"error": f"Base already taken: {'、'.join(duplicate_bases)}"}

    for player in game.players:
        base_name = chosen_bases.get(player.id)
        if not base_name:
            continue
        faction = game.faction_by_id.get(player.faction_id, {})
        if player.faction_id in {"uyghur_family", "tibet_family"}:
            variant_map = {b.get("name"): b.get("variant_faction") for b in faction.get("bases", [])}
            player.faction_id = variant_map.get(base_name, player.faction_id)
        player.base = base_name
        player.organizations = {base_name: 1}
    game.static_purchase_supply = dict(STATIC_PURCHASE_CARD_SUPPLY)
    for player in game.players:
        game._apply_setup_abilities(player)
    game.pending_base_choices = game._compute_pending_base_choices()
    if game.pending_base_choices:
        game.game_phase = GamePhase.BASE_SELECTION
    else:
        game._assign_starting_bases()
        game.game_phase = GamePhase.MAIN
        first_non_red = next((idx for idx, player in enumerate(game.players) if player.faction_id != 'red_army'), 0)
        game.current_player_index = first_non_red
        game.round_start_player_index = first_non_red
        if game.turn_phase in {TurnPhase.EVENT, TurnPhase.ACTION} and not game.current_event:
            game._start_event_phase()

    manager.games[game_id] = game
    manager.connections.setdefault(game_id, {})

    return {"success": True, "market_mode": lobby_market_mode.get(game_id, "sample_53")}


@app.get("/factions")
def list_factions():
    return build_faction_presentation()


@app.post("/choose-faction")
def choose_faction(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")
    faction_id = payload.get("faction_id")
    base_name = payload.get("base_name")

    if game_id not in lobby:
        return {"error": "Game not found"}

    if player_id not in [pid for pid, _ in lobby[game_id]]:
        return {"error": "Player not found in lobby"}

    from pathlib import Path
    import json
    path = Path(__file__).resolve().parent.parent / "data" / "factions" / "all_faction.integrated.v2.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by_id = {x["id"]: x for x in data["factions"]}

    # prevent duplicate category selection (主陣營唯一)
    taken = lobby_factions.get(game_id, {})
    wanted_category = faction_category(faction_id)
    required_faction = _required_faction_for_player(game_id, player_id)
    if required_faction and faction_id != required_faction:
        return {"error": "房間尚無紅軍；最後一個席位只能選擇紅軍"}
    if any(pid != player_id and faction_category(fid) == wanted_category for pid, fid in taken.items()):
        return {"error": "Faction category already taken"}

    valid_bases = faction_base_options(by_id, faction_id)
    resolved_bases = faction_base_resolved(by_id, faction_id)
    if base_name:
        valid_towns = {town for towns in resolved_bases.values() for town in towns}
        if base_name not in valid_towns:
            return {"error": "Invalid base option"}
        occupied_bases = lobby_bases.get(game_id, {})
        if any(pid != player_id and chosen_base == base_name for pid, chosen_base in occupied_bases.items()):
            return {"error": "Base already taken"}

    lobby_factions.setdefault(game_id, {})[player_id] = faction_id
    lobby_ready.setdefault(game_id, {})[player_id] = False
    if base_name:
        lobby_bases.setdefault(game_id, {})[player_id] = base_name
    else:
        lobby_bases.setdefault(game_id, {}).pop(player_id, None)
    return {"success": True, "factions": lobby_factions[game_id], "bases": lobby_bases.get(game_id, {})}


@app.post("/ready")
def set_ready(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")
    is_ready = bool(payload.get("ready"))

    if game_id not in lobby:
        return {"error": "Game not found"}
    if player_id not in [pid for pid, _ in lobby[game_id]]:
        return {"error": "Player not found in lobby"}
    if is_ready and player_id not in lobby_factions.get(game_id, {}):
        return {"error": "Choose faction before ready"}

    ready = lobby_ready.setdefault(game_id, {})
    ready[player_id] = is_ready
    return {"success": True, "ready": ready}


@app.get("/lobby/{game_id}")
def lobby_state(game_id: str):
    if game_id not in lobby:
        return {"error": "Game not found"}

    ready = lobby_ready.setdefault(game_id, {})
    for pid, _ in lobby[game_id]:
        ready.setdefault(pid, False)

    return {
        "players": lobby[game_id],
        "host_id": lobby_hosts.get(game_id),
        "count": len(lobby[game_id]),
        "factions": lobby_factions.get(game_id, {}),
        "bases": lobby_bases.get(game_id, {}),
        "ready": ready,
        "started": manager.games.get(game_id) is not None,
        "market_mode": lobby_market_mode.get(game_id, "sample_53"),
        "required_faction_by_player": {
            pid: required
            for pid, _ in lobby[game_id]
            if (required := _required_faction_for_player(game_id, pid))
        },
    }


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


_set_hand_test_routes = SetHandTestRoutes(lambda: manager)
app.include_router(_set_hand_test_routes.router)
test_set_hand = _set_hand_test_routes.test_set_hand


_build_view_persistence_test_routes = BuildViewPersistenceTestRoutes(
    lambda: manager,
    lambda: broadcast_game_state,
)
app.include_router(_build_view_persistence_test_routes.router)
test_setup_build_view_persistence_proof = (
    _build_view_persistence_test_routes.test_setup_build_view_persistence_proof
)


_build_queue_test_routes = BuildQueueTestRoutes(
    lambda: BuildQueueRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_build_queue_test_routes.router)
test_setup_build_queue_proof = (
    _build_queue_test_routes.test_setup_build_queue_proof
)


_negotiation_test_routes = NegotiationTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_negotiation_test_routes.router)
test_setup_negotiation_proof = (
    _negotiation_test_routes.test_setup_negotiation_proof
)


_scope_audit_test_routes = ScopeAuditTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_scope_audit_test_routes.router)
test_setup_scope_audit_proof = (
    _scope_audit_test_routes.test_setup_scope_audit_proof
)


_inside_wall_test_routes = InsideWallTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_inside_wall_test_routes.router)
test_setup_inside_wall_proof = (
    _inside_wall_test_routes.test_setup_inside_wall_proof
)


_card_scenario_test_routes = CardScenarioTestRoutes(lambda: manager)
app.include_router(_card_scenario_test_routes.router)
test_setup_card_scenario = _card_scenario_test_routes.test_setup_card_scenario


_force_base_selection_test_routes = ForceBaseSelectionTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_force_base_selection_test_routes.router)
test_force_base_selection = (
    _force_base_selection_test_routes.test_force_base_selection
)


_intel_network_test_routes = IntelNetworkTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_intel_network_test_routes.router)
test_setup_intel_network_proof = (
    _intel_network_test_routes.test_setup_intel_network_proof
)


_press_advantage_test_routes = PressAdvantageTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_press_advantage_test_routes.router)
test_setup_press_advantage_proof = (
    _press_advantage_test_routes.test_setup_press_advantage_proof
)


_expand_results_test_routes = ExpandResultsTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_expand_results_test_routes.router)
test_setup_expand_results_proof = (
    _expand_results_test_routes.test_setup_expand_results_proof
)


_intel_network_reaction_test_routes = IntelNetworkReactionTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_intel_network_reaction_test_routes.router)
test_setup_intel_network_cancel_reaction_proof = (
    _intel_network_reaction_test_routes.test_setup_intel_network_cancel_reaction_proof
)
test_resolve_intel_network_cancel_reaction_proof = (
    _intel_network_reaction_test_routes.test_resolve_intel_network_cancel_reaction_proof
)


_hong_kong_safehouse_test_routes = HongKongSafehouseTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_hong_kong_safehouse_test_routes.router)
test_setup_hong_kong_safehouse = (
    _hong_kong_safehouse_test_routes.test_setup_hong_kong_safehouse
)


_pending_choice_board_guard_test_routes = PendingChoiceBoardGuardTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_pending_choice_board_guard_test_routes.router)
test_setup_pending_choice_board_guard = (
    _pending_choice_board_guard_test_routes.test_setup_pending_choice_board_guard
)


_enemy_occupancy_test_routes = EnemyOccupancyTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_enemy_occupancy_test_routes.router)
test_setup_enemy_occupancy_proof = (
    _enemy_occupancy_test_routes.test_setup_enemy_occupancy_proof
)


_move_confirmation_test_routes = MoveConfirmationTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_move_confirmation_test_routes.router)
test_setup_move_confirmation_proof = (
    _move_confirmation_test_routes.test_setup_move_confirmation_proof
)


_destroyed_red_base_marker_test_routes = DestroyedRedBaseMarkerTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_destroyed_red_base_marker_test_routes.router)
test_setup_destroyed_red_base_marker_proof = (
    _destroyed_red_base_marker_test_routes.test_setup_destroyed_red_base_marker_proof
)


_hu_taiwan_shared_test_routes = HuTaiwanSharedTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_hu_taiwan_shared_test_routes.router)
test_setup_hu_taiwan_shared = (
    _hu_taiwan_shared_test_routes.test_setup_hu_taiwan_shared
)


_shared_dissolve_test_routes = SharedDissolveTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_shared_dissolve_test_routes.router)
test_setup_shared_dissolve = (
    _shared_dissolve_test_routes.test_setup_shared_dissolve
)


_india_support_purchase_test_routes = IndiaSupportPurchaseTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_india_support_purchase_test_routes.router)
test_setup_india_support_purchase = (
    _india_support_purchase_test_routes.test_setup_india_support_purchase
)


_remove_to_purchase_test_routes = RemoveToPurchaseTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_remove_to_purchase_test_routes.router)
test_setup_remove_to_purchase = (
    _remove_to_purchase_test_routes.test_setup_remove_to_purchase
)


_underground_party_test_routes = UndergroundPartyTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_underground_party_test_routes.router)
test_setup_underground_party = (
    _underground_party_test_routes.test_setup_underground_party
)


_recruit_talent_test_routes = RecruitTalentTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_recruit_talent_test_routes.router)
test_setup_recruit_talent_proof = (
    _recruit_talent_test_routes.test_setup_recruit_talent_proof
)


_support_card_play_test_routes = SupportCardPlayTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_support_card_play_test_routes.router)
test_setup_support_card_play = (
    _support_card_play_test_routes.test_setup_support_card_play
)


_purchase_deck_ui_test_routes = PurchaseDeckUiTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_purchase_deck_ui_test_routes.router)
test_setup_purchase_deck_ui = (
    _purchase_deck_ui_test_routes.test_setup_purchase_deck_ui
)


_hand_preview_test_routes = HandPreviewTestRoutes(
    lambda: HandPreviewRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_hand_preview_test_routes.router)
test_setup_hand_preview = _hand_preview_test_routes.test_setup_hand_preview


_end_turn_topdeck_test_routes = EndTurnTopdeckTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_end_turn_topdeck_test_routes.router)
test_setup_end_turn_topdeck_proof = (
    _end_turn_topdeck_test_routes.test_setup_end_turn_topdeck_proof
)


_business_network_transport_test_routes = BusinessNetworkTransportTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_business_network_transport_test_routes.router)
test_setup_business_network_transport_proof = (
    _business_network_transport_test_routes.test_setup_business_network_transport_proof
)


_planning_lobby_ui_test_routes = PlanningLobbyUiTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_planning_lobby_ui_test_routes.router)
test_setup_planning_lobby_ui = (
    _planning_lobby_ui_test_routes.test_setup_planning_lobby_ui
)


_trash_choice_ui_test_routes = TrashChoiceUiTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_trash_choice_ui_test_routes.router)
test_setup_trash_choice_ui = (
    _trash_choice_ui_test_routes.test_setup_trash_choice_ui
)


_red_support_test_routes = RedSupportTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_red_support_test_routes.router)
test_setup_red_support_proof = (
    _red_support_test_routes.test_setup_red_support_proof
)


_red_army_abilities_test_routes = RedArmyAbilitiesTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_red_army_abilities_test_routes.router)
test_setup_red_army_abilities_proof = (
    _red_army_abilities_test_routes.test_setup_red_army_abilities_proof
)


_spy_test_routes = SpyTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_spy_test_routes.router)
test_setup_spy_proof = _spy_test_routes.test_setup_spy_proof


_victory_test_routes = VictoryTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_victory_test_routes.router)
test_setup_victory_proof = _victory_test_routes.test_setup_victory_proof


_draw_privacy_test_routes = DrawPrivacyTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    ),
    lambda: broadcast_game_state,
)
app.include_router(_draw_privacy_test_routes.router)
test_setup_draw_privacy_proof = (
    _draw_privacy_test_routes.test_setup_draw_privacy_proof
)
test_trigger_draw_privacy_proof = (
    _draw_privacy_test_routes.test_trigger_draw_privacy_proof
)


_elite_defection_discard_test_routes = EliteDefectionDiscardTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_elite_defection_discard_test_routes.router)
test_setup_elite_defection_discard_proof = (
    _elite_defection_discard_test_routes.test_setup_elite_defection_discard_proof
)


_discard_reshuffle_test_routes = DiscardReshuffleTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_discard_reshuffle_test_routes.router)
test_setup_discard_reshuffle_proof = (
    _discard_reshuffle_test_routes.test_setup_discard_reshuffle_proof
)


_support_test_routes = SupportTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_support_test_routes.router)
test_setup_support_proof = _support_test_routes.test_setup_support_proof


_taiwan_support_test_routes = TaiwanSupportTestRoutes(test_setup_support_proof)
app.include_router(_taiwan_support_test_routes.router)
test_setup_taiwan_support_proof = (
    _taiwan_support_test_routes.test_setup_taiwan_support_proof
)


_bait_exhaustion_ui_test_routes = BaitExhaustionUiTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
    )
)
app.include_router(_bait_exhaustion_ui_test_routes.router)
test_setup_bait_exhaustion_ui = (
    _bait_exhaustion_ui_test_routes.test_setup_bait_exhaustion_ui
)


_manchuria_era_reorder_test_routes = ManchuriaEraReorderTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_manchuria_era_reorder_test_routes.router)
test_setup_manchuria_era_reorder_proof = (
    _manchuria_era_reorder_test_routes.test_setup_manchuria_era_reorder_proof
)


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


_event_card_test_routes = EventCardTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_event_card_test_routes.router)
test_setup_event_card_proof = _event_card_test_routes.test_setup_event_card_proof


_npc_red_dissolve_test_routes = NpcRedDissolveTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_npc_red_dissolve_test_routes.router)
test_setup_national_people_congress_red_dissolve_proof = (
    _npc_red_dissolve_test_routes.test_setup_national_people_congress_red_dissolve_proof
)


_npc_inner_build_test_routes = NpcInnerBuildTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_npc_inner_build_test_routes.router)
test_setup_national_people_congress_inner_build_proof = (
    _npc_inner_build_test_routes.test_setup_national_people_congress_inner_build_proof
)


_trade_war_event_test_routes = TradeWarEventTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_trade_war_event_test_routes.router)
test_setup_trade_war_event_proof = (
    _trade_war_event_test_routes.test_setup_trade_war_event_proof
)


_discard_topdeck_choice_test_routes = DiscardTopdeckChoiceTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_discard_topdeck_choice_test_routes.router)
test_setup_discard_topdeck_choice = (
    _discard_topdeck_choice_test_routes.test_setup_discard_topdeck_choice
)


_ccdi_choice_test_routes = CcdiChoiceTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_ccdi_choice_test_routes.router)
test_setup_ccdi_choice = _ccdi_choice_test_routes.test_setup_ccdi_choice


_elite_defection_event_test_routes = EliteDefectionEventTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_elite_defection_event_test_routes.router)
test_setup_elite_defection_event_proof = (
    _elite_defection_event_test_routes.test_setup_elite_defection_event_proof
)


_belt_road_red_turn_test_routes = BeltRoadRedTurnTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    ),
    lambda: broadcast_game_state,
)
app.include_router(_belt_road_red_turn_test_routes.router)
test_setup_belt_road_red_turn_proof = (
    _belt_road_red_turn_test_routes.test_setup_belt_road_red_turn_proof
)


_tibet_era_red_build_test_routes = TibetEraRedBuildTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_tibet_era_red_build_test_routes.router)
test_setup_tibet_era_red_build_proof = (
    _tibet_era_red_build_test_routes.test_setup_tibet_era_red_build_proof
)


_era_event_layout_test_routes = EraEventLayoutTestRoutes(lambda: manager)
app.include_router(_era_event_layout_test_routes.router)
test_setup_era_event_layout_proof = (
    _era_event_layout_test_routes.test_setup_era_event_layout_proof
)


_era_notification_test_routes = EraNotificationTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_era_notification_test_routes.router)
test_setup_era_notification_proof = (
    _era_notification_test_routes.test_setup_era_notification_proof
)


_hong_kong_era_red_discard_test_routes = HongKongEraRedDiscardTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_hong_kong_era_red_discard_test_routes.router)
test_setup_hong_kong_era_red_discard_proof = (
    _hong_kong_era_red_discard_test_routes.test_setup_hong_kong_era_red_discard_proof
)


_uyghur_era_red_dissolve_test_routes = UyghurEraRedDissolveTestRoutes(
    lambda: GameSetupRuntime(
        manager=manager,
        lobby=lobby,
        lobby_hosts=lobby_hosts,
        lobby_factions=lobby_factions,
        lobby_bases=lobby_bases,
        lobby_ready=lobby_ready,
    )
)
app.include_router(_uyghur_era_red_dissolve_test_routes.router)
test_setup_uyghur_era_red_dissolve_proof = (
    _uyghur_era_red_dissolve_test_routes.test_setup_uyghur_era_red_dissolve_proof
)


@app.post("/test/setup-urumqi-event-proof")
def test_setup_urumqi_event_proof(payload: dict):
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = "taiwan_green"
    red.faction_id = "red_army"
    viewer.base = "臺北"
    red.base = "北京"
    viewer.organizations = {"北京": 1}
    red.organizations = {"北京": 1}
    viewer.resources = {"money": 0, "propaganda": 0}
    viewer.hand = [Card("保留手牌", "command", {})]
    viewer.deck.draw_pile = [Card("牌庫保留", "command", {})]
    viewer.deck.discard_pile = []
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    event = game._event_by_name("烏魯木齊七五事件")
    game.current_event = event
    game.event_progress = {
        "count": 0,
        "required": int((event or {}).get("trigger", {}).get("count", 1) or 1),
        "succeeded": False,
        "settled": False,
        "status": "active",
    }
    game.event_notification = game._event_display_payload()
    game.event_deck.draw_pile = []
    game.event_deck.discard_pile = []

    if payload.get("settle", True):
        game.advance_turn_phase()

    game_id = str(uuid.uuid4())
    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "red_player_id": red.id,
        "event_name": event.get("name") if event else None,
        "url": f"/?game_id={game_id}&player_id={viewer.id}",
        "state": game.state(),
    }


@app.post("/test/setup-faction-action-used-proof")
def test_setup_faction_action_used_proof(payload: dict):
    """Proof setup for the 2026-08-09 playtest bug: a faction with a one-per-turn activated
    ability (澳門/賭徒耳語 by default) that has ALREADY used it this turn should not have the
    centred faction-action modal keep force-reopening every time an unrelated action (e.g.
    playing a hand card as a resource) triggers a re-render."""
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "opponent")]
    game = Game(players)

    viewer = game.players[0]
    opponent = game.players[1]

    faction_id = payload.get("faction_id", "aomen")
    resource_card_name = payload.get("resource_card_name", "領導")
    faction_action_used = payload.get("faction_action_used", True)

    def proof_card(name):
        entry = next((c for c in game.structured_cards if c.get("name") == name), None)
        if entry:
            return Card(entry["name"], entry.get("type", "command"), dict(entry.get("resources", {}) or {}))
        return Card(name, "command", {})

    viewer.faction_id = faction_id
    viewer.base = payload.get("base", "澳門城")
    viewer.organizations = {viewer.base: 1}
    viewer.resources = {"money": 0, "propaganda": 0}
    viewer.hand = [proof_card(resource_card_name)]
    viewer.deck.draw_pile = [proof_card(name) for name in (payload.get("draw_pile") or ["補牌1", "補牌2"])]
    viewer.deck.discard_pile = []

    opponent.faction_id = "red_army"
    opponent.base = "北京"
    opponent.organizations = {"北京": 1}
    opponent.hand = []

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.pending_choice = None
    # 固定換成無效果的歲月靜好，避免隨機抽到互動型事件在 setup 當下就掛一個 pending_choice，
    # 讓這支 proof 端點的行為與初始 Game() 建構時抽到什麼事件脫鉤、可穩定重跑。
    noop_event = game._event_by_name("歲月靜好")
    game.current_event = dict(noop_event or {})
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    game.turn_log["faction_action_used"] = bool(faction_action_used)
    game.id = game_id
    game.log(f"UI proof setup: viewer already used this turn's faction action ({faction_id}).")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, opponent.id: opponent.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, opponent.id: opponent.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "resource_card_name": resource_card_name,
        "state": game.state(),
    }


@app.post("/test/setup-show-strength-choice-proof")
def test_setup_show_strength_choice_proof(payload: dict):
    """建立「展現實力」已達成且等待能力擁有者選擇獎勵的 Browser proof。"""
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "滿洲玩家"), (str(uuid.uuid4()), "紅軍玩家")]
    game = Game(players)
    player, red = game.players

    player.faction_id = "manchuria"
    player.base = "東京"
    player.organizations = {"東京": 1}
    player.resources = {"money": 0, "propaganda": 0}
    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    game.current_player_index = 0
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.pending_base_choices = {}
    game.turn_log = game._new_turn_log()
    game.turn_log["played_nonstarter_names"] = ["甲", "乙", "丙"]
    game.current_event = None
    game.event_progress = {}
    game.event_modifiers = []
    game.id = game_id

    game._apply_card_play_faction_abilities(player, cost_has_money=False, cost_has_propaganda=False)

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(candidate.id, candidate.name) for candidate in game.players]
    lobby_hosts[game_id] = player.id
    lobby_factions[game_id] = {player.id: player.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {player.id: player.base, red.id: red.base}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": player.id,
        "pending_choice": game.pending_choice,
        "resources": dict(player.resources),
    }


@app.post("/test/setup-peer-choice-notice-proof")
def test_setup_peer_choice_notice_proof(payload: dict):
    """Proof setup for the 2026-08-09 playtest request: when a card (e.g. 武裝小隊) forces the
    OTHER player into a pending choice they must resolve (e.g. choosing which card to discard),
    that player's screen should go straight to the choice UI — not force them to first minimize
    the big "peer action notice" broadcast overlay about the card that was just played."""
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "actor"), (str(uuid.uuid4()), "viewer")]
    game = Game(players)

    actor = game.players[0]
    viewer = game.players[1]

    source_name = payload.get("source_name", "武裝小隊")
    hand_names = payload.get("viewer_hand", ["情報網", "領導", "謀劃"])

    def proof_card(name):
        entry = next((c for c in game.structured_cards if c.get("name") == name), None)
        if entry:
            return Card(entry["name"], entry.get("type", "command"), dict(entry.get("resources", {}) or {}))
        return Card(name, "command", {})

    actor.faction_id = payload.get("actor_faction_id", "red_army")
    actor.base = "北京"
    actor.organizations = {"北京": 1}
    actor.hand = []
    actor.deck.discard_pile = []

    viewer.faction_id = payload.get("viewer_faction_id", "liberals")
    viewer.base = payload.get("viewer_base", "德拉敦")
    viewer.organizations = {viewer.base: 1}
    viewer.hand = [proof_card(name) for name in hand_names]
    viewer.deck.draw_pile = [Card("補牌", "command", {})]
    viewer.deck.discard_pile = []

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    noop_event = game._event_by_name("歲月靜好")
    game.current_event = dict(noop_event or {})
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    game.id = game_id

    # 直接建立 armed_target_discard pending choice（比照 effect_engine.py 的 force_discard
    # 分支對武裝系列卡牌的真正處理方式），略過武裝卡本身的合法目標檢查，聚焦在驗證
    # 「viewer 是否直接看到選擇視窗，而不是先被通知疊層擋住」這件事本身。
    game._set_pending_card_choice(
        viewer,
        'armed_target_discard',
        list(viewer.hand),
        f'{source_name}：從所有手牌中棄掉任 1 張牌。',
        source_name=source_name,
        initiator_player_id=actor.id,
        initiator_player_name=actor.name,
        target_player_name=viewer.name,
    )
    game.log(f"{actor.name} used {source_name} to ask {viewer.name} to choose 1 discard(s)")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = actor.id
    lobby_factions[game_id] = {actor.id: actor.faction_id, viewer.id: viewer.faction_id}
    lobby_bases[game_id] = {actor.id: actor.base, viewer.id: viewer.base}

    return {
        "success": True,
        "game_id": game_id,
        "actor_player_id": actor.id,
        "viewer_player_id": viewer.id,
        "state": game.state(),
    }


@app.post("/test/setup-safehouse-range-proof")
def test_setup_safehouse_range_proof(payload: dict):
    """Proof setup for the 2026-08-09 playtest bug: 安全屋 是被動能力（passive），
    不該有任何專屬按鈕／面板／地圖捷徑；它唯一的表現方式，是玩家用正常方式（打出帶
    build 效果的行動卡）建立組織時，牆內目標的可建立距離 +1。

    payload:
      base: "臺北"（預設）或 "香港城"，兩個都是帶安全屋的香港根據地。
      card: 選填，發一張指定的行動卡到 viewer 手上，用來證明「卡牌觸發的建立候選
            清單仍然含有 2 格外的牆內城鎮」（正面案例，例：組織經驗丙）。
    """
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "opponent")]
    game = Game(players)

    viewer = game.players[0]
    opponent = game.players[1]

    base = payload.get("base", "臺北")

    viewer.faction_id = "hong_kong"
    viewer.base = base
    viewer.organizations = {base: 1}
    viewer.hand = []
    viewer.deck.draw_pile = []
    viewer.deck.discard_pile = []

    card_name = payload.get("card")
    if card_name:
        card_def = next((c for c in game.structured_cards if c.get("name") == card_name), None)
        if not card_def:
            return {"error": f"找不到卡牌：{card_name}"}
        viewer.hand = [Card(card_def["name"], card_def["type"], card_def.get("resources", {}) or {})]

    opponent.faction_id = "red_army"
    opponent.base = "北京"
    opponent.organizations = {"北京": 1}
    opponent.hand = []

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    noop_event = game._event_by_name("歲月靜好")
    game.current_event = dict(noop_event or {})
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, opponent.id: opponent.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, opponent.id: opponent.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "state": game.state(),
    }


@app.post("/test/setup-era-restrict-ignore-distance-proof")
def test_setup_era_restrict_ignore_distance_proof(payload: dict):
    """2026-08-09 playtest 回報的兩個問題共用的驗證場景：

    1. 時代關卡的 `restrict_ignore_distance_build` 紅色壓制（[反賊]公知世代的終結、
       [哈薩克]伊塔事件）生效後，思想家／組織經驗甲／東洋奧援 不該再無視距離建立
       牆內組織，只能退回己方組織 1 格內（另有增加建立距離的能力時為 2 格）；牆外
       仍維持無視距離。
    2. 「時代關卡達成」浮窗縮小之後，任何玩家（不只觸發者）都要能再點右上角的釘選
       卡片重新看到完整說明。

    payload:
      era: 時代 id，預設 "rebels"；"kazakh" 可驗證同型效果的泛用性。
      faction: 觸發方陣營，預設 "liberals"（rebel 陣營）。
      origin: 觸發方既有組織所在城鎮，預設 "上海"。
      card: 選填，發一張指定行動卡到觸發方手上（例：思想家）。
      build_range_bonus: 選填整數，用來驗證退回距離會加成到 2 格。
      extra_eras: 選填的時代 id 陣列，與 era 一併啟用——用來驗證四人局可能同時有多個
        時代關卡生效時，指揮中心提示列與釘選卡片能各自對應正確的時代（2026-08-09
        使用者回報：分頁上方的提示列比右上角釘選卡片更該是點擊入口）。
    """
    era_id = payload.get("era", "rebels")
    extra_era_ids = payload.get("extra_eras") or []
    faction_id = payload.get("faction", "liberals")
    origin = payload.get("origin", "上海")

    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "opponent")]
    game = Game(players)
    viewer, opponent = game.players

    viewer.faction_id = faction_id
    viewer.base = origin
    viewer.organizations = {origin: 1}
    viewer.hand = []
    viewer.deck.draw_pile = []
    viewer.deck.discard_pile = []
    viewer.build_range_bonus = int(payload.get("build_range_bonus", 0) or 0)

    opponent.faction_id = "red_army"
    opponent.base = "北京"
    opponent.organizations = {"北京": 1}
    opponent.hand = []

    card_name = payload.get("card")
    if card_name:
        card_def = next((c for c in game.structured_cards if c.get("name") == card_name), None)
        if not card_def:
            return {"error": f"找不到卡牌：{card_name}"}
        viewer.hand = [Card(card_def["name"], card_def["type"], card_def.get("resources", {}) or {})]

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    noop_event = game._event_by_name("歲月靜好")
    game.current_event = dict(noop_event or {})
    game.event_progress = {"count": 0, "required": 0, "succeeded": True, "settled": True, "status": "idle"}
    game.event_modifiers = []
    game.id = game_id

    era_def = None
    if era_id:
        if not game.era_engine.activate_era(era_id):
            return {"error": f"時代關卡無法啟用：{era_id}"}
        era_def = game.era_engine.get_definition(era_id)
        game._apply_era_activation_effects(era_def)
        game.era_notification = game._era_notification_payload(era_def)
    for extra_era_id in extra_era_ids:
        if not game.era_engine.activate_era(extra_era_id):
            return {"error": f"時代關卡無法啟用：{extra_era_id}"}
        extra_era_def = game.era_engine.get_definition(extra_era_id)
        game._apply_era_activation_effects(extra_era_def)

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, opponent.id: opponent.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, opponent.id: opponent.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}

    inner_towns = set(game._towns_for_region_alias("china"))
    near_inner = set(game._towns_within_steps([origin], max_steps=1)) & inner_towns

    def _build_towns(name):
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        effect = next((e for e in (card_def or {}).get("effect", []) if e.get("type") == "build"), None)
        if not effect:
            return []
        return sorted({entry["town"] for entry in game._card_build_town_choices(viewer, effect)})

    ideologue = _build_towns("思想家")
    org_experience_a = _build_towns("組織經驗甲")
    support_anywhere = sorted({e["town"] for e in game._interactive_support_build_towns(viewer, near_only=False)})
    support_near = sorted({e["town"] for e in game._interactive_support_build_towns(viewer, near_only=True)})

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "opponent_player_id": opponent.id,
        "era_id": era_id,
        "era_name": (era_def or {}).get("name"),
        "origin": origin,
        "near_inner": sorted(near_inner),
        "ideologue_inner": [t for t in ideologue if t in inner_towns],
        "ideologue_outer_count": len([t for t in ideologue if t not in inner_towns]),
        "org_experience_a_inner": [t for t in org_experience_a if t in inner_towns],
        "east_asia_support_anywhere": support_anywhere,
        "east_asia_support_near": support_near,
        "url": f"/?game_id={game_id}&player_id={viewer.id}",
        "opponent_url": f"/?game_id={game_id}&player_id={opponent.id}",
        "state": game.state(),
    }
