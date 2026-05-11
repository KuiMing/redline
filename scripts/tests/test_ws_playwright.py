from playwright.sync_api import sync_playwright
import requests
import time

BASE = "http://localhost:8000"

# Create room
r = requests.post(f"{BASE}/create")
data = r.json()
room_id = data["game_id"]
host_id = data["host_id"]

# Join A
r = requests.post(f"{BASE}/join", json={"game_id": room_id, "name": "Alice"})
alice_id = r.json()["player_id"]

# Join B
r = requests.post(f"{BASE}/join", json={"game_id": room_id, "name": "Bob"})
bob_id = r.json()["player_id"]

# Start game
requests.post(f"{BASE}/start", json={"game_id": room_id, "player_id": host_id})

time.sleep(0.5)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # Create two contexts (simulate two players)
    context_a = browser.new_context()
    context_b = browser.new_context()

    page_a = context_a.new_page()
    page_b = context_b.new_page()

    # Connect both players via WebSocket by loading page and injecting IDs
    page_a.goto(BASE)
    page_b.goto(BASE)

    # Manually connect using JS
    page_a.evaluate(f"""
        window.ws = new WebSocket('ws://localhost:8000/ws/{room_id}/{alice_id}');
    """)

    page_b.evaluate(f"""
        window.ws = new WebSocket('ws://localhost:8000/ws/{room_id}/{bob_id}');
    """)

    # Wait for initial state
    time.sleep(1)

    # Send advance from A
    page_a.evaluate("window.ws.send(JSON.stringify({action:'advance'}));")

    time.sleep(1)

    print("✅ Playwright multi-client test completed (no crash)")

    browser.close()
