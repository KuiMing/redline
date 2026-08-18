#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8766')
RECORD_DIR = BASE / 'docs' / 'records' / 'phase-flow'


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
    page.wait_for_function('window.lastGameState && window.lastGameState.players && document.querySelectorAll(".hand-card").length > 0', timeout=15000)
    page.wait_for_timeout(350)
    dismiss_event_reveal(page)
    return page.evaluate('window.lastGameState')


def event_panel_snapshot(page):
    panel = page.locator('#eventCardPanel')
    return {
        'visible': panel.is_visible(timeout=5000),
        'text': panel.inner_text(timeout=5000) if panel.is_visible(timeout=5000) else '',
        'html': panel.inner_html(timeout=5000) if panel.is_visible(timeout=5000) else '',
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_dir = RECORD_DIR / f'action-first-phase-{stamp}'
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    game_id, ids, tokens = make_formal_game()
    prepared = post_json('/test/set-hand', {
        'game_id': game_id,
        'player_id': ids['hk'],
        'cards': ['追隨者', '追隨者', '追隨者', '追隨者', '追隨者'],
        'turn_phase': 'action',
        'set_current_player': True,
    })
    if prepared.get('error'):
        raise AssertionError(prepared)

    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        url = f'{BASE_URL}/?game_id={game_id}&player_id={ids["hk"]}&resume_token={tokens["hk"]}&v=action-first-phase-{stamp}'
        page.goto(url, wait_until='domcontentloaded')
        state = wait_state(page)
        meta = page.locator('#phaseActionMeta').inner_text(timeout=5000)
        advance_text = page.locator('#advanceStepBtn').inner_text(timeout=5000)
        event_panel = event_panel_snapshot(page)
        resource_disabled = page.locator(".hand-card").filter(has_text='追隨者').locator("button[data-card-mode='resource']").first.is_disabled()
        action_disabled = page.locator(".hand-card").filter(has_text='追隨者').locator("button[data-card-mode='action']").first.is_disabled()
        # 出牌與購買同屬一個行動階段：不必先按 advance，購買勾選框一開始就可用。
        buy_enabled_action = not page.locator('#purchaseStatic .purchase-card-checkbox input').first.is_disabled()
        shot1 = screenshot_dir / '01_initial_action_phase_cards_and_buy_enabled.png'
        page.screenshot(path=str(shot1), full_page=True)
        checks.append({'name': 'starts_in_action_phase', 'passed': state.get('turn_phase') == 'action' and '目前：行動｜下一步：結束行動階段' in meta and advance_text == '結束行動階段', 'details': {'meta': meta, 'advance_text': advance_text, 'turn_phase': state.get('turn_phase')}})
        event_name = (state.get('current_event') or {}).get('name', '')
        checks.append({'name': 'current_event_visible_at_action_start', 'passed': bool(state.get('current_event')) and event_panel['visible'] and (event_name in event_panel['text'] or event_name in event_panel['html']), 'details': {'current_event': state.get('current_event'), 'event_panel': {k: v for k, v in event_panel.items() if k != 'html'}}})
        checks.append({'name': 'hand_actions_enabled_initially', 'passed': not resource_disabled and not action_disabled})
        checks.append({'name': 'purchase_enabled_in_action_phase_without_advancing', 'passed': buy_enabled_action})

        # 使用者回報的流程：出牌 -> 購買 -> 再出牌，全程不按 advance。
        for _ in range(3):
            page.locator(".hand-card").filter(has_text='追隨者').locator("button[data-card-mode='resource']").first.click(timeout=5000)
            page.wait_for_timeout(250)
        state_after_play = page.evaluate('window.lastGameState')

        page.locator('#purchaseStatic .purchase-card-checkbox input').first.check(timeout=5000)
        page.wait_for_timeout(200)
        page.locator('#openPurchaseConfirmBtn').click(timeout=5000)
        page.wait_for_timeout(250)
        page.locator('#confirmPurchaseBtn').click(timeout=5000)
        page.wait_for_timeout(600)
        state_after_buy = page.evaluate('window.lastGameState')

        hand_after_buy_enabled = bool(page.locator(".hand-card button[data-card-mode='resource']").count()) and not page.locator(".hand-card button[data-card-mode='resource']").first.is_disabled()
        page.locator(".hand-card").filter(has_text='追隨者').locator("button[data-card-mode='resource']").first.click(timeout=5000)
        page.wait_for_timeout(400)
        state_mid = page.evaluate('window.lastGameState')
        notice = page.locator('#phaseActionNotice')
        notice_text = notice.inner_text(timeout=2000) if notice.count() and notice.is_visible() else ''
        buy_still_enabled = not page.locator('#purchaseStatic .purchase-card-checkbox input').first.is_disabled()
        shot2 = screenshot_dir / '02_play_buy_play_all_inside_one_action_phase.png'
        page.screenshot(path=str(shot2), full_page=True)
        checks.append({
            'name': 'play_then_buy_then_play_again_inside_one_action_phase',
            'passed': (
                state_after_play.get('turn_phase') == 'action'
                and state_after_buy.get('turn_phase') == 'action'
                and state_mid.get('turn_phase') == 'action'
                and hand_after_buy_enabled
                and buy_still_enabled
                and '購買階段' not in notice_text
            ),
            'details': {
                'turn_phase_after_play': state_after_play.get('turn_phase'),
                'turn_phase_after_buy': state_after_buy.get('turn_phase'),
                'turn_phase_after_second_play': state_mid.get('turn_phase'),
                'hand_enabled_after_buy': hand_after_buy_enabled,
                'buy_still_enabled': buy_still_enabled,
                'notice_text': notice_text,
            },
        })

        # 唯一不可逆的動作：按一次「結束行動階段」→ 補牌、換下一位玩家。
        before_player = state_mid.get('current_player')
        page.locator('#advanceStepBtn').click(timeout=5000)
        page.wait_for_function('window.lastGameState && window.lastGameState.current_player !== %s' % json.dumps(before_player), timeout=10000)
        page.wait_for_timeout(350)
        state2 = page.evaluate('window.lastGameState')
        shot3 = screenshot_dir / '03_after_ending_action_phase_seat_passed.png'
        page.screenshot(path=str(shot3), full_page=True)
        checks.append({'name': 'single_advance_ends_action_phase_and_passes_seat', 'passed': state2.get('current_player') != before_player and state2.get('turn_phase') == 'action', 'details': {'before_player': before_player, 'after': {'current_player': state2.get('current_player'), 'turn_phase': state2.get('turn_phase')}}})
        browser.close()

    summary = {'total': len(checks), 'passed': sum(1 for c in checks if c['passed']), 'failed': sum(1 for c in checks if not c['passed'])}
    report = {'summary': summary, 'checks': checks, 'screenshots': [str(p.relative_to(BASE)) for p in sorted(screenshot_dir.glob('*.png'))]}
    json_path = RECORD_DIR / f'ACTION_FIRST_PHASE_BROWSER_{stamp}.json'
    md_path = RECORD_DIR / f'ACTION_FIRST_PHASE_BROWSER_{stamp}.md'
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    md_path.write_text('# Action-first phase browser validation\n\n```json\n' + json.dumps(report, ensure_ascii=False, indent=2) + '\n```\n', encoding='utf-8')
    print(json.dumps({'summary': summary, 'reports': [str(json_path), str(md_path)], 'screenshots': [str(BASE / p) for p in report['screenshots']]}, ensure_ascii=False))
    if summary['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
