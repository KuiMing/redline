from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game
from server.game_manager import GameManager
import uuid

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

manager = GameManager()


@app.post("/create")
def create_game():
    # Temporary fixed 4 players; later can be dynamic
    player_names = ["Player1", "Player2", "Player3", "Player4"]
    game = manager.create_game(Game, player_names)
    return {"game_id": game.id}


@app.websocket("/ws/{game_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
    await websocket.accept()

    game = manager.get_game(game_id)
    if not game:
        await websocket.send_json({"error": "Game not found"})
        await websocket.close()
        return

    ok = manager.register_connection(game_id, player_id, websocket)
    if not ok:
        await websocket.send_json({"error": "Room full"})
        await websocket.close()
        return

    try:
        # Send initial projected state
        await websocket.send_json(game.project_state(player_id))

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            # Turn lock
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
        <head><title>Redline Multiplayer</title></head>
        <body>
            <h1>Redline Multiplayer</h1>
            <button onclick="createGame()">Create Game</button>
            <div id='game'></div>
            <script>
                let ws = null;
                let gameId = null;
                let playerId = null;

                async function createGame() {
                    const res = await fetch('/create', {method: 'POST'});
                    const data = await res.json();
                    gameId = data.game_id;
                    playerId = crypto.randomUUID();
                    connect();
                }

                function connect() {
                    ws = new WebSocket(`ws://${location.host}/ws/${gameId}/${playerId}`);

                    ws.onmessage = (event) => {
                        const state = JSON.parse(event.data);
                        render(state);
                    };
                }

                function send(action, payload={}) {
                    ws.send(JSON.stringify({action, ...payload}));
                }

                function render(state) {
                    const container = document.getElementById('game');
                    if (state.error) {
                        container.innerHTML = state.error;
                        return;
                    }

                    container.innerHTML = `<pre>${JSON.stringify(state, null, 2)}</pre>`;
                }
            </script>
        </body>
    </html>
    """)
