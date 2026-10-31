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
  // 每個分頁（玩家）自己的手把選擇：sessionStorage（重新整理仍在，不和同一瀏覽器的其他分頁共用）。
  const CLAIM_STORAGE_KEY = 'redline.controller.claim.v1';
  const FOCUS_CLASS = 'rl-pad-focus';
  const FOCUSABLE = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], '
    + '[tabindex]:not([tabindex="-1"]), .card[data-card-zone]';
  const SKIP_IDS = new Set(['emergencyNewGameBtn', 'padToggleBtn']);
  // 導覽列「Joy-Con 說明」按鈕：R／SR 環的額外焦點（focusKind 'help'；不是區段、不在方向焦點集合內），A 開啟說明圖。
  const HELP_ENTRY_ID = 'joyconHelpBtn';
  const HELP_RING_KEY = 'joyconHelp'; // = RedlineLivingRoomCore.RING_HELP_KEY（layer.runSectionRing 到達說明按鈕時的回傳值）
  // unbound＝bridge v2 已連線但這個分頁還沒有手把：輸入一律丟棄（只有 connected 才處理）。
  const STATUS_TEXT = {
    off: '未啟用', connecting: '連線中…', connected: '已連線', unbound: '未選擇手把', stale: '訊號中斷', error: '無法連線',
  };
  const NO_BINDING = Object.freeze({ mode: 'legacy', owned: null, side: null });
  // socket 開啟後、收到 v2 roster 前：假設是舊版 bridge（唯一一支右 Joy-Con）；新版 bridge 在送 roster 前不送任何 frame。
  const LEGACY_BINDING = Object.freeze({ mode: 'legacy', owned: Core.LEGACY_CONTROLLER_ID, side: 'right' });

  const ctl = {
    settings: Core.normalizeSettings(null),
    status: 'off',
    socket: null,
    reconnectTimer: null,
    attempt: 0,
    staleTimer: null,
    input: Core.createInputState(),
    inputKey: null, // 目前 reducer 屬於哪一支手把／哪一個 epoch（換了就重新 baseline）
    binding: NO_BINDING, // {mode:'legacy'|'v2', owned, side}：這個分頁擁有的手把（bridge roster 為準）
    roster: null,
    claimPref: Core.normalizeClaimPref(null),
    claimInFlight: null,
    claimTimer: null,
    claimNotice: null,
    autoClaimSig: null,
    // 起始畫面導覽（start_flow_ui.js 以 setStartNav 開關）：恰好一支有訊號的 Joy-Con 時自動 claim 它操作開始流程。
    // 未啟用搖桿控制時只為此開一條暫時連線（不寫入設定）；navClaim＝自動 claim 的那一支（不存成手把偏好、不綁席位）。
    startNav: false,
    navPreferred: null, // 重新開始沿用的 P1：起始導覽只拿這一支（start_flow_ui.js 提供；沒有＝恰好一支的既有規則）
    navClaim: null,
    // 已送出的起始導覽 claim。即使離開起始流程時 claim 尚未完成，也不得把晚到的 ownership 當成一般手把並保存。
    navTransientClaim: null,
    // 導覽 release 後，不讓預設 auto 模式立刻把同一支手把搶回來。既有明確 id 偏好不受影響。
    navAutoBlock: null,
    navOff: false, // 玩家在 HUD 取消勾選「啟用搖桿控制」：這次起始畫面不再自動連線
    navManual: false, // 玩家在 HUD 自己選手把：這次起始畫面不再自動 claim／release
    padActive: false, // 至少收到一次有效操作後才顯示/接管焦點
    helpOpen: false,
    focusEl: null,
    focusSig: null,
    focusTown: null,
    focusKind: null, // 'dom' | 'map' | 'browse'（SL 全域地圖聚焦的城鎮：只看，不在 action 焦點集合內）
    browseTargets: null, // 'browse' 焦點建立時的地圖目標簽章（Core.mapTargetsSig）；目標改變就交回既有規則
    mapSnapshot: null,
    autofocusMap: false,
    lastScopeId: null,
    pageFocusMemory: null,
    observer: null,
    reconcileTimer: null,
    choiceSnapTimer: null, // 必選地圖目標切到戰略地圖後補要 snapshot 的計時器（有目標的 snapshot 到達即停止）
    // 遊戲選單：stickHold＝按住搖桿按鈕的長按累積（Core.stepStickHold）；menuGate＝開啟／換層級時仍按住的鍵（放開前不作用）。
    stickHold: Core.createStickHold(),
    menuGate: Core.createMenuGate(null),
  };

  // ------------------------------------------------------------ settings
  function loadSettings() {
    try { ctl.settings = Core.normalizeSettings(JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')); } catch { ctl.settings = Core.normalizeSettings(null); }
  }
  function saveSettings() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(ctl.settings)); } catch { /* storage may be blocked */ }
  }
  function loadClaimPref() {
    try { ctl.claimPref = Core.normalizeClaimPref(JSON.parse(sessionStorage.getItem(CLAIM_STORAGE_KEY) || 'null')); } catch { ctl.claimPref = Core.normalizeClaimPref(null); }
  }
  function saveClaimPref(pref) {
    ctl.claimPref = Core.normalizeClaimPref(pref);
    try { sessionStorage.setItem(CLAIM_STORAGE_KEY, JSON.stringify(ctl.claimPref)); } catch { /* storage may be blocked */ }
  }

  // ------------------------------------------------------------ bridge connection
  /** 是否要連 bridge：玩家啟用搖桿控制，或起始畫面導覽（玩家沒在 HUD 關掉）。 */
  function live() { return ctl.settings.enabled || (ctl.startNav && !ctl.navOff); }
  /** 起始畫面導覽接管這個分頁的 claim（取代記住的手把偏好與 autoClaimDecision）。 */
  function navManaged() { return live() && ctl.startNav && !ctl.navManual; }

  function setStatus(status) {
    if (ctl.status === status) return;
    ctl.status = status;
    // bridge 不再是 connected（停用、斷線、重連中、stale）：SL 聚焦選單關閉並取消等待中的請求（兩種顯示模式）。
    if (status !== 'connected' && layer && initialized && typeof layer.resetFocusMenu === 'function') layer.resetFocusMenu({ silent: !ctl.padActive });
    renderHud();
  }

  // 失聯、停用、stale、換手把：清空 held state；之後第一筆 frame 只當 baseline。
  function resetInput() { ctl.input = Core.resetInputState(); ctl.inputKey = null; ctl.stickHold = Core.createStickHold(); }

  function resetBinding(binding) {
    ctl.binding = binding;
    ctl.roster = null;
    ctl.claimInFlight = null;
    ctl.autoClaimSig = null;
    ctl.navClaim = null; // 換連線＝bridge 已釋放這條連線擁有的手把
    ctl.navTransientClaim = null;
    clearTimeout(ctl.claimTimer);
    ctl.claimTimer = null;
  }

  function closeSocket() {
    const socket = ctl.socket;
    ctl.socket = null;
    resetBinding(NO_BINDING);
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
      try { socket.close(); } catch { /* ignore */ }
    }
  }

  function scheduleReconnect() {
    if (!live() || ctl.reconnectTimer) return;
    const delay = Core.reconnectDelayMs(ctl.attempt);
    ctl.attempt += 1;
    ctl.reconnectTimer = setTimeout(() => { ctl.reconnectTimer = null; connect(); }, delay);
  }

  function connect() {
    if (!live()) return;
    clearTimeout(ctl.reconnectTimer);
    ctl.reconnectTimer = null;
    closeSocket();
    resetInput();
    setStatus('connecting');
    let socket;
    try { socket = new WebSocket(ctl.settings.url); } catch { setStatus('error'); scheduleReconnect(); return; }
    ctl.socket = socket;
    socket.onopen = () => {
      ctl.attempt = 0;
      resetInput();
      resetBinding(LEGACY_BINDING);
      // 新版 bridge 收到 hello 才把這個連線當 v2（之後只送 roster 與本分頁擁有的手把 frame）；舊版 bridge 不讀 client 訊息。
      try { socket.send(JSON.stringify(Core.bridgeHello())); } catch { /* ignore */ }
      setStatus('connected');
    };
    socket.onmessage = (event) => ingest(event.data, socket);
    socket.onclose = () => {
      if (ctl.socket !== socket) return;
      ctl.socket = null;
      resetBinding(NO_BINDING);
      resetInput();
      setStatus(live() ? 'error' : 'off');
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

  function bridgeOpen() { return !!ctl.socket && ctl.socket.readyState === 1; } // WebSocket.OPEN

  /** 快捷鍵提示與執行的必要條件：啟用、connected 且目前 bridge socket 開著。 */
  function bridgeConnected() {
    return Core.bridgeConnected({ enabled: live(), status: ctl.status, socketOpen: bridgeOpen() });
  }

  /**
   * 所有輸入的共同入口（bridge 訊息與公開 feed()）。只有已連線時才進 reduceFrame；
   * off／connecting／error／失聯一律丟棄；stale 只能由目前 bridge socket 自己的 frame 恢復，且那一筆只當 baseline。
   */
  function ingest(raw, source) {
    if (!live()) return;
    let parsed = raw;
    if (typeof raw === 'string') { try { parsed = JSON.parse(raw); } catch { return; } }
    const msg = Core.classifyBridgeMessage(parsed, ctl.binding.mode);
    if (!msg) return;
    const fromBridge = !!source && source === ctl.socket;
    // 手把清單與 claim 結果只接受目前的 bridge socket（公開 feed() 不能改變綁定）。
    if (msg.kind === 'roster') { if (fromBridge) applyRoster(msg.roster); return; }
    if (msg.kind === 'claim') { if (fromBridge) applyClaimResult(msg); return; }
    if (document.hidden) { resetInput(); return; }
    // 未啟用搖桿控制、只為起始畫面導覽開的連線：只接受 bridge v2 roster 裡自己擁有的那一支（不收舊版 bridge 的無身份 frame）。
    if (!ctl.settings.enabled && ctl.binding.mode !== 'v2') return;
    // 只有這個分頁擁有的那一支手把能進 reducer；其他手把（或左右不符）的 frame 一律丟棄。
    if (!Core.acceptControllerFrame(ctl.binding, msg)) return;
    const gate = Core.bridgeInputGate({ enabled: live(), status: ctl.status, socketOpen: bridgeOpen(), fromBridge });
    if (gate === 'drop') return;
    if (gate === 'recover') { resetInput(); setStatus('connected'); }
    // 換了手把或同一支重新連線（epoch 改變）：先清空，這一筆只當 baseline。
    const now = performance.now();
    const step = Core.stepControllerInput({ input: ctl.input, key: ctl.inputKey }, msg, now);
    ctl.input = step.pad.input;
    ctl.inputKey = step.pad.key;
    for (const action of trackStickHold(step.actions, now)) dispatch(action);
  }

  // ------------------------------------------------------------ controller claim（bridge v2；bridge 是擁有權的權威）
  function applyRoster(roster) {
    const before = ctl.binding.owned;
    ctl.roster = roster;
    const owned = roster.owned ? roster.controllers.find(c => c.id === roster.owned) : null;
    ctl.binding = { mode: 'v2', owned: owned ? owned.id : null, side: owned ? owned.side : null };
    if (roster.lost) ctl.claimNotice = Core.lostReasonText(roster.lost.reason);
    if (!owned) {
      ctl.navTransientClaim = null;
      if (ctl.status === 'connected' || ctl.status === 'stale') { resetInput(); setStatus('unbound'); }
    } else if (owned.id !== before) {
      // 記住：重連時只會再 claim 同一支，不會改拿別支。起始畫面導覽自動拿的那一支不記住（之後的席位綁定另由配對決定）。
      if (owned.id !== ctl.navClaim && owned.id !== ctl.navTransientClaim) saveClaimPref({ mode: 'id', id: owned.id });
      ctl.claimNotice = null;
      resetInput();
      setStatus(owned.status === 'active' ? 'connected' : 'stale');
    } else if (owned.status === 'stale' && ctl.status === 'connected') {
      resetInput(); // 只清這一支的狀態；恢復時由 bridge socket 的 frame 回到 connected（第一筆只當 baseline）
      setStatus('stale');
    }
    maybeAutoClaim();
    renderHud();
  }

  function applyClaimResult(result) {
    clearTimeout(ctl.claimTimer);
    ctl.claimTimer = null;
    ctl.claimInFlight = null;
    if (!result.ok) ctl.claimNotice = Core.claimReasonText(result.reason);
    else if (result.request !== 'release') ctl.claimNotice = null;
    renderHud(); // 綁定以 bridge 接著送來的 roster 為準
  }

  function sendClaim(message) {
    const socket = ctl.socket;
    if (!socket || socket.readyState !== 1 || ctl.binding.mode !== 'v2') return false;
    try { socket.send(JSON.stringify({ ...message, v: Core.BRIDGE_PROTOCOL_VERSION })); } catch { return false; }
    clearTimeout(ctl.claimTimer);
    ctl.claimInFlight = message.type;
    ctl.claimTimer = setTimeout(() => { ctl.claimTimer = null; ctl.claimInFlight = null; maybeAutoClaim(); renderHud(); }, 2000);
    return true;
  }

  /** 記住的手把或舊版相容預設（唯一一支右 Joy-Con）；同一份清單只自動嘗試一次。 */
  function maybeAutoClaim() {
    if (ctl.binding.mode !== 'v2' || !bridgeOpen()) return;
    if (navManaged()) { syncNavClaim(); return; }
    if (ctl.claimInFlight) return;
    // 客廳輪流大廳（hotseat_ui.js）：主連線只 claim 目前席位綁定的那一支；單手把自動 claim 不得搶走綁定流程。
    if (gate && initialized && typeof gate.managesClaims === 'function' && gate.managesClaims()) { ctl.autoClaimSig = null; return; }
    const decision = Core.autoClaimDecision(ctl.claimPref, ctl.roster);
    if (!decision) { ctl.autoClaimSig = null; return; }
    if (decision.type === 'claim' && decision.controller === ctl.navAutoBlock) return;
    const sig = JSON.stringify([decision, ctl.roster.controllers]);
    if (sig === ctl.autoClaimSig) return;
    ctl.autoClaimSig = sig;
    sendClaim(decision);
  }

  /**
   * 起始畫面導覽：恰好一支有訊號、沒人使用的手把 → claim；擁有的那支不再是唯一候選（多支、stale、消失）→ 立刻停止接受
   * 它的輸入（unbound）並 release。不送任何 server mutation、不綁定玩家席位。
   */
  function syncNavClaim() {
    const decision = Core.startNavDecision(ctl.roster, ctl.binding.owned, ctl.navPreferred);
    if (!decision) return;
    if (decision.type === 'release') { revokeNav(); return; }
    if (ctl.claimInFlight) return;
    ctl.navClaim = decision.controller;
    ctl.navTransientClaim = decision.controller;
    sendClaim(decision);
  }

  function revokeNav() {
    const released = ctl.navClaim || ctl.navTransientClaim || ctl.binding.owned;
    if (released && !(ctl.claimPref.mode === 'id' && ctl.claimPref.id === released)) ctl.navAutoBlock = released;
    ctl.navClaim = null;
    resetInput();
    clearFocus();
    ctl.padActive = false; // 下一次取得導覽時第一下仍只放焦點
    if (ctl.status === 'connected' || ctl.status === 'stale') setStatus('unbound'); // 之後的 frame 一律丟棄，不等 bridge 回覆
    if (ctl.claimInFlight !== 'release') sendClaim({ type: 'release' });
  }

  /**
   * start_flow_ui.js：起始畫面（尚未進入正式 SL＋SR 配對）顯示中＝on；離開、進入配對或改用既有 session＝off。
   * opts.preferred：重新開始沿用的 P1 手把（只認這一支）；沒給＝恰好一支有訊號的既有規則。
   */
  function setStartNav(on, opts) {
    const next = !!on;
    const preferred = opts && Core.isControllerId(opts.preferred) ? opts.preferred : null;
    if (preferred !== ctl.navPreferred) {
      ctl.navPreferred = preferred;
      if (initialized && next && next === ctl.startNav) maybeAutoClaim(); // 同一畫面改了偏好：立即重新判定（不是 P1 的會被 release）
    }
    // init() 之前（設定與 bridge 位址尚未載入）只記下，由 init() 依 live() 連線；不可先連預設位址。
    if (!initialized) { ctl.startNav = next; return; }
    if (next === ctl.startNav) { if (next && live() && !ctl.socket && !ctl.reconnectTimer) connect(); return; }
    ctl.startNav = next;
    ctl.navOff = false;
    ctl.navManual = false;
    if (next) {
      if (!ctl.socket && !ctl.reconnectTimer) connect();
      else maybeAutoClaim();
    } else if (!ctl.settings.enabled) {
      // 暫時連線：關閉（bridge 釋放手把）；焦點與第一下只放焦點的狀態都重來。
      disconnect();
      ctl.padActive = false;
    } else if (ctl.navClaim) {
      // claim 可能仍在傳輸中。照樣在同一條 socket 後送 release，並保留 transient 標記直到 roster 確認已釋放。
      revokeNav();
    } else {
      ctl.navClaim = null;
      maybeAutoClaim();
    }
    renderHud();
  }

  /** 玩家明確選擇：id＝claim 那一支（bridge 驗證；不合法 fail closed）；null／''＝不使用手把（release，之後不自動 claim）。 */
  function selectController(id) {
    ctl.navAutoBlock = null; // 玩家已明確選擇；之後依一般 controller 設定處理。
    if (id === null || id === undefined || id === '') {
      saveClaimPref({ mode: 'none' });
      ctl.claimNotice = null;
      const sent = sendClaim({ type: 'release' });
      renderHud();
      return sent;
    }
    if (!Core.isControllerId(id)) { ctl.claimNotice = Core.claimReasonText('invalid-controller'); renderHud(); return false; }
    saveClaimPref({ mode: 'id', id });
    ctl.claimNotice = null;
    const sent = sendClaim({ type: 'claim', controller: id });
    renderHud();
    return sent;
  }

  function boundController() {
    const id = ctl.binding.owned;
    if (!id) return null;
    if (id === Core.LEGACY_CONTROLLER_ID) return { id, side: 'right' };
    return (ctl.roster && ctl.roster.controllers.find(c => c.id === id)) || null;
  }

  /** 公開 feed()（測試／除錯）：與 bridge 訊息同一個入口，但不是 bridge socket，所以無法把 stale 救回 connected。 */
  function feed(raw) { ingest(raw, null); }

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

  /** 目前必選地圖目標的識別（伺服器 choice_id；沒有時用候選城鎮）；沒有鎖 → null。 */
  function choiceLockKey() {
    if (!choiceLocked()) return null;
    const p = lastSupportChoiceMapHighlightPayload;
    if (p.choiceId !== undefined && p.choiceId !== null && p.choiceId !== '') return `choice:${p.choiceId}`;
    const towns = Array.isArray(p.towns) ? p.towns.map(t => (t && t.town) || '').join('|') : '';
    return `towns:${p.actionKind || ''}:${towns}`;
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
        // 必選地圖目標時鎖住背景：分頁與回合列本來就不是方向焦點；其他分頁沒有任何內容，只能用 R／SR 回到戰略地圖。
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

  // 手牌每次狀態推送都整列重建，焦點靠 sig 重新綁定：手牌卡 div 帶 data-card-index（伺服器手牌位置），
  // 同名手牌（例如第 1 與第 6 張都是追隨者）才不會被綁回第一張。
  function sigOf(el) {
    if (el.id) return `#${el.id}`;
    const d = el.dataset || {};
    return [el.tagName, d.view, d.cardZone, d.cardName, d.cardMode, d.cardIndex, d.marketMode, d.aiRedArmy,
      (el.textContent || '').trim().slice(0, 16)].join('|');
  }

  /** 方向焦點排除描述（桌面與客廳共用，由 Core.isDirectionalExcluded 判斷）。 */
  function directionalFlags(el) {
    return {
      handAction: el.matches('.hand-card-action-btn'),
      cardCheckbox: el.matches('.purchase-card-select-button')
        || (el.tagName === 'INPUT' && el.type === 'checkbox' && !!el.closest('[data-card-zone]')),
      sectionTab: el.matches('.game-tab') || !!el.closest('#gameTabs .game-tab'),
      turnControl: !!el.closest('#turnActionButtons'),
      hintBar: !!el.closest('#lrBar'),
      factionAbility: !!el.closest('#factionActionButtons') || el.id === 'redArmyAbilityBtn',
      helpEntry: el.id === HELP_ENTRY_ID,
    };
  }

  function padExcluded(el) {
    return !!el && el.nodeType === 1 && typeof el.matches === 'function' && Core.isDirectionalExcluded(directionalFlags(el));
  }

  /**
   * 原生焦點停在排除的控制上（滑鼠點過、或舊焦點）時放掉。整張卡牌 div 無法取得原生焦點，
   * 所以 focus() 到卡牌時不會自動把原本停在分頁／結束行動／手牌按鈕上的原生焦點移走。
   */
  function releaseExcludedFocus() {
    const active = document.activeElement;
    if (ctl.focusKind === 'help' && active === ctl.focusEl) return; // R／SR 環放在 Joy-Con 說明按鈕上的焦點
    if (active && active !== document.body && padExcluded(active)) {
      try { active.blur(); } catch { /* ignore */ }
    }
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
        ...directionalFlags(el),
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
      // 執行結果交給 layer 以 req 對應（兩種顯示模式的地圖 Y 共用；沒有等待中的 req 一律當 stale 忽略）；不符 schema 視為沒有收到確認。
      const result = Core.sanitizeMapResult(event.data);
      if (result && layer && initialized && typeof layer.onMapResult === 'function') layer.onMapResult(result);
      return;
    }
    if (event.data.type !== 'redline-controller-map-snapshot') return;
    const snap = Core.sanitizeMapSnapshot(event.data);
    // SL 聚焦選單（兩種顯示模式）：只採用對上自己 req（且已先收到同一個 req 的及時 ok:true）的 snapshot；
    // 不合 schema 的 snapshot 讓等待中的請求 fail closed。
    const notifyMenu = (s) => { if (layer && initialized && typeof layer.onMapSnapshot === 'function') layer.onMapSnapshot(s); };
    if (!snap) { ctl.mapSnapshot = null; if (layerActive()) layer.scheduleRender(); notifyMenu(null); return; }
    if (ctl.mapSnapshot && snap.seq < ctl.mapSnapshot.seq) return;
    const detailChanged = (ctl.mapSnapshot ? ctl.mapSnapshot.detail : null) !== snap.detail;
    ctl.mapSnapshot = snap;
    if (layerActive()) layer.scheduleRender();
    notifyMenu(snap);
    if (detailChanged) renderHud(); // 城鎮說明開／關：提示列的 B 跟著更新
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
    releaseExcludedFocus();
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
    if (ctl.focusKind === 'map' || ctl.focusKind === 'browse') sendToMap('clearFocus');
    ctl.focusEl = null;
    ctl.focusSig = null;
    ctl.focusTown = null;
    ctl.focusKind = null;
    ctl.padActive = false;
    // 兩種顯示模式：SL 聚焦選單關閉並取消等待中的請求（晚到的回覆不會再開啟）。
    if (layer && initialized && typeof layer.resetFocusMenu === 'function') layer.resetFocusMenu();
    if (layerActive()) layer.onClear();
    renderHud();
  }

  function focusDom(item) {
    // 不變式：搖桿焦點（class 與原生 focus）永遠不落在排除的控制上。任何路徑（記憶還原、舊 sig）要求聚焦它們時：
    // 手牌卡內按鈕改為整張手牌，其他（分頁、結束行動、陣營能力鈕、購買選擇按鈕）直接不聚焦。
    if (padExcluded(item.el)) {
      const card = item.el.matches('.hand-card-action-btn') ? item.el.closest('.card[data-card-zone="hand"]') : null;
      if (!card) return;
      item = { ...item, el: card, sig: sigOf(card) };
    }
    clearDomFocus();
    if (ctl.focusKind === 'map' || ctl.focusKind === 'browse') sendToMap('clearFocus');
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

  /**
   * SL 全域地圖聚焦選定城鎮後的桌面模式焦點（iframe 已收到 focusTown 並自己畫 focus ring）。城鎮是目前的地圖目標 →
   * 與方向鍵相同的目標焦點（A 選取／Y 既有地圖操作照舊）；否則是只看的 'browse' 焦點：不在 action 焦點集合內，A／Y 不作用。
   * 不送 clearFocus（它會排在 focusTown 之後把新的 ring 清掉）。回傳 'target'｜'browse'。
   */
  function focusBrowseTown(town) {
    const scope = currentScope();
    ctl.lastScopeId = scope.id;
    ctl.pageFocusMemory = null;
    ctl.autofocusMap = false;
    const item = scope.kind === 'map' ? collectMap().find(i => i.key === `town:${town}`) : null;
    if (item) { applyItem(item); return 'target'; }
    clearDomFocus();
    ctl.focusKind = 'browse';
    ctl.focusEl = null;
    ctl.focusSig = `browse:${town}`;
    ctl.focusTown = town;
    ctl.browseTargets = Core.mapTargetsSig(ctl.mapSnapshot);
    renderHud();
    return 'browse';
  }

  /** 放掉 'browse' 焦點（並清掉 iframe 的 ring）；town 有給時只放掉該城鎮。回傳是否放掉。 */
  function dropBrowseFocus(town) {
    if (ctl.focusKind !== 'browse' || (town !== undefined && ctl.focusTown !== town)) return false;
    sendToMap('clearFocus');
    ctl.focusKind = null;
    ctl.focusEl = null;
    ctl.focusSig = null;
    ctl.focusTown = null;
    ctl.browseTargets = null;
    renderHud();
    return true;
  }

  /** 方向鍵從 'browse' 焦點出發時的起點：被聚焦的城鎮已置中，所以用地圖 iframe 的中心。 */
  function browseOrigin(scope) {
    const frame = mapFrame();
    if (scope.kind !== 'map' || ctl.focusKind !== 'browse' || !frame) return null;
    const r = frame.getBoundingClientRect();
    const x = (r.left + r.right) / 2;
    const y = (r.top + r.bottom) / 2;
    return { key: ctl.focusSig, kind: 'browse', left: x - 6, right: x + 6, top: y - 6, bottom: y + 6 };
  }

  function helpEntryEl() {
    const el = document.getElementById(HELP_ENTRY_ID);
    return isShown(document.getElementById('gameShell')) && isUsable(el) ? el : null;
  }

  /** 焦點目前停在可用的 Joy-Con 說明按鈕（modal 開著時不算）。 */
  function helpFocused(scope) {
    return ctl.focusKind === 'help' && scope.kind !== 'modal' && !!helpEntryEl() && ctl.focusEl === helpEntryEl();
  }

  /** R／SR 環到達 Joy-Con 說明按鈕，或說明圖關閉後回焦：只放焦點（不開圖）。回傳是否成功。 */
  function focusHelpEntry() {
    const el = helpEntryEl();
    if (!el) return false;
    clearDomFocus();
    if (ctl.focusKind === 'map' || ctl.focusKind === 'browse') sendToMap('clearFocus');
    ctl.focusKind = 'help';
    ctl.focusEl = el;
    ctl.focusSig = `#${HELP_ENTRY_ID}`;
    ctl.focusTown = null;
    ctl.browseTargets = null;
    ctl.autofocusMap = false;
    ctl.pageFocusMemory = null;
    ctl.padActive = true;
    ctl.lastScopeId = currentScope().id;
    el.classList.add(FOCUS_CLASS);
    try { el.focus({ preventScroll: true }); } catch { /* ignore */ }
    renderHud();
    return true;
  }

  /** 方向鍵從 Joy-Con 說明按鈕出發時的起點（按鈕本身不在方向焦點集合內）。 */
  function helpOrigin(scope) {
    if (!helpFocused(scope)) return null;
    const r = ctl.focusEl.getBoundingClientRect();
    return { key: ctl.focusSig, kind: 'help', left: r.left, right: r.right, top: r.top, bottom: r.bottom };
  }

  /** 畫面流程明確指定新焦點時，同步控制器的內部焦點，避免 reconcile 拉回上一個已隱藏控制附近。 */
  function focusElement(target) {
    const el = typeof target === 'string' ? document.getElementById(target) : target;
    if (!el) return false;
    const scope = currentScope();
    const item = buildItems(scope).dom.find(i => i.el === el);
    if (!item) return false;
    ctl.lastScopeId = scope.id;
    ctl.pageFocusMemory = null;
    ctl.padActive = true; // 流程明確指定的焦點：下一次 A 直接作用在它上面（不是「第一下只放焦點」）
    applyItem(item);
    return true;
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
    // 預設焦點只放在內容（與客廳模式相同）：指揮中心先放手牌，其他分頁放該分頁內第一個內容項目。
    const view = scope.kind === 'page' ? document.querySelector('.game-view.active') : null;
    const inView = view ? items.dom.filter(i => view.contains(i.el)) : [];
    return Core.pickInitial(inView.filter(i => i.el.matches('#hand .card[data-card-zone="hand"]')))
      || Core.pickInitial(inView) || Core.pickInitial(items.dom);
  }

  function reconcile() {
    ctl.reconcileTimer = null;
    if (!live() || !ctl.padActive) return;
    releaseExcludedFocus();
    // 控制器使用中出現必選地圖目標、但畫面留在其他分頁（例如手上還有可排入的建立卡）：自動切到戰略地圖一次。
    if (redirectChoiceToMap(currentScope(), true)) return;
    if (layerActive() && layer.reconcile()) return;
    const scope = currentScope();
    // Joy-Con 說明按鈕上的焦點（不在 action 焦點集合內）：按鈕仍可用就保留；說明圖關閉後回到按鈕。
    if (scope.kind !== 'modal' && ctl.focusKind === 'help') {
      if (helpFocused(scope)) {
        ctl.lastScopeId = scope.id;
        if (!ctl.focusEl.classList.contains(FOCUS_CLASS)) ctl.focusEl.classList.add(FOCUS_CLASS);
        return;
      }
      clearDomFocus();
      ctl.focusKind = null; ctl.focusEl = null; ctl.focusSig = null;
    }
    if (scope.kind !== 'modal' && scope.id !== ctl.lastScopeId && ctl.pageFocusMemory && ctl.pageFocusMemory.kind === 'help'
      && focusHelpEntry()) return;
    const items = buildItems(scope);
    // SL 瀏覽焦點刻意不在 action 焦點集合內：仍在戰略地圖、仍是 canonical 城鎮且地圖目標沒變時保留（直到下一次使用者導航）。
    // 目標改變（例如新的 pending choice）或城鎮不再可瀏覽 → 放掉，以既有的地圖預設焦點（iframe 的焦點城鎮或第一個城鎮目標）接手。
    if (scope.kind === 'map' && ctl.focusKind === 'browse') {
      const snap = ctl.mapSnapshot;
      if (snap && snap.browseTowns.some(t => t.town === ctl.focusTown) && Core.mapTargetsSig(snap) === ctl.browseTargets) return;
      dropBrowseFocus();
      if (scope.id === ctl.lastScopeId) { applyItem(defaultItem(items, scope)); return; }
    }
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

  // ------------------------------------------------------------ 必選地圖目標 → 戰略地圖
  // 切到地圖時 iframe 可能尚未掛載或還在載入，第一個 snapshot 指令會落空：依序補要，直到有目標的 snapshot 到達、
  // 鎖解除或離開地圖為止（有上限，不會無限送）。snapshot 指令只讀，iframe 每次都以權威資料重算。
  const CHOICE_SNAPSHOT_RETRY_MS = Object.freeze([250, 600, 1200, 2500, 4000]);

  function choiceSnapshotReady() {
    const snap = ctl.mapSnapshot;
    return !!snap && snap.scope === 'choice' && snap.targets.length > 0;
  }

  function requestChoiceSnapshot() {
    clearTimeout(ctl.choiceSnapTimer);
    ctl.choiceSnapTimer = null;
    let attempt = 0;
    const tick = () => {
      ctl.choiceSnapTimer = null;
      if (!ctl.padActive || !choiceLocked() || currentScope().kind !== 'map' || choiceSnapshotReady()) return;
      sendToMap('snapshot');
      if (attempt < CHOICE_SNAPSHOT_RETRY_MS.length) ctl.choiceSnapTimer = setTimeout(tick, CHOICE_SNAPSHOT_RETRY_MS[attempt++]);
    };
    ctl.choiceSnapTimer = setTimeout(tick, CHOICE_SNAPSHOT_RETRY_MS[attempt++]);
  }

  /**
   * 必選地圖目標但不在戰略地圖（page scope）：以既有區段切換（與 R／SR 同一條路，必選時只到戰略地圖）帶到地圖。
   * iframe 尚未掛載時由既有分頁流程掛載；之後第一份有目標的 snapshot 到達就把焦點放到地圖目標
   * （桌面＝autofocusMap，客廳＝地圖清單）。proactive＝鎖剛出現時的自動切換（每個 choice 一次；客廳輪流遮罩或
   * 不是這個席位的 Joy-Con 時不做）；否則＝控制器輸入 input（該輸入不執行）。回傳是否真的切到了戰略地圖。
   */
  function redirectChoiceToMap(scope, proactive, input = null) {
    if (!layer || !initialized || typeof layer.choiceMapRedirect !== 'function') return false;
    if (proactive && gate && typeof gate.allowsPage === 'function' && !gate.allowsPage({ owned: ctl.binding.owned })) return false;
    if (!layer.choiceMapRedirect({ scopeKind: scope.kind, proactive, input })) return false;
    ctl.padActive = true;
    if (layerActive()) layer.runSectionRing(1, null);
    else changeSection(scope, 1);
    if (activeGameView() !== 'map') return false;
    requestChoiceSnapshot();
    renderHud();
    return true;
  }

  /** app.js 的陣營選擇 Joy-Con 階段 API（RedlineFactionPickerPad）；不完整就當作沒有（維持既有 modal 流程）。 */
  function factionPickerPad() {
    const pad = window.RedlineFactionPickerPad;
    return pad && typeof pad.phase === 'function' && typeof pad.run === 'function' && typeof pad.hintContext === 'function' ? pad : null;
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

  // ------------------------------------------------------------ 遊戲選單（遊戲中按住搖桿按鈕 2 秒）
  // 開啟、導覽、取消都只改這個分頁的 DOM（不送遊戲 mutation、不消耗行動、不動地圖）；「Joy-Con 功能表」點既有說明按鈕，
  // 「重新開始」先開第二層確認，確認後才點既有的 /new-game 連結。
  const GAME_MENU_IDS = new Set([Core.GAME_MENU_MODAL_ID, Core.GAME_MENU_CONFIRM_ID]);

  function gameMenuLevel() {
    if (isShown(document.getElementById(Core.GAME_MENU_CONFIRM_ID))) return 'confirm';
    if (isShown(document.getElementById(Core.GAME_MENU_MODAL_ID))) return 'menu';
    return null;
  }

  /** 開始流程（含 Joy-Con 配對）畫面看得到，或 Joy-Con 自動建房／席位配置尚未完成。 */
  function startFlowActive() {
    const sf = window.RedlineStartFlow;
    return isShown(document.getElementById('startFlow')) || !!(sf && typeof sf.autoSetupActive === 'function' && sf.autoSetupActive());
  }

  /** Core.gameMenuBlocker 的輸入（目前 DOM／連線／hot-seat 狀態）。 */
  function gameMenuContext() {
    const owned = ctl.binding.owned;
    const scope = currentScope();
    return {
      connected: bridgeConnected(),
      owned: !!owned,
      hidden: document.hidden,
      startFlow: startFlowActive(),
      inGame: inGame() && !isShown(document.getElementById('lobby')),
      hasState: !!window.lastGameState,
      handoff: document.documentElement.dataset.hotseat === 'masked',
      // 客廳輪流：只有目前行動席位綁定的 Joy-Con（未啟用 hot-seat＝本分頁擁有的那一支）。
      activeController: !(gate && initialized && typeof gate.allowsPage === 'function') || gate.allowsPage({ owned }) === true,
      modal: scope.kind === 'modal',
      // 必選地圖目標停在其他分頁：STICK 照既有規則先切回戰略地圖（不被長按吃掉）。
      choiceRedirect: scope.kind === 'page' && choiceLocked(),
    };
  }

  /** 長按開始時的情境；累積中改變（換手把／epoch、換 scope、換行動者或 pending choice）就取消。 */
  function stickHoldKey() {
    const s = window.lastGameState || {};
    const choice = s.pending_choice ? s.pending_choice.choice_id ?? null : null;
    return JSON.stringify([ctl.inputKey, ctl.binding.owned, currentScope().id, s.current_player ?? null, choice]);
  }

  /** 每一筆已接受的 frame：更新 release gate 與長按累積；回傳要照常 dispatch 的 action（長按的 STICK press 不 dispatch）。 */
  function trackStickHold(actions, now) {
    const held = ctl.input.held || {};
    const gated = ctl.menuGate.blocked.length;
    ctl.menuGate = Core.stepMenuGate(ctl.menuGate, held);
    if (ctl.menuGate.blocked.length !== gated && gameMenuLevel()) renderHud(); // 「放開搖桿按鈕後操作」提示消失
    const pressed = actions.some(a => a.type === 'press' && a.button === 'STICK');
    const evaluate = held.STICK === true && (pressed || ctl.stickHold.since !== null);
    const r = Core.stepStickHold(ctl.stickHold, {
      pressed,
      held: held.STICK === true,
      neutral: ctl.input.dir === null,
      others: Core.BUTTON_NAMES.some(name => name !== 'STICK' && held[name] === true),
      eligible: evaluate && Core.gameMenuBlocker(gameMenuContext()) === null,
      key: evaluate ? stickHoldKey() : null,
    }, now);
    ctl.stickHold = r.hold;
    if (r.consume || r.cancelled) renderHud(); // 「繼續按住」提示出現／消失
    if (r.fire) openGameMenu();
    return r.consume ? actions.filter(a => !(a.type === 'press' && a.button === 'STICK')) : actions;
  }

  function setOverlayShown(el, on) {
    if (!el) return;
    el.style.display = on ? 'flex' : 'none';
    el.setAttribute('aria-hidden', on ? 'false' : 'true');
  }

  /** 換層級後的焦點：scope 改變由既有 reconcile 記住／還原頁面焦點並放到 scope 的預設焦點；id 有給時再移到該按鈕。 */
  function settleGameMenuFocus(id) {
    if (!ctl.padActive || !live()) return;
    clearTimeout(ctl.reconcileTimer);
    reconcile();
    const el = id ? document.getElementById(id) : null;
    const item = el ? buildItems(currentScope()).dom.find(i => i.el === el) : null;
    if (item) applyItem(item);
  }

  function openGameMenu() {
    const menu = document.getElementById(Core.GAME_MENU_MODAL_ID);
    if (!menu || Core.gameMenuBlocker(gameMenuContext()) !== null) return false;
    ctl.menuGate = Core.createMenuGate(ctl.input.held); // 開啟時 STICK 仍按住：放開前選單不接受任何輸入
    setOverlayShown(menu, true);
    ctl.padActive = true;
    settleGameMenuFocus(null);
    renderHud();
    return true;
  }

  /** 返回遊戲／B／背景：關閉兩層；焦點交回既有 reconcile（還原開啟前的頁面焦點）。silent＝不重新放焦點（接著開啟其他 modal）。 */
  function closeGameMenu({ silent = false } = {}) {
    const wasOpen = !!gameMenuLevel();
    for (const id of GAME_MENU_IDS) setOverlayShown(document.getElementById(id), false);
    if (!wasOpen) return;
    if (ctl.focusKind === 'dom' && ctl.focusEl && [...GAME_MENU_IDS].some(id => document.getElementById(id)?.contains(ctl.focusEl))) {
      clearDomFocus();
      ctl.focusEl = null;
      ctl.focusSig = null;
      ctl.focusKind = null;
    }
    if (!silent) settleGameMenuFocus(null);
    renderHud();
  }

  /** 「Joy-Con 功能表」：關閉選單後走既有 Joy-Con 說明按鈕（openJoyconHelp）；說明圖的 B／× 照既有流程關閉。 */
  function openGameMenuSettings() {
    if (gameMenuLevel() !== 'menu') return;
    closeGameMenu({ silent: true });
    const btn = document.getElementById(HELP_ENTRY_ID);
    if (isUsable(btn)) btn.click();
    else if (typeof window.openJoyconHelp === 'function') window.openJoyconHelp();
    scheduleReconcile();
  }

  /** 「重新開始」：只開啟第二層確認（不執行）。 */
  function openRestartConfirm() {
    if (gameMenuLevel() !== 'menu') return;
    ctl.menuGate = Core.createMenuGate(ctl.input.held); // 選這一項的 A 放開前，確認畫面不接受 A
    setOverlayShown(document.getElementById(Core.GAME_MENU_MODAL_ID), false);
    setOverlayShown(document.getElementById(Core.GAME_MENU_CONFIRM_ID), true);
    settleGameMenuFocus(null);
    renderHud();
  }

  /** 確認畫面的 B／返回選單：回到遊戲選單，焦點回到「重新開始」。 */
  function cancelRestartConfirm() {
    if (gameMenuLevel() !== 'confirm') return;
    ctl.menuGate = Core.createMenuGate(ctl.input.held); // 同一個按住的 B 不會接著關閉遊戲選單
    setOverlayShown(document.getElementById(Core.GAME_MENU_CONFIRM_ID), false);
    setOverlayShown(document.getElementById(Core.GAME_MENU_MODAL_ID), true);
    settleGameMenuFocus('gameMenuRestartBtn');
    renderHud();
  }

  /** 確認重新開始：走既有正式 /new-game 入口（右上「重新開始」連結；不在就直接導向同一個 route）。 */
  function confirmRestart() {
    if (gameMenuLevel() !== 'confirm') return;
    closeGameMenu({ silent: true });
    const link = document.getElementById('emergencyNewGameBtn');
    if (link && link.getAttribute('href') === '/new-game') link.click(); // 連結的 click（capture）由 hotseat_ui 記下沿用的配對
    else {
      window.RedlineHotSeat?.prepareRestart?.();
      window.location.assign('/new-game');
    }
  }

  /** 選單開著時離開遊戲畫面、交接遮罩或回到開始流程：關閉（不還原焦點）。 */
  function revalidateGameMenu() {
    if (!gameMenuLevel()) return;
    const c = gameMenuContext();
    if (!c.inGame || c.handoff || c.startFlow) closeGameMenu({ silent: true });
  }

  function gameMenuIntercept(action) {
    const level = gameMenuLevel();
    if (!level || !GAME_MENU_IDS.has(currentScope().id)) return false;
    if (!Core.menuGateAllows(ctl.menuGate, action)) { renderHud(); return true; }
    return Core.gameMenuCommand(level, Core.logicalAction(action)).cmd === 'none';
  }

  function bindGameMenu() {
    const $ = id => document.getElementById(id);
    const on = (id, fn) => { const el = $(id); if (el) el.addEventListener('click', fn); };
    on('gameMenuResumeBtn', () => closeGameMenu());
    on('gameMenuSettingsBtn', openGameMenuSettings);
    on('gameMenuRestartBtn', openRestartConfirm);
    on('gameMenuConfirmCancelBtn', cancelRestartConfirm);
    on('gameMenuConfirmOkBtn', confirmRestart);
    // 滑鼠點背景：選單＝返回遊戲；確認畫面＝返回遊戲選單（不會執行重新開始）。
    $(Core.GAME_MENU_MODAL_ID)?.addEventListener('click', (e) => { if (e.target === e.currentTarget) closeGameMenu(); });
    $(Core.GAME_MENU_CONFIRM_ID)?.addEventListener('click', (e) => { if (e.target === e.currentTarget) cancelRestartConfirm(); });
  }

  // ------------------------------------------------------------ dispatch (logical → UI)
  function dispatch(action) {
    // 開始流程的 Joy-Con 配對畫面（start_flow_ui.js）：P1 的 A＝既有「完成配對」、B＝取消配對（不需先移焦點）。其他畫面一律放行。
    if (startGate && initialized && startGate.intercept(action, { owned: ctl.binding.owned })) return;
    // 客廳輪流（hot-seat，hotseat_ui.js）：交接遮罩時所有輸入只給交接確認；顯示時只有該席位綁定的 Joy-Con 能操作。
    // 未啟用 hot-seat 時 gate 一律放行，既有行為不變。
    if (gate && initialized && gate.intercept(action, { owned: ctl.binding.owned })) return;
    // 遊戲選單（按住搖桿 2 秒開啟）：release gate＋scope lock；方向／A／B 交回下面既有的 modal 流程。
    if (gameMenuIntercept(action)) return;
    // 全螢幕勝利插畫是最高層 overlay。B 只關閉 viewer，不穿透到底下的結算視窗。
    if (action?.type === 'press' && action.button === 'B' && window.RedlineVictoryArt?.isOpen()) {
      document.getElementById('victoryArtViewerClose')?.click();
      renderHud();
      return;
    }
    // 遊戲結束後 Y 直接開啟最後勝利插畫。hot-seat gate 已先確認控制權，因此其他席位與交接遮罩不能穿透；
    // 勝利視窗縮小後仍可使用，且不受「第一下只放焦點」規則限制。
    if (action?.type === 'press' && action.button === 'Y' && window.RedlineVictoryArt?.available()) {
      window.RedlineVictoryArt.open();
      renderHud();
      return;
    }
    // 搖桿輸入一律先放掉停在排除控制上的原生焦點（分頁、結束行動、手牌按鈕等）。
    releaseExcludedFocus();
    // 必選地圖目標但停在其他分頁（那裡沒有任何焦點）：方向與 A／B／X／Y／R／SR／STICK／+／Capture 先切回戰略地圖，
    // 不執行原本的按鍵。SL 不攔（它有自己的「切到地圖再開啟聚焦選單」流程）；ZR 在其他分頁照舊完全不作用。
    if (action && redirectChoiceToMap(currentScope(), false, action)) return;
    // 客廳模式的 page／map scope 由 layer 處理；modal、大廳與桌面模式維持下面的既有流程。
    if (layerActive() && layer.dispatch(action)) return;
    // 桌面模式的 Capture（結束行動）／PLUS（陣營能力）：與客廳模式同一套既有流程與閘門（第一下仍只放焦點）。
    const shortcut = !layerActive() && layer ? layer.desktopShortcutOf(action) : null;
    const logical = Core.logicalAction(action);
    if (!logical && !shortcut) return;
    const scope = currentScope();
    // ZR＝戰略地圖縮放，與焦點無關：地圖 scope 直接執行（第一下也執行；不放焦點、不改 padActive），頁面、大廳與任何 modal
    // （含 SL 聚焦選單）完全 no-op（連焦點都不改）。客廳模式的 page／map scope 已由 layer.dispatch 處理。
    if (logical && logical.name === 'mapZoom') {
      if (Core.routeAction({ scopeKind: scope.kind }, logical) && layer) { layer.runDesktopMapZoom(); renderHud(); }
      return;
    }
    const items = buildItems(scope);
    const focusMenuOpen = scope.kind === 'modal' && scope.id === Core.FOCUS_MENU_MODAL_ID;
    // Y 在卡牌（手牌行動／購買卡購買所選）與地圖城鎮目標（既有地圖操作）上不是說明；SL 聚焦選單內 Y 完全不作用。
    if (logical && logical.name === 'toggleHelp' && !focusMenuOpen
      && !(ctl.padActive && (cardFocused(items) || mapTargetFocused(scope, items)))) {
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
    if (shortcut) {
      if (scope.kind !== 'modal') layer.runDesktopShortcut(shortcut);
      renderHud();
      return;
    }
    // 陣營／根據地選擇：陣營 →（具體陣營）→ 根據地 → 閱讀陣營資訊 → A 最終確認；閱讀時搖桿上下只捲動右側資訊。
    // 選擇一律由 app.js 走既有按鈕的 click handler；pass（例如焦點在「返回作戰室」時的 A、陣營階段的 B）交回下面的既有流程。
    const pickerPad = scope.kind === 'modal' && scope.id === 'factionPicker' ? factionPickerPad() : null;
    if (pickerPad && logical) {
      const pickerCmd = Core.factionPickerCommand(pickerPad.phase(), logical);
      const pickerKey = currentKey(items.all);
      const pickerFocus = items.all.find(i => i.key === pickerKey && i.kind === 'dom') || null;
      if (pickerCmd.cmd !== 'pass' && pickerPad.run(pickerCmd, pickerFocus ? pickerFocus.el : null)) { renderHud(); return; }
    }
    // 由 R／SR 開啟的事件卡／時代關卡說明 modal：R／SR 以既有關閉收起並前往下一個區段；其他 modal 維持 scope lock。
    if ((logical.name === 'nextSection' || logical.name === 'prevSection') && scope.kind === 'modal' && !layerActive()
      && layer && layer.isSectionModal(scope.id) && !choiceLocked()) {
      changeSection(scope, logical.name === 'nextSection' ? 1 : -1);
      return;
    }
    const key = currentKey(items.all);
    const mapCancel = scope.kind === 'map' && ctl.mapSnapshot && ctl.mapSnapshot.canCancel;
    const focused = items.all.find(i => i.key === key) || null;
    const onHelp = helpFocused(scope);
    const ctx = {
      scopeKind: scope.kind,
      hasFocus: key !== null || onHelp,
      helpEntry: onHelp,
      card: cardContext(focused),
      mapTarget: scope.kind === 'map' && !!focused && focused.kind === 'town',
      browseFocus: scope.kind === 'map' && ctl.focusKind === 'browse' && !!ctl.focusTown,
      cancelAvailable: scope.kind === 'modal' ? !!modalCancelTarget(scope) : !!mapCancel,
      // 必選地圖目標：在地圖上 R／SR 不動；其他分頁的 R／SR 只回戰略地圖（由區段環處理）。
      sectionsLocked: scope.kind === 'map' && choiceLocked(),
      focusMenuOpen,
    };
    const command = Core.routeAction(ctx, logical);
    if (!command) return;
    // 沒有焦點時只有「移動」「取消」、R／SR 區段與 SL 聚焦選單可直接執行（無可聚焦項目的 modal，例如卡牌預覽，仍須能用 B 關閉；
    // 分頁不是方向焦點，沒有內容的分頁也必須能用 R／SR 離開；聚焦選單本身就是用來找焦點的；SL 瀏覽焦點的城鎮說明不在 action 焦點集合內）。
    if (key === null && !onHelp && !['move', 'cancel', 'section', 'focusMenu', 'townDetail'].includes(command.cmd)) { applyItem(defaultItem(items, scope)); return; }
    const current = items.all.find(i => i.key === key);
    if (current) lastRect = { left: current.left, right: current.right, top: current.top, bottom: current.bottom };

    let activated = false;
    switch (command.cmd) {
      case 'move': {
        // SL 瀏覽焦點：從被聚焦的城鎮（地圖中心）往該方向找最近的地圖目標或控制；Joy-Con 說明按鈕：從按鈕位置出發。
        const origin = browseOrigin(scope) || helpOrigin(scope);
        const from = origin ? origin.key : key;
        const next = Core.pickDirectional(origin ? [...items.all, origin] : items.all, from, command.dir);
        if (next && next.key !== from) applyItem(next);
        break;
      }
      case 'activate': activated = activate(scope, items, current); break;
      // A 在 Joy-Con 說明按鈕上：點既有按鈕開啟說明圖（modal 開啟後 reconcile 記住回焦點＝說明按鈕）。
      case 'openHelp': if (helpEntryEl()) { helpEntryEl().click(); scheduleReconcile(); activated = true; } break;
      // A 在 SL 瀏覽焦點上：重新開啟該城鎮說明（iframe 重驗 town＝目前的 map focus；唯讀，不選取、不動相機）。
      case 'townDetail': sendToMap('detail', { town: ctl.focusTown }); break;
      case 'cardPreview': activated = previewCard(current); break;
      case 'cardToggle': activated = toggleCard(current); break;
      case 'cardMode': activated = playCardMode(current, command.mode); break;
      // 購買卡 Y／地圖目標 Y：與客廳模式同一套既有流程與閘門（layer 只在桌面模式執行；客廳模式的 page／map 由 layer.dispatch 處理）。
      case 'cardBuy': if (layer && current && current.kind === 'dom') layer.runDesktopCardBuy(current.el); break;
      // 一般奧援手牌 X：同一個 startDiscard 與閘門，只開啟危險確認單（預設焦點＝返回）；確認單內的 A 才點既有「棄置」。
      case 'cardDiscard': if (layer && current && current.kind === 'dom') layer.runDesktopCardDiscard(current.el); break;
      case 'mapAct': if (layer && current && current.kind === 'town') layer.runDesktopMapAct(current.town); break;
      case 'cancel': cancel(scope); break;
      case 'section': changeSection(scope, command.step); break;
      // SL：開啟／關閉全域地圖聚焦選單（只改地圖相機與焦點）。客廳模式的 page／map 由 layer.dispatch 處理；這裡是桌面模式、大廳與 modal 內。
      case 'focusMenu': if (layer) layer.runFocusMenuKey(); break;
      case 'focusTurnBar': focusTurnBar(items); break;
      default: break;
    }
    // 客廳模式（例如 modal 內的 A）：只有真的執行才開始 250ms 執行冷卻；桌面模式沒有 layer，不受影響。
    // SL 聚焦選單內的 A 由 layer 自己記錄冷卻（城鎮：iframe 以同一個 req 回覆 focusTown ok:true 後；失敗的選定不阻擋下一個按鍵）。
    if (activated && layerActive() && !focusMenuOpen) layer.noteActivation();
  }

  // ------------------------------------------------------------ card focus (A 預覽 / B 選擇 / 手牌 X 資源（一般奧援＝棄置）Y 行動)
  function cardHost(item) {
    if (!item || item.kind !== 'dom' || !item.el.isConnected) return null;
    return item.el.closest('[data-card-zone]');
  }

  function purchaseToggle(host) {
    if (!host || host.dataset.cardZone !== 'purchase') return null;
    return host.closest('.purchase-card-item')?.querySelector('.purchase-card-select-button[data-purchase-index]') || null;
  }

  function cardContext(item) {
    const host = cardHost(item);
    if (!host) return null;
    const zone = host.dataset.cardZone || '';
    // hasDiscard：手牌帶既有「棄置」控制（一般奧援）→ X 走 layer 的危險確認；layer 不在 → false（X 照舊只接受「資源」鈕，fail closed）。
    const hasDiscard = zone === 'hand' && !!layer && layer.hasHandDiscard(host) === true;
    return { zone, hasToggle: !!purchaseToggle(host), hasDiscard };
  }

  function cardFocused(items) {
    const key = currentKey(items.all);
    return !!cardContext(items.all.find(i => i.key === key));
  }

  /** 焦點是地圖 snapshot 的城鎮目標（不是 iframe 按鈕外框）。 */
  function mapTargetFocused(scope, items) {
    if (scope.kind !== 'map') return false;
    const key = currentKey(items.all);
    const item = items.all.find(i => i.key === key);
    return !!item && item.kind === 'town';
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

  /** B：點擊該購買卡同項目內、可見且啟用的選擇按鈕（伺服器權威的 canSelect 已反映在 disabled）。 */
  function toggleCard(current) {
    const host = cardHost(current);
    const toggle = purchaseToggle(host);
    if (!isUsable(toggle)) return false;
    toggle.click();
    scheduleReconcile();
    return true;
  }

  /** X/Y：只在手牌卡上，點擊該卡既有的「資源」／「行動」按鈕；找不到或被停用即 fail-closed（一般奧援的 X 走 cardDiscard，不經這裡）。 */
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
    if (document.getElementById('gameShell') && isShown(document.getElementById('gameShell'))) {
      // 六個全域區段（四個分頁＋事件卡＋時代關卡）只由 R／SR 循環，與客廳模式同一個環與既有分頁／說明 modal；
      // 必選地圖目標時環只提供「戰略地圖」（已在地圖則不動）。分頁永遠不是方向焦點：切換後清掉舊焦點，
      // 再把焦點放到新區段的內容（不留在分頁上）。
      // 環上另有一個額外焦點：導覽列的 Joy-Con 說明按鈕（layer 已把焦點放上去；不切頁、不開圖，焦點不清掉）。
      const reached = layer && layer.runSectionRing(step, scope.kind === 'modal' ? scope : null);
      if (!reached) return;
      if (reached === HELP_RING_KEY) return;
      if (ctl.focusKind === 'help') ctl.focusKind = null; // 離開說明按鈕：原生焦點也一併放掉
      clearDomFocus();
      if (ctl.focusKind === 'map' || ctl.focusKind === 'browse') sendToMap('clearFocus');
      ctl.focusEl = null;
      ctl.focusSig = null;
      ctl.focusTown = null;
      ctl.focusKind = null;
      ctl.autofocusMap = activeGameView() === 'map';
      ctl.pageFocusMemory = null;
      ctl.lastScopeId = null;
      setTimeout(() => { if (ctl.padActive && !layerActive()) { ctl.lastScopeId = null; reconcile(); } }, 160);
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
  function inGame() { return isShown(document.getElementById('gameShell')); }
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
        <div class="pad-row">我的手把：<b id="padBindingText">—</b></div>
        <label class="pad-row">選擇手把（每位玩家各拿一支）
          <select id="padControllerSelect"></select>
        </label>
        <div id="padClaimNote" class="pad-note pad-error" hidden></div>
        <div id="padSideMap" class="pad-note" hidden></div>
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
        <div class="pad-note">搖桿＝移動　A 確認　B 返回　R/SR 六個區段＋Joy-Con 說明按鈕（A 開圖、B 關閉）　Y 說明<br>Capture 結束行動（確認）　+ 陣營能力<br>卡牌：A 查看　手牌 X 資源／Y 行動（一般奧援 X＝棄置，需確認）　購買卡 B 選擇 → Y 購買所選（確認）<br>地圖目標：A 選取　Y 建立組織／確認移動／瓦解組織<br>ZR（戰略地圖）：放大一級，到最大後再按回到最小<br>SL 地圖聚焦：依統治者／陣營區域選任一城鎮，置中放大（只改地圖畫面）<br>遊戲中按住搖桿 2 秒：遊戲選單（返回遊戲／Joy-Con 功能表／重新開始需確認）</div>
      </div>`;
    stage.appendChild(hud);
    const $ = id => document.getElementById(id);
    // 遊戲畫面不提供設定面板（說明列移到上方中央、🎮 鈕隱藏）；程式觸發的 click 也不開。
    $('padToggleBtn').addEventListener('click', () => { if (inGame()) return; $('padPanel').hidden = !$('padPanel').hidden; renderHud(); });
    $('padEnableChk').addEventListener('change', (e) => { if (!e.target.checked) ctl.navOff = true; setEnabled(e.target.checked); });
    $('padSaveBtn').addEventListener('click', () => saveUrlFromInput());
    $('padResetBtn').addEventListener('click', () => { $('padUrlInput').value = Core.DEFAULT_BRIDGE_URL; saveUrlFromInput(); });
    $('padReconnectBtn').addEventListener('click', () => { if (live()) { ctl.attempt = 0; connect(); } });
    $('padUrlInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') saveUrlFromInput(); });
    $('padControllerSelect').addEventListener('change', (e) => { ctl.navManual = true; selectController(e.target.value || null); });
  }

  // 玩家可見的手把名稱一律經 Core.controllerLabel／bindingBadge 並帶目前 roster（左右＋同側序號；不顯示埠、id、名稱指紋）。
  function rosterList() { return ctl.roster ? ctl.roster.controllers : null; }

  function bindingText() {
    if (!live() || !ctl.socket) return '—';
    const c = boundController();
    if (c) return `${Core.controllerLabel(c, rosterList())}${c.status === 'stale' ? '・訊號中斷' : ''}`;
    return ctl.binding.mode === 'v2' ? '尚未選擇（在下方選一支）' : '—';
  }

  /** 下拉選單只列 bridge roster 的手把；其他玩家使用中或沒有訊號的不能選。舊版 bridge 只有一個唯讀選項。 */
  function controllerOptions() {
    if (ctl.binding.mode !== 'v2' || !ctl.roster) {
      const c = boundController();
      return [{ value: c ? c.id : '', label: c ? Core.controllerLabel(c, rosterList()) : '—', disabled: true }];
    }
    const options = [{ value: '', label: '— 不使用手把 —', disabled: false }];
    for (const c of ctl.roster.controllers) {
      const note = c.owner === 'other' ? '・其他玩家使用中' : c.status === 'stale' ? '・訊號中斷' : '';
      // value＝完整 id（claim 身份）；label 只有玩家名稱。
      options.push({ value: c.id, label: `${Core.controllerLabel(c, rosterList())}${note}`, disabled: c.owner === 'other' || (c.owner !== 'you' && c.status !== 'active') });
    }
    return options;
  }

  function renderControllerSelect(select) {
    const options = controllerOptions();
    const value = ctl.binding.owned || '';
    const sig = JSON.stringify([options, value, ctl.binding.mode]);
    if (select.dataset.sig === sig) return; // 內容沒變不重建（下拉選單開著時不跳動）
    select.dataset.sig = sig;
    select.textContent = '';
    for (const o of options) {
      const option = document.createElement('option');
      option.value = o.value;
      option.textContent = o.label;
      option.disabled = o.disabled;
      select.appendChild(option);
    }
    select.value = value;
    select.disabled = ctl.binding.mode !== 'v2';
  }

  /** 狀態文字：前面帶本分頁手把的玩家名稱（例如「左 Joy-Con 訊號中斷」；同側多支時「右 Joy-Con 2 訊號中斷」）。 */
  function statusLabel() {
    const badge = Core.bindingBadge(ctl.binding, rosterList());
    const text = STATUS_TEXT[ctl.status] || ctl.status;
    return badge && ctl.status !== 'off' ? `${badge} ${text}` : text;
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
    ctl.navAutoBlock = null; // 玩家明確切換設定，可重新啟動一般 auto claim。
    ctl.settings.enabled = !!enabled;
    saveSettings();
    // 起始畫面導覽仍在：改由暫時連線（重新連線＝bridge 釋放後重新判斷；第一筆 frame 只當 baseline）。
    if (enabled || live()) connect(); else disconnect();
    renderHud();
  }

  function hintText() {
    const scope = currentScope();
    if (scope.kind === 'modal' && GAME_MENU_IDS.has(scope.id)) {
      if (!Core.menuGateAllows(ctl.menuGate, null)) return '遊戲選單　放開搖桿按鈕後操作';
      if (scope.id === Core.GAME_MENU_MODAL_ID) return '遊戲選單　搖桿上下 選擇　A 執行　B 返回遊戲';
      const ok = ctl.focusEl && ctl.focusEl.id === 'gameMenuConfirmOkBtn';
      return `重新開始確認　${ok ? 'A 確認重新開始（離開目前遊戲）' : '搖桿 選擇　A 執行'}　B 返回遊戲選單`;
    }
    if (ctl.stickHold.since !== null && scope.kind !== 'modal') return '繼續按住搖桿按鈕（2 秒）開啟遊戲選單';
    if (scope.kind === 'modal' && scope.id === Core.FOCUS_MENU_MODAL_ID) return '搖桿 選擇　A 開啟分組／置中放大城鎮（不執行）　B／SL 關閉';
    if (scope.kind === 'modal' && scope.id === 'joyconHelpModal') return 'Joy-Con 說明圖　B 關閉';
    if (helpFocused(scope)) return 'Joy-Con 說明　A 開啟說明圖　R/SR 區段';
    const pickerPad = scope.kind === 'modal' && scope.id === 'factionPicker' ? factionPickerPad() : null;
    const pickerHint = pickerPad ? Core.factionPickerHint(pickerPad.phase(), pickerPad.hintContext()) : null;
    if (pickerHint) return pickerHint;
    if (scope.kind === 'modal') {
      const cancel = modalCancelTarget(scope);
      // 客廳模式的 legend 自己補「R/SR 下一個區段」；桌面模式在這裡補。
      const section = !layerActive() && layer && layer.isSectionModal(scope.id) && !choiceLocked() ? '　R/SR 下一個區段' : '';
      return `移動 搖桿　A 確認${cancel ? '　B 返回' : ''}${section}`;
    }
    // canonical 城鎮清單完整時，提示可用 SL 聚焦選單（客廳模式由提示列顯示）。
    const menu = !layerActive() && layer && layer.focusMenuAvailable() ? '　SL 聚焦選單' : '';
    // 城鎮說明 popup 開著：B 的第一下只關閉說明。
    const detail = scope.kind === 'map' && ctl.mapSnapshot && ctl.mapSnapshot.detail ? '　B 關閉城鎮說明' : '';
    if (scope.kind === 'map' && ctl.focusKind === 'browse') {
      return `聚焦 ${ctl.focusTown}（只看）　搖桿 移到地圖目標${detail || '　A 城鎮說明'}　ZR 放大地圖（循環）${menu}${choiceLocked() ? '' : '　R/SR 區段'}`;
    }
    if (scope.kind === 'map') {
      const act = ctl.focusKind === 'map' && ctl.focusTown && layer && !layerActive() ? layer.desktopMapActLabel(ctl.focusTown) : null;
      return `移動 搖桿　A 選取${act ? `　Y ${act}` : ''}${detail || '　B 取消'}　ZR 放大地圖（循環）${menu}${choiceLocked() ? '' : '　R/SR 區段'}`;
    }
    if (choiceLocked()) return `必選地圖目標：R/SR 回戰略地圖${menu}`;
    const focused = ctl.focusKind === 'dom' ? cardContext({ kind: 'dom', el: ctl.focusEl }) : null;
    if (focused) {
      const buy = focused.zone === 'purchase' ? '　選擇後 Y 購買所選' : '';
      const hand = focused.zone === 'hand' ? `　${focused.hasDiscard ? 'X 棄置（確認）' : 'X 資源'}　Y 行動` : '';
      return `移動 搖桿　A 查看${focused.hasToggle ? '　B 選擇' : ''}${buy}${hand}　R/SR 區段`;
    }
    return '移動 搖桿　A 確認　R/SR 區段　Capture 結束行動　長按搖桿 選單';
  }

  function setText(el, text) { if (el.textContent !== text) el.textContent = text; }

  function renderHud() {
    if (!hud) return;
    if (layerActive()) layer.renderLegend();
    const $ = id => document.getElementById(id);
    $('padEnableChk').checked = ctl.settings.enabled;
    if (document.activeElement !== $('padUrlInput')) $('padUrlInput').value = ctl.settings.url;
    setText($('padStatusText'), STATUS_TEXT[ctl.status] || ctl.status);
    setText($('padBindingText'), bindingText());
    renderControllerSelect($('padControllerSelect'));
    $('padClaimNote').hidden = !ctl.claimNotice;
    setText($('padClaimNote'), ctl.claimNotice || '');
    const legend = ctl.binding.owned ? Core.sideKeyLegend(ctl.binding.side) : null;
    $('padSideMap').hidden = !legend;
    setText($('padSideMap'), legend || '');
    $('padMixedNote').hidden = !Core.mixedContentRisk(location.protocol, ctl.settings.url);
    if (inGame()) $('padPanel').hidden = true; // 大廳開著的設定面板不帶進遊戲
    hud.dataset.status = ctl.status;
    hud.dataset.side = ctl.binding.owned ? ctl.binding.side : '';
    const hint = $('padHint');
    // 起始畫面導覽的暫時連線：只有真的拿到手把並開始操作才顯示（沒有 bridge 的滑鼠玩家不看到連線錯誤）。
    const show = ctl.settings.enabled ? (ctl.status !== 'connected' || ctl.helpOpen || ctl.padActive)
      : live() && ctl.status === 'connected' && (ctl.helpOpen || ctl.padActive);
    hint.hidden = !show;
    if (show) {
      // 桌面模式專用鍵 fail closed 的原因（例如「先按 B 選擇這張卡，再按 Y 購買」）暫時接在提示前面；客廳模式顯示在提示列狀態欄。
      const notice = ctl.status === 'connected' && layer && !layerActive() && typeof layer.notice === 'function' ? layer.notice() : null;
      const badge = Core.bindingBadge(ctl.binding, rosterList());
      setText(hint, ctl.status === 'connected'
        ? `🎮 ${badge ? `${badge}｜` : ''}${notice ? `${notice}｜` : ''}${hintText()}` : `🎮 ${statusLabel()}`);
    }
  }

  // ------------------------------------------------------------ init
  function init() {
    loadSettings();
    loadClaimPref();
    buildHud();
    bindGameMenu();
    renderHud();
    ctl.staleTimer = setInterval(checkStale, 250);
    ctl.observer = new MutationObserver((records) => {
      // 自己的 HUD／焦點 class 與客廳模式覆蓋層變動不能再觸發重算，否則會自我迴圈。
      const relevant = records.some(r => !(hud && hud.contains(r.target)) && !isOverlayNode(r.target));
      if (relevant) revalidateGameMenu();
      if (relevant && ctl.padActive) { scheduleReconcile(); renderHud(); }
      if (relevant && layerActive()) layer.scheduleRender();
      // 桌面模式的 Capture 危險確認單：既有按鈕失效或換了步驟就關閉；SL 聚焦選單：被其他視窗蓋過或離開遊戲就關閉
      // （客廳模式由 layer render 處理）。
      else if (relevant && layer && layer.revalidateConfirm) layer.revalidateConfirm();
    });
    ctl.observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class', 'disabled'] });
    document.addEventListener('visibilitychange', () => { if (document.hidden) resetInput(); });
    window.addEventListener('blur', resetInput);
    initialized = true;
    if (layer) layer.init(host);
    if (live()) connect();
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
    cardContext, previewCard, toggleCard, playCardMode, modalCancelTarget, sendToMap, choiceLocked, choiceLockKey, activeGameView,
    scheduleReconcile, renderHud, hintText, clearFocus, bridgeConnected, directionalFlags, focusBrowseTown, dropBrowseFocus, focusHelpEntry,
    getMapSnapshot: () => ctl.mapSnapshot,
    statusText: statusLabel,
    bindingBadge: () => Core.bindingBadge(ctl.binding, rosterList()),
  };
  function attachLayer(next) {
    layer = next;
    if (initialized) layer.init(host);
  }
  // 客廳輪流（hot-seat）閘門：只決定輸入是否放行／交給交接確認，不改焦點、layer 或綁定。
  let gate = null;
  function attachGate(next) { gate = next && typeof next.intercept === 'function' ? next : null; }
  // 開始流程配對畫面閘門：只在配對畫面攔截 P1 的 A／B，不改焦點、layer 或綁定。
  let startGate = null;
  function attachStartGate(next) { startGate = next && typeof next.intercept === 'function' ? next : null; }

  window.RedlineController = {
    feed, // 測試／除錯：與 bridge 訊息同一個入口，只在已啟用且已連線時處理（不能讓 stale 恢復）
    getState: () => ({
      enabled: ctl.settings.enabled, status: ctl.status, url: ctl.settings.url, padActive: ctl.padActive, helpOpen: ctl.helpOpen,
      focusKind: ctl.focusKind, focusSig: ctl.focusSig, focusTown: ctl.focusTown,
      scope: currentScope().id, held: { ...ctl.input.held },
      reconcilePending: !!ctl.reconcileTimer, // 除錯：DOM 變動後的 80ms reconcile 尚未跑完
      // 除錯：parent 目前採用的地圖 snapshot 摘要（沒有或最新一份不合 schema 被丟棄＝null）；sig＝Core.mapTargetsSig。
      map: ctl.mapSnapshot ? {
        seq: ctl.mapSnapshot.seq, scope: ctl.mapSnapshot.scope, targets: ctl.mapSnapshot.targets.length,
        selected: ctl.mapSnapshot.selected, focusTown: ctl.mapSnapshot.focusTown, sig: Core.mapTargetsSig(ctl.mapSnapshot),
      } : null,
      livingRoom: layerActive() ? layer.debugState() : null,
      shortcuts: layer && initialized && !layerActive() ? layer.shortcutState() : null, // 桌面模式專用鍵的閘門狀態
      // 遊戲選單：level＝null｜'menu'｜'confirm'；holding＝長按累積中（holdMs＝已按住多久）；gate＝放開前不作用的鍵；blocker＝目前不能開啟的原因。
      gameMenu: {
        level: gameMenuLevel(), holding: ctl.stickHold.since !== null, latched: ctl.stickHold.latched,
        holdMs: ctl.stickHold.since !== null ? Math.round(performance.now() - ctl.stickHold.since) : null,
        gate: [...ctl.menuGate.blocked], blocker: Core.gameMenuBlocker(gameMenuContext()),
      },
      // 這個分頁擁有的手把（bridge roster 為準）與清單摘要；inputKey＝目前 reducer 屬於哪一支／哪一個 epoch。
      // 起始畫面導覽：on＝start flow 要求、live＝目前允許連線（含暫時連線）、claim＝自動 claim 的那一支（不是玩家席位）。
      startNav: { on: ctl.startNav, live: live(), claim: ctl.navClaim, off: ctl.navOff, manual: ctl.navManual, preferred: ctl.navPreferred },
      controller: {
        mode: ctl.binding.mode, owned: ctl.binding.owned, side: ctl.binding.side, pref: { ...ctl.claimPref },
        claimInFlight: ctl.claimInFlight, notice: ctl.claimNotice, inputKey: ctl.inputKey,
        roster: ctl.roster ? ctl.roster.controllers.map(c => ({ id: c.id, side: c.side, status: c.status, owner: c.owner })) : null,
      },
    }),
    setEnabled,
    selectController, // HUD 下拉選單同一個入口：claim 指定的手把，或 null＝不使用
    setStartNav,
    focusElement,
    refreshHud: renderHud, // 畫面流程非同步改變階段後更新底部提示（例如陣營選擇進入閱讀階段）
    attachLayer,
    attachGate,
    attachStartGate,
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
