#!/usr/bin/env python3
"""Formal browser proof for the eleven full-screen AI victory backgrounds and viewer-scoped Red Army endings."""

from __future__ import annotations

import json
import struct
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"
RECORD_DIR = ROOT / "docs" / "records" / "playtest-flow" / "victory-ai-art"
OUT_JSON = RECORD_DIR / "VICTORY_AI_ART_VALIDATION.json"
OUT_MD = RECORD_DIR / "VICTORY_AI_ART_VALIDATION.md"
CONTACT_SHEET = RECORD_DIR / "victory_ai_art_contact_sheet.png"

SCENES = {
    "red_army": "red_army",
    "taiwan_green": "taiwan_green",
    "taiwan_blue": "taiwan_blue",
    "hong_kong": "hong_kong",
    "uyghur": "uyghur_family",
    "tibet": "tibet_family",
    "manchuria": "manchuria",
    "mongol": "mongol",
    "kazakh": "kazakh",
    "rebel": "dian",
}
ART_KEYS = [*SCENES, "red_army_triumph"]


def post_json(path: str, payload: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Invalid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def main() -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []

    def record(name: str, ok: bool, detail: dict[str, object]) -> None:
        results.append({"name": name, "ok": bool(ok), "detail": detail})

    for scene_key in ART_KEYS:
        path = ROOT / "static" / "victory-art" / f"{scene_key}.png"
        exists = path.exists()
        width, height = png_dimensions(path) if exists else (0, 0)
        record(
            f"asset_{scene_key}_is_landscape_png",
            exists and width >= 1600 and height >= 900 and width > height,
            {"path": str(path), "width": width, "height": height},
        )

    setup = post_json("/test/setup-victory-proof", {"winner_name": "GREEN", "co_winners": []})
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(
            f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}",
            wait_until="networkidle",
        )
        page.wait_for_function("() => Boolean(window.lastGameState)")

        for scene_key, faction_id in SCENES.items():
            expected_scene_key = "red_army_triumph" if scene_key == "red_army" else scene_key
            page.evaluate(
                """({ factionId }) => {
                    victoryModalDismissedFor = null;
                    const state = structuredClone(window.lastGameState);
                    const winnerPlayer = state.players.find(player => player.name === 'GREEN') || state.players[0];
                    winnerPlayer.faction = factionId;
                    state.winner = winnerPlayer.name;
                    state.co_winners = [];
                    renderVictoryModal(state);
                }""",
                {"factionId": faction_id},
            )
            page.wait_for_function(
                "() => { const image = document.getElementById('victoryEndingArt'); return image?.complete && image.naturalWidth > 0; }"
            )
            page.wait_for_timeout(100)
            measurement = page.evaluate(
                """({ sceneKey }) => {
                    const overlay = document.getElementById('victoryModal');
                    const scene = document.getElementById('victoryEndingScene');
                    const image = document.getElementById('victoryEndingArt');
                    const glass = document.querySelector('.victory-glass');
                    const overlayRect = overlay.getBoundingClientRect();
                    const sceneRect = scene.getBoundingClientRect();
                    const imageRect = image.getBoundingClientRect();
                    const glassRect = glass.getBoundingClientRect();
                    return {
                        overlayDisplay: overlay.style.display,
                        sceneClass: scene.className,
                        imageSrc: image.currentSrc,
                        imageNaturalWidth: image.naturalWidth,
                        imageNaturalHeight: image.naturalHeight,
                        overlay: { x: overlayRect.x, y: overlayRect.y, width: overlayRect.width, height: overlayRect.height },
                        scene: { x: sceneRect.x, y: sceneRect.y, width: sceneRect.width, height: sceneRect.height },
                        image: { x: imageRect.x, y: imageRect.y, width: imageRect.width, height: imageRect.height },
                        glass: { x: glassRect.x, y: glassRect.y, width: glassRect.width, height: glassRect.height, bottom: glassRect.bottom },
                        expectedClass: `victory-ending-scene--${sceneKey}`,
                    };
                }""",
                {"sceneKey": expected_scene_key},
            )
            overlay = measurement["overlay"]
            scene = measurement["scene"]
            image = measurement["image"]
            glass = measurement["glass"]
            ok = (
                measurement["overlayDisplay"] == "flex"
                and measurement["expectedClass"] in measurement["sceneClass"]
                and f"/static/victory-art/{expected_scene_key}.png" in measurement["imageSrc"]
                and measurement["imageNaturalWidth"] >= 1600
                and overlay["width"] == 1280
                and overlay["height"] == 720
                and scene["width"] == overlay["width"]
                and scene["height"] == overlay["height"]
                and image["x"] <= 0
                and image["y"] <= 0
                and image["x"] + image["width"] >= overlay["width"]
                and image["y"] + image["height"] >= overlay["height"]
                and glass["x"] >= 0
                and glass["bottom"] <= 720
                and glass["height"] <= 346
            )
            record(f"browser_{scene_key}_fills_stage_with_results_panel", ok, measurement)
            page.screenshot(path=str(RECORD_DIR / f"victory_{scene_key}.png"))

        # 非紅軍觀看真正 winner='red_army'：顯示生靈塗炭版與上緣資訊板。
        red_setup = post_json("/test/setup-victory-proof", {"winner": "red_army"})
        red_page = context.new_page()
        red_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        red_page.on("pageerror", lambda error: console_errors.append(str(error)))
        red_page.goto(
            f"{BASE_URL}/?game_id={red_setup['game_id']}&player_id={red_setup['player_id']}",
            wait_until="networkidle",
        )
        red_page.wait_for_function(
            "() => { const image = document.getElementById('victoryEndingArt'); return image?.complete && image.naturalWidth > 0; }"
        )
        red_page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
        red_page.wait_for_timeout(100)
        red_actual = red_page.evaluate(
            """() => ({
                title: document.getElementById('victoryTitle')?.textContent,
                endingTitle: document.getElementById('victoryEndingTitle')?.textContent,
                sceneClass: document.getElementById('victoryEndingScene')?.className,
                imageSrc: document.getElementById('victoryEndingArt')?.currentSrc,
                glassTop: document.querySelector('.victory-glass')?.getBoundingClientRect().top,
            })"""
        )
        record(
            "non_red_viewer_sees_red_army_catastrophe_art_and_top_panel",
            red_actual["title"] == "RED 獲勝"
            and red_actual["endingTitle"] == "紅色鐵幕，籠罩天下"
            and "victory-ending-scene--red_army" in red_actual["sceneClass"]
            and "/static/victory-art/red_army.png" in red_actual["imageSrc"]
            and red_actual["glassTop"] <= 32,
            red_actual,
        )
        red_page.screenshot(path=str(RECORD_DIR / "victory_red_army.png"))
        red_page.close()

        # 紅軍自己觀看同一局：改為征服世界宣傳版，並維持一般的底部資訊板。
        red_viewer_page = context.new_page()
        red_viewer_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        red_viewer_page.on("pageerror", lambda error: console_errors.append(str(error)))
        red_viewer_page.goto(
            f"{BASE_URL}/?game_id={red_setup['game_id']}&player_id={red_setup['red_player_id']}",
            wait_until="networkidle",
        )
        red_viewer_page.wait_for_function(
            "() => { const image = document.getElementById('victoryEndingArt'); return image?.complete && image.naturalWidth > 0; }"
        )
        red_viewer_page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); }")
        red_viewer_page.wait_for_timeout(100)
        red_viewer_actual = red_viewer_page.evaluate(
            """() => ({
                title: document.getElementById('victoryTitle')?.textContent,
                endingTitle: document.getElementById('victoryEndingTitle')?.textContent,
                sceneClass: document.getElementById('victoryEndingScene')?.className,
                imageSrc: document.getElementById('victoryEndingArt')?.currentSrc,
                glassTop: document.querySelector('.victory-glass')?.getBoundingClientRect().top,
            })"""
        )
        record(
            "red_army_viewer_sees_world_conquest_art_and_bottom_panel",
            red_viewer_actual["title"] == "RED 獲勝"
            and red_viewer_actual["endingTitle"] == "赤旗遍寰宇，天下歸一統"
            and "victory-ending-scene--red_army_triumph" in red_viewer_actual["sceneClass"]
            and "/static/victory-art/red_army_triumph.png" in red_viewer_actual["imageSrc"]
            and red_viewer_actual["glassTop"] >= 300,
            red_viewer_actual,
        )
        red_viewer_page.screenshot(path=str(RECORD_DIR / "victory_red_army_triumph.png"))
        red_viewer_page.close()

        contact = context.new_page()
        cards = "".join(
            f'<figure><img src="{BASE_URL}/static/victory-art/{key}.png"><figcaption>{key}</figcaption></figure>'
            for key in ART_KEYS
        )
        contact.set_content(
            "<!doctype html><style>body{margin:0;padding:20px;background:#05080d;color:#fff;font:18px sans-serif;}"
            "main{display:grid;grid-template-columns:repeat(2,640px);gap:16px;}figure{margin:0;background:#111827;padding:8px;}"
            "img{display:block;width:624px;aspect-ratio:16/9;object-fit:cover;}figcaption{padding:7px 2px 1px;}</style>"
            f"<main>{cards}</main>",
            wait_until="load",
        )
        contact.wait_for_function("() => [...document.images].every(image => image.complete && image.naturalWidth > 0)")
        contact.screenshot(path=str(CONTACT_SHEET), full_page=True)
        contact.close()
        context.close()
        browser.close()

    record("browser_console_has_no_errors", not console_errors, {"errors": console_errors})
    payload = {
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result["ok"]),
            "failed": sum(1 for result in results if not result["ok"]),
        },
        "results": results,
        "contact_sheet": str(CONTACT_SHEET),
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 全版 AI 勝利畫面驗證",
        "",
        "重跑：`uv run --with playwright python scripts/validate_victory_fullscreen_ai_art.py`",
        "",
        f"- total: {payload['summary']['total']}",
        f"- passed: {payload['summary']['passed']}",
        f"- failed: {payload['summary']['failed']}",
        f"- contact sheet: `{CONTACT_SHEET}`",
        "",
        "## Results",
    ]
    for result in results:
        lines.append(f"- {'✅' if result['ok'] else '❌'} `{result['name']}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    if payload["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
