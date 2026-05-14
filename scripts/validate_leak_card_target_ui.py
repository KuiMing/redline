import json
import subprocess
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RECORD_DIR = BASE / 'docs' / 'records' / 'leak-card'
OUT_JSON = RECORD_DIR / 'LEAK_CARD_TARGET_UI_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LEAK_CARD_TARGET_UI_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'leak_card_target_modal.png'
BASE_URL = 'http://127.0.0.1:8000/static/index.html?validate_leak_target_ui=1'


def record_path(path):
    return str(path.relative_to(BASE))


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception:
        py = '/usr/bin/python3'
        if Path(py).exists() and Path(sys.executable).resolve() != Path(py).resolve():
            result = subprocess.run([py, str(Path(__file__).resolve())], cwd=str(BASE))
            raise SystemExit(result.returncode)
        raise


def check(name, passed, details):
    return {'name': name, 'passed': bool(passed), 'details': details}


def run_checks():
    sync_playwright = ensure_playwright()
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720}, device_scale_factor=1)
        page.goto(BASE_URL, wait_until='networkidle')
        seeded = page.evaluate("""
        async () => {
          gameId = 'demo';
          playerId = 'p1';
          ws = {readyState: 1, send: (msg) => { window.lastSent = msg; }};
          document.getElementById('lobby').style.display = 'none';
          document.getElementById('gameShell').style.display = 'block';
          const state = {
            turn: 1,
            game_phase: 'main',
            turn_phase: 'action',
            current_player: 'actor',
            market_mode: 'sample_53',
            active_era_details: [],
            players: [
              {id:'p1', name:'actor', faction:'red_army', base:'北京', orgs:{'北京':1}, resources:{money:0, propaganda:0}, moves_left:0, hand:['走漏風聲']},
              {id:'p2', name:'target-a', faction:'hong_kong', base:'香港城', orgs:{'香港城':1}, resources:{money:0, propaganda:0}, moves_left:0, hand:['追隨者','樂捐者']},
              {id:'p3', name:'target-b', faction:'taiwan_green', base:'臺北', orgs:{'臺北':1}, resources:{money:0, propaganda:0}, moves_left:0, hand:['資助者']}
            ],
            purchase_area:['宣傳家','思想家','資助者','資本家','分神','內鬥','走漏風聲','地下黨','離間','合作談判','資助者'],
            action_log:['測試狀態：actor 準備打出走漏風聲']
          };
          window.lastGameState = state;
          await window.render(state);
          return {
            handText: document.getElementById('hand').innerText,
            buttonHtml: Array.from(document.querySelectorAll('#hand button')).map(b => b.outerHTML)
          };
        }
        """)
        page.locator('#hand button').filter(has_text='行動').click()
        page.wait_for_selector('#factionActionModal', state='visible')
        modal_text = page.locator('#factionActionModal').inner_text()
        modal_box = page.locator('#factionActionModal .modal-glass').bounding_box()
        page.screenshot(path=str(SCREENSHOT), full_page=False)

        checks.append(check(
            '走漏風聲_action_button_opens_target_modal_with_all_other_players',
            '走漏風聲：請選擇棄牌庫頂牌對象' in modal_text
            and 'target-a' in modal_text
            and 'target-b' in modal_text
            and modal_box is not None,
            {
                'seeded': seeded,
                'modal_text': modal_text,
                'modal_box': modal_box,
                'screenshot': record_path(SCREENSHOT),
            },
        ))

        page.get_by_role('button', name='target-b').click()
        sent_raw = page.evaluate('window.lastSent || null')
        try:
            sent = json.loads(sent_raw) if sent_raw else None
        except Exception:
            sent = None
        checks.append(check(
            '走漏風聲_clicking_target_b_sends_target_player_id_p3',
            sent == {'action': 'play_card', 'index': 0, 'mode': 'action', 'target_player_id': 'p3'},
            {'sent_raw': sent_raw, 'sent': sent},
        ))
        browser.close()
    return checks


def write_outputs(checks):
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        'total': len(checks),
        'passed': sum(1 for c in checks if c['passed']),
        'failed': sum(1 for c in checks if not c['passed']),
    }
    out = {'date': date.today().isoformat(), 'summary': summary, 'screenshot': record_path(SCREENSHOT), 'checks': checks}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# LEAK CARD TARGET UI VALIDATION', '', f"日期：{out['date']}", '', f"summary: {summary}", '', f"screenshot: {out['screenshot']}", '']
    for item in checks:
        status = 'PASS' if item['passed'] else 'FAIL'
        lines.append(f"## {item['name']} — {status}")
        for k, v in item['details'].items():
            lines.append(f"- {k}: {v}")
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')
    return out


def main():
    out = write_outputs(run_checks())
    print(json.dumps({'summary': out['summary'], 'screenshot': out['screenshot'], 'json': record_path(OUT_JSON), 'md': record_path(OUT_MD)}, ensure_ascii=False))
    if out['summary']['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
