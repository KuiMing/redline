/*
 * REDLINE 開始遊戲前流程 — 瀏覽器端膠合層（純邏輯在 start_flow_core.js）。
 *
 * 初始畫面：建立真人紅軍／建立 AI 紅軍／輸入房間代碼加入。建立者選難度與操作方式；選 Joy-Con 後，
 * 每支手把同時按 SL＋SR 依成功順序配成 P1～P4，按「完成配對」才繼續。繼續後進入既有「行動代號／陣營」畫面，
 * 房間（含這些設定）在那裡按「建立作戰室」時由伺服器 /create 建立並保存；加入者只讀房主設定。
 * Joy-Con 配對沿用客廳輪流大廳的作法：每支手把一條只 claim 自己那一支的 bridge 連線，只看 SL＋SR。
 */
(function () {
  'use strict';
  const Core = window.RedlineStartFlowCore;
  if (!Core) return;

  const PAIRING_KEY = 'redline.startflow.pairing.v1';
  const GUEST_ENABLED_KEY = 'redline.startflow.joycon-enabled.v1';
  const $ = id => document.getElementById(id);
  const RETRY_MS = 2000;

  const sf = {
    draft: Core.normalizeDraft(null),
    pairing: Core.createPairing(Core.MAX_CONTROLLERS),
    pending: null, // 完成設定後、按「建立作戰室」前：{ settings, controllers }
    listeners: new Map(), // controller id → { controller, socket, owned, roster, epoch, claimAt, retryAt }
    timer: null,
    status: '',
    claimTimer: null,
  };

  const ctlApi = () => window.RedlineController || null;
  const ctlState = () => { try { return ctlApi() ? ctlApi().getState() : null; } catch { return null; } };
  const CtlCore = () => window.RedlineControllerCore || null;
  const lobbyEl = () => $('lobby');
  const setFlow = value => { const el = lobbyEl(); if (el) { if (value) el.dataset.flow = value; else delete el.dataset.flow; } };

  function controllerName(id) {
    const cs = ctlState();
    const roster = (cs && cs.controller && cs.controller.roster) || [];
    try { return CtlCore().controllerDisplayName(id, roster); } catch { return 'Joy-Con'; }
  }

  // ------------------------------------------------------------ 配對：每支手把一條 claim 自己的 bridge 連線
  function closeListener(listener) {
    if (sf.listeners.get(listener.controller) === listener) sf.listeners.delete(listener.controller);
    const socket = listener.socket;
    listener.socket = null;
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
      try { socket.close(); } catch { /* ignore */ } // 連線結束＝bridge 釋放這一支
    }
  }

  function closeAllListeners() { for (const l of [...sf.listeners.values()]) closeListener(l); }

  function openListener(controller) {
    const cs = ctlState();
    const listener = { controller, socket: null, owned: null, roster: null, claimAt: 0, retryAt: 0 };
    sf.listeners.set(controller, listener);
    let socket;
    try { socket = new WebSocket(cs.url); } catch { listener.retryAt = Date.now() + RETRY_MS; return listener; }
    listener.socket = socket;
    socket.onopen = () => { try { socket.send(JSON.stringify(CtlCore().bridgeHello())); } catch { /* ignore */ } };
    socket.onmessage = event => onListenerMessage(listener, event.data);
    socket.onclose = () => {
      if (listener.socket !== socket) return;
      listener.socket = null;
      listener.owned = null;
      listener.retryAt = Date.now() + RETRY_MS;
    };
    socket.onerror = () => { try { socket.close(); } catch { /* ignore */ } };
    return listener;
  }

  function claimForListener(listener) {
    const socket = listener.socket;
    if (!socket || socket.readyState !== 1 || listener.owned === listener.controller) return;
    const entry = (listener.roster || []).find(c => c.id === listener.controller);
    if (!entry || entry.owner || entry.status !== 'active') return;
    const now = Date.now();
    if (now - listener.claimAt < 1000) return;
    listener.claimAt = now;
    try { socket.send(JSON.stringify({ type: 'claim', controller: listener.controller, v: CtlCore().BRIDGE_PROTOCOL_VERSION })); } catch { /* ignore */ }
  }

  function onListenerMessage(listener, raw) {
    if (sf.listeners.get(listener.controller) !== listener) return;
    let parsed;
    try { parsed = JSON.parse(raw); } catch { return; }
    const msg = CtlCore().classifyBridgeMessage(parsed, 'v2');
    if (!msg) return;
    if (msg.kind === 'roster') {
      const owned = msg.roster.owned ? msg.roster.controllers.find(c => c.id === msg.roster.owned) : null;
      listener.owned = owned ? owned.id : null;
      listener.roster = msg.roster.controllers;
      claimForListener(listener);
      return;
    }
    if (msg.kind !== 'frame' || document.hidden) return;
    if (msg.controller !== listener.controller || msg.controller !== listener.owned) return;
    const r = Core.observeFrame(sf.pairing, msg.controller, msg.epoch, msg.frame.buttons);
    sf.pairing = r.pairing;
    if (r.added) {
      const n = sf.pairing.order.length;
      sf.status = `P${n} 配對成功：${controllerName(r.added)}`;
      render();
    }
  }

  /** 想要的監聽＝bridge 上有訊號、沒有人使用的每一支；配對期間才開，離開（完成／返回／改用電腦）全部關閉。 */
  function syncListeners() {
    const cs = ctlState();
    const active = pairingActive() && !!CtlCore() && !!cs && cs.enabled && !!cs.url;
    const roster = (cs && cs.controller && cs.controller.roster) || [];
    const want = new Set(active ? roster.filter(c => c.status === 'active' && (c.owner === null || sf.listeners.has(c.id))).map(c => c.id) : []);
    // 主連線自己擁有的那一支（例如先前 claim 的）：先釋放，才能由配對連線 claim。
    if (active && cs.controller.owned) ctlApi().selectController(null);
    for (const l of [...sf.listeners.values()]) if (!want.has(l.controller)) closeListener(l);
    const now = Date.now();
    for (const id of want) {
      const l = sf.listeners.get(id);
      if (!l) openListener(id);
      else if (!l.socket && now >= l.retryAt) { closeListener(l); openListener(id); }
      else claimForListener(l);
    }
    // 配對中的手把訊號消失：保留名額（重連後同一身份仍屬原席位）。
    const connected = !!cs && cs.status === 'connected';
    if (active && !connected && !sf.status) sf.status = '正在連線到 Joy-Con Bridge…';
    renderStatus();
  }

  const pairingActive = () => sf.draft.controlMode === 'joycon' && !!$('sfSetup') && !$('sfSetup').hidden;

  // ------------------------------------------------------------ 畫面
  function show(step) {
    closeAllListeners();
    setFlow('start');
    const flow = $('startFlow');
    if (flow) flow.hidden = false;
    if (step === 'setup') showStep('setup'); else showStep('entry');
    $('sfJoinError').textContent = '';
    startTimer();
  }

  function showStep(step) {
    $('sfEntry').hidden = step !== 'entry';
    $('sfSetup').hidden = step !== 'setup';
    if (step === 'entry') { closeAllListeners(); sf.pairing = Core.createPairing(Core.maxControllers(false)); }
    render();
  }

  function render() {
    const d = sf.draft;
    $('sfSetupTitle').textContent = d.aiRedArmy ? '建立 AI 紅軍遊戲' : '建立真人紅軍遊戲';
    document.querySelectorAll('[data-sf-market]').forEach(b => b.classList.toggle('active', b.dataset.sfMarket === d.marketMode));
    document.querySelectorAll('[data-sf-control]').forEach(b => b.classList.toggle('active', b.dataset.sfControl === d.controlMode));
    const joy = d.controlMode === 'joycon';
    $('sfPairing').hidden = !joy;
    const slots = Core.slots(sf.pairing);
    $('sfSlots').replaceChildren(...slots.map(s => {
      const el = document.createElement('div');
      el.className = 'sf-slot';
      el.dataset.slot = s.label;
      el.dataset.paired = String(s.paired);
      const title = document.createElement('strong');
      title.textContent = s.label;
      const note = document.createElement('span');
      note.textContent = s.paired ? controllerName(s.controller) : '等待 SL + SR';
      el.append(title, note);
      return el;
    }));
    const ok = Core.canContinue(d, sf.pairing);
    const btn = $('sfContinueBtn');
    btn.disabled = !ok;
    btn.textContent = joy ? `完成配對（已配對 ${sf.pairing.order.length} 支）` : '繼續';
    $('sfContinueHint').textContent = joy
      ? (ok ? `已配對 ${sf.pairing.order.length}/${sf.pairing.max} 支；還有人要加入就繼續按 SL + SR，否則按「完成配對」。`
        : '至少要有一支 Joy-Con 配對成功才能繼續。')
      : '';
    renderStatus();
  }

  function renderStatus() {
    const el = $('sfPairingStatus');
    if (!el) return;
    const cs = ctlState();
    let text = sf.status;
    if (pairingActive() && (!cs || !cs.enabled)) text = '尚未啟用搖桿控制。';
    else if (pairingActive() && (cs.status === 'error' || cs.status === 'off')) text = '無法連線到 Joy-Con Bridge，請確認 tools/joycon_bridge 已啟動。';
    if (el.textContent !== text) el.textContent = text;
  }

  function startTimer() {
    if (sf.timer) return;
    sf.timer = setInterval(() => { if (pairingActive()) { syncListeners(); render(); } }, 500);
  }

  function chooseControl(mode) {
    sf.draft = Core.normalizeDraft({ ...sf.draft, controlMode: mode });
    sf.status = '';
    if (mode === 'joycon') {
      const api = ctlApi();
      if (api) { api.setEnabled(true); api.selectController(null); } // 配對連線自己 claim；主連線先不自動搶
      syncListeners();
    } else {
      closeAllListeners();
      sf.pairing = Core.createPairing(Core.maxControllers(sf.draft.aiRedArmy));
    }
    render();
  }

  function chooseEntry(ai) {
    sf.draft = Core.normalizeDraft({ ...sf.draft, aiRedArmy: ai });
    sf.pairing = Core.createPairing(Core.maxControllers(ai));
    showStep('setup');
    if (sf.draft.controlMode === 'joycon') chooseControl('joycon');
  }

  // ------------------------------------------------------------ 完成設定 → 既有行動代號／陣營畫面
  function applyRoomDisplay(summary) {
    const el = $('roomSettingsSummary');
    if (el && summary) el.textContent = summary.text;
  }

  function finishCreateSetup() {
    if (!Core.canContinue(sf.draft, sf.pairing)) return false;
    const settings = Core.createSettings(sf.draft, sf.pairing);
    const controllers = settings.control_mode === 'joycon' ? sf.pairing.order.slice() : [];
    closeAllListeners();
    sf.pending = { settings, controllers };
    try { sessionStorage.setItem(PAIRING_KEY, JSON.stringify({ controllers })); } catch { /* ignore */ }
    $('startFlow').hidden = true;
    setFlow('create');
    const room = $('roomId');
    if (room) { room.readOnly = true; room.value = ''; room.placeholder = '建立作戰室後顯示房間代碼'; }
    applyRoomDisplay(Core.settingsSummary(settings));
    $('roomSettingsHint').textContent = '輸入行動代號後按「建立作戰室」，房主設定會由伺服器保存。';
    $('sfBackBtn').hidden = false;
    if (typeof applyMarketMode === 'function') applyMarketMode(settings.market_mode);
    if (typeof applyAiRedArmy === 'function') applyAiRedArmy(settings.ai_red_army);
    if (controllers.length) claimFirst(controllers[0]);
    return true;
  }

  /** 完成配對後，主連線 claim P1（bridge 剛釋放配對連線，可能要重試幾次）。 */
  function claimFirst(controller) {
    clearInterval(sf.claimTimer);
    let tries = 0;
    sf.claimTimer = setInterval(() => {
      const cs = ctlState();
      tries += 1;
      if ((cs && cs.controller && cs.controller.owned === controller) || tries > 12) { clearInterval(sf.claimTimer); return; }
      if (cs && cs.enabled && cs.status === 'connected' && !cs.controller.claimInFlight) ctlApi().selectController(controller);
    }, 600);
  }

  async function join() {
    const code = Core.cleanRoomCode($('sfRoomCode').value);
    const err = $('sfJoinError');
    if (!code) { err.textContent = '請輸入房間代碼。'; return; }
    let data;
    try { data = await (await fetch(`/lobby/${encodeURIComponent(code)}`)).json(); }
    catch { err.textContent = '無法連線到伺服器，請再試一次。'; return; }
    if (!data || data.error) { err.textContent = typeof playerMessageZhTw === 'function' ? playerMessageZhTw((data && data.error) || 'Game not found') : '找不到房間。'; return; }
    if (data.started) { err.textContent = '這個房間已經開始遊戲，無法加入。'; return; }
    closeAllListeners();
    sf.pending = null;
    $('startFlow').hidden = true;
    setFlow('join');
    const room = $('roomId');
    if (room) { room.value = code; room.readOnly = true; if (typeof syncLobbyRoomCode === 'function') syncLobbyRoomCode(); }
    $('sfBackBtn').hidden = false;
    onRoomSettings(data);
    $('roomSettingsHint').textContent = '以房主設定進行；輸入行動代號後按「進入作戰室」。';
  }

  // ------------------------------------------------------------ app.js hooks
  /** 房主設定（伺服器 /lobby）：顯示、讓難度／紅軍控制與伺服器一致，並讓 Joy-Con 房間的成員啟用搖桿控制。 */
  function onRoomSettings(lobbyRes) {
    if (!lobbyRes) return;
    const summary = Core.settingsSummary(lobbyRes);
    applyRoomDisplay(summary);
    if (typeof applyMarketMode === 'function' && lobbyRes.market_mode) applyMarketMode(lobbyRes.market_mode);
    if (typeof applyAiRedArmy === 'function') applyAiRedArmy(!!lobbyRes.ai_red_army);
    const session = window.RedlineSession && window.RedlineSession.current ? window.RedlineSession.current() : {};
    if (session.playerId) {
      $('sfBackBtn').hidden = true;
      $('roomSettingsHint').textContent = lobbyRes.host_id === session.playerId ? '' : '房主設定由房主決定，訪客只能查看。';
      // 房主設定為 Joy-Con：每位成員的分頁都啟用搖桿控制（一次；之後尊重玩家自己的開關）。
      if (lobbyRes.control_mode === 'joycon' && ctlApi()) {
        let done = false;
        try { done = sessionStorage.getItem(GUEST_ENABLED_KEY) === session.gameId; } catch { /* ignore */ }
        if (!done) {
          try { sessionStorage.setItem(GUEST_ENABLED_KEY, session.gameId || ''); } catch { /* ignore */ }
          const cs = ctlState();
          if (cs && !cs.enabled) ctlApi().setEnabled(true);
        }
      }
    }
  }

  /** createRoom() 送出前取得的房主設定；沒有走開始流程（舊流程）時為 null，/create 維持原預設。 */
  function pendingCreate() { return sf.pending ? { ...sf.pending.settings } : null; }

  /** 房間建立後：配對到多支手把時，沿用客廳輪流為 P2～Pn 新增本機席位並依配對順序綁定。 */
  async function afterCreate() {
    const pending = sf.pending;
    sf.pending = null;
    try { sessionStorage.removeItem(PAIRING_KEY); } catch { /* ignore */ }
    if (!pending || pending.controllers.length < 2) return;
    const hs = window.RedlineHotSeat;
    if (hs && typeof hs.provisionSeats === 'function') await hs.provisionSeats(pending.controllers);
  }

  function init() {
    const on = (id, fn) => { const el = $(id); if (el) el.addEventListener('click', fn); };
    on('sfCreateHuman', () => chooseEntry(false));
    on('sfCreateAi', () => chooseEntry(true));
    on('sfJoinBtn', join);
    on('sfBackToEntry', () => showStep('entry'));
    on('sfContinueBtn', finishCreateSetup);
    on('sfBackBtn', () => {
      const room = $('roomId');
      if (room) { room.readOnly = false; room.value = ''; }
      sf.pending = null;
      show('entry');
    });
    const code = $('sfRoomCode');
    if (code) code.addEventListener('keydown', e => { if (e.key === 'Enter') join(); });
    document.querySelectorAll('[data-sf-market]').forEach(b => b.addEventListener('click', () => {
      sf.draft = Core.normalizeDraft({ ...sf.draft, marketMode: b.dataset.sfMarket });
      render();
    }));
    document.querySelectorAll('[data-sf-control]').forEach(b => b.addEventListener('click', () => chooseControl(b.dataset.sfControl)));
  }

  window.RedlineStartFlow = {
    show, pendingCreate, afterCreate, onRoomSettings,
    /** 流程已被既有 session 取代（恢復連線、proof URL）：不顯示開始畫面。 */
    hide: () => { closeAllListeners(); const f = $('startFlow'); if (f) f.hidden = true; setFlow(null); },
    // 除錯／E2E
    getState: () => ({
      step: $('startFlow') && !$('startFlow').hidden ? ($('sfSetup').hidden ? 'entry' : 'setup') : 'done',
      draft: { ...sf.draft }, paired: sf.pairing.order.slice(), max: sf.pairing.max,
      listeners: [...sf.listeners.values()].map(l => ({ controller: l.controller, owned: l.owned, open: !!l.socket })),
      pending: sf.pending ? { settings: { ...sf.pending.settings }, controllers: sf.pending.controllers.slice() } : null,
    }),
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
