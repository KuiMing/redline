#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import struct
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
BASE_URL = os.environ.get("REDLINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
RECORD_DIR = ROOT / "docs/records/card-art"
OUT_JSON = RECORD_DIR / "PLAYABLE_CARD_ART_BROWSER_VALIDATION.json"
OUT_MD = RECORD_DIR / "PLAYABLE_CARD_ART_BROWSER_VALIDATION.md"
HAND_SHOT = RECORD_DIR / "playable_card_art_hand.png"
PREVIEW_SHOT = RECORD_DIR / "playable_card_art_preview.png"
SUPPORT_SHOT = RECORD_DIR / "playable_card_art_support_variant.png"


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        signature = handle.read(24)
    if signature[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not PNG: {path}")
    return struct.unpack(">II", signature[16:24])


def open_game(browser, setup: dict):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto(
        f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
        wait_until="networkidle",
    )
    page.wait_for_selector("#gameShell", state="visible", timeout=10000)
    page.evaluate("""() => {
      document.getElementById('closeFactionActionModal')?.click();
      if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
      if (typeof closeEventReveal === 'function') closeEventReveal();
    }""")
    return context, page, console_errors


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    def record(name: str, passed: bool, details) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    action_files = sorted((ROOT / "static/card-art/actions").glob("*.png"))
    support_files = sorted((ROOT / "static/card-art/support").glob("*.png"))
    action_sizes = {path.name: png_size(path) for path in action_files}
    support_sizes = {path.name: png_size(path) for path in support_files}
    record(
        "all_action_and_support_art_assets_installed",
        len(action_files) == 46
        and len(support_files) == 17
        and set(action_sizes.values()) == {(1100, 1350)}
        and set(support_sizes.values()) == {(1100, 1350)},
        {"action_count": len(action_files), "support_count": len(support_files), "action_sizes": sorted(set(action_sizes.values())), "support_sizes": sorted(set(support_sizes.values()))},
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        setup = post_json(
            "/test/setup-hand-preview",
            {"hand_names": ["交通經驗甲", "領導", "英美奧援"], "faction_id": "taiwan_green", "base": "臺北"},
        )
        context, page, console_errors = open_game(browser, setup)
        page.wait_for_function("[...document.querySelectorAll('#hand .playable-card-art-image')].length === 3 && [...document.querySelectorAll('#hand .playable-card-art-image')].every(img => img.naturalWidth === 1100 && img.naturalHeight === 1350)")
        hand_data = page.evaluate("""() => [...document.querySelectorAll('#hand .hand-card')].map(card => {
          const image = card.querySelector('.playable-card-art-image');
          const face = card.querySelector('.card-art-face');
          const rect = face?.getBoundingClientRect();
          return {
            name: card.dataset.cardName,
            srcFile: image ? decodeURIComponent(new URL(image.src).pathname.split('/').pop()) : '',
            srcQuery: image ? new URL(image.src).search : '',
            alt: image?.alt || '',
            natural: image ? [image.naturalWidth, image.naturalHeight] : null,
            faceRect: rect ? {width: rect.width, height: rect.height} : null,
            buttons: [...card.querySelectorAll('.hand-card-action-btn')].map(btn => btn.textContent.trim()),
          };
        })""")
        expected_files = {"交通經驗甲": "交通經驗甲.png", "領導": "領導.png", "英美奧援": "01_英美奧援_歐洲-天方.png"}
        hand_ok = len(hand_data) == 3
        for item in hand_data:
            hand_ok = hand_ok and item["srcFile"] == expected_files[item["name"]]
            hand_ok = hand_ok and (item["srcQuery"] == "?v=head-safe-20260726" if item["name"] != "英美奧援" else item["srcQuery"] == "")
            hand_ok = hand_ok and item["natural"] == [1100, 1350]
            hand_ok = hand_ok and item["alt"] == f"{item['name']}完整卡面"
            hand_ok = hand_ok and abs((item["faceRect"]["width"] / item["faceRect"]["height"]) - (22 / 27)) < 0.02
        hand_ok = hand_ok and hand_data[0]["buttons"] == ["資源", "行動"] and hand_data[2]["buttons"] == ["棄置", "行動"]
        record("hand_cards_use_complete_action_and_support_faces", hand_ok, hand_data)
        purchase_data = page.evaluate("""() => {
          const cards = [...document.querySelectorAll('#purchaseStatic .card, #purchaseRandom .card')];
          const images = cards.map(card => card.querySelector('.playable-card-art-image'));
          return {
            expected: window.lastGameState?.purchase_area?.length || 0,
            cards: cards.length,
            images: images.length,
            loaded: images.filter(image => image?.naturalWidth === 1100 && image?.naturalHeight === 1350).length,
            failed: cards.filter(card => card.querySelector('.playable-card-art-load-failed')).length,
            staticCards: document.querySelectorAll('#purchaseStatic .card').length,
            staticCountBadges: document.querySelectorAll('#purchaseStatic .card > .card-art-face > .card-count').length,
            randomCountBadges: document.querySelectorAll('#purchaseRandom .card > .card-art-face > .card-count').length,
          };
        }""")
        record(
            "static_and_random_purchase_areas_use_complete_faces",
            purchase_data["cards"] == purchase_data["expected"]
            and purchase_data["images"] == purchase_data["expected"]
            and purchase_data["loaded"] == purchase_data["expected"]
            and purchase_data["failed"] == 0
            and purchase_data["staticCountBadges"] == purchase_data["staticCards"]
            and purchase_data["randomCountBadges"] == 0,
            purchase_data,
        )
        page.screenshot(path=str(HAND_SHOT), full_page=True)

        page.locator("#hand .hand-card[data-card-name='交通經驗甲']").click(position={"x": 100, "y": 100})
        page.locator("#cardPreviewModal").wait_for(state="visible")
        page.wait_for_function("document.querySelector('#cardPreviewContent .playable-card-art-image')?.naturalWidth === 1100")
        preview_data = page.evaluate("""() => {
          const content = document.getElementById('cardPreviewContent');
          const image = content.querySelector('.playable-card-art-image');
          const rect = content.getBoundingClientRect();
          return {
            srcFile: decodeURIComponent(new URL(image.src).pathname.split('/').pop()),
            natural: [image.naturalWidth, image.naturalHeight],
            rect: {width: rect.width, height: rect.height},
            ratioDelta: Math.abs((rect.width / rect.height) - (22 / 27)),
            countBadge: !!content.querySelector('.card-art-face > .card-count'),
          };
        }""")
        record(
            "clicking_card_opens_correct_aspect_ratio_art_preview",
            preview_data["srcFile"] == "交通經驗甲.png"
            and preview_data["natural"] == [1100, 1350]
            and preview_data["ratioDelta"] < 0.002
            and not preview_data["countBadge"],
            preview_data,
        )
        page.screenshot(path=str(PREVIEW_SHOT), full_page=True)
        page.keyboard.press("Escape")
        record("main_art_browser_console_has_no_errors", not console_errors, console_errors)
        context.close()

        variant_setup = post_json(
            "/test/setup-support-card-play",
            {"support_name": "英美奧援", "variant_index": 1, "orgs": {"東京": 1}},
        )
        support_context, support_page, support_errors = open_game(browser, variant_setup)
        support_page.wait_for_function("document.querySelector('#hand .playable-card-art-image')?.naturalWidth === 1100")
        support_data = support_page.evaluate("""() => {
          const card = document.querySelector('#hand .hand-card');
          const image = card?.querySelector('.playable-card-art-image');
          return {
            variantIndex: card?.dataset.cardVariantIndex || '',
            srcFile: image ? decodeURIComponent(new URL(image.src).pathname.split('/').pop()) : '',
            alt: image?.alt || '',
          };
        }""")
        record(
            "support_variant_one_uses_its_own_printed_face",
            support_data == {"variantIndex": "1", "srcFile": "02_英美奧援_東洋-臺灣.png", "alt": "英美奧援完整卡面"},
            support_data,
        )
        support_page.screenshot(path=str(SUPPORT_SHOT), full_page=True)
        record("support_art_browser_console_has_no_errors", not support_errors, support_errors)
        support_context.close()
        browser.close()

    summary = {
        "total": len(checks),
        "passed": sum(1 for item in checks if item["passed"]),
        "failed": sum(1 for item in checks if not item["passed"]),
    }
    report = {
        "summary": summary,
        "base_url": BASE_URL,
        "checks": checks,
        "screenshots": [str(path.relative_to(ROOT)) for path in (HAND_SHOT, PREVIEW_SHOT, SUPPORT_SHOT)],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 行動卡與奧援卡完整卡面瀏覽器驗證",
        "",
        "可重跑：`uv run --with playwright python scripts/validate/validate_playable_card_art_browser.py`",
        "",
        f"- total: {summary['total']} / passed: {summary['passed']} / failed: {summary['failed']}",
        "",
    ]
    for item in checks:
        lines.append(f"- {'✅' if item['passed'] else '❌'} `{item['name']}` — {json.dumps(item['details'], ensure_ascii=False)}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
