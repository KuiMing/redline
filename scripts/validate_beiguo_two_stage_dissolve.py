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
RECORD_DIR = ROOT / 'docs' / 'records' / 'support-cards'
BASE_URL = 'http://127.0.0.1:8000'
OUT_JSON = RECORD_DIR / 'BEIGUO_TWO_STAGE_DISSOLVE_VALIDATION.json'
OUT_MD = RECORD_DIR / 'BEIGUO_TWO_STAGE_DISSOLVE_VALIDATION.md'
SCREENSHOT = RECORD_DIR / 'beiguo_two_stage_dissolve.png'


def post_json(path, payload=None):
    data = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def start_flow(page):
    setup = post_json('/test/setup-support-proof', {'support_name': '北國奧援', 'tier': 1})
    gid, pid = setup['game_id'], setup['player_id']
    page.goto(f'{BASE_URL}/?game_id={gid}&player_id={pid}', wait_until='networkidle')
    page.wait_for_selector('#gameShell', state='visible', timeout=10000)
    page.wait_for_timeout(900)
    page.evaluate("() => { if (typeof closeEventReveal === 'function') closeEventReveal(); const b=document.getElementById('closeFactionActionModal'); if(b) b.click(); }")
    page.wait_for_timeout(200)
    page.click('button.hand-card-action-btn[data-card-name="北國奧援"][data-card-mode="action"]')
    page.wait_for_timeout(800)
    return pid


def step_info(page):
    return page.evaluate(
        """() => ({
          step: window.lastGameState?.pending_choice?.step,
          modalVisible: (()=>{const o=document.getElementById('choiceModal');return o&&getComputedStyle(o).display!=='none';})(),
          closeVisible: (()=>{const b=document.getElementById('closeChoiceModal');return b&&getComputedStyle(b).display!=='none';})(),
        })"""
    )


def orgs(page, pid, faction=None):
    if faction:
        return page.evaluate("(f) => window.lastGameState?.players?.find(p=>p.faction===f)?.orgs || {}", faction)
    return page.evaluate("(id) => window.lastGameState?.players?.find(p=>p.id===id)?.orgs || {}", pid)


def check(browser):
    results = []

    def record(name, ok, detail=None):
        results.append({'name': name, 'ok': bool(ok), 'detail': detail or {}})

    # --- Path 0: cancel before choosing the sacrificed organization ---
    cancel_page = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
    cancel_pid = start_flow(cancel_page)
    cancel_page.click('#closeChoiceModal')
    cancel_page.wait_for_timeout(800)
    cancel_state = cancel_page.evaluate("() => window.lastGameState")
    cancel_me = next((p for p in cancel_state.get('players', []) if p.get('id') == cancel_pid), {})
    cancel_hand_count = len(cancel_me.get('hand') or [])
    cancel_enemy_orgs = next((p.get('orgs') for p in cancel_state.get('players', []) if p.get('faction') == 'red_army'), None)
    record(
        'initial_cancel_restores_card_and_leaves_board_unchanged',
        cancel_state.get('pending_choice') is None
        and cancel_hand_count == 1
        and sum((cancel_me.get('orgs') or {}).values()) == 2
        and sum((cancel_enemy_orgs or {}).values()) == 1,
        {
            'hand_count': cancel_hand_count,
            'mine': cancel_me.get('orgs'),
            'enemy': cancel_enemy_orgs,
        },
    )
    cancel_page.close()

    # --- Path A: complete both stages through the modal ---
    page = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
    pid = start_flow(page)
    s1 = step_info(page)
    record(
        'sacrifice_step_has_cancel_button_before_any_board_mutation',
        s1['step'] == 'sacrifice_town' and s1['modalVisible'] and s1['closeVisible'],
        {'step1': s1},
    )
    page.click('#choiceModalCards .modal-choice-btn')  # pick the own org to sacrifice
    page.wait_for_timeout(800)
    s2 = step_info(page)
    record(
        'picking_sacrifice_advances_to_enemy_target_step',
        s2['step'] == 'target' and s2['modalVisible'],
        {'step2': s2},
    )
    record(
        'target_step_keeps_a_close_button_for_the_map_path',
        s2['closeVisible'],
        {'closeVisible': s2['closeVisible']},
    )
    page.screenshot(path=str(SCREENSHOT))
    page.click('#choiceModalCards .modal-choice-btn')  # pick the enemy target
    page.wait_for_timeout(800)
    record(
        'modal_path_dissolves_enemy_and_sacrifices_own_org',
        page.evaluate("() => window.lastGameState?.pending_choice") is None
        and orgs(page, pid, 'red_army') == {}
        and orgs(page, pid) == {'巴黎': 1},
        {'enemy': orgs(page, pid, 'red_army'), 'mine': orgs(page, pid)},
    )
    page.close()

    # --- Path B: close the target modal and finish via the map sidebar ---
    page2 = browser.new_context(viewport={'width': 1280, 'height': 800}).new_page()
    pid2 = start_flow(page2)
    page2.click('#choiceModalCards .modal-choice-btn')  # pick sacrifice
    page2.wait_for_timeout(800)
    page2.evaluate("() => document.getElementById('closeChoiceModal').click()")  # close target modal (map-context)
    page2.wait_for_timeout(400)
    still_pending = page2.evaluate("() => window.lastGameState?.pending_choice?.step")
    page2.click('button.game-tab[data-view="map"]')
    page2.wait_for_timeout(1400)
    page2.evaluate("() => document.getElementById('strategicMapFrame').contentWindow.selectTownForCurrentMapAction('慕尼黑', {autoFocus:true})")
    page2.wait_for_timeout(400)
    btn = page2.evaluate(
        "() => { const b=document.getElementById('strategicMapFrame').contentDocument.getElementById('dissolveBtn'); return { text: b?.textContent, disabled: b?.disabled }; }"
    )
    record(
        'closing_target_modal_keeps_pending_and_map_sidebar_can_finish',
        still_pending == 'target' and btn and not btn['disabled'],
        {'still_pending': still_pending, 'dissolve_btn': btn},
    )
    page2.evaluate("() => document.getElementById('strategicMapFrame').contentDocument.getElementById('dissolveBtn').click()")
    page2.wait_for_timeout(800)
    record(
        'map_path_dissolves_enemy_and_sacrifices_own_org',
        page2.evaluate("() => window.lastGameState?.pending_choice") is None
        and orgs(page2, pid2, 'red_army') == {}
        and orgs(page2, pid2) == {'巴黎': 1},
        {'enemy': orgs(page2, pid2, 'red_army'), 'mine': orgs(page2, pid2)},
    )
    page2.close()

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
        '# 北國奧援 I級兩段式瓦解驗證',
        '',
        '可重跑指令：`python3 scripts/validate_beiguo_two_stage_dissolve.py`',
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
