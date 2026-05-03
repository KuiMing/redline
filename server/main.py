from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game
from server.game_manager import GameManager
import uuid
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

manager = GameManager()
lobby = {}        # {game_id: [player_names]}
lobby_hosts = {}  # {game_id: host_player_id}


@app.post("/create")
def create_room():
    game_id = manager.create_room()
    host_id = str(uuid.uuid4())

    lobby[game_id] = []  # will store (player_id, name)
    lobby_hosts[game_id] = host_id

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

    manager.start_game(game_id, Game, lobby[game_id])

    # ✅ 對齊 Lobby player_id 與 Game.player.id
    game = manager.get_game(game_id)
    lobby_player_ids = list(manager.connections.get(game_id, {}).keys())

    for player, lobby_id in zip(game.players, lobby_player_ids):
        player.id = lobby_id

    return {"success": True}


@app.get("/lobby/{game_id}")
def lobby_state(game_id: str):
    if game_id not in lobby:
        return {"error": "Game not found"}

    return {
        "players": lobby[game_id],
        "host_id": lobby_hosts.get(game_id),
        "count": len(lobby[game_id])
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

@app.get("/")
def index():
    return FileResponse("static/index.html")
