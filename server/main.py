from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game, TurnPhase, GamePhase
from server.cards import Card
from server.game_manager import GameManager
import uuid
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

manager = GameManager()
lobby = {}        # {game_id: [(player_id, name)]}
lobby_hosts = {}  # {game_id: host_player_id}
lobby_factions = {}  # {game_id: {player_id: faction_id}}


@app.post("/create")
def create_room():
    game_id = manager.create_room()
    host_id = str(uuid.uuid4())

    lobby[game_id] = []  # will store (player_id, name)
    lobby_hosts[game_id] = host_id
    lobby_factions[game_id] = {}

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
                return {"player_id": requested_player_id}
        player_id = requested_player_id
    else:
        player_id = str(uuid.uuid4())

    if len(lobby[game_id]) >= 4:
        return {"error": "Room full"}

    lobby[game_id].append((player_id, name))
    return {"player_id": player_id}


@app.post("/start")
def start_game(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")

    if game_id not in lobby:
        return {"error": "Game not found"}

    if len(lobby[game_id]) < 2:
        return {"error": "Need at least 2 players"}

    if lobby_hosts.get(game_id) != player_id:
        return {"error": "Only host can start"}

    player_list = lobby[game_id]
    chosen = lobby_factions.get(game_id, {})
    if len(chosen) != len(player_list):
        return {"error": "All players must choose factions first"}
    if sum(1 for fid in chosen.values() if fid == 'red_army') != 1:
        return {"error": "Exactly one player must choose red_army"}

    game = Game(player_list)
    # override randomized faction assignment with chosen factions
    for player in game.players:
        if player.id in chosen:
            player.faction_id = chosen[player.id]
    game.faction_by_id = {f["id"]: f for f in game.factions}
    game.pending_base_choices = game._compute_pending_base_choices()
    if game.pending_base_choices:
        game.game_phase = GamePhase.BASE_SELECTION
    else:
        game._assign_starting_bases()
        game.game_phase = GamePhase.MAIN

    manager.games[game_id] = game
    manager.connections.setdefault(game_id, {})

    return {"success": True}


@app.get("/factions")
def list_factions():
    from pathlib import Path
    import json
    from collections import defaultdict
    path = Path(__file__).resolve().parent.parent / "data" / "factions" / "all_faction.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    grouped = defaultdict(list)
    singles = []
    for x in data["factions"]:
        item = {"id": x["id"], "name": x["name"], "variant": x.get("variant"), "camp": x.get("camp"), "group": x.get("group")}
        grouped[x["name"]].append(item)

    families = []
    for name, items in grouped.items():
        if len(items) == 1:
            singles.append(items[0])
        else:
            families.append({
                "family": name,
                "options": items,
            })

    return {
        "factions": [{"id": x["id"], "name": x["name"], "variant": x.get("variant"), "camp": x.get("camp"), "group": x.get("group")} for x in data["factions"]],
        "families": families,
        "singles": singles,
    }


@app.post("/choose-faction")
def choose_faction(payload: dict):
    game_id = payload.get("game_id")
    player_id = payload.get("player_id")
    faction_id = payload.get("faction_id")

    if game_id not in lobby:
        return {"error": "Game not found"}

    if player_id not in [pid for pid, _ in lobby[game_id]]:
        return {"error": "Player not found in lobby"}

    # prevent duplicate faction selection
    taken = lobby_factions.get(game_id, {})
    if any(pid != player_id and fid == faction_id for pid, fid in taken.items()):
        return {"error": "Faction already taken"}

    lobby_factions.setdefault(game_id, {})[player_id] = faction_id
    return {"success": True, "factions": lobby_factions[game_id]}


@app.get("/lobby/{game_id}")
def lobby_state(game_id: str):
    if game_id not in lobby:
        return {"error": "Game not found"}

    return {
        "players": lobby[game_id],
        "host_id": lobby_hosts.get(game_id),
        "count": len(lobby[game_id]),
        "factions": lobby_factions.get(game_id, {})
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
                result = game.play_card(data.get("index"))
            elif action == "buy_card":
                result = game.buy_card(data.get("index"))
            elif action == "set_base":
                result = game.set_base_choice(player_id, data.get("town"))
            elif action == "build":
                result = game.build_organization(data.get("town"))
            elif action == "move":
                result = game.move_organization(
                    data.get("from"),
                    data.get("to"),
                    data.get("mode", "road")
                )

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


@app.get("/")
def index():
    return FileResponse("static/index.html")
