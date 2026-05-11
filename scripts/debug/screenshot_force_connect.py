from playwright.sync_api import sync_playwright
import requests
import time

BASE = "http://localhost:8000"

# ✅ Create room
r = requests.post(f"{BASE}/create")
data = r.json()
room_id = data["game_id"]
host_id = data["host_id"]

# ✅ Join player
r = requests.post(f"{BASE}/join", json={"game_id": room_id, "name": "Hong Kong"})
player_id = r.json()["player_id"]

# ✅ Start game
requests.post(f"{BASE}/start", json={"game_id": room_id, "player_id": host_id})

time.sleep(0.5)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto(BASE)

    # ✅ 直接注入 gameId / playerId 並呼叫 connect()
    page.evaluate(f"""
        gameId = '{room_id}';
        playerId = '{player_id}';
        connect();
    """)

    page.wait_for_selector("#commandGrid", state="visible", timeout=5000)

    time.sleep(1)

    page.screenshot(path="console_real_flow.png", full_page=True)

    browser.close()

print("✅ Forced connect screenshot saved")
