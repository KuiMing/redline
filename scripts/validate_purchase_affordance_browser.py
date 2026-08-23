#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8768')
RECORD_DIR = BASE / 'docs' / 'records' / 'purchase'


def post_json(path, payload=None):
    data = json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode('utf-8'))


def make_formal_game():
    create = post_json('/create')
    game_id = create['game_id']
    host_id = create['host_id']
    joined = post_json('/join', {'game_id': game_id, 'name': 'hk'})
    tokens = {'host': create.get('resume_token'), 'hk': joined.get('resume_token')}
    players = [
        ('host', host_id, 'red_army', '北京'),
        ('hk', joined['player_id'], 'hong_kong', '香港城'),
    ]
    for name, pid, faction_id, base_name in players:
        chosen = post_json('/choose-faction', {'game_id': game_id, 'player_id': pid, 'faction_id': faction_id, 'base_name': base_name})
        if chosen.get('error'):
            raise AssertionError(f'choose {name}: {chosen}')
        ready = post_json('/ready', {'game_id': game_id, 'player_id': pid, 'ready': True})
        if ready.get('error'):
            raise AssertionError(f'ready {name}: {ready}')
    started = post_json('/start', {'game_id': game_id, 'player_id': host_id, 'market_mode': 'sample_53'})
    if started.get('error'):
        raise AssertionError(started)
    return game_id, {name: pid for name, pid, *_ in players}, tokens


def dismiss_event_reveal(page):
    # 開局會自動跳出事件卡放大檢視，先關掉才不會攔截後續點擊。
    overlay = page.locator('#eventRevealModal')
    if overlay.count() and overlay.is_visible():
        page.evaluate('closeEventReveal()')
        page.wait_for_timeout(250)


def wait_state(page):
    page.wait_for_function('window.lastGameState && window.lastGameState.players && document.querySelectorAll("#purchaseStatic .card").length === 6', timeout=15000)
    page.wait_for_timeout(350)
    dismiss_event_reveal(page)
    return page.evaluate('window.lastGameState')


def static_card_checkbox(page, card_name='宣傳家'):
    return page.locator('#purchaseStatic .card').filter(has_text=card_name).locator('.purchase-card-checkbox input').first


def play_follower_resources(page, count=3):
    for _ in range(count):
        page.locator('.hand-card').filter(has_text='追隨者').locator("button[data-card-mode='resource']").first.click(timeout=5000)
        page.wait_for_timeout(250)


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_dir = RECORD_DIR / f'purchase-affordance-browser-{stamp}'
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    checks = []
    game_id, ids, tokens = make_formal_game()

    prepared = post_json('/test/set-hand', {
        'game_id': game_id,
        'player_id': ids['hk'],
        'cards': ['追隨者', '追隨者', '追隨者'],
        'turn_phase': 'action',
        'set_current_player': True,
    })
    if prepared.get('error'):
        raise AssertionError(prepared)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        page.on('dialog', lambda dialog: dialog.accept())
        url = f'{BASE_URL}/?game_id={game_id}&player_id={ids["hk"]}&resume_token={tokens["hk"]}&v=purchase-affordance-{stamp}'
        page.goto(url, wait_until='domcontentloaded')
        state = wait_state(page)
        initial_propagandist_supply = int((state.get('static_purchase_supply') or {}).get('宣傳家', 0) or 0)
        meta = page.locator('#phaseActionMeta').inner_text(timeout=5000)
        advance_text = page.locator('#advanceStepBtn').inner_text(timeout=5000)
        advance_display = page.locator('#advanceStepBtn').evaluate('el => getComputedStyle(el).display')
        shot1 = screenshot_dir / '01_initial_action_phase_no_continue_button.png'
        page.screenshot(path=str(shot1), full_page=True)
        checks.append({
            'name': 'initial_action_phase_offers_single_end_action_button',
            'passed': state.get('turn_phase') == 'action' and '繼續行動階段' not in meta and advance_text == '結束行動' and advance_display != 'none',
            'details': {'turn_phase': state.get('turn_phase'), 'meta': meta, 'advance_text': advance_text, 'advance_display': advance_display, 'screenshot': str(shot1.relative_to(BASE))},
        })

        # 出牌與購買同屬一個行動階段：不必先按 advance，購買勾選框在 action 就已可用；
        # 資源不足時擋在確認視窗（勾選仍可，確認鈕停用並顯示「資源不足」）。
        no_resource_state = page.evaluate('window.lastGameState')
        no_resource_selectable = not static_card_checkbox(page).is_disabled()
        static_card_checkbox(page).check(timeout=5000)
        page.wait_for_timeout(250)
        no_resource_buy_disabled = page.locator('#openPurchaseConfirmBtn').is_disabled()
        no_resource_buy_title = page.locator('#openPurchaseConfirmBtn').get_attribute('title')
        shot2 = screenshot_dir / '02_action_phase_no_resources_buy_disabled.png'
        page.screenshot(path=str(shot2), full_page=True)
        page.evaluate('clearPurchaseSelection()')
        page.wait_for_timeout(200)
        checks.append({
            'name': 'purchase_selectable_in_action_phase_but_buy_blocked_without_resources',
            'passed': no_resource_state.get('turn_phase') == 'action' and no_resource_selectable and no_resource_buy_disabled and '超過目前資源' in (no_resource_buy_title or ''),
            'details': {'turn_phase': no_resource_state.get('turn_phase'), 'buy_title': no_resource_buy_title, 'hk_resources': next(pl for pl in no_resource_state['players'] if pl['id'] == ids['hk']).get('resources'), 'screenshot': str(shot2.relative_to(BASE))},
        })

        prepared = post_json('/test/set-hand', {
            'game_id': game_id,
            'player_id': ids['hk'],
            'cards': ['追隨者', '追隨者', '追隨者'],
            'turn_phase': 'action',
            'set_current_player': True,
        })
        if prepared.get('error'):
            raise AssertionError(prepared)
        page.reload(wait_until='domcontentloaded')
        wait_state(page)
        play_follower_resources(page, 3)
        resourced_state = page.evaluate('window.lastGameState')
        # 不按 advance，直接在行動階段購買。
        checkbox = static_card_checkbox(page)
        before_buy_disabled = checkbox.is_disabled()
        before_buy_title = page.locator('#purchaseStatic .card').filter(has_text='宣傳家').locator('.purchase-card-checkbox').first.get_attribute('title')
        checkbox.check(timeout=5000)
        page.wait_for_timeout(200)
        page.locator('#openPurchaseConfirmBtn').click(timeout=5000)
        page.wait_for_timeout(250)
        page.locator('#confirmPurchaseBtn').click(timeout=5000)
        expected_supply_after_buy = initial_propagandist_supply - 1
        page.wait_for_function('(expected) => window.lastGameState && window.lastGameState.static_purchase_supply && window.lastGameState.static_purchase_supply["宣傳家"] === expected', arg=expected_supply_after_buy, timeout=10000)
        page.wait_for_timeout(350)
        bought_state = page.evaluate('window.lastGameState')
        hk = next(pl for pl in bought_state['players'] if pl['id'] == ids['hk'])
        shot3 = screenshot_dir / '03_after_real_click_buy_static_card.png'
        page.screenshot(path=str(shot3), full_page=True)
        checks.append({
            'name': 'after_resources_purchase_enabled_and_real_click_buys_card_in_action_phase',
            'passed': not before_buy_disabled and bought_state.get('turn_phase') == 'action' and bought_state.get('static_purchase_supply', {}).get('宣傳家') == expected_supply_after_buy and '宣傳家' in hk.get('discard_pile', []),
            'details': {
                'resources_before_purchase_step': next(pl for pl in resourced_state['players'] if pl['id'] == ids['hk']).get('resources'),
                'turn_phase_after_buy': bought_state.get('turn_phase'),
                'checkbox_title_before_buy': before_buy_title,
                'static_supply_after_buy': bought_state.get('static_purchase_supply'),
                'hk_resources_after_buy': hk.get('resources'),
                'hk_discard_pile': hk.get('discard_pile'),
                'action_log_tail': bought_state.get('action_log', [])[-6:],
                'screenshot': str(shot3.relative_to(BASE)),
            },
        })
        browser.close()

    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    report = {'summary': summary, 'checks': checks}
    json_path = RECORD_DIR / f'PURCHASE_AFFORDANCE_BROWSER_{stamp}.json'
    md_path = RECORD_DIR / f'PURCHASE_AFFORDANCE_BROWSER_{stamp}.md'
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text('# Purchase affordance browser validation\n\n```json\n' + json.dumps(report, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    print(json.dumps({'summary': summary, 'reports': [str(json_path), str(md_path)], 'screenshots': [str(p) for p in sorted(screenshot_dir.glob('*.png'))]}, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
