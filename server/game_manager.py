import uuid

class GameManager:
    def __init__(self):
        self.games = {}              # {game_id: Game}
        self.connections = {}        # {game_id: {player_id: [websocket, ...]}}

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
        current = self.connections[game_id]
        # 人數上限只限制「不同玩家」的數量；同一位玩家重新連線（重新整理、睡眠喚醒、
        # 戰略地圖 iframe 重連）必須永遠允許，否則滿桌 4 人時任何一次重連都會被拒絕，
        # 該玩家從此收不到任何盤面更新。
        if player_id not in current and len(current) >= 4:
            return False
        sockets = current.setdefault(player_id, [])
        if websocket not in sockets:
            sockets.append(websocket)
        return True

    def remove_connection(self, game_id, player_id, websocket=None):
        """移除連線。傳入 websocket 時只有「目前登記的就是這條連線」才會移除，
        避免舊連線的 handler 收尾時，把該玩家後來建立的新連線一起踢掉。"""
        if game_id not in self.connections:
            return
        sockets = self.connections[game_id].get(player_id) or []
        if websocket is None:
            self.connections[game_id].pop(player_id, None)
            return
        if websocket not in sockets:
            return
        sockets.remove(websocket)
        if not sockets:
            self.connections[game_id].pop(player_id, None)

    async def broadcast(self, game_id, game):
        if game_id not in self.connections:
            return
        for player_id, sockets in list(self.connections[game_id].items()):
            state = game.project_state(player_id)
            for ws in list(sockets):
                try:
                    await ws.send_json(state)
                except Exception:
                    self.remove_connection(game_id, player_id, ws)


manager = GameManager()
