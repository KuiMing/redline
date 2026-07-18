"""自動 playtest：紅軍 vs 臺灣綠線，玩滿 20 回合（或提前分出勝負），每個動作截圖。

策略（簡單但能覆蓋主要流程）：
- ACTION 階段：第 1 張手牌用「行動」打出（觸發各種效果流程），其餘用「資源」（奧援卡用「棄置」）；
  出現待選擇一律選第一個可行選項（modal 卡片/選項/城鎮；地圖情境用 resolve_choice fallback）。
- END 階段：買第一張買得起的卡，然後結束回合；回合結束前的置頂提示選「不使用」。
- 全程每個動作後截圖到 playthrough_screens/，附 JSONL 行動紀錄；卡住（連續 N 次無進展）就
  記錄 issue 並強制 advance，再不行就中止並保留現場截圖。

可重跑指令：python3 scripts/auto_playthrough_20260718.py
"""
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOT_DIR = ROOT / 'playthrough_screens'
BASE_URL = 'http://127.0.0.1:8000'
LOG_PATH = SHOT_DIR / 'playthrough_log.jsonl'
MAX_TURNS = 20

seq = 0
log_lines = []


def log(entry):
    entry['t'] = time.strftime('%H:%M:%S')
    log_lines.append(entry)
    LOG_PATH.write_text('\n'.join(json.dumps(e, ensure_ascii=False) for e in log_lines) + '\n', encoding='utf-8')


def shot(page, label):
    global seq
    seq += 1
    name = f"{seq:03d}_{label}.png"
    try:
        page.screenshot(path=str(SHOT_DIR / name))
    except Exception as err:
        log({'event': 'screenshot_failed', 'label': label, 'error': str(err)})
    return name


def request_json(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL + path, data=data, headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))


def state_of(page):
    return page.evaluate('window.lastGameState') or {}


def my_name(page):
    return page.evaluate("(() => { const s = window.lastGameState; const me = (s?.players||[]).find(p => p.id === playerId); return me?.name; })()")


def pending_choice(page):
    return page.evaluate("window.lastGameState?.pending_choice || null")


def close_faction_modal(page):
    page.evaluate("() => { const b = document.getElementById('closeFactionActionModal'); if (b && b.offsetParent) b.click(); }")


def try_resolve_pending(page, who):
    """處理一個 pending choice：優先點 modal 裡第一個可點項，否則用 resolve_choice(0)。回傳是否處理了。"""
    pc = pending_choice(page)
    if not pc:
        return False
    me = page.evaluate('playerId')
    if pc.get('player_id') and pc.get('player_id') != me:
        return False  # 不是這個玩家的選擇
    key = pc.get('choice_key') or pc.get('type')
    if pc.get('type') == 'multi_card_choice':
        # 多選型：直接送索引陣列（取前 count 張）
        count = pc.get('count') or pc.get('min_count') or 1
        count = max(1, min(int(count), len(pc.get('cards') or []) or 1))
        page.evaluate("(idx) => sendAction('resolve_choice', { index: idx })", list(range(count)))
        clicked = f'resolve_choice([0..{count-1}])'
    else:
        # modal 內的可點項（卡片選擇/選項選擇/城鎮選擇都渲染在 #choiceModalCards）
        clicked = page.evaluate(
            """() => {
              const cards = document.querySelectorAll('#choiceModalCards button:not([disabled])');
              if (cards.length) { cards[0].click(); return 'modal-first-item'; }
              return null;
            }"""
        )
        if not clicked:
            # 地圖情境或未渲染 modal：直接 resolve index 0
            page.evaluate("() => sendAction('resolve_choice', { index: 0 })")
            clicked = 'resolve_choice(0)'
    page.wait_for_timeout(700)
    shot(page, f"{who}_resolve_{key}")
    log({'event': 'resolve_choice', 'who': who, 'choice_key': key, 'via': clicked})
    return True


def drain_pending(page, who, limit=12):
    """反覆處理 pending choice 直到清空（上限防呆）。"""
    for _ in range(limit):
        if not try_resolve_pending(page, who):
            return True
    log({'event': 'issue', 'who': who, 'note': f'pending choice 連續 {limit} 次未清空', 'pending': pending_choice(page)})
    return False


def is_my_turn(page):
    return page.evaluate("(() => { const s = window.lastGameState; if (!s) return false; const me = (s.players||[]).find(p => p.id === playerId); return me && s.current_player === me.name; })()")


def phase(page):
    return str(state_of(page).get('turn_phase') or '').lower()


def hand_buttons(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('#hand .hand-card')].map((card, i) => ({
          i,
          name: card.querySelector('.purchase-card-title')?.textContent || '',
          buttons: [...card.querySelectorAll('.hand-card-action-btn')].map(b => ({text: b.textContent.trim(), mode: b.dataset.cardMode, disabled: b.disabled})),
        }))"""
    )


def click_hand_button(page, card_index, mode):
    return page.evaluate(
        """([idx, mode]) => {
          const cards = document.querySelectorAll('#hand .hand-card');
          const card = cards[idx];
          if (!card) return false;
          const btn = [...card.querySelectorAll('.hand-card-action-btn')].find(b => b.dataset.cardMode === mode && !b.disabled);
          if (!btn) return false;
          btn.click();
          return true;
        }""",
        [card_index, mode],
    )


def play_action_phase(page, who, turn):
    """行動階段：第 1 張手牌打「行動」，其餘打「資源／棄置」。"""
    played_action = False
    for round_i in range(10):  # 上限防呆
        if pending_choice(page):
            drain_pending(page, who)
            continue
        cards = hand_buttons(page)
        if not cards:
            break
        target = None
        mode = None
        if not played_action:
            for c in cards:
                if any(b['mode'] == 'action' and not b['disabled'] for b in c['buttons']):
                    target, mode = c, 'action'
                    break
        if target is None:
            for c in cards:
                if any(b['mode'] == 'resource' and not b['disabled'] for b in c['buttons']):
                    target, mode = c, 'resource'
                    break
        if target is None:
            break  # 沒有可打的牌了
        ok = click_hand_button(page, target['i'], mode)
        if not ok:
            break
        page.wait_for_timeout(700)
        label = f"{who}_t{turn}_play_{target['name']}_{mode}"
        shot(page, label)
        log({'event': 'play_card', 'who': who, 'turn': turn, 'card': target['name'], 'mode': mode})
        if mode == 'action':
            played_action = True
        drain_pending(page, who)


def buy_phase(page, who, turn):
    if pending_choice(page):
        drain_pending(page, who)
    bought = page.evaluate(
        """() => {
          const btns = [...document.querySelectorAll('.purchase-card-buy-btn')].filter(b => !b.disabled);
          if (!btns.length) return null;
          const card = btns[0].closest('.card');
          const name = card?.querySelector('.purchase-card-title')?.textContent || '?';
          btns[0].click();
          return name;
        }"""
    )
    page.wait_for_timeout(700)
    if bought:
        shot(page, f"{who}_t{turn}_buy_{bought}")
        log({'event': 'buy_card', 'who': who, 'turn': turn, 'card': bought})
    drain_pending(page, who)


def advance(page, who, turn, note):
    if pending_choice(page):
        drain_pending(page, who)
    enabled = page.evaluate("() => { const b = document.getElementById('advanceStepBtn'); return b && !b.disabled; }")
    if enabled:
        page.click('#advanceStepBtn')
    else:
        page.evaluate("() => sendAction('advance', {})")
        log({'event': 'issue', 'who': who, 'turn': turn, 'note': f'advance 按鈕 disabled，用 sendAction fallback（{note}）'})
    page.wait_for_timeout(800)
    shot(page, f"{who}_t{turn}_advance_{note}")
    log({'event': 'advance', 'who': who, 'turn': turn, 'note': note})
    drain_pending(page, who)


def main():
    SHOT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
        host = ctx.new_page()
        ally = ctx.new_page()

        host.goto(BASE_URL + '/', wait_until='networkidle')
        ally.goto(BASE_URL + '/', wait_until='networkidle')
        shot(host, 'setup_lobby')

        host.fill('#playerName', 'RED')
        host.click('#createRoomBtn')
        host.wait_for_function("() => document.querySelector('#roomId')?.value?.length > 10", timeout=10000)
        game_id = host.locator('#roomId').input_value()
        host_pid = host.evaluate('playerId')
        ally.fill('#roomId', game_id)
        ally.fill('#playerName', 'GREEN')
        ally.click('#joinRoomBtn')
        ally.wait_for_function("() => typeof playerId !== 'undefined' && playerId", timeout=10000)
        ally_pid = ally.evaluate('playerId')

        request_json('/choose-faction', {'game_id': game_id, 'player_id': host_pid, 'faction_id': 'red_army'})
        request_json('/choose-faction', {'game_id': game_id, 'player_id': ally_pid, 'faction_id': 'taiwan_green', 'base_name': '臺北'})
        host.click('#toggleReadyBtn')
        ally.click('#toggleReadyBtn')
        host.wait_for_timeout(400)
        shot(host, 'setup_ready')
        host.click('#startGameBtn')
        host.wait_for_selector('#gameShell', state='visible', timeout=10000)
        ally.wait_for_selector('#gameShell', state='visible', timeout=10000)
        host.wait_for_timeout(1200)
        close_faction_modal(host)
        close_faction_modal(ally)
        shot(host, 'game_start_host_view')
        shot(ally, 'game_start_ally_view')
        log({'event': 'game_start', 'game_id': game_id})

        host_name = my_name(host)
        ally_name = my_name(ally)
        pages = {host_name: host, ally_name: ally}
        log({'event': 'player_names', 'host': host_name, 'ally': ally_name})
        stall = 0
        last_sig = None
        start_time = time.time()

        while True:
            if time.time() - start_time > 25 * 60:
                log({'event': 'issue', 'note': '超過 25 分鐘上限，中止'})
                break
            st = state_of(host) or state_of(ally)
            turn = st.get('turn') or 0
            winner = st.get('winner')
            if winner:
                shot(host, f"game_over_winner_{winner}")
                shot(ally, f"game_over_ally_view")
                log({'event': 'game_over', 'winner': winner, 'turn': turn})
                break
            if turn > MAX_TURNS:
                shot(host, 'reached_turn_limit')
                log({'event': 'turn_limit_reached', 'turn': turn})
                break

            current = st.get('current_player')
            page = pages.get(current)
            if page is None:
                log({'event': 'issue', 'note': f'未知 current_player: {current}'})
                break
            who = current

            # 停滯偵測：狀態簽名沒變化就計數
            sig = (turn, current, phase(page), len((state_of(page).get('players') or [{}])[0].get('hand', [])), json.dumps(pending_choice(page) is not None))
            if sig == last_sig:
                stall += 1
            else:
                stall = 0
                last_sig = sig
            if stall >= 4:
                shot(page, f"{who}_t{turn}_STALLED")
                log({'event': 'issue', 'who': who, 'turn': turn, 'note': '連續 4 輪無進展，強制 advance', 'phase': phase(page), 'pending': pending_choice(page)})
                page.evaluate("() => sendAction('advance', {})")
                page.wait_for_timeout(800)
                if stall >= 8:
                    log({'event': 'abort', 'note': '強制 advance 仍無進展，中止'})
                    break
                continue

            # 別的玩家頁面上可能有屬於他的 pending（例如被迫棄牌）
            for other_name, other_page in pages.items():
                if other_name != who:
                    try_resolve_pending(other_page, other_name)

            ph = phase(page)
            if pending_choice(page):
                drain_pending(page, who)
                continue
            if ph == 'action':
                play_action_phase(page, who, turn)
                advance(page, who, turn, 'to_end')
            elif ph == 'end':
                buy_phase(page, who, turn)
                advance(page, who, turn, 'end_turn')
            else:
                advance(page, who, turn, f'phase_{ph}')

        final = state_of(host)
        log({'event': 'final_state', 'turn': final.get('turn'), 'winner': final.get('winner'),
             'players': [{'name': p.get('name'), 'orgs': sum((p.get('orgs') or {}).values()),
                          'money': (p.get('resources') or {}).get('money'), 'propaganda': (p.get('resources') or {}).get('propaganda')}
                         for p in (final.get('players') or [])]})
        browser.close()
    print(json.dumps({'screenshots': seq, 'log': str(LOG_PATH)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
