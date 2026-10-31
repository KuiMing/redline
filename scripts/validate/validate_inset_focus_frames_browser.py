#!/usr/bin/env python3
"""黃色焦點／選取框內縮幾何驗證（Browser／Playwright Chromium）。

焦點一律是 synthetic：直接在目標元素加上 controller_ui.js 使用的 `.rl-pad-focus` class（**不是實體 Joy-Con**，
也不經 bridge）。驗證的是 CSS 幾何：黃框／選取框只畫在卡面或目標元素自身 rect 內、不外擴光暈、
不框住來源標籤、不改尺寸（無布局位移）、不被 Modal 捲動容器或 viewport 裁切。

需要 ENABLE_TEST_ROUTES=true 的獨立伺服器（預設 http://127.0.0.1:8201，可用 REDLINE_BASE_URL 覆寫）。
加 `--serve` 時由本程式在同一行程內啟動 server.main:app（127.0.0.1:8201、ENABLE_TEST_ROUTES=true），結束即停止。
截圖與 JSON 報告寫到 REDLINE_EVIDENCE_DIR（預設 /tmp/redline-yellow-frame-evidence）。
"""
from __future__ import annotations

import base64
import contextlib
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get('REDLINE_BASE_URL', 'http://127.0.0.1:8201').rstrip('/')
OUT = Path(os.environ.get('REDLINE_EVIDENCE_DIR', '/tmp/redline-yellow-frame-evidence'))
ROOT = Path(__file__).resolve().parent.parent.parent


@contextlib.contextmanager
def serve_8201():
    os.environ['ENABLE_TEST_ROUTES'] = 'true'
    sys.path.insert(0, str(ROOT))
    import uvicorn
    from server.main import app
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8201, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError('8201 server did not start (port in use?)')
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=10)

# 量測工具：注入頁面一次。frameOf(el) 回傳元素自身焦點框（outline／box-shadow）的外擴量；
# cardFrame(btn) 回傳 Modal 卡牌按鈕的卡面 ::after 框與來源標籤幾何。
HELPERS_JS = r"""() => {
  if (window.__ff) return;
  const box = r => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height });
  const splitShadows = s => {
    if (!s || s === 'none') return [];
    const out = []; let depth = 0, cur = '';
    for (const ch of s) {
      if (ch === '(') depth++;
      if (ch === ')') depth--;
      if (ch === ',' && depth === 0) { out.push(cur.trim()); cur = ''; } else cur += ch;
    }
    if (cur.trim()) out.push(cur.trim());
    return out;
  };
  const outerShadows = s => splitShadows(s).filter(x => !/\binset\b/.test(x));
  const outlineOut = cs => {
    if (cs.outlineStyle === 'none') return 0;
    const w = parseFloat(cs.outlineWidth) || 0;
    return w > 0 ? Math.max(0, w + (parseFloat(cs.outlineOffset) || 0)) : 0;
  };
  const inside = (a, b, tol = 0.5) => a.left >= b.left - tol && a.top >= b.top - tol && a.right <= b.right + tol && a.bottom <= b.bottom + tol;
  const intersects = (a, b) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;
  // 元素 rect 是否在每個 overflow 非 visible 的祖先可視區與 viewport 內（框在元素內，元素沒被裁＝框沒被裁）。
  const clipCheck = el => {
    const r = box(el.getBoundingClientRect());
    const clips = [];
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (/(auto|scroll|hidden|clip)/.test(cs.overflowX + cs.overflowY)) {
        const pr = p.getBoundingClientRect();
        const c = { left: pr.left + p.clientLeft, top: pr.top + p.clientTop };
        c.right = c.left + p.clientWidth; c.bottom = c.top + p.clientHeight;
        clips.push({ id: p.id || p.className, ok: inside(r, c) });
      }
    }
    const vp = { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
    return { clips, inViewport: inside(r, vp), allOk: clips.every(c => c.ok) && inside(r, vp) };
  };
  const siblingRects = el => [...(el.parentElement?.children || [])].filter(n => n !== el).map(n => box(n.getBoundingClientRect()));
  window.__ff = { box, splitShadows, outerShadows, outlineOut, inside, intersects, clipCheck, siblingRects };

  window.__ff.clearFocus = () => document.querySelectorAll('.rl-pad-focus').forEach(n => n.classList.remove('rl-pad-focus'));

  // 通用元素：加 focus class 前後比較 rect（布局位移）、相鄰元素 rect、外擴量、裁切。
  window.__ff.frameOf = el => {
    window.__ff.clearFocus();
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    const plain = box(el.getBoundingClientRect());
    const sibsPlain = siblingRects(el);
    el.classList.add('rl-pad-focus');
    const cs = getComputedStyle(el);
    const focused = box(el.getBoundingClientRect());
    const sibsFocused = siblingRects(el);
    const res = {
      tag: el.tagName.toLowerCase(), id: el.id, cls: el.className, text: (el.textContent || el.value || '').trim().slice(0, 30),
      outlineStyle: cs.outlineStyle, outlineWidth: parseFloat(cs.outlineWidth), outlineOffset: parseFloat(cs.outlineOffset),
      outlineColor: cs.outlineColor, boxShadow: cs.boxShadow, position: cs.position,
      outlineOut: outlineOut(cs), outerShadows: outerShadows(cs.boxShadow),
      rect: focused, noShift: JSON.stringify(plain) === JSON.stringify(focused) && JSON.stringify(sibsPlain) === JSON.stringify(sibsFocused),
      neighborOverlap: sibsFocused.some(s => s.width > 0 && intersects(s, focused)),
      clip: clipCheck(el),
    };
    res.ok = res.outlineOut === 0 && res.outerShadows.length === 0 && res.noShift && res.clip.allOk
      && res.outlineStyle === 'solid' && res.outlineWidth === 3 && res.outlineOffset === -3;
    return res;
  };

  // Modal 卡牌按鈕：框必須在 :scope > .card-face 的 ::after（inset:0），按鈕本身無 outline／box-shadow，
  // 來源標籤 rect 與卡面 rect 不相交，卡面在按鈕內、在 grid 可視範圍與 viewport 內。
  window.__ff.cardFrame = btn => {
    const face = btn.querySelector(':scope > .card-face');
    const label = btn.querySelector(':scope > .choice-card-zone-label');
    const bcs = getComputedStyle(btn);
    const after = getComputedStyle(face, '::after');
    const faceRect = box(face.getBoundingClientRect());
    const btnRect = box(btn.getBoundingClientRect());
    return {
      focus: btn.classList.contains('rl-pad-focus'), selected: btn.classList.contains('selected'),
      btnOutlineStyle: bcs.outlineStyle, btnOutlineOut: outlineOut(bcs), btnShadow: bcs.boxShadow, btnTransform: bcs.transform,
      faceRect, btnRect, labelRect: label ? box(label.getBoundingClientRect()) : null, labelText: label ? label.textContent.trim() : null,
      afterContent: after.content, afterPosition: after.position,
      afterInset: [after.top, after.right, after.bottom, after.left],
      afterBorderWidth: after.borderTopWidth, afterBorderStyle: after.borderTopStyle, afterBorderColor: after.borderTopColor,
      afterShadow: after.boxShadow, afterOuterShadows: outerShadows(after.boxShadow),
      faceInBtn: inside(faceRect, btnRect),
      labelOutsideFace: label ? !intersects(box(label.getBoundingClientRect()), faceRect) : true,
      clip: clipCheck(face),
    };
  };
}"""

# 在截圖上取樣：卡面四邊內 1px 應是黃色；卡面上緣外 3px（卡面與來源標籤之間的 8px 間隙）、按鈕左側外 3px 不可是黃色。
PIXELS_JS = r"""async ([png, f]) => {
  const img = new Image(); img.src = 'data:image/png;base64,' + png; await img.decode();
  const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
  const g = c.getContext('2d'); g.drawImage(img, 0, 0);
  const at = (x, y) => Array.from(g.getImageData(Math.floor(x), Math.floor(y), 1, 1).data.slice(0, 3));
  const cx = (f.left + f.right) / 2, cy = (f.top + f.bottom) / 2;
  return {
    inTop: at(cx, f.top + 1), inBottom: at(cx, f.bottom - 2), inLeft: at(f.left + 1, cy), inRight: at(f.right - 2, cy),
    outTop: at(cx, f.top - 3), outLeft: at(f.left - 3, cy), outRight: at(f.right + 2, cy), outBottom: at(cx, f.bottom + 2),
  };
}"""

YELLOW = lambda p: p[0] >= 200 and p[1] >= 170 and p[2] <= 140  # noqa: E731


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(BASE_URL + path, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))


checks: list[dict] = []


def record(name: str, ok: bool, detail=None) -> None:
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS ' if ok else 'FAIL ') + name)


def card_ok(m: dict, *, focus: bool, selected: bool) -> bool:
    base = (m['btnOutlineOut'] == 0 and m['btnShadow'] == 'none' and m['faceInBtn'] and m['labelOutsideFace']
            and m['clip']['allOk'] and m['afterPosition'] == 'absolute' and m['afterInset'] == ['0px'] * 4
            and not m['afterOuterShadows'])
    if focus:
        base = base and m['afterBorderWidth'] == '3px' and m['afterBorderStyle'] == 'solid' and m['afterBorderColor'] == 'rgb(255, 225, 77)'
        has_blue = 'rgba(96, 165, 250' in m['afterShadow']
        base = base and (has_blue if selected else not has_blue)
    elif selected:
        base = base and m['afterBorderWidth'] == '0px' and 'rgba(96, 165, 250' in m['afterShadow']
    return base


def pixels_ok(page, face: dict) -> tuple[bool, dict]:
    png = page.screenshot()
    px = page.evaluate(PIXELS_JS, [base64.b64encode(png).decode(), face])
    ok = all(YELLOW(px[k]) for k in ('inTop', 'inBottom', 'inLeft', 'inRight')) and not any(
        YELLOW(px[k]) for k in ('outTop', 'outLeft', 'outRight', 'outBottom'))
    return ok, px


def open_game(browser, url: str):
    ctx = browser.new_context(viewport={'width': 1280, 'height': 720}, device_scale_factor=1)
    page = ctx.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE_URL + url, wait_until='domcontentloaded')
    page.locator('#gameShell').wait_for(state='visible', timeout=15000)
    page.wait_for_function('() => !!window.lastGameState', timeout=15000)
    page.wait_for_timeout(400)
    page.evaluate("""() => {
      if (typeof closeEventReveal === 'function') closeEventReveal();
      if (typeof minimizeEraAchievement === 'function') minimizeEraAchievement();
      const er = document.getElementById('eventRevealModal'); if (er) er.style.display = 'none';
    }""")
    page.evaluate(HELPERS_JS)
    return ctx, page, errors


def wait_choice_cards(page, multi: bool):
    sel = '#choiceModalCards .choice-card-btn' + ('.choice-card-btn-multi' if multi else ':not(.choice-card-btn-multi)')
    page.wait_for_selector('#choiceModal', state='visible', timeout=10000)
    page.wait_for_selector(sel, state='visible', timeout=10000)
    return sel


def check_single(page, name: str, sel: str, expect_label: bool):
    for which in ('first', 'last'):
        idx = 0 if which == 'first' else page.locator(sel).count() - 1
        m = page.evaluate(f"""() => {{ __ff.clearFocus(); const b = document.querySelectorAll({json.dumps(sel)})[{idx}];
            b.scrollIntoView({{ block: 'nearest' }}); b.classList.add('rl-pad-focus'); return __ff.cardFrame(b); }}""")
        page.wait_for_timeout(80)
        px_ok, px = pixels_ok(page, m['faceRect'])
        label_ok = (m['labelRect'] is not None) == expect_label
        record(f'{name}_{which}_focus_inside_card_face', card_ok(m, focus=True, selected=False) and px_ok and label_ok,
               {'measure': m, 'pixels': px})
        page.screenshot(path=str(OUT / f'{name}_{which}_focus.png'))


def check_multi(page, name: str, sel: str):
    # 用既有 onclick 選第一張（真的切換 selected），再對它加焦點：selected＋focus 同時存在。
    page.locator(sel).first.click()
    # 滑鼠移開：既有的滑鼠 :hover 抬升（translateY -2px）不是焦點樣式，避免量到 transition 中的位置。
    page.mouse.move(2, 2)
    page.wait_for_timeout(300)
    rects_before = page.evaluate(f"() => [...document.querySelectorAll({json.dumps(sel)})].map(b => __ff.box(b.getBoundingClientRect()))")
    both = page.evaluate(f"""() => {{ __ff.clearFocus(); const b = document.querySelectorAll({json.dumps(sel)})[0];
        b.scrollIntoView({{ block: 'nearest' }}); b.classList.add('rl-pad-focus'); return __ff.cardFrame(b); }}""")
    page.wait_for_timeout(80)
    px_ok, px = pixels_ok(page, both['faceRect'])
    record(f'{name}_selected_and_focus_inside_card_face', both['selected'] and card_ok(both, focus=True, selected=True) and px_ok,
           {'measure': both, 'pixels': px})
    page.screenshot(path=str(OUT / f'{name}_selected_focus.png'))
    # 焦點移到第二張：第一張只剩 selected（藍色內框、無黃框），第二張只有 focus（黃＋黑、無藍）；兩者可分辨。
    pair = page.evaluate(f"""() => {{ __ff.clearFocus(); const bs = document.querySelectorAll({json.dumps(sel)});
        bs[1].classList.add('rl-pad-focus'); return [__ff.cardFrame(bs[0]), __ff.cardFrame(bs[1])]; }}""")
    record(f'{name}_selected_only_and_focus_only_distinguishable',
           pair[0]['selected'] and not pair[0]['focus'] and card_ok(pair[0], focus=False, selected=True)
           and pair[1]['focus'] and not pair[1]['selected'] and card_ok(pair[1], focus=True, selected=False)
           and pair[0]['afterShadow'] != pair[1]['afterShadow'], pair)
    rects_after = page.evaluate(f"() => [...document.querySelectorAll({json.dumps(sel)})].map(b => __ff.box(b.getBoundingClientRect()))")
    record(f'{name}_selected_focus_no_layout_shift', rects_before == rects_after, {'before': rects_before, 'after': rects_after})
    page.screenshot(path=str(OUT / f'{name}_selected_vs_focus.png'))


def check_frames(page, name: str, selector: str, *, limit: int = 6):
    res = page.evaluate(f"""() => [...document.querySelectorAll({json.dumps(selector)})]
        .filter(el => {{ const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }})
        .slice(0, {limit}).map(el => __ff.frameOf(el))""")
    record(f'{name}_frames_inside_target', bool(res) and all(r['ok'] for r in res), res)
    return res


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        # 1. 貿易戰加劇 event_topdeck_from_discard 單選（大棄牌堆，捲動 grid 的第一張與最後一張）。
        s = post_json('/test/setup-discard-topdeck-choice', {'discard_count': 18})
        ctx, page, errs = open_game(browser, s['url'])
        record('topdeck_pending_key', page.evaluate("window.lastGameState.pending_choice?.choice_key") == 'event_topdeck_from_discard',
               page.evaluate("window.lastGameState.pending_choice?.choice_key"))
        check_single(page, 'event_topdeck_from_discard', wait_choice_cards(page, False), expect_label=False)
        record('topdeck_no_page_errors', not errs, errs)
        ctx.close()

        # 2. trash_from_hand_or_discard 單選（有「手牌／棄牌堆」來源標籤）。
        s = post_json('/test/setup-trash-choice-ui', {'count': 1})
        ctx, page, errs = open_game(browser, f"/?game_id={s['game_id']}&player_id={s['player_id']}")
        check_single(page, 'trash_single', wait_choice_cards(page, False), expect_label=True)
        ctx.close()

        # 3. trash_from_hand_or_discard 複選 selected＋focus（有來源標籤）。
        s = post_json('/test/setup-trash-choice-ui', {'count': 2})
        ctx, page, errs = open_game(browser, f"/?game_id={s['game_id']}&player_id={s['player_id']}")
        sel = wait_choice_cards(page, True)
        record('trash_multi_has_zone_labels', page.locator(sel + ' > .choice-card-zone-label').count() == 4,
               page.locator(sel + ' > .choice-card-zone-label').count())
        check_multi(page, 'trash_multi', sel)
        ctx.close()

        # 4. 中紀委 red_army_ccdi_discard_draw 複選 selected＋focus。
        s = post_json('/test/setup-ccdi-choice', {})
        ctx, page, errs = open_game(browser, s['url'])
        record('ccdi_pending_key', page.evaluate("window.lastGameState.pending_choice?.choice_key") == 'red_army_ccdi_discard_draw',
               page.evaluate("window.lastGameState.pending_choice?.choice_key"))
        check_multi(page, 'ccdi', wait_choice_cards(page, True))
        ctx.close()

        # 5. 合作談判：玩家按鈕（#factionActionModalChoices .modal-choice-btn）。
        s = post_json('/test/setup-negotiation-proof', {})
        ctx, page, errs = open_game(browser, f"/?game_id={s['game_id']}&player_id={s['player_id']}")
        page.evaluate("setActiveGameView('command')")
        page.locator("button.hand-card-action-btn[data-card-name='合作談判'][data-card-mode='action']").first.click()
        page.wait_for_selector('#factionActionModal', state='visible', timeout=10000)
        check_frames(page, 'negotiation_player_buttons', '#factionActionModalChoices .modal-choice-btn')
        page.screenshot(path=str(OUT / 'negotiation_player_focus.png'))
        ctx.close()

        # 6. 離間：玩家按鈕（選取＋焦點）與確認鈕。
        s = post_json('/test/setup-divide-targets-proof', {})
        ctx, page, errs = open_game(browser, s['url'])
        page.evaluate("setActiveGameView('command')")
        page.locator("button.hand-card-action-btn[data-card-name='離間'][data-card-mode='action']").first.click()
        page.wait_for_selector('#factionActionModalChoices .divide-target-choice', state='visible', timeout=10000)
        page.locator('#factionActionModalChoices .divide-target-choice').first.click()
        page.wait_for_timeout(120)
        res = check_frames(page, 'divide_player_buttons', '#factionActionModalChoices .modal-choice-btn')
        sel_frame = page.evaluate("""() => { const b = document.querySelector('.divide-target-choice.divide-target-selected');
            const f = __ff.frameOf(b); return { ...f, selected: b.classList.contains('divide-target-selected') }; }""")
        record('divide_selected_and_focus_inside_target', sel_frame['selected'] and sel_frame['ok'], sel_frame)
        unfocused_sel = page.evaluate("""() => { __ff.clearFocus(); const b = document.querySelector('.divide-target-selected');
            return __ff.outerShadows(getComputedStyle(b).boxShadow); }""")
        record('divide_selected_has_no_outer_shadow', unfocused_sel == [], unfocused_sel)
        page.evaluate("() => __ff.frameOf(document.querySelector('.divide-target-selected'))")
        page.screenshot(path=str(OUT / 'divide_selected_focus.png'))
        page.evaluate("() => { document.getElementById('closeFactionActionModal')?.click(); }")
        page.wait_for_timeout(200)

        # 7. 遊戲畫面一般控制（分頁、說明、階段資訊、棄牌按鈕、手牌按鈕）＋真正 .card 的內縮 ::after 不被破壞＋CSSOM 稽核。
        page.evaluate(HELPERS_JS)
        check_frames(page, 'game_shell_controls',
                     '#gameTabs .game-tab, .joycon-help-btn, #phaseActionMeta, button.player-status-discard-card, .phase-action-btn', limit=12)
        card = page.evaluate("""() => { __ff.clearFocus(); const c = document.querySelector('#commandGrid .card');
            if (!c) return null; c.classList.add('rl-pad-focus'); const cs = getComputedStyle(c), a = getComputedStyle(c, '::after');
            return { outline: cs.outlineStyle, shadowOuter: __ff.outerShadows(cs.boxShadow), border: a.borderTopWidth, color: a.borderTopColor,
                     inset: [a.top, a.right, a.bottom, a.left], position: a.position }; }""")
        record('command_grid_card_keeps_inset_after_frame',
               card is not None and card['outline'] == 'none' and card['border'] == '2px' and card['color'] == 'rgb(255, 216, 61)'
               and card['inset'] == ['0px'] * 4 and card['position'] == 'absolute', card)
        # living-room 區域框與地圖按鈕框（parent overlay）：注入暫時元素量 computed style 與標籤位置。
        overlay = page.evaluate("""() => {
          const stage = document.getElementById('designStage'), html = document.documentElement;
          const prev = html.dataset.display;
          html.dataset.display = 'living-room';
          const ring = document.createElement('div'); ring.id = 'lrZoneRing'; ring.innerHTML = '<div id="lrZoneLabel">指揮中心｜手牌 3 張　A 進入</div>';
          Object.assign(ring.style, { left: '20px', top: '200px', width: '400px', height: '200px' });
          const btn = document.createElement('div'); btn.id = 'padButtonRing';
          Object.assign(btn.style, { left: '600px', top: '200px', width: '120px', height: '40px' });
          const had = [document.getElementById('lrZoneRing'), document.getElementById('padButtonRing')];
          had.forEach(n => n && n.remove());
          stage.append(ring, btn);
          const rc = getComputedStyle(ring), lc = getComputedStyle(document.getElementById('lrZoneLabel')), bc = getComputedStyle(btn);
          const rr = __ff.box(ring.getBoundingClientRect()), lr = __ff.box(document.getElementById('lrZoneLabel').getBoundingClientRect());
          const out = { ringBoxSizing: rc.boxSizing, ringBorder: rc.borderTopWidth, ringOuter: __ff.outerShadows(rc.boxShadow),
            labelShown: lc.display !== 'none', labelInside: __ff.inside(lr, rr), labelOuter: __ff.outerShadows(lc.boxShadow),
            btnOutlineOut: __ff.outlineOut(bc), btnOuter: __ff.outerShadows(bc.boxShadow) };
          ring.dataset.layer = 'item';
          out.itemOuter = __ff.outerShadows(getComputedStyle(ring).boxShadow);
          // 內容層不顯示內置標籤（會蓋住區域內的項目）；區域層照常顯示。
          out.itemLabelHidden = getComputedStyle(document.getElementById('lrZoneLabel')).display === 'none';
          ring.remove(); btn.remove(); had.forEach(n => n && stage.appendChild(n));
          if (prev === undefined) delete html.dataset.display; else html.dataset.display = prev;
          return out; }""")
        record('living_room_zone_ring_and_map_button_ring_inside',
               overlay['ringBoxSizing'] == 'border-box' and not overlay['ringOuter'] and not overlay['itemOuter']
               and overlay['labelShown'] and overlay['labelInside'] and not overlay['labelOuter'] and overlay['itemLabelHidden']
               and overlay['btnOutlineOut'] == 0 and not overlay['btnOuter'], overlay)
        # CSSOM 稽核：style.css 中任何黃／琥珀色 outline 必須 offset ≤ -width；黃／琥珀色 box-shadow 必須全部 inset。
        audit = page.evaluate(r"""() => {
          // CSSOM 會保留原始寫法（#hex 或 rgb()），兩種都解析；黃／琥珀＝紅高、藍低。
          const yellow = c => {
            let rgb = null;
            const m = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(c || '');
            if (m) rgb = m.slice(1).map(Number);
            const h = !m && /#([0-9a-f]{6}|[0-9a-f]{3})\b/i.exec(c || '');
            if (h) { const s = h[1].length === 3 ? h[1].split('').map(x => x + x).join('') : h[1]; rgb = [0, 2, 4].map(i => parseInt(s.slice(i, i + 2), 16)); }
            return !!rgb && rgb[0] >= 200 && rgb[1] >= 140 && rgb[2] <= 170 && rgb[0] - rgb[2] >= 60;
          };
          const bad = [];
          const sheet = [...document.styleSheets].find(s => (s.href || '').includes('style.css'));
          const walk = rules => { for (const r of rules) {
            if (r.cssRules && !r.style) { walk(r.cssRules); continue; }
            if (!r.style) continue;
            const st = r.style;
            if (st.outlineStyle && st.outlineStyle !== 'none' && yellow(st.outlineColor)) {
              const w = parseFloat(st.outlineWidth) || 0, off = parseFloat(st.outlineOffset) || 0;
              if (w + off > 0) bad.push({ sel: r.selectorText, kind: 'outline', w, off });
            }
            for (const sh of __ff.outerShadows(st.boxShadow)) if (yellow(sh)) bad.push({ sel: r.selectorText, kind: 'box-shadow', sh });
          } };
          walk(sheet.cssRules);
          return bad; }""")
        record('stylesheet_has_no_outward_yellow_outline_or_shadow', audit == [], audit)
        ctx.close()

        # 8. 開始遊戲入口（建立房間兩鈕、房間代碼輸入框、加入鈕）。
        ctx = browser.new_context(viewport={'width': 1280, 'height': 720}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(BASE_URL + '/', wait_until='domcontentloaded')
        page.wait_for_selector('#sfCreateHuman', state='visible', timeout=15000)
        page.evaluate(HELPERS_JS)
        res = check_frames(page, 'start_entry_controls', '#sfCreateHuman, #sfCreateAi, #sfRoomCode, #sfJoinBtn')
        record('start_entry_room_code_and_join_do_not_intrude',
               all(not r['neighborOverlap'] for r in res if r['id'] in ('sfRoomCode', 'sfJoinBtn')), res)
        page.evaluate("() => __ff.frameOf(document.getElementById('sfRoomCode'))")
        page.screenshot(path=str(OUT / 'start_entry_room_code_focus.png'))
        ctx.close()
        browser.close()

    passed = sum(c['ok'] for c in checks)
    report = {'base_url': BASE_URL, 'passed': passed, 'total': len(checks), 'checks': checks}
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': passed, 'total': len(checks), 'evidence': str(OUT)}, ensure_ascii=False))
    if passed != len(checks):
        raise SystemExit(1)


if __name__ == '__main__':
    if '--serve' in sys.argv:
        with serve_8201():
            main()
    else:
        main()
