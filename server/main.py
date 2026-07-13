from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game, TurnPhase, GamePhase, STATIC_PURCHASE_CARD_SUPPLY
from server.cards import Card
from server.game_manager import GameManager
import uuid
import asyncio
import csv
from pathlib import Path

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

manager = GameManager()
lobby = {}        # {game_id: [(player_id, name)]}
lobby_hosts = {}  # {game_id: host_player_id}
lobby_factions = {}  # {game_id: {player_id: faction_id}}
lobby_bases = {}  # {game_id: {player_id: base_name}}
lobby_ready = {}  # {game_id: {player_id: bool}}
lobby_market_mode = {}  # {game_id: "sample_53" | "all_cards"}
REACTION_RESPONSE_TIMEOUT_SECONDS = 10
reaction_timeout_tasks = {}


async def broadcast_game_state(game_id, game, last_action_result=None):
    for pid, ws in manager.connections.get(game_id, {}).items():
        state = game.state(pid)
        if last_action_result:
            if last_action_result.get("pending_choice"):
                state["pending_choice"] = game.state(pid).get("pending_choice")
            else:
                state["last_action_result"] = last_action_result
        await ws.send_json(state)


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

BASE_DIR = Path(__file__).resolve().parent.parent
ACTION_CSV_PATH = BASE_DIR / 'data' / 'raw' / 'action_cards.csv'
SUPPORT_CSV_PATH = BASE_DIR / 'data' / 'raw' / 'support_cards.csv'


def _load_card_presentation_catalog():
    catalog = {}
    if ACTION_CSV_PATH.exists():
        with ACTION_CSV_PATH.open(encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 10 or not row[1]:
                    continue
                catalog[row[1]] = {
                    'name': row[1],
                    'color': row[2],
                    'kind': row[3],
                    'strength': row[4],
                    'cost_text': row[5],
                    'effect_text': row[6],
                    'resource_text': row[7],
                    'position_text': row[8],
                    'meaning_text': row[9],
                    'count_text': row[10] if len(row) > 10 else '',
                }
    if SUPPORT_CSV_PATH.exists():
        with SUPPORT_CSV_PATH.open(encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            seen = set()
            for row in reader:
                if len(row) < 9 or not row[0] or row[0] in seen:
                    continue
                seen.add(row[0])
                catalog[row[0]] = {
                    'name': row[0],
                    'color': '奧援',
                    'kind': '奧援',
                    'strength': '特殊',
                    'cost_text': row[1],
                    'effect_text': f"III級：{row[3]}\nII級：{row[5]}\nI級：{row[7]}",
                    'resource_text': '依效果而定',
                    'position_text': '隨機購買區',
                    'meaning_text': '奧援卡',
                    'count_text': row[8] if len(row) > 8 else '',
                }
    catalog['紅軍奧援'] = {
        'name': '紅軍奧援',
        'color': '奧援',
        'kind': '奧援',
        'strength': '特殊',
        'cost_text': '起始牌',
        'effect_text': '行動：抽1張牌。若您為紅軍，打出後將本牌放進任一反共陣營玩家棄牌堆；若您為反共陣營玩家，打出後將本牌放進紅軍棄牌堆。',
        'resource_text': '提供1資金+1宣傳；打出後依陣營放入對應棄牌堆',
        'position_text': '起始牌',
        'meaning_text': '會轉移至對立陣營棄牌堆的特殊奧援卡',
        'count_text': '1',
    }
    return catalog


CARD_PRESENTATION_CATALOG = _load_card_presentation_catalog()


def faction_category(faction_id: str):
    if faction_id == 'red_army':
        return 'red_army'
    if faction_id in {'taiwan_green', 'taiwan_blue'}:
        return 'taiwan'
    if faction_id in {'uyghur_family', 'uyghur_istanbul', 'uyghur_munich', 'uyghur_washington', 'uyghur_almaty'}:
        return 'uyghur'
    if faction_id in {'tibet_family', 'tibet_dharamsala', 'tibet_dehradun', 'tibet_chogu'}:
        return 'tibet'
    if faction_id in {'hong_kong', 'manchuria', 'mongol', 'kazakh'}:
        return faction_id
    return 'rebel'


def semantic_base_pool(option_name: str):
    pools = {
        '任意牆內': [],
        '任意牆內城鎮': [],
        '任意英美城鎮': ['華盛頓', '紐約', '多倫多', '卡加利', '溫哥華', '舊金山', '洛杉磯', '倫敦'],
        '任意南洋': ['曼谷', '吉隆坡', '新加坡', '雅加達', '河內', '胡志明市', '仰光'],
        '任意南洋城鎮': ['曼谷', '吉隆坡', '新加坡', '雅加達', '河內', '胡志明市', '仰光'],
        '任意東洋': ['東京', '大阪', '福岡', '札幌', '仙臺', '沖繩', '首爾', '釜山'],
    }
    return pools.get(option_name, [])


def faction_base_options(by_id, faction_id: str):
    if faction_id == 'mongol':
        return ['烏蘭巴托', '東京', '紐約']
    if faction_id == 'manchuria':
        return ['東京', '舊金山', '海參崴']
    if faction_id == 'kazakh':
        return ['阿拉木圖']
    if faction_id == 'hong_kong':
        return ['香港城']
    if faction_id in {'uyghur_family', 'uyghur_istanbul', 'uyghur_munich', 'uyghur_washington', 'uyghur_almaty'}:
        return ['伊斯坦堡', '慕尼黑', '華盛頓', '阿拉木圖']
    if faction_id in {'tibet_family', 'tibet_dharamsala', 'tibet_dehradun', 'tibet_chogu'}:
        return ['達蘭薩拉', '德拉敦', '哲古宗']

    faction = by_id.get(faction_id, {})
    options = []
    for base in faction.get('bases', []):
        name = base.get('name') if isinstance(base, dict) else base
        if name and name not in options:
            options.append(name)
    return options


def faction_base_resolved(by_id, faction_id: str):
    options = faction_base_options(by_id, faction_id)
    resolved = {}
    for option in options:
        towns = semantic_base_pool(option)
        resolved[option] = towns if towns else [option]
    return resolved


@app.get('/card-presentation')
def card_presentation():
    return {'cards': CARD_PRESENTATION_CATALOG}


@app.post("/create")
def create_room():
    game_id = manager.create_room()
    host_id = str(uuid.uuid4())

    lobby[game_id] = [(host_id, 'host')]  # host is immediately in lobby
    lobby_hosts[game_id] = host_id
    lobby_factions[game_id] = {}
    lobby_bases[game_id] = {}
    lobby_ready[game_id] = {host_id: False}
    lobby_market_mode[game_id] = "sample_53"

    return {"game_id": game_id, "host_id": host_id}


@app.post("/join")
def join_game(payload: dict):
    game_id = payload.get("game_id")
    name = payload.get("name")
    requested_player_id = payload.get("player_id")

    if game_id not in lobby:
        return {"error": "Game not found"}

    if not name:
        return {"error": "Name required"}

    # Reuse reserved/known player id when provided (e.g. room host)
    if requested_player_id:
        for idx, (pid, _) in enumerate(lobby[game_id]):
            if pid == requested_player_id:
                lobby[game_id][idx] = (requested_player_id, name)
                lobby_ready.setdefault(game_id, {}).setdefault(requested_player_id, False)
                return {"player_id": requested_player_id}
        player_id = requested_player_id
    else:
        player_id = str(uuid.uuid4())

    if len(lobby[game_id]) >= 4:
        return {"error": "Room full"}

    lobby[game_id].append((player_id, name))
    lobby_ready.setdefault(game_id, {})[player_id] = False
    return {"player_id": player_id}


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
        return {"error": "Exactly one player must choose red_army"}

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
    from pathlib import Path
    import json
    path = Path(__file__).resolve().parent.parent / "data" / "factions" / "all_faction.integrated.v2.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    factions = data["factions"]
    by_id = {x["id"]: x for x in factions}
    rebels = [x for x in factions if x.get("camp") == "rebel"]
    ability_templates = data.get("ability_templates", {})

    def resolve_ui_faction(faction):
        resolved = dict(faction)
        resolved_abilities = []
        for ability in faction.get("abilities", []):
            if isinstance(ability, dict) and ability.get("ref"):
                template = ability_templates.get(ability.get("ref"), {})
                merged = dict(template)
                merged.update({k: v for k, v in ability.items() if k != "ref"})
                if ability.get("name_override"):
                    merged["name"] = ability["name_override"]
                resolved_abilities.append(merged)
            else:
                resolved_abilities.append(ability)
        resolved["abilities"] = resolved_abilities
        return resolved

    def resolve_family_ui_faction(family_id, name, camp, variant_ids):
        bases = []
        variant_details = {}
        for variant_id in variant_ids:
            variant = resolve_ui_faction(by_id[variant_id])
            base = next((b for b in variant.get("bases", []) if isinstance(b, dict) and b.get("name")), None)
            base_name = base.get("name") if base else variant.get("variant")
            if base_name:
                bases.append({"name": base_name, "variant_faction": variant_id})
                variant_details[base_name] = variant
        return {
            "id": family_id,
            "name": name,
            "camp": camp,
            "bases": bases,
            "variant_details": variant_details,
        }

    categories = [
        {"id": "red_army", "label": "紅軍", "mode": "direct", "options": [resolve_ui_faction(by_id["red_army"])]},
        {"id": "taiwan", "label": "臺灣", "mode": "variant", "options": [resolve_ui_faction(by_id["taiwan_green"]), resolve_ui_faction(by_id["taiwan_blue"])]},
        {"id": "hong_kong", "label": "香港", "mode": "direct", "options": [resolve_ui_faction(by_id["hong_kong"])]},
        {"id": "uyghur", "label": "維吾爾", "mode": "direct", "options": [resolve_family_ui_faction("uyghur_family", "維吾爾", "uyghur", ["uyghur_istanbul", "uyghur_munich", "uyghur_washington", "uyghur_almaty"])]},
        {"id": "tibet", "label": "西藏", "mode": "direct", "options": [resolve_family_ui_faction("tibet_family", "西藏", "tibet", ["tibet_dharamsala", "tibet_dehradun", "tibet_chogu"])]},
        {"id": "manchuria", "label": "滿洲", "mode": "direct", "options": [resolve_ui_faction(by_id["manchuria"])]},
        {"id": "mongol", "label": "蒙古", "mode": "direct", "options": [resolve_ui_faction(by_id["mongol"])]},
        {"id": "kazakh", "label": "哈薩克", "mode": "direct", "options": [resolve_ui_faction(by_id["kazakh"])]},
        {"id": "rebel", "label": "反賊", "mode": "variant", "options": [resolve_ui_faction(x) for x in rebels]},
    ]

    for category in categories:
        for option in category["options"]:
            option["base_options"] = faction_base_options(by_id, option["id"])
            option["base_resolved"] = faction_base_resolved(by_id, option["id"])

    return {"categories": categories}


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
    if any(pid != player_id and faction_category(fid) == wanted_category for pid, fid in taken.items()):
        return {"error": "Faction category already taken"}

    valid_bases = faction_base_options(by_id, faction_id)
    resolved_bases = faction_base_resolved(by_id, faction_id)
    if base_name:
        valid_towns = {town for towns in resolved_bases.values() for town in towns}
        if base_name not in valid_towns:
            return {"error": "Invalid base option"}

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
    }


@app.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    await websocket.accept()

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

            bypass_turn_check = False
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
            elif action == "play_card":
                result = game.play_card(data.get("index"), mode=data.get("mode"), target_player_id=data.get("target_player_id"))
            elif action == "buy_card":
                result = game.buy_card(data.get("index"))
            elif action == "set_base":
                result = game.set_base_choice(player_id, data.get("town"))
            elif action == "build":
                if data.get("from") and data.get("town"):
                    result = game.build_organization_with_support(data.get("from"), data.get("town"))
                else:
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
        manager.remove_connection(game_id, player_id)


@app.get("/town-coordinates")
def get_town_coordinates():
    from pathlib import Path
    import json
    path = Path(__file__).resolve().parent.parent / "data" / "town_coordinates.v1.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.get("/map-test")
def map_test():
    return FileResponse("static/map_test.html")

@app.get("/map-data")
def get_map_data():
    from pathlib import Path
    import json
    path = Path(__file__).resolve().parent.parent / "data" / "map.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.post("/test/set-hand")
def test_set_hand(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")
    cards = payload.get("cards", [])
    turn_phase = payload.get("turn_phase")
    set_current_player = bool(payload.get("set_current_player"))

    game = manager.get_game(game_id)
    if not game:
        return {"error": "Game not found"}

    player = next((p for p in game.players if p.id == player_id), None)
    if not player:
        return {"error": "Player not found"}

    player.hand = []
    for name in cards:
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            player.hand.append(Card(card_def["name"], card_def.get("type", "test"), card_def.get("resources", {})))
        else:
            player.hand.append(game._starter_card(name))

    if turn_phase == "action":
        game.turn_phase = TurnPhase.ACTION
    elif turn_phase == "event":
        game.turn_phase = TurnPhase.EVENT
    elif turn_phase == "end":
        game.turn_phase = TurnPhase.END

    if set_current_player:
        for idx, candidate in enumerate(game.players):
            if candidate.id == player_id:
                game.current_player_index = idx
                break

    return {
        "success": True,
        "hand": [c.name for c in player.hand],
        "turn_phase": game.turn_phase,
        "current_player": game.current_player().name if game.current_player() else None,
        "current_player_id": game.current_player().id if game.current_player() else None,
    }


@app.post("/test/setup-card-scenario")
def test_setup_card_scenario(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")
    card_name = payload.get("card_name")

    game = manager.get_game(game_id)
    if not game:
        return {"error": "Game not found"}

    return game.setup_test_card_scenario(player_id, card_name)


@app.post("/test/force-base-selection")
def test_force_base_selection(payload: dict):
    game_id = payload.get("game_id")
    faction_ids = payload.get("faction_ids", [])
    player_names = payload.get("player_names") or [f"player{i+1}" for i in range(len(faction_ids))]
    chosen_bases = payload.get("chosen_bases") or {}

    if len(faction_ids) < 2:
        return {"error": "Need at least 2 faction ids"}

    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), name) for name in player_names]
    game = Game(players)
    for player, faction_id in zip(game.players, faction_ids):
        player.faction_id = faction_id

    game.pending_base_choices = game._compute_pending_base_choices()
    for player in game.players:
        base_name = chosen_bases.get(player.name) or chosen_bases.get(player.id)
        if not base_name:
            continue
        result = game.choose_base(player.id, base_name)
        if result.get("error"):
            return {"error": result["error"], "player": player.name, "base_name": base_name}

    if game.pending_base_choices:
        game.game_phase = GamePhase.BASE_SELECTION
    else:
        game.game_phase = GamePhase.MAIN
        first_non_red = next((idx for idx, player in enumerate(game.players) if player.faction_id != 'red_army'), 0)
        game.current_player_index = first_non_red

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = game.players[0].id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}

    return {
        "success": True,
        "game_id": game_id,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id, "base": p.base} for p in game.players],
        "pending_base_choices": game.pending_base_choices,
        "game_phase": game.game_phase,
    }


@app.post("/test/setup-intel-network-proof")
def test_setup_intel_network_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [
        (str(uuid.uuid4()), "viewer"),
        (str(uuid.uuid4()), "enemyA"),
        (str(uuid.uuid4()), "enemyB"),
        (str(uuid.uuid4()), "enemyC"),
    ]
    game = Game(players)

    viewer, enemy_a, enemy_b, enemy_c = game.players

    viewer.faction_id = payload.get("viewer_faction", "red_army")
    viewer.base = payload.get("viewer_base", "北京")
    viewer.organizations = {"北京": 1}
    viewer.hand = [Card("情報網", "command", {})]

    enemy_a.faction_id = payload.get("enemy_a_faction", "hong_kong")
    enemy_a.base = payload.get("enemy_a_base", "香港城")
    enemy_a_organizations = payload.get("enemy_a_organizations") or {"天津": 1, "香港城": 1, "廣州": 1}
    enemy_a.organizations = dict(enemy_a_organizations)
    enemy_a.hand = [Card("敵方手牌A1", "command", {}), Card("敵方手牌A2", "command", {})]

    enemy_b.faction_id = payload.get("enemy_b_faction", "taiwan_green")
    enemy_b.base = payload.get("enemy_b_base", "臺北")
    enemy_b.organizations = {"臺北": 1}
    enemy_b.hand = [Card("敵方手牌B1", "command", {}), Card("敵方手牌B2", "command", {})]

    enemy_c.faction_id = payload.get("enemy_c_faction", "minyun")
    enemy_c.base = payload.get("enemy_c_base", "巴黎")
    enemy_c.organizations = {"巴黎": 1, "上海": 1}
    enemy_c.hand = [Card("敵方手牌C1", "command", {}), Card("敵方手牌C2", "command", {})]

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-press-advantage-proof")
def test_setup_press_advantage_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [
        (str(uuid.uuid4()), "viewer"),
        (str(uuid.uuid4()), "enemy"),
    ]
    game = Game(players)
    viewer, enemy = game.players

    def proof_card(name):
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))
        return Card(name, "command", {})

    viewer.faction_id = payload.get("viewer_faction", "red_army")
    viewer.base = payload.get("viewer_base", "北京")
    viewer.organizations = {viewer.base: 1}
    viewer.hand = [proof_card("乘勝追擊")]
    viewer.deck.draw_pile = [proof_card(name) for name in payload.get("draw_pile", ["抽牌A", "抽牌B"])]
    discard_names = payload.get("discard_pile") or ["宣傳家", "合作談判", "走漏風聲"]
    viewer.deck.discard_pile = [proof_card(name) for name in discard_names]
    viewer.resources = {"money": 0, "propaganda": 0}

    enemy.faction_id = payload.get("enemy_faction", "hong_kong")
    enemy.base = payload.get("enemy_base", "香港城")
    enemy.organizations = {enemy.base: 1}
    enemy.hand = [proof_card("對手手牌A")]
    enemy.deck.draw_pile = [proof_card("對手抽牌A")]
    enemy.deck.discard_pile = []
    enemy.resources = {"money": 0, "propaganda": 0}

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id
    game.log("UI proof setup: viewer has 乘勝追擊; discard pile contains 宣傳家 / 合作談判 / 走漏風聲.")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id, "base": p.base} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-expand-results-proof")
def test_setup_expand_results_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [
        (str(uuid.uuid4()), "viewer"),
        (str(uuid.uuid4()), "enemy"),
    ]
    game = Game(players)
    viewer, enemy = game.players

    def proof_card(name):
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))
        return Card(name, "command", {})

    viewer.faction_id = payload.get("viewer_faction", "red_army")
    viewer.base = payload.get("viewer_base", "北京")
    viewer.organizations = {viewer.base: 1}
    viewer.hand = [proof_card("擴大戰果")]
    viewer.deck.draw_pile = [proof_card(name) for name in payload.get("draw_pile", ["抽牌A", "抽牌B"])]
    discard_names = payload.get("discard_pile") or ["宣傳家", "合作談判", "走漏風聲"]
    viewer.deck.discard_pile = [proof_card(name) for name in discard_names]
    viewer.resources = {"money": 0, "propaganda": 0}

    enemy.faction_id = payload.get("enemy_faction", "hong_kong")
    enemy.base = payload.get("enemy_base", "香港城")
    enemy.organizations = {enemy.base: 1}
    enemy.hand = [proof_card("對手手牌A")]
    enemy.deck.draw_pile = [proof_card("對手抽牌A")]
    enemy.deck.discard_pile = []
    enemy.resources = {"money": 0, "propaganda": 0}

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id
    game.log("UI proof setup: viewer has 擴大戰果; discard pile contains 宣傳家 / 合作談判 / 走漏風聲.")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id, "base": p.base} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-intel-network-cancel-reaction-proof")
def test_setup_intel_network_cancel_reaction_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [
        (str(uuid.uuid4()), "actor"),
        (str(uuid.uuid4()), "reactor"),
    ]
    game = Game(players)
    actor, reactor = game.players

    def proof_card(name):
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))
        return Card(name, "command", {})

    actor_card = payload.get("actor_card", "領導")
    reaction_card = payload.get("reaction_card", "情報網")

    actor.faction_id = payload.get("actor_faction", "hong_kong")
    actor.base = payload.get("actor_base", "香港城")
    actor.organizations = {actor.base: 1}
    actor.hand = [proof_card(actor_card)]
    actor.deck.draw_pile = [proof_card(payload.get("actor_draw_top", "ShouldNotDraw"))]
    actor.deck.discard_pile = []
    actor.resources = {"money": 0, "propaganda": 0}

    reactor.faction_id = payload.get("reactor_faction", "red_army")
    reactor.base = payload.get("reactor_base", "北京")
    reactor.organizations = {reactor.base: 1}
    reactor.hand = [proof_card(reaction_card)]
    reactor.deck.draw_pile = [proof_card(payload.get("reactor_draw_top", "IntelShouldNotDrawBonus"))]
    reactor.deck.discard_pile = []
    reactor.resources = {"money": 0, "propaganda": 0}

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id
    game.log(f"{reaction_card}取消反應測試：actor 準備打出 {actor_card}；reactor 手牌有 {reaction_card} 可取消。")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = actor.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players}

    return {
        "success": True,
        "game_id": game_id,
        "actor_id": actor.id,
        "reactor_id": reactor.id,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/resolve-intel-network-cancel-reaction-proof")
def test_resolve_intel_network_cancel_reaction_proof(payload: dict):
    game_id = payload.get("game_id")
    game = manager.get_game(game_id)
    if not game:
        return {"error": "Game not found"}
    actor = next((p for p in game.players if p.name == payload.get("actor_name", "actor")), game.current_player())
    reactor = next((p for p in game.players if p.name == payload.get("reactor_name", "reactor")), None)
    if not actor or not reactor:
        return {"error": "Proof players not found"}
    for idx, candidate in enumerate(game.players):
        if candidate.id == actor.id:
            game.current_player_index = idx
            break
    result = game.play_card(0, mode="action", reaction={"player_id": reactor.id, "card_index": 0})
    state = game.state()
    state["last_action_result"] = result
    return {
        "success": not bool(result.get("error")) if isinstance(result, dict) else True,
        "result": result,
        "state": state,
    }


@app.post("/test/setup-hong-kong-safehouse")
def test_setup_hong_kong_safehouse(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "hk"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    hk = game.players[0]
    red = game.players[1]

    hk.faction_id = "hong_kong"
    hk.base = payload.get("base", "香港城")
    hk.organizations = {hk.base: 1}
    hk.hand = []

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = hk.id
    lobby_factions[game_id] = {hk.id: "hong_kong", red.id: "red_army"}
    lobby_bases[game_id] = {hk.id: hk.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": hk.id,
        "base": hk.base,
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-enemy-occupancy-proof")
def test_setup_enemy_occupancy_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "f"), (str(uuid.uuid4()), "紅軍")]
    game = Game(players, market_mode="all_cards")
    actor = game.players[0]
    red = game.players[1]

    actor.faction_id = payload.get("actor_faction", "taiwan_green")
    actor.base = payload.get("actor_base", "臺北")
    actor.organizations = {payload.get("actor_town", "桃園"): 1}
    actor.hand = [Card("宣傳家", "propaganda", {"propaganda": 2})]
    actor.moves_left = int(payload.get("moves_left", 1) or 1)
    actor.resources = {"money": 0, "propaganda": 0}

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {payload.get("red_town", "新竹"): 1}
    red.hand = []

    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.pending_choice = None
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = actor.id
    lobby_factions[game_id] = {actor.id: actor.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {actor.id: actor.base, red.id: red.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": actor.id,
        "red_player_id": red.id,
        "url": f"/?game_id={game_id}&player_id={actor.id}",
        "state": game.state(),
        "move_to_enemy_result": game.move_organization("桃園", "新竹", "rail") if payload.get("probe_move", False) else None,
        "card_build_choices": game._card_build_town_choices(actor, {"type": "build", "range": 1}),
    }


@app.post("/test/setup-move-confirmation-proof")
def test_setup_move_confirmation_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "mover"), (str(uuid.uuid4()), "opponent")]
    game = Game(players, market_mode="all_cards")
    mover = game.players[0]
    opponent = game.players[1]

    mover.faction_id = payload.get("mover_faction", "taiwan_green")
    mover.base = payload.get("mover_base", "臺北")
    mover.organizations = {payload.get("mover_town", "臺北"): 1}
    mover.moves_left = int(payload.get("moves_left", 5) or 5)

    opponent.faction_id = "red_army"
    opponent.base = "北京"
    opponent.organizations = {"北京": 1}

    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.pending_choice = None
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = mover.id
    lobby_factions[game_id] = {mover.id: mover.faction_id, opponent.id: opponent.faction_id}
    lobby_bases[game_id] = {mover.id: mover.base, opponent.id: opponent.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": mover.id,
        "opponent_player_id": opponent.id,
        "url": f"/?game_id={game_id}&player_id={mover.id}",
        "state": game.state(),
    }


@app.post("/test/setup-hu-taiwan-shared")
def test_setup_hu_taiwan_shared(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "hu"), (str(uuid.uuid4()), "taiwan")]
    game = Game(players)

    hu = game.players[0]
    tw = game.players[1]

    hu.faction_id = "hu"
    hu.base = payload.get("hu_base", "紐約")
    hu.organizations = {hu.base: 1}
    hu.hand = []
    hu.moves_left = 0

    tw.faction_id = "taiwan_green"
    tw.base = payload.get("tw_base", "臺北")
    tw.organizations = {
        payload.get("shared_town", "上海"): 1,
        tw.base: 1,
    }
    tw.hand = []

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = hu.id
    lobby_factions[game_id] = {hu.id: "hu", tw.id: "taiwan_green"}
    lobby_bases[game_id] = {hu.id: hu.base, tw.id: tw.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": hu.id,
        "shared_town": payload.get("shared_town", "上海"),
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-shared-dissolve")
def test_setup_shared_dissolve(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "atk"), (str(uuid.uuid4()), "hu"), (str(uuid.uuid4()), "taiwan")]
    game = Game(players)

    attacker = game.players[0]
    hu = game.players[1]
    tw = game.players[2]

    attacker.faction_id = payload.get("attacker_faction", "red_army")
    attacker.base = payload.get("attacker_base", "南京")
    attacker.organizations = {attacker.base: 1}
    attacker.hand = [] if payload.get("attacker_no_hand") else [Card("測試手牌", "money", {"money": 1})]

    hu.faction_id = "hu"
    hu.base = payload.get("hu_base", "紐約")
    hu.organizations = {hu.base: 1}
    hu.hand = []

    tw.faction_id = payload.get("tw_faction", "taiwan_green")
    tw.base = payload.get("tw_base", "臺北")
    tw.organizations = {
        payload.get("shared_town", "上海"): 1,
        tw.base: 1,
    }
    tw.hand = []
    tw.deck.draw_pile = [Card("補牌A", "money", {"money": 1})]

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = attacker.id
    lobby_factions[game_id] = {attacker.id: attacker.faction_id, hu.id: "hu", tw.id: tw.faction_id}
    lobby_bases[game_id] = {attacker.id: attacker.base, hu.id: hu.base, tw.id: tw.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": attacker.id,
        "shared_town": payload.get("shared_town", "上海"),
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-india-support-purchase")
def test_setup_india_support_purchase(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "tibet"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    tibet = game.players[0]
    red = game.players[1]

    tibet.faction_id = "tibet_dehradun"
    tibet.base = payload.get("base", "德拉敦")
    tibet.organizations = {tibet.base: 1}
    tibet.resources = {"money": 5, "propaganda": 5}
    tibet.hand = []

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}

    support_name = payload.get("support_name", "印度奧援")
    game.purchase_area = [game._make_support_card(support_name)]
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = tibet.id
    lobby_factions[game_id] = {tibet.id: tibet.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {tibet.id: tibet.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": tibet.id,
        "support_name": support_name,
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-remove-to-purchase")
def test_setup_remove_to_purchase(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 4, "propaganda": 3}

    card_name = payload.get("card_name", "宣傳家")
    card_def = next((c for c in game.structured_cards if c.get("name") == card_name), None)
    if card_def:
        viewer.hand = [Card(card_def["name"], card_def["type"], card_def.get("resources", {}))]
    else:
        viewer.hand = [Card(card_name, "command", {})]

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = []

    game.purchase_area = game._static_purchase_cards()[:]
    while len(game.purchase_area) < 11:
        drawn = game._draw_purchase_cards(1)
        if not drawn:
            break
        game.purchase_area.extend(drawn)

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players}

    return {
        "game_id": game_id,
        "player_id": viewer.id,
        "card_name": card_name,
        "purchase_area": [getattr(c, 'name', str(c)) for c in game.purchase_area],
        "hand": [getattr(c, 'name', str(c)) for c in viewer.hand],
    }


@app.post("/test/setup-underground-party")
def test_setup_underground_party(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    def proof_card(name):
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))
        return Card(name, "command", {})

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 4, "propaganda": 4}
    viewer.hand = [proof_card("地下黨")]
    viewer.deck.draw_pile = [proof_card("抽牌A"), proof_card("抽牌B")]
    viewer.deck.discard_pile = []

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = []

    # Deck.draw() pops from the end; arrange the three proof candidates so the UI reveals them in this order.
    candidate_names = payload.get("candidate_names") or ["宣傳家", "合作談判", "走漏風聲"]
    game.purchase_deck.draw_pile = [proof_card(name) for name in reversed(candidate_names)]
    game.purchase_deck.discard_pile = []
    game.purchase_area = game._static_purchase_cards()[:]
    random_market_names = payload.get("purchase_area_random") or ["批鬥", "組織經驗甲", "組織經驗丙", "北國奧援", "模仿戰術"]
    game.purchase_area.extend(proof_card(name) for name in random_market_names)

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id
    game.log("UI proof setup: viewer has 地下黨; purchase deck top reveals 宣傳家 / 合作談判 / 走漏風聲.")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "purchase_draw_pile": [getattr(c, 'name', str(c)) for c in game.purchase_deck.draw_pile],
        "expected_reveal_order": list(candidate_names),
        "hand": [getattr(c, 'name', str(c)) for c in viewer.hand],
        "state": game.state(),
    }


@app.post("/test/setup-recruit-talent-proof")
def test_setup_recruit_talent_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    def proof_card(name):
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))
        return Card(name, "command", {})

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base") or ("北京" if viewer.faction_id == "red_army" else "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 4, "propaganda": 4}
    viewer.hand = [proof_card("網羅人才")]
    deck_names = payload.get("deck_names") or ["宣傳家", "合作談判", "走漏風聲"]
    discard_names = payload.get("discard_names") or ["棄牌見證"]
    viewer.deck.draw_pile = [proof_card(name) for name in deck_names]
    viewer.deck.discard_pile = [proof_card(name) for name in discard_names]

    if viewer.faction_id == "red_army":
        red.faction_id = "tibet_dehradun"
        red.base = "德拉敦"
    else:
        red.faction_id = "red_army"
        red.base = "北京"
    red.organizations = {red.base: 1}
    red.hand = []

    game.purchase_area = game._static_purchase_cards()[:]
    random_market_names = payload.get("purchase_area_random") or ["批鬥", "組織經驗甲", "組織經驗丙", "北國奧援", "模仿戰術"]
    game.purchase_area.extend(proof_card(name) for name in random_market_names)

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id
    log_target = "deck/discard choices" if viewer.faction_id == "red_army" else "deck choices"
    game.log(f"UI proof setup: viewer has 網羅人才; {log_target} include {' / '.join(deck_names + discard_names)}.")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "deck_draw_pile": [getattr(c, 'name', str(c)) for c in viewer.deck.draw_pile],
        "discard_pile": [getattr(c, 'name', str(c)) for c in viewer.deck.discard_pile],
        "hand": [getattr(c, 'name', str(c)) for c in viewer.hand],
        "state": game.state(),
    }


@app.post("/test/setup-support-card-play")
def test_setup_support_card_play(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "player"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    player = game.players[0]
    red = game.players[1]

    player.faction_id = payload.get("faction_id", "tibet_dehradun")
    player.base = payload.get("base", "德拉敦")
    player.organizations = payload.get("orgs") or {player.base: 1}
    player.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
    player.hand = [game._make_support_card(payload.get("support_name", "印度奧援"))]
    player.deck.draw_pile = [Card("補牌A", "command", {}), Card("補牌B", "command", {})]
    player.deck.discard_pile = []

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = []
    red.deck.draw_pile = [Card("紅軍抽牌A", "command", {})]
    red.deck.discard_pile = []

    game.purchase_area = []
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = player.id
    lobby_factions[game_id] = {player.id: player.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {player.id: player.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": player.id,
        "support_name": payload.get("support_name", "印度奧援"),
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "support_tier": game._support_card_tier(player, payload.get("support_name", "印度奧援"))[0],
        "state": game.state(),
    }


@app.post("/test/setup-purchase-deck-ui")
def test_setup_purchase_deck_ui(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 5, "propaganda": 5}
    viewer.hand = []

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}

    # full purchase UI path: static 6 + 5 random. Tests may pin the
    # random slots to verify a specific market-card purchase/refill flow.
    pinned_random = payload.get("purchase_area_random") or []
    if pinned_random:
        game.purchase_area = game._static_purchase_cards()[:]
        for name in pinned_random[:5]:
            support = game._support_taxonomy_entry(name)
            if support:
                game.purchase_area.append(game._make_support_card(name))
                continue
            card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
            if card_def:
                game.purchase_area.append(Card(card_def["name"], card_def.get("type", "command"), card_def.get("resources", {})))
            else:
                game.purchase_area.append(Card(name, "command", {}))
    while len(game.purchase_area) < 11:
        drawn = game._draw_purchase_cards(1)
        if not drawn:
            break
        game.purchase_area.extend(drawn)

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-hand-preview")
def test_setup_hand_preview(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 4, "propaganda": 3}

    hand_names = payload.get("hand_names") or ["宣傳家", "印度奧援", "東洋奧援"]
    hand_cards = []
    for name in hand_names:
        support_entry = game._support_taxonomy_entry(name)
        if support_entry:
            hand_cards.append(game._make_support_card(name))
            continue
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            hand_cards.append(Card(card_def["name"], card_def["type"], card_def.get("resources", {})))
        else:
            hand_cards.append(Card(name, "command", {}))
    viewer.hand = hand_cards

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}

    while len(game.purchase_area) < 11:
        drawn = game._draw_purchase_cards(1)
        if not drawn:
            break
        game.purchase_area.extend(drawn)

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "hand_names": hand_names,
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-end-turn-topdeck-proof")
def test_setup_end_turn_topdeck_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    card_name = payload.get("card_name", "行動預告")
    bought_card_name = payload.get("bought_card", "本回合購得牌")
    extra_hand = payload.get("extra_hand") or ["Filler"]

    def proof_card(name):
        card_def = next((c for c in game.structured_cards if c.get("name") == name), None)
        if card_def:
            return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))
        return Card(name, "command", {})

    bought_card = proof_card(bought_card_name)

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
    viewer.hand = [proof_card(card_name)] + [proof_card(name) for name in extra_hand]
    viewer.deck.draw_pile = [proof_card(name) for name in (payload.get("draw_pile") or ["補牌1", "補牌2", "補牌3", "補牌4", "補牌5"])]
    viewer.deck.discard_pile = [bought_card]

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = []

    game.current_player_index = 0
    game.turn_phase = TurnPhase.END
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.turn_log["purchased_cards_this_turn"] = [bought_card]
    game.id = game_id
    game.log(f"UI proof setup: viewer has {card_name}; bought card {bought_card_name} is in discard before end-turn refill.")

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "card_name": card_name,
        "bought_card": bought_card_name,
        "state": game.state(),
    }


@app.post("/test/setup-business-network-transport-proof")
def test_setup_business_network_transport_proof(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
    viewer.moves_left = 4
    viewer.hand = []

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = []

    game.purchase_area = game._static_purchase_cards() + [
        Card("合作談判", "command", {"propaganda": 1}),
        Card("交通經驗乙", "transport", {"money": 2}),
        Card("模仿戰術", "command", {"propaganda": 2}),
        Card("資本家", "money", {"money": 3}),
        Card("填充D", "command", {}),
    ]
    game.pending_choice = {
        "type": "card_choice",
        "choice_key": "use_purchase_area_card",
        "player_id": viewer.id,
        "cards": [
            {
                "card": game.purchase_area[6],
                "name": getattr(game.purchase_area[6], "name", str(game.purchase_area[6])),
                "zone": "purchase_area",
                "zone_label": "購買區槽位 1",
                "purchase_index": 6,
            },
            {
                "card": game.purchase_area[7],
                "name": getattr(game.purchase_area[7], "name", str(game.purchase_area[7])),
                "zone": "purchase_area",
                "zone_label": "購買區槽位 2",
                "purchase_index": 7,
            },
            {
                "card": game.purchase_area[8],
                "name": getattr(game.purchase_area[8], "name", str(game.purchase_area[8])),
                "zone": "purchase_area",
                "zone_label": "購買區槽位 3",
                "purchase_index": 8,
            },
            {
                "card": game.purchase_area[9],
                "name": getattr(game.purchase_area[9], "name", str(game.purchase_area[9])),
                "zone": "purchase_area",
                "zone_label": "購買區槽位 4",
                "purchase_index": 9,
            },
            {
                "card": game.purchase_area[10],
                "name": getattr(game.purchase_area[10], "name", str(game.purchase_area[10])),
                "zone": "purchase_area",
                "zone_label": "購買區槽位 5",
                "purchase_index": 10,
            },
        ],
        "prompt": "企業人脈：選擇購買區正面朝上的 1 張牌，視同打出該牌。",
        "source_name": "企業人脈",
    }

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-planning-lobby-ui")
def test_setup_planning_lobby_ui(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
    card_def = next(c for c in game.structured_cards if c.get("name") == "企畫遊說")
    viewer.hand = [Card(card_def["name"], card_def["type"], card_def.get("resources", {}))]
    top_card_name = payload.get("top_card_name", "思想家")
    top_card_def = next((c for c in game.structured_cards if c.get("name") == top_card_name), None)
    if top_card_def:
        top_card = Card(top_card_def["name"], top_card_def["type"], top_card_def.get("resources", {}))
    else:
        top_card = Card(top_card_name, "command", {})
    viewer.deck.draw_pile = [top_card]
    viewer.deck.discard_pile = []

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = []

    while len(game.purchase_area) < 11:
        drawn = game._draw_purchase_cards(1)
        if not drawn:
            break
        game.purchase_area.extend(drawn)

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "top_card_name": top_card_name,
        "top_card_cost": game._card_purchase_cost(top_card),
        "turn_phase": game.turn_phase,
        "game_phase": game.game_phase,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-trash-choice-ui")
def test_setup_trash_choice_ui(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    viewer.faction_id = payload.get("faction_id", "red_army")
    viewer.base = payload.get("base", "北京")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
    viewer.hand = [
        Card("思想家", "command", {"propaganda": 2}),
        Card("宣傳家", "propaganda", {"propaganda": 1}),
    ]
    viewer.deck.discard_pile = [
        Card("資本家", "money", {"money": 3}),
        Card("樂捐者", "money", {"money": 1}),
    ]

    red.faction_id = "hong_kong"
    red.base = "香港城"
    red.organizations = {"香港城": 1}
    red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    red.deck.discard_pile = []

    while len(game.purchase_area) < 11:
        drawn = game._draw_purchase_cards(1)
        if not drawn:
            break
        game.purchase_area.extend(drawn)

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id
    source_name = payload.get('source_name', '批判')
    count = int(payload.get('count', 1) or 1)
    cards = [
        {'card': viewer.hand[0], 'zone': 'hand', 'zone_label': '手牌'},
        {'card': viewer.hand[1], 'zone': 'hand', 'zone_label': '手牌'},
        {'card': viewer.deck.discard_pile[0], 'zone': 'discard', 'zone_label': '棄牌堆'},
        {'card': viewer.deck.discard_pile[1], 'zone': 'discard', 'zone_label': '棄牌堆'},
    ]
    prompt = f"{source_name}：請從己方手牌或棄牌堆中移除 {count} 張牌。"
    if count <= 1:
        game._set_pending_card_choice(
            viewer,
            'trash_from_hand_or_discard',
            cards,
            prompt,
            source_name=source_name,
            count=1,
        )
    else:
        game._set_pending_multi_card_choice(
            viewer,
            'trash_from_hand_or_discard',
            cards,
            prompt,
            count=count,
            source_name=source_name,
        )

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

    return {
        'success': True,
        'game_id': game_id,
        'player_id': viewer.id,
        'state': game.state(),
        'players': [{'id': p.id, 'name': p.name, 'faction': p.faction_id} for p in game.players],
    }


@app.post("/test/setup-red-support-proof")
def test_setup_red_support_proof(payload: dict):
    mode = payload.get("mode", "resource")
    actor_faction = payload.get("actor_faction", "liberals")
    opponent_faction = payload.get("opponent_faction", "red_army" if actor_faction != "red_army" else "liberals")

    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "target")]
    game = Game(players)

    viewer = game.players[0]
    target = game.players[1]

    viewer.faction_id = actor_faction
    viewer.base = "北京" if actor_faction == "red_army" else "德拉敦"
    viewer.organizations = {viewer.base: 1}
    viewer.resources = {"money": 0, "propaganda": 0}
    viewer.hand = [game._make_support_card("紅軍奧援")]
    viewer.deck.draw_pile = []
    viewer.deck.discard_pile = []

    target.faction_id = opponent_faction
    target.base = "北京" if opponent_faction == "red_army" else "香港城"
    target.organizations = {target.base: 1}
    target.resources = {"money": 0, "propaganda": 0}
    target.hand = []
    target.deck.draw_pile = []
    target.deck.discard_pile = []

    if mode == "action":
        viewer.deck.discard_pile = [Card("抽到展示牌", "command", {})]

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, target.id: target.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, target.id: target.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": viewer.id,
        "mode": mode,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-red-army-abilities-proof")
def test_setup_red_army_abilities_proof():
    game_id = str(uuid.uuid4())
    players = [("red-proof", "紅軍"), ("lib-proof", "自由派"), ("hk-proof", "香港")]
    game = Game(players, market_mode="all_cards")
    red, liberals, hong_kong = game.players

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = [Card("手牌甲", "test", {}), Card("手牌乙", "test", {})]
    red.deck.draw_pile = [Card("補牌甲", "test", {}), Card("補牌乙", "test", {}), Card("補牌丙", "test", {})]
    red.deck.discard_pile = []

    liberals.faction_id = "liberals"
    liberals.base = "香港城"
    liberals.organizations = {"天津": 1}
    liberals.deck.draw_pile = []
    liberals.deck.discard_pile = []

    hong_kong.faction_id = "hong_kong"
    hong_kong.base = "香港城"
    hong_kong.organizations = {"上海": 1}

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.turn_log = game._new_turn_log()
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = red.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": red.id,
        "target_player_id": liberals.id,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-spy-proof")
def test_setup_spy_proof(payload: dict):
    card_name = payload.get("card_name", "派遣間諜")
    if card_name not in {"派遣間諜", "內應間諜"}:
        return {"error": "Unsupported spy card"}

    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), payload.get("player_name", "viewer")), (str(uuid.uuid4()), payload.get("enemy_name", "enemy"))]
    game = Game(players)
    player = game.players[0]
    enemy = game.players[1]

    player.faction_id = payload.get("faction_id", "red_army")
    player.base = payload.get("base", "北京")
    enemy.faction_id = payload.get("enemy_faction_id", "taiwan_green")
    enemy.base = payload.get("enemy_base", "臺北")

    default_player_orgs = {
        "派遣間諜": {"北京": 1, "上海": 1},
        "內應間諜": {"北京": 1},
    }
    default_enemy_orgs = {
        "派遣間諜": {"天津": 1, "杭州": 1, "香港城": 1},
        "內應間諜": {"天津": 1, "香港城": 1},
    }
    player.organizations = payload.get("orgs") or default_player_orgs[card_name]
    enemy.organizations = payload.get("enemy_orgs") or default_enemy_orgs[card_name]
    player.resources = {"money": 0, "propaganda": 0}
    enemy.resources = {"money": 0, "propaganda": 0}
    resources = {"propaganda": 1} if card_name == "派遣間諜" else {"propaganda": 2}
    player.hand = [Card(card_name, "spy", resources)]
    enemy.hand = [Card("對手手牌1", "command", {}), Card("對手手牌2", "command", {})]
    player.deck.draw_pile = []
    player.deck.discard_pile = []
    enemy.deck.draw_pile = []
    enemy.deck.discard_pile = []

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = player.id
    lobby_factions[game_id] = {player.id: player.faction_id, enemy.id: enemy.faction_id}
    lobby_bases[game_id] = {player.id: player.base, enemy.id: enemy.base}

    return {
        "success": True,
        "game_id": game_id,
        "player_id": player.id,
        "enemy_id": enemy.id,
        "card_name": card_name,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id, "base": p.base} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-support-proof")
def test_setup_support_proof(payload: dict):
    support_name = payload.get("support_name", "臺灣奧援")
    tier = int(payload.get("tier", 2) or 2)
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), payload.get("player_name", "player")), (str(uuid.uuid4()), payload.get("enemy_name", "red"))]
    game = Game(players)

    player = game.players[0]
    enemy = game.players[1]

    default_player_faction = {
        "臺灣奧援": "taiwan_green",
        "北國奧援": "liberals",
    }
    default_player_base = {
        "臺灣奧援": "臺北",
        "北國奧援": "海參崴",
    }
    default_orgs_by_card = {
        "臺灣奧援": {
            3: {"臺北": 1, "屏東": 1, "佬沃": 1, "馬祖": 1},
            2: {"臺北": 1, "屏東": 1, "佬沃": 1, "馬祖": 1},
            1: {"東京": 1},
        },
        "北國奧援": {
            3: {"海參崴": 1},
            2: {"巴黎": 1, "沖繩": 1},
            1: {"巴黎": 1, "日內瓦": 1},
        },
    }
    default_regions_by_card = {
        "臺灣奧援": {
            3: ['臺灣'],
            2: ['東洋', '南洋'],
            1: ['東洋'],
        },
        "北國奧援": {
            3: ['北國'],
            2: ['歐洲', '東洋'],
            1: ['歐洲'],
        },
    }
    default_enemy_orgs_by_card = {
        "臺灣奧援": {
            3: {"北京": 1, "福州": 1},
            2: {"北京": 1, "福州": 1},
            1: {"北京": 1},
        },
        "北國奧援": {
            3: {"北京": 1, "伯力": 1},
            2: {"北京": 1, "福州": 1},
            1: {"慕尼黑": 1},
        },
    }
    default_enemy_base = {
        "臺灣奧援": "北京",
        "北國奧援": "北京",
    }
    default_enemy_faction = {
        "臺灣奧援": "red_army",
        "北國奧援": "red_army",
    }

    player.faction_id = payload.get("faction_id", default_player_faction.get(support_name, "taiwan_green"))
    player.base = payload.get("base", default_player_base.get(support_name, "臺北"))
    player.organizations = payload.get("orgs") or default_orgs_by_card.get(support_name, {}).get(tier, {})
    player.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
    player.hand = [game._make_support_card(support_name)]
    player.deck.draw_pile = []
    player.deck.discard_pile = []

    enemy.faction_id = payload.get("enemy_faction_id", default_enemy_faction.get(support_name, "red_army"))
    enemy.base = payload.get("enemy_base", default_enemy_base.get(support_name, "北京"))
    enemy.organizations = payload.get("enemy_orgs") or default_enemy_orgs_by_card.get(support_name, {}).get(tier, {})
    enemy.resources = {"money": 0, "propaganda": 0}
    enemy_hand_names = payload.get("enemy_hand") or []
    enemy.hand = [Card(name, "command", {}) for name in enemy_hand_names]
    enemy.deck.draw_pile = []
    enemy.deck.discard_pile = []

    original_resolver = game._support_card_tier

    def forced_tier(target_player, card_name):
        if getattr(target_player, 'id', None) == player.id and card_name == support_name:
            matched = payload.get('matched_regions')
            if matched is None:
                matched = default_regions_by_card.get(support_name, {}).get(tier, [])
            return tier, 0, list(matched)
        return original_resolver(target_player, card_name)

    game._support_card_tier = forced_tier

    game.current_player_index = 0
    requested_phase = str(payload.get("turn_phase", "action") or "action").lower()
    game.turn_phase = TurnPhase.EVENT if requested_phase == "event" else TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = player.id
    lobby_factions[game_id] = {player.id: player.faction_id, enemy.id: enemy.faction_id}
    lobby_bases[game_id] = {player.id: player.base, enemy.id: enemy.base}

    auto_resolve_target_index = payload.get("auto_resolve_target_index")
    if auto_resolve_target_index is not None:
        played = game.play_card(0, mode='action')
        if played.get('pending_choice'):
            game.resolve_pending_choice(player.id, int(auto_resolve_target_index))

    return {
        "success": True,
        "game_id": game_id,
        "player_id": player.id,
        "tier": tier,
        "support_name": support_name,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "state": game.state(),
    }


@app.post("/test/setup-taiwan-support-proof")
def test_setup_taiwan_support_proof(payload: dict):
    scoped = dict(payload or {})
    scoped.setdefault("support_name", "臺灣奧援")
    return test_setup_support_proof(scoped)


@app.post("/test/setup-bait-exhaustion-ui")
def test_setup_bait_exhaustion_ui(payload: dict):
    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players)

    viewer = game.players[0]
    red = game.players[1]

    viewer.faction_id = payload.get("faction_id", "red_army")
    viewer.base = payload.get("base", "北京")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 0, "propaganda": 0}
    viewer.hand = [
        Card("誘導虛耗", "command", {"propaganda": 1}),
        Card("可移除手牌", "command", {}),
    ]
    top_card_name = payload.get("draw_top_card", "宣傳家")
    viewer.deck.draw_pile = [Card(top_card_name, "propaganda", {"propaganda": 1})]
    viewer.deck.discard_pile = []

    red.faction_id = "hong_kong"
    red.base = "香港城"
    red.organizations = {"香港城": 1}
    red.hand = [Card("對手被棄牌", "command", {})]
    red.deck.draw_pile = [Card("對手抽牌A", "command", {})]
    red.deck.discard_pile = []

    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    game.id = game_id

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = viewer.id
    lobby_factions[game_id] = {viewer.id: viewer.faction_id, red.id: red.faction_id}
    lobby_bases[game_id] = {viewer.id: viewer.base, red.id: red.base}

    return {
        'success': True,
        'game_id': game_id,
        'player_id': viewer.id,
        'state': game.state(),
        'players': [{'id': p.id, 'name': p.name, 'faction': p.faction_id} for p in game.players],
    }


@app.post("/test/setup-manchuria-era-reorder-proof")
def test_setup_manchuria_era_reorder_proof(payload: dict):
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = "manchuria"
    red.faction_id = "red_army"
    viewer.base = "瀋陽"
    red.base = "北京"
    viewer.organizations = {"瀋陽": 1}
    red.organizations = {"北京": 1}
    viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    viewer.deck.draw_pile = [Card(f"底牌{i}", "command", {}) for i in range(3)] + [
        Card("第七張", "command", {}),
        Card("第六張", "command", {}),
        Card("第五張", "command", {}),
        Card("第四張", "command", {}),
        Card("第三張", "command", {}),
        Card("第二張", "command", {}),
        Card("第一張", "command", {}),
    ]
    viewer.deck.discard_pile = []
    red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.era_engine.activate_era("manchuria")
    era = game.era_engine.get_definition("manchuria")
    runtime_effects = game._apply_era_activation_effects(era)
    game.era_notification = {
        "id": era.get("id") if era else "manchuria",
        "name": era.get("name") if era else "[滿洲]滿洲地方派系凝聚",
        "runtime_effects": runtime_effects,
    }

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
        "era_name": era.get("name") if era else None,
        "runtime_effects": runtime_effects,
        "url": f"/?game_id={game_id}&player_id={viewer.id}",
        "state": game.state(),
    }


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/test/setup-event-card-proof")
def test_setup_event_card_proof(payload: dict):
    event_name = payload.get("event_name") or "香港抗暴之戰"
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    game.players[0].faction_id = "liberals"
    game.players[1].faction_id = "red_army"
    game.players[0].base = "臺北"
    game.players[1].base = "北京"
    game.players[0].organizations = {"臺北": 1}
    game.players[1].organizations = {"北京": 1}
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.EVENT
    game.players[0].hand = [Card("合作談判", "command", {}), Card("追隨者", "propaganda", {"propaganda": 1})]
    game.players[0].deck.discard_pile = []
    event = game._event_by_name(event_name) or game._event_by_name("香港抗暴之戰")
    if payload.get("current_event_active") and event:
        game.current_event = event
        game.event_progress = {
            "count": 0,
            "required": int(event.get("trigger", {}).get("count", 1) or 1),
            "succeeded": False,
            "settled": False,
            "status": "active",
        }
        game.event_notification = game._event_display_payload()
        game.turn_phase = TurnPhase.ACTION
        game.event_deck.draw_pile = []
        game.event_deck.discard_pile = []
    else:
        game.event_deck.draw_pile = [event] if event else []
        game.event_deck.discard_pile = []

    game_id = str(uuid.uuid4())
    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = game.players[0].id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": game.players[0].id,
        "red_player_id": game.players[1].id,
        "event_name": event.get("name") if event else None,
        "url": f"/?game_id={game_id}&player_id={game.players[0].id}",
        "state": game.state(),
    }


@app.post("/test/setup-national-people-congress-red-dissolve-proof")
def test_setup_national_people_congress_red_dissolve_proof(payload: dict):
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = "liberals"
    red.faction_id = "red_army"
    viewer.base = "臺北"
    red.base = "北京"
    viewer.organizations = {"北京": 1}
    red.organizations = {"臺北": 1}
    viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    event = game._event_by_name("全國人大召開")
    game.current_event = event
    game.event_progress = {
        "count": 0,
        "required": int((event or {}).get("trigger", {}).get("count", 1) or 1),
        "succeeded": False,
        "settled": True,
        "status": "failure",
    }
    if event:
        game._apply_event_effect(event.get("failure"), viewer, outcome="failure")
    game.event_notification = game._event_display_payload()
    game.event_deck.draw_pile = []
    game.event_deck.discard_pile = [event] if event else []

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
        "url": f"/?game_id={game_id}&player_id={red.id}",
        "state": game.state(),
    }


@app.post("/test/setup-trade-war-event-proof")
def test_setup_trade_war_event_proof(payload: dict):
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = "liberals"
    red.faction_id = "red_army"
    viewer.base = "臺北"
    red.base = "北京"
    viewer.organizations = {"臺北": 1}
    red.organizations = {"北京": 1}
    viewer.resources = {"money": 4, "propaganda": 0}
    viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    viewer.deck.draw_pile = [Card("原牌庫頂下方", "command", {})]
    viewer.deck.discard_pile = [Card("舊棄牌", "command", {})]
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    event = game._event_by_name("貿易戰加劇")
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
    game.purchase_area = game._static_purchase_cards() + [Card("擴大戰果", "command", {})]

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
        "purchase_index": len(game._static_purchase_cards()),
        "url": f"/?game_id={game_id}&player_id={viewer.id}",
        "state": game.state(),
    }


@app.post("/test/setup-discard-topdeck-choice")
def test_setup_discard_topdeck_choice(payload: dict):
    """Put the viewer straight into a 貿易戰加劇 topdeck-from-discard card choice over a
    large discard pile, to exercise the scrollable choice grid."""
    discard_count = int(payload.get("discard_count", 18) or 18)
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = "liberals"
    red.faction_id = "red_army"
    viewer.base = "臺北"
    red.base = "北京"
    viewer.organizations = {"臺北": 1}
    red.organizations = {"北京": 1}
    viewer.resources = {"money": 0, "propaganda": 0}
    viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    viewer.deck.draw_pile = [Card("原牌庫頂下方", "command", {})]
    viewer.deck.discard_pile = [Card(f"棄牌{i + 1:02d}", "command", {}) for i in range(discard_count)]

    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    event = game._event_by_name("貿易戰加劇")
    game.current_event = event
    game.event_notification = game._event_display_payload()
    game.event_deck.draw_pile = []
    game.event_deck.discard_pile = []

    # Trigger the success effect directly so the topdeck-from-discard card choice is pending.
    game._apply_event_effect({"type": "topdeck_from_discard", "count": 1}, viewer)

    game_id = str(uuid.uuid4())
    game.id = game_id
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
        "discard_count": discard_count,
        "url": f"/?game_id={game_id}&player_id={viewer.id}",
        "state": game.state(),
    }


@app.post("/test/setup-ccdi-choice")
def test_setup_ccdi_choice(payload: dict):
    """Put a Red Army player straight into the 中紀委 (red_army_ccdi_discard_draw) choice,
    to exercise the cancellable-choice close/cancel behaviour."""
    players = [(str(uuid.uuid4()), "red"), (str(uuid.uuid4()), "opp")]
    game = Game(players, market_mode="all_cards")
    red = game.players[0]
    opp = game.players[1]
    red.faction_id = "red_army"
    opp.faction_id = "liberals"
    red.base = "北京"
    red.organizations = {"北京": 1}
    opp.base = "臺北"
    opp.organizations = {"臺北": 1}
    red.hand = [Card("手牌甲", "command", {}), Card("手牌乙", "command", {}), Card("手牌丙", "command", {})]
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.turn_log = game._new_turn_log()

    game._activated_faction_action(red, "中紀委")

    game_id = str(uuid.uuid4())
    game.id = game_id
    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = red.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": red.id,
        "url": f"/?game_id={game_id}&player_id={red.id}",
        "state": game.state(),
    }


@app.post("/test/setup-elite-defection-event-proof")
def test_setup_elite_defection_event_proof(payload: dict):
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = "liberals"
    red.faction_id = "red_army"
    viewer.base = "臺北"
    red.base = "北京"
    viewer.organizations = {"臺北": 1, "桃園": 1, "基隆": 1, "臺中": 1}
    red.organizations = {"北京": 1}
    viewer.moves_left = 3
    viewer.resources = {"money": 0, "propaganda": 0}
    viewer.hand = [Card("手牌移除目標", "command", {}), Card("手牌保留", "command", {})]
    viewer.deck.draw_pile = [Card("牌庫保留", "command", {})]
    viewer.deck.discard_pile = [Card("棄牌移除目標", "command", {})]
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    event = game._event_by_name("紅軍權貴出逃")
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
        "moves": [
            {"from": "桃園", "to": "新竹", "mode": "rail"},
            {"from": "基隆", "to": "新北", "mode": "road"},
            {"from": "臺中", "to": "南投", "mode": "road"},
        ],
        "url": f"/?game_id={game_id}&player_id={viewer.id}",
        "state": game.state(),
    }


@app.post("/test/setup-belt-road-red-turn-proof")
def test_setup_belt_road_red_turn_proof(payload: dict):
    players = [(str(uuid.uuid4()), "BEN"), (str(uuid.uuid4()), "紅軍")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    viewer.faction_id = payload.get("viewer_faction", "liberals")
    red.faction_id = "red_army"
    viewer.base = payload.get("viewer_base", "臺北")
    red.base = "北京"
    viewer.organizations = {viewer.base: 1}
    red.organizations = {"北京": 1}
    viewer.hand = [Card("BEN 保留手牌", "money", {"money": 1})]
    red.hand = [Card("紅軍保留手牌", "propaganda", {"propaganda": 1})]
    game.pending_base_choices = {}
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.round_start_player_index = 0
    game.turn_phase = TurnPhase.EVENT
    event_name = payload.get("event_name", "一帶一路 南洋")
    event = game._event_by_name(event_name)
    game.event_deck.draw_pile = [event] if event else []
    game.event_deck.discard_pile = []
    game.current_event = None
    game.event_progress = None
    game.event_notification = None
    game.pending_choice = None
    draw_result = game.advance_turn_phase()
    initial_state = game.state()
    advance_results = []
    if payload.get("advance_to_red", False):
        for _ in range(3):
            advance_results.append(game.advance_turn_phase())
            if game.current_player_index == 1 and game.turn_phase == TurnPhase.EVENT:
                break
    if payload.get("stale_visual_build", False):
        stale_town = payload.get("stale_town", "曼谷")
        if game.pending_choice and game.pending_choice.get("choice_key") == "event_build_organization":
            red.organizations[stale_town] = max(1, red.organizations.get(stale_town, 0))

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
        "event_name": event_name,
        "draw_result": draw_result,
        "advance_results": advance_results,
        "initial_state": initial_state,
        "url": f"/?game_id={game_id}&player_id={red.id}",
        "state": game.state(),
    }


@app.post("/test/setup-tibet-era-red-build-proof")
def test_setup_tibet_era_red_build_proof(payload: dict):
    players = [(str(uuid.uuid4()), "藏國"), (str(uuid.uuid4()), "紅軍")]
    game = Game(players, market_mode="all_cards")
    actor = game.players[0]
    red = game.players[1]
    actor.faction_id = "tibet"
    red.faction_id = "red_army"
    actor.base = "拉薩"
    red.base = "北京"
    actor.resources = {"money": 0, "propaganda": 0}
    red.resources = {"money": 0, "propaganda": 0}
    tibet_town = "列城"
    actor.organizations = {tibet_town: 1}
    red.organizations = {"北京": 1}
    red.hand = [
        Card("紅軍棄牌 UI proof 一", "money", {"money": 1}),
        Card("紅軍棄牌 UI proof 二", "propaganda", {"propaganda": 1}),
        Card("紅軍保留 UI proof", "money", {"money": 1}),
    ]
    red.deck.discard_pile = []
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 1
    game.turn_phase = TurnPhase.ACTION
    game.era_engine.activate_era("tibet")
    era = game.era_engine.get_definition("tibet")
    runtime_effects = game._apply_era_activation_effects(era)
    discard_result = None
    if payload.get("resolve_discard", True):
        discard_indices = payload.get("discard_indices")
        if discard_indices is None:
            discard_indices = [0, 1]
        discard_result = game.resolve_pending_choice(red.id, discard_indices)

    game_id = str(uuid.uuid4())
    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = actor.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": red.id,
        "actor_player_id": actor.id,
        "tibet_town": tibet_town,
        "runtime_effects": runtime_effects,
        "discard_result": discard_result,
        "pending_choice": game.pending_choice,
        "url": f"/?game_id={game_id}&player_id={red.id}",
        "state": game.state(),
    }


@app.post("/test/setup-era-notification-proof")
def test_setup_era_notification_proof(payload: dict):
    era_id = payload.get("era_id") or payload.get("id") or "mongolia"
    players = [(str(uuid.uuid4()), "viewer"), (str(uuid.uuid4()), "red")]
    game = Game(players, market_mode="all_cards")
    viewer = game.players[0]
    red = game.players[1]
    era = game.era_engine.get_definition(era_id)
    if not era:
        return {"success": False, "error": f"Unknown era: {era_id}"}

    trigger = era.get("trigger") or {}
    camp_to_faction = {
        "mongol": ("mongol", "烏蘭巴托"),
        "tibet": ("tibet", "拉薩"),
        "kazakh": ("kazakh", "阿拉木圖"),
        "uyghur": ("uyghur", "烏魯木齊"),
        "manchuria": ("manchuria", "瀋陽"),
        "rebel": ("liberals", "上海"),
        "taiwan": ("taiwan_green", "臺北"),
        "hong_kong": ("hong_kong", "香港"),
    }
    viewer.faction_id, viewer.base = camp_to_faction.get(trigger.get("camp"), ("liberals", "上海"))
    red.faction_id = "red_army"
    red.base = "北京"
    viewer.organizations = {viewer.base: 1}
    red.organizations = {"北京": 1}
    viewer.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    red.hand = [Card("追隨者", "propaganda", {"propaganda": 1})]
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.era_engine.activate_era(era_id)
    game.era_notification = game._era_notification_payload(era)
    game.era_notification["runtime_effects"] = {
        "red_suppression": (era.get("effects") or {}).get("red_suppression"),
        "revolution_counterattack": (era.get("effects") or {}).get("revolution_counterattack"),
    }

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
        "era_id": era.get("id"),
        "era_name": era.get("name"),
        "url": f"/?game_id={game_id}&player_id={viewer.id}",
        "state": game.state(),
    }


@app.post("/test/setup-hong-kong-era-red-discard-proof")
def test_setup_hong_kong_era_red_discard_proof(payload: dict):
    players = [(str(uuid.uuid4()), "香港"), (str(uuid.uuid4()), "紅軍")]
    game = Game(players, market_mode="all_cards")
    actor = game.players[0]
    red = game.players[1]
    actor.faction_id = "hong_kong"
    red.faction_id = "red_army"
    actor.base = "香港城"
    red.base = "北京"
    actor.organizations = {"天津": 1}
    red.organizations = {"北京": 1}
    actor.hand = [Card("香港目標手牌", "money", {"money": 1}), Card("香港保留手牌", "propaganda", {"propaganda": 1})]
    actor.deck.discard_pile = []
    red.hand = [Card("內應間諜", "spy", {"propaganda": 2})]
    red.deck.discard_pile = []
    actor.resources = {"money": 0, "propaganda": 0}
    red.resources = {"money": 0, "propaganda": 0}
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 1
    game.turn_phase = TurnPhase.ACTION
    game.era_engine.activate_era("hong_kong")
    era = game.era_engine.get_definition("hong_kong")
    game.era_notification = game._era_notification_payload(era) if era else {
        "id": "hong_kong",
        "name": "[香港]香港人被自殺",
    }
    game.era_notification["runtime_effects"] = {
        "red_suppression": (era.get("effects") or {}).get("red_suppression") if era else None,
        "revolution_counterattack": (era.get("effects") or {}).get("revolution_counterattack") if era else None,
    }

    game_id = str(uuid.uuid4())
    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = actor.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": red.id,
        "red_player_id": red.id,
        "hong_kong_player_id": actor.id,
        "target_town": "天津",
        "red_url": f"/?game_id={game_id}&player_id={red.id}",
        "hong_kong_url": f"/?game_id={game_id}&player_id={actor.id}",
        "url": f"/?game_id={game_id}&player_id={red.id}",
        "state": game.state(),
    }


@app.post("/test/setup-uyghur-era-red-dissolve-proof")
def test_setup_uyghur_era_red_dissolve_proof(payload: dict):
    players = [(str(uuid.uuid4()), "維吾爾"), (str(uuid.uuid4()), "紅軍")]
    game = Game(players, market_mode="all_cards")
    actor = game.players[0]
    red = game.players[1]
    actor.faction_id = "uyghur_istanbul"
    red.faction_id = "red_army"
    actor.base = "烏魯木齊"
    red.base = "北京"
    actor.organizations = {"天津": 1}
    red.organizations = {"北京": 1}
    actor.hand = [Card("維吾爾棄牌 UI proof", "money", {"money": 1})]
    actor.deck.discard_pile = []
    red.hand = [Card("武裝者", "armed", {"propaganda": 1})]
    red.deck.discard_pile = []
    actor.resources = {"money": 0, "propaganda": 0}
    red.resources = {"money": 0, "propaganda": 0}
    game.pending_base_choices = []
    game.game_phase = GamePhase.MAIN
    game.current_player_index = 1
    game.turn_phase = TurnPhase.ACTION
    game.era_engine.activate_era("uyghur")
    play_result = game.play_card(0, mode="action", target_player_id=actor.id)
    discard_choice = dict(game.pending_choice or {})
    discard_result = game.resolve_pending_choice(actor.id, 0)

    game_id = str(uuid.uuid4())
    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = [(p.id, p.name) for p in game.players]
    lobby_hosts[game_id] = actor.id
    lobby_factions[game_id] = {p.id: p.faction_id for p in game.players}
    lobby_bases[game_id] = {p.id: p.base for p in game.players if p.base}
    lobby_ready[game_id] = {p.id: True for p in game.players}
    return {
        "success": True,
        "game_id": game_id,
        "player_id": red.id,
        "actor_player_id": actor.id,
        "play_result": play_result,
        "discard_choice": discard_choice,
        "discard_result": discard_result,
        "pending_choice": game.pending_choice,
        "url": f"/?game_id={game_id}&player_id={red.id}",
        "state": game.state(),
    }


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
