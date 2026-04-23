import uuid

class GameManager:
    def __init__(self):
        self.games = {}              # {game_id: Game}
        self.connections = {}        # {game_id: {player_id: websocket}}

    def create_room(self):
        game_id = str(uuid.uuid4())
        self.games[game_id] = None
        self.connections[game_id] = {}
        return game_id

    # Game is now started explicitly via /start endpoint
    def start_game(self, game_id, GameClass, players):
        if self.games.get(game_id) is None:
            self.games[game_id] = GameClass(players)
            return True
        return False

    def get_game(self, game_id):
        return self.games.get(game_id)

    def register_connection(self, game_id, player_id, websocket):
        if game_id not in self.connections:
            return False
        if len(self.connections[game_id]) >= 4:
            return False
        self.connections[game_id][player_id] = websocket
        return True

    def remove_connection(self, game_id, player_id):
        if game_id in self.connections:
            self.connections[game_id].pop(player_id, None)

    async def broadcast(self, game_id, game):
        if game_id not in self.connections:
            return
        for player_id, ws in self.connections[game_id].items():
            await ws.send_json(game.project_state(player_id))
