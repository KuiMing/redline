import json
import sys
import urllib.request
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.game import Game
from server.cards import Card

BASE = 'http://127.0.0.1:8000'


def post(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req).read().decode('utf-8'))


def validate_engine():
    g = Game([('p1', 'A'), ('p2', 'B')])
    p = g.players[0]
    p.faction_id = 'zhuang'
    p.hand = [Card('墊牌', 'money', {'money': 1})]
    p.deck.draw_pile = [Card('奇數牌', 'money', {'money': 1})]
    g._top_card_cost_total = lambda card: 1
    result = g._activated_faction_action(p, '民族祭儀', guess='odd')
    return result, dict(p.resources)


def validate_ui():
    created = post('/create', {})
    game_id = created['game_id']
    host_id = created['host_id']
    guest_id = str(uuid.uuid4())
    post('/join', {'game_id': game_id, 'name': 'guest', 'player_id': guest_id})
    post('/choose-faction', {'game_id': game_id, 'player_id': host_id, 'faction_id': 'zhuang', 'base_name': '南寧'})
    post('/choose-faction', {'game_id': game_id, 'player_id': guest_id, 'faction_id': 'red_army', 'base_name': '北京'})
    post('/start', {'game_id': game_id, 'player_id': host_id})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        page.goto(BASE + '/', wait_until='networkidle')
        page.fill('#roomId', game_id)
        page.fill('#playerName', 'host')
        page.evaluate(f"playerId={json.dumps(host_id)}")
        page.click('text=JOIN OPERATION')
        page.evaluate(f"gameId={json.dumps(game_id)}; playerId={json.dumps(host_id)}; connect();")
        page.wait_for_timeout(1200)
        page.click('text=ADVANCE')
        page.wait_for_timeout(700)
        visible = page.locator('#factionActionPanel').is_visible()
        page.click('text=發動 民族祭儀')
        page.wait_for_timeout(300)
        modal_visible = page.locator('#factionActionModal').is_visible()
        page.screenshot(path='ethnic_ritual_guess_modal_ui.png', full_page=True)
        browser.close()
    return visible, modal_visible


def main():
    engine_result, resources = validate_engine()
    panel_visible, modal_visible = validate_ui()
    payload = {
        'summary': {
            'total': 3,
            'passed': int(engine_result.get('success') is True) + int(resources.get('money') == 2 and resources.get('propaganda') == 2) + int(panel_visible and modal_visible),
            'failed': 3 - (int(engine_result.get('success') is True) + int(resources.get('money') == 2 and resources.get('propaganda') == 2) + int(panel_visible and modal_visible)),
        },
        'engine_result': engine_result,
        'resources': resources,
        'panel_visible': panel_visible,
        'modal_visible': modal_visible,
    }
    Path('ETHNIC_RITUAL_UI_AND_ENGINE_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path('ETHNIC_RITUAL_UI_AND_ENGINE_VALIDATION.md').write_text(
        '# ETHNIC RITUAL UI AND ENGINE VALIDATION\n\n'
        f"- engine_result: {json.dumps(engine_result, ensure_ascii=False)}\n"
        f"- resources: {resources}\n"
        f"- panel_visible: {panel_visible}\n"
        f"- modal_visible: {modal_visible}\n",
        encoding='utf-8'
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == '__main__':
    main()
