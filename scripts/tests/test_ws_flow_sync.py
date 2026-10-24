import websocket
import requests
import json
import time

BASE = "http://localhost:8000"

# 1️⃣ Create
r = requests.post(f"{BASE}/create")
data = r.json()
room_id = data["game_id"]
host_id = data["host_id"]

# 2️⃣ Join A
r = requests.post(f"{BASE}/join", json={
    "game_id": room_id,
    "name": "Alice"
})
alice_id = r.json()["player_id"]

# 3️⃣ Join B
r = requests.post(f"{BASE}/join", json={
    "game_id": room_id,
    "name": "Bob"
})
bob_id = r.json()["player_id"]

# 4️⃣ Start
r = requests.post(f"{BASE}/start", json={
    "game_id": room_id,
    "player_id": host_id
})
print("Start:", r.json())

# ✅ 等待 Game 完全建立
time.sleep(0.6)

# 5️⃣ Connect A
ws_a = websocket.create_connection(
    f"ws://localhost:8000/ws/{room_id}/{alice_id}"
)

# 6️⃣ Connect B
ws_b = websocket.create_connection(
    f"ws://localhost:8000/ws/{room_id}/{bob_id}"
)

# 7️⃣ Receive initial state
print("Alice initial:", ws_a.recv()[:120])
print("Bob initial:", ws_b.recv()[:120])

# 8️⃣ Alice advance
ws_a.send(json.dumps({"action": "advance"}))

time.sleep(0.5)

print("Alice update:", ws_a.recv()[:120])
print("Bob update:", ws_b.recv()[:120])

print("✅ WebSocket sync OK")

ws_a.close()
ws_b.close()
