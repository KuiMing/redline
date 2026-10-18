/*
 * REDLINE 客廳大螢幕模式（living-room）— 瀏覽器端膠合層。
 *
 * 同一 route、同一 DOM：html[data-display="living-room"] 只切換 CSS 版面層，並為搖桿加上
 *   內容區（zone）→ 內容項目（item）兩層導航、R／SR 全域區段循環、專用快捷鍵（Capture／PLUS／B／Y）、
 *   不可聚焦的按鍵提示列、危險操作確認單、地圖兩段式目標清單。
 * 方向鍵只在內容資料（卡牌、玩家動態、根據地候選、地圖目標）間移動；按鈕類控制只由專用鍵鏡射。
 * 只呼叫 controller_ui.js 交出的既有焦點／卡牌／地圖函式與既有元素的 click()；
 * 不合成滑鼠或鍵盤事件、不建構 action payload、不新增遊戲 action target。
 * 一般 modal、大廳與桌面模式一律交回 controller_ui.js 的既有流程。
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
  // 與焦點無關的全域鍵：任何層（即使目前沒有內容區）都直接處理。
  const GLOBAL_COMMANDS = new Set(['section', 'endStep', 'factionAbility', 'zoneCycle', 'focusMenu']);
  const BLOCK_TEXT = {
    'not-selected': '先按 B 選擇這張卡，再按 Y 購買', 'buy-unavailable': '購買所選目前不可用（資源不足或未選擇）', 'card-gone': '此卡目前不可購買',
  };

  let host = null;
  let displayMode = 'desktop';

  const lr = {
    zone: null, layer: 'zone', view: null, mem: {}, returnZone: null, lastCommandZone: null,
    guard: LR.createGuard(), stateRef: undefined, stateSeq: 0, lockTimer: null,
    hints: [], hintSig: '', mapList: LR.buildMapList(null), mapSig: '', mapStageKey: '', mapStageChanged: false,
    mapFocusTown: null, notice: null, noticeTimer: null, renderTimer: null, confirm: null,
    mapReqSeq: 0, mapAckTimer: null, lastMapAck: null, sectionKey: null, lastCommand: null,
    // SL 聚焦選單：menu＝開著時的 {model, origin, sig}；
    // menuReq＝等待中的 snapshot 請求 {req, at, acked, purpose:'open'|'pick'|'refresh', origin?|key?}。
    menu: null, menuReq: null, menuTimer: null,
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
      onClear(); // 含 resetFocusMenu
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
    return qa('.purchase-card-select-button[data-purchase-index]', root)
      .filter(button => button.getAttribute('aria-pressed') === 'true').length;
  }
  function controlSource(id, el, label) {
    if (!el) return null;
    return {
      id, label: label === undefined ? text(el) : label, visible: shown(el), disabled: el.disabled === true,
      ariaDisabled: el.getAttribute('aria-disabled') === 'true', inert: !!el.closest('[inert]'),
    };
  }

  // ------------------------------------------------------------ overlay DOM
  function ensureDom() {
    if (!enabled() || $('lrBar')) return;
    const stage = $('designStage');
    if (!stage) return;
    const bar = document.createElement('div');
    bar.id = 'lrBar';
    bar.setAttribute('data-controller-overlay', '');
    bar.setAttribute('aria-label', '搖桿按鍵提示（只顯示，不接受焦點）');
    bar.hidden = true;
    bar.innerHTML = '<div id="lrBarStatus"></div><div id="lrHints"></div><div id="lrLegend"></div>';
    stage.appendChild(bar);

    const help = document.createElement('div');
    help.id = 'lrHelp';
    help.setAttribute('data-controller-overlay', '');
    help.hidden = true;
    help.innerHTML = `
      <div class="lr-help-title">搖桿操作（客廳模式）</div>
      <div>搖桿：選內容區（卡牌／玩家動態／地圖目標）；A 進入後在區內移動</div>
      <div>A：進入區域；卡牌＝查看；地圖目標＝選取／預備</div>
      <div>B：購買卡選擇／取消；奧援手牌＝棄置（⚠ 需確認）；地圖＝取消</div>
      <div>X：手牌＝資源　Y：手牌＝行動；購買卡先按 B 選擇再按 Y＝開啟購買確認；地圖目標＝建立／移動／瓦解</div>
      <div>+：發動陣營能力（例如賭徒耳語）</div>
      <div>Capture：結束行動／結束回合（⚠ 需確認，預設返回）</div>
      <div>R／SR：指揮中心→戰略地圖→戰況紀錄→我的陣營→事件卡→時代關卡</div>
      <div>SL：聚焦選單（依統治者／陣營區域跳到可建立組織的合法城鎮；只移焦點，再按 SL 或 B 返回）</div>
      <div>按下搖桿：下一個內容區</div>
      <div>ZR：戰略地圖放大一級，到最大後再按回到最小（最大地圖範圍）；其他分頁不作用</div>`;
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
    ensureConfirmDom();
  }

  /** 危險操作確認單（Capture 結束行動、B 棄置）：兩種顯示模式共用；桌面模式在第一次 Capture 時才建立。 */
  function ensureConfirmDom() {
    const stage = $('designStage');
    if (!stage || $('lrConfirmModal')) return;
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

  /**
   * SL 聚焦選單（兩種顯示模式共用；第一次開啟時才建立）。既有 modal scope 機制負責 scope lock 與方向導航：
   * 方向只在選項間移動、A 選取、B 點既有關閉 ×（× 保留滑鼠操作，但不是方向焦點）。
   */
  function ensureFocusMenuDom() {
    const stage = $('designStage');
    if (!stage || $(Core.FOCUS_MENU_MODAL_ID)) return;
    const modal = document.createElement('div');
    modal.id = Core.FOCUS_MENU_MODAL_ID;
    modal.className = 'modal-overlay lr-focus-overlay';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'lrFocusMenuTitle');
    modal.setAttribute('aria-hidden', 'true');
    modal.style.display = 'none';
    modal.innerHTML = `
      <div class="modal-glass lr-focus-glass">
        <div class="lr-focus-head">
          <div id="lrFocusMenuTitle" class="modal-title-text"></div>
          <button id="lrFocusMenuClose" type="button" class="lr-focus-close" aria-label="關閉聚焦選單" title="關閉" data-controller-skip>×</button>
        </div>
        <div class="lr-focus-lead">選範圍後，焦點移到該範圍內可建立組織的合法城鎮；不會建立、移動或瓦解（建立仍按 Y）。</div>
        <div id="lrFocusMenuSections"></div>
        <div class="lr-focus-footer">搖桿 選範圍　A 聚焦　B／SL 返回</div>
      </div>`;
    stage.appendChild(modal);
    $('lrFocusMenuClose').addEventListener('click', () => { closeFocusMenu(); if (host) host.renderHud(); });
    $('lrFocusMenuSections').addEventListener('click', (e) => {
      const option = e.target.closest('.lr-focus-option');
      if (option) pickFocusMenuOption(option.dataset.key);
    });
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

  // ------------------------------------------------------------ existing controls mirrored by dedicated keys
  function handCardOf(el) { return el ? el.closest('#hand .card[data-card-zone="hand"]') : null; }

  function handCardByKey(key) {
    if (!key) return null;
    const zone = describeZone('hand');
    if (!zone) return null;
    const index = zone.keys.indexOf(key);
    return index >= 0 ? zone.items[index] : null;
  }

  /** 手牌第一顆按鈕標示「棄置」的既有控制（一般奧援）；紅軍奧援的「資源」或其他卡牌永遠不是。 */
  function discardButtonOf(card) {
    if (!card) return null;
    const buttons = qa('.hand-card-action-btn[data-card-mode="resource"]', card);
    const index = LR.discardControlIndex(buttons.map(text));
    return index >= 0 ? buttons[index] : null;
  }

  function handModeButton(card, mode) {
    if (!card) return null;
    const buttons = qa(`.hand-card-action-btn[data-card-mode="${mode}"]`, card);
    if (buttons.length !== 1) return null;
    if (mode === 'resource' && text(buttons[0]) !== '資源') return null;
    return buttons[0];
  }

  /** PLUS：陣營能力面板的既有發動鈕或紅軍能力鈕；恰好一個可用才算。 */
  function factionAbilityTarget() {
    const candidates = [...qa('#factionActionButtons button'), $('redArmyAbilityBtn')].filter(Boolean);
    const index = LR.pickFactionAbility(candidates.map(el => ({ usable: usable(el) })));
    return index >= 0 ? candidates[index] : null;
  }

  function purchaseParts(el) {
    const card = el ? el.closest('.card[data-card-zone="purchase"]') : null;
    const toggle = card ? card.closest('.purchase-card-item')?.querySelector('.purchase-card-select-button[data-purchase-index]') : null;
    return { card, toggle, buy: $('openPurchaseConfirmBtn') };
  }

  // ------------------------------------------------------------ key-hint bar（不可聚焦，只鏡射既有、可見、啟用的控制）
  function collectHints() {
    // 只有 bridge 已連線才鏡射：off／connecting／error／stale 時快捷鍵不會執行，提示也不顯示。
    if (!gameShown() || !host.ctl.padActive || !host.bridgeConnected()) return [];
    if (focusMenuOpen()) return []; // 選單內的按鍵由 legend 說明；背景快捷鍵此時都不作用
    const sources = [];
    const el = lr.layer === 'item' ? host.ctl.focusEl : null;
    const card = el ? host.cardContext({ kind: 'dom', el }) : null;
    if (card && card.zone === 'hand') {
      const hand = handCardOf(el);
      const name = hand ? hand.dataset.cardName || '' : '';
      sources.push(controlSource('cardAction', handModeButton(hand, 'action'), `行動 ${name}`));
      sources.push(controlSource('cardResource', handModeButton(hand, 'resource'), `資源 ${name}`));
      sources.push(controlSource('cardDiscard', discardButtonOf(hand), `棄置 ${name}`));
    } else if (card && card.zone === 'purchase') {
      const { toggle, buy } = purchaseParts(el);
      const selected = toggle?.getAttribute('aria-pressed') === 'true';
      if (toggle) sources.push(controlSource('cardToggle', toggle, selected ? '取消選擇' : '選擇卡牌'));
      // Y 只在焦點卡已用 B 選擇（且選擇按鈕仍可用）時提示；未選擇時提示列只有「B 選擇卡牌」。
      if (toggle && selected && host.isUsable(toggle) && buy) sources.push(controlSource('cardBuy', buy, `${text(buy)}（開啟購買確認）`));
    } else if (lr.zone === 'maplist' && el && el.dataset.town) {
      const act = LR.mapActFor(lr.mapList.rows.find(r => r.town === el.dataset.town), lr.mapList);
      if (act) sources.push({ id: 'mapAct', label: act.label, visible: true });
    }
    const snap = host.getMapSnapshot();
    if (lr.zone === 'maplist' && activeView() === 'map' && snap && snap.canCancel) {
      const cancelBtn = snap.buttons.find(b => b.id === 'cancelDissolveChoiceBtn');
      sources.push({ id: 'mapCancel', label: cancelBtn ? cancelBtn.label : '取消選取', visible: true });
    }
    const menu = LR.buildFocusMenu(snap);
    if (menu.ok) sources.push({ id: 'focusMenu', label: `聚焦選單（${menu.total} 個目標）`, visible: true });
    const ability = factionAbilityTarget();
    if (ability) sources.push(controlSource('factionAbility', ability));
    sources.push(controlSource('endStep', $('advanceStepBtn')));
    return LR.buildKeyHints(sources.filter(Boolean));
  }

  function renderHints() {
    const hints = collectHints();
    lr.hints = hints;
    const menuOpen = focusMenuOpen();
    const sig = JSON.stringify([hints, menuOpen]);
    if (sig === lr.hintSig) return;
    lr.hintSig = sig;
    const box = $('lrHints');
    if (!box) return;
    box.textContent = '';
    if (!hints.length) {
      const empty = document.createElement('div');
      empty.className = 'lr-hint-empty';
      empty.textContent = host.ctl.padActive && host.bridgeConnected() && !menuOpen ? '目前沒有快捷操作' : '';
      box.appendChild(empty);
      return;
    }
    for (const hint of hints) {
      const el = document.createElement('div');
      el.className = 'lr-hint';
      el.dataset.hintId = hint.id;
      el.dataset.danger = hint.danger ? 'true' : 'false';
      const key = document.createElement('kbd');
      key.className = 'lr-key';
      key.textContent = hint.key;
      const label = document.createElement('span');
      label.textContent = hint.label;
      el.append(key, label);
      box.appendChild(el);
    }
  }

  // ------------------------------------------------------------ map list（兩段式，資料只來自 iframe 權威 snapshot）
  function mapRowMeta(row, list) {
    const act = LR.mapActFor(row, list);
    const yText = act ? `Y ${act.label.split(' ')[0]}` : '';
    if (row.role === 'origin') return ['可行動來源', yText].filter(Boolean).join('・');
    if (row.role === 'choice') return [list.selected === row.town ? '✔ 已選取' : '待選目標', yText].filter(Boolean).join('・');
    const parts = [LR.moveModeLabel(row.mode)];
    if (row.cost !== null && row.cost !== undefined) parts.push(`消耗 ${row.cost}`);
    if (yText) parts.push(yText);
    return parts.filter(Boolean).join('・');
  }

  function renderMapPanel() {
    const panel = $('lrMapPanel');
    if (!panel) return false;
    const visible = enabled() && host.ctl.settings.enabled && activeView() === 'map';
    if (panel.hidden === visible) panel.hidden = !visible;
    const list = activeView() === 'map' ? LR.buildMapList(host.getMapSnapshot()) : LR.buildMapList(null);
    // 只有真的換了一份清單才把焦點放回第一列；pending choice 的 A 選取不算（焦點留在剛選的那一列）。
    const stageKey = LR.mapStageKey(list);
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
      if (row.act) el.dataset.act = row.act;
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
    if (list.pending) footer = `已預備：${list.pending.from} → ${list.pending.to}　按 Y 確認移動`;
    else if (list.stage === 'destination') footer = 'A 預備移動　Y 直接移動　B 取消來源';
    else if (list.stage === 'choice') footer = list.selected ? `已選取 ${list.selected}　按 Y 執行` : 'A 選取　Y 直接執行';
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

  // ------------------------------------------------------------ zones（只有內容資料）
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

  /** 交給 LR.isDirectionalExcluded 判斷的既有控制描述：與桌面模式同一份（host.directionalFlags）。 */
  function directionalDescriptor(el) {
    return host.directionalFlags(el);
  }

  function controlsWithin(roots) {
    const out = [];
    for (const root of roots.filter(shown)) {
      for (const el of qa(CONTROL_SELECTOR, root)) {
        if (out.includes(el) || !usable(el)) continue;
        if (LR.isDirectionalExcluded(directionalDescriptor(el))) continue;
        out.push(el);
      }
    }
    return out;
  }

  function describeZone(id) {
    switch (id) {
      case 'static':
        return zoneOf(id, '常設購買區', 'cards', [$('purchaseSection')], qa('#purchaseStatic .card[data-card-zone="purchase"]').filter(shown));
      case 'random':
        return zoneOf(id, '隨機購買區', 'cards', [$('randomMarketPanel')], qa('#purchaseRandom .card[data-card-zone="purchase"]').filter(shown));
      case 'faction': {
        // 陣營能力發動鈕由 PLUS 執行，不在方向焦點內；這裡只剩根據地候選等內容選項。
        const frames = [$('factionActionPanel'), $('baseSelectionPanel')];
        return zoneOf(id, '陣營／根據地', 'controls', frames, controlsWithin(frames));
      }
      case 'hand':
        return zoneOf(id, '手牌', 'cards', [$('handPanel')], qa('#hand .card[data-card-zone="hand"]').filter(shown));
      case 'activity': {
        // 玩家動態：縮小在左下角的對手行動通知（展開鈕）。完整通知是 modal，由既有 modal 流程處理。
        const peer = $('peerActionNotice');
        const minimized = !!peer && peer.classList.contains('peer-action-notice-minimized');
        const expand = minimized ? $('peerActionNoticeMinimizeBtn') : null;
        return zoneOf(id, '玩家動態', 'controls', [peer].filter(Boolean), [expand].filter(usable));
      }
      case 'view': {
        const view = document.querySelector('.game-view.active');
        return zoneOf(id, VIEW_LABEL[activeView()] || '內容', 'controls', [view].filter(Boolean), view ? controlsWithin([view]) : [], true);
      }
      case 'maplist': {
        const panel = $('lrMapPanel');
        return zoneOf(id, '地圖目標清單', 'mapList', [panel].filter(Boolean), panel ? qa('.lr-map-row', panel) : [], true);
      }
      default:
        return null;
    }
  }

  function keysFor(zone) {
    const counts = new Map();
    return zone.items.map((el, index) => {
      if (zone.id === 'maplist') return `town:${el.dataset.town}`;
      const toggle = el.matches('.card[data-card-zone="purchase"]') ? purchaseParts(el).toggle : null;
      if (toggle) return `purchase:${toggle.dataset.purchaseIndex}`;
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
    const out = [];
    for (const id of LR.contentZonesFor(view, { choiceLock: host.choiceLocked() })) {
      const zone = describeZone(id);
      if (zone && zone.available) out.push(zone);
    }
    return out;
  }

  function zoneSummary(zone) {
    if (zone.id === 'hand') return `${zone.items.length} 張`;
    if (zone.id === 'static' || zone.id === 'random') {
      const selected = checkedPurchases(zone.frames[0]);
      return `${zone.items.length} 張${selected ? `｜已選擇 ${selected}` : ''}`;
    }
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
    if (activeView() === 'command') lr.lastCommandZone = zone.id;
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
    if (zone.id === 'maplist') focusMapTown(el.dataset.town);
    else clearMapTownFocus();
    rememberCommandZone(zone);
    if (!user) noteRedraw();
    drawRing(zone);
  }

  /** 地圖清單還沒有目標時：停在清單內容層、不聚焦任何列（A／Y 無作用）。 */
  function focusEmptyMapList(zone, { user = true } = {}) {
    clearMapTownFocus();
    host.clearDomFocus();
    host.ctl.focusKind = 'zone';
    host.ctl.focusEl = null;
    host.ctl.focusSig = 'lr:maplist-empty';
    lr.zone = zone.id;
    lr.layer = 'item';
    if (!user) noteRedraw();
    drawRing(zone);
  }

  /** 進入地圖清單內容層；清單暫時沒有目標也算已進入（停在空清單）。回傳是否成功進入。 */
  function enterMapList(zone, { user = true } = {}) {
    if (!zone || zone.kind !== 'mapList') return false;
    const mem = lr.mem.maplist || {};
    const index = LR.reconcileIndex(zone.keys, mem.key, mem.index ?? 0, null);
    if (index >= 0) focusItem(zone, index, { user });
    else focusEmptyMapList(zone, { user });
    return lr.zone === zone.id && lr.layer === 'item';
  }

  function clearZoneFocus() {
    hideRing();
    clearMapTownFocus();
    host.clearDomFocus();
    host.ctl.focusKind = 'zone';
    host.ctl.focusEl = null;
    host.ctl.focusSig = 'zone:none';
    lr.zone = null;
    lr.layer = 'zone';
  }

  function placeDefault(view, zones, { user = true } = {}) {
    lr.view = view;
    const ids = zones.map(z => z.id);
    const preferred = view === 'command' ? (lr.returnZone || lr.lastCommandZone) : view === 'map' ? 'maplist' : 'view';
    lr.returnZone = null;
    const id = LR.resolveZone(ids, preferred);
    const zone = zones.find(z => z.id === id);
    if (zone) focusZone(zone, { user });
    else clearZoneFocus();
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

  /**
   * modal scope：只有 R／SR 開啟的兩個唯讀說明 modal（事件卡、時代關卡）允許 R／SR 前往下一個區段。
   * SL 聚焦選單內：SL＝關閉（同 B）；只有方向、A、B 交回既有 modal 流程，其他鍵（R/SR、X、Y、+、Capture、ZR、STICK）一律吞掉。
   * 其他 modal 內的 SL 不作用（scope lock）。
   */
  function dispatchModal(action, scope) {
    const logical = LR.logicalAction(action);
    if (logical && scope.id === Core.FOCUS_MENU_MODAL_ID && host.ctl.padActive) {
      if (logical.name === 'focusMenu') { closeFocusMenu(); host.renderHud(); return true; }
      if (!['move', 'confirm', 'cancel'].includes(logical.name)) { host.renderHud(); return true; }
    }
    if (logical && logical.name === 'focusMenu') return host.ctl.padActive;
    const sectionKey = logical && (logical.name === 'nextSection' || logical.name === 'prevSection');
    if (sectionKey && host.ctl.padActive && gameShown() && LR.SECTION_MODALS.has(scope.id) && !host.choiceLocked()) {
      syncStateToken();
      runSection(logical.name === 'nextSection' ? 1 : -1, scope);
      host.renderHud();
      return true;
    }
    return gateModalConfirm(action);
  }

  /** 只在既有元素確實被執行後開始 250ms 冷卻；fail-closed 的 no-op 不影響下一次合法操作。 */
  function noteActivation() {
    lr.guard = LR.noteActivation(lr.guard, performance.now());
  }

  function itemContext(zone, el) {
    const card = host.cardContext({ kind: 'dom', el });
    return {
      card: card ? { zone: card.zone, hasToggle: card.hasToggle, hasDiscard: card.zone === 'hand' && !!discardButtonOf(handCardOf(el)) } : null,
      mapRow: zone.id === 'maplist',
    };
  }

  function dispatch(action) {
    const scope = host.currentScope();
    if (scope.kind === 'modal') return dispatchModal(action, scope);
    if (!handles(scope)) return false;
    syncStateToken();
    const logical = LR.logicalAction(action);
    if (!logical) return true;
    const ctl = host.ctl;
    const view = activeView();
    // ZR＝戰略地圖縮放，與焦點無關：戰略地圖上直接執行（第一下也執行；不放焦點、不改區域／層級），
    // 其他分頁完全 no-op（不放焦點、不回區域層、不切分頁）。
    if (logical.name === 'mapZoom') {
      const zoom = LR.routeLivingRoom({ scopeKind: scope.kind, view }, logical);
      if (zoom) { execute(zoom, null, -1, [], view); host.renderHud(); }
      return true;
    }
    renderAll();
    const zones = zonesNow(view);
    // 第一次有效操作（含 Capture／PLUS）只放焦點，不執行。
    if (!ctl.padActive) {
      ctl.padActive = true;
      ctl.lastScopeId = scope.id;
      placeDefault(view, zones);
      host.renderHud();
      return true;
    }
    const zone = lr.view === view ? zones.find(z => z.id === lr.zone) || null : null;
    const index = zone && lr.layer === 'item' ? currentIndex(zone) : -1;
    const el = zone && index >= 0 ? zone.items[index] : null;
    const snap = host.getMapSnapshot();
    const choiceLock = host.choiceLocked();
    const ctx = {
      scopeKind: scope.kind, view, layer: zone ? lr.layer : 'zone', zone: zone ? zone.id : null,
      choiceLock, locked: scope.kind === 'map' && choiceLock,
      mapCanCancel: !!(snap && snap.canCancel),
      item: el ? itemContext(zone, el) : null,
    };
    const command = LR.routeLivingRoom(ctx, logical);
    if (command && GLOBAL_COMMANDS.has(command.cmd)) {
      execute(command, zone, index, zones, view);
      host.renderHud();
      return true;
    }
    // 區域消失或分頁被滑鼠切換：只重新放焦點，不執行。
    if (!zone) {
      placeDefault(view, zones);
      host.renderHud();
      return true;
    }
    if (lr.layer === 'item' && index < 0 && zone.id !== 'maplist') { focusZone(zone); host.renderHud(); return true; }
    if (command) execute(command, zone, index, zones, view);
    host.renderHud();
    return true;
  }

  function execute(command, zone, index, zones, view) {
    guarded(command.cmd, () => run(command, zone, index, zones, view));
  }

  /** 處理中鎖／地圖等待／重繪冷卻／執行冷卻的共同閘門（客廳模式與桌面模式的專用鍵共用）；回傳是否真的執行。 */
  function guarded(cmd, fn) {
    const waiting = lr.guard.mapRequest;
    const verdict = LR.gate(lr.guard, performance.now(), lr.stateSeq, cmd);
    lr.guard = verdict.guard;
    if (waiting && !lr.guard.mapRequest) onMapRequestExpired(waiting); // gate 只會以逾時清掉等待中的地圖請求
    if (!verdict.allowed) {
      lr.lastCommand = { cmd, result: verdict.reason };
      if (verdict.reason === 'processing' || verdict.reason === 'map-pending') flash('處理中…請稍候');
      return false;
    }
    // 只有真的執行了（fn 回傳 true）才開始 250ms 冷卻；fail-closed no-op 與導航不記錄。
    const executed = fn() === true;
    lr.lastCommand = { cmd, result: executed ? 'executed' : 'noop' };
    if (executed && LR.ACTIVATION_GATED.has(cmd)) noteActivation();
    return executed;
  }

  /**
   * 回傳 true 表示確實執行了（click 既有控制、開啟預覽／確認單、成功進入區域）。
   * 地圖 iframe 指令一律回傳 false：是否執行要等 iframe 以同一個 req 回覆 ok:true，由 onMapResult 記錄冷卻／上鎖。
   */
  function run(command, zone, index, zones, view) {
    const el = zone && index >= 0 ? zone.items[index] : null;
    const item = el ? { kind: 'dom', el } : null;
    switch (command.cmd) {
      case 'zoneMove': {
        const id = LR.pickZone(zones.map(z => ({ id: z.id, rect: z.rect })), zone.id, command.dir);
        const next = zones.find(z => z.id === id);
        if (next && next.id !== zone.id) focusZone(next);
        return false;
      }
      case 'section': runSection(command.step, null); return false; // 導航，不啟動執行冷卻
      case 'zoneCycle': cycleContentZone(zones, zone); return false;
      case 'focusMenu': return requestFocusMenu(); // 等 iframe 回應自己 req 的 snapshot 才開啟（onMapSnapshot）
      case 'mapZoom': return requestMapZoom(); // 等 iframe 以同一個 req 回覆 ok:true（onMapResult）
      case 'endStep': return startEndStep();
      case 'factionAbility': return runFactionAbility();
      case 'enterZone': return enterZone(zone);
      case 'itemMove': moveItem(zone, index, command.dir); return false;
      case 'toZoneLayer': focusZone(zone); return false;
      case 'toggleHelp': host.ctl.helpOpen = !host.ctl.helpOpen; renderHelp(); return false;
      case 'cardPreview': return host.previewCard(item) === true;
      case 'cardToggle': return host.toggleCard(item) === true;
      case 'cardMode': {
        const played = host.playCardMode(item, command.mode) === true;
        if (played) lock();
        return played;
      }
      case 'cardDiscard': return startDiscard(zone, index);
      case 'cardBuy': return buyFromCard(el);
      case 'activate': return activateControl(el);
      case 'mapPick': return el ? mapPick(el.dataset.town) : false;
      case 'mapAct': return el ? mapAct(el.dataset.town) : false;
      case 'mapCancel': return mapCancel();
      default: return false;
    }
  }

  /**
   * A 進入區域：把焦點放到記憶／預設項目（地圖清單沒有目標時停在空清單）。
   * 成功進入即回傳 true（開始 250ms 冷卻，避免同一串連按立刻執行剛聚焦的第一項）；無法進入回傳 false。
   */
  function enterZone(zone, { user = true } = {}) {
    if (zone.kind === 'mapList') return enterMapList(zone, { user });
    if (!zone.items.length) return false;
    const mem = lr.mem[zone.id] || {};
    const index = LR.reconcileIndex(zone.keys, mem.key, mem.index ?? 0, null);
    if (index < 0) return false;
    focusItem(zone, index, { user });
    return lr.zone === zone.id && lr.layer === 'item';
  }

  /** 按下搖桿：直接進入下一個內容區（還原上次項目）。非使用者指定的項目 → 300ms 內忽略 A/B/X/Y。 */
  function cycleContentZone(zones, zone) {
    if (!zones.length) { flash('目前沒有可切換的內容區'); return; }
    const nextId = LR.cycleZone(zones.map(z => z.id), zone ? zone.id : null, 1);
    const next = zones.find(z => z.id === nextId);
    if (!next) return;
    if (zone && next.id === zone.id && lr.layer === 'item') return; // 只有這一區：留在原位
    lr.view = activeView();
    if (!enterZone(next, { user: false })) focusZone(next, { user: false });
  }

  function moveItem(zone, index, dir) {
    let next = index;
    if (zone.kind === 'cards') {
      const rects = zone.items.map(el => el.getBoundingClientRect());
      next = LR.gridMove(zone.items.length, LR.gridColumns(rects), index, dir);
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

  function activateControl(el) {
    if (!usable(el)) return false;
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) { el.focus(); return false; }
    el.click();
    // 只開啟既有視窗（例如展開玩家動態）不是伺服器動作；其餘（例如根據地候選）等下一份 state 前不再送出。
    if (!el.matches('.game-tab[data-view]') && host.currentScope().kind !== 'modal') lock();
    host.scheduleReconcile();
    return true;
  }

  // ------------------------------------------------------------ R / SR：六個全域區段
  function sectionKeyOf(tab) {
    if (tab.dataset.view && LR.sectionOfKey(`view:${tab.dataset.view}`)) return `view:${tab.dataset.view}`;
    if (tab.id === 'eventCardTab') return 'event';
    if (tab.classList.contains('era-stage-tab') && tab.dataset.eraId) return `era:${tab.dataset.eraId}`;
    return null;
  }

  function sectionStops() {
    return qa('#gameTabs .game-tab')
      .map(tab => ({ key: sectionKeyOf(tab), el: tab, usable: usable(tab) }))
      .filter(stop => stop.key);
  }

  function currentSectionKey(stops, modalScope) {
    if (modalScope && LR.SECTION_MODALS.get(modalScope.id) === 'event') return 'event';
    if (modalScope && LR.SECTION_MODALS.get(modalScope.id) === 'era') {
      if (lr.sectionKey && LR.sectionOfKey(lr.sectionKey) === 'era' && stops.some(s => s.key === lr.sectionKey)) return lr.sectionKey;
      // eslint-disable-next-line no-undef
      const viewing = typeof eraAchievementViewId !== 'undefined' && eraAchievementViewId != null ? `era:${eraAchievementViewId}` : null;
      if (viewing && stops.some(s => s.key === viewing)) return viewing;
      const first = stops.find(s => LR.sectionOfKey(s.key) === 'era');
      return first ? first.key : `view:${activeView()}`;
    }
    return `view:${activeView()}`;
  }

  /**
   * R／SR 選取下一個／上一個全域區段：分頁＝既有分頁切換；事件卡／時代關卡＝既有開啟說明 modal。
   * 從說明 modal 出發時先用該 modal 既有的關閉控制收起。必選地圖目標時只提供「戰略地圖」。
   */
  function runSection(step, modalScope) {
    const stops = sectionStops();
    const current = currentSectionKey(stops, modalScope);
    const choiceLock = host.choiceLocked();
    const key = LR.stepSection(stops, current, step, { choiceLock, view: activeView() });
    const target = key ? stops.find(s => s.key === key) : null;
    if (!target || !usable(target.el)) {
      if (choiceLock && activeView() === 'map') flash('請先完成地圖上的必選目標');
      return false;
    }
    if (modalScope) {
      const close = host.modalCancelTarget(modalScope);
      if (!close) return false;
      close.click(); // 既有關閉（事件卡背景／時代關卡「縮小」）
    }
    lr.sectionKey = key;
    target.el.click(); // 既有分頁／事件卡／時代關卡
    if (key === 'view:map') host.sendToMap('snapshot');
    host.scheduleReconcile();
    // 說明 modal 真的開啟才算一次執行：其中的 A 需間隔 250ms。
    if (!key.startsWith('view:') && host.currentScope().kind === 'modal') noteActivation();
    return true;
  }

  // ------------------------------------------------------------ Capture／PLUS／B 棄置／Y 購買
  function startEndStep() {
    if (!usable($('advanceStepBtn'))) { flash('目前不能結束這個步驟'); return false; }
    return openConfirm({ kind: 'advance' });
  }

  function runFactionAbility() {
    const el = factionAbilityTarget();
    if (!el) { flash('目前沒有可發動的陣營能力'); return false; }
    el.click(); // 既有陣營能力流程（開啟既有選擇視窗，或由既有 handler 送出）
    // 沒有開啟既有視窗代表 handler 已直接送出伺服器動作：等下一份 state 前不再送出。
    if (host.currentScope().kind !== 'modal') lock();
    host.scheduleReconcile();
    return true;
  }

  function startDiscard(zone, index) {
    const card = handCardOf(zone.items[index]);
    if (!usable(discardButtonOf(card))) { flash('這張牌目前不能棄置'); return false; }
    return openConfirm({ kind: 'discard', key: zone.keys[index], name: card.dataset.cardName || '' });
  }

  /**
   * Y：焦點購買卡已用 B 選擇（選擇按鈕仍可見可用）且既有「購買所選」可用 → 點它開啟既有購買確認單，內容是目前整份選擇；
   * 資源檢查與送出仍走既有流程。Y 不會選擇任何卡；不符一律 fail closed。
   */
  function buyFromCard(el) {
    const { card, toggle, buy } = purchaseParts(el);
    const blocker = LR.purchaseBuyBlocker({
      // selectable：與 B 選擇（host.toggleCard）同一個判斷——按鈕可見、未停用、不在 [inert] 內。
      cardShown: !!card && shown(card) && !!toggle && toggle.isConnected,
      selectable: !!toggle && host.isUsable(toggle),
      checked: toggle?.getAttribute('aria-pressed') === 'true',
      buyUsable: usable(buy),
    });
    if (blocker) { flash(BLOCK_TEXT[blocker] || '此操作目前不可用'); return false; }
    buy.click();
    host.scheduleReconcile();
    return shown($('purchaseConfirmModal'));
  }

  function mapPick(town) {
    // 只送出目前清單（最新 snapshot）裡的城鎮；iframe 執行前仍會用伺服器權威資料重驗。
    if (!lr.mapList.rows.some(r => r.town === town)) return false;
    return sendMapRequest('activate', { town }, {});
  }

  /** Y：清單列的既有地圖操作（建立組織／確認移動／瓦解組織）。iframe 重驗、預備並點既有按鈕後才回 ok:true。 */
  function mapAct(town) {
    return sendMapAct(town, LR.mapActFor(lr.mapList.rows.find(r => r.town === town), lr.mapList));
  }

  /** 桌面模式地圖目標的 Y 操作：直接取自最新 iframe 權威 snapshot 的該目標（與客廳清單列的 act 同一個來源）。 */
  function snapshotMapAct(town) {
    const snap = host.getMapSnapshot();
    const target = snap && snap.scope !== 'none' ? snap.targets.find(t => t.town === town) : null;
    return LR.mapActFor(target ? { town: target.town, act: target.act } : null, { selected: snap ? snap.selected : null });
  }

  function sendMapAct(town, act) {
    if (!act) { flash('此目標沒有可執行的地圖操作'); return false; }
    return sendMapRequest('act', { town, id: act.id }, { lock: true });
  }

  function mapCancel() {
    // 「取消瓦解」會送出伺服器 cancel_choice：iframe 回報實際走了該按鈕才上處理中鎖，新 state 抵達（或逾時）前不會重送；
    // 只取消地圖選取是純 UI，不上鎖但受 250ms 執行冷卻保護。snapshot 沒有可取消流程時不送。
    const snap = host.getMapSnapshot();
    if (!snap || !snap.canCancel) return false;
    return sendMapRequest('cancel', {}, { lockVia: 'cancelDissolveChoiceBtn' });
  }

  /** ZR 的前置條件（LR.mapZoomBlocker）以當下 DOM 與連線狀態重算；回傳阻擋原因或 null。 */
  function mapZoomBlockerNow() {
    if (!host) return 'disconnected';
    const frame = $('strategicMapFrame');
    return LR.mapZoomBlocker({
      connected: host.bridgeConnected(), gameShown: gameShown(),
      scopeKind: host.currentScope().kind, view: activeView(),
      frameReady: !!frame && frame.isConnected && !!frame.contentWindow && host.isShown(frame),
    });
  }

  /**
   * ZR（兩種顯示模式）：向戰略地圖 iframe 送帶唯一 req 的 `zoom`（放大一級，最大後回到最小；iframe 以 Leaflet API 執行並保留中心）。
   * 不需要焦點；前置條件不符 → no-op。一律回傳 false：只有同一個 req 及時回覆 ok:true、且當下仍符合前置條件，onMapResult 才記錄成功與
   * 250ms 執行冷卻（縮放不是遊戲動作，不上處理中鎖）。
   */
  function requestMapZoom() {
    if (mapZoomBlockerNow()) return false;
    return sendMapRequest('zoom', {}, {});
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
    if (out.expired) onMapRequestExpired(out.expired);
  }

  /** 等待中的地圖請求逾時（ack 計時器，或任一按鍵經過閘門時發現）：視為未執行並 fail closed。 */
  function onMapRequestExpired(expired) {
    clearTimeout(lr.mapAckTimer);
    lr.mapAckTimer = null;
    if (!host) return;
    lr.lastMapAck = { req: expired.req, cmd: expired.cmd, outcome: 'timeout', lock: false };
    if (lr.menuReq && lr.menuReq.req === expired.req) failMenuRequest(null); // 聚焦選單的 snapshot 請求逾時：晚到的回覆不再採用
    flash('地圖沒有回應，請再試一次');
    host.scheduleReconcile();
  }

  /**
   * controller_ui 交來已 sanitize 的 iframe 回覆；只有對上等待中的 req 且 ok:true 才記錄冷卻／上鎖。
   * ZR 縮放的 ok:true 到達時再驗一次前置條件：等待期間離開戰略地圖、開了 modal、停用／斷線／stale 或 iframe 被隱藏 → 視為 ok:false。
   */
  function onMapResult(result) {
    const pending = lr.guard.mapRequest;
    const zoomBlocked = pending && pending.cmd === 'zoom' && result.cmd === 'zoom' && result.req === pending.req && result.ok === true
      ? mapZoomBlockerNow() : null;
    const effective = zoomBlocked ? { ...result, ok: false, reason: zoomBlocked } : result;
    const out = LR.settleMapResult(lr.guard, performance.now(), effective);
    if (out.outcome === 'stale') return;
    lr.guard = out.guard;
    clearTimeout(lr.mapAckTimer);
    lr.mapAckTimer = null;
    lr.lastMapAck = { req: out.request.req, cmd: out.request.cmd, outcome: out.outcome, lock: out.lock, reason: effective.reason || null };
    // 聚焦選單：及時的 ok:true 只記下 acked，之後還要同一個 req 的 snapshot（onMapSnapshot）；ok:false／逾時直接 fail closed。
    if (lr.menuReq && lr.menuReq.req === out.request.req) {
      if (out.outcome === 'success') lr.menuReq.acked = true;
      else failMenuRequest(null);
    }
    if (out.lock) lock();
    if (out.outcome === 'failed') flash(out.request.cmd === 'zoom' ? '地圖目前無法縮放' : '此操作目前不可用');
    else if (out.outcome === 'timeout') flash('地圖沒有回應，請再試一次');
    host.scheduleReconcile();
    host.renderHud();
  }

  // ------------------------------------------------------------ SL 聚焦選單（兩種顯示模式共用；只移焦點）
  // 開啟、選定與開著時的刷新都先向 iframe 要一份新的權威 snapshot（帶 req）：只採用同一個 req 先及時回覆 ok:true、
  // 再於 1000ms 內送達的那一份（一般推送只觸發一次新的請求，本身不更新選單）。缺 snapshot、逾時、ok:false、
  // 不合 schema、沒有合法建立目標或分組資料不足一律 fail closed 並顯示短原因。選定後只移焦點：不選取、不建立、不移動、不瓦解。
  // 只有真的開啟選單或真的把焦點移到合法城鎮才開始 250ms 執行冷卻。

  function focusMenuReason(code) { return LR.FOCUS_MENU_REASONS[code] || LR.FOCUS_MENU_REASONS['no-targets']; }

  function focusMenuOpen() {
    const modal = $(Core.FOCUS_MENU_MODAL_ID);
    return !!lr.menu && !!modal && modal.style.display !== 'none';
  }

  /** 提示用：最新權威 snapshot 是否有可分組的合法建立目標（真正開啟時仍會重新要一份 req 綁定的 snapshot）。 */
  function focusMenuAvailable() {
    return !!host && gameShown() && LR.buildFocusMenu(host.getMapSnapshot()).ok;
  }

  /** 開啟當下的「目前焦點」城鎮（選定分組含它時保留）：客廳模式＝地圖清單焦點列；桌面模式＝地圖城鎮焦點。 */
  function focusMenuOrigin() {
    if (enabled()) return { town: activeView() === 'map' && lr.zone === 'maplist' && lr.layer === 'item' ? lr.mapFocusTown : null };
    const ctl = host.ctl;
    return { town: ctl.focusKind === 'map' && ctl.focusTown ? ctl.focusTown : null };
  }

  function finishMenuRequest() {
    lr.menuReq = null;
    clearTimeout(lr.menuTimer);
    lr.menuTimer = null;
  }

  /**
   * 聚焦選單請求 fail closed：清掉等待（晚到的回覆不再採用）。刷新失敗或回覆不合 schema（close）時一併關閉選單：
   * 畫面上的候選不能再保證是最新的權威資料。reason＝要顯示的短原因（null＝呼叫端已顯示）。
   */
  function failMenuRequest(reason, { close = false } = {}) {
    const pending = lr.menuReq;
    finishMenuRequest();
    if (pending && (close || pending.purpose === 'refresh')) closeFocusMenu();
    if (reason) flash(focusMenuReason(reason));
  }

  /**
   * 送出帶 req 的 snapshot 指令（與其他地圖指令同一個等待／逾時機制；確認成功不記錄執行冷卻）。
   * 一律回傳 false：開啟、選定或刷新都要等 onMapResult 的 ok:true 與同一個 req 的 snapshot。
   */
  function sendMenuRequest(purpose, extra) {
    sendMapRequest('snapshot', {}, { noActivation: true });
    const pending = lr.guard.mapRequest;
    if (!pending || pending.cmd !== 'snapshot' || pending.req !== lr.mapReqSeq) { // 沒有 iframe：已 fail closed
      if (purpose === 'refresh') closeFocusMenu();
      return false;
    }
    lr.menuReq = { ...extra, purpose, req: pending.req, at: pending.at, acked: false };
    clearTimeout(lr.menuTimer);
    // ok:true 已到但同一個 req 的 snapshot 在逾時前沒到：同樣 fail closed（逾時後到達的也會被 menuSnapshotVerdict 拒絕）。
    lr.menuTimer = setTimeout(() => {
      lr.menuTimer = null;
      if (lr.menuReq && lr.menuReq.req === pending.req) failMenuRequest('stale');
    }, LR.DEFAULT_GUARD_CONFIG.mapAckTimeoutMs + 40);
    return false;
  }

  /** SL（選單未開）：先做本地檢查，再向 iframe 要新的 snapshot。 */
  function requestFocusMenu() {
    if (!host) return false;
    if (!gameShown()) { flash(focusMenuReason('no-game')); return false; }
    if (host.currentScope().kind === 'modal') return false;
    if (!host.getMapSnapshot()) { flash(focusMenuReason('no-snapshot')); return false; }
    return sendMenuRequest('open', { origin: focusMenuOrigin() });
  }

  /**
   * controller_ui 交來每一份已 sanitize 的 snapshot（不合 schema 時為 null）。只有回應等待中請求、且通過
   * menuSnapshotVerdict 的那一份才會開啟／選定／刷新；選單開著時的一般推送只觸發一次新的 req 綁定刷新。
   */
  function onMapSnapshot(snap) {
    if (!host) return;
    const pending = lr.menuReq;
    const verdict = LR.menuSnapshotVerdict(pending, snap, performance.now());
    if (verdict === 'invalid') { failMenuRequest('no-group-data', { close: true }); return; }
    if (verdict === 'stale') { failMenuRequest('stale'); return; }
    if (verdict === 'accept') {
      finishMenuRequest();
      completeMenuRequest(pending, snap);
      return;
    }
    // 其他請求（含選定）等待中時不另外送：它的回覆本身就是更新的權威 snapshot。
    if (!pending && !lr.guard.mapRequest && focusMenuOpen()) sendMenuRequest('refresh', {});
  }

  function completeMenuRequest(pending, snap) {
    // 停用、清除焦點或 bridge 斷線之後才到的回覆：不開啟、不選定（resetFocusMenu 已清掉等待，這裡再擋一次）。
    if (!host.ctl.padActive || !host.bridgeConnected()) { closeFocusMenu(); return; }
    const model = LR.buildFocusMenu(snap);
    if (pending.purpose === 'open') {
      if (!gameShown() || host.currentScope().kind === 'modal') return; // 等待期間開了其他視窗：不蓋上去
      if (!model.ok) { flash(focusMenuReason(model.reason)); return; }
      if (openFocusMenu(model, pending.origin)) noteActivation(); // 真的開啟才開始 250ms 執行冷卻（之後的 A 需間隔）
      return;
    }
    if (!focusMenuOpen()) return; // 等待期間已用 B／SL／× 關閉
    if (!model.ok) { closeFocusMenu(); flash(focusMenuReason(model.reason)); return; }
    if (pending.purpose === 'refresh') { renderFocusMenu(model, { redraw: true }); return; }
    if (LR.focusMenuDrift(lr.menu.model, model)) {
      // 開啟後清單段或 pending choice 的已選城鎮變了：刷新選單、不移焦點。
      renderFocusMenu(model, { redraw: true });
      flash(focusMenuReason('changed'));
      return;
    }
    const town = LR.pickFocusMenuTown(LR.findFocusMenuGroup(model, pending.key), lr.menu.origin.town);
    if (!town) {
      // 候選在選定瞬間消失：刷新選單、不移焦點。
      renderFocusMenu(model, { redraw: true });
      flash(focusMenuReason('gone'));
      return;
    }
    closeFocusMenu();
    if (focusMapTarget(town)) noteActivation(); // 焦點真的移到合法城鎮才開始 250ms 執行冷卻
  }

  function openFocusMenu(model, origin) {
    ensureFocusMenuDom();
    const modal = $(Core.FOCUS_MENU_MODAL_ID);
    if (!modal) return false;
    lr.menu = { model, origin: origin || { town: null }, sig: '' };
    renderFocusMenu(model);
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    host.scheduleReconcile(); // 既有 modal scope：焦點移到第一個選項，背景控制不在焦點集合內
    host.renderHud();
    return true;
  }

  /**
   * 選項只來自模型（每次都是 req 綁定的新 snapshot）；內容沒變就不重建（焦點元素不換）。
   * 在游標下重建＝非使用者造成的焦點變更：300ms 內忽略 A。
   */
  function renderFocusMenu(model, { redraw = false } = {}) {
    lr.menu.model = model;
    const title = $('lrFocusMenuTitle');
    const titleText = `聚焦選單｜可建立組織 ${model.total} 個`;
    if (title.textContent !== titleText) title.textContent = titleText;
    const sig = JSON.stringify(model.sections.map(s => s.groups.map(g => [g.key, g.count])));
    if (sig === lr.menu.sig) return;
    lr.menu.sig = sig;
    if (redraw) noteRedraw();
    const box = $('lrFocusMenuSections');
    box.textContent = '';
    for (const section of model.sections) {
      const el = document.createElement('section');
      el.className = 'lr-focus-section';
      el.dataset.focusSection = section.kind;
      const head = document.createElement('div');
      head.className = 'lr-focus-section-title';
      head.textContent = section.label;
      const grid = document.createElement('div');
      grid.className = 'lr-focus-grid';
      if (!section.groups.length) {
        const empty = document.createElement('div');
        empty.className = 'lr-focus-empty';
        empty.textContent = '沒有含合法目標的項目';
        grid.appendChild(empty);
      }
      for (const group of section.groups) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'lr-focus-option';
        button.id = `lrFocusOpt-${group.kind}-${group.name}`;
        button.dataset.key = group.key;
        button.dataset.kind = group.kind;
        button.dataset.name = group.name;
        button.dataset.count = String(group.count);
        button.setAttribute('aria-label', `${section.label} ${group.name}${group.note ? `（${group.note}）` : ''}：${group.count} 個合法城鎮`);
        const name = document.createElement('span');
        name.className = 'lr-focus-name';
        name.textContent = group.name;
        button.appendChild(name);
        if (group.note) {
          const note = document.createElement('span');
          note.className = 'lr-focus-tag';
          note.textContent = group.note;
          button.appendChild(note);
        }
        const count = document.createElement('span');
        count.className = 'lr-focus-count';
        count.textContent = `${group.count} 個`;
        button.appendChild(count);
        grid.appendChild(button);
      }
      el.append(head, grid);
      box.appendChild(el);
    }
  }

  /** A（或滑鼠）選定一個選項：重新要一份 snapshot，在 completeMenuRequest 驗證後才移焦點。 */
  function pickFocusMenuOption(key) {
    if (!host || !focusMenuOpen() || typeof key !== 'string') return false;
    syncStateToken();
    return guarded('focusMenuPick', () => sendMenuRequest('pick', { key }));
  }

  /** B／×／SL 再按，或被其他視窗蓋過：關閉。焦點由既有 reconcile 還原（桌面＝scope 記憶，客廳＝區域／項目記憶）。 */
  function closeFocusMenu({ silent = false } = {}) {
    if (lr.menuReq && lr.menuReq.purpose !== 'open') finishMenuRequest(); // 等待中的選定／刷新跟著作廢
    const wasOpen = !!lr.menu;
    lr.menu = null;
    const modal = $(Core.FOCUS_MENU_MODAL_ID);
    if (modal && modal.style.display !== 'none') {
      modal.style.display = 'none';
      modal.setAttribute('aria-hidden', 'true');
    }
    // 搖桿焦點不留在隱藏的選項上：還原交給 reconcile（沒有可還原的內容時就不放焦點，例如必選地圖目標時的其他分頁）。
    const ctl = host && host.ctl;
    if (ctl && ctl.focusKind === 'dom' && ctl.focusEl && modal && modal.contains(ctl.focusEl)) {
      host.clearDomFocus();
      ctl.focusEl = null;
      ctl.focusSig = null;
      ctl.focusKind = null;
    }
    if (wasOpen && !silent && host) host.scheduleReconcile();
  }

  /**
   * 停用控制器、清除焦點、切換顯示模式或 bridge 斷線（含 stale）：關閉選單並取消等待中的開啟／選定／刷新請求，
   * 之後才到的 iframe 回覆不會再開啟或選定。silent:false＝還原開啟前的焦點（仍連著 bridge 的情況）。
   */
  function resetFocusMenu({ silent = true } = {}) {
    finishMenuRequest();
    closeFocusMenu({ silent });
  }

  function otherModalShown(id) {
    const el = $(id);
    if (!el || !host.isShown(el)) return false;
    return !(id === 'peerActionNotice' && el.classList.contains('peer-action-notice-minimized'));
  }

  /** 選單開著時離開遊戲畫面或出現其他視窗（例如伺服器推來的選擇視窗）：關閉，交給該視窗的既有 scope。 */
  function revalidateFocusMenu() {
    if (!lr.menu || !host) return;
    if (!focusMenuOpen()) { lr.menu = null; return; }
    const covered = Core.MODAL_SCOPES.some(s => s.id !== Core.FOCUS_MENU_MODAL_ID && otherModalShown(s.id));
    if (!gameShown() || covered) closeFocusMenu();
  }

  /**
   * 把焦點移到選定的合法城鎮：不在戰略地圖就用既有分頁切換過去（與 R／SR 相同的 tab click，不模擬滑鼠或鍵盤）；
   * 客廳模式聚焦地圖清單的該列，桌面模式聚焦地圖城鎮目標。找不到（已不是目標）→ fail closed，不移到非法城鎮。
   */
  function focusMapTarget(town) {
    if (activeView() !== 'map') {
      const stop = sectionStops().find(s => s.key === 'view:map');
      if (!stop || !stop.usable) { flash(focusMenuReason('map-unavailable')); host.scheduleReconcile(); return false; }
      lr.sectionKey = 'view:map';
      stop.el.click(); // 既有分頁切換
      host.sendToMap('snapshot');
    }
    const key = `town:${town}`;
    if (enabled()) {
      renderAll();
      lr.mapStageChanged = false; // 這次換清單由使用者選定，不要回到第一列
      const zone = describeZone('maplist');
      const index = zone ? zone.keys.indexOf(key) : -1;
      if (index < 0) { flash(focusMenuReason('gone')); host.scheduleReconcile(); return false; }
      lr.view = 'map';
      host.ctl.lastScopeId = 'map';
      focusItem(zone, index);
    } else {
      const scope = host.currentScope();
      const item = scope.kind === 'map' ? host.buildItems(scope).map.find(i => i.key === key) : null;
      if (!item) { flash(focusMenuReason('gone')); host.scheduleReconcile(); return false; }
      const ctl = host.ctl;
      ctl.lastScopeId = scope.id;
      ctl.pageFocusMemory = null;
      ctl.autofocusMap = false;
      host.applyItem(item);
    }
    host.renderHud();
    return true;
  }

  /** controller_ui 路徑的 SL（桌面模式 page／map／modal、客廳模式大廳）：開著就關，否則經同一個閘門開啟。 */
  function runFocusMenuKey() {
    if (!host) return false;
    if (focusMenuOpen()) { closeFocusMenu(); host.renderHud(); return true; }
    if (host.currentScope().kind === 'modal') return false;
    syncStateToken();
    guarded('focusMenu', requestFocusMenu);
    host.renderHud();
    return true;
  }

  function focusMenuDebug() {
    return {
      focusMenu: lr.menu ? { stage: lr.menu.model.stage, selected: lr.menu.model.selected, total: lr.menu.model.total,
        origin: lr.menu.origin.town, keys: lr.menu.model.sections.flatMap(s => s.groups.map(g => g.key)) } : null,
      focusMenuRequest: lr.menuReq ? { req: lr.menuReq.req, purpose: lr.menuReq.purpose, acked: lr.menuReq.acked } : null,
    };
  }

  // ------------------------------------------------------------ dangerous confirm（預設焦點＝返回）
  function playableHandCount() {
    return qa('#hand .hand-card-action-btn[data-card-mode="action"]').filter(usable).length;
  }

  /** 危險目標當下的既有控制：結束步驟按鈕，或指定手牌（以 key 綁定）的「棄置」鈕；不可用 → null。 */
  function resolveDanger(target) {
    if (!target) return null;
    if (target.kind === 'advance') {
      const el = $('advanceStepBtn');
      return usable(el) ? el : null;
    }
    if (target.kind === 'discard') {
      const btn = discardButtonOf(handCardByKey(target.key));
      return usable(btn) ? btn : null;
    }
    return null;
  }

  function dangerLabel(target, el) {
    return target.kind === 'discard' ? `棄置 ${target.name}` : text(el);
  }

  /** 確認單開著時目標改變（按鈕失效、結束步驟的文字換了）就不再算同一個操作。 */
  function dangerStillValid(pending) {
    const el = resolveDanger(pending);
    return !!el && dangerLabel(pending, el) === pending.label;
  }

  /** 開啟確認單；回傳是否真的開啟（開啟本身算一次執行，確認鍵需間隔 250ms）。 */
  function openConfirm(target) {
    ensureConfirmDom();
    const modal = $('lrConfirmModal');
    const el = resolveDanger(target);
    if (!modal || !el) return false;
    const label = dangerLabel(target, el);
    lr.confirm = { ...target, label };
    $('lrConfirmTitle').textContent = `確認：${label}`;
    $('lrConfirmBody').textContent = '送出後無法復原。要執行請向右移到「確認」再按 A；B 或「返回」取消。';
    const info = $('lrConfirmInfo');
    info.textContent = '';
    for (const line of LR.confirmInfoLines({ playableHand: target.kind === 'advance' ? playableHandCount() : 0, selectedPurchases: checkedPurchases() })) {
      const li = document.createElement('li');
      li.textContent = line;
      info.appendChild(li);
    }
    $('lrConfirmOkBtn').textContent = `確認${label}`;
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
    if (!dangerStillValid(pending)) { flash('此操作目前不可用'); return; }
    resolveDanger(pending).click(); // 既有按鈕的既有 handler
    lock();
  }

  // ------------------------------------------------------------ legend / status / help
  function legendText() {
    const ctl = host.ctl;
    const scope = host.currentScope();
    if (scope.kind === 'modal') {
      const base = host.hintText();
      return LR.SECTION_MODALS.has(scope.id) && !host.choiceLocked() ? `${base}　R/SR 下一個區段` : base;
    }
    if (!ctl.padActive) return '任意鍵開始：先選內容區，A 進入；R/SR 切換區段';
    const view = activeView();
    if (!lr.zone) return host.choiceLocked() ? '必選地圖目標：按 R／SR 前往戰略地圖' : '此分頁沒有內容區　R/SR 切換區段';
    if (lr.layer === 'zone') {
      return `搖桿 選內容區　A 進入　按下搖桿 下一區　R/SR 區段　Y 說明${view === 'map' ? '　ZR 放大地圖（循環）' : ''}`;
    }
    if (lr.zone === 'maplist') {
      const stage = lr.mapList.stage;
      if (stage === 'destination') return '↑↓ 選目的地　A 預備　Y 移動　B 取消來源　ZR 放大地圖（循環）';
      if (stage === 'choice') return '↑↓ 選目標　A 選取　Y 執行　B 取消／返回　ZR 放大地圖（循環）';
      if (stage === 'source') return '↑↓ 選來源　A 選取　B 返回　ZR 放大地圖（循環）　R/SR 區段';
      return '沒有可操作的地圖目標　ZR 放大地圖（循環）　R/SR 區段';
    }
    const card = ctl.focusEl ? host.cardContext({ kind: 'dom', el: ctl.focusEl }) : null;
    if (card && card.zone === 'hand') return '←→ 選牌　A 查看　X 資源　Y 行動　B 棄置（奧援）　按下搖桿 下一區';
    if (card) return '←→ 選牌　A 查看　B 選擇／取消　選擇後 Y 購買所選　按下搖桿 下一區';
    return 'A 確認　B 回區域層　R/SR 區段';
  }

  function statusText() {
    const ctl = host.ctl;
    if (!ctl.settings.enabled) return { text: '🎮 搖桿未啟用（右下 🎮 設定）', alert: false };
    if (ctl.status !== 'connected') {
      return { text: `🎮 ${host.statusText()}`, alert: ctl.status === 'stale' || ctl.status === 'error' || ctl.status === 'unbound' };
    }
    if (processing()) return { text: '處理中…', alert: false, busy: true };
    if (lr.notice) return { text: lr.notice, alert: true };
    const zone = lr.zone ? (describeZone(lr.zone) || { label: '' }).label : '';
    const badge = host.bindingBadge(); // 這個分頁綁定的手把（左右＋埠）
    return { text: `${badge ? `🎮 ${badge}｜` : ''}${VIEW_LABEL[activeView()] || ''}${zone ? ` › ${zone}` : ''}`, alert: false };
  }

  function renderLegend() {
    if (!enabled()) return;
    const legend = $('lrLegend');
    const status = $('lrBarStatus');
    if (!legend || !status) return;
    const legendValue = host.ctl.settings.enabled ? legendText() : '啟用搖桿後可用內容區導航；滑鼠與鍵盤照常操作。';
    if (legend.textContent !== legendValue) legend.textContent = legendValue;
    const s = statusText();
    if (status.textContent !== s.text) status.textContent = s.text;
    status.dataset.alert = s.alert ? 'true' : 'false';
    status.dataset.busy = s.busy ? 'true' : 'false';
    renderHints();
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
    const changed = renderMapPanel();
    if (lr.confirm && !dangerStillValid(lr.confirm)) {
      closeConfirm();
      flash('此操作目前不可用');
    }
    revalidateFocusMenu();
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

  /** 重繪規則：同 key → 原位；key 消失 → 同區域同索引；區域空 → 該區域的區域層；永不跨區域。 */
  function reconcile() {
    const scope = host.currentScope();
    renderAll();
    if (!handles(scope)) { hideRing(); return false; }
    const ctl = host.ctl;
    ctl.lastScopeId = scope.id;
    const view = activeView();
    const zones = zonesNow(view);
    if (view !== lr.view) {
      // 分頁切換（R／SR 或滑鼠）：焦點落點不是使用者直接指定 → 300ms 內忽略 A/B/X/Y。
      lr.view = view;
      if (view === 'map') {
        const list = zones.find(z => z.id === 'maplist');
        lr.mapStageChanged = false;
        if (list) { enterMapList(list, { user: false }); return true; }
      }
      placeDefault(view, zones, { user: false });
      return true;
    }
    const zone = zones.find(z => z.id === lr.zone);
    if (!zone) {
      const fallback = zones.find(z => z.id === LR.resolveZone(zones.map(z2 => z2.id), null));
      if (fallback) focusZone(fallback, { user: false });
      else clearZoneFocus();
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
      // 來源 → 目的地（或反向）換了一份清單：從第一列開始，並視為非使用者造成的焦點變更（防連按 A／Y）。
      lr.mapStageChanged = false;
      index = zone.items.length ? 0 : -1;
      user = false;
    } else {
      index = LR.reconcileIndex(zone.keys, mem.key, mem.index, null);
      if (index >= 0 && zone.keys[index] !== mem.key) user = false;
    }
    if (index < 0) {
      if (zone.id === 'maplist') focusEmptyMapList(zone, { user: false });
      else focusZone(zone, { user: false });
      return true;
    }
    const el = zone.items[index];
    if (!user || ctl.focusEl !== el || !el.classList.contains('rl-pad-focus')) focusItem(zone, index, { user });
    else drawRing(zone);
    return true;
  }

  function onClear() {
    resetFocusMenu();
    hideRing();
    clearMapTownFocus();
    lr.layer = 'zone';
    lr.view = null;
  }

  // ------------------------------------------------------------ 桌面模式共用（同一套既有流程與閘門）
  /** 桌面模式的 Capture／PLUS：回傳 'endStep'｜'factionAbility'；其他按鍵 null。 */
  function desktopShortcutOf(action) {
    const logical = LR.logicalAction(action);
    return logical && (logical.name === 'endStep' || logical.name === 'factionAbility') ? logical.name : null;
  }

  /** 桌面模式的 Capture（既有結束行動＋危險確認）／PLUS（唯一可用的既有陣營能力）：經過與客廳模式相同的閘門。 */
  function runDesktopShortcut(name) {
    if (enabled() || !host || !gameShown() || (name !== 'endStep' && name !== 'factionAbility')) return false;
    syncStateToken();
    execute({ cmd: name }, null, -1, [], activeView());
    return true;
  }

  /** 桌面模式購買卡 Y：與客廳模式同一個 buyFromCard 與閘門（焦點卡須已用 B 選擇；只開啟既有購買確認單）。 */
  function runDesktopCardBuy(el) {
    if (enabled() || !host || !gameShown() || !el) return false;
    syncStateToken();
    return guarded('cardBuy', () => buyFromCard(el));
  }

  /**
   * 桌面模式地圖城鎮目標的 Y：與客廳模式同一條 iframe `act`＋req 確認路徑與閘門。一律回傳 false（尚未執行）：
   * 只有 iframe 以同一個 req 回覆 ok:true 才由 onMapResult 記錄冷卻並上處理中鎖；沒有 act、沒有 iframe、ok:false、逾時一律 fail closed。
   */
  function runDesktopMapAct(town) {
    if (enabled() || !host || !gameShown() || typeof town !== 'string') return false;
    syncStateToken();
    return guarded('mapAct', () => sendMapAct(town, snapshotMapAct(town)));
  }

  /**
   * 桌面模式的 ZR（controller_ui 只在地圖 scope 呼叫）：與客廳模式同一條 `zoom`＋req 確認路徑與閘門。一律回傳 false（尚未執行）：
   * 只有 iframe 以同一個 req 回覆 ok:true 且仍符合前置條件，onMapResult 才記錄成功與冷卻。
   */
  function runDesktopMapZoom() {
    if (enabled() || !host || !gameShown()) return false;
    syncStateToken();
    return guarded('mapZoom', requestMapZoom);
  }

  /** 桌面模式提示：焦點城鎮目標的 Y 操作文字（例如「建立組織 新北」）；沒有則 null。 */
  function desktopMapActLabel(town) {
    const act = host && typeof town === 'string' ? snapshotMapAct(town) : null;
    return act ? act.label : null;
  }

  /** 桌面模式提示列用：專用鍵 fail closed 的原因（1.8 秒後自動清除）。 */
  function notice() { return lr.notice; }

  /** 除錯／驗證：桌面模式專用鍵（Capture／+／購買卡 Y／地圖 Y／ZR）共用的閘門狀態（唯讀）。 */
  function shortcutState() {
    return {
      processing: processing(), activatedAt: lr.guard.activatedAt, notice: lr.notice, lastCommand: lr.lastCommand,
      mapRequest: lr.guard.mapRequest ? { req: lr.guard.mapRequest.req, cmd: lr.guard.mapRequest.cmd } : null, lastMapAck: lr.lastMapAck,
      redrawAt: lr.guard.redrawAt, ...focusMenuDebug(),
    };
  }

  /** 桌面模式的 R／SR：與客廳模式同一個六區段環；回傳是否真的切到下一個區段。 */
  function runSectionRing(step, modalScope) {
    if (!host || !gameShown()) return false;
    syncStateToken();
    return runSection(step < 0 ? -1 : 1, modalScope || null);
  }

  function isSectionModal(id) { return LR.SECTION_MODALS.has(id); }

  /** 桌面模式：確認單開著時，既有按鈕失效或換了步驟就關閉；聚焦選單被其他視窗蓋過就關閉（客廳模式由 renderAll 處理）。 */
  function revalidateConfirm() {
    if (lr.confirm && !dangerStillValid(lr.confirm)) closeConfirm();
    revalidateFocusMenu();
  }

  function debugState() {
    return {
      mode: displayMode, view: lr.view, zone: lr.zone, layer: lr.layer,
      itemKey: lr.zone && lr.mem[lr.zone] ? lr.mem[lr.zone].key : null,
      zones: host && gameShown() ? zonesNow(activeView()).map(z => z.id) : [],
      hints: lr.hints.map(h => ({ id: h.id, key: h.key, label: h.label, danger: h.danger })),
      mapStage: lr.mapList.stage, mapRows: lr.mapList.rows.map(r => r.town), mapActs: lr.mapList.rows.map(r => r.act || null),
      mapSelected: lr.mapList.selected, mapPending: lr.mapList.pending, processing: processing(),
      confirmOpen: !!lr.confirm, confirm: lr.confirm ? { kind: lr.confirm.kind, label: lr.confirm.label, key: lr.confirm.key || null } : null,
      activatedAt: lr.guard.activatedAt, redrawAt: lr.guard.redrawAt,
      mapRequest: lr.guard.mapRequest ? { req: lr.guard.mapRequest.req, cmd: lr.guard.mapRequest.cmd } : null,
      lastMapAck: lr.lastMapAck, sectionKey: lr.sectionKey, lastCommand: lr.lastCommand, ...focusMenuDebug(),
      // DOM 變動後的 80ms reconcile／50ms render 尚未跑完：zone／layer／itemKey 仍是重繪前的值（輸入一律以當下 DOM 重新解析）。
      reconcilePending: !!(host && host.ctl.reconcileTimer) || !!lr.renderTimer,
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
    desktopShortcutOf,
    runDesktopShortcut,
    runDesktopCardBuy,
    runDesktopMapAct,
    runDesktopMapZoom,
    desktopMapActLabel,
    notice,
    shortcutState,
    runSectionRing,
    isSectionModal,
    revalidateConfirm,
    onMapSnapshot,
    runFocusMenuKey,
    focusMenuAvailable,
    resetFocusMenu,
  });
  window.RedlineDisplayMode = { get: () => displayMode, set: mode => setDisplayMode(mode) };
})();
