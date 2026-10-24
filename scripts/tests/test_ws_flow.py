import asyncio
import websockets
import requests
import json

BASE = "http://localhost:8000"

async def run_test():
    # 1️⃣ Create
    r = requests.post(f"{BASE}/create")
    data = r.json()
    room_id = data["game_id"]
    host_id = data["host_id"]
    print("Room:", room_id)

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

    # 5️⃣ Connect WebSockets
    uri_a = f"ws://localhost:8000/ws/{room_id}/{alice_id}"
    uri_b = f"ws://localhost:8000/ws/{room_id}/{bob_id}"

    async with websockets.connect(uri_a) as ws_a, \
               websockets.connect(uri_b) as ws_b:

        # 接收初始狀態
        msg_a = await ws_a.recv()
        msg_b = await ws_b.recv()

        print("Alice initial:", msg_a[:120])
        print("Bob initial:", msg_b[:120])

        # Alice 嘗試推進階段
        await ws_a.send(json.dumps({
            "action": "advance"
        }))

        # 兩邊都應收到更新
        update_a = await ws_a.recv()
        update_b = await ws_b.recv()

        print("Alice update:", update_a[:120])
        print("Bob update:", update_b[:120])

        print("✅ WebSocket sync OK")

asyncio.run(run_test())
