/*
 * REDLINE 開始遊戲前流程 — 瀏覽器端膠合層（純邏輯在 start_flow_core.js）。
 *
 * 初始畫面：建立真人紅軍／建立 AI 紅軍／輸入房間代碼加入。建立者選難度與操作方式；選 Joy-Con 後，
 * 每支手把同時按 SL＋SR 依成功順序配成 P1～P4，按「完成配對」才繼續。繼續後：電腦操作進入既有「行動代號／陣營」畫面，
 * 房間（含這些設定）在那裡按「建立作戰室」時由伺服器 /create 建立並保存；Joy-Con 行動代號固定為 P1～P4，
 * 完成配對後背景以 P1 自動建房、配置 P2～Pn 本機席位並直接開啟陣營選擇；加入者只讀房主設定。
 * Joy-Con 配對沿用客廳輪流大廳的作法：每支手把一條只 claim 自己那一支的 bridge 連線，只看 SL＋SR。
 * 配對畫面上 P1（已交給主連線）按 A＝「完成配對」、按 B＝取消整個配對；已取消時原 P1（只有它）再按 B＝「← 重新選擇」，或按 SL＋SR 重新配對。
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
    cancelled: false, // 配對畫面上 P1 按 B 取消了整個配對、尚未重新配對（再按 B＝「← 重新選擇」）
    cancelledBy: null, // 取消配對的那一支（原 P1）controller id：只有它的 B 能觸發「← 重新選擇」
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

  function cancelClaimFirst() {
    clearInterval(sf.claimTimer);
    sf.claimTimer = null;
  }

  function closeAllListeners() {
    cancelClaimFirst();
    for (const l of [...sf.listeners.values()]) closeListener(l);
    clearCancelled(); // 離開配對（返回、完成、改用電腦、加入、hide）：「已取消」暫態一併清除
  }

  function clearCancelled() {
    sf.cancelled = false;
    sf.cancelledBy = null;
  }

  /** 已取消、尚未重新配對時，只有取消的那一支（fail closed：沒有記錄就沒有任何一支）可以按 B 回到重新選擇。 */
  const mayReturnToEntry = controller => sf.cancelled && !sf.pairing.order.length
    && !!sf.cancelledBy && controller === sf.cancelledBy;

  function openListener(controller) {
    const cs = ctlState();
    const listener = { controller, socket: null, owned: null, roster: null, claimAt: 0, retryAt: 0, bEpoch: null, bDown: false };
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
    // B 的按下瞬間：每條連線（同一 epoch）的第一筆只當 baseline，進來就按著的 B 要先放開再按。
    const bHeld = !!msg.frame.buttons.B;
    const bPressed = bHeld && listener.bEpoch === msg.epoch && !listener.bDown;
    listener.bEpoch = msg.epoch;
    listener.bDown = bHeld;
    // 已取消配對、尚未重新配對：取消的那一支再按 B＝既有「← 重新選擇」（P1 已交還配對 listener，所以 B 從這裡進來）。
    // 其他手把的 B 不返回、不改變取消狀態，照常只看 SL＋SR。
    if (bPressed && mayReturnToEntry(msg.controller)) { clickIfEnabled('sfBackToEntry'); return; }
    const r = Core.observeFrame(sf.pairing, msg.controller, msg.epoch, msg.frame.buttons);
    sf.pairing = r.pairing;
    if (r.added) {
      clearCancelled();
      const n = sf.pairing.order.length;
      sf.status = `P${n} 配對成功：${controllerName(r.added)}`;
      render();
      // P1 配對完成後立即交給主控制連線。否則配對 listener 會持有 P1，
      // 既有 RedlineController 只能顯示「其他玩家使用中」，P1 便無法用 A 完成配對、B 取消配對（見 interceptPad）。
      if (n === 1) {
        closeListener(listener);
        claimFirst(r.added);
      }
    }
  }

  function clickIfEnabled(id) {
    const el = $(id);
    if (el && !el.disabled && !el.hidden) el.click();
  }

  /**
   * controller_ui.js dispatch 的第一個閘門（只有主連線擁有的那一支手把的輸入會到這裡）。只在 Joy-Con 配對畫面作用：
   * P1 的 A＝點既有「完成配對」（不需先把焦點移到按鈕）；P1 的 B＝取消整個配對。已取消、主連線仍持有剛釋放的那一支
   * （release 尚在傳輸）時：只有取消的那一支的 B＝點既有「← 重新選擇」，其他輸入不穿透。其餘一律放行（既有焦點／方向鍵行為不變）。
   */
  function interceptPad(action, { owned }) {
    if (!action || !owned || !pairingActive()) return false;
    const press = action.type === 'press' ? action.button : null;
    const primary = sf.pairing.order[0] || null;
    if (sf.cancelled && !primary) {
      if (press === 'B' && mayReturnToEntry(owned)) clickIfEnabled('sfBackToEntry');
      return true;
    }
    if (owned !== primary) return false;
    if (press === 'A') { clickIfEnabled('sfContinueBtn'); return true; }
    if (press === 'B') { cancelPairing(owned); return true; }
    return false;
  }

  /**
   * 取消目前整個 Joy-Con 配對：清空 P1～Pn、留在配對畫面。主連線釋放 P1（偏好改為不使用，之後不會自動搶回），
   * P1 交接的 claim 重試停止（晚到的重試不可奪回）；bridge 釋放後由配對 listener 重新 claim，等待 SL＋SR 重新配對。
   * 其他已配對手把的配對 listener 保留，配對狀態重來（下一筆只當 baseline）。記下取消者 controller，
   * 之後只有它的 B 能回到重新選擇。
   */
  function cancelPairing(controller) {
    cancelClaimFirst();
    sf.pairing = Core.createPairing(sf.pairing.max);
    sf.cancelled = true;
    sf.cancelledBy = controller || null;
    sf.status = '已取消 Joy-Con 配對。';
    const api = ctlApi();
    if (api) api.selectController(null);
    syncListeners();
    render();
  }

  /** 想要的監聽＝bridge 上有訊號、沒有人使用的每一支；配對期間才開，離開（完成／返回／改用電腦）全部關閉。 */
  function syncListeners() {
    const cs = ctlState();
    const active = pairingActive() && !!CtlCore() && !!cs && cs.enabled && !!cs.url;
    const roster = (cs && cs.controller && cs.controller.roster) || [];
    const primary = sf.pairing.order[0] || null;
    // P1 由主控制連線持有，讓玩家在配對畫面直接使用方向鍵與 A。
    // 其餘手把仍由各自的配對 listener 持有，以繼續接收 SL＋SR。
    const want = new Set(active ? roster.filter(c => c.status === 'active' && c.id !== primary
      && (c.owner === null || sf.listeners.has(c.id))).map(c => c.id) : []);
    // 尚未產生 P1 時，主連線不可先占用候選手把。若持有的不是已配對 P1，也要釋放。
    if (active && cs.controller.owned && cs.controller.owned !== primary) ctlApi().selectController(null);
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

  // 開始流程隱藏後（完成配對進入作戰準備）配對監聽必須停止並釋放手把，主連線才能 claim；#sfSetup 本身不會被隱藏。
  const pairingActive = () => sf.draft.controlMode === 'joycon' && !!$('sfSetup') && !$('sfSetup').hidden
    && !!$('startFlow') && !$('startFlow').hidden;

  // 起始畫面導覽：開始畫面顯示中、尚未進入正式 SL＋SR 配對時，主連線在 bridge 恰好一支有訊號的 Joy-Con 時自動拿它
  // 操作既有按鈕（真人／AI 紅軍、難度、操作方式、繼續）。只是導覽，不建立／綁定席位、不送 server mutation。
  const startNavWanted = () => !!$('startFlow') && !$('startFlow').hidden && !pairingActive();
  function syncStartNav() {
    const api = ctlApi();
    if (api && typeof api.setStartNav === 'function') api.setStartNav(startNavWanted());
  }

  // ------------------------------------------------------------ 畫面
  function show(step, moveFocus) {
    closeAllListeners();
    hideAuto();
    setJoyconLobby(false);
    syncPreRoomAiSeat(false);
    setFlow('start');
    const flow = $('startFlow');
    if (flow) flow.hidden = false;
    if (step === 'setup') showStep('setup', moveFocus); else showStep('entry', moveFocus);
    $('sfJoinError').textContent = '';
    startTimer();
  }

  function focusEl(el) { if (el && typeof el.focus === 'function') el.focus({ preventScroll: true }); }

  /** moveFocus：使用者切換畫面時，把焦點移到新畫面的標題（標題 tabindex=-1），讓輔助科技與鍵盤使用者知道畫面已換。 */
  function showStep(step, moveFocus) {
    const lobby = lobbyEl();
    if (lobby) lobby.dataset.startStep = step;
    $('sfEntry').hidden = step !== 'entry';
    $('sfSetup').hidden = step !== 'setup';
    if (step === 'entry') { closeAllListeners(); sf.pairing = Core.createPairing(Core.maxControllers(false)); sf.status = ''; }
    render();
    if (moveFocus) focusEl(step === 'setup' ? $('sfSetupTitle') : $('sfTitle'));
  }

  function render() {
    const d = sf.draft;
    $('sfSetupTitle').textContent = d.aiRedArmy ? '建立 AI 紅軍遊戲' : '建立真人紅軍遊戲';
    const setPressed = (b, on) => { b.classList.toggle('active', on); b.setAttribute('aria-pressed', String(on)); };
    document.querySelectorAll('[data-sf-market]').forEach(b => setPressed(b, b.dataset.sfMarket === d.marketMode));
    document.querySelectorAll('[data-sf-control]').forEach(b => setPressed(b, b.dataset.sfControl === d.controlMode));
    const joy = d.controlMode === 'joycon';
    $('sfPairing').hidden = !joy;
    const cancelled = joy && sf.cancelled && !sf.pairing.order.length;
    if (cancelled) $('sfPairing').dataset.cancelled = 'true'; else delete $('sfPairing').dataset.cancelled;
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
      ? (ok ? `已配對 ${sf.pairing.order.length}/${sf.pairing.max} 支；還有人要加入就繼續按 SL + SR，否則按「完成配對」（P1 按 A；按 B 取消配對）。`
        : cancelled ? '配對已取消：按 SL + SR 重新配對，或由原 P1 再按一次 B 回到重新選擇。'
          : '至少要有一支 Joy-Con 配對成功才能繼續。')
      : '';
    renderStatus();
    syncStartNav();
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
    sf.timer = setInterval(() => { if (pairingActive()) { syncListeners(); render(); } else syncStartNav(); }, 500);
  }

  function chooseControl(mode) {
    sf.draft = Core.normalizeDraft({ ...sf.draft, controlMode: mode });
    sf.status = '';
    clearCancelled();
    syncStartNav(); // 進入配對：導覽手把先釋放，P1 一樣要按 SL＋SR
    if (mode === 'joycon') {
      const api = ctlApi();
      if (api) { api.setEnabled(true); api.selectController(null); } // 配對連線自己 claim；主連線先不自動搶
      syncListeners();
    } else {
      closeAllListeners();
      const api = ctlApi();
      if (api) { api.selectController(null); api.setEnabled(false); }
      sf.pairing = Core.createPairing(Core.maxControllers(sf.draft.aiRedArmy));
    }
    render();
  }

  function chooseEntry(ai) {
    sf.draft = Core.normalizeDraft({ ...sf.draft, aiRedArmy: ai });
    sf.pairing = Core.createPairing(Core.maxControllers(ai));
    showStep('setup', true);
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
    sf.pending = {
      settings,
      controllers,
      createRequestId: settings.control_mode === 'joycon' ? createRequestId() : null,
    };
    try { sessionStorage.setItem(PAIRING_KEY, JSON.stringify({ controllers })); } catch { /* ignore */ }
    $('startFlow').hidden = true;
    syncStartNav();
    setFlow('create');
    const room = $('roomId');
    if (room) { room.readOnly = true; room.value = ''; room.placeholder = '建立作戰室後顯示房間代碼'; }
    applyRoomDisplay(Core.settingsSummary(settings));
    $('roomSettingsHint').textContent = '輸入行動代號後按「建立作戰室」，房主設定會由伺服器保存。';
    $('sfBackBtn').hidden = false;
    if (typeof applyMarketMode === 'function') applyMarketMode(settings.market_mode);
    if (typeof applyAiRedArmy === 'function') applyAiRedArmy(settings.ai_red_army);
    const joy = settings.control_mode === 'joycon';
    setJoyconLobby(joy);
    syncPreRoomAiSeat(settings.ai_red_army);
    if (joy) {
      // Joy-Con 人數與 P1～Pn 已由配對決定：不問行動代號、不需按「建立作戰室」，背景自動建房並開啟陣營選擇。
      $('sfBackBtn').hidden = true;
      sf.pending.auto = true;
      if (controllers.length) claimFirst(controllers[0]);
      runAutoCreate();
      return true;
    }
    focusEl($('playerName'));
    return true;
  }

  /** Joy-Con 建立畫面：房主設定摘要、房間代碼、LAN 網址、難易度、紅軍席位都已在開始流程決定，不再顯示也不進方向焦點。 */
  function setJoyconLobby(on) {
    const lobby = lobbyEl();
    if (lobby) { if (on) lobby.dataset.joyconLobby = 'true'; else delete lobby.dataset.joyconLobby; }
    const back = $('sfBackBtn');
    if (back) { if (on) back.setAttribute('data-controller-skip', ''); else back.removeAttribute('data-controller-skip'); }
  }

  /** 房間建立前，右側先顯示不可占用的 AI 紅軍席位；建立後由 app.js 依 server /lobby 重畫（canonical）。 */
  function syncPreRoomAiSeat(ai) {
    const roster = $('lobbyRoster');
    if (!roster) return;
    roster.querySelectorAll('[data-preroom]').forEach(el => el.remove());
    if (!ai) return;
    const card = document.createElement('div');
    card.className = 'lobby-player-card ai-seat';
    card.dataset.preroom = 'true';
    card.innerHTML = '<div class="lobby-player-avatar">AI</div><div><strong>AI 紅軍</strong><span>電腦代打｜無需真人加入</span></div>';
    const empty = roster.querySelector('.lobby-player-card.empty');
    roster.insertBefore(card, empty);
  }

  // ------------------------------------------------------------ Joy-Con 自動建房（沿用 app.js createRoom／hotseat provisionSeats）
  function showAuto(state, text) {
    const box = $('sfAutoSetup');
    if (!box) return;
    box.hidden = false;
    box.dataset.state = state;
    $('sfAutoStatus').textContent = text;
    const failed = state === 'failed';
    $('sfAutoRetryBtn').hidden = !failed;
    // 房間已建立就不能退回配對（會留下孤立房間）；只有尚未建房時才提供。
    $('sfAutoBackBtn').hidden = !failed || !!(sf.pending && sf.pending.roomId);
    $('sfAutoRetryBtn').disabled = !failed;
  }

  function hideAuto() { const box = $('sfAutoSetup'); if (box) { box.hidden = true; delete box.dataset.state; } }

  function nextFrame() { return new Promise(resolve => requestAnimationFrame(() => resolve())); }

  function createRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    const bytes = new Uint8Array(24);
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  }

  /** 陣營畫面開啟後，把焦點放在第一個陣營選項（app.js 預設落在關閉鈕），並同步給控制器。 */
  async function focusFirstFaction() {
    await nextFrame();
    await nextFrame();
    const first = document.querySelector('#factionPicker #factionList .faction-choice-btn:not(:disabled)');
    if (!first) return;
    focusEl(first);
    if (ctlApi() && typeof ctlApi().focusElement === 'function') ctlApi().focusElement(first);
  }

  async function runAutoCreate() {
    if (!sf.pending || !sf.pending.auto || sf.pending.busy) return;
    const pending = sf.pending;
    pending.busy = true;
    showAuto('running', `正在建立作戰室並配置 P1～P${pending.controllers.length}…`);
    let result;
    try { result = await window.createRoom({ codename: 'P1', isCurrent: () => sf.pending === pending }); }
    catch { result = { ok: false, error: '無法連線到伺服器，請重試。' }; }
    pending.busy = false;
    const ok = !!result && result.ok !== false;
    if (!ok && (sf.pending !== pending || (result && result.cancelled))) return;
    if (!ok) {
      showAuto('failed', (result && result.error) || '作戰室建立失敗，請重試。');
      const retry = $('sfAutoRetryBtn');
      if (ctlApi() && typeof ctlApi().focusElement === 'function' && ctlApi().focusElement('sfAutoRetryBtn')) return;
      focusEl(retry);
      return;
    }
    hideAuto();
    await focusFirstFaction();
  }

  /** 完成配對後，主連線 claim P1（bridge 剛釋放配對連線，可能要重試幾次）。 */
  function claimFirst(controller) {
    cancelClaimFirst();
    sf.claimTimer = setInterval(() => {
      const cs = ctlState();
      if (cs && cs.controller && cs.controller.owned === controller) { cancelClaimFirst(); return; }
      // 配對連線釋放後主連線的 roster 沒有自己的手把＝unbound；connected／unbound 都是可 claim 的合法狀態。
      // 不設固定截止次數：主連線的單次重連退避可能超過 8 秒。只有成功、返回、切換電腦模式或 hide 才取消。
      if (cs && cs.enabled && (cs.status === 'connected' || cs.status === 'unbound') && !cs.controller.claimInFlight) ctlApi().selectController(controller);
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
    hideAuto();
    setJoyconLobby(false);
    syncPreRoomAiSeat(false);
    $('startFlow').hidden = true;
    syncStartNav();
    setFlow('join');
    const room = $('roomId');
    if (room) { room.value = code; room.readOnly = true; if (typeof syncLobbyRoomCode === 'function') syncLobbyRoomCode(); }
    $('sfBackBtn').hidden = false;
    onRoomSettings(data);
    $('roomSettingsHint').textContent = '以房主設定進行；輸入行動代號後按「進入作戰室」。';
    // 欄位預設值 host 是房主的代號；加入者要輸入自己的行動代號，不能預設成現有房主。
    const nameInput = $('playerName');
    if (nameInput) {
      if (!nameInput.dataset.userEdited) nameInput.value = '';
      focusEl(nameInput);
    }
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
    // Joy-Con 房間的本機席位（含逐棒交接後整頁重新載入的 P2～Pn、回到房主）：沿用建立時的精簡畫面，不顯示代碼／網址／難度／AI。
    const hs = window.RedlineHotSeat;
    const localJoycon = lobbyRes.control_mode === 'joycon' && !!session.playerId && !!hs && hs.isLocalSeat && hs.isLocalSeat(session.gameId, session.playerId);
    if (localJoycon && !sf.pending && lobbyEl() && lobbyEl().dataset.flow !== 'start') setFlow('create');
    setJoyconLobby(localJoycon || !!(sf.pending && sf.pending.auto));
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
  function pendingCreate() {
    if (!sf.pending) return null;
    return {
      ...sf.pending.settings,
      ...(sf.pending.createRequestId ? { create_request_id: sf.pending.createRequestId } : {}),
    };
  }

  function clearPending() {
    sf.pending = null;
    try { sessionStorage.removeItem(PAIRING_KEY); } catch { /* ignore */ }
  }

  /**
   * 房間建立後：配對到多支手把時，沿用客廳輪流為 P2～Pn 新增本機席位並依配對順序綁定。
   * 只有全部席位成功且驗證通過才清除 pending／配對；失敗則保留（連同 roomId）供同一房間重試，回傳 { ok:false, error }。
   */
  async function afterCreate(roomId) {
    const pending = sf.pending;
    if (!pending) return { ok: true };
    pending.roomId = roomId || pending.roomId || null;
    if (pending.controllers.length >= 2) {
      const hs = window.RedlineHotSeat;
      let result;
      try { result = hs && typeof hs.provisionSeats === 'function' ? await hs.provisionSeats(pending.controllers) : null; }
      catch { result = null; }
      if (!result || !result.ok) {
        return { ok: false, error: (result && result.error) || 'Joy-Con 席位建立失敗，請重試。' };
      }
    }
    // 自動建房要等陣營畫面真的開啟（entered）才清除；之前任何失敗都從同一個房間重試。
    if (!pending.auto) clearPending();
    return { ok: true };
  }

  /** createRoom 剛建好房間：先記下房間，之後的失敗（含席位配置前的例外）都只重試、不重複建房。 */
  function roomCreated(roomId) { if (sf.pending) sf.pending.roomId = roomId || null; }

  /** 陣營選擇已開啟：自動流程完成。 */
  function entered(roomId) {
    if (sf.pending && sf.pending.auto && (!sf.pending.roomId || sf.pending.roomId === roomId)) clearPending();
  }

  /** 該房間已建立、但 Joy-Con 席位尚未全部配置完成（等待重試）。 */
  /** Joy-Con 自動建房還沒完成（配置中或失敗待重試）。 */
  function autoSetupActive() { return !!(sf.pending && sf.pending.auto); }

  function hasPendingProvision(roomId) { return !!(sf.pending && sf.pending.roomId && sf.pending.roomId === roomId); }

  function init() {
    const on = (id, fn) => { const el = $(id); if (el) el.addEventListener('click', fn); };
    on('sfCreateHuman', () => chooseEntry(false));
    on('sfCreateAi', () => chooseEntry(true));
    on('sfJoinBtn', join);
    on('sfBackToEntry', () => showStep('entry', true));
    on('sfContinueBtn', finishCreateSetup);
    on('sfAutoRetryBtn', () => { runAutoCreate(); });
    on('sfAutoBackBtn', () => { sf.pending = null; hideAuto(); show('entry', true); });
    on('sfBackBtn', () => {
      const room = $('roomId');
      if (room) { room.readOnly = false; room.value = ''; }
      sf.pending = null;
      show('entry', true);
    });
    const code = $('sfRoomCode');
    if (code) code.addEventListener('keydown', e => { if (e.key === 'Enter') join(); });
    document.querySelectorAll('[data-sf-market]').forEach(b => b.addEventListener('click', () => {
      sf.draft = Core.normalizeDraft({ ...sf.draft, marketMode: b.dataset.sfMarket });
      render();
    }));
    document.querySelectorAll('[data-sf-control]').forEach(b => b.addEventListener('click', () => chooseControl(b.dataset.sfControl)));
    const api = ctlApi();
    if (api && typeof api.attachStartGate === 'function') api.attachStartGate({ intercept: interceptPad });
  }

  window.RedlineStartFlow = {
    show, pendingCreate, afterCreate, roomCreated, entered, autoSetupActive, hasPendingProvision, onRoomSettings,
    /** 流程已被既有 session 取代（恢復連線、proof URL）：不顯示開始畫面。 */
    hide: () => { closeAllListeners(); sf.pending = null; hideAuto(); const f = $('startFlow'); if (f) f.hidden = true; syncStartNav(); setFlow(null); },
    // 除錯／E2E
    getState: () => ({
      step: $('startFlow') && !$('startFlow').hidden ? ($('sfSetup').hidden ? 'entry' : 'setup') : 'done',
      draft: { ...sf.draft }, paired: sf.pairing.order.slice(), max: sf.pairing.max, cancelled: sf.cancelled, cancelledBy: sf.cancelledBy,
      listeners: [...sf.listeners.values()].map(l => ({ controller: l.controller, owned: l.owned, open: !!l.socket })),
      claimPending: !!sf.claimTimer,
      startNav: startNavWanted(),
      pending: sf.pending ? { settings: { ...sf.pending.settings }, controllers: sf.pending.controllers.slice() } : null,
    }),
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
