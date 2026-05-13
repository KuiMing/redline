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

BASE = Path(__file__).resolve().parent.parent
RECORD_DIR = BASE / 'docs' / 'records' / 'card-ui'
OUT_JSON = RECORD_DIR / 'CARD_UI_VALIDATION_RESULTS.json'
OUT_MD = RECORD_DIR / 'CARD_UI_VALIDATION_RESULTS.md'
CARDS = json.loads((BASE / 'data' / 'action_cards_structured.v1.1.json').read_text(encoding='utf-8'))['cards']

TYPE_ORDER = [
    'propaganda', 'money', 'disruption', 'command', 'transport',
    'organization', 'purge', 'propaganda_special', 'spy', 'armed'
]

TYPE_CARD = {}
for t in TYPE_ORDER:
    TYPE_CARD[t] = next(card['name'] for card in CARDS if card['type'] == t)

FACTION_ID_BY_SELECTION = {
    ('紅軍', None, '北京'): 'red_army',
    ('香港', None, '香港城'): 'hong_kong',
    ('臺灣', '綠線', '臺北'): 'taiwan_green',
    ('維吾爾', '阿拉木圖', '阿拉木圖'): 'uyghur_almaty',
    ('西藏', '達蘭薩拉', '達蘭薩拉'): 'tibet_dharamsala',
}


def create_context(p):
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={'width': 1440, 'height': 960})
    return browser, ctx


def mark_ready(page):
    page.click('text=我已準備')
    page.wait_for_timeout(1200)


def wait_for_lobby_state(page, predicate_js, timeout_ms=10000):
    page.wait_for_function(
        f"""() => {{
            const state = window.latestLobbyState || null;
            return !!({predicate_js});
        }}""",
        timeout=timeout_ms,
    )


def request_json(page, path, payload=None):
    payload_json = 'null' if payload is None else json.dumps(payload, ensure_ascii=False)
    return page.evaluate(
        f"""async () => {{
            const payload = {payload_json};
            const options = payload ? {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(payload),
            }} : undefined;
            const res = await fetch({json.dumps(path)}, options);
            return await res.json();
        }}"""
    )


def refresh_lobby_until(page, predicate_js, attempts=8, timeout_ms=4000):
    last_error = None
    for _ in range(attempts):
        page.evaluate('refreshLobbyState().catch(() => null)')
        try:
            wait_for_lobby_state(page, predicate_js, timeout_ms=timeout_ms)
            return
        except Exception as exc:
            last_error = exc
    raise last_error


def wait_for_confirmed_faction(page, player_id, timeout_ms=10000):
    pid = json.dumps(player_id)
    deadline = timeout_ms
    while deadline > 0:
        lobby = request_json(page, f'/lobby/{page.locator("#roomId").input_value()}')
        if lobby.get('factions', {}).get(player_id) and lobby.get('bases', {}).get(player_id):
            page.evaluate('refreshLobbyState().catch(() => null)')
            return
        page.wait_for_timeout(250)
        deadline -= 250
    raise RuntimeError(f'confirmed faction not visible in lobby for {player_id}')


def wait_for_ready_state(page, player_id, ready=True, timeout_ms=10000):
    expected = ready
    deadline = timeout_ms
    while deadline > 0:
        lobby = request_json(page, f'/lobby/{page.locator("#roomId").input_value()}')
        if lobby.get('ready', {}).get(player_id) is expected:
            page.evaluate('refreshLobbyState().catch(() => null)')
            return
        page.wait_for_timeout(250)
        deadline -= 250
    raise RuntimeError(f'ready state not visible in lobby for {player_id}: expected={expected}')


def wait_for_lobby_started(page, timeout_ms=10000):
    deadline = timeout_ms
    while deadline > 0:
        lobby = request_json(page, f'/lobby/{page.locator("#roomId").input_value()}')
        if lobby.get('started') is True:
            page.evaluate('refreshLobbyState().catch(() => null)')
            return
        page.wait_for_timeout(250)
        deadline -= 250
    raise RuntimeError('lobby did not transition to started=true')


def wait_for_ws_state(page, predicate_js, timeout_ms=15000):
    page.wait_for_function(
        f"""() => {{
            const state = window.lastGameState || null;
            return !!({predicate_js});
        }}""",
        timeout=timeout_ms,
    )


def connect_and_wait_for_state(page, timeout_ms=15000):
    page.evaluate('connect()')
    wait_for_ws_state(page, 'state && state.players && state.players.length >= 2', timeout_ms=timeout_ms)


def wait_for_my_turn(page, timeout_ms=15000):
    wait_for_ws_state(
        page,
        "state && state.players && state.players.some(p => p.id === playerId && state.current_player === p.name)",
        timeout_ms=timeout_ms,
    )


def create_and_start(page, player_count):
    page.goto('http://127.0.0.1:8000/', wait_until='networkidle')
    create_payload = request_json(page, '/create', {})
    room = create_payload['game_id']
    host_id = create_payload['host_id']
    page.fill('#roomId', room)
    page.fill('#playerName', 'host')
    host_join_payload = request_json(page, '/join', {'game_id': room, 'name': 'host', 'player_id': host_id})
    host_join_id = host_join_payload.get('player_id') or host_join_payload.get('id') or ((host_join_payload.get('player') or {}).get('id'))
    if host_join_id != host_id:
        raise RuntimeError(f'host join did not preserve reserved host id: {host_join_payload}')
    page.evaluate(f'playerId = {json.dumps(host_id)}')
    page.click('text=進入作戰室')
    page.wait_for_timeout(300)
    choose_payload = request_json(page, '/choose-faction', {'game_id': room, 'player_id': host_id, 'faction_id': 'red_army', 'base_name': '北京'})
    if choose_payload.get('error'):
        raise RuntimeError(f'host choose faction failed: {choose_payload}')
    ready_payload = request_json(page, '/ready', {'game_id': room, 'player_id': host_id, 'ready': True})
    if ready_payload.get('error'):
        raise RuntimeError(f'host ready failed: {ready_payload}')
    wait_for_confirmed_faction(page, host_id)
    wait_for_ready_state(page, host_id, True)

    player_ids = [('host', host_id)]
    for i in range(2, player_count + 1):
        payload = request_json(page, '/join', {'game_id': room, 'name': f'guest{i}'})
        player_id = payload.get('player_id') or payload.get('id') or ((payload.get('player') or {}).get('id'))
        if not player_id:
            raise RuntimeError(f'join payload missing player id: {payload}')
        player_ids.append((f'guest{i}', player_id))

    return room, player_ids


def open_secondary_page(ctx, room, name, player_id, faction_button='臺灣', variant_button=None, base_button='臺北', ready=True):
    page = ctx.new_page()
    page.goto('http://127.0.0.1:8000/', wait_until='networkidle')
    page.fill('#roomId', room)
    page.fill('#playerName', name)
    page.evaluate(f'playerId = {json.dumps(player_id)}')
    page.click('text=進入作戰室')
    page.wait_for_timeout(500)
    faction_id = FACTION_ID_BY_SELECTION.get((faction_button, variant_button, base_button))
    if not faction_id:
        raise RuntimeError(f'unsupported faction mapping: {(faction_button, variant_button, base_button)}')
    choose_payload = request_json(page, '/choose-faction', {
        'game_id': room,
        'player_id': player_id,
        'faction_id': faction_id,
        'base_name': base_button,
    })
    if choose_payload.get('error'):
        raise RuntimeError(f'{name} choose faction failed: {choose_payload}')
    wait_for_confirmed_faction(page, player_id)
    if ready:
        ready_payload = request_json(page, '/ready', {'game_id': room, 'player_id': player_id, 'ready': True})
        if ready_payload.get('error'):
            raise RuntimeError(f'{name} ready failed: {ready_payload}')
        wait_for_ready_state(page, player_id, True)
    return page


def hand_cards(page):
    return page.locator('#hand .card').all_inner_texts()


def log_lines(page):
    return page.locator('#log > div').all_inner_texts()


def advance_to_action(page):
    wait_for_my_turn(page)
    page.wait_for_function(
        """() => {
            const btn = document.getElementById('advanceStepBtn');
            return !!(btn && !btn.disabled);
        }""",
        timeout=15000,
    )
    while True:
        state = page.evaluate('window.lastGameState') or {}
        if state.get('turn_phase') == 'action':
            return
        page.click('#advanceStepBtn')
        page.wait_for_function(
            """prevPhase => {
                const state = window.lastGameState || {};
                return !!state.turn_phase && state.turn_phase !== prevPhase;
            }""",
            arg=state.get('turn_phase'),
            timeout=15000,
        )
        wait_for_my_turn(page)
        page.wait_for_function(
            """() => {
                const btn = document.getElementById('advanceStepBtn');
                return !!(btn && !btn.disabled);
            }""",
            timeout=15000,
        )


def active_turn_page(primary_page, secondary_pages):
    primary_state = primary_page.evaluate('window.lastGameState') or {}
    primary_player = primary_state.get('current_player')
    me = next((p for p in (primary_state.get('players') or []) if p.get('id') == primary_page.evaluate('playerId')), None)
    if me and me.get('name') == primary_player:
        return primary_page
    for page in secondary_pages:
        state = page.evaluate('window.lastGameState') or {}
        current = state.get('current_player')
        me = next((p for p in (state.get('players') or []) if p.get('id') == page.evaluate('playerId')), None)
        if me and me.get('name') == current:
            return page
    raise RuntimeError('no page matches current_player in lastGameState')


def validate_visibility(player_count):
    with sync_playwright() as p:
        browser, ctx = create_context(p)
        host = ctx.new_page()
        room, players = create_and_start(host, player_count)

        others = []
        ready_configs = [
            ('guest2', players[1][1], '臺灣', '綠線', '臺北'),
            ('guest3', players[2][1], '維吾爾', '阿拉木圖', '阿拉木圖') if player_count >= 3 else None,
            ('guest4', players[3][1], '西藏', '達蘭薩拉', '達蘭薩拉') if player_count >= 4 else None,
        ]
        for config in ready_configs:
            if not config:
                continue
            name, pid, faction_button, variant_button, base_button = config
            others.append((name, open_secondary_page(ctx, room, name, pid, faction_button=faction_button, variant_button=variant_button, base_button=base_button, ready=True)))

        deadline = 10000
        while deadline > 0:
            lobby = request_json(host, f'/lobby/{room}')
            everyone_ready = len(lobby.get('players', [])) == player_count and len(lobby.get('factions', {})) == player_count and all(lobby.get('ready', {}).get(pid) is True for pid, _ in lobby.get('players', []))
            if everyone_ready:
                host.evaluate('refreshLobbyState().catch(() => null)')
                break
            host.wait_for_timeout(250)
            deadline -= 250
        if deadline <= 0:
            raise RuntimeError(f'lobby not fully ready before start: {request_json(host, f"/lobby/{room}")}')
        start_payload = request_json(host, '/start', {'game_id': room, 'player_id': players[0][1], 'market_mode': 'sample_53'})
        if start_payload.get('error'):
            raise RuntimeError(f'start failed: {start_payload}')
        connect_and_wait_for_state(host)
        host_hand = hand_cards(host)
        other_hands = {}
        for name, page in others:
            connect_and_wait_for_state(page)
            other_hands[name] = hand_cards(page)
        browser.close()
        return {
            'player_count': player_count,
            'host_hand': host_hand,
            'other_hands': other_hands,
        }


def validate_type_flow(card_type, card_name):
    with sync_playwright() as p:
        browser, ctx = create_context(p)
        page = ctx.new_page()
        room, players = create_and_start(page, 2)
        guest_page = open_secondary_page(ctx, room, 'guest2', players[1][1], faction_button='臺灣', variant_button='綠線', base_button='臺北', ready=True)

        deadline = 10000
        while deadline > 0:
            lobby = request_json(page, f'/lobby/{room}')
            everyone_ready = len(lobby.get('players', [])) == 2 and len(lobby.get('factions', {})) == 2 and all(lobby.get('ready', {}).get(pid) is True for pid, _ in lobby.get('players', []))
            if everyone_ready:
                page.evaluate('refreshLobbyState().catch(() => null)')
                break
            page.wait_for_timeout(250)
            deadline -= 250
        if deadline <= 0:
            raise RuntimeError(f'2p lobby not fully ready before start: {request_json(page, f"/lobby/{room}")}')
        start_payload = request_json(page, '/start', {'game_id': room, 'player_id': players[0][1], 'market_mode': 'sample_53'})
        if start_payload.get('error'):
            raise RuntimeError(f'start failed: {start_payload}')
        wait_for_lobby_started(page)
        connect_and_wait_for_state(page)
        connect_and_wait_for_state(guest_page)
        turn_page = active_turn_page(page, [guest_page])
        waiting_page = guest_page if turn_page is page else page

        displayed = hand_cards(turn_page)
        advance_to_action(turn_page)
        connect_and_wait_for_state(waiting_page)
        waiting_page.wait_for_timeout(400)
        after_phase = turn_page.evaluate('window.lastGameState.turn_phase')

        guest_before = waiting_page.evaluate('window.lastGameState')
        guest_logs_before = log_lines(waiting_page)
        guest_hand_before = hand_cards(waiting_page)
        guest_button_disabled = False
        if waiting_page.locator('#hand .card button').count() > 0:
            guest_button_disabled = bool(waiting_page.locator('#hand .card button').nth(0).evaluate('(btn) => btn.disabled'))
            if not guest_button_disabled:
                waiting_page.locator('#hand .card button').nth(0).click(force=True)
                waiting_page.wait_for_timeout(1200)
        guest_after = waiting_page.evaluate('window.lastGameState')
        guest_logs_after = log_lines(waiting_page)
        guest_hand_after = hand_cards(waiting_page)

        host_hand_before = hand_cards(turn_page)
        hud_before = turn_page.locator('#hud').inner_text() if turn_page.locator('#hud').count() else ''
        chosen_card = host_hand_before[0] if host_hand_before else None
        if turn_page.locator('#hand .card button').count() > 0:
            turn_page.locator('#hand .card button').nth(0).click()
            turn_page.wait_for_timeout(1500)
        host_hand_after = hand_cards(turn_page)
        host_logs_after = log_lines(turn_page)
        host_state_after = turn_page.evaluate('window.lastGameState')
        hud_after = turn_page.locator('#hud').inner_text() if turn_page.locator('#hud').count() else ''

        browser.close()
        return {
            'type': card_type,
            'representative_card': card_name,
            'displayed_before': displayed,
            'chosen_card': chosen_card,
            'phase_after_advance': after_phase,
            'guest_illegal_play_state_same': guest_before == guest_after,
            'guest_log_unchanged': guest_logs_before == guest_logs_after,
            'guest_button_disabled': guest_button_disabled,
            'guest_hand_before': guest_hand_before,
            'guest_hand_after': guest_hand_after,
            'host_hand_before': host_hand_before,
            'host_hand_after': host_hand_after,
            'host_logs_after': host_logs_after[:5],
            'hud_before': hud_before,
            'hud_after': hud_after,
            'host_state_after': host_state_after,
        }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        'visibility': [validate_visibility(2), validate_visibility(3), validate_visibility(4)],
        'type_flows': [],
    }
    for t in TYPE_ORDER:
        report['type_flows'].append(validate_type_flow(t, TYPE_CARD[t]))

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    md = []
    md.append('# CARD UI VALIDATION RESULTS')
    md.append('')
    md.append('日期：2026-05-03')
    md.append('')
    md.append('## 手牌可見性')
    for item in report['visibility']:
        md.append(f"### {item['player_count']} 人")
        md.append(f"- host hand: {item['host_hand']}")
        md.append(f"- other_hands: {item['other_hands']}")
        md.append('')
    md.append('## 類型代表卡 UI 流程')
    for item in report['type_flows']:
        md.append(f"### {item['type']} — {item['representative_card']}")
        md.append(f"- displayed_before: {item['displayed_before']}")
        md.append(f"- phase_after_advance: {item['phase_after_advance']}")
        md.append(f"- guest_illegal_play_state_same: {item['guest_illegal_play_state_same']}")
        md.append(f"- guest_log_unchanged: {item['guest_log_unchanged']}")
        md.append(f"- guest_button_disabled: {item['guest_button_disabled']}")
        md.append(f"- guest_hand_before -> after: {item['guest_hand_before']} -> {item['guest_hand_after']}")
        md.append(f"- host_hand_before -> after: {item['host_hand_before']} -> {item['host_hand_after']}")
        md.append(f"- host_logs_after: {item['host_logs_after']}")
        md.append(f"- HUD before -> after: {item['hud_before']} -> {item['hud_after']}")
        md.append('')
    OUT_MD.write_text('\n'.join(md), encoding='utf-8')
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == '__main__':
    main()
