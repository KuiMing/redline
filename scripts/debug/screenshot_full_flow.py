from playwright.sync_api import sync_playwright
import requests
import time

BASE = "http://localhost:8000"

# ✅ Create room
r = requests.post(f"{BASE}/create")
data = r.json()
room_id = data["game_id"]
host_id = data["host_id"]

# ✅ Join players via API
r = requests.post(f"{BASE}/join", json={"game_id": room_id, "name": "Hong Kong"})
hk_id = r.json()["player_id"]

r = requests.post(f"{BASE}/join", json={"game_id": room_id, "name": "Red Army"})
red_id = r.json()["player_id"]

# ✅ Start game via API
requests.post(f"{BASE}/start", json={"game_id": room_id, "player_id": host_id})

time.sleep(0.5)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    page.goto(BASE)

    # ✅ Fill join form
    page.fill("#roomId", room_id)
    page.fill("#playerName", "Hong Kong")
    page.click("text=JOIN OPERATION")

    # ✅ Directly call connect() (avoid second /start call)
    page.evaluate("connect()")

    # ✅ Wait until commandGrid visible
    page.wait_for_selector("#commandGrid", state="visible", timeout=5000)

    time.sleep(1)

    page.screenshot(path="console_full_flow.png", full_page=True)

    browser.close()

print("✅ Full game flow screenshot saved")
