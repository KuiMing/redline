import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    system_python = '/usr/bin/python3'
    if sys.executable != system_python and Path(system_python).exists():
        os.execv(system_python, [system_python, __file__, *sys.argv[1:]])
    raise

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'playtest-flow'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'MY_FACTION_MODAL_VALIDATION.json'
OUT_MD = RECORD_DIR / 'MY_FACTION_MODAL_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'my_faction_modal.png'
SCREENSHOT_HK = RECORD_DIR / 'my_faction_modal_hong_kong.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # --- 1. 臺灣綠線：按鈕開啟、標題染陣營色、四個區塊都有內容 ---
    page = browser.new_context(viewport={'width': 1440, 'height': 900}).new_page()
    setup = post_json('/test/setup-support-card-play', {'support_name': '臺灣奧援', 'faction_id': 'taiwan_green', 'base': '臺北'})
    page.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_timeout(900)
    page.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page.wait_for_timeout(300)

    btn_visible = page.evaluate("() => { const b = document.getElementById('myFactionBtn'); return !!b && getComputedStyle(b).display !== 'none'; }")
    record('my_faction_button_visible_in_game_tabs', btn_visible, {'visible': btn_visible})

    page.click('#myFactionBtn')
    page.wait_for_timeout(300)
    modal_visible = page.evaluate("() => document.getElementById('myFactionModal')?.style.display === 'flex'")
    title = page.evaluate("() => document.getElementById('myFactionTitle')?.textContent")
    title_color = page.evaluate("() => document.querySelector('#myFactionTitle span')?.style.color")
    sections = page.evaluate("() => [...document.querySelectorAll('#myFactionBody .faction-detail-section-title')].map(e => e.textContent)")
    non_empty = page.evaluate("() => [...document.querySelectorAll('#myFactionBody ul')].every(ul => ul.children.length > 0)")
    page.screenshot(path=str(SCREENSHOT))
    record(
        'modal_opens_with_faction_colored_title_and_all_sections',
        modal_visible and title == '臺灣（綠線）' and title_color == 'rgb(74, 222, 128)'
        and sections == ['根據地', '能力', '規則與限制', '獲勝條件'] and non_empty,
        {'modal_visible': modal_visible, 'title': title, 'title_color': title_color, 'sections': sections, 'non_empty': non_empty},
    )

    base_text = page.evaluate("() => document.querySelectorAll('#myFactionBody ul')[0]?.textContent")
    record('base_section_shows_actual_base', '臺北' in (base_text or ''), {'base_text': base_text})

    page.click('#closeMyFactionModal')
    page.wait_for_timeout(200)
    closed = page.evaluate("() => document.getElementById('myFactionModal')?.style.display")
    record('close_button_hides_modal', closed == 'none', {'display': closed})
    page.close()

    # --- 2. 香港（不同陣營資料結構）：能開、有內容，不因資料形狀不同而壞掉 ---
    page2 = browser.new_context(viewport={'width': 1440, 'height': 900}).new_page()
    setup2 = post_json('/test/setup-support-card-play', {'support_name': '臺灣奧援', 'faction_id': 'hong_kong', 'base': '香港城'})
    page2.goto(f"{BASE_URL}/?game_id={setup2['game_id']}&player_id={setup2['player_id']}", wait_until='networkidle')
    page2.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page2.wait_for_timeout(900)
    page2.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b) b.click(); }")
    page2.wait_for_timeout(300)
    page2.click('#myFactionBtn')
    page2.wait_for_timeout(300)
    title2 = page2.evaluate("() => document.getElementById('myFactionTitle')?.textContent")
    ability_count2 = page2.evaluate("() => document.querySelectorAll('#myFactionBody ul')[1]?.children.length")
    page2.screenshot(path=str(SCREENSHOT_HK))
    record(
        'hong_kong_faction_also_renders_correctly',
        title2 == '香港' and (ability_count2 or 0) > 0,
        {'title': title2, 'ability_count': ability_count2},
    )
    page2.close()

    return {
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshots': [str(SCREENSHOT), str(SCREENSHOT_HK)],
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 「我的陣營」按鈕與 modal 驗證',
        '',
        '可重跑指令：`python3 scripts/validate_my_faction_modal.py`',
        '',
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
        f"- screenshots: {', '.join(payload['screenshots'])}",
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
