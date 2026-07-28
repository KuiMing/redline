import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "playtest-flow"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT_JSON = RECORD_DIR / "MY_FACTION_TAB_VALIDATION.json"
OUT_MD = RECORD_DIR / "MY_FACTION_TAB_VALIDATION.md"
SCREENSHOT = RECORD_DIR / "my_faction_tab.png"
SCREENSHOT_HK = RECORD_DIR / "my_faction_tab_hong_kong.png"


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode("utf-8"))


def open_game(browser, faction_id, base):
    setup = post_json(
        "/test/setup-support-card-play",
        {"support_name": "臺灣奧援", "faction_id": faction_id, "base": base},
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(
        f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
        wait_until="networkidle",
    )
    page.wait_for_selector("#gameShell", state="visible", timeout=10000)
    page.wait_for_timeout(700)
    page.evaluate("""() => {
      if (typeof closeEventReveal === 'function') closeEventReveal();
      const factionClose = document.getElementById('closeFactionActionModal');
      if (factionClose) factionClose.click();
    }""")
    return context, page


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    context, page = open_game(browser, "taiwan_green", "臺北")
    button = page.locator("#myFactionBtn")
    record(
        "my_faction_button_is_a_real_tab",
        button.is_visible()
        and button.get_attribute("data-view") == "myFaction"
        and button.get_attribute("onclick") is None,
        {
            "visible": button.is_visible(),
            "data_view": button.get_attribute("data-view"),
            "onclick": button.get_attribute("onclick"),
        },
    )

    button.click()
    page.wait_for_timeout(150)
    data = page.evaluate("""() => ({
      viewActive: document.getElementById('myFactionView')?.classList.contains('active'),
      tabActive: document.getElementById('myFactionBtn')?.classList.contains('active'),
      commandActive: document.getElementById('commandView')?.classList.contains('active'),
      modalExists: !!document.getElementById('myFactionModal'),
      overlayCount: document.querySelectorAll('#myFactionView .modal-overlay').length,
      title: document.getElementById('myFactionTitle')?.textContent,
      titleColor: document.querySelector('#myFactionTitle span')?.style.color,
      sections: [...document.querySelectorAll('#myFactionBody .faction-detail-section-title')].map(el => el.textContent),
      nonEmpty: [...document.querySelectorAll('#myFactionBody ul')].every(ul => ul.children.length > 0),
      baseText: document.querySelectorAll('#myFactionBody ul')[0]?.textContent,
      panelRect: document.querySelector('#myFactionView .personal-info-panel')?.getBoundingClientRect().toJSON(),
      viewRect: document.getElementById('myFactionView')?.getBoundingClientRect().toJSON(),
    })""")
    record(
        "faction_content_renders_in_main_view_without_modal",
        data["viewActive"]
        and data["tabActive"]
        and not data["commandActive"]
        and not data["modalExists"]
        and data["overlayCount"] == 0,
        data,
    )
    record(
        "faction_title_sections_and_base_are_complete",
        data["title"] == "臺灣（綠線）"
        and data["titleColor"] == "rgb(74, 222, 128)"
        and data["sections"] == ["根據地", "能力", "規則與限制", "獲勝條件"]
        and data["nonEmpty"]
        and "臺北" in (data["baseText"] or ""),
        data,
    )
    rect_ok = bool(data["panelRect"] and data["viewRect"]) and (
        data["panelRect"]["left"] >= data["viewRect"]["left"]
        and data["panelRect"]["right"] <= data["viewRect"]["right"]
        and data["panelRect"]["top"] >= data["viewRect"]["top"]
        and data["panelRect"]["bottom"] <= data["viewRect"]["bottom"]
    )
    record("faction_panel_fits_inside_main_view", rect_ok, data)
    page.screenshot(path=str(SCREENSHOT), full_page=True)

    page.click('#gameTabs [data-view="command"]')
    page.wait_for_timeout(100)
    switched = page.evaluate("""() => ({
      factionActive: document.getElementById('myFactionView')?.classList.contains('active'),
      commandActive: document.getElementById('commandView')?.classList.contains('active'),
    })""")
    record(
        "switching_tabs_leaves_personal_info_without_close_action",
        not switched["factionActive"] and switched["commandActive"],
        switched,
    )
    context.close()

    hk_context, hk_page = open_game(browser, "hong_kong", "香港城")
    hk_page.click("#myFactionBtn")
    hk_page.wait_for_timeout(150)
    hk_data = hk_page.evaluate("""() => ({
      title: document.getElementById('myFactionTitle')?.textContent,
      abilityCount: document.querySelectorAll('#myFactionBody ul')[1]?.children.length,
      active: document.getElementById('myFactionView')?.classList.contains('active'),
    })""")
    record(
        "hong_kong_faction_structure_renders_in_tab",
        hk_data["active"] and hk_data["title"] == "香港" and (hk_data["abilityCount"] or 0) > 0,
        hk_data,
    )
    hk_page.screenshot(path=str(SCREENSHOT_HK), full_page=True)
    hk_context.close()

    return {
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["ok"]),
            "failed": sum(1 for result in results if not result["ok"]),
        },
        "results": results,
        "screenshots": [str(SCREENSHOT), str(SCREENSHOT_HK)],
        "base_url": BASE_URL,
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 「我的陣營」頁內 Tab 驗證",
        "",
        "可重跑指令：`uv run --with playwright python scripts/validate_my_faction_modal.py`",
        "",
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
        f"- base URL: {payload['base_url']}",
        f"- screenshots: {', '.join(payload['screenshots'])}",
        "",
        "## Results",
    ]
    for result in payload["results"]:
        icon = "✅" if result["ok"] else "❌"
        lines.append(f"- {icon} `{result['name']}` — {json.dumps(result['detail'], ensure_ascii=False)}")
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
