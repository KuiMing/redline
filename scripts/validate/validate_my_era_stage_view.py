import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "event-cards"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT_JSON = RECORD_DIR / "MY_ERA_STAGE_TAB_VALIDATION.json"
OUT_MD = RECORD_DIR / "MY_ERA_STAGE_TAB_VALIDATION.md"
PENDING_SCREENSHOT = RECORD_DIR / "my_era_stage_tab_pending.png"
ACTIVE_SCREENSHOT = RECORD_DIR / "my_era_stage_tab_active.png"
RED_SCREENSHOT = RECORD_DIR / "my_era_stage_tab_red_army.png"


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode("utf-8"))


def setup_era(era_id, via_lifecycle=False):
    payload = {"era_id": era_id}
    if via_lifecycle:
        payload["via_lifecycle"] = True
    last = None
    for _ in range(3):
        last = post_json("/test/setup-era-notification-proof", payload)
        if last.get("success") and last.get("game_id") and last.get("player_id"):
            return last
    raise RuntimeError(f"era proof setup failed: {last}")


def open_game(browser, setup):
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
      if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
      const factionClose = document.getElementById('closeFactionActionModal');
      if (factionClose) factionClose.click();
    }""")
    page.wait_for_timeout(100)
    return context, page


def inspect_era_tab(page):
    return page.evaluate("""() => {
      const view = document.getElementById('myFactionView');
      const panel = view?.querySelector('.personal-info-panel');
      const viewRect = view?.getBoundingClientRect();
      const panelRect = panel?.getBoundingClientRect();
      return {
        viewActive: view?.classList.contains('active'),
        tabActive: document.getElementById('myFactionBtn')?.classList.contains('active'),
        commandActive: document.getElementById('commandView')?.classList.contains('active'),
        modalExists: !!document.getElementById('myEraStageModal'),
        overlayCount: view?.querySelectorAll('.modal-overlay').length ?? -1,
        title: document.getElementById('myEraStageTitle')?.textContent,
        status: document.getElementById('myEraStageStatus')?.textContent,
        statusClass: document.getElementById('myEraStageStatus')?.className,
        summary: document.getElementById('myEraStageSummary')?.textContent,
        sections: [...document.querySelectorAll('#myEraStageBody .era-achievement-section-title')].map(el => el.textContent),
        texts: [...document.querySelectorAll('#myEraStageBody .modal-body-text')].map(el => el.textContent),
        imageCount: document.querySelectorAll('#myFactionView .era-card-art-image').length,
        artActive: document.getElementById('myEraStageBody')?.classList.contains('era-card-art-active'),
        image: (() => {
          const image = document.querySelector('#myFactionView .era-card-art-image');
          const body = document.getElementById('myEraStageBody');
          if (!image || !body) return null;
          const rect = image.getBoundingClientRect();
          const bodyRect = body.getBoundingClientRect();
          return {
            alt: image.alt,
            width: image.naturalWidth,
            height: image.naturalHeight,
            rect: {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height},
            contained: rect.left >= bodyRect.left && rect.right <= bodyRect.right && rect.top >= bodyRect.top && rect.bottom <= bodyRect.bottom + 1,
          };
        })(),
        fallbackVisible: (() => {
          const fallback = document.querySelector('#myFactionView .era-card-art-fallback');
          return fallback ? getComputedStyle(fallback).display !== 'none' : false;
        })(),
        scrollHeight: document.getElementById('myEraStageBody')?.scrollHeight,
        clientHeight: document.getElementById('myEraStageBody')?.clientHeight,
        panelFits: !!(viewRect && panelRect)
          && panelRect.left >= viewRect.left
          && panelRect.right <= viewRect.right
          && panelRect.top >= viewRect.top
          && panelRect.bottom <= viewRect.bottom,
        stateId: window.lastGameState?.my_era_stage?.id ?? null,
        achieved: window.lastGameState?.my_era_stage?.achieved ?? null,
        active: window.lastGameState?.my_era_stage?.active ?? null,
        remaining: window.lastGameState?.my_era_stage?.remaining ?? null,
      };
    }""")


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    pending_setup = post_json(
        "/test/setup-support-card-play",
        {"support_name": "臺灣奧援", "faction_id": "taiwan_green", "base": "臺北"},
    )
    pending_context, pending_page = open_game(browser, pending_setup)
    faction_button = pending_page.locator("#myFactionBtn")
    record(
        "era_stage_is_merged_into_single_faction_tab",
        faction_button.is_visible()
        and faction_button.get_attribute("data-view") == "myFaction"
        and faction_button.get_attribute("onclick") is None
        and pending_page.locator("#myEraStageBtn").count() == 0
        and pending_page.locator("#myEraStageView").count() == 0
        and pending_page.locator("#myFactionView #myEraStagePane").count() == 1,
        {
            "faction_data_view": faction_button.get_attribute("data-view"),
            "faction_onclick": faction_button.get_attribute("onclick"),
            "era_tab_count": pending_page.locator("#myEraStageBtn").count(),
            "era_view_count": pending_page.locator("#myEraStageView").count(),
            "merged_pane_count": pending_page.locator("#myFactionView #myEraStagePane").count(),
        },
    )

    position = pending_page.evaluate("""() => {
      const rect = selector => document.querySelector(selector)?.getBoundingClientRect();
      const log = rect('#gameTabs [data-view="log"]');
      const faction = rect('#myFactionBtn');
      const eventPanel = document.querySelector('.event-card-panel');
      const oldDisplay = eventPanel?.style.display;
      if (eventPanel) eventPanel.style.display = 'block';
      const event = eventPanel?.getBoundingClientRect();
      if (eventPanel) eventPanel.style.display = oldDisplay;
      return {
        gapAfterLog: faction && log ? faction.left - log.right : null,
        noEventOverlap: !!(faction && event && faction.right < event.left),
      };
    }""")
    record(
        "merged_personal_tab_stays_clear_of_event_panel",
        position["gapAfterLog"] is not None
        and 0 <= position["gapAfterLog"] <= 16
        and position["noEventOverlap"],
        position,
    )

    faction_button.click()
    pending_page.wait_for_function("document.querySelector('#myFactionView .era-card-art-image')?.naturalWidth === 1350")
    pending_page.wait_for_timeout(100)
    pending_data = inspect_era_tab(pending_page)
    record(
        "pending_taiwan_stage_renders_in_main_view_without_modal",
        pending_data["viewActive"]
        and pending_data["tabActive"]
        and not pending_data["commandActive"]
        and not pending_data["modalExists"]
        and pending_data["overlayCount"] == 0
        and pending_data["panelFits"],
        pending_data,
    )
    record(
        "pending_stage_shows_approved_complete_card_art",
        "[臺灣]綏靖派反對介入對岸" in (pending_data["title"] or "")
        and pending_data["status"] == "尚未達成"
        and bool(pending_data["summary"])
        and pending_data["sections"] == ["觸發條件", "紅軍壓制", "革命反撲", "效果期限"]
        and all(pending_data["texts"])
        and pending_data["imageCount"] == 1
        and pending_data["artActive"]
        and pending_data["image"] == {
            "alt": "[臺灣]綏靖派反對介入對岸完整卡面",
            "width": 1350,
            "height": 1100,
            "rect": pending_data["image"]["rect"],
            "contained": True,
        }
        and not pending_data["fallbackVisible"],
        pending_data,
    )
    pending_page.screenshot(path=str(PENDING_SCREENSHOT), full_page=True)

    pending_page.evaluate("document.querySelector('#myFactionView .era-card-art-image').src = '/static/card-art/era/__missing__.png'")
    pending_page.wait_for_function("document.querySelector('#myFactionView .era-card-art-shell')?.classList.contains('era-card-art-load-failed')")
    fallback_data = inspect_era_tab(pending_page)
    record(
        "missing_era_art_falls_back_to_complete_text",
        fallback_data["fallbackVisible"]
        and fallback_data["sections"] == ["觸發條件", "紅軍壓制", "革命反撲", "效果期限"]
        and all(fallback_data["texts"]),
        fallback_data,
    )

    pending_page.click('#gameTabs [data-view="log"]')
    pending_page.wait_for_timeout(100)
    switched = pending_page.evaluate("""() => ({
      factionActive: document.getElementById('myFactionView')?.classList.contains('active'),
      logActive: document.getElementById('logView')?.classList.contains('active'),
    })""")
    record(
        "switching_tabs_leaves_era_view_without_close_action",
        not switched["factionActive"] and switched["logActive"],
        switched,
    )
    pending_context.close()

    active_setup = setup_era("mongolia")
    active_context, active_page = open_game(browser, active_setup)
    active_page.click("#myFactionBtn")
    active_page.wait_for_function("document.querySelector('#myFactionView .era-card-art-image')?.naturalWidth === 1350")
    active_page.wait_for_timeout(100)
    active_data = inspect_era_tab(active_page)
    record(
        "active_mongolia_stage_shows_achieved_status_and_remaining_turns",
        "[蒙古]莫日根事件爆發" in (active_data["title"] or "")
        and active_data["status"] == "條件已達成｜剩餘 1 回合"
        and "active" in (active_data["statusClass"] or "")
        and active_data["stateId"] == "mongolia"
        and active_data["achieved"] is True
        and active_data["active"] is True
        and active_data["remaining"] == 1
        and active_data["imageCount"] == 1
        and active_data["image"]["width"] == 1350
        and active_data["image"]["height"] == 1100
        and active_data["image"]["contained"],
        active_data,
    )
    active_page.screenshot(path=str(ACTIVE_SCREENSHOT), full_page=True)
    active_context.close()

    lifecycle_setup = setup_era("taiwan", via_lifecycle=True)
    lifecycle_context, lifecycle_page = open_game(browser, lifecycle_setup)
    lifecycle_page.click("#myFactionBtn")
    lifecycle_page.wait_for_function("document.querySelector('#myFactionView .era-card-art-image')?.naturalWidth === 1350")
    lifecycle_page.wait_for_timeout(100)
    lifecycle_data = inspect_era_tab(lifecycle_page)
    record(
        "taiwan_stage_triggered_through_turn_lifecycle_is_projected_to_tab",
        lifecycle_setup.get("via_lifecycle") is True
        and len(lifecycle_setup.get("viewer_organizations") or {}) == 7
        and lifecycle_data["stateId"] == "taiwan"
        and lifecycle_data["achieved"] is True
        and lifecycle_data["active"] is True
        and lifecycle_data["remaining"] == 2
        and lifecycle_data["status"] == "條件已達成｜剩餘 2 回合",
        {**lifecycle_data, "organizations": lifecycle_setup.get("viewer_organizations")},
    )
    lifecycle_context.close()

    # 2026-09-06：紅軍沒有個人時代關卡，右欄改列出其他玩家的陣營與獲勝條件
    # （見 scripts/validate/validate_red_army_other_players_win_conditions.py 的完整覆蓋）。
    # 這裡仍指定一個非紅軍對手，確保這個合併頁籤本身有正確顯示該對手的獲勝條件。
    red_setup = post_json(
        "/test/setup-support-card-play",
        {
            "support_name": "紅軍奧援",
            "faction_id": "red_army",
            "base": "北京",
            "enemy_faction_id": "taiwan_green",
            "enemy_base": "臺北",
        },
    )
    red_context, red_page = open_game(browser, red_setup)
    red_page.click("#myFactionBtn")
    red_page.wait_for_timeout(100)
    red_data = inspect_era_tab(red_page)
    projected = red_page.evaluate("() => window.lastGameState?.my_era_stage ?? null")
    other_players_panel = red_page.evaluate("""() => ({
      panelLabel: document.getElementById('myEraStagePanelLabel')?.textContent,
      title: document.getElementById('myEraStageTitle')?.textContent,
      status: document.getElementById('myEraStageStatus')?.textContent,
      sections: [...document.querySelectorAll('#myEraStageBody .era-achievement-section-title')].map(el => el.textContent),
      wins: [...document.querySelectorAll('#myEraStageBody .my-era-stage-other-wins')].map(
        ul => [...ul.querySelectorAll('li')].map(li => li.textContent)
      ),
    })""")
    record(
        "red_army_tab_lists_other_player_faction_and_win_condition_instead_of_era_stage",
        projected is None
        and red_data["viewActive"]
        and other_players_panel["panelLabel"] == "其他玩家獲勝條件"
        and other_players_panel["title"] == "全桌獲勝條件一覽"
        and other_players_panel["status"] == "共 1 位其他玩家"
        and len(other_players_panel["sections"]) == 1
        and "臺灣" in other_players_panel["sections"][0]
        and len(other_players_panel["wins"]) == 1
        and other_players_panel["wins"][0]
        and "14" in other_players_panel["wins"][0][0],
        {**red_data, "projected": projected, "other_players_panel": other_players_panel},
    )
    red_page.screenshot(path=str(RED_SCREENSHOT), full_page=True)
    red_context.close()

    return {
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["ok"]),
            "failed": sum(1 for result in results if not result["ok"]),
        },
        "results": results,
        "screenshots": [str(PENDING_SCREENSHOT), str(ACTIVE_SCREENSHOT), str(RED_SCREENSHOT)],
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
        "# 「我的陣營」合併時代關卡驗證",
        "",
        "可重跑指令：`uv run --with playwright python scripts/validate/validate_my_era_stage_view.py`",
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
