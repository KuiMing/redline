import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = "/usr/bin/python3"
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000")
RECORD_DIR = ROOT / "docs" / "records" / "layout-ui" / "discard-log-scroll"
OUT_JSON = RECORD_DIR / "DISCARD_LOG_SCROLL_VALIDATION.json"
SCREENSHOT = RECORD_DIR / "discard_log_scroll_1280x720.png"


def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))


def check_viewport(browser, viewport, capture=False):
    discard_cycle = ["宣傳家", "思想家", "資助者", "資本家", "分神", "內鬥", "東洋奧援", "印度奧援"]
    discard_names = [discard_cycle[index % len(discard_cycle)] for index in range(64)]
    action_log = [f"[Turn {index + 1}] viewer 完成測試事件紀錄 {index + 1}" for index in range(80)]
    setup = post(
        "/test/setup-hand-preview",
        {
            "hand_names": ["宣傳家", "思想家", "資助者", "資本家", "分神"],
            "viewer_discard_names": discard_names,
            "red_discard_names": list(reversed(discard_names)),
            "action_log": action_log,
        },
    )
    if setup.get("error"):
        raise RuntimeError(setup["error"])

    context = browser.new_context(viewport=viewport, device_scale_factor=1)
    page = context.new_page()
    console_errors = []
    page_errors = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    page.goto(BASE_URL + "/", wait_until="networkidle")
    page.evaluate(
        "([gameIdValue, playerIdValue]) => { gameId = gameIdValue; playerId = playerIdValue; connect(); }",
        [setup["game_id"], setup["player_id"]],
    )
    page.get_by_text("戰況紀錄", exact=True).click()
    page.wait_for_selector("#playerStatusOverview .player-status-card", state="visible", timeout=15000)
    page.wait_for_function(
        "document.querySelectorAll('#playerStatusOverview .player-status-discard-card').length >= 128"
    )
    page.wait_for_function("document.querySelectorAll('#logViewContent > div').length >= 80")
    page.evaluate("document.fonts && document.fonts.ready")
    page.wait_for_timeout(250)

    geometry = page.evaluate(
        """() => {
          const panel = document.querySelector('#logViewPanel');
          const overview = document.querySelector('#playerStatusOverview');
          const log = document.querySelector('#logViewContent');
          const title = document.querySelector('.log-section-title');
          const lists = [...document.querySelectorAll('.player-status-discard-list')];
          const rect = el => {
            const r = el.getBoundingClientRect();
            return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height};
          };
          const panelRect = rect(panel);
          const logRect = rect(log);
          const titleRect = rect(title);
          const overviewRect = rect(overview);
          const statusCards = [...document.querySelectorAll('.player-status-card')].map(rect);
          return {
            stageScale: document.querySelector('#designStage').getBoundingClientRect().width / 1280,
            panel: panelRect,
            overview: overviewRect,
            statusCards,
            eventTitle: titleRect,
            log: {...logRect, clientHeight: log.clientHeight, scrollHeight: log.scrollHeight, overflowY: getComputedStyle(log).overflowY},
            discardLists: lists.map(el => ({...rect(el), clientHeight: el.clientHeight, scrollHeight: el.scrollHeight, overflowY: getComputedStyle(el).overflowY})),
            statusCardsInsideOverview: statusCards.every(card => card.top >= overviewRect.top - 1 && card.bottom <= overviewRect.bottom + 1),
            logInsidePanel: logRect.top >= panelRect.top - 1 && logRect.bottom <= panelRect.bottom + 1,
            titleVisibleAboveLog: titleRect.height > 0 && titleRect.bottom <= logRect.top + 1,
          };
        }"""
    )

    first_list = page.locator(".player-status-discard-list").first
    before_discard_scroll = first_list.evaluate("el => el.scrollTop")
    first_list.evaluate("el => { el.scrollTop = el.scrollHeight; }")
    after_discard_scroll = first_list.evaluate("el => el.scrollTop")
    log = page.locator("#logViewContent")
    before_log_scroll = log.evaluate("el => el.scrollTop")
    log.evaluate("el => { el.scrollTop = el.scrollHeight; }")
    after_log_scroll = log.evaluate("el => el.scrollTop")
    log.evaluate("el => { el.scrollTop = 0; }")

    scale = geometry["stageScale"] or 1
    event_log_design_height = geometry["log"]["height"] / scale
    discard_lists_scrollable = all(
        item["scrollHeight"] > item["clientHeight"] + 1 and item["overflowY"] in {"auto", "scroll"}
        for item in geometry["discardLists"]
    )
    event_log_scrollable = (
        geometry["log"]["scrollHeight"] > geometry["log"]["clientHeight"] + 1
        and geometry["log"]["overflowY"] in {"auto", "scroll"}
        and after_log_scroll > before_log_scroll
    )

    results = [
        {
            "name": "discard_piles_are_independently_scrollable",
            "ok": discard_lists_scrollable and after_discard_scroll > before_discard_scroll,
            "detail": {"before": before_discard_scroll, "after": after_discard_scroll, "lists": geometry["discardLists"]},
        },
        {
            "name": "player_status_cards_remain_inside_scroll_region",
            "ok": geometry["statusCardsInsideOverview"],
            "detail": {"overview": geometry["overview"], "status_cards": geometry["statusCards"]},
        },
        {
            "name": "event_log_keeps_usable_height_with_large_discards",
            "ok": event_log_design_height >= 139.5,
            "detail": {"design_height": event_log_design_height, "geometry": geometry},
        },
        {
            "name": "event_log_remains_scrollable",
            "ok": event_log_scrollable,
            "detail": {"before": before_log_scroll, "after": after_log_scroll, "log": geometry["log"]},
        },
        {
            "name": "event_log_and_title_remain_inside_panel",
            "ok": geometry["logInsidePanel"] and geometry["titleVisibleAboveLog"],
            "detail": geometry,
        },
        {
            "name": "browser_console_has_no_errors",
            "ok": not console_errors and not page_errors,
            "detail": {"console_errors": console_errors, "page_errors": page_errors},
        },
    ]

    if capture:
        page.screenshot(path=str(SCREENSHOT))

    context.close()
    return {
        "viewport": viewport,
        "setup": {"game_id": setup["game_id"], "player_id": setup["player_id"]},
        "summary": {
            "total": len(results),
            "passed": sum(1 for item in results if item["ok"]),
            "failed": sum(1 for item in results if not item["ok"]),
        },
        "results": results,
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        runs = [
            check_viewport(browser, {"width": 1280, "height": 720}, capture=True),
            check_viewport(browser, {"width": 1024, "height": 768}),
        ]
        browser.close()

    all_results = [result for run in runs for result in run["results"]]
    payload = {
        "summary": {
            "total": len(all_results),
            "passed": sum(1 for item in all_results if item["ok"]),
            "failed": sum(1 for item in all_results if not item["ok"]),
        },
        "runs": runs,
        "screenshot": str(SCREENSHOT),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
