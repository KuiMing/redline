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

from validate_ui_card_flows import create_context, create_and_start, open_secondary_page, request_json, connect_and_wait_for_state


def main():
    with sync_playwright() as p:
        browser, ctx = create_context(p)
        page = ctx.new_page()
        room, players = create_and_start(page, 2)
        guest_page = open_secondary_page(ctx, room, 'guest2', players[1][1], faction_button='臺灣', variant_button='綠線', base_button='臺北', ready=True)
        start_payload = request_json(page, '/start', {'game_id': room, 'player_id': players[0][1], 'market_mode': 'sample_53'})
        print('start_payload=', json.dumps(start_payload, ensure_ascii=False))
        connect_and_wait_for_state(page)
        connect_and_wait_for_state(guest_page)
        print('host_state=', json.dumps(page.evaluate('window.lastGameState'), ensure_ascii=False, indent=2))
        print('guest_state=', json.dumps(guest_page.evaluate('window.lastGameState'), ensure_ascii=False, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
