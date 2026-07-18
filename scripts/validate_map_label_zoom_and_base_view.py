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
RECORD_DIR = ROOT / 'docs' / 'records' / 'map-ui'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'MAP_LABEL_ZOOM_AND_BASE_VIEW_VALIDATION.json'
OUT_MD = RECORD_DIR / 'MAP_LABEL_ZOOM_AND_BASE_VIEW_VALIDATION.md'
SCREENSHOT_FAR = RECORD_DIR / 'map_label_far_zoom.png'
SCREENSHOT_NEAR = RECORD_DIR / 'map_label_near_zoom.png'


def request_json(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def taipei_label(page):
    return page.evaluate(
        """() => {
          const f = document.getElementById('strategicMapFrame');
          const win = f.contentWindow;
          let text = null;
          win.__redlinePlayableMap.eachLayer(layer => {
            if (layer.getTooltip && layer.getTooltip()) {
              const content = layer.getTooltip().getContent();
              if (String(content).startsWith('臺北')) text = String(content);
            }
          });
          return text;
        }"""
    )


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
    host = ctx.new_page()
    ally = ctx.new_page()

    host.goto(BASE_URL + '/', wait_until='networkidle')
    ally.goto(BASE_URL + '/', wait_until='networkidle')

    host.fill('#playerName', 'host')
    host.click('#createRoomBtn')
    host.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
    game_id = host.locator('#roomId').input_value()
    host_player_id = host.evaluate('playerId')

    ally.fill('#roomId', game_id)
    ally.fill('#playerName', 'ally')
    ally.click('#joinRoomBtn')
    ally.wait_for_function("() => typeof playerId !== 'undefined' && playerId", timeout=10000)
    ally_player_id = ally.evaluate('playerId')

    request_json('/choose-faction', {'game_id': game_id, 'player_id': host_player_id, 'faction_id': 'red_army'})
    request_json('/choose-faction', {'game_id': game_id, 'player_id': ally_player_id, 'faction_id': 'taiwan_green', 'base_name': '臺北'})

    host.click('#toggleReadyBtn')
    ally.click('#toggleReadyBtn')
    host.wait_for_timeout(400)
    host.click('#startGameBtn')
    host.wait_for_selector('#gameShell', state='visible', timeout=10000)
    ally.wait_for_selector('#gameShell', state='visible', timeout=10000)

    # --- 1. 開局地圖以自己的根據地為中心 zoom 9（用 ally＝臺灣綠線、根據地臺北 驗證） ---
    ally.click('button.game-tab[data-view="map"]')
    ally.wait_for_timeout(2500)
    view = ally.evaluate(
        """() => {
          const f = document.getElementById('strategicMapFrame');
          const m = f.contentWindow.__redlinePlayableMap;
          const c = m.getCenter();
          return { lat: c.lat, lon: c.lng, zoom: m.getZoom() };
        }"""
    )
    # 臺北座標約 (25.03, 121.56)；容許小數誤差
    record(
        'initial_view_centers_on_own_base_at_zoom_9',
        view['zoom'] == 9 and abs(view['lat'] - 25.03) < 0.5 and abs(view['lon'] - 121.56) < 0.5,
        {'view': view},
    )

    # --- 2. 側欄「當前行動玩家」名字使用「該玩家自己」的陣營色 ---
    # 必須在兩個玩家的頁面都驗：舊 bug 是用「觀看者」的陣營查色，viewer ≠ current 的那一頁
    # 會染錯色（例如紅軍視角把 GREEN 的名字染成紅色）；不論起始玩家是誰，兩頁同驗必抓得到。
    host.click('button.game-tab[data-view="map"]')
    host.wait_for_timeout(2500)
    sidebar_color_ally = ally.evaluate(
        """() => {
          const f = document.getElementById('strategicMapFrame');
          const el = f.contentWindow.document.getElementById('statusCurrentPlayer');
          return el ? el.style.color : null;
        }"""
    )
    sidebar_color_host = host.evaluate(
        """() => {
          const f = document.getElementById('strategicMapFrame');
          const el = f.contentWindow.document.getElementById('statusCurrentPlayer');
          return el ? el.style.color : null;
        }"""
    )
    current_is_host = ally.evaluate("() => window.lastGameState?.current_player")
    # 起始玩家可能是 host（紅軍 #f04f56）或 ally（綠線 #4ade80）
    expected = 'rgb(240, 79, 86)' if current_is_host == 'host' else 'rgb(74, 222, 128)'
    record(
        'map_sidebar_current_player_name_uses_that_players_faction_color_on_both_views',
        sidebar_color_ally == expected and sidebar_color_host == expected,
        {'sidebar_color_ally': sidebar_color_ally, 'sidebar_color_host': sidebar_color_host,
         'current_player': current_is_host, 'expected': expected},
    )

    # --- 3. 標籤 zoom 門檻：ally 開局在根據地臺北有 1 個組織；遠 zoom 標籤只有「臺北 1」、
    # zoom >= 9 才附陣營文字 ---
    ally.wait_for_timeout(300)
    has_taipei_org = ally.evaluate(
        "() => { const s = window.lastGameState; const me = (s?.players || []).find(p => p.name === 'ally'); return (me?.orgs?.['臺北'] || 0) > 0; }"
    )

    # 門檻為 10：zoom 9（開局根據地視角）仍是短標籤，zoom 10 起才附陣營文字。
    ally.evaluate("() => { const f = document.getElementById('strategicMapFrame'); f.contentWindow.__redlinePlayableMap.setView([24.7, 121.2], 9, {animate:false}); }")
    ally.wait_for_timeout(800)
    label_far = taipei_label(ally)
    ally.locator('#strategicMapFrame').screenshot(path=str(SCREENSHOT_FAR))

    ally.evaluate("() => { const f = document.getElementById('strategicMapFrame'); f.contentWindow.__redlinePlayableMap.setView([25.03, 121.45], 10, {animate:false}); }")
    ally.wait_for_timeout(800)
    label_near = taipei_label(ally)
    ally.locator('#strategicMapFrame').screenshot(path=str(SCREENSHOT_NEAR))

    record(
        'far_zoom_label_omits_faction_text',
        has_taipei_org and label_far == '臺北 1',
        {'has_taipei_org': has_taipei_org, 'label_far': label_far},
    )
    record(
        'near_zoom_label_includes_faction_text',
        has_taipei_org and label_near == '臺北 1（臺灣（綠線））',
        {'label_near': label_near},
    )

    # --- 4. 主畫面：戰況總覽玩家名與 HUD 當前玩家名使用陣營色 ---
    ally.click('button.game-tab[data-view="log"]')
    ally.wait_for_timeout(400)
    status_colors = ally.evaluate(
        """() => [...document.querySelectorAll('#playerStatusOverview .player-status-name')].map(el => ({name: el.textContent, color: el.style.color}))"""
    )
    by_name = {entry['name']: entry['color'] for entry in status_colors}
    record(
        'status_overview_names_use_faction_colors',
        by_name.get('host') == 'rgb(240, 79, 86)' and by_name.get('ally') == 'rgb(74, 222, 128)',
        {'status_colors': status_colors},
    )
    hud_color = ally.evaluate(
        """() => {
          const chips = [...document.querySelectorAll('.hud-chip')];
          const chip = chips.find(c => c.textContent.includes('當前玩家'));
          const span = chip ? chip.querySelector('span') : null;
          return span ? span.style.color : null;
        }"""
    )
    record(
        'hud_current_player_name_uses_faction_color',
        hud_color == expected,
        {'hud_color': hud_color, 'expected': expected},
    )

    ctx.close()
    return {
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results if r['ok']),
            'failed': sum(1 for r in results if not r['ok']),
        },
        'results': results,
        'screenshots': [str(SCREENSHOT_FAR), str(SCREENSHOT_NEAR)],
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        payload = check(browser)
        browser.close()

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# 地圖標籤 zoom 門檻／開局根據地視角／玩家名陣營色 驗證',
        '',
        '可重跑指令：`python3 scripts/validate_map_label_zoom_and_base_view.py`',
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
