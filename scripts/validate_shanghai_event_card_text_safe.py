#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import cast

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8000')
ASSET = ROOT / 'static/card-art/events/上海合作組織.png'
OUT_DIR = ROOT / 'docs/records/event-cards'
JSON_PATH = OUT_DIR / 'SHANGHAI_COOPERATION_TEXT_SAFE_VALIDATION.json'
SCREENSHOT_PATH = OUT_DIR / 'SHANGHAI_COOPERATION_TEXT_SAFE_20260731.png'
CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


def is_dark_rgb(pixel: object) -> bool:
    if not isinstance(pixel, tuple):
        return False
    channels = cast(tuple[int, ...], pixel)
    return bool(channels) and max(channels) < 100


def post_json(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(ASSET) as image:
        asset_size = image.size
        rgb = image.convert('RGB')
        # The mission body occupies y=540..660. Text in this right-side safety strip
        # means the rendered glyphs have reached the panel edge and risk clipping.
        safety_strip = rgb.crop((1260, 540, 1295, 660))
        pixels = safety_strip.load()
        dark_pixels = sum(
            1
            for x in range(safety_strip.width)
            for y in range(safety_strip.height)
            if pixels is not None and is_dark_rgb(pixels[x, y])
        )

    fixture = post_json(
        '/test/setup-event-card-proof',
        {'event_name': '上海合作組織', 'current_event_active': True, 'viewer_faction': 'taiwan'},
    )
    url = f"{BASE_URL}{fixture['url']}&v=shanghai-text-safe-20260731"

    console_errors: list[str] = []
    http_errors: list[dict] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        page.on(
            'response',
            lambda response: http_errors.append({'status': response.status, 'url': response.url})
            if response.status >= 400
            else None,
        )
        page.goto(url, wait_until='networkidle')
        page.locator('#eventRevealModal').wait_for(state='visible', timeout=10000)
        page.wait_for_function(
            """() => {
              const image = document.querySelector('#eventRevealCard .event-card-art-image');
              return image && image.complete && image.naturalWidth === 1350 && image.naturalHeight === 1100;
            }""",
            timeout=10000,
        )
        page.wait_for_timeout(300)
        browser_state = page.evaluate(
            """() => {
              const modal = document.getElementById('eventRevealModal');
              const card = document.getElementById('eventRevealCard');
              const image = card.querySelector('.event-card-art-image');
              const rect = image.getBoundingClientRect();
              return {
                modalVisible: getComputedStyle(modal).display === 'flex',
                imageSrc: image.currentSrc || image.src,
                imageAlt: image.alt,
                naturalWidth: image.naturalWidth,
                naturalHeight: image.naturalHeight,
                renderedWidth: rect.width,
                renderedHeight: rect.height,
                renderedRatio: rect.width / rect.height,
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                insideViewport: rect.left >= 0 && rect.top >= 0 && rect.right <= window.innerWidth && rect.bottom <= window.innerHeight,
                statusText: card.innerText,
              };
            }"""
        )
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        browser.close()

    native_ratio = 1350 / 1100
    unexpected_http_errors = [item for item in http_errors if not item['url'].endswith('/favicon.ico')]
    effective_console_errors = [
        message
        for message in console_errors
        if not (
            message == 'Failed to load resource: the server responded with a status of 404 (Not Found)'
            and http_errors
            and not unexpected_http_errors
        )
    ]
    checks = {
        'runtime_asset_is_1350x1100': asset_size == (1350, 1100),
        'mission_text_respects_right_safety_strip': dark_pixels == 0,
        'modal_is_visible': browser_state['modalVisible'],
        'correct_runtime_asset_is_bound': '上海合作組織.png' in urllib.parse.unquote(browser_state['imageSrc']),
        'image_alt_is_meaningful': browser_state['imageAlt'] == '上海合作組織完整卡面',
        'browser_loaded_native_dimensions': browser_state['naturalWidth'] == 1350 and browser_state['naturalHeight'] == 1100,
        'rendered_ratio_is_preserved': abs(browser_state['renderedRatio'] - native_ratio) < 0.01,
        'rendered_card_stays_inside_viewport': browser_state['insideViewport'],
        'runtime_status_is_present': '進行中' in browser_state['statusText'],
        'console_has_no_errors': not effective_console_errors and not unexpected_http_errors,
    }
    payload = {
        'summary': {
            'total': len(checks),
            'passed': sum(checks.values()),
            'failed': len(checks) - sum(checks.values()),
        },
        'checks': checks,
        'asset': {
            'path': str(ASSET.relative_to(ROOT)),
            'size': list(asset_size),
            'right_safety_strip_dark_pixels': dark_pixels,
        },
        'browser': browser_state,
        'console_errors': console_errors,
        'effective_console_errors': effective_console_errors,
        'http_errors': http_errors,
        'unexpected_http_errors': unexpected_http_errors,
        'screenshot': str(SCREENSHOT_PATH.relative_to(ROOT)),
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
