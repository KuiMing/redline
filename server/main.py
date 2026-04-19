from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from server.game import Game

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

current_game = None


class BaseRequest(BaseModel):
    town: str


@app.post("/create")
def create_game():
    global current_game
    player_names = ["Player1", "Player2", "Player3", "Player4"]
    current_game = Game(player_names)
    return current_game.state()


@app.post("/set_base")
def set_base(req: BaseRequest):
    if current_game is None:
        return {"error": "No game created"}
    result = current_game.set_base(req.town)
    return {**result, "state": current_game.state()}


@app.get("/state")
def get_state():
    if current_game is None:
        return {"error": "No game created"}
    return current_game.state()


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
        <head>
            <title>Redline Game</title>
        </head>
        <body>
            <h1>Redline MVP - Base Setup</h1>
            <button onclick="createGame()">Create Game</button>
            <br><br>
            <input id="townInput" placeholder="Enter town name" />
            <button onclick="setBase()">Set Base</button>
            <button onclick="loadState()">Load State</button>
            <pre id='output'></pre>

            <script>
                async function createGame() {
                    const res = await fetch('/create', {method: 'POST'});
                    const data = await res.json();
                    document.getElementById('output').textContent = JSON.stringify(data, null, 2);
                }

                async function setBase() {
                    const town = document.getElementById('townInput').value;
                    const res = await fetch('/set_base', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({town})
                    });
                    const data = await res.json();
                    document.getElementById('output').textContent = JSON.stringify(data, null, 2);
                }

                async function loadState() {
                    const res = await fetch('/state');
                    const data = await res.json();
                    document.getElementById('output').textContent = JSON.stringify(data, null, 2);
                }
            </script>
        </body>
    </html>
    """
