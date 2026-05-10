from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game, TurnPhase, GamePhase
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

    categories = [
        {"id": "red_army", "label": "紅軍", "mode": "direct", "options": [resolve_ui_faction(by_id["red_army"])]},
        {"id": "taiwan", "label": "臺灣", "mode": "variant", "options": [resolve_ui_faction(by_id["taiwan_green"]), resolve_ui_faction(by_id["taiwan_blue"])]},
        {"id": "hong_kong", "label": "香港", "mode": "direct", "options": [resolve_ui_faction(by_id["hong_kong"])]},
        {"id": "uyghur", "label": "維吾爾", "mode": "direct", "options": [{"id": "uyghur_family", "name": "維吾爾"}]},
        {"id": "tibet", "label": "西藏", "mode": "direct", "options": [{"id": "tibet_family", "name": "西藏"}]},
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
    await websocket.send_json(game.state())

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "set_base":
                result = game.set_base_choice(player_id, data.get("town"), data.get("label"))
                if result and result.get("error"):
                    error_state = dict(game.state())
                    error_state["error"] = result.get("error")
                    await websocket.send_json(error_state)
                    continue
                for pid, ws in manager.connections.get(game_id, {}).items():
                    await ws.send_json(game.state())
                continue

            if game.current_player().id != player_id:
                await websocket.send_json({"error": "Not your turn"})
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
                result = game._activated_faction_action(game.current_player(), data.get("name"), guess=data.get("guess"))
            elif action == "resolve_choice":
                result = game.resolve_pending_choice(player_id, data.get("index"))

            if result and result.get("error"):
                error_state = dict(game.state())
                error_state["error"] = result.get("error")
                await websocket.send_json(error_state)
                continue

            # Broadcast updated state
            for pid, ws in manager.connections.get(game_id, {}).items():
                await ws.send_json(game.state())

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

    game = manager.get_game(game_id)
    if not game:
        return {"error": "Game not found"}

    player = next((p for p in game.players if p.id == player_id), None)
    if not player:
        return {"error": "Player not found"}

    player.hand = []
    for name in cards:
        player.hand.append(Card(name, "test", {}))

    if turn_phase == "action":
        game.turn_phase = TurnPhase.ACTION
    elif turn_phase == "event":
        game.turn_phase = TurnPhase.EVENT
    elif turn_phase == "end":
        game.turn_phase = TurnPhase.END

    return {"success": True, "hand": [c.name for c in player.hand], "turn_phase": game.turn_phase}


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

    if len(faction_ids) < 2:
        return {"error": "Need at least 2 faction ids"}

    game_id = str(uuid.uuid4())
    players = [(str(uuid.uuid4()), name) for name in player_names]
    game = Game(players)
    for player, faction_id in zip(game.players, faction_ids):
        player.faction_id = faction_id
    game.pending_base_choices = game._compute_pending_base_choices()
    if game.pending_base_choices:
        game.game_phase = GamePhase.BASE_SELECTION
    else:
        game._assign_starting_bases()
        game.game_phase = GamePhase.MAIN

    manager.games[game_id] = game
    manager.connections[game_id] = manager.connections.get(game_id, {})
    lobby[game_id] = list(zip([p.id for p in game.players], [p.name for p in game.players]))
    lobby_hosts[game_id] = game.players[0].id

    return {
        "success": True,
        "game_id": game_id,
        "players": [{"id": p.id, "name": p.name, "faction": p.faction_id} for p in game.players],
        "pending_base_choices": game.pending_base_choices,
        "game_phase": game.game_phase,
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

    viewer.faction_id = payload.get("faction_id", "tibet_dehradun")
    viewer.base = payload.get("base", "德拉敦")
    viewer.organizations = payload.get("orgs") or {viewer.base: 1}
    viewer.resources = payload.get("resources") or {"money": 4, "propaganda": 4}
    card_def = next(c for c in game.structured_cards if c.get("name") == "地下黨")
    viewer.hand = [Card(card_def["name"], card_def["type"], card_def.get("resources", {}))]

    red.faction_id = "red_army"
    red.base = "北京"
    red.organizations = {"北京": 1}
    red.hand = []

    game.purchase_deck.draw_pile = [
        Card("候選A", "command", {}),
        Card("候選B", "command", {}),
        Card("候選C", "command", {}),
    ]
    game.purchase_deck.discard_pile = []
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
        "purchase_draw_pile": [getattr(c, 'name', str(c)) for c in game.purchase_deck.draw_pile],
        "hand": [getattr(c, 'name', str(c)) for c in viewer.hand],
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

    # full purchase UI path: static 6 + 5 random
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


@app.get("/")
def index():
    return FileResponse("static/index.html")
