from playwright.sync_api import sync_playwright
from pathlib import Path

output_path = Path(__file__).parent / "console_preview.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:8000", wait_until="networkidle")
    page.wait_for_timeout(3000)
    page.screenshot(path=str(output_path), full_page=True)
    browser.close()

print(f"Saved to {output_path}")
