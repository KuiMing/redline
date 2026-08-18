#!/usr/bin/env python3
"""行動階段合併驗收（真實瀏覽器）。

對應使用者回報的錯誤流程：「出牌 → 結束行動 → 購買 → 無法再出牌」。
合併後出牌／購買／陣營能力同屬一個行動階段，可自由交錯，只有「結束行動階段」
是不可逆的動作（補手牌到 5 張、換下一位玩家）。

用法：先啟動伺服器，再以 REDLINE_BASE_URL 指向它：
    REDLINE_BASE_URL=http://127.0.0.1:8765 python scripts/validate_action_phase_interleave_browser.py
"""
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8765')
RECORD_DIR = BASE / 'docs' / 'records' / 'turn-flow'


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode('utf-8'))


def make_formal_game():
    create = post_json('/create')
    game_id = create['game_id']
    host_id = create['host_id']
    joined = post_json('/join', {'game_id': game_id, 'name': 'ally'})
    ally_id = joined['player_id']
    seats = [
        (host_id, 'red_army', '北京'),
        (ally_id, 'hong_kong', '香港城'),
    ]
    for pid, faction_id, base_name in seats:
        chosen = post_json('/choose-faction', {'game_id': game_id, 'player_id': pid, 'faction_id': faction_id, 'base_name': base_name})
        if chosen.get('error'):
            raise AssertionError(chosen)
        ready = post_json('/ready', {'game_id': game_id, 'player_id': pid, 'ready': True})
        if ready.get('error'):
            raise AssertionError(ready)
    started = post_json('/start', {'game_id': game_id, 'player_id': host_id, 'market_mode': 'sample_53'})
    if started.get('error'):
        raise AssertionError(started)
    return game_id, ally_id, joined.get('resume_token')


def dismiss_overlays(page):
    for selector, closer in (('#eventRevealModal', 'closeEventReveal()'), ('#factionActionModal', None)):
        overlay = page.locator(selector)
        if overlay.count() and overlay.is_visible():
            if closer:
                page.evaluate(closer)
            else:
                page.evaluate("document.getElementById('factionActionModal').style.display='none'")
            page.wait_for_timeout(200)


def play_first_follower(page):
    page.locator('.hand-card').filter(has_text='追隨者').locator("button[data-card-mode='resource']").first.click(timeout=5000)
    page.wait_for_timeout(400)


def buy_first_static_card(page):
    page.locator('#purchaseStatic .purchase-card-checkbox input').first.check(timeout=5000)
    page.wait_for_timeout(200)
    page.locator('#openPurchaseConfirmBtn').click(timeout=5000)
    page.wait_for_timeout(250)
    page.locator('#confirmPurchaseBtn').click(timeout=5000)
    page.wait_for_timeout(700)


def main():
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    shots_dir = RECORD_DIR / f'action-phase-interleave-{stamp}'
    shots_dir.mkdir(parents=True, exist_ok=True)
    game_id, ally_id, token = make_formal_game()
    prepared = post_json('/test/set-hand', {
        'game_id': game_id,
        'player_id': ally_id,
        'cards': ['追隨者'] * 8,
        'turn_phase': 'action',
        'set_current_player': True,
    })
    if prepared.get('error'):
        raise AssertionError(prepared)

    checks = []
    console_errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: console_errors.append(str(e)))
        page.goto(f'{BASE_URL}/?game_id={game_id}&player_id={ally_id}&resume_token={token}&v=interleave-{stamp}', wait_until='domcontentloaded')
        page.wait_for_function('window.lastGameState && document.querySelectorAll(".hand-card").length > 0', timeout=15000)
        page.wait_for_timeout(400)
        dismiss_overlays(page)

        # 1. 行動階段一開始就顯示「結束行動階段」，且購買區已可勾選。
        state0 = page.evaluate('window.lastGameState')
        advance_text = page.locator('#advanceStepBtn').inner_text(timeout=5000)
        buy_selectable = not page.locator('#purchaseStatic .purchase-card-checkbox input').first.is_disabled()
        page.screenshot(path=str(shots_dir / '01_action_phase_start_buy_already_selectable.png'), full_page=True)
        checks.append({
            'name': '01_action_phase_starts_with_end_action_button_and_selectable_purchase',
            'passed': state0.get('turn_phase') == 'action' and advance_text == '結束行動階段' and buy_selectable,
            'details': {'turn_phase': state0.get('turn_phase'), 'advance_text': advance_text, 'buy_selectable': buy_selectable},
        })

        # 2. 打出手牌（資源模式）→ 資源增加、仍在 action。
        me0 = next(pl for pl in state0['players'] if pl['id'] == ally_id)
        for _ in range(3):
            play_first_follower(page)
        state1 = page.evaluate('window.lastGameState')
        me1 = next(pl for pl in state1['players'] if pl['id'] == ally_id)
        page.screenshot(path=str(shots_dir / '02_after_first_hand_cards.png'), full_page=True)
        checks.append({
            'name': '02_playing_hand_cards_grants_resources_and_stays_in_action',
            'passed': state1.get('turn_phase') == 'action' and (me1.get('resources') or {}).get('propaganda', 0) > (me0.get('resources') or {}).get('propaganda', 0),
            'details': {'turn_phase': state1.get('turn_phase'), 'resources_before': me0.get('resources'), 'resources_after': me1.get('resources')},
        })

        # 3. 購買一張卡 → 成功、仍在 action。
        supply_before = (state1.get('static_purchase_supply') or {}).get('宣傳家')
        buy_first_static_card(page)
        state2 = page.evaluate('window.lastGameState')
        me2 = next(pl for pl in state2['players'] if pl['id'] == ally_id)
        page.screenshot(path=str(shots_dir / '03_after_first_purchase_still_action.png'), full_page=True)
        checks.append({
            'name': '03_first_purchase_succeeds_without_leaving_action_phase',
            'passed': state2.get('turn_phase') == 'action' and '宣傳家' in (me2.get('discard_pile') or []) and (state2.get('static_purchase_supply') or {}).get('宣傳家') == supply_before - 1,
            'details': {'turn_phase': state2.get('turn_phase'), 'discard_pile': me2.get('discard_pile'), 'supply_before': supply_before, 'supply_after': (state2.get('static_purchase_supply') or {}).get('宣傳家')},
        })

        # 4. 購買後再打出一張手牌 —— 這正是修正前會失敗的步驟。
        hand_before_second_play = len(me2.get('hand') or [])
        play_first_follower(page)
        state3 = page.evaluate('window.lastGameState')
        me3 = next(pl for pl in state3['players'] if pl['id'] == ally_id)
        notice = page.locator('#phaseActionNotice')
        notice_text = notice.inner_text(timeout=2000) if notice.count() and notice.is_visible() else ''
        page.screenshot(path=str(shots_dir / '04_play_hand_card_after_purchase.png'), full_page=True)
        checks.append({
            'name': '04_can_play_hand_card_again_after_buying',
            'passed': state3.get('turn_phase') == 'action' and len(me3.get('hand') or []) == hand_before_second_play - 1 and '購買階段' not in notice_text,
            'details': {'turn_phase': state3.get('turn_phase'), 'hand_before': hand_before_second_play, 'hand_after': len(me3.get('hand') or []), 'notice': notice_text},
        })

        # 5. 再購買一次 → 成功（先補足這次購買所需的宣傳）。
        for _ in range(2):
            play_first_follower(page)
        state3b = page.evaluate('window.lastGameState')
        supply_before2 = (state3b.get('static_purchase_supply') or {}).get('宣傳家')
        buy_first_static_card(page)
        state4 = page.evaluate('window.lastGameState')
        me4 = next(pl for pl in state4['players'] if pl['id'] == ally_id)
        page.screenshot(path=str(shots_dir / '05_second_purchase_after_second_play.png'), full_page=True)
        checks.append({
            'name': '05_second_purchase_after_second_play_succeeds',
            'passed': state4.get('turn_phase') == 'action' and (state4.get('static_purchase_supply') or {}).get('宣傳家') == supply_before2 - 1 and (me4.get('discard_pile') or []).count('宣傳家') >= 2,
            'details': {'turn_phase': state4.get('turn_phase'), 'supply_before': supply_before2, 'supply_after': (state4.get('static_purchase_supply') or {}).get('宣傳家'), 'discard_pile': me4.get('discard_pile')},
        })

        # 6. 陣營主動能力入口在整個合併行動階段都可用。
        faction_panel_visible = page.locator('#factionActionPanel').evaluate('el => getComputedStyle(el).display') != 'none'
        faction_buttons = page.locator('#factionActionButtons button').count()
        my_faction_tab_enabled = not page.locator('#myFactionBtn').is_disabled()
        page.screenshot(path=str(shots_dir / '06_faction_ability_entry_available.png'), full_page=True)
        checks.append({
            'name': '06_faction_ability_entry_available_during_merged_action_phase',
            'passed': my_faction_tab_enabled and state4.get('turn_phase') == 'action',
            'details': {'faction_panel_visible': faction_panel_visible, 'faction_buttons': faction_buttons, 'my_faction_tab_enabled': my_faction_tab_enabled},
        })

        # 7. 按一次「結束行動階段」→ 補手牌到 5 張、換下一位玩家、回到 action。
        before_player = state4.get('current_player')
        page.locator('#advanceStepBtn').click(timeout=5000)
        page.wait_for_function('(name) => window.lastGameState && window.lastGameState.current_player !== name', arg=before_player, timeout=15000)
        page.wait_for_timeout(500)
        state5 = page.evaluate('window.lastGameState')
        me5 = next(pl for pl in state5['players'] if pl['id'] == ally_id)
        page.screenshot(path=str(shots_dir / '07_after_single_end_action_phase.png'), full_page=True)
        checks.append({
            'name': '07_single_end_action_phase_refills_hand_and_passes_seat',
            'passed': state5.get('current_player') != before_player and state5.get('turn_phase') == 'action' and len(me5.get('hand') or []) == 5,
            'details': {'before_player': before_player, 'after_player': state5.get('current_player'), 'turn_phase': state5.get('turn_phase'), 'hand_size': len(me5.get('hand') or [])},
        })

        checks.append({
            'name': '08_no_console_errors',
            'passed': len(console_errors) == 0,
            'details': {'console_errors': console_errors},
        })
        browser.close()

    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    report = {'summary': summary, 'checks': checks, 'screenshots': [str(s.relative_to(BASE)) for s in sorted(shots_dir.glob('*.png'))]}
    json_path = RECORD_DIR / f'ACTION_PHASE_INTERLEAVE_BROWSER_{stamp}.json'
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'summary': summary, 'json': str(json_path), 'screenshots_dir': str(shots_dir)}, ensure_ascii=False))
    if summary['failed']:
        for check in checks:
            if not check['passed']:
                print(json.dumps(check, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
