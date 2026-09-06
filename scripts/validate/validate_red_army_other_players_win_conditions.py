"""Focused Browser UI validator for the red-army "other players' win conditions" pane.

Feature (2026-09-06 使用者需求): when the red army player opens "我的陣營", the
right-hand pane that normally shows their personal 時代關卡 has no content for
red army (it has no personal era stage), so it now lists every other player in
the game with their name, faction and win condition instead. Non-red-army
players keep the original 時代關卡 pane unchanged.
"""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "faction-ui"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT_JSON = RECORD_DIR / "RED_ARMY_OTHER_PLAYERS_WIN_CONDITIONS_VALIDATION.json"
OUT_MD = RECORD_DIR / "RED_ARMY_OTHER_PLAYERS_WIN_CONDITIONS_VALIDATION.md"
RED_SCREENSHOT = RECORD_DIR / "red_army_other_players_win_conditions.png"
NON_RED_SCREENSHOT = RECORD_DIR / "non_red_army_era_stage_unchanged.png"


def post_json(path, payload=None):
    import urllib.request

    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode("utf-8"))


def setup_scenario():
    # 沿用既有的「合作談判」多人測試 fixture：actor=自由派、ally=香港、
    # enemy=紅軍、observer=臺灣（綠線）。四位玩家、四種不同陣營，剛好用來驗證
    # 紅軍視角要同時列出三位其他玩家，且陣營各不相同。
    last = None
    for _ in range(3):
        last = post_json("/test/setup-negotiation-proof", {})
        if last.get("success") and last.get("game_id") and last.get("enemy_player_id"):
            return last
    raise RuntimeError(f"negotiation proof setup failed: {last}")


def open_game(browser, game_id, player_id):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(
        f"{BASE_URL}/?game_id={game_id}&player_id={player_id}",
        wait_until="networkidle",
    )
    page.wait_for_selector("#gameShell", state="visible", timeout=10000)
    page.wait_for_timeout(700)
    page.evaluate("""() => {
      if (typeof closeEventReveal === 'function') closeEventReveal();
      if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
      const factionClose = document.getElementById('closeFactionActionModal');
      if (factionClose) factionClose.click();
    }""")
    page.wait_for_timeout(100)
    return context, page


def inspect_pane(page):
    return page.evaluate("""() => {
      const bodyText = document.getElementById('myEraStageBody')?.innerText || '';
      return {
        panelLabel: document.getElementById('myEraStagePanelLabel')?.textContent,
        title: document.getElementById('myEraStageTitle')?.textContent,
        status: document.getElementById('myEraStageStatus')?.textContent,
        statusClass: document.getElementById('myEraStageStatus')?.className,
        summary: document.getElementById('myEraStageSummary')?.textContent,
        sections: [...document.querySelectorAll('#myEraStageBody .era-achievement-section-title')].map(el => el.textContent),
        wins: [...document.querySelectorAll('#myEraStageBody .my-era-stage-other-wins')].map(
          ul => [...ul.querySelectorAll('li')].map(li => li.textContent)
        ),
        bodyText,
        scrollable: (() => {
          const el = document.getElementById('myEraStageBody');
          return el ? el.classList.contains('personal-info-scroll') : false;
        })(),
      };
    }""")


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    setup = setup_scenario()
    game_id = setup["game_id"]
    enemy_id = setup["enemy_player_id"]
    state = setup["state"]
    players = {p["name"]: p for p in state["players"]}
    record(
        "fixture_has_red_army_viewer_and_three_distinct_other_factions",
        players.get("Enemy", {}).get("faction") == "red_army"
        and len({p["faction"] for p in state["players"]}) == 4,
        {"players": state["players"]},
    )

    red_context, red_page = open_game(browser, game_id, enemy_id)
    red_page.click("#myFactionBtn")
    red_page.wait_for_timeout(150)
    red_pane = inspect_pane(red_page)
    record(
        "red_army_pane_relabeled_to_other_players_win_conditions",
        red_pane["panelLabel"] == "其他玩家獲勝條件"
        and red_pane["title"] == "非紅軍的獲勝條件"
        and red_pane["status"] == "共 3 位其他玩家",
        red_pane,
    )
    record(
        "red_army_pane_lists_every_other_player_name_and_faction",
        set(red_pane["sections"]) == {"Actor｜自由派", "Ally｜香港", "Observer｜臺灣（綠線）"},
        red_pane,
    )
    record(
        "red_army_pane_shows_win_condition_text_for_each_other_player",
        len(red_pane["wins"]) == 3
        and all(wins and "14" in wins[0] and "牆內" in wins[0] for wins in red_pane["wins"]),
        red_pane,
    )
    record(
        "red_army_pane_does_not_leak_other_players_hand_contents",
        "合作談判" not in red_pane["bodyText"],
        {"bodyText": red_pane["bodyText"]},
    )
    record(
        "red_army_pane_keeps_scrollable_layout",
        red_pane["scrollable"],
        red_pane,
    )
    red_page.screenshot(path=str(RED_SCREENSHOT), full_page=True)
    red_context.close()

    ally_id = players["Ally"]["id"]
    ally_context, ally_page = open_game(browser, game_id, ally_id)
    ally_page.click("#myFactionBtn")
    ally_page.wait_for_timeout(150)
    ally_pane = inspect_pane(ally_page)
    record(
        "non_red_army_player_still_sees_personal_era_stage_pane_unchanged",
        ally_pane["panelLabel"] == "時代關卡"
        and ally_pane["title"] != "非紅軍的獲勝條件"
        and "共 " not in (ally_pane["status"] or ""),
        ally_pane,
    )
    ally_page.screenshot(path=str(NON_RED_SCREENSHOT), full_page=True)
    ally_context.close()

    return {
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["ok"]),
            "failed": sum(1 for result in results if not result["ok"]),
        },
        "results": results,
        "screenshots": [str(RED_SCREENSHOT), str(NON_RED_SCREENSHOT)],
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
        "# 紅軍「我的陣營」右欄：其他玩家獲勝條件驗證",
        "",
        "可重跑指令：`uv run --with playwright python scripts/validate/validate_red_army_other_players_win_conditions.py`",
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
