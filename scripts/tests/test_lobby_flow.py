import requests

BASE = "http://localhost:8000"

print("1️⃣ Create room")
r = requests.post(f"{BASE}/create")
print("Create status:", r.status_code, r.text)
create_data = r.json()
room_id = create_data["game_id"]
host_id = create_data["host_id"]

print("2️⃣ Join player A")
r = requests.post(f"{BASE}/join", json={"game_id": room_id, "name": "Alice"})
print("Join A status:", r.status_code, r.text)
alice_id = r.json()["player_id"]

print("3️⃣ Join player B")
r = requests.post(f"{BASE}/join", json={"game_id": room_id, "name": "Bob"})
print("Join B status:", r.status_code, r.text)
bob_id = r.json()["player_id"]

print("4️⃣ Check lobby state")
r = requests.get(f"{BASE}/lobby/{room_id}")
print("Lobby status:", r.status_code, r.text)

print("5️⃣ Attempt start with non-host")
r = requests.post(f"{BASE}/start", json={"game_id": room_id, "player_id": alice_id})
print("Non-host start:", r.status_code, r.text)

print("6️⃣ Start with host")
r = requests.post(f"{BASE}/start", json={"game_id": room_id, "player_id": host_id})
print("Host start:", r.status_code, r.text)

print("✅ Test finished")