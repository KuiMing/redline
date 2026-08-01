#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RECORD_DIR = ROOT / "docs/records/game-area-width"
OUT_JSON = RECORD_DIR / "GAME_AREA_WIDTH_BROWSER_VALIDATION.json"
OUT_MD = RECORD_DIR / "GAME_AREA_WIDTH_BROWSER_VALIDATION.md"
VIEWPORTS = [(1280, 720), (1024, 768)]
HAND_NAMES = ["交通經驗甲", "領導", "英美奧援", "宣傳家", "資助者"]


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def chromium_launch_options() -> dict:
    options: dict = {"headless": True}
    cache_root = Path.home() / "Library/Caches/ms-playwright"
    candidates = sorted(
        cache_root.glob("chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"),
        reverse=True,
    )
    if candidates:
        options["executable_path"] = str(candidates[0])
    return options


def geometry(page) -> dict:
    return page.evaluate(
        """() => {
          const ids = ['controlPanel', 'randomMarketPanel', 'handPanel'];
          const rect = el => {
            const r = el.getBoundingClientRect();
            return {left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:r.width, height:r.height};
          };
          const zoneData = (zoneId, cardSelector) => {
            const zone = document.getElementById(zoneId);
            const panel = zone.closest('.panel');
            const cards = [...zone.querySelectorAll(cardSelector)];
            const zoneRect = rect(zone);
            const panelRect = rect(panel);
            const cardRows = cards.map(card => {
              const cardRect = rect(card);
              const buttons = [...card.querySelectorAll('button')].map(button => ({
                text: button.textContent.trim(),
                ...rect(button),
              }));
              return {name: card.dataset.cardName || card.innerText.slice(0, 24), ...cardRect, buttons};
            });
            const epsilon = 1.5;
            return {
              id: zoneId,
              clientWidth: zone.clientWidth,
              scrollWidth: zone.scrollWidth,
              hasHorizontalOverflow: zone.scrollWidth > zone.clientWidth + 1,
              zoneRect,
              panelRect,
              cardCount: cards.length,
              cards: cardRows,
              cardsInsidePanel: cardRows.every(card => card.left >= panelRect.left - epsilon && card.right <= panelRect.right + epsilon),
              controlsInsideCards: cardRows.every(card => card.buttons.every(button => button.left >= card.left - epsilon && button.right <= card.right + epsilon)),
            };
          };
          return {
            viewport: {width: innerWidth, height: innerHeight},
            stageScale: getComputedStyle(document.documentElement).getPropertyValue('--stage-scale').trim(),
            commandGrid: rect(document.getElementById('commandGrid')),
            panels: Object.fromEntries(ids.map(id => [id, rect(document.getElementById(id))])),
            staticZone: zoneData('purchaseStatic', '.card'),
            randomZone: zoneData('purchaseRandom', '.card'),
            handZone: zoneData('hand', '.hand-card'),
            documentHorizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1 || document.body.scrollWidth > innerWidth + 1,
            purchaseControls: (() => {
              const controls = document.getElementById('purchaseSelectionControls');
              return {display:getComputedStyle(controls).display, rect:rect(controls)};
            })(),
          };
        }"""
    )


def main() -> int:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    console_errors: list[dict] = []
    screenshots: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_options())
        for width, height in VIEWPORTS:
            setup = post_json(
                "/test/setup-hand-preview",
                {"hand_names": HAND_NAMES, "faction_id": "taiwan_green", "base": "臺北"},
            )
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            errors: list[str] = []
            page.on("console", lambda message, sink=errors: sink.append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error, sink=errors: sink.append(str(error)))
            page.goto(
                f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
                wait_until="domcontentloaded",
            )
            page.wait_for_function(
                "window.lastGameState && document.querySelectorAll('#hand .hand-card').length === 5 && document.querySelectorAll('#purchaseRandom .card').length >= 2",
                timeout=15000,
            )
            page.wait_for_function(
                """() => {
                  const cards = [...document.querySelectorAll('#purchaseStatic .card, #purchaseRandom .card, #hand .hand-card')];
                  const images = cards.map(card => card.querySelector('.playable-card-art-image'));
                  return cards.length > 0 && images.length === cards.length && images.every(image => image?.complete && image.naturalWidth > 0);
                }""",
                timeout=15000,
            )
            page.evaluate("""() => {
              if (typeof closeEventReveal === 'function') closeEventReveal();
              if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
              if (typeof closeFactionActionModal === 'function') closeFactionActionModal();
            }""")
            page.locator(".game-tab[data-view='command']").click()
            page.locator("#commandView").wait_for(state="visible", timeout=5000)
            page.wait_for_function(
                """() => {
                  const cards = [...document.querySelectorAll('#purchaseStatic .card, #purchaseRandom .card, #hand .hand-card')];
                  const images = cards.map(card => card.querySelector('.playable-card-art-image'));
                  return cards.length > 0 && images.length === cards.length && images.every(image => image?.complete && image.naturalWidth > 0);
                }""",
                timeout=15000,
            )
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
            data = geometry(page)
            panels = data["panels"]
            scale = float(data["stageScale"] or "1")
            expected_static = 284 * scale
            expected_wide = 474 * scale
            zones = [data["staticZone"], data["randomZone"], data["handZone"]]
            checks = {
                "static_panel_is_narrower_than_wide_panels": panels["controlPanel"]["width"] < panels["randomMarketPanel"]["width"] and panels["controlPanel"]["width"] < panels["handPanel"]["width"],
                "columns_match_target_distribution": abs(panels["controlPanel"]["width"] - expected_static) <= 1.5 and abs(panels["randomMarketPanel"]["width"] - expected_wide) <= 1.5 and abs(panels["handPanel"]["width"] - expected_wide) <= 1.5,
                "all_cards_inside_panel_bounds": all(zone["cardsInsidePanel"] for zone in zones),
                "no_zone_horizontal_overflow": all(not zone["hasHorizontalOverflow"] for zone in zones),
                "hand_controls_inside_cards": data["handZone"]["controlsInsideCards"],
                "no_document_horizontal_overflow": not data["documentHorizontalOverflow"],
                "command_grid_inside_viewport": data["commandGrid"]["left"] >= -1.5 and data["commandGrid"]["right"] <= width + 1.5,
                "all_panels_inside_viewport": all(panel["left"] >= -1.5 and panel["right"] <= width + 1.5 for panel in panels.values()),
                "expected_card_inventory_visible": data["handZone"]["cardCount"] == 5 and data["randomZone"]["cardCount"] >= 2 and data["staticZone"]["cardCount"] >= 1,
                "browser_console_has_no_errors": not errors,
            }
            shot = RECORD_DIR / f"game-area-width-{width}x{height}.png"
            page.screenshot(path=str(shot), full_page=True)
            screenshots.append(str(shot.relative_to(ROOT)))
            results.append({
                "viewport": f"{width}x{height}",
                "passed": all(checks.values()),
                "checks": checks,
                "geometry": data,
            })
            if errors:
                console_errors.append({"viewport": f"{width}x{height}", "errors": errors})
            context.close()
        browser.close()

    passed = sum(sum(1 for value in result["checks"].values() if value) for result in results)
    total = sum(len(result["checks"]) for result in results)
    report = {
        "status": "passed" if passed == total else "failed",
        "generated_at": datetime.now().astimezone().isoformat(),
        "base_url": BASE_URL,
        "checks_passed": passed,
        "checks_total": total,
        "results": results,
        "console_errors": console_errors,
        "screenshots": screenshots,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 遊戲區域寬度 Browser Validation",
        "",
        f"- 結果：**{passed}/{total} passed**",
        f"- 正式端點：`{BASE_URL}`",
        "- 目標欄寬：常設 284px／隨機 474px／手牌 474px（依舞台縮放同比例）。",
        "",
    ]
    for result in results:
        lines.append(f"## {result['viewport']}")
        lines.append("")
        for name, ok in result["checks"].items():
            lines.append(f"- {'PASS' if ok else 'FAIL'} `{name}`")
        lines.append("")
        panels = result["geometry"]["panels"]
        lines.append(
            f"- panel widths：`{panels['controlPanel']['width']:.2f}` / `{panels['randomMarketPanel']['width']:.2f}` / `{panels['handPanel']['width']:.2f}`"
        )
        for key in ("staticZone", "randomZone", "handZone"):
            zone = result["geometry"][key]
            lines.append(f"- `{zone['id']}` client/scroll：`{zone['clientWidth']}/{zone['scrollWidth']}`")
        lines.append("")
    lines.append("## Screenshots")
    lines.append("")
    lines.extend(f"- `{path}`" for path in screenshots)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks_passed": passed, "checks_total": total}, ensure_ascii=False))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
