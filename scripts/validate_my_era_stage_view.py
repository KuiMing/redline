import json
import os
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / "docs" / "records" / "event-cards"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUT_JSON = RECORD_DIR / "MY_ERA_STAGE_VIEW_VALIDATION.json"
OUT_MD = RECORD_DIR / "MY_ERA_STAGE_VIEW_VALIDATION.md"
PENDING_SCREENSHOT = RECORD_DIR / "my_era_stage_pending.png"
ACTIVE_SCREENSHOT = RECORD_DIR / "my_era_stage_active.png"
TAIWAN_LIFECYCLE_SCREENSHOT = RECORD_DIR / "taiwan_era_stage_lifecycle_active.png"
POSITION_SCREENSHOT = RECORD_DIR / "my_era_stage_entry_position.png"
ACHIEVEMENT_SCREENSHOT = RECORD_DIR / "era_stage_achievement_art.png"


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(request, timeout=20).read().decode("utf-8"))


def open_game(browser, setup):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(
        f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
        wait_until="networkidle",
    )
    page.wait_for_selector("#gameShell", state="visible", timeout=10000)
    page.wait_for_timeout(900)
    page.evaluate("""() => {
      const factionClose = document.getElementById('closeFactionActionModal');
      if (factionClose) factionClose.click();
      if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
      if (typeof closeEventReveal === 'function') closeEventReveal();
    }""")
    page.wait_for_timeout(200)
    return context, page


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({"name": name, "ok": bool(ok), "detail": detail or {}})

    era_art_files = sorted((ROOT / "static/card-art/era").glob("*.png"))
    record(
        "all_eight_era_art_assets_are_installed",
        len(era_art_files) == 8,
        {"files": [path.name for path in era_art_files]},
    )

    pending_setup = post_json(
        "/test/setup-support-card-play",
        {"support_name": "臺灣奧援", "faction_id": "taiwan_green", "base": "臺北"},
    )
    pending_context, pending_page = open_game(browser, pending_setup)

    button = pending_page.locator("#myEraStageBtn")
    record(
        "my_era_stage_button_visible_in_game_tabs",
        button.is_visible() and button.inner_text() == "我的時代關卡",
        {"visible": button.is_visible(), "text": button.inner_text()},
    )
    position_data = pending_page.evaluate("""() => {
      const rect = selector => document.querySelector(selector)?.getBoundingClientRect();
      const log = rect('#gameTabs [data-view="log"]');
      const faction = rect('#myFactionBtn');
      const era = rect('#myEraStageBtn');
      const eventPanel = document.querySelector('.event-card-panel');
      const previousEventDisplay = eventPanel?.style.display;
      if (eventPanel) eventPanel.style.display = 'block';
      const event = eventPanel?.getBoundingClientRect();
      if (eventPanel) eventPanel.style.display = previousEventDisplay;
      return {
        logRight: log?.right,
        factionLeft: faction?.left,
        factionRight: faction?.right,
        eraLeft: era?.left,
        eraRight: era?.right,
        eventLeft: event?.left,
        gapAfterLog: faction && log ? faction.left - log.right : null,
        gapBetweenPersonalTabs: era && faction ? era.left - faction.right : null,
        noEventOverlap: !!(era && event && era.right < event.left),
      };
    }""")
    record(
        "personal_info_tabs_sit_next_to_log_without_event_card_overlap",
        position_data["gapAfterLog"] is not None
        and 0 <= position_data["gapAfterLog"] <= 16
        and position_data["gapBetweenPersonalTabs"] is not None
        and 0 <= position_data["gapBetweenPersonalTabs"] <= 16
        and position_data["noEventOverlap"],
        position_data,
    )
    pending_page.screenshot(path=str(POSITION_SCREENSHOT), full_page=True)
    faction_button = pending_page.locator("#myFactionBtn")
    faction_button.click()
    pending_page.wait_for_timeout(150)
    faction_modal_visible = pending_page.locator("#myFactionModal").evaluate("el => el.style.display") == "flex"
    pending_page.click("#closeMyFactionModal")
    record(
        "adjacent_my_faction_entry_still_works",
        faction_button.is_visible() and faction_modal_visible,
        {"button_visible": faction_button.is_visible(), "modal_visible": faction_modal_visible},
    )
    button.click()
    pending_page.wait_for_timeout(200)
    pending_page.wait_for_function("document.querySelector('#myEraStageModal .era-card-art-image')?.naturalWidth === 1350")
    pending_data = pending_page.evaluate("""() => ({
      modalVisible: document.getElementById('myEraStageModal')?.style.display === 'flex',
      title: document.getElementById('myEraStageTitle')?.textContent,
      status: document.getElementById('myEraStageStatus')?.textContent,
      summary: document.getElementById('myEraStageSummary')?.textContent,
      sections: [...document.querySelectorAll('#myEraStageBody .era-achievement-section-title')].map(el => el.textContent),
      texts: [...document.querySelectorAll('#myEraStageBody .modal-body-text')].map(el => el.textContent),
      imageCount: document.querySelectorAll('#myEraStageModal img').length,
      image: (() => {
        const image = document.querySelector('#myEraStageModal .era-card-art-image');
        return image ? {alt: image.alt, width: image.naturalWidth, height: image.naturalHeight} : null;
      })(),
    })""")
    record(
        "pending_taiwan_stage_shows_complete_art_card",
        pending_data["modalVisible"]
        and "[臺灣]綏靖派反對介入對岸" in (pending_data["title"] or "")
        and pending_data["status"] == "尚未達成"
        and bool(pending_data["summary"])
        and pending_data["sections"] == ["觸發條件", "紅軍壓制", "革命反撲", "效果期限"]
        and all(pending_data["texts"])
        and pending_data["imageCount"] == 1
        and pending_data["image"] == {"alt": "[臺灣]綏靖派反對介入對岸完整卡面", "width": 1350, "height": 1100},
        pending_data,
    )
    pending_page.screenshot(path=str(PENDING_SCREENSHOT), full_page=True)
    pending_page.click("#closeMyEraStageModal")
    record(
        "close_button_hides_my_era_stage_modal",
        pending_page.locator("#myEraStageModal").evaluate("el => el.style.display") == "none",
        {"display": pending_page.locator("#myEraStageModal").evaluate("el => el.style.display")},
    )
    pending_context.close()

    taiwan_setup = post_json(
        "/test/setup-era-notification-proof",
        {"era_id": "taiwan", "via_lifecycle": True},
    )
    taiwan_context, taiwan_page = open_game(browser, taiwan_setup)
    taiwan_page.click("#myEraStageBtn")
    taiwan_page.wait_for_timeout(200)
    taiwan_page.wait_for_function("document.querySelector('#myEraStageModal .era-card-art-image')?.naturalWidth === 1350")
    taiwan_data = taiwan_page.evaluate("""() => ({
      title: document.getElementById('myEraStageTitle')?.textContent,
      status: document.getElementById('myEraStageStatus')?.textContent,
      activeClass: document.getElementById('myEraStageStatus')?.classList.contains('active'),
      stateId: window.lastGameState?.my_era_stage?.id,
      achieved: window.lastGameState?.my_era_stage?.achieved,
      active: window.lastGameState?.my_era_stage?.active,
      remaining: window.lastGameState?.my_era_stage?.remaining,
    })""")
    record(
        "taiwan_seven_distinct_organizations_trigger_stage_through_turn_lifecycle",
        taiwan_setup.get("via_lifecycle") is True
        and len(taiwan_setup.get("viewer_organizations") or {}) == 7
        and "[臺灣]綏靖派反對介入對岸" in (taiwan_data["title"] or "")
        and taiwan_data["status"] == "條件已達成｜剩餘 2 回合"
        and taiwan_data["activeClass"]
        and taiwan_data["stateId"] == "taiwan"
        and taiwan_data["achieved"] is True
        and taiwan_data["active"] is True
        and taiwan_data["remaining"] == 2,
        {**taiwan_data, "organizations": taiwan_setup.get("viewer_organizations")},
    )
    taiwan_page.screenshot(path=str(TAIWAN_LIFECYCLE_SCREENSHOT), full_page=True)
    taiwan_context.close()

    active_setup = post_json("/test/setup-era-notification-proof", {"era_id": "mongolia"})
    active_context, active_page = open_game(browser, active_setup)
    active_page.click("#myEraStageBtn")
    active_page.wait_for_timeout(200)
    active_page.wait_for_function("document.querySelector('#myEraStageModal .era-card-art-image')?.naturalWidth === 1350")
    active_data = active_page.evaluate("""() => ({
      title: document.getElementById('myEraStageTitle')?.textContent,
      status: document.getElementById('myEraStageStatus')?.textContent,
      activeClass: document.getElementById('myEraStageStatus')?.classList.contains('active'),
      stateId: window.lastGameState?.my_era_stage?.id,
      stateActive: window.lastGameState?.my_era_stage?.active,
      remaining: window.lastGameState?.my_era_stage?.remaining,
      image: (() => {
        const image = document.querySelector('#myEraStageModal .era-card-art-image');
        return image ? {alt: image.alt, width: image.naturalWidth, height: image.naturalHeight} : null;
      })(),
    })""")
    record(
        "active_mongolia_stage_shows_achieved_status_and_remaining_turns",
        "[蒙古]莫日根事件爆發" in (active_data["title"] or "")
        and active_data["status"] == "條件已達成｜剩餘 1 回合"
        and active_data["activeClass"]
        and active_data["stateId"] == "mongolia"
        and active_data["stateActive"] is True
        and active_data["remaining"] == 1
        and active_data["image"] == {"alt": "[蒙古]莫日根事件爆發完整卡面", "width": 1350, "height": 1100},
        active_data,
    )
    active_page.screenshot(path=str(ACTIVE_SCREENSHOT), full_page=True)
    active_page.click("#closeMyEraStageModal")
    active_page.evaluate("lastEraNotificationKey = null; renderEraAchievement(window.lastGameState)")
    active_page.locator("#eraAchievementModal").wait_for(state="visible")
    active_page.wait_for_function("document.querySelector('#eraAchievementArt img')?.naturalWidth === 1350")
    achievement_data = active_page.evaluate("""() => {
      const image = document.querySelector('#eraAchievementArt .era-card-art-image');
      return {
        activeClass: document.querySelector('.era-achievement-glass')?.classList.contains('era-card-art-active'),
        image: image ? {alt: image.alt, width: image.naturalWidth, height: image.naturalHeight} : null,
        minimizeVisible: document.getElementById('eraAchievementMinimizeBtn')?.offsetParent !== null,
      };
    }""")
    record(
        "achieved_era_notification_shows_complete_art_card",
        achievement_data["activeClass"]
        and achievement_data["image"] == {"alt": "[蒙古]莫日根事件爆發完整卡面", "width": 1350, "height": 1100}
        and achievement_data["minimizeVisible"],
        achievement_data,
    )
    active_page.screenshot(path=str(ACHIEVEMENT_SCREENSHOT), full_page=True)
    active_context.close()

    red_setup = post_json(
        "/test/setup-support-card-play",
        {"support_name": "紅軍奧援", "faction_id": "red_army", "base": "北京"},
    )
    red_context, red_page = open_game(browser, red_setup)
    red_page.click("#myEraStageBtn")
    red_data = red_page.evaluate("""() => ({
      title: document.getElementById('myEraStageTitle')?.textContent,
      status: document.getElementById('myEraStageStatus')?.textContent,
      summary: document.getElementById('myEraStageSummary')?.textContent,
      projected: window.lastGameState?.my_era_stage ?? null,
    })""")
    record(
        "red_army_gets_clear_no_personal_stage_message",
        red_data["projected"] is None
        and red_data["title"] == "無個人時代關卡"
        and red_data["status"] == "此陣營沒有專屬時代關卡"
        and "紅軍沒有個人時代關卡" in (red_data["summary"] or ""),
        red_data,
    )
    red_context.close()

    return {
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["ok"]),
            "failed": sum(1 for result in results if not result["ok"]),
        },
        "results": results,
        "screenshots": [
            str(POSITION_SCREENSHOT),
            str(PENDING_SCREENSHOT),
            str(TAIWAN_LIFECYCLE_SCREENSHOT),
            str(ACTIVE_SCREENSHOT),
            str(ACHIEVEMENT_SCREENSHOT),
        ],
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
        "# 「我的時代關卡」遊戲內查看入口驗證",
        "",
        "可重跑指令：`uv run --with playwright python scripts/validate_my_era_stage_view.py`",
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
