/*
 * REDLINE Joy-Con／搖桿輸入 — 瀏覽器端膠合層。
 * physical input（本機 bridge WebSocket）→ logical actions → context router（modal / map / page）
 * → 呼叫「既有」UI 元素的 click handler。不建構 action payload、不複製遊戲規則。
 * 玩家在設定面板明確啟用後才連線 bridge 並接管焦點；未啟用或未連線時 UI 完全不變。
 */
(function () {
  'use strict';
  const Core = window.RedlineControllerCore;
  if (!Core) return;

  const STORAGE_KEY = 'redline.controller.v1';
  const FOCUS_CLASS = 'rl-pad-focus';
  const FOCUSABLE = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], '
    + '[tabindex]:not([tabindex="-1"]), .card[data-card-zone]';
  const SKIP_IDS = new Set(['emergencyNewGameBtn', 'padToggleBtn']);
  const STATUS_TEXT = {
    off: '未啟用', connecting: '連線中…', connected: '已連線', stale: '訊號中斷', error: '無法連線',
  };

  const ctl = {
    settings: Core.normalizeSettings(null),
    status: 'off',
    socket: null,
    reconnectTimer: null,
    attempt: 0,
    staleTimer: null,
    input: Core.createInputState(),
    padActive: false, // 至少收到一次有效操作後才顯示/接管焦點
    helpOpen: false,
    focusEl: null,
    focusSig: null,
    focusTown: null,
    focusKind: null, // 'dom' | 'map'
    mapSnapshot: null,
    autofocusMap: false,
    lastScopeId: null,
    pageFocusMemory: null,
    observer: null,
    reconcileTimer: null,
  };

  // ------------------------------------------------------------ settings
  function loadSettings() {
    try { ctl.settings = Core.normalizeSettings(JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')); } catch { ctl.settings = Core.normalizeSettings(null); }
  }
  function saveSettings() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(ctl.settings)); } catch { /* storage may be blocked */ }
  }

  // ------------------------------------------------------------ bridge connection
  function setStatus(status) {
    if (ctl.status === status) return;
    ctl.status = status;
    renderHud();
  }

  // 失聯、停用或 stale：清空 held state；重新連線後第一筆 frame 只當 baseline。
  function resetInput() { ctl.input = Core.resetInputState(); }

  function closeSocket() {
    const socket = ctl.socket;
    ctl.socket = null;
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
      try { socket.close(); } catch { /* ignore */ }
    }
  }

  function scheduleReconnect() {
    if (!ctl.settings.enabled || ctl.reconnectTimer) return;
    const delay = Core.reconnectDelayMs(ctl.attempt);
    ctl.attempt += 1;
    ctl.reconnectTimer = setTimeout(() => { ctl.reconnectTimer = null; connect(); }, delay);
  }

  function connect() {
    if (!ctl.settings.enabled) return;
    clearTimeout(ctl.reconnectTimer);
    ctl.reconnectTimer = null;
    closeSocket();
    resetInput();
    setStatus('connecting');
    let socket;
    try { socket = new WebSocket(ctl.settings.url); } catch { setStatus('error'); scheduleReconnect(); return; }
    ctl.socket = socket;
    socket.onopen = () => { ctl.attempt = 0; resetInput(); setStatus('connected'); };
    socket.onmessage = (event) => feed(event.data);
    socket.onclose = () => {
      if (ctl.socket !== socket) return;
      ctl.socket = null;
      resetInput();
      setStatus(ctl.settings.enabled ? 'error' : 'off');
      scheduleReconnect();
    };
    socket.onerror = () => { try { socket.close(); } catch { /* ignore */ } };
  }

  function disconnect() {
    clearTimeout(ctl.reconnectTimer);
    ctl.reconnectTimer = null;
    ctl.attempt = 0;
    closeSocket();
    resetInput();
    clearFocus();
    setStatus('off');
  }

  function checkStale() {
    if (!ctl.socket || ctl.status === 'connecting' || ctl.status === 'error') return;
    if (ctl.status === 'connected' && ctl.input.armed && Core.isStale(ctl.input, performance.now())) {
      resetInput();
      setStatus('stale');
    }
  }

  /** bridge 訊息入口（真實 WebSocket 與測試共用）。只有啟用時才處理。 */
  function feed(raw) {
    if (!ctl.settings.enabled) return;
    if (document.hidden) { resetInput(); return; }
    let parsed = raw;
    if (typeof raw === 'string') { try { parsed = JSON.parse(raw); } catch { return; } }
    const frame = Core.normalizeFrame(parsed);
    if (!frame) return;
    if (ctl.status === 'stale') { resetInput(); setStatus('connected'); }
    const { state, actions } = Core.reduceFrame(ctl.input, frame, performance.now());
    ctl.input = state;
    for (const action of actions) dispatch(action);
  }

  // ------------------------------------------------------------ DOM scope / focus set
  function isShown(el) {
    if (!el || !el.isConnected) return false;
    if (el.getClientRects().length === 0) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  }

  function visibleModalIds() {
    const ids = [];
    for (const scope of Core.MODAL_SCOPES) {
      const el = document.getElementById(scope.id);
      if (!isShown(el)) continue;
      if (scope.id === 'peerActionNotice' && el.classList.contains('peer-action-notice-minimized')) continue;
      ids.push(scope.id);
    }
    return ids;
  }

  function activeGameView() {
    const tab = document.querySelector('.game-tab.active[data-view]');
    return tab ? tab.dataset.view : null;
  }

  function choiceLocked() {
    return typeof lastSupportChoiceMapHighlightPayload !== 'undefined' && !!lastSupportChoiceMapHighlightPayload;
  }

  function currentScope() {
    const modal = Core.resolveModalScope(visibleModalIds());
    if (modal) return { kind: 'modal', id: modal.id, def: modal };
    const frame = document.getElementById('strategicMapFrame');
    if (isShown(document.getElementById('gameShell')) && activeGameView() === 'map' && isShown(frame)) {
      return { kind: 'map', id: 'map' };
    }
    return { kind: 'page', id: 'page' };
  }

  function rootsFor(scope) {
    if (scope.kind === 'modal') return [document.getElementById(scope.id)];
    const roots = [];
    if (isShown(document.getElementById('gameShell'))) {
      if (choiceLocked()) {
        // 必選地圖目標時鎖住背景：分頁與回合按鈕不可用；在其他分頁時只提供「回到戰略地圖」。
        if (scope.kind === 'page') roots.push(document.querySelector('.game-tab[data-view="map"]'));
      } else {
        roots.push(document.getElementById('gameTabs'));
        if (scope.kind === 'page') roots.push(document.querySelector('.game-view.active'));
      }
    } else if (isShown(document.getElementById('lobby'))) {
      roots.push(document.getElementById('lobby'));
    }
    const peer = document.getElementById('peerActionNotice');
    if (peer && isShown(peer)) roots.push(peer);
    return roots.filter(Boolean);
  }

  function sigOf(el) {
    if (el.id) return `#${el.id}`;
    const d = el.dataset || {};
    return [el.tagName, d.view, d.cardZone, d.cardName, d.cardMode, d.cardIndex, d.marketMode, d.aiRedArmy,
      (el.textContent || '').trim().slice(0, 16)].join('|');
  }

  function collectDom(scope) {
    const seen = new Set();
    const candidates = [];
    const take = (el) => {
      if (seen.has(el)) return;
      seen.add(el);
      const rect = el.getBoundingClientRect();
      candidates.push({
        key: sigOf(el) + '@' + candidates.length,
        el,
        sig: sigOf(el),
        scope: scope.id,
        visible: isShown(el) && rect.width > 0 && rect.height > 0 && !el.closest('[inert]'),
        disabled: el.disabled === true,
        ariaDisabled: el.getAttribute('aria-disabled') === 'true',
        skip: SKIP_IDS.has(el.id) || el.hasAttribute('data-controller-skip'),
        cardCheckbox: el.tagName === 'INPUT' && el.type === 'checkbox' && !!el.closest('[data-card-zone]'),
        left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
      });
    };
    for (const root of rootsFor(scope)) {
      if (root.matches && root.matches(FOCUSABLE)) take(root);
      root.querySelectorAll(FOCUSABLE).forEach(take);
    }
    return Core.buildFocusSet(candidates, scope.id);
  }

  // ------------------------------------------------------------ map iframe protocol (parent side)
  function mapFrame() { return document.getElementById('strategicMapFrame'); }

  /** 回傳是否真的送出（沒有 iframe 或 postMessage 失敗為 false）；送出不代表 iframe 已執行。 */
  function sendToMap(cmd, extra = {}) {
    const frame = mapFrame();
    if (!frame || !frame.contentWindow) return false;
    try {
      frame.contentWindow.postMessage({ type: 'redline-controller-command', v: Core.MAP_MESSAGE_VERSION, cmd, ...extra }, window.location.origin);
      return true;
    } catch (err) { console.warn('controller: map postMessage failed', err); return false; }
  }

  window.addEventListener('message', (event) => {
    const frame = mapFrame();
    if (!frame || !Core.isTrustedMessage(event, window.location.origin, frame.contentWindow)) return;
    if (event.data.type === 'redline-controller-result') {
      // 執行結果只交給客廳模式 layer 以 req 對應；不符 schema 視為沒有收到確認。
      const result = Core.sanitizeMapResult(event.data);
      if (result && layerActive() && typeof layer.onMapResult === 'function') layer.onMapResult(result);
      return;
    }
    if (event.data.type !== 'redline-controller-map-snapshot') return;
    const snap = Core.sanitizeMapSnapshot(event.data);
    if (!snap) { ctl.mapSnapshot = null; if (layerActive()) layer.scheduleRender(); return; }
    if (ctl.mapSnapshot && snap.seq < ctl.mapSnapshot.seq) return;
    ctl.mapSnapshot = snap;
    if (layerActive()) layer.scheduleRender();
    if (ctl.padActive && ctl.autofocusMap && snap.targets.length) {
      // 用 R/SR 切進地圖後，第一份有目標的 snapshot 到達時把焦點放到地圖目標（而不是停在分頁上）。
      const scope = currentScope();
      if (scope.kind === 'map') { ctl.autofocusMap = false; applyItem(defaultItem(buildItems(scope), scope)); return; }
    }
    if (ctl.status !== 'off' && ctl.padActive) scheduleReconcile();
  });

  function collectMap() {
    const snap = ctl.mapSnapshot;
    const frame = mapFrame();
    if (!snap || snap.scope === 'none' || !frame) return [];
    const fr = frame.getBoundingClientRect();
    const scale = frame.clientWidth ? fr.width / frame.clientWidth : 1;
    const items = [];
    for (const t of snap.targets) {
      const x = fr.left + t.x * scale;
      const y = fr.top + t.y * scale;
      items.push({ key: `town:${t.town}`, kind: 'town', town: t.town, role: t.role, left: x - 6, right: x + 6, top: y - 6, bottom: y + 6 });
    }
    for (const b of snap.buttons) {
      items.push({
        key: `button:${b.id}`, kind: 'button', id: b.id,
        left: fr.left + b.x * scale, top: fr.top + b.y * scale,
        right: fr.left + (b.x + b.w) * scale, bottom: fr.top + (b.y + b.h) * scale,
      });
    }
    return items;
  }

  // ------------------------------------------------------------ focus management
  function clearDomFocus() {
    document.querySelectorAll('.' + FOCUS_CLASS).forEach(el => el.classList.remove(FOCUS_CLASS));
    const ring = document.getElementById('padButtonRing');
    if (ring) ring.hidden = true;
  }

  // 地圖 iframe 內的按鈕不在 parent DOM：用 parent 端疊一圈等大的高對比框（pointer-events:none）。
  function drawButtonRing(item) {
    const stage = document.getElementById('designStage');
    if (!stage) return;
    let ring = document.getElementById('padButtonRing');
    if (!ring) {
      ring = document.createElement('div');
      ring.id = 'padButtonRing';
      stage.appendChild(ring);
    }
    const sr = stage.getBoundingClientRect();
    const scale = stage.offsetWidth ? sr.width / stage.offsetWidth : 1;
    ring.style.left = `${(item.left - sr.left) / scale}px`;
    ring.style.top = `${(item.top - sr.top) / scale}px`;
    ring.style.width = `${(item.right - item.left) / scale}px`;
    ring.style.height = `${(item.bottom - item.top) / scale}px`;
    ring.hidden = false;
  }

  function clearFocus() {
    clearDomFocus();
    if (ctl.focusKind === 'map') sendToMap('clearFocus');
    ctl.focusEl = null;
    ctl.focusSig = null;
    ctl.focusTown = null;
    ctl.focusKind = null;
    ctl.padActive = false;
    if (layerActive()) layer.onClear();
    renderHud();
  }

  function focusDom(item) {
    clearDomFocus();
    if (ctl.focusKind === 'map') sendToMap('clearFocus');
    ctl.focusKind = 'dom';
    ctl.focusEl = item.el;
    ctl.focusSig = item.sig;
    ctl.focusTown = null;
    item.el.classList.add(FOCUS_CLASS);
    try { item.el.focus({ preventScroll: true }); } catch { /* not focusable */ }
    item.el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }

  function focusMapItem(item) {
    clearDomFocus();
    ctl.focusKind = 'map';
    ctl.focusEl = null;
    ctl.focusSig = item.key;
    if (item.kind === 'town') {
      ctl.focusTown = item.town;
      sendToMap('focus', { town: item.town });
    } else {
      ctl.focusTown = null;
      sendToMap('clearFocus');
      drawButtonRing(item);
    }
  }

  /** 目前 context 的完整焦點集合（DOM 與地圖項目統一成 rect item）。 */
  function buildItems(scope) {
    const dom = collectDom(scope).map(i => ({ ...i, kind: 'dom' }));
    const map = scope.kind === 'map' ? collectMap() : [];
    return { dom, map, all: [...dom, ...map] };
  }

  function currentKey(items) {
    if (ctl.focusKind === 'map') return items.find(i => i.key === ctl.focusSig)?.key ?? null;
    if (ctl.focusKind === 'dom') {
      const still = items.find(i => i.el === ctl.focusEl) || items.find(i => i.kind === 'dom' && i.sig === ctl.focusSig);
      return still ? still.key : null;
    }
    return null;
  }

  function applyItem(item) {
    if (!item) return;
    if (item.kind === 'dom') focusDom(item);
    else focusMapItem(item);
    renderHud();
  }

  function defaultItem(items, scope) {
    if (scope.kind === 'modal' && scope.def && scope.def.initial) {
      const initial = items.dom.find(i => i.el.matches(scope.def.initial));
      if (initial) return initial;
    }
    if (scope.kind === 'map') {
      const snap = ctl.mapSnapshot;
      const preferred = snap && snap.focusTown ? items.all.find(i => i.key === `town:${snap.focusTown}`) : null;
      return preferred || Core.pickInitial(items.map.filter(i => i.kind === 'town'))
        || Core.pickInitial(items.map) || Core.pickInitial(items.dom);
    }
    return Core.pickInitial(items.dom);
  }

  function reconcile() {
    ctl.reconcileTimer = null;
    if (!ctl.settings.enabled || !ctl.padActive) return;
    if (layerActive() && layer.reconcile()) return;
    const scope = currentScope();
    const items = buildItems(scope);
    if (scope.id !== ctl.lastScopeId) {
      // scope 改變（modal 開關、分頁切換）：記住頁面焦點，進 modal 時搶回焦點，離開時還原。
      if (ctl.lastScopeId === 'page' || ctl.lastScopeId === 'map') ctl.pageFocusMemory = { sig: ctl.focusSig, kind: ctl.focusKind };
      ctl.lastScopeId = scope.id;
      let target = null;
      if (scope.kind !== 'modal' && ctl.pageFocusMemory) {
        const mem = ctl.pageFocusMemory.sig;
        target = mem ? items.all.find(i => i.key === mem || i.sig === mem) : null;
      }
      applyItem(target || defaultItem(items, scope));
      return;
    }
    const key = currentKey(items.all);
    if (key === null) { applyItem(nearestTo(items, scope) || defaultItem(items, scope)); return; }
    // 同一個焦點但 DOM 被重繪：重新綁定到新元素並補上標示。
    const same = items.all.find(i => i.key === key);
    if (same && same.kind === 'dom' && same.el !== ctl.focusEl) applyItem(same);
    else if (same && same.kind === 'dom' && !same.el.classList.contains(FOCUS_CLASS)) same.el.classList.add(FOCUS_CLASS);
  }

  let lastRect = null;
  function nearestTo(items, scope) {
    if (!lastRect || !items.all.length) return null;
    const cx = (lastRect.left + lastRect.right) / 2;
    const cy = (lastRect.top + lastRect.bottom) / 2;
    let best = null; let bestD = Infinity;
    for (const i of items.all) {
      const d = Math.hypot((i.left + i.right) / 2 - cx, (i.top + i.bottom) / 2 - cy);
      if (d < bestD) { best = i; bestD = d; }
    }
    return best;
  }

  function scheduleReconcile() {
    if (ctl.reconcileTimer) return;
    ctl.reconcileTimer = setTimeout(reconcile, 80);
  }

  // ------------------------------------------------------------ B / cancel
  function modalCancelTarget(scope) {
    const root = document.getElementById(scope.id);
    for (const selector of scope.def.cancel) {
      if (selector === 'self') return root;
      const el = root.querySelector(selector);
      if (el && isShown(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true') return el;
    }
    return null;
  }

  // ------------------------------------------------------------ dispatch (logical → UI)
  function dispatch(action) {
    // 客廳模式的 page／map scope 由 layer 處理；modal、大廳與桌面模式維持下面的既有流程。
    if (layerActive() && layer.dispatch(action)) return;
    const logical = Core.logicalAction(action);
    if (!logical) return;
    const scope = currentScope();
    const items = buildItems(scope);
    if (logical.name === 'toggleHelp' && !(ctl.padActive && cardFocused(items))) {
      ctl.helpOpen = !ctl.helpOpen;
      renderHud();
      return;
    }
    // 第一次有效操作只負責把焦點放上去，不執行（避免第一下就誤觸）。
    if (!ctl.padActive) {
      ctl.padActive = true;
      ctl.lastScopeId = scope.id;
      if (scope.kind === 'map') sendToMap('snapshot');
      applyItem(defaultItem(items, scope));
      return;
    }
    const key = currentKey(items.all);
    const mapCancel = scope.kind === 'map' && ctl.mapSnapshot && ctl.mapSnapshot.canCancel;
    const focused = items.all.find(i => i.key === key) || null;
    const ctx = {
      scopeKind: scope.kind,
      hasFocus: key !== null,
      card: cardContext(focused),
      cancelAvailable: scope.kind === 'modal' ? !!modalCancelTarget(scope) : !!mapCancel,
      sectionsLocked: choiceLocked(),
    };
    const command = Core.routeAction(ctx, logical);
    if (!command) return;
    // 沒有焦點時只有「移動」與「取消」可直接執行（無可聚焦項目的 modal，例如卡牌預覽，仍須能用 B 關閉）。
    if (key === null && command.cmd !== 'move' && command.cmd !== 'cancel') { applyItem(defaultItem(items, scope)); return; }
    const current = items.all.find(i => i.key === key);
    if (current) lastRect = { left: current.left, right: current.right, top: current.top, bottom: current.bottom };

    let activated = false;
    switch (command.cmd) {
      case 'move': {
        const next = Core.pickDirectional(items.all, key, command.dir);
        if (next && next.key !== key) applyItem(next);
        break;
      }
      case 'activate': activated = activate(scope, items, current); break;
      case 'cardPreview': activated = previewCard(current); break;
      case 'cardToggle': activated = toggleCard(current); break;
      case 'cardMode': activated = playCardMode(current, command.mode); break;
      case 'cancel': cancel(scope); break;
      case 'section': changeSection(scope, command.step); break;
      case 'focusTurnBar': focusTurnBar(items); break;
      default: break;
    }
    // 客廳模式（例如 modal 內的 A）：只有真的執行才開始 250ms 執行冷卻；桌面模式沒有 layer，不受影響。
    if (activated && layerActive()) layer.noteActivation();
  }

  // ------------------------------------------------------------ card focus (A 預覽 / B 勾選 / 手牌 X 資源 Y 行動)
  function cardHost(item) {
    if (!item || item.kind !== 'dom' || !item.el.isConnected) return null;
    return item.el.closest('[data-card-zone]');
  }

  function cardContext(item) {
    const host = cardHost(item);
    if (!host) return null;
    return { zone: host.dataset.cardZone || '', hasToggle: !!host.querySelector('input[type="checkbox"]') };
  }

  function cardFocused(items) {
    const key = currentKey(items.all);
    return !!cardContext(items.all.find(i => i.key === key));
  }

  function isUsable(el) {
    return !!el && el.isConnected && isShown(el) && !el.disabled && el.getAttribute('aria-disabled') !== 'true'
      && !el.closest('[inert]');
  }

  /** A：只開啟既有置中卡牌預覽，不點擊卡牌內任何控制項。 */
  function previewCard(current) {
    const host = cardHost(current);
    if (!host || typeof selectCardDetail !== 'function') return false;
    selectCardDetail(host);
    scheduleReconcile();
    return true;
  }

  /** B：點擊該卡牌內既有、可見且啟用的勾選框（伺服器權威的 canSelect 已反映在 disabled）。 */
  function toggleCard(current) {
    const host = cardHost(current);
    const box = host && host.querySelector('input[type="checkbox"]');
    if (!isUsable(box)) return false;
    box.click();
    scheduleReconcile();
    return true;
  }

  /** X/Y：只在手牌卡上，點擊該卡既有的「資源」／「行動」按鈕；找不到或被停用即 fail-closed。 */
  function playCardMode(current, mode) {
    const host = cardHost(current);
    if (!host || host.dataset.cardZone !== 'hand' || !host.closest('#hand')) return false;
    const matches = [...host.querySelectorAll(`.hand-card-action-btn[data-card-mode="${mode}"]`)];
    if (matches.length !== 1) return false;
    const btn = matches[0];
    // 非紅軍奧援的 resource 位是「棄置」，不是資源使用：只接受標示為「資源」的按鈕。
    if (mode === 'resource' && (btn.textContent || '').trim() !== '資源') return false;
    if (!isUsable(btn)) return false;
    btn.click();
    scheduleReconcile();
    return true;
  }

  /** 回傳是否真的執行（click／送出地圖指令）；只聚焦文字欄位或元素已失效時為 false。 */
  function activate(scope, items, current) {
    if (!current) return false;
    if (current.kind === 'dom') {
      const el = current.el;
      if (!el.isConnected) return false;
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) { el.focus(); return false; }
      el.click();
      scheduleReconcile();
      return true;
    }
    if (current.kind === 'town') sendToMap('activate', { town: current.town });
    else sendToMap('button', { id: current.id });
    return true;
  }

  function cancel(scope) {
    if (scope.kind === 'modal') {
      const target = modalCancelTarget(scope);
      if (target) target.click();
    } else if (scope.kind === 'map') {
      sendToMap('cancel');
    }
    scheduleReconcile();
  }

  function changeSection(scope, step) {
    if (choiceLocked()) return;
    if (document.getElementById('gameShell') && isShown(document.getElementById('gameShell'))) {
      const tabs = [...document.querySelectorAll('.game-tab[data-view]')].filter(t => isShown(t) && !t.disabled);
      if (!tabs.length) return;
      const index = tabs.findIndex(t => t.classList.contains('active'));
      const nextTab = tabs[Core.cycleIndex(tabs.length, index, step)];
      ctl.autofocusMap = nextTab.dataset.view === 'map';
      nextTab.click();
      ctl.pageFocusMemory = null;
      ctl.lastScopeId = null;
      setTimeout(() => { if (ctl.padActive) { ctl.lastScopeId = null; reconcile(); } }, 160);
      return;
    }
    const regions = [...document.querySelectorAll('#lobby .lobby-column, #lobby .lobby-actions')].filter(r => isShown(r));
    if (!regions.length) return;
    const focusedRegion = ctl.focusEl ? regions.findIndex(r => r.contains(ctl.focusEl)) : -1;
    const region = regions[Core.cycleIndex(regions.length, focusedRegion, step)];
    const first = collectDom({ kind: 'page', id: 'page' }).filter(i => region.contains(i.el));
    applyItem(Core.pickInitial(first) && { ...Core.pickInitial(first), kind: 'dom' });
  }

  function focusTurnBar(items) {
    const bar = document.getElementById('turnActionButtons');
    if (!bar) return;
    const inBar = items.dom.filter(i => bar.contains(i.el));
    const first = Core.pickInitial(inBar);
    if (first) applyItem(first);
  }

  // ------------------------------------------------------------ HUD (設定入口 + 精簡提示)
  let hud = null;
  function buildHud() {
    const stage = document.getElementById('designStage');
    if (!stage || hud) return;
    hud = document.createElement('div');
    hud.id = 'padHud';
    hud.innerHTML = `
      <div id="padHint" hidden></div>
      <button id="padToggleBtn" type="button" aria-label="搖桿設定" title="搖桿設定">🎮</button>
      <div id="padPanel" hidden>
        <label class="pad-row"><input id="padEnableChk" type="checkbox"> 啟用搖桿控制</label>
        <div class="pad-row">狀態：<b id="padStatusText">未啟用</b></div>
        <label class="pad-row">Bridge 位址
          <input id="padUrlInput" type="text" spellcheck="false" autocomplete="off">
        </label>
        <div id="padUrlError" class="pad-note pad-error" hidden></div>
        <div id="padMixedNote" class="pad-note" hidden>此頁為 https，瀏覽器可能擋下 ws://（mixed content）；請改用 http 頁面或 wss bridge。</div>
        <div class="pad-row pad-actions">
          <button id="padSaveBtn" type="button">儲存</button>
          <button id="padReconnectBtn" type="button">重新連線</button>
          <button id="padResetBtn" type="button">預設</button>
        </div>
        <div class="pad-note">搖桿＝移動　A 確認　B 返回　R/SR 分頁　X 回合操作　Y 說明<br>卡牌：A 查看　B 勾選　手牌 X 資源／Y 行動<br>客廳模式：A 進入區域　ZR 回區域層　PLUS 動作列（只移焦點）</div>
      </div>`;
    stage.appendChild(hud);
    const $ = id => document.getElementById(id);
    $('padToggleBtn').addEventListener('click', () => { $('padPanel').hidden = !$('padPanel').hidden; renderHud(); });
    $('padEnableChk').addEventListener('change', (e) => setEnabled(e.target.checked));
    $('padSaveBtn').addEventListener('click', () => saveUrlFromInput());
    $('padResetBtn').addEventListener('click', () => { $('padUrlInput').value = Core.DEFAULT_BRIDGE_URL; saveUrlFromInput(); });
    $('padReconnectBtn').addEventListener('click', () => { if (ctl.settings.enabled) { ctl.attempt = 0; connect(); } });
    $('padUrlInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') saveUrlFromInput(); });
  }

  function saveUrlFromInput() {
    const input = document.getElementById('padUrlInput');
    const error = document.getElementById('padUrlError');
    const url = Core.validateBridgeUrl(input.value);
    if (!url) {
      error.textContent = '位址必須是 ws://127.0.0.1、ws://localhost 或 ws://[::1]。';
      error.hidden = false;
      return false;
    }
    error.hidden = true;
    ctl.settings.url = url;
    input.value = url;
    saveSettings();
    if (ctl.settings.enabled) connect();
    renderHud();
    return true;
  }

  function setEnabled(enabled) {
    ctl.settings.enabled = !!enabled;
    saveSettings();
    if (enabled) connect(); else disconnect();
    renderHud();
  }

  function hintText() {
    const scope = currentScope();
    if (scope.kind === 'modal') {
      const cancel = modalCancelTarget(scope);
      return `移動 搖桿　A 確認${cancel ? '　B 返回' : ''}`;
    }
    if (scope.kind === 'map') {
      return `移動 搖桿　A 選取　B 取消${choiceLocked() ? '' : '　R/SR 分頁'}`;
    }
    const focused = ctl.focusKind === 'dom' ? cardContext({ kind: 'dom', el: ctl.focusEl }) : null;
    if (focused) {
      return `移動 搖桿　A 查看${focused.hasToggle ? '　B 勾選' : ''}${focused.zone === 'hand' ? '　X 資源　Y 行動' : ''}　R/SR 分頁`;
    }
    return '移動 搖桿　A 確認　R/SR 分頁　X 回合操作';
  }

  function setText(el, text) { if (el.textContent !== text) el.textContent = text; }

  function renderHud() {
    if (!hud) return;
    if (layerActive()) layer.renderLegend();
    const $ = id => document.getElementById(id);
    $('padEnableChk').checked = ctl.settings.enabled;
    if (document.activeElement !== $('padUrlInput')) $('padUrlInput').value = ctl.settings.url;
    setText($('padStatusText'), STATUS_TEXT[ctl.status] || ctl.status);
    $('padMixedNote').hidden = !Core.mixedContentRisk(location.protocol, ctl.settings.url);
    hud.dataset.status = ctl.status;
    const hint = $('padHint');
    const show = ctl.settings.enabled && (ctl.status !== 'connected' || ctl.helpOpen || ctl.padActive);
    hint.hidden = !show;
    if (show) {
      setText(hint, ctl.status === 'connected' ? `🎮 ${hintText()}` : `🎮 ${STATUS_TEXT[ctl.status]}`);
    }
  }

  // ------------------------------------------------------------ init
  function init() {
    loadSettings();
    buildHud();
    renderHud();
    ctl.staleTimer = setInterval(checkStale, 250);
    ctl.observer = new MutationObserver((records) => {
      // 自己的 HUD／焦點 class 與客廳模式覆蓋層變動不能再觸發重算，否則會自我迴圈。
      const relevant = records.some(r => !(hud && hud.contains(r.target)) && !isOverlayNode(r.target));
      if (relevant && ctl.padActive) { scheduleReconcile(); renderHud(); }
      if (relevant && layerActive()) layer.scheduleRender();
    });
    ctl.observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class', 'disabled'] });
    document.addEventListener('visibilitychange', () => { if (document.hidden) resetInput(); });
    window.addEventListener('blur', resetInput);
    initialized = true;
    if (layer) layer.init(host);
    if (ctl.settings.enabled) connect();
  }

  // ------------------------------------------------------------ display-mode layer（客廳模式）
  // layer 由 controller_living_room.js 掛上；只呼叫這裡提供的既有焦點／卡牌／地圖函式，不另建 action 路徑。
  let layer = null;
  let initialized = false;
  function layerActive() { return !!layer && initialized && layer.enabled(); }
  function isOverlayNode(node) {
    const el = node && node.nodeType === 1 ? node : node && node.parentElement;
    return !!(el && el.closest && el.closest('[data-controller-overlay]'));
  }
  const host = {
    ctl, currentScope, buildItems, collectDom, applyItem, focusDom, clearDomFocus, defaultItem, isShown, isUsable,
    cardContext, previewCard, toggleCard, playCardMode, modalCancelTarget, sendToMap, choiceLocked, activeGameView,
    scheduleReconcile, renderHud, hintText, clearFocus,
    getMapSnapshot: () => ctl.mapSnapshot,
    statusText: () => STATUS_TEXT[ctl.status] || ctl.status,
  };
  function attachLayer(next) {
    layer = next;
    if (initialized) layer.init(host);
  }

  window.RedlineController = {
    feed, // 測試／除錯：與 bridge 訊息同路徑，且仍受「已啟用」限制
    getState: () => ({
      enabled: ctl.settings.enabled, status: ctl.status, url: ctl.settings.url, padActive: ctl.padActive, helpOpen: ctl.helpOpen,
      focusKind: ctl.focusKind, focusSig: ctl.focusSig, focusTown: ctl.focusTown,
      scope: currentScope().id, held: { ...ctl.input.held },
      livingRoom: layerActive() ? layer.debugState() : null,
    }),
    setEnabled,
    attachLayer,
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
