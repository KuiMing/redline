#!/usr/bin/env python3
import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8781")
RECORD_DIR = BASE / "docs" / "records" / "purchase" / "international-line-payment"


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def add_check(checks, name, passed, details):
    checks.append({"name": name, "passed": bool(passed), "details": details})


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-underground-party",
        {
            "faction_id": "hong_kong",
            "base": "倫敦",
            "resources": {"money": 3, "propaganda": 2},
        },
    )
    game_id = setup["game_id"]
    player_id = setup["player_id"]
    initial_state = setup["state"]
    thinker_index = initial_state["purchase_area"].index("思想家")
    initial_supply = initial_state["static_purchase_supply"]["思想家"]
    checks = []
    console_errors = []
    page_errors = []

    add_check(
        checks,
        "server_projects_mixed_payment_for_thinker",
        initial_state["purchase_area_costs"][thinker_index] == {"money": 0, "propaganda": 5}
        and initial_state["purchase_area_payments"][thinker_index] == {"money": 3, "propaganda": 2}
        and initial_state["purchase_area_affordable"][thinker_index] is True,
        {
            "cost": initial_state["purchase_area_costs"][thinker_index],
            "payment": initial_state["purchase_area_payments"][thinker_index],
            "policy": initial_state.get("purchase_payment_policy"),
        },
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={game_id}&player_id={player_id}&v=international-line-payment-proof",
            wait_until="domcontentloaded",
        )
        page.wait_for_function(
            "window.lastGameState && document.querySelectorAll('#purchaseStatic .card').length === 6",
            timeout=15000,
        )
        page.wait_for_timeout(350)
        reveal = page.locator("#eventRevealModal")
        if reveal.count() and reveal.is_visible():
            page.evaluate("closeEventReveal()")
            page.wait_for_timeout(200)

        thinker = page.locator("#purchaseStatic .card").filter(has_text="思想家").first
        thinker.locator(".purchase-card-checkbox input").check()
        page.wait_for_timeout(200)
        summary = page.locator("#purchaseSelectionSummary").inner_text()
        buy_enabled = not page.locator("#openPurchaseConfirmBtn").is_disabled()
        selected_shot = RECORD_DIR / "01-thinker-selected-3-money-2-propaganda.png"
        page.screenshot(path=str(selected_shot), full_page=True)
        add_check(
            checks,
            "selection_summary_uses_three_money_and_two_propaganda",
            summary == "已選 1 張｜合計 3 資金 ＋ 2 宣傳" and buy_enabled,
            {"summary": summary, "buy_enabled": buy_enabled, "screenshot": str(selected_shot.relative_to(BASE))},
        )

        page.locator("#openPurchaseConfirmBtn").click()
        page.wait_for_timeout(200)
        modal_card = page.locator("#purchaseConfirmCards").inner_text()
        modal_total = page.locator("#purchaseConfirmTotal").inner_text()
        confirm_enabled = not page.locator("#confirmPurchaseBtn").is_disabled()
        modal_shot = RECORD_DIR / "02-confirm-mixed-payment.png"
        page.screenshot(path=str(modal_shot), full_page=True)
        add_check(
            checks,
            "confirmation_modal_shows_mixed_payment",
            "思想家" in modal_card
            and "3 資金 ＋ 2 宣傳" in modal_card
            and modal_total == "共 1 張｜合計 3 資金 ＋ 2 宣傳"
            and confirm_enabled,
            {
                "card": modal_card,
                "total": modal_total,
                "confirm_enabled": confirm_enabled,
                "screenshot": str(modal_shot.relative_to(BASE)),
            },
        )

        page.locator("#confirmPurchaseBtn").click()
        page.wait_for_function(
            "([pid, supply]) => { const s = window.lastGameState; const p = s && s.players.find(x => x.id === pid); return p && p.resources.money === 0 && p.resources.propaganda === 0 && s.static_purchase_supply['思想家'] === supply - 1; }",
            arg=[player_id, initial_supply],
            timeout=10000,
        )
        page.wait_for_timeout(250)
        final_state = page.evaluate("window.lastGameState")
        player = next(item for item in final_state["players"] if item["id"] == player_id)
        trigger_logs = [entry for entry in final_state["action_log"] if "triggered 國際線 to pay propaganda with money" in entry]
        after_shot = RECORD_DIR / "03-after-purchase.png"
        page.screenshot(path=str(after_shot), full_page=True)
        add_check(
            checks,
            "purchase_deducts_resources_and_moves_thinker",
            player["resources"] == {"money": 0, "propaganda": 0}
            and "思想家" in player["discard_pile"]
            and final_state["static_purchase_supply"]["思想家"] == initial_supply - 1
            and len(trigger_logs) == 1,
            {
                "resources": player["resources"],
                "discard_pile": player["discard_pile"],
                "thinker_supply": final_state["static_purchase_supply"]["思想家"],
                "trigger_logs": trigger_logs,
                "screenshot": str(after_shot.relative_to(BASE)),
            },
        )
        browser.close()

    add_check(
        checks,
        "browser_console_is_clean",
        not console_errors and not page_errors,
        {"console_errors": console_errors, "page_errors": page_errors},
    )
    summary = {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
    }
    report = {"summary": summary, "checks": checks}
    json_path = RECORD_DIR / "INTERNATIONAL_LINE_PAYMENT_VALIDATION.json"
    md_path = RECORD_DIR / "INTERNATIONAL_LINE_PAYMENT_VALIDATION.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(
        "# 國際線混合付款 Browser 驗證\n\n"
        "香港根據地位於倫敦，玩家持有 3 資金與 2 宣傳，購買費用為 5 宣傳的思想家。\n\n"
        f"- Checks: {summary['passed']}/{summary['total']} passed\n"
        "- Expected payment: 3 資金 ＋ 2 宣傳\n"
        "- Expected final resources: 0 資金 ＋ 0 宣傳\n\n"
        "```json\n" + json.dumps(report, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps({"summary": summary, "record_dir": str(RECORD_DIR)}, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
