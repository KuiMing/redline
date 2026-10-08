/*
 * REDLINE 客廳大螢幕模式（living-room）— 瀏覽器端膠合層。
 *
 * 同一 route、同一 DOM：html[data-display="living-room"] 只切換 CSS 版面層，並為搖桿加上
 *   區域層（zone）→ 內容層（item）兩層導航、固定情境動作列、危險操作確認單、地圖兩段式目標清單。
 * 只呼叫 controller_ui.js 交出的既有焦點／卡牌／地圖函式與既有元素的 click()；
 * 不合成滑鼠或鍵盤事件、不建構 action payload、不新增遊戲 action target。
 * modal、大廳與桌面模式一律交回 controller_ui.js 的既有流程。
 */
(function () {
  'use strict';
  const Core = window.RedlineControllerCore;
  const LR = window.RedlineLivingRoomCore;
  if (!Core || !LR || !window.RedlineController || typeof window.RedlineController.attachLayer !== 'function') return;

  const html = document.documentElement;
  const $ = id => document.getElementById(id);
  const qa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const CONTROL_SELECTOR = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])';
  const VIEW_LABEL = { command: '指揮中心', map: '戰略地圖', log: '戰況紀錄', myFaction: '我的陣營' };
  const VIEW_ZONES = {
    command: ['status', 'static', 'random', 'faction', 'hand', 'map', 'activity', 'actionbar'],
    map: ['maplist', 'actionbar'],
    other: ['view', 'actionbar'],
  };
  const RETURN_ZONE = { map: 'map', log: 'activity', myFaction: 'status' };

  let host = null;
  let displayMode = 'desktop';

  const lr = {
    zone: null, layer: 'zone', view: null, mem: {}, returnZone: null, lastCommandZone: null,
    guard: LR.createGuard(), stateRef: undefined, stateSeq: 0, lockTimer: null,
    slots: [], slotSig: '', mapList: LR.buildMapList(null), mapSig: '', mapStageKey: '', mapStageChanged: false,
    mapFocusTown: null, lastHandKey: null, notice: null, noticeTimer: null, renderTimer: null, confirm: null,
    mapReqSeq: 0, mapAckTimer: null, lastMapAck: null,
  };

  // ------------------------------------------------------------ display mode
  function storedDisplayMode() {
    try { return localStorage.getItem(LR.DISPLAY_STORAGE_KEY); } catch { return null; }
  }
  function storeDisplayMode(mode) {
    try { localStorage.setItem(LR.DISPLAY_STORAGE_KEY, mode); } catch { /* storage may be blocked */ }
  }

  function setDisplayMode(mode, { persist = true } = {}) {
    const previous = displayMode;
    displayMode = LR.normalizeDisplayMode(mode);
    if (displayMode === 'living-room') html.dataset.display = 'living-room';
    else delete html.dataset.display;
    if (persist) storeDisplayMode(displayMode);
    if (typeof window.resizeStage === 'function') window.resizeStage();
    if (typeof window.layoutGameShell === 'function') window.layoutGameShell();
    if (!host) return;
    ensureDom();
    if (!enabled()) {
      for (const id of ['lrBar', 'lrHelp', 'lrZoneRing', 'lrMapPanel']) { const el = $(id); if (el) el.hidden = true; }
    }
    if (previous !== displayMode) {
      closeConfirm({ silent: true });
      onClear();
      if (host.ctl.padActive) host.clearFocus();
    }
    renderAll();
    syncSettingsUi();
    host.renderHud();
  }

  // 在 DOMContentLoaded 前同步套用，第一次 resizeStage 就已使用安全區。
  const initialMode = LR.resolveDisplayMode(window.location.search, storedDisplayMode());
  setDisplayMode(initialMode.mode, { persist: initialMode.persist });

  function enabled() { return displayMode === 'living-room'; }

  // ------------------------------------------------------------ small DOM helpers
  function text(el) { return (el && el.textContent || '').replace(/\s+/g, ' ').trim(); }
  function shown(el) {
    if (!el || !host.isShown(el)) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && !el.closest('[inert]');
  }
  function usable(el) { return !!el && shown(el) && host.isUsable(el); }
  function activeView() { return host.activeGameView() || 'command'; }
  function gameShown() { return host.isShown($('gameShell')); }
  function unionRect(els) {
    const rects = els.filter(Boolean).map(el => el.getBoundingClientRect()).filter(r => r.width > 0 || r.height > 0);
    if (!rects.length) return null;
    return {
      left: Math.min(...rects.map(r => r.left)), top: Math.min(...rects.map(r => r.top)),
      right: Math.max(...rects.map(r => r.right)), bottom: Math.max(...rects.map(r => r.bottom)),
    };
  }
  function checkedPurchases(root = document) {
    return qa('input[data-purchase-index]', root).filter(box => box.checked).length;
  }

  // ------------------------------------------------------------ overlay DOM
  function ensureDom() {
    if (!enabled() || $('lrBar')) return;
    const stage = $('designStage');
    if (!stage) return;
    const bar = document.createElement('div');
    bar.id = 'lrBar';
    bar.setAttribute('data-controller-overlay', '');
    bar.setAttribute('aria-label', '情境動作列（搖桿）');
    bar.hidden = true;
    bar.innerHTML = '<div id="lrBarStatus"></div><div id="lrSlots"></div><div id="lrLegend"></div>';
    stage.appendChild(bar);

    const help = document.createElement('div');
    help.id = 'lrHelp';
    help.setAttribute('data-controller-overlay', '');
    help.hidden = true;
    help.innerHTML = `
      <div class="lr-help-title">搖桿操作（客廳模式）</div>
      <div>搖桿：區域層選區域／區域內移動</div>
      <div>A：進入區域；卡牌＝查看；動作列＝執行（⚠ 需確認）</div>
      <div>B：購買卡勾選／取消；其他項目回區域層</div>
      <div>X／Y：手牌＝資源／行動；其他＝動作列／說明</div>
      <div>ZR：回區域層（區域層再按＝回指揮中心）</div>
      <div>PLUS：跳到動作列（只移焦點，不執行）</div>
      <div>R／SR：下一個／上一個區域</div>`;
    stage.appendChild(help);

    const ring = document.createElement('div');
    ring.id = 'lrZoneRing';
    ring.setAttribute('data-controller-overlay', '');
    ring.hidden = true;
    ring.innerHTML = '<div id="lrZoneLabel"></div>';
    stage.appendChild(ring);

    const mapView = $('mapView');
    if (mapView) {
      const panel = document.createElement('div');
      panel.id = 'lrMapPanel';
      panel.setAttribute('data-controller-overlay', '');
      panel.hidden = true;
      panel.innerHTML = '<div id="lrMapTitle"></div><div id="lrMapRows" role="listbox" aria-label="地圖目標清單"></div><div id="lrMapFooter"></div>';
      mapView.appendChild(panel);
    }

    const modal = document.createElement('div');
    modal.id = 'lrConfirmModal';
    modal.className = 'modal-overlay lr-confirm-overlay';
    modal.setAttribute('role', 'alertdialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'lrConfirmTitle');
    modal.setAttribute('aria-hidden', 'true');
    modal.style.display = 'none';
    modal.innerHTML = `
      <div class="modal-glass lr-confirm-glass">
        <div class="panel-title">危險操作確認</div>
        <div id="lrConfirmTitle" class="modal-title-text"></div>
        <div id="lrConfirmBody" class="modal-body-text"></div>
        <ul id="lrConfirmInfo"></ul>
        <div class="lr-confirm-actions">
          <button id="lrConfirmCancelBtn" type="button" class="modal-cancel-btn">返回</button>
          <button id="lrConfirmOkBtn" type="button" class="modal-choice-btn lr-confirm-ok">確認</button>
        </div>
      </div>`;
    stage.appendChild(modal);
    $('lrConfirmCancelBtn').addEventListener('click', () => closeConfirm());
    $('lrConfirmOkBtn').addEventListener('click', confirmOk);
  }

  function ensureSettingsUi() {
    const panel = $('padPanel');
    if (!panel || $('padDisplaySelect')) return;
    const row = document.createElement('label');
    row.className = 'pad-row';
    row.innerHTML = '顯示模式 <select id="padDisplaySelect"><option value="desktop">桌面</option><option value="living-room">客廳大螢幕</option></select>';
    const note = panel.querySelector('.pad-note:not([id])');
    panel.insertBefore(row, note || null);
    $('padDisplaySelect').addEventListener('change', (e) => setDisplayMode(e.target.value));
    syncSettingsUi();
  }
  function syncSettingsUi() {
    const select = $('padDisplaySelect');
    if (select && select.value !== displayMode) select.value = displayMode;
  }

  // ------------------------------------------------------------ notices / processing lock
  function syncStateToken() {
    const state = window.lastGameState;
    if (state !== lr.stateRef) {
      lr.stateRef = state;
      lr.stateSeq += 1;
    }
  }
  function processing() {
    syncStateToken();
    return LR.processingActive(lr.guard, performance.now(), lr.stateSeq);
  }
  function lock() {
    syncStateToken();
    lr.guard = LR.lockProcessing(lr.guard, performance.now(), lr.stateSeq);
    clearTimeout(lr.lockTimer);
    lr.lockTimer = setTimeout(() => host && host.renderHud(), LR.DEFAULT_GUARD_CONFIG.processingTimeoutMs + 30);
  }
  function noteRedraw() { lr.guard = LR.noteRedraw(lr.guard, performance.now()); }
  function flash(message) {
    lr.notice = message;
    clearTimeout(lr.noticeTimer);
    lr.noticeTimer = setTimeout(() => { lr.notice = null; if (host) host.renderHud(); }, 1800);
    host.renderHud();
  }

  // ------------------------------------------------------------ action bar（只鏡射既有、可見、啟用的控制）
  function domSource(id, label) {
    const el = $(id);
    if (!el) return null;
    return {
      id, kind: 'dom', label: label || text(el), visible: shown(el), disabled: el.disabled === true,
      ariaDisabled: el.getAttribute('aria-disabled') === 'true', inert: !!el.closest('[inert]'),
    };
  }

  function handCardByKey(key) {
    if (!key) return null;
    const zone = describeZone('hand');
    if (!zone) return null;
    const index = zone.keys.indexOf(key);
    return index >= 0 ? zone.items[index] : null;
  }

  // 一般奧援的第一顆按鈕是「棄置」（不可逆）：只鏡射「最近聚焦的手牌」那一顆，且一律走確認單。
  function handDiscardButton() {
    const card = handCardByKey(lr.lastHandKey);
    if (!card) return null;
    const buttons = qa('.hand-card-action-btn[data-card-mode="resource"]', card);
    if (buttons.length !== 1 || text(buttons[0]) !== '棄置') return null;
    return buttons[0];
  }

  function mapSlotLabel(button, snap) {
    if (button.id === 'confirmMoveBtn' && snap.pending) return `確認移動 ${snap.pending.from}→${snap.pending.to}`;
    return button.label;
  }

  function collectSlots() {
    if (!gameShown()) return [];
    const view = activeView();
    const sources = [];
    if (view === 'map') {
      const snap = host.getMapSnapshot();
      if (snap) for (const b of snap.buttons) sources.push({ id: b.id, kind: 'map', label: mapSlotLabel(b, snap), visible: true, disabled: false });
    }
    if (view === 'command') {
      const buy = $('openPurchaseConfirmBtn');
      sources.push(domSource('openPurchaseConfirmBtn', buy ? `${text(buy)}（${checkedPurchases()} 張）` : ''));
      sources.push(domSource('clearPurchaseSelectionBtn'));
      sources.push(domSource('topdeckRightBtn'));
      const discard = handDiscardButton();
      if (discard) {
        const name = discard.closest('[data-card-name]')?.dataset.cardName || '';
        sources.push({
          id: 'handDiscard', kind: 'dom', label: `棄置 ${name}`, visible: shown(discard), disabled: discard.disabled === true,
          ariaDisabled: discard.getAttribute('aria-disabled') === 'true', inert: !!discard.closest('[inert]'),
        });
      }
    }
    sources.push(domSource('redArmyAbilityBtn'));
    sources.push(domSource('advanceStepBtn'));
    return LR.buildActionBar(sources.filter(Boolean));
  }

  /** 按下當下重驗：回傳仍可用的既有目標，否則 null（fail-closed）。 */
  function resolveSlot(id) {
    if (LR.MAP_SLOT_IDS.includes(id)) {
      const snap = host.getMapSnapshot();
      return activeView() === 'map' && snap && snap.buttons.some(b => b.id === id) ? { kind: 'map', id } : null;
    }
    if (id === 'handDiscard') {
      const btn = handDiscardButton();
      return usable(btn) ? { kind: 'dom', el: btn } : null;
    }
    if (!LR.SLOT_ORDER.includes(id)) return null;
    const el = $(id);
    return usable(el) ? { kind: 'dom', el } : null;
  }

  function renderSlots() {
    const slots = collectSlots();
    const sig = JSON.stringify(slots);
    lr.slots = slots;
    if (sig === lr.slotSig) return false;
    lr.slotSig = sig;
    const box = $('lrSlots');
    if (!box) return true;
    box.textContent = '';
    if (!slots.length) {
      const empty = document.createElement('div');
      empty.className = 'lr-slot-empty';
      empty.textContent = '目前沒有可用操作';
      box.appendChild(empty);
      return true;
    }
    for (const slot of slots) {
      const el = document.createElement('div');
      el.className = 'lr-slot';
      el.dataset.slotId = slot.id;
      el.dataset.danger = slot.danger ? 'true' : 'false';
      el.textContent = slot.label;
      box.appendChild(el);
    }
    return true;
  }

  // ------------------------------------------------------------ map list（兩段式，資料只來自 iframe 權威 snapshot）
  function mapRowMeta(row, list) {
    if (row.role === 'origin') return '可行動來源';
    if (row.role === 'choice') return list.selected === row.town ? '✔ 已選取' : '待選目標';
    const parts = [LR.moveModeLabel(row.mode)];
    if (row.cost !== null && row.cost !== undefined) parts.push(`消耗 ${row.cost}`);
    return parts.filter(Boolean).join('・');
  }

  function renderMapPanel() {
    const panel = $('lrMapPanel');
    if (!panel) return false;
    const visible = enabled() && host.ctl.settings.enabled && activeView() === 'map';
    if (panel.hidden === visible) panel.hidden = !visible;
    const list = activeView() === 'map' ? LR.buildMapList(host.getMapSnapshot()) : LR.buildMapList(null);
    const stageKey = `${list.stage}|${list.selected || ''}`;
    if (stageKey !== lr.mapStageKey) {
      lr.mapStageChanged = lr.mapStageKey !== '';
      lr.mapStageKey = stageKey;
    }
    lr.mapList = list;
    const sig = JSON.stringify(list);
    if (sig === lr.mapSig) return false;
    lr.mapSig = sig;
    const title = {
      none: '沒有可操作的地圖目標',
      choice: `選擇目標（${list.rows.length}）`,
      source: `選擇來源（${list.rows.length}）`,
      destination: `選擇目的地（${list.rows.length}）・來源 ${list.selected}`,
    }[list.stage];
    $('lrMapTitle').textContent = title;
    const rows = $('lrMapRows');
    rows.textContent = '';
    for (const row of list.rows) {
      const el = document.createElement('div');
      el.className = 'lr-map-row';
      el.setAttribute('role', 'option');
      el.dataset.town = row.town;
      el.dataset.role = row.role;
      const name = document.createElement('span');
      name.className = 'lr-map-town';
      name.textContent = row.town;
      const meta = document.createElement('span');
      meta.className = 'lr-map-meta';
      meta.textContent = mapRowMeta(row, list);
      el.append(name, meta);
      rows.appendChild(el);
    }
    let footer = '滑鼠仍可直接點選地圖。';
    if (list.pending) footer = `已預備：${list.pending.from} → ${list.pending.to}　按 PLUS 到動作列確認`;
    else if (list.stage === 'destination') footer = 'A 預備移動（不會立即執行）　B 取消來源';
    else if (list.stage === 'choice' && list.selected) footer = `已選取 ${list.selected}　按 PLUS 到動作列確認`;
    $('lrMapFooter').textContent = footer;
    return true;
  }

  function focusMapTown(town) {
    if (lr.mapFocusTown === town) return;
    lr.mapFocusTown = town;
    host.sendToMap('focus', { town });
  }
  function clearMapTownFocus() {
    if (!lr.mapFocusTown) return;
    lr.mapFocusTown = null;
    host.sendToMap('clearFocus');
  }

  // ------------------------------------------------------------ zones
  function zoneOf(id, label, kind, frames, items, always = false) {
    const visibleFrames = frames.filter(shown);
    if (!visibleFrames.length) return null;
    const rect = unionRect(visibleFrames);
    if (!rect) return null;
    const zone = { id, label, kind, frames: visibleFrames, rect, items, keys: [] };
    zone.keys = keysFor(zone);
    zone.available = always || items.length > 0;
    return zone;
  }

  function controlsWithin(roots) {
    const out = [];
    for (const root of roots.filter(shown)) {
      for (const el of qa(CONTROL_SELECTOR, root)) {
        if (out.includes(el) || !usable(el)) continue;
        if (el.matches('input[type="checkbox"]') && el.closest('[data-card-zone]')) continue; // checkbox 保留給滑鼠
        out.push(el);
      }
    }
    return out;
  }

  function describeZone(id) {
    switch (id) {
      case 'status':
        return zoneOf(id, '玩家狀態', 'controls', [$('hud')],
          qa('#myFactionBtn, #eventCardTab, #activeEraTabs .era-stage-tab').filter(usable));
      case 'static':
        return zoneOf(id, '常設購買區', 'cards', [$('purchaseSection')], qa('#purchaseStatic .card[data-card-zone="purchase"]').filter(shown));
      case 'random':
        return zoneOf(id, '隨機購買區', 'cards', [$('randomMarketPanel')], qa('#purchaseRandom .card[data-card-zone="purchase"]').filter(shown));
      case 'faction': {
        const frames = [$('factionActionPanel'), $('baseSelectionPanel')];
        return zoneOf(id, '陣營能力', 'controls', frames, controlsWithin(frames));
      }
      case 'hand':
        return zoneOf(id, '手牌', 'cards', [$('handPanel')], qa('#hand .card[data-card-zone="hand"]').filter(shown));
      case 'map': {
        const tab = document.querySelector('.game-tab[data-view="map"]');
        return zoneOf(id, '戰略地圖', 'portal', [tab], [tab].filter(usable));
      }
      case 'activity': {
        const tab = document.querySelector('.game-tab[data-view="log"]');
        const peer = $('peerActionNotice');
        const expand = peer && peer.classList.contains('peer-action-notice-minimized') ? $('peerActionNoticeMinimizeBtn') : null;
        return zoneOf(id, '玩家動態', 'controls', [tab], [tab, expand].filter(usable));
      }
      case 'view': {
        const view = document.querySelector('.game-view.active');
        return zoneOf(id, VIEW_LABEL[activeView()] || '內容', 'controls', [view], controlsWithin([view]), true);
      }
      case 'maplist': {
        const panel = $('lrMapPanel');
        return zoneOf(id, '地圖目標清單', 'mapList', [panel], panel ? qa('.lr-map-row', panel) : [], true);
      }
      case 'actionbar':
        return zoneOf(id, '情境動作列', 'bar', [$('lrSlots')], qa('#lrSlots .lr-slot'));
      default:
        return null;
    }
  }

  function keysFor(zone) {
    const counts = new Map();
    return zone.items.map((el, index) => {
      if (zone.id === 'actionbar') return `slot:${el.dataset.slotId}`;
      if (zone.id === 'maplist') return `town:${el.dataset.town}`;
      const box = el.matches('.card[data-card-zone="purchase"]') ? el.querySelector('input[data-purchase-index]') : null;
      if (box) return `purchase:${box.dataset.purchaseIndex}`;
      // 手牌以「位置＋卡名」為 key：打出一張後，同位置換成別張牌時視為 key 消失 → 留在同索引，
      // 不會因為同名卡（例如多張追隨者）而跳到更右邊的另一張。
      if (zone.id === 'hand') return `hand:${index}:${el.dataset.cardName || ''}`;
      const base = el.matches('.card[data-card-zone]')
        ? `card:${el.dataset.cardZone}:${el.dataset.cardName || ''}`
        : el.id ? `#${el.id}` : [el.tagName, el.dataset.view || '', el.dataset.eraId || '', text(el).slice(0, 16)].join('|');
      const n = counts.get(base) || 0;
      counts.set(base, n + 1);
      return `${base}#${n}`;
    });
  }

  function zonesNow(view) {
    const ids = VIEW_ZONES[view] || VIEW_ZONES.other;
    const locked = view === 'command' && host.choiceLocked();
    const out = [];
    for (const id of ids) {
      // 必選地圖目標時，指揮中心只保留「戰略地圖」入口與動作列。
      if (locked && id !== 'map' && id !== 'actionbar') continue;
      const zone = describeZone(id);
      if (zone && zone.available) out.push(zone);
    }
    return out;
  }

  function dangerKeys() {
    return new Set(lr.slots.filter(s => s.danger).map(s => `slot:${s.id}`));
  }

  function zoneSummary(zone) {
    if (zone.id === 'hand') return `${zone.items.length} 張`;
    if (zone.id === 'static' || zone.id === 'random') {
      const selected = checkedPurchases(zone.frames[0]);
      return `${zone.items.length} 張${selected ? `｜已勾選 ${selected}` : ''}`;
    }
    if (zone.id === 'actionbar') return `${zone.items.length} 項`;
    if (zone.id === 'maplist') return lr.mapList.stage === 'none' ? '無目標' : `${lr.mapList.rows.length} 個`;
    return '';
  }

  // ------------------------------------------------------------ focus rendering
  function hideRing() {
    const ring = $('lrZoneRing');
    if (ring && !ring.hidden) ring.hidden = true;
  }

  function drawRing(zone) {
    const ring = $('lrZoneRing');
    const stage = $('designStage');
    if (!ring || !stage || !zone) return;
    const focused = lr.layer === 'item' && host.ctl.focusEl && zone.items.includes(host.ctl.focusEl) ? host.ctl.focusEl : null;
    const rect = unionRect([...zone.frames, focused]) || zone.rect;
    const sr = stage.getBoundingClientRect();
    const scale = stage.offsetWidth ? sr.width / stage.offsetWidth : 1;
    const pad = 4;
    const left = Math.max(2, (rect.left - sr.left) / scale - pad);
    const top = Math.max(2, (rect.top - sr.top) / scale - pad);
    const right = Math.min(stage.offsetWidth - 2, (rect.right - sr.left) / scale + pad);
    const bottom = Math.min(stage.offsetHeight - 2, (rect.bottom - sr.top) / scale + pad);
    ring.style.left = `${left}px`;
    ring.style.top = `${top}px`;
    ring.style.width = `${Math.max(0, right - left)}px`;
    ring.style.height = `${Math.max(0, bottom - top)}px`;
    ring.dataset.layer = lr.layer;
    ring.dataset.zone = zone.id;
    ring.dataset.labelInside = top < 30 ? 'true' : 'false';
    const summary = zoneSummary(zone);
    const label = `${zone.label}${summary ? `｜${summary}` : ''}${lr.layer === 'zone' ? '　A 進入' : ''}`;
    const labelEl = $('lrZoneLabel');
    if (labelEl.textContent !== label) labelEl.textContent = label;
    ring.hidden = false;
  }

  function rememberCommandZone(zone) {
    if (activeView() === 'command' && zone.id !== 'actionbar') lr.lastCommandZone = zone.id;
  }

  function focusZone(zone, { user = true } = {}) {
    clearMapTownFocus();
    host.clearDomFocus();
    const ctl = host.ctl;
    ctl.focusKind = 'zone';
    ctl.focusEl = null;
    ctl.focusSig = `zone:${zone.id}`;
    ctl.focusTown = null;
    lr.zone = zone.id;
    lr.layer = 'zone';
    rememberCommandZone(zone);
    if (!user) noteRedraw();
    drawRing(zone);
  }

  function focusItem(zone, index, { user = true } = {}) {
    const el = zone.items[index];
    if (!el) { focusZone(zone, { user }); return; }
    const key = zone.keys[index];
    const ctl = host.ctl;
    if (ctl.focusEl !== el || !el.classList.contains('rl-pad-focus')) host.focusDom({ el, sig: `lr:${key}` });
    ctl.focusSig = `lr:${key}`;
    lr.zone = zone.id;
    lr.layer = 'item';
    lr.mem[zone.id] = { key, index };
    if (zone.id === 'hand') lr.lastHandKey = key;
    if (zone.id === 'maplist') focusMapTown(el.dataset.town);
    else clearMapTownFocus();
    rememberCommandZone(zone);
    if (!user) noteRedraw();
    drawRing(zone);
  }

  /** 地圖清單還沒有目標時：停在清單內容層、不聚焦任何列（A 無作用）。 */
  function focusEmptyMapList(zone) {
    clearMapTownFocus();
    host.clearDomFocus();
    host.ctl.focusKind = 'zone';
    host.ctl.focusEl = null;
    host.ctl.focusSig = 'lr:maplist-empty';
    lr.zone = zone.id;
    lr.layer = 'item';
    drawRing(zone);
  }

  /** 進入地圖清單內容層；清單暫時沒有目標也算已進入（停在空清單，A 無作用）。回傳是否成功進入。 */
  function enterMapList(zone, { user = true } = {}) {
    if (!zone || zone.kind !== 'mapList') return false;
    const mem = lr.mem.maplist || {};
    const index = LR.reconcileIndex(zone.keys, mem.key, mem.index ?? 0, null);
    if (index >= 0) focusItem(zone, index, { user });
    else focusEmptyMapList(zone);
    return lr.zone === zone.id && lr.layer === 'item';
  }

  function placeDefault(view, zones) {
    lr.view = view;
    const ids = zones.map(z => z.id);
    const preferred = view === 'command' ? (lr.returnZone || lr.lastCommandZone) : view === 'map' ? 'maplist' : 'view';
    lr.returnZone = null;
    const id = LR.resolveZone(ids, preferred);
    const zone = zones.find(z => z.id === id);
    if (zone) focusZone(zone);
    else { hideRing(); host.clearDomFocus(); lr.zone = null; lr.layer = 'zone'; }
  }

  // ------------------------------------------------------------ dispatch
  function handles(scope) {
    return gameShown() && (scope.kind === 'page' || scope.kind === 'map');
  }

  function currentIndex(zone) {
    const byEl = zone.items.indexOf(host.ctl.focusEl);
    if (byEl >= 0) return byEl;
    const mem = lr.mem[zone.id];
    return mem ? zone.keys.indexOf(mem.key) : -1;
  }

  /**
   * 客廳模式下 modal 內的 A：只套用 250ms 執行冷卻，通過時交回 controller_ui 的既有 modal 流程
   * （回傳 false）；被擋下時吞掉這次輸入（回傳 true）。B／方向等其他輸入一律交回既有流程。
   */
  function gateModalConfirm(action) {
    const logical = LR.logicalAction(action);
    if (!host.ctl.padActive || !logical || logical.name !== 'confirm') return false;
    syncStateToken();
    const verdict = LR.gate(lr.guard, performance.now(), lr.stateSeq, 'modalConfirm');
    lr.guard = verdict.guard;
    if (!verdict.allowed) { host.renderHud(); return true; }
    // 是否真的執行由既有 modal 流程決定；實際執行後 controller_ui 會呼叫 noteActivation()。
    return false;
  }

  /** 只在既有元素確實被執行後開始 250ms 冷卻；fail-closed 的 no-op 不影響下一次合法操作。 */
  function noteActivation() {
    lr.guard = LR.noteActivation(lr.guard, performance.now());
  }

  function dispatch(action) {
    const scope = host.currentScope();
    if (scope.kind === 'modal') return gateModalConfirm(action);
    if (!handles(scope)) return false;
    syncStateToken();
    const logical = LR.logicalAction(action);
    if (!logical) return true;
    const ctl = host.ctl;
    const view = activeView();
    renderAll();
    const zones = zonesNow(view);
    // 第一次有效操作（或區域消失、分頁被滑鼠切換）只放焦點，不執行。
    if (!ctl.padActive) {
      ctl.padActive = true;
      ctl.lastScopeId = scope.id;
      placeDefault(view, zones);
      host.renderHud();
      return true;
    }
    const zone = zones.find(z => z.id === lr.zone);
    if (lr.view !== view || !zone) {
      placeDefault(view, zones);
      host.renderHud();
      return true;
    }
    let index = -1;
    if (lr.layer === 'item') {
      index = currentIndex(zone);
      if (index < 0 && zone.id !== 'maplist') { focusZone(zone); host.renderHud(); return true; }
    }
    const el = index >= 0 ? zone.items[index] : null;
    const snap = host.getMapSnapshot();
    const ctx = {
      scopeKind: scope.kind, view, layer: lr.layer, zone: zone.id,
      locked: scope.kind === 'map' && host.choiceLocked(),
      mapCanCancel: !!(snap && snap.canCancel),
      item: el ? { card: host.cardContext({ kind: 'dom', el }), slot: zone.id === 'actionbar', mapRow: zone.id === 'maplist' } : null,
    };
    const command = LR.routeLivingRoom(ctx, logical);
    if (command) {
      const verdict = LR.gate(lr.guard, performance.now(), lr.stateSeq, command.cmd);
      lr.guard = verdict.guard;
      if (verdict.allowed) {
        // 只有真的執行了（run 回傳 true）才開始 250ms 冷卻；fail-closed no-op 與方向／ZR／PLUS 不記錄。
        if (run(command, zone, index, zones, view) && LR.ACTIVATION_GATED.has(command.cmd)) noteActivation();
      } else if (verdict.reason === 'processing' || verdict.reason === 'map-pending') flash('處理中…請稍候');
    }
    host.renderHud();
    return true;
  }

  /**
   * 回傳 true 表示確實執行了（click 既有控制、開啟預覽／確認單、成功進入區域）。
   * 地圖 iframe 指令一律回傳 false：是否執行要等 iframe 以同一個 req 回覆 ok:true，由 onMapResult 記錄冷卻／上鎖。
   */
  function run(command, zone, index, zones, view) {
    const el = index >= 0 ? zone.items[index] : null;
    const item = el ? { kind: 'dom', el } : null;
    switch (command.cmd) {
      case 'zoneMove': {
        const id = LR.pickZone(zones.map(z => ({ id: z.id, rect: z.rect })), zone.id, command.dir);
        const next = zones.find(z => z.id === id);
        if (next && next.id !== zone.id) focusZone(next);
        return false;
      }
      case 'ring': {
        const next = zones.find(z => z.id === LR.cycleZone(zones.map(z2 => z2.id), zone.id, command.step));
        if (next) focusZone(next);
        return false;
      }
      case 'enterZone': return enterZone(zone);
      case 'itemMove': moveItem(zone, index, command.dir); return false;
      case 'toZoneLayer': focusZone(zone); return false;
      case 'focusActionBar': focusActionBar(zones); return false;
      case 'leaveView': leaveView(view); return false;
      case 'toggleHelp': host.ctl.helpOpen = !host.ctl.helpOpen; renderHelp(); return false;
      case 'cardPreview': return host.previewCard(item) === true;
      case 'cardToggle': return host.toggleCard(item) === true;
      case 'cardMode': {
        const played = host.playCardMode(item, command.mode) === true;
        if (played) lock();
        return played;
      }
      case 'activate': return activateControl(el);
      case 'slotActivate': return el ? activateSlot(el.dataset.slotId) : false;
      case 'mapPick': return el ? mapPick(el.dataset.town) : false;
      case 'mapCancel': return mapCancel();
      default: return false;
    }
  }

  /**
   * A 進入區域：入口區域切換分頁；其他區域把焦點放到記憶／預設項目（地圖清單沒有目標時停在空清單）。
   * 成功進入即回傳 true（開始 250ms 冷卻，避免同一串連按立刻執行剛聚焦的第一項，
   * 例如動作列第一格或地圖第一個來源）；無法進入（入口不可用、區域沒有項目）回傳 false。
   */
  function enterZone(zone) {
    if (zone.kind === 'portal') {
      const tab = zone.items[0];
      if (!usable(tab)) return false;
      lr.returnZone = zone.id;
      tab.click(); // 既有分頁切換
      host.sendToMap('snapshot');
      host.scheduleReconcile();
      return true;
    }
    if (zone.kind === 'mapList') return enterMapList(zone);
    if (!zone.items.length) return false;
    const mem = lr.mem[zone.id] || {};
    let index;
    if (zone.id === 'actionbar') {
      const remembered = zone.keys.indexOf(mem.key);
      index = remembered >= 0 && !dangerKeys().has(zone.keys[remembered]) ? remembered : LR.defaultSlotIndex(lr.slots);
    } else {
      index = LR.reconcileIndex(zone.keys, mem.key, mem.index ?? 0, null);
    }
    if (index < 0) return false;
    focusItem(zone, index);
    return lr.zone === zone.id && lr.layer === 'item';
  }

  function moveItem(zone, index, dir) {
    let next = index;
    if (zone.kind === 'cards') {
      const rects = zone.items.map(el => el.getBoundingClientRect());
      next = LR.gridMove(zone.items.length, LR.gridColumns(rects), index, dir);
    } else if (zone.kind === 'bar') {
      next = LR.gridMove(zone.items.length, zone.items.length, index, dir);
    } else if (zone.kind === 'mapList') {
      if (!zone.items.length) return;
      next = index < 0 ? 0 : LR.listMove(zone.items.length, index, dir);
    } else {
      const items = zone.items.map((el, i) => {
        const r = el.getBoundingClientRect();
        return { key: String(i), left: r.left, top: r.top, right: r.right, bottom: r.bottom };
      });
      const picked = Core.pickDirectional(items, String(index), dir);
      next = picked ? Number(picked.key) : index;
    }
    if (next >= 0 && next !== index) focusItem(zone, next);
  }

  function focusActionBar(zones) {
    const bar = zones.find(z => z.id === 'actionbar');
    const index = LR.defaultSlotIndex(lr.slots);
    if (!bar || index < 0) { flash('目前沒有可用操作'); return; }
    focusItem(bar, index);
  }

  function leaveView(view) {
    const tab = document.querySelector('.game-tab[data-view="command"]');
    if (!usable(tab)) return;
    lr.returnZone = RETURN_ZONE[view] || null;
    tab.click(); // 既有分頁切換
    host.scheduleReconcile();
  }

  function activateControl(el) {
    if (!usable(el)) return false;
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) { el.focus(); return false; }
    el.click();
    if (!el.matches('.game-tab[data-view]')) lock();
    host.scheduleReconcile();
    return true;
  }

  function activateSlot(id) {
    const target = resolveSlot(id);
    if (!target) { flash('此操作目前不可用'); host.scheduleReconcile(); return false; }
    if (LR.DANGER_SLOT_IDS.has(id)) return openConfirm(id);
    // 地圖按鈕：iframe 端再驗一次白名單與可用性；成功回覆後才上處理中鎖並記錄冷卻。
    if (target.kind === 'map') return sendMapRequest('button', { id }, { lock: true });
    target.el.click();
    lock();
    host.scheduleReconcile();
    return true;
  }

  function mapPick(town) {
    // 只送出目前清單（最新 snapshot）裡的城鎮；iframe 執行前仍會用伺服器權威資料重驗。
    if (!lr.mapList.rows.some(r => r.town === town)) return false;
    return sendMapRequest('activate', { town }, {});
  }

  function mapCancel() {
    // 「取消瓦解」會送出伺服器 cancel_choice：iframe 回報實際走了該按鈕才上處理中鎖，新 state 抵達（或逾時）前不會重送；
    // 只取消地圖選取是純 UI，不上鎖但受 250ms 執行冷卻保護。snapshot 沒有可取消流程時不送。
    const snap = host.getMapSnapshot();
    if (!snap || !snap.canCancel) return false;
    return sendMapRequest('cancel', {}, { lockVia: 'cancelDissolveChoiceBtn' });
  }

  // ------------------------------------------------------------ map iframe acknowledgment
  /**
   * 送出帶 req 的地圖執行型指令並登記為等待確認。一律回傳 false（尚未執行）：
   * 沒有 iframe／送出失敗 → 立即 fail closed；送出成功 → 等 onMapResult 依 iframe 回覆決定。
   */
  function sendMapRequest(cmd, extra, meta) {
    lr.mapReqSeq += 1;
    const req = lr.mapReqSeq;
    if (!host.sendToMap(cmd, { ...extra, req })) {
      lr.lastMapAck = { req, cmd, outcome: 'no-frame', lock: false };
      flash('地圖尚未就緒');
      host.scheduleReconcile();
      return false;
    }
    lr.guard = LR.beginMapRequest(lr.guard, performance.now(), req, { cmd, ...meta });
    clearTimeout(lr.mapAckTimer);
    lr.mapAckTimer = setTimeout(expireMapRequest, LR.DEFAULT_GUARD_CONFIG.mapAckTimeoutMs + 20);
    return false;
  }

  function expireMapRequest() {
    lr.mapAckTimer = null;
    const out = LR.expireMapRequest(lr.guard, performance.now());
    lr.guard = out.guard;
    if (!out.expired || !host) return;
    lr.lastMapAck = { req: out.expired.req, cmd: out.expired.cmd, outcome: 'timeout', lock: false };
    flash('地圖沒有回應，請再試一次');
    host.scheduleReconcile();
  }

  /** controller_ui 交來已 sanitize 的 iframe 回覆；只有對上等待中的 req 且 ok:true 才記錄冷卻／上鎖。 */
  function onMapResult(result) {
    const out = LR.settleMapResult(lr.guard, performance.now(), result);
    if (out.outcome === 'stale') return;
    lr.guard = out.guard;
    clearTimeout(lr.mapAckTimer);
    lr.mapAckTimer = null;
    lr.lastMapAck = { req: out.request.req, cmd: out.request.cmd, outcome: out.outcome, lock: out.lock };
    if (out.lock) lock();
    if (out.outcome === 'failed') flash('此操作目前不可用');
    else if (out.outcome === 'timeout') flash('地圖沒有回應，請再試一次');
    host.scheduleReconcile();
    host.renderHud();
  }

  // ------------------------------------------------------------ dangerous confirm（預設焦點＝返回）
  function playableHandCount() {
    return qa('#hand .hand-card-action-btn[data-card-mode="action"]').filter(usable).length;
  }

  /** 開啟確認單；回傳是否真的開啟（開啟本身算一次執行，確認鍵需間隔 250ms）。 */
  function openConfirm(id) {
    const slot = lr.slots.find(s => s.id === id);
    const modal = $('lrConfirmModal');
    if (!slot || !modal) return false;
    lr.confirm = { id, label: slot.label };
    $('lrConfirmTitle').textContent = `確認：${slot.label}`;
    $('lrConfirmBody').textContent = '送出後無法復原。要執行請向右移到「確認」再按 A；B 或「返回」取消。';
    const info = $('lrConfirmInfo');
    info.textContent = '';
    for (const line of LR.confirmInfoLines({ playableHand: id === 'advanceStepBtn' ? playableHandCount() : 0, selectedPurchases: checkedPurchases() })) {
      const li = document.createElement('li');
      li.textContent = line;
      info.appendChild(li);
    }
    $('lrConfirmOkBtn').textContent = `確認${slot.label}`;
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    host.scheduleReconcile();
    return true;
  }

  function closeConfirm({ silent = false } = {}) {
    const modal = $('lrConfirmModal');
    lr.confirm = null;
    if (modal && modal.style.display !== 'none') {
      modal.style.display = 'none';
      modal.setAttribute('aria-hidden', 'true');
      if (!silent && host) host.scheduleReconcile();
    }
  }

  function confirmOk() {
    const pending = lr.confirm;
    closeConfirm();
    if (!pending) return;
    if (processing()) { flash('處理中…請稍候'); return; }
    const target = resolveSlot(pending.id);
    if (!target || target.kind !== 'dom') { flash('此操作目前不可用'); return; }
    target.el.click(); // 既有按鈕的既有 handler
    lock();
  }

  // ------------------------------------------------------------ legend / status / help
  function legendText() {
    const ctl = host.ctl;
    const scope = host.currentScope();
    if (scope.kind === 'modal') return host.hintText();
    if (!ctl.padActive) return '任意鍵開始：先選區域，A 進入';
    const view = activeView();
    if (lr.layer === 'zone') {
      return `搖桿 選區域　A 進入　R/SR 切換區域　PLUS 動作列　Y 說明${view !== 'command' ? '　ZR 回指揮中心' : ''}`;
    }
    if (lr.zone === 'actionbar') return '←→ 選擇　A 執行（⚠ 會先確認）　ZR 回區域層　B 回區域層';
    if (lr.zone === 'maplist') {
      const stage = lr.mapList.stage;
      if (stage === 'destination') return '↑↓ 選目的地　A 預備移動　B 取消來源　PLUS 動作列確認';
      if (stage === 'choice') return '↑↓ 選目標　A 選取　B 取消／返回　PLUS 動作列確認';
      if (stage === 'source') return '↑↓ 選來源　A 選取　B 返回　PLUS 動作列　ZR 回區域層';
      return '沒有可操作的地圖目標　ZR 回區域層　PLUS 動作列';
    }
    const card = ctl.focusEl ? host.cardContext({ kind: 'dom', el: ctl.focusEl }) : null;
    if (card && card.zone === 'hand') return '←→ 選牌　A 查看　X 資源　Y 行動　ZR 回區域層　PLUS 動作列';
    if (card) return '←→ 選牌　A 查看　B 勾選／取消　ZR 回區域層　PLUS 動作列';
    return 'A 確認　B 回區域層　ZR 回區域層　PLUS 動作列';
  }

  function statusText() {
    const ctl = host.ctl;
    if (!ctl.settings.enabled) return { text: '🎮 搖桿未啟用（右下 🎮 設定）', alert: false };
    if (ctl.status !== 'connected') return { text: `🎮 ${host.statusText()}`, alert: ctl.status === 'stale' || ctl.status === 'error' };
    if (processing()) return { text: '處理中…', alert: false, busy: true };
    if (lr.notice) return { text: lr.notice, alert: true };
    const zone = lr.zone ? (describeZone(lr.zone) || { label: '' }).label : '';
    return { text: `${VIEW_LABEL[activeView()] || ''}${zone ? ` › ${zone}` : ''}`, alert: false };
  }

  function renderLegend() {
    if (!enabled()) return;
    const legend = $('lrLegend');
    const status = $('lrBarStatus');
    if (!legend || !status) return;
    const legendValue = host.ctl.settings.enabled ? legendText() : '啟用搖桿後可用區域導航；滑鼠與鍵盤照常操作。';
    if (legend.textContent !== legendValue) legend.textContent = legendValue;
    const s = statusText();
    if (status.textContent !== s.text) status.textContent = s.text;
    status.dataset.alert = s.alert ? 'true' : 'false';
    status.dataset.busy = s.busy ? 'true' : 'false';
    renderHelp();
  }

  function renderHelp() {
    const help = $('lrHelp');
    if (!help) return;
    const show = enabled() && gameShown() && host.ctl.helpOpen;
    if (help.hidden === show) help.hidden = !show;
  }

  // ------------------------------------------------------------ render / reconcile
  function renderAll() {
    if (!enabled() || !host) return false;
    ensureDom();
    const bar = $('lrBar');
    const showBar = gameShown();
    if (bar && bar.hidden === showBar) bar.hidden = !showBar;
    let changed = renderSlots();
    changed = renderMapPanel() || changed;
    if (lr.confirm && !resolveSlot(lr.confirm.id)) {
      closeConfirm();
      flash('此操作目前不可用');
    }
    if (!host.ctl.padActive) hideRing();
    renderLegend();
    return changed;
  }

  function scheduleRender() {
    if (lr.renderTimer) return;
    lr.renderTimer = setTimeout(() => {
      lr.renderTimer = null;
      if (!enabled() || !host) return;
      const changed = renderAll();
      if ((changed || lr.mapStageChanged) && host.ctl.padActive) host.scheduleReconcile();
    }, 50);
  }

  /** 重繪規則：同 key → 原位；key 消失 → 同區域同索引；區域空 → 該區域的區域層；永不跨區域、永不自動落在危險操作。 */
  function reconcile() {
    const scope = host.currentScope();
    renderAll();
    if (!handles(scope)) { hideRing(); return false; }
    const ctl = host.ctl;
    ctl.lastScopeId = scope.id;
    const view = activeView();
    const zones = zonesNow(view);
    if (view !== lr.view) {
      lr.view = view;
      if (view === 'map') {
        const list = zones.find(z => z.id === 'maplist');
        lr.mapStageChanged = false;
        if (list) { enterMapList(list); return true; }
      }
      placeDefault(view, zones);
      return true;
    }
    const zone = zones.find(z => z.id === lr.zone);
    if (!zone) {
      const fallback = zones.find(z => z.id === LR.resolveZone(zones.map(z2 => z2.id), null));
      if (fallback) focusZone(fallback, { user: false });
      else { hideRing(); host.clearDomFocus(); lr.zone = null; }
      return true;
    }
    if (lr.layer === 'zone') {
      if (ctl.focusSig !== `zone:${zone.id}`) focusZone(zone);
      else drawRing(zone);
      return true;
    }
    const mem = lr.mem[zone.id] || {};
    let index;
    let user = true;
    if (zone.id === 'maplist' && lr.mapStageChanged) {
      // 來源 → 目的地（或反向）換了一份清單：從第一列開始，並視為非使用者造成的焦點變更（防連按 A）。
      lr.mapStageChanged = false;
      index = zone.items.length ? 0 : -1;
      user = false;
    } else {
      index = LR.reconcileIndex(zone.keys, mem.key, mem.index, zone.id === 'actionbar' ? dangerKeys() : null);
      if (index >= 0 && zone.keys[index] !== mem.key) user = false;
    }
    if (index < 0) {
      if (zone.id === 'maplist') focusEmptyMapList(zone);
      else focusZone(zone, { user: false });
      return true;
    }
    const el = zone.items[index];
    if (!user || ctl.focusEl !== el || !el.classList.contains('rl-pad-focus')) focusItem(zone, index, { user });
    else drawRing(zone);
    return true;
  }

  function onClear() {
    hideRing();
    clearMapTownFocus();
    lr.layer = 'zone';
    lr.view = null;
  }

  function debugState() {
    return {
      mode: displayMode, view: lr.view, zone: lr.zone, layer: lr.layer,
      itemKey: lr.zone && lr.mem[lr.zone] ? lr.mem[lr.zone].key : null,
      slots: lr.slots.map(s => ({ id: s.id, label: s.label, danger: s.danger })),
      mapStage: lr.mapList.stage, mapRows: lr.mapList.rows.map(r => r.town), mapSelected: lr.mapList.selected,
      mapPending: lr.mapList.pending, processing: processing(), confirmOpen: !!lr.confirm,
      activatedAt: lr.guard.activatedAt,
      mapRequest: lr.guard.mapRequest ? { req: lr.guard.mapRequest.req, cmd: lr.guard.mapRequest.cmd } : null,
      lastMapAck: lr.lastMapAck,
    };
  }

  window.RedlineController.attachLayer({
    init(nextHost) {
      host = nextHost;
      syncStateToken();
      ensureSettingsUi();
      setDisplayMode(displayMode, { persist: false });
      // 視窗縮放只改 <html> 的 CSS 變數（不在 MutationObserver 範圍內）：重畫區域框位置。
      window.addEventListener('resize', () => {
        if (enabled() && host.ctl.padActive) host.scheduleReconcile();
      });
    },
    enabled,
    dispatch,
    reconcile,
    renderLegend,
    scheduleRender,
    onClear,
    noteActivation,
    onMapResult,
    debugState,
  });
  window.RedlineDisplayMode = { get: () => displayMode, set: mode => setDisplayMode(mode) };
})();
