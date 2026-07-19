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
OUT_JSON = RECORD_DIR / 'VICTORY_SCREEN_AND_CREATOR_NAME_VALIDATION.json'
OUT_MD = RECORD_DIR / 'VICTORY_SCREEN_AND_CREATOR_NAME_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'victory_screen.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # --- 1. 建房者的「行動代號」不再被忽略 ---
    page = browser.new_context(viewport={'width': 1440, 'height': 900}).new_page()
    page.goto(BASE_URL + '/', wait_until='networkidle')
    page.fill('#playerName', '測試代號X')
    page.click('#createRoomBtn')
    page.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
    page.wait_for_timeout(800)  # 等 lobby sync 更新 roster
    roster_name = page.evaluate("() => document.getElementById('lobbyRosterName')?.textContent")
    record('creator_typed_name_is_used_not_host', roster_name == '測試代號X', {'roster_name': roster_name})
    page.close()

    # --- 2. 綠線玩家獲勝：勝利畫面顯示、名字染陣營色、戰況表 ---
    page2 = browser.new_context(viewport={'width': 1440, 'height': 900}).new_page()
    setup = post_json('/test/setup-victory-proof', {'winner_name': 'GREEN', 'co_winners': []})
    page2.goto(f"{BASE_URL}/?game_id={setup['game_id']}&player_id={setup['player_id']}", wait_until='networkidle')
    page2.wait_for_timeout(1200)
    visible = page2.evaluate("() => document.getElementById('victoryModal')?.style.display !== 'none'")
    title = page2.evaluate("() => document.getElementById('victoryTitle')?.textContent")
    title_color = page2.evaluate("() => document.querySelector('#victoryTitle span')?.style.color")
    subtitle = page2.evaluate("() => document.getElementById('victorySubtitle')?.textContent")
    rows = page2.evaluate("() => document.querySelectorAll('#victorySummary .victory-summary-row:not(.header)').length")
    winner_row = page2.evaluate("() => document.querySelector('#victorySummary .winner-row .victory-player-name')?.textContent")
    page2.screenshot(path=str(SCREENSHOT))
    record(
        'green_winner_modal_shows_name_in_faction_color',
        visible and title == 'GREEN 獲勝' and title_color == 'rgb(74, 222, 128)',
        {'visible': visible, 'title': title, 'title_color': title_color},
    )
    record(
        'modal_shows_faction_turn_and_player_summary',
        subtitle == '臺灣（綠線）｜第 21 回合結算' and rows == 2 and (winner_row or '').startswith('GREEN'),
        {'subtitle': subtitle, 'rows': rows, 'winner_row': winner_row},
    )

    # --- 3. 縮小後顯示徽章、點徽章可重開 ---
    page2.click('#victoryMinimizeBtn')
    page2.wait_for_timeout(300)
    minimized = page2.evaluate(
        "() => ({ modal: document.getElementById('victoryModal').style.display, badge: document.getElementById('victoryBadge').style.display, badge_text: document.getElementById('victoryBadge').textContent })"
    )
    page2.click('#victoryBadge')
    page2.wait_for_timeout(300)
    reopened = page2.evaluate("() => document.getElementById('victoryModal').style.display")
    record(
        'minimize_shows_badge_and_badge_reopens_modal',
        minimized['modal'] == 'none' and minimized['badge'] == 'block'
        and '遊戲結束' in minimized['badge_text'] and reopened == 'flex',
        {'minimized': minimized, 'reopened': reopened},
    )
    page2.close()

    # --- 4. 紅軍獲勝（winner='red_army'）：解析到紅軍玩家、染紅 ---
    page3 = browser.new_context(viewport={'width': 1440, 'height': 900}).new_page()
    setup3 = post_json('/test/setup-victory-proof', {'winner': 'red_army'})
    page3.goto(f"{BASE_URL}/?game_id={setup3['game_id']}&player_id={setup3['player_id']}", wait_until='networkidle')
    page3.wait_for_timeout(1200)
    title3 = page3.evaluate("() => document.getElementById('victoryTitle')?.textContent")
    color3 = page3.evaluate("() => document.querySelector('#victoryTitle span')?.style.color")
    record(
        'red_army_winner_resolves_to_red_player_in_red',
        title3 == 'RED 獲勝' and color3 == 'rgb(240, 79, 86)',
        {'title': title3, 'color': color3},
    )
    page3.close()

    return {
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
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 勝利畫面／建房者行動代號 驗證',
        '',
        '可重跑指令：`python3 scripts/validate_victory_screen_and_creator_name.py`',
        '',
        f"- total: {payload['summary']['total']} / passed: {payload['summary']['passed']} / failed: {payload['summary']['failed']}",
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
