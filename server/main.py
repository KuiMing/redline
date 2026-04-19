from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from server.game import Game

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

current_game = None


@app.post("/create")
def create_game():
    global current_game
    player_names = ["Player1", "Player2", "Player3", "Player4"]
    current_game = Game(player_names)
    return current_game.state()


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
            <h1>Redline MVP</h1>
            <button onclick="createGame()">Create Game</button>
            <button onclick="loadState()">Load State</button>
            <pre id='output'></pre>

            <script>
                async function createGame() {
                    const res = await fetch('/create', {method: 'POST'});
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
