from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game
from server.game_manager import GameManager
import uuid

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

manager = GameManager()
lobby = {}        # {game_id: [player_names]}
lobby_hosts = {}  # {game_id: player_id}


@app.post("/create")
def create_room():
    game_id = manager.create_room()
    lobby[game_id] = []
    return {"game_id": game_id}


@app.post("/join")
def join_game(payload: dict):
    game_id = payload.get("game_id")
    name = payload.get("name")

    if game_id not in lobby:
        return {"error": "Game not found"}

    if len(lobby[game_id]) >= 4:
        return {"error": "Room full"}

    player_id = str(uuid.uuid4())
    lobby[game_id].append(name)

    # 第一位加入者成為房主
    if game_id not in lobby_hosts:
        lobby_hosts[game_id] = player_id

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
    return {"success": True}


@app.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    await websocket.accept()

    game = manager.get_game(game_id)
    if not game:
        await websocket.send_json({"error": "Game not ready"})
        await websocket.close()
        return

    ok = manager.register_connection(game_id, player_id, websocket)
    if not ok:
        await websocket.send_json({"error": "Room full"})
        await websocket.close()
        return

    try:
        await websocket.send_json(game.project_state(player_id))

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if game.current_player().id != player_id:
                await websocket.send_json({"error": "Not your turn"})
                continue

            if action == "play_card":
                game.play_card(data.get("index"))
            elif action == "buy_card":
                game.buy_card(data.get("index"))
            elif action == "build":
                game.build_organization(data.get("town"))
            elif action == "move":
                game.move_organization(
                    data.get("from"),
                    data.get("to"),
                    data.get("mode", "road")
                )
            elif action == "advance":
                game.advance_turn_phase()

            await manager.broadcast(game_id, game)

    except WebSocketDisconnect:
        manager.remove_connection(game_id, player_id)


@app.get("/")
def index():
    return HTMLResponse("""
    <html>
        <head><title>Redline Lobby</title></head>
        <body>
            <h1>Redline Lobby</h1>

            <h3>Create Room</h3>
            <button onclick="createRoom()">Create</button>
            <div id='roomInfo'></div>

            <h3>Join Room</h3>
            <input id='roomId' placeholder='Room ID'>
            <input id='playerName' placeholder='Your Name'>
            <button onclick='joinRoom()'>Join</button>

            <div id='game'></div>

            <script>
                let ws = null;
                let gameId = null;
                let playerId = null;

                async function createRoom() {
                    const res = await fetch('/create', {method: 'POST'});
                    const data = await res.json();
                    gameId = data.game_id;
                    document.getElementById('roomInfo').innerText = 'Room ID: ' + gameId;
                }

                async function joinRoom() {
                    gameId = document.getElementById('roomId').value;
                    const name = document.getElementById('playerName').value;

                    const res = await fetch('/join', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({game_id: gameId, name})
                    });

                    const data = await res.json();
                    if (data.error) {
                        alert(data.error);
                        return;
                    }

                    playerId = data.player_id;
                    connect();
                }

                function connect() {
                    ws = new WebSocket(`ws://${location.host}/ws/${gameId}/${playerId}`);
                    ws.onmessage = (event) => {
                        const state = JSON.parse(event.data);
                        document.getElementById('game').innerHTML = '<pre>' + JSON.stringify(state, null, 2) + '</pre>';
                    };
                }
            </script>
        </body>
    </html>
    """)
