import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
RECORD_DIR = ROOT / "docs" / "records" / "map-ui"
BASE_URL = "http://127.0.0.1:8000"
OUT_JSON = RECORD_DIR / "ONE_ORGANIZATION_PER_TOWN_UI_VALIDATION.json"
OUT_MD = RECORD_DIR / "ONE_ORGANIZATION_PER_TOWN_UI_VALIDATION.md"
SCREENSHOT = RECORD_DIR / "one_organization_per_town_ui.png"


def post_json(path, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode("utf-8"))


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    setup = post_json(
        "/test/setup-enemy-occupancy-proof",
        {
            "actor_faction": "hong_kong",
            "actor_base": "香港城",
            "actor_town": "臺北",
            "red_town": "新竹",
            "moves_left": 2,
        },
    )
    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    record("official_test_setup_succeeded", setup.get("success") is True, setup)
    server_build_towns = {entry["town"] for entry in setup.get("card_build_choices", [])}
    record(
        "server_build_choices_exclude_all_occupied_towns",
        "臺北" not in server_build_towns and "新竹" not in server_build_towns,
        {"occupied": ["臺北", "新竹"], "sample": sorted(server_build_towns & {"桃園", "新竹", "新北", "臺北"})},
    )

    console_errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.goto(BASE_URL + setup["url"], wait_until="networkidle")
        page.wait_for_selector("#gameShell", state="visible", timeout=10000)
        reveal = page.locator("#eventRevealModal")
        if reveal.is_visible():
            reveal.click(position={"x": 8, "y": 8})
            reveal.wait_for(state="hidden")
        page.click('button.game-tab[data-view="map"]')
        page.wait_for_timeout(2200)

        ui_state = page.evaluate(
            """() => {
              const frame = document.getElementById('strategicMapFrame');
              const win = frame.contentWindow;
              win.__selectTownForTest('臺北');
              const doc = frame.contentDocument;
              const movement = win.movementOptionsForTown('臺北');
              const builds = win.buildOptionsForTown('臺北');
              win.refreshDirectBuildUi();
              return {
                movement,
                builds,
                directBuildDisabled: doc.getElementById('directBuildBtn').disabled,
                hint: doc.getElementById('directBuildHint').textContent,
                occupancy: win.lastGameState.map.towns,
              };
            }"""
        )
        road_and_rail = {
            entry["town"]
            for mode in ("road", "rail")
            for entry in ui_state["movement"][mode]
        }
        record(
            "map_movement_targets_follow_backend_projection_and_exclude_occupied_towns",
            "臺北" not in road_and_rail and "新竹" not in road_and_rail,
            {"movement": ui_state["movement"]},
        )
        record(
            "map_build_targets_exclude_every_occupied_town",
            "臺北" not in ui_state["builds"] and "新竹" not in ui_state["builds"] and "新北" in ui_state["builds"],
            {"builds": ui_state["builds"]},
        )
        record(
            "occupied_town_direct_build_control_is_disabled_with_rule_hint",
            ui_state["directBuildDisabled"] and "每城只能有 1 個組織" in ui_state["hint"],
            {"disabled": ui_state["directBuildDisabled"], "hint": ui_state["hint"]},
        )
        occupancy = ui_state["occupancy"]
        record(
            "official_ui_state_contains_one_piece_per_occupied_town",
            sum(int(entry.get("count", 0) or 0) for entry in occupancy.get("臺北", [])) == 1
            and sum(int(entry.get("count", 0) or 0) for entry in occupancy.get("新竹", [])) == 1,
            {"臺北": occupancy.get("臺北"), "新竹": occupancy.get("新竹")},
        )

        page.evaluate(
            """() => {
              const win = document.getElementById('strategicMapFrame').contentWindow;
              win.__redlinePlayableMap.setView([24.9, 121.15], 9, {animate:false});
            }"""
        )
        direct_hint = page.frame_locator("#strategicMapFrame").locator("#directBuildHint")
        direct_hint.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator("#strategicMapFrame").screenshot(path=str(SCREENSHOT))
        browser.close()

    record("browser_console_has_no_errors", not console_errors, {"errors": console_errors})
    summary = {
        "total": len(results),
        "passed": sum(1 for item in results if item["ok"]),
        "failed": sum(1 for item in results if not item["ok"]),
    }
    payload = {"summary": summary, "results": results, "screenshot": str(SCREENSHOT)}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 一城一組織正式 UI 驗證",
        "",
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        f"- screenshot: `{SCREENSHOT}`",
        "",
    ]
    lines.extend(f"- {'PASS' if item['ok'] else 'FAIL'} `{item['name']}` — {json.dumps(item['detail'], ensure_ascii=False)}" for item in results)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
