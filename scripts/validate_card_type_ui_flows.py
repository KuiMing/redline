import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
RECORD_DIR = BASE / 'docs' / 'records' / 'card-ui'
CARDS = json.loads((BASE / 'data' / 'action_cards_structured.v1.1.json').read_text(encoding='utf-8'))['cards']

TYPE_ORDER = [
    'propaganda', 'money', 'disruption', 'command', 'transport',
    'organization', 'purge', 'propaganda_special', 'spy', 'armed'
]
TYPE_CARD = {t: next(card['name'] for card in CARDS if card['type'] == t) for t in TYPE_ORDER}


def create_and_start(page, player_count):
    create = page.evaluate("""async () => (await (await fetch('/create', {method:'POST'})).json())""")
    room = create['game_id']
    host_id = create['host_id']
    host_join = page.evaluate(f"""async () => (await (await fetch('/join', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{'game_id':'{room}','name':'host','player_id':'{host_id}'}})}})).json())""")
    players = [('host', host_join['player_id'])]
    for i in range(2, player_count + 1):
        joined = page.evaluate(f"""async () => (await (await fetch('/join', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{'game_id':'{room}','name':'guest{i}'}})}})).json())""")
        players.append((f'guest{i}', joined['player_id']))
    start = page.evaluate(f"""async () => (await (await fetch('/start', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{'game_id':'{room}','player_id':'{host_id}'}})}})).json())""")
    return room, players, start


def connect_page(page, room, pid):
    page.evaluate(f"gameId={json.dumps(room)}; playerId={json.dumps(pid)}; connect();")
    page.wait_for_timeout(1800)


def set_hand(page, room, pid, cards):
    page.evaluate(f"""async () => await fetch('/test/set-hand', {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{'game_id':{json.dumps(room)},'player_id':{json.dumps(pid)},'cards':{json.dumps(cards)},'turn_phase':'action'}})
    }})""")
    page.wait_for_timeout(300)
    page.reload(wait_until='networkidle')
    connect_page(page, room, pid)
    page.wait_for_timeout(1000)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={'width': 1440, 'height': 960})
    page = ctx.new_page()
    page.goto('http://localhost:8000/', wait_until='networkidle')
    room, players, start = create_and_start(page, 2)
    host_id = players[0][1]
    connect_page(page, room, host_id)

    results = []
    for card_type in TYPE_ORDER:
        card_name = TYPE_CARD[card_type]
        set_hand(page, room, host_id, [card_name])
        hand_before = page.locator('#hand .card').all_inner_texts()
        hud_before = page.locator('#hud').inner_text() if page.locator('#hud').count() else ''
        log_before = page.locator('#log > div').all_inner_texts()
        if page.locator('#hand .card').count() > 0:
            page.locator('#hand .card').first.click()
            page.wait_for_timeout(1500)
        hand_after = page.locator('#hand .card').all_inner_texts()
        hud_after = page.locator('#hud').inner_text() if page.locator('#hud').count() else ''
        log_after = page.locator('#log > div').all_inner_texts()
        state_after = page.evaluate('window.lastGameState')
        results.append({
            'type': card_type,
            'card': card_name,
            'hand_before': hand_before,
            'hand_after': hand_after,
            'hud_changed': hud_before != hud_after,
            'log_changed': log_before != log_after,
            'error': state_after.get('error') if state_after else None,
            'resources': state_after['players'][0]['resources'] if state_after else None,
            'moves_left': state_after['players'][0]['moves_left'] if state_after else None,
        })

    browser.close()

RECORD_DIR.mkdir(parents=True, exist_ok=True)
out_json = RECORD_DIR / 'CARD_UI_TYPE_VALIDATION.json'
out_md = RECORD_DIR / 'CARD_UI_TYPE_VALIDATION.md'
out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['# CARD UI TYPE VALIDATION', '', '日期：2026-05-03', '']
for r in results:
    lines.append(f"## {r['type']} — {r['card']}")
    lines.append(f"- hand_before: {r['hand_before']}")
    lines.append(f"- hand_after: {r['hand_after']}")
    lines.append(f"- hud_changed: {r['hud_changed']}")
    lines.append(f"- log_changed: {r['log_changed']}")
    lines.append(f"- error: {r['error']}")
    lines.append(f"- resources: {r['resources']}")
    lines.append(f"- moves_left: {r['moves_left']}")
    lines.append('')
out_md.write_text('\n'.join(lines), encoding='utf-8')
print(out_json)
print(out_md)
