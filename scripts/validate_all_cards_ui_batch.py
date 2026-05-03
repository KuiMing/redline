import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
CARDS = json.loads((BASE / 'data' / 'action_cards_structured.v1.1.json').read_text(encoding='utf-8'))['cards']


def create_and_start(page):
    create = page.evaluate("""async () => (await (await fetch('/create', {method:'POST'})).json())""")
    room = create['game_id']
    host_id = create['host_id']
    host_join = page.evaluate(f"""async () => (await (await fetch('/join', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{'game_id':'{room}','name':'host','player_id':'{host_id}'}})}})).json())""")
    guest_join = page.evaluate(f"""async () => (await (await fetch('/join', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{'game_id':'{room}','name':'guest'}})}})).json())""")
    page.evaluate(f"""async () => (await (await fetch('/start', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{'game_id':'{room}','player_id':'{host_id}'}})}})).json())""")
    return room, host_join['player_id'], guest_join['player_id']


def connect_page(page, room, pid):
    page.evaluate(f"gameId={json.dumps(room)}; playerId={json.dumps(pid)}; connect();")
    page.wait_for_timeout(1500)


def run_batch(start_idx, end_idx):
    batch_cards = CARDS[start_idx:end_idx]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 960})
        page = ctx.new_page()
        page.goto('http://localhost:8000/', wait_until='networkidle')
        room, host_id, guest_id = create_and_start(page)
        connect_page(page, room, host_id)

        results = []
        for card in batch_cards:
            print(f"running {card['name']}", flush=True)
            page.evaluate(f"""async () => await fetch('/test/setup-card-scenario', {{
              method:'POST',
              headers:{{'Content-Type':'application/json'}},
              body: JSON.stringify({{'game_id':{json.dumps(room)},'player_id':{json.dumps(host_id)},'card_name':{json.dumps(card['name'])}}})
            }})""")
            page.wait_for_timeout(300)
            page.reload(wait_until='networkidle')
            connect_page(page, room, host_id)
            page.wait_for_timeout(600)

            hand_before = page.locator('#hand .card').all_inner_texts()
            hud_before = page.locator('#hud').inner_text() if page.locator('#hud').count() else ''
            log_before = page.locator('#log > div').all_inner_texts()
            purchase_before = page.locator('#purchase .card').all_inner_texts()
            state_before = page.evaluate('window.lastGameState')

            if page.locator('#hand .card').count() > 0:
                for i in range(page.locator('#hand .card').count()):
                    txt = page.locator('#hand .card').nth(i).inner_text()
                    if txt == card['name']:
                        page.locator('#hand .card').nth(i).click()
                        break
                page.wait_for_timeout(1000)

            hand_after = page.locator('#hand .card').all_inner_texts()
            hud_after = page.locator('#hud').inner_text() if page.locator('#hud').count() else ''
            log_after = page.locator('#log > div').all_inner_texts()
            purchase_after = page.locator('#purchase .card').all_inner_texts()
            state_after = page.evaluate('window.lastGameState')

            me_before = next((pl for pl in state_before['players'] if pl['id'] == host_id), None)
            me_after = next((pl for pl in state_after['players'] if pl['id'] == host_id), None)
            opponents_before = {pl['name']: pl for pl in state_before['players'] if pl['id'] != host_id}
            opponents_after = {pl['name']: pl for pl in state_after['players'] if pl['id'] != host_id}

            results.append({
                'card': card['name'],
                'type': card['type'],
                'effects': [e['type'] for e in card.get('effect', [])],
                'hand_before': hand_before,
                'hand_after': hand_after,
                'hud_changed': hud_before != hud_after,
                'log_changed': log_before != log_after,
                'purchase_changed': purchase_before != purchase_after,
                'error': state_after.get('error') if state_after else None,
                'resources_before': me_before['resources'] if me_before else None,
                'resources_after': me_after['resources'] if me_after else None,
                'moves_before': me_before['moves_left'] if me_before else None,
                'moves_after': me_after['moves_left'] if me_after else None,
                'orgs_before': me_before['orgs'] if me_before else None,
                'orgs_after': me_after['orgs'] if me_after else None,
                'opponents_before': {k: {'hand': len(v['hand']), 'orgs': v['orgs']} for k,v in opponents_before.items()},
                'opponents_after': {k: {'hand': len(v['hand']), 'orgs': v['orgs']} for k,v in opponents_after.items()},
            })
        browser.close()
        return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    args = parser.parse_args()
    results = run_batch(args.start, args.end)
    out = BASE / f"CARD_UI_FULL_VALIDATION_BATCH_{args.start}_{args.end}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(out)

if __name__ == '__main__':
    main()
