import json
import os
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'lobby'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'LOBBY_COPY_DEDUP_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LOBBY_COPY_DEDUP_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'lobby_copy_dedup_validation.png'


def check_page(page):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.click('#createRoomBtn')
    page.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
    game_id = page.locator('#roomId').input_value()
    page.wait_for_timeout(300)

    banner_copy_button_removed = page.evaluate(
        "() => document.getElementById('copyRoomBannerBtn') === null"
    )
    record('banner_copy_button_removed', banner_copy_button_removed)

    banner_code_not_clickable = page.evaluate(
        """() => {
          const el = document.getElementById('lobbyRoomBannerCode');
          if (!el) return { present: false };
          return {
            present: true,
            tag: el.tagName.toLowerCase(),
            hasOnclick: !!el.getAttribute('onclick'),
          };
        }"""
    )
    record(
        'banner_code_is_non_interactive_display',
        banner_code_not_clickable.get('present') and banner_code_not_clickable.get('tag') == 'span' and not banner_code_not_clickable.get('hasOnclick'),
        banner_code_not_clickable,
    )

    banner_shows_room_code = page.evaluate(
        "() => document.getElementById('lobbyRoomBannerCode')?.textContent || ''"
    )
    record('banner_still_displays_room_code', banner_shows_room_code == game_id, {'banner_text': banner_shows_room_code, 'game_id': game_id})

    remaining_copy_buttons = page.evaluate(
        "() => [...document.querySelectorAll('button[onclick=\"copyRoomId()\"]')].map(b => b.id)"
    )
    record('exactly_one_copy_button_remains', remaining_copy_buttons == ['copyRoomBtn'], {'remaining_copy_buttons': remaining_copy_buttons})

    page.evaluate("() => { window.__lastRoomCopyResult = null; }")
    page.click('#copyRoomBtn')
    page.wait_for_timeout(300)
    copy_result = page.evaluate('() => window.__lastRoomCopyResult')
    record('remaining_copy_button_still_copies_room_code', bool(copy_result and copy_result.get('value') == game_id), copy_result)

    page.screenshot(path=str(SCREENSHOT), full_page=True)
    return {
        'game_id': game_id,
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshot': str(SCREENSHOT),
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = ctx.new_page()
        payload = check_page(page)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Lobby room-code copy dedup validation',
        '',
        f"- game_id: {payload['game_id']}",
        f"- total: {payload['summary']['total']}",
        f"- passed: {payload['summary']['passed']}",
        f"- failed: {payload['summary']['failed']}",
        f"- screenshot: {payload['screenshot']}",
        '',
        '## Results',
    ]
    for r in payload['results']:
        lines.append(f"- {'✅' if r['ok'] else '❌'} `{r['name']}` — {json.dumps(r['detail'], ensure_ascii=False)}")
    lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(payload['summary'], ensure_ascii=False))
    if payload['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
