"""Lobby formation routes: create/join/resume a room, choose faction/base,
mark ready, and start the game — the pre-game-start state machine.

Once /start hands a game_id off to `manager.games[game_id]`, everything
past that point (websocket connections, in-game state, reaction timeouts)
is a separate concern that stays in main.py. This is a verbatim move from
main.py, not a rewrite — nothing about the logic changed.
"""

import json
import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter

from server.faction_presentation import (
    faction_base_options,
    faction_base_resolved,
    faction_category,
)
from server.game import Game, GamePhase, STATIC_PURCHASE_CARD_SUPPLY, TurnPhase
from server.game_manager import manager

router = APIRouter()

lobby = {}        # {game_id: [(player_id, name)]}
lobby_hosts = {}  # {game_id: host_player_id}
lobby_factions = {}  # {game_id: {player_id: faction_id}}
lobby_bases = {}  # {game_id: {player_id: base_name}}
lobby_ready = {}  # {game_id: {player_id: bool}}
lobby_market_mode = {}  # {game_id: "sample_53" | "all_cards"}
lobby_player_credentials = {}  # {game_id: {player_id: {device_id, resume_token}}}


@router.post("/create")
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


@router.post("/join")
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


@router.post("/resume")
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


@router.post("/market-mode")
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


@router.post("/start")
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

    # Pass the real chosen factions into the constructor rather than overriding
    # player.faction_id afterward: Game.__init__ may resolve the game's first
    # event card before returning (some are "auto" and restricted to a specific
    # faction, e.g. player_faction: "red_army"), and an override applied only
    # after construction is too late — that first event has already resolved
    # against whichever player construction's own random assignment happened
    # to pick, not the player who actually chose that faction in the lobby.
    game = Game(player_list, market_mode=lobby_market_mode.get(game_id, "sample_53"), factions=chosen)
    chosen_bases = lobby_bases.get(game_id, {})
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


@router.post("/choose-faction")
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


@router.post("/ready")
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


@router.get("/lobby/{game_id}")
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
