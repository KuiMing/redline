let ws = null;
let wsReconnectTimer = null;
let wsReconnectAttempts = 0;
let pendingOutboundActions = [];
let gameId = null;
let playerId = null;
let resumeToken = null;
const REDLINE_DEVICE_ID_KEY = 'redline.device_id.v1';
const REDLINE_SESSIONS_KEY = 'redline.sessions.v1';
let previousEras = [];
let availableFactionCategories = [];
let pendingFactionCategory = null;
let pendingFactionChoice = null;
let pendingFactionBaseChoice = null;
let pendingFactionBaseGroup = null;
let cachedFullMapData = null;
let activeFactionActionModal = null;
let cardPresentationCatalog = null;
let lastEraNotificationKey = null;
let eraAchievementDetailsById = {};   // 生效中的時代關卡說明，供釘選卡片重新點開使用
let eraAchievementViewId = null;      // 時代關卡浮窗目前顯示的時代 id
let stageResizeBound = false;
let lobbySyncTimer = null;
let latestLobbyState = null;
let lobbyTransientStatus = null;
let activeChoiceModal = null;
let lastFactionActionResultKey = null;
let lastSupportChoiceMapHighlightPayload = null;
let lastEventRevealKey = null;
let stickyPlayerErrorNotice = '';
let stickyPlayerErrorTimer = null;
let unavailableActionModalReturnFocus = null;
const selectedPurchaseIndices = new Set();
// 這兩張卡的取消能力只能被動觸發（其他玩家打出可取消的卡牌時自動跳出反應視窗），
// 自己回合主動點「行動」不會取消任何東西，白白浪費這張卡，因此手牌區直接 disable。
const REACTION_ONLY_ACTION_CARDS = new Set(['爆料黑幕', '產業滲透']);

function resizeStage() {
  const scale = Math.min(
    window.innerWidth / 1280,
    window.innerHeight / 720
  );
  document.documentElement.style.setProperty('--stage-scale', String(scale));
  document.documentElement.style.setProperty('--stage-left', `${Math.max(0, (window.innerWidth - 1280 * scale) / 2)}px`);
  document.documentElement.style.setProperty('--stage-top', `${Math.max(0, (window.innerHeight - 720 * scale) / 2)}px`);
}

function playerInitialFromInput(name) {
  const trimmed = (name || '').trim();
  return (trimmed[0] || 'H').toUpperCase();
}

function redlineDeviceId() {
  let value = localStorage.getItem(REDLINE_DEVICE_ID_KEY);
  if (!value) {
    value = globalThis.crypto?.randomUUID?.() || `device-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(REDLINE_DEVICE_ID_KEY, value);
  }
  return value;
}

function storedRedlineSessions() {
  try {
    const parsed = JSON.parse(localStorage.getItem(REDLINE_SESSIONS_KEY) || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (_) {
    return {};
  }
}

function saveRedlineSession(name = '') {
  if (!gameId || !playerId || !resumeToken) return;
  const sessions = storedRedlineSessions();
  sessions[gameId] = {
    game_id: gameId,
    player_id: playerId,
    resume_token: resumeToken,
    name: String(name || document.getElementById('playerName')?.value || '').trim(),
    saved_at: Date.now(),
  };
  localStorage.setItem(REDLINE_SESSIONS_KEY, JSON.stringify(sessions));
}

function latestRedlineSession() {
  return Object.values(storedRedlineSessions())
    .filter(session => session?.game_id && session?.player_id && session?.resume_token)
    .sort((a, b) => Number(b.saved_at || 0) - Number(a.saved_at || 0))[0] || null;
}

function removeRedlineSession(roomId) {
  const sessions = storedRedlineSessions();
  delete sessions[roomId];
  localStorage.setItem(REDLINE_SESSIONS_KEY, JSON.stringify(sessions));
}

function updateLobbyStatus(statusText = null) {
  const nameInput = document.getElementById('playerName');
  const rosterName = document.getElementById('lobbyRosterName');
  const rosterStatus = document.getElementById('lobbyRosterStatus');
  const avatar = document.querySelector('.lobby-player-card.host .lobby-player-avatar');
  const hint = document.getElementById('lobbyStatusHint');
  const name = (nameInput?.value || 'host').trim() || 'host';
  if (rosterName) rosterName.textContent = name;
  if (avatar) avatar.textContent = playerInitialFromInput(name);
  if (statusText) {
    lobbyTransientStatus = statusText;
    if (rosterStatus) rosterStatus.textContent = statusText;
    if (hint) hint.textContent = statusText;
  }
}

function deriveLobbyHint(lobbyRes) {
  const players = lobbyRes?.players || [];
  const chosen = lobbyRes?.factions || {};
  const ready = lobbyRes?.ready || {};
  const everyoneChose = players.length > 0 && Object.keys(chosen).length === players.length;
  const everyoneReady = players.length > 0 && players.every(([pid]) => ready[pid]);
  const hasRedArmy = Object.values(chosen).includes('red_army');
  if (everyoneChose && everyoneReady && !hasRedArmy) return '房間必須有一名紅軍玩家，才能啟動行動。';
  if (everyoneChose && everyoneReady) return '所有玩家已準備；房主可以啟動行動。';
  if (everyoneChose) return '玩家陣營已選定；等待所有玩家按下準備。';
  return `已進入 ${players.length}/4 人作戰室；等待玩家選擇陣營。`;
}

function renderLobbyRoster(lobbyRes, statusText = null) {
  const roster = document.getElementById('lobbyRoster');
  const hint = document.getElementById('lobbyStatusHint');
  if (!roster || !lobbyRes) {
    updateLobbyStatus(statusText);
    return;
  }

  latestLobbyState = lobbyRes;
  const players = lobbyRes.players || [];
  const chosen = lobbyRes.factions || {};
  const bases = lobbyRes.bases || {};
  const ready = lobbyRes.ready || {};
  const hostId = lobbyRes.host_id;
  const cards = players.map(([pid, name]) => {
    const isHost = pid === hostId;
    const isMe = pid === playerId;
    const faction = chosen[pid];
    const base = bases[pid];
    const role = [isHost ? '房主' : '玩家', isMe ? '你' : null].filter(Boolean).join(' / ');
    const readyText = ready[pid] ? '已準備' : '未準備';
    const factionText = faction
      ? `${factionDisplayName(faction)}${base ? `｜${baseDisplayName(base)}` : ''}`
      : '尚未選擇陣營';
    const status = `${role}｜${readyText}｜${factionText}`;
    return `
      <div class="lobby-player-card ${isHost ? 'host' : ''}${isMe ? ' self' : ''}${ready[pid] ? ' ready' : ''}">
        <div class="lobby-player-avatar">${escapeHtml(playerInitialFromInput(name))}</div>
        <div>
          <strong${isMe ? ' id="lobbyRosterName"' : ''}>${escapeHtml(name)}</strong>
          <span${isMe ? ' id="lobbyRosterStatus"' : ''}>${escapeHtml(status)}</span>
        </div>
      </div>`;
  }).join('');

  const emptySlots = Math.max(0, 4 - players.length);
  const emptyCards = Array.from({length: emptySlots}).map((_, idx) => `
    <div class="lobby-player-card empty">
      <div class="lobby-player-avatar">+</div>
      <div>
        <strong>${idx === 0 ? '等待玩家加入' : '空席位'}</strong>
        <span>${idx === 0 ? '分享房間代碼邀請下一位玩家' : '最多 4 位玩家'}</span>
      </div>
    </div>`).join('');

  roster.innerHTML = cards + emptyCards;
  updateLobbyActionControls(lobbyRes);
  if (hint) {
    if (statusText) lobbyTransientStatus = statusText;
    const transient = lobbyTransientStatus;
    hint.textContent = transient || deriveLobbyHint(lobbyRes);
  }
}

function lobbyReadiness(lobbyRes = latestLobbyState) {
  const players = lobbyRes?.players || [];
  const chosen = lobbyRes?.factions || {};
  const ready = lobbyRes?.ready || {};
  const hasRoom = !!(gameId && playerId && players.length);
  const isHost = hasRoom && lobbyRes?.host_id === playerId;
  const meChose = !!chosen[playerId];
  const meReady = !!ready[playerId];
  const enoughPlayers = players.length >= 2;
  const everyoneChose = enoughPlayers && Object.keys(chosen).length === players.length;
  const everyoneReady = enoughPlayers && players.every(([pid]) => ready[pid]);
  const hasRedArmy = Object.values(chosen).includes('red_army');
  return {players, chosen, ready, hasRoom, isHost, meChose, meReady, enoughPlayers, everyoneChose, everyoneReady, hasRedArmy};
}

function updateLobbyActionControls(lobbyRes = latestLobbyState) {
  const startBtn = document.getElementById('startGameBtn');
  const readyBtn = document.getElementById('toggleReadyBtn');
  const status = lobbyReadiness(lobbyRes);
  const marketMode = lobbyRes?.market_mode || document.getElementById('marketModeSelect')?.value || 'sample_53';
  applyMarketMode(marketMode);
  document.querySelectorAll('.lobby-market-option').forEach(button => {
    button.disabled = !status.isHost;
    button.setAttribute('aria-disabled', String(!status.isHost));
    const cardCounts = button.dataset.cardCounts || '';
    const hostNote = status.isHost
      ? ''
      : status.hasRoom
        ? ' 只有房主可以切換遊戲難易度。'
        : ' 建立房間後，只有房主可以切換遊戲難易度。';
    button.dataset.tooltip = `${cardCounts}${hostNote}`.trim();
  });

  if (readyBtn) {
    readyBtn.disabled = !status.hasRoom || !status.meChose;
    readyBtn.textContent = status.meReady ? '取消準備' : '我已準備';
    readyBtn.title = !status.hasRoom
      ? '請先建立或進入作戰室'
      : !status.meChose
        ? '請先選擇陣營與根據地'
        : status.meReady ? '取消你的準備狀態' : '確認準備狀態';
  }

  if (startBtn) {
    startBtn.disabled = !(status.isHost && status.everyoneChose && status.everyoneReady && status.hasRedArmy);
    startBtn.title = !status.hasRoom
      ? '請先建立作戰室'
      : !status.isHost
        ? '只有房主可以啟動行動'
        : !status.enoughPlayers
          ? '至少需要 2 位玩家'
          : !status.everyoneChose
            ? '所有玩家都需要先選擇陣營'
            : !status.everyoneReady
              ? '所有玩家都需要按下準備'
              : !status.hasRedArmy
                ? '房間必須有一名紅軍玩家，才能啟動行動'
                : '所有玩家已準備，可以啟動行動';
  }
}

async function refreshLobbyState(statusText = null) {
  if (!gameId) return null;
  if (statusText) lobbyTransientStatus = statusText;
  const res = await fetch(`/lobby/${gameId}`);
  const lobbyRes = await res.json();
  if (lobbyRes.error) {
    updateLobbyStatus(playerMessageZhTw(lobbyRes.error));
    return null;
  }
  await loadFactions();
  if (lobbyRes.started && !ws) {
    updateLobbyStatus('作戰已啟動，正在進入遊戲。');
    connect();
    return lobbyRes;
  }
  renderLobbyRoster(lobbyRes, statusText);
  return lobbyRes;
}

function startLobbySync() {
  if (lobbySyncTimer) clearInterval(lobbySyncTimer);
  lobbySyncTimer = setInterval(() => {
    if (!gameId || ws) return;
    refreshLobbyState().catch(err => console.warn('Lobby sync failed', err));
  }, 1500);
}

function stopLobbySync() {
  if (lobbySyncTimer) clearInterval(lobbySyncTimer);
  lobbySyncTimer = null;
}

async function toggleReady() {
  if (!gameId || !playerId) {
    updateLobbyStatus('請先建立或進入作戰室。');
    return;
  }
  const nextReady = !latestLobbyState?.ready?.[playerId];
  const res = await fetch('/ready', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ game_id: gameId, player_id: playerId, ready: nextReady })
  });
  const data = await res.json();
  if (data.error) {
    updateLobbyStatus(playerMessageZhTw(data.error));
    await refreshLobbyState();
    return;
  }
  await refreshLobbyState(nextReady ? '你已標記準備，等待其他玩家。' : '你已取消準備。');
}

function currentRoomCode() {
  return (gameId || document.getElementById('roomId')?.value || '').trim();
}

function syncLobbyRoomCode() {
  const roomInput = document.getElementById('roomId');
  const lobby = document.getElementById('lobby');
  const value = currentRoomCode();
  if (roomInput) roomInput.title = value || '貼上房間代碼後按「進入作戰室」，或按「建立作戰室」建立新房間。';
  if (lobby) lobby.classList.toggle('room-active', !!value);
}

function applyMarketMode(mode) {
  const select = document.getElementById('marketModeSelect');
  if (select) select.value = mode;
  document.querySelectorAll('.lobby-market-option').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.marketMode === mode);
  });
}

async function setMarketMode(mode) {
  const status = lobbyReadiness();
  if (!status.isHost) {
    updateLobbyStatus(status.hasRoom ? '只有房主可以切換遊戲難易度。' : '請先建立作戰室。');
    updateLobbyActionControls();
    return;
  }
  const res = await fetch('/market-mode', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({game_id: gameId, player_id: playerId, market_mode: mode}),
  });
  const data = await res.json();
  if (data.error) {
    updateLobbyStatus(data.error === 'Only host can change game difficulty' ? '只有房主可以切換遊戲難易度。' : playerMessageZhTw(data.error));
    await refreshLobbyState();
    return;
  }
  applyMarketMode(data.market_mode || mode);
  await refreshLobbyState(data.market_mode === 'all_cards' ? '遊戲難易度已改為一般模式。' : '遊戲難易度已改為簡單模式。');
}

function selectRoomCodeForManualCopy(roomIdValue) {
  const roomInput = document.getElementById('roomId');
  if (roomInput) {
    roomInput.focus();
    roomInput.select();
    roomInput.setSelectionRange(0, roomInput.value.length);
    return;
  }
  const selection = window.getSelection();
  if (selection) selection.removeAllRanges();
}

function copyRoomIdWithExecCommand(roomIdValue) {
  const copyTarget = document.createElement('textarea');
  copyTarget.value = roomIdValue;
  copyTarget.setAttribute('readonly', 'readonly');
  copyTarget.setAttribute('aria-hidden', 'true');
  copyTarget.style.position = 'fixed';
  copyTarget.style.left = '-9999px';
  copyTarget.style.top = '0';
  document.body.appendChild(copyTarget);
  copyTarget.focus();
  copyTarget.select();
  copyTarget.setSelectionRange(0, copyTarget.value.length);
  let copied = false;
  try {
    copied = document.execCommand && document.execCommand('copy');
  } catch (err) {
    copied = false;
  }
  document.body.removeChild(copyTarget);
  return !!copied;
}

// 區網連線資訊（2026-07-19 使用者需求：開房的人要能把 IP:port 告訴其他玩家）
async function loadLanInfo() {
  const input = document.getElementById('lanUrl');
  if (!input) return;
  try {
    const res = await fetch('/server-info');
    const data = await res.json();
    if (data.base_url) {
      // base_url 是後端依這次請求實際連線方式（Host header／反向代理標頭）組出來的
      // 完整網址，部署到 Docker 發布 port 或 Render 這類網域後面時都是對的；
      // 舊的 lan_ip+port 只在裸機直接 uv run 時才靠猜測法補上（見 server-info 註解）。
      input.value = data.base_url;
    } else if (data.lan_ip) {
      input.value = `http://${data.lan_ip}:${data.port}`;
    } else {
      input.value = '無法自動偵測（請查本機 IP，網址為 http://<IP>:' + (data.port || location.port || 8000) + '）';
    }
  } catch (err) {
    input.value = '偵測失敗，請確認伺服器狀態。';
  }
}

async function copyLanUrl() {
  const input = document.getElementById('lanUrl');
  const value = (input?.value || '').trim();
  if (!value.startsWith('http')) {
    updateLobbyStatus('尚未取得區網網址，無法複製。');
    return;
  }
  if (copyRoomIdWithExecCommand(value)) {
    updateLobbyStatus('連線網址已複製，分享給其他玩家後，記得也給他們房間代碼。');
    return;
  }
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
    await navigator.clipboard.writeText(value);
    updateLobbyStatus('連線網址已複製，分享給其他玩家後，記得也給他們房間代碼。');
  } catch (err) {
    updateLobbyStatus(`自動複製失敗，請手動複製：${value}`);
  }
}

async function copyRoomId() {
  const roomIdValue = currentRoomCode();
  if (!roomIdValue) {
    updateLobbyStatus('尚未建立作戰室，沒有可複製的房間代碼。');
    window.__lastRoomCopyResult = { ok: false, method: 'empty', value: '' };
    return;
  }

  if (copyRoomIdWithExecCommand(roomIdValue)) {
    updateLobbyStatus('房間代碼已複製，可以分享給其他玩家。');
    window.__lastRoomCopyResult = { ok: true, method: 'execCommand', value: roomIdValue };
    return;
  }

  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard API unavailable');
    await navigator.clipboard.writeText(roomIdValue);
    updateLobbyStatus('房間代碼已複製，可以分享給其他玩家。');
    window.__lastRoomCopyResult = { ok: true, method: 'clipboard', value: roomIdValue };
  } catch (err) {
    selectRoomCodeForManualCopy(roomIdValue);
    updateLobbyStatus('無法自動複製；已選取房間代碼，請按 Ctrl+C / ⌘C 手動複製。');
    window.__lastRoomCopyResult = { ok: false, method: 'manual-select', value: roomIdValue };
  }
}

function initProofSessionFromUrl() {
  if (ws || gameId || playerId) return false;
  const params = new URLSearchParams(window.location.search || '');
  const proofGameId = params.get('game_id');
  const proofPlayerId = params.get('player_id');
  if (!proofGameId || !proofPlayerId) return false;
  gameId = proofGameId;
  playerId = proofPlayerId;
  resumeToken = params.get('resume_token') || null;
  connect();
  return true;
}

async function resumeStoredGame() {
  const saved = latestRedlineSession();
  if (!saved) return false;
  const res = await fetch('/resume', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      game_id: saved.game_id,
      player_id: saved.player_id,
      resume_token: saved.resume_token,
      device_id: redlineDeviceId(),
    }),
  });
  const data = await res.json();
  if (data.error) {
    if (data.error === 'Game not found' || data.error === 'Player not found in lobby') {
      removeRedlineSession(saved.game_id);
    }
    return false;
  }
  gameId = data.game_id;
  playerId = data.player_id;
  resumeToken = data.resume_token;
  const roomInput = document.getElementById('roomId');
  const nameInput = document.getElementById('playerName');
  if (roomInput) roomInput.value = gameId;
  if (nameInput && data.name) nameInput.value = data.name;
  saveRedlineSession(data.name);
  if (data.started) {
    connect({reconnect: true});
  } else {
    await loadFactions();
    startLobbySync();
    await renderFactionPicker();
    await refreshLobbyState('已恢復原本的作戰席位。');
  }
  return true;
}

async function initLobbyControls() {
  resizeStage();
  const params = new URLSearchParams(window.location.search || '');
  const startFresh = params.get('new_game') === '1' || sessionStorage.getItem('redline.start_fresh_once') === '1';
  if (startFresh) {
    sessionStorage.removeItem('redline.start_fresh_once');
    history.replaceState(null, '', window.location.pathname);
    gameId = null;
    playerId = null;
    resumeToken = null;
  } else if (initProofSessionFromUrl()) {
    return;
  }
  if (!stageResizeBound) {
    window.addEventListener('resize', resizeStage);
    stageResizeBound = true;
  }
  loadLanInfo();
  const nameInput = document.getElementById('playerName');
  if (nameInput && nameInput.dataset.bound !== '1') {
    nameInput.dataset.bound = '1';
    nameInput.addEventListener('input', () => {
      lobbyTransientStatus = null;
      updateLobbyStatus();
    });
  }
  const roomInput = document.getElementById('roomId');
  if (roomInput && roomInput.dataset.bound !== '1') {
    roomInput.dataset.bound = '1';
    roomInput.addEventListener('input', syncLobbyRoomCode);
  }
  const select = document.getElementById('marketModeSelect');
  applyMarketMode(select?.value || 'sample_53');
  updateLobbyStatus();
  updateLobbyActionControls();
  syncLobbyRoomCode();
  if (!startFresh) await resumeStoredGame();
}

async function setActiveGameView(view) {
  const tabs = document.querySelectorAll('.game-tab');
  const views = document.querySelectorAll('.game-view');
  if (!tabs.length || !views.length) return;
  tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.view === view));
  views.forEach(v => v.classList.toggle('active', v.id === `${view}View`));

  if (view === 'map') {
    await ensureStrategicMapMounted();
  }
}

function initTabs() {
  const tabs = document.querySelectorAll('.game-tab');
  const views = document.querySelectorAll('.game-view');
  if (!tabs.length || !views.length) return;

  tabs.forEach(tab => {
    if (!tab.dataset.view) return;
    if (tab.dataset.bound === '1') return;
    tab.dataset.bound = '1';
    tab.addEventListener('click', async () => {
      await setActiveGameView(tab.dataset.view);
    });
  });
}

async function loadFactions() {
  if (availableFactionCategories.length) return availableFactionCategories;
  const res = await fetch('/factions');
  const data = await res.json();
  availableFactionCategories = data.categories || [];
  return availableFactionCategories;
}

async function loadCardPresentationCatalog() {
  if (cardPresentationCatalog) return cardPresentationCatalog;
  const res = await fetch('/card-presentation');
  const data = await res.json();
  cardPresentationCatalog = data.cards || {};
  return cardPresentationCatalog;
}

async function createRoom() {
  // 建房也要帶「行動代號」：/create 之前不吃名字、建房者永遠叫 host
  //（2026-07-18 自動桌測發現，2026-07-19 修正）。
  const creatorName = (document.getElementById('playerName')?.value || '').trim();
  const res = await fetch('/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: creatorName, device_id: redlineDeviceId() }),
  });
  const data = await res.json();
  gameId = data.game_id;
  playerId = data.host_id;
  resumeToken = data.resume_token;
  saveRedlineSession(creatorName);
  const roomInput = document.getElementById('roomId');
  if (roomInput) {
    roomInput.value = gameId;
    syncLobbyRoomCode();
  }
  const marketSelect = document.getElementById('marketModeSelect');
  if (marketSelect) applyMarketMode('sample_53');
  lobbyTransientStatus = '作戰室已建立；請選擇陣營，或分享房間代碼。';
  await loadFactions();
  startLobbySync();
  await renderFactionPicker();
  updateLobbyStatus(lobbyTransientStatus);
}

async function chooseFaction(factionId) {
  lobbyTransientStatus = null;
  pendingFactionChoice = factionId;
  pendingFactionBaseGroup = null;
  const opt = factionOptionById(factionId);
  const baseOptions = opt?.base_options || [];
  const baseResolved = opt?.base_resolved || {};
  if (baseOptions.length === 1) {
    const only = baseOptions[0];
    const towns = baseResolved[only] || [only];
    pendingFactionBaseChoice = towns.length === 1 ? towns[0] : null;
    pendingFactionBaseGroup = towns.length === 1 ? only : null;
  } else {
    pendingFactionBaseChoice = null;
  }
  await renderFactionPicker();
}

async function confirmFactionChoice() {
  if (!pendingFactionChoice) return;
  const selectedOption = factionOptionById(pendingFactionChoice);
  const baseOptions = selectedOption?.base_options || [];
  const baseResolved = selectedOption?.base_resolved || {};
  let chosenBase = pendingFactionBaseChoice;
  if (!chosenBase && baseOptions.length === 1) {
    const only = baseOptions[0];
    const resolvedOnly = baseResolved[only];
    const towns = Array.isArray(resolvedOnly) && resolvedOnly.length ? resolvedOnly : [only];
    chosenBase = towns[0] || only;
  }
  const res = await fetch('/choose-faction', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ game_id: gameId, player_id: playerId, faction_id: pendingFactionChoice, base_name: chosenBase })
  });
  const data = await res.json();
  if (data.error) {
    updateLobbyStatus(playerMessageZhTw(data.error));
    return;
  }
  pendingFactionChoice = null;
  pendingFactionBaseChoice = null;
  pendingFactionBaseGroup = null;
  pendingFactionCategory = null;
  await refreshLobbyState('陣營已確認，請按下準備。');
  await renderFactionPicker();
}

function factionCategoryOf(factionId) {
  if (factionId === 'red_army') return 'red_army';
  if (['taiwan_green', 'taiwan_blue'].includes(factionId)) return 'taiwan';
  if (['uyghur_family', 'uyghur_istanbul', 'uyghur_munich', 'uyghur_washington', 'uyghur_almaty'].includes(factionId)) return 'uyghur';
  if (['tibet_family', 'tibet_dharamsala', 'tibet_dehradun', 'tibet_chogu'].includes(factionId)) return 'tibet';
  if (['hong_kong', 'manchuria', 'mongol', 'kazakh'].includes(factionId)) return factionId;
  return 'rebel';
}

// 與地圖 iframe（leaflet_game_map_logic.js 的 palette／FACTION_COLOR_OVERRIDE）一致的陣營代表色，
// 供玩家名稱字色使用（2026-07-18 使用者需求：使用者名稱字色＝陣營色）。
// 2026-07-18 依使用者提供的原版桌遊陣營色校正（香港紫/蒙古深藍/藏國綠/哈薩克青綠/維吾爾淺藍/滿洲金黃）。
const FACTION_CATEGORY_COLOR = {
  red_army: '#f04f56', taiwan: '#3fb6ff', hong_kong: '#a855f7', tibet: '#15803d',
  uyghur: '#93c5fd', kazakh: '#14b8a6', mongol: '#2563eb', manchuria: '#eab308', rebel: '#f97316',
};
const FACTION_NAME_COLOR_OVERRIDE = { taiwan_green: '#4ade80', taiwan_blue: '#3fb6ff' };

function factionNameColor(factionId) {
  if (!factionId) return null;
  return FACTION_NAME_COLOR_OVERRIDE[factionId] || FACTION_CATEGORY_COLOR[factionCategoryOf(factionId)] || null;
}

function factionDisplayName(factionId) {
  for (const category of availableFactionCategories) {
    for (const opt of (category.options || [])) {
      if (opt.id !== factionId) continue;
      if (factionId === 'taiwan_green') return '臺灣（綠線）';
      if (factionId === 'taiwan_blue') return '臺灣（藍線）';
      if (category.id === 'uyghur' || category.id === 'tibet') {
        if (opt.id === `${category.id}_family`) return category.label;
        return `${category.label}（${opt.variant || opt.name || opt.id}）`;
      }
      return opt.variant || opt.name || opt.label || opt.id;
    }
  }

  const fallbackNames = {
    red_army: '紅軍',
    taiwan_green: '臺灣（綠線）',
    taiwan_blue: '臺灣（藍線）',
    hong_kong: '香港',
    manchuria: '滿洲',
    mongol: '蒙古',
    kazakh: '哈薩克',
    uyghur_family: '維吾爾',
    uyghur_istanbul: '維吾爾（伊斯坦堡）',
    uyghur_munich: '維吾爾（慕尼黑）',
    uyghur_washington: '維吾爾（華府）',
    uyghur_almaty: '維吾爾（阿拉木圖）',
    tibet_family: '西藏',
    tibet_dharamsala: '西藏（達蘭薩拉）',
    tibet_dehradun: '西藏（德拉敦）',
    tibet_chogu: '西藏（錯古）'
  };
  return fallbackNames[factionId] || factionId || '未選陣營';
}

function factionOptionById(factionId) {
  for (const category of availableFactionCategories) {
    for (const opt of (category.options || [])) {
      if (opt.id === factionId) return opt;
    }
  }
  return null;
}

function humanizeWinCondition(w) {
  if (!w) return '（暫無資料）';
  if (typeof w === 'string') return w;
  if (w.text) return w.text;

  if (w.type === 'count_only') {
    return `回合結束時在${w.scope || '指定區域'}擁有至少 ${w.count} 個有效組織。`;
  }

  if (w.type === 'count_and_required') {
    const required = (w.required_locations || []).join('、');
    return `回合結束時在${w.scope || '指定區域'}擁有至少 ${w.count} 個有效組織，且必須包含 ${required}。`;
  }

  if (w.type === 'default_survival') {
    return w.text || '遊戲結束前未有反共陣營玩家達成勝利條件。';
  }

  if (w.type === 'taiwan_override') {
    return w.text || '若有玩家選用臺灣，紅軍在臺灣城鎮達成指定組織數時直接獲勝。';
  }

  return JSON.stringify(w, null, 0);
}

function baseDisplayName(baseName) {
  if (!baseName) return '';
  return baseName;
}

const CARD_COLOR_STYLES = {
  '灰': {
    accent: '#9ca3af',
    bg: 'linear-gradient(180deg, rgba(156,163,175,.18) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(156,163,175,.62)',
    title: '#f3f4f6',
    tagBg: 'rgba(156,163,175,.20)',
    tagBorder: 'rgba(156,163,175,.72)',
    tagText: '#f9fafb'
  },
  '銅': {
    accent: '#b87333',
    bg: 'linear-gradient(180deg, rgba(184,115,51,.20) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(184,115,51,.72)',
    title: '#ffd6a3',
    tagBg: 'rgba(184,115,51,.22)',
    tagBorder: 'rgba(184,115,51,.78)',
    tagText: '#ffe1bd'
  },
  '紫': {
    accent: '#a78bfa',
    bg: 'linear-gradient(180deg, rgba(167,139,250,.22) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(167,139,250,.68)',
    title: '#ddd6fe',
    tagBg: 'rgba(167,139,250,.22)',
    tagBorder: 'rgba(167,139,250,.82)',
    tagText: '#ede9fe'
  },
  '青': {
    accent: '#22d3ee',
    bg: 'linear-gradient(180deg, rgba(34,211,238,.18) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(34,211,238,.66)',
    title: '#cffafe',
    tagBg: 'rgba(34,211,238,.20)',
    tagBorder: 'rgba(34,211,238,.78)',
    tagText: '#ecfeff'
  },
  '藍': {
    accent: '#60a5fa',
    bg: 'linear-gradient(180deg, rgba(96,165,250,.18) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(96,165,250,.68)',
    title: '#dbeafe',
    tagBg: 'rgba(96,165,250,.22)',
    tagBorder: 'rgba(96,165,250,.80)',
    tagText: '#eff6ff'
  },
  '綠': {
    accent: '#4ade80',
    bg: 'linear-gradient(180deg, rgba(74,222,128,.18) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(74,222,128,.64)',
    title: '#dcfce7',
    tagBg: 'rgba(74,222,128,.19)',
    tagBorder: 'rgba(74,222,128,.78)',
    tagText: '#f0fdf4'
  },
  '棕': {
    accent: '#a16207',
    bg: 'linear-gradient(180deg, rgba(161,98,7,.22) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(161,98,7,.72)',
    title: '#fde68a',
    tagBg: 'rgba(161,98,7,.23)',
    tagBorder: 'rgba(161,98,7,.82)',
    tagText: '#fef3c7'
  },
  '橘': {
    accent: '#f59e0b',
    bg: 'linear-gradient(180deg, rgba(245,158,11,.20) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(245,158,11,.72)',
    title: '#ffedd5',
    tagBg: 'rgba(245,158,11,.22)',
    tagBorder: 'rgba(245,158,11,.82)',
    tagText: '#fff7ed'
  },
  '紅': {
    accent: '#ef4444',
    bg: 'linear-gradient(180deg, rgba(239,68,68,.18) 0%, rgba(255,255,255,.025) 100%)',
    border: 'rgba(239,68,68,.68)',
    title: '#fee2e2',
    tagBg: 'rgba(239,68,68,.22)',
    tagBorder: 'rgba(239,68,68,.82)',
    tagText: '#fef2f2'
  },
  '奧援': {
    accent: '#f59e0b',
    bg: 'linear-gradient(135deg, rgba(245,158,11,.18), rgba(96,165,250,.10))',
    border: 'rgba(245,158,11,.76)',
    title: '#ffedd5',
    tagBg: 'rgba(245,158,11,.24)',
    tagBorder: 'rgba(245,158,11,.86)',
    tagText: '#fff7ed'
  }
};

function cardColorClass(colorName) {
  const mapping = {
    '灰': 'card-color-gray',
    '銅': 'card-color-copper',
    '紫': 'card-color-purple',
    '青': 'card-color-cyan',
    '藍': 'card-color-blue',
    '綠': 'card-color-green',
    '棕': 'card-color-brown',
    '橘': 'card-color-orange',
    '紅': 'card-color-red',
    '奧援': 'card-color-support',
  };
  return mapping[colorName] || '';
}

function styleVars(style) {
  return [
    `--card-accent:${style.accent}`,
    `--card-bg:${style.bg}`,
    `--card-border:${style.border}`,
    `--card-title:${style.title}`,
    `--tag-bg:${style.tagBg}`,
    `--tag-border:${style.tagBorder}`,
    `--tag-text:${style.tagText}`,
  ].join(';');
}

function cardColorStyle(color) {
  return CARD_COLOR_STYLES[color] || CARD_COLOR_STYLES['灰'];
}

function cardPresentation(cardName) {
  return (cardPresentationCatalog || {})[cardName] || null;
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function jsSingleQuotedString(value) {
  return `'${String(value || '')
    .replaceAll('\\', '\\\\')
    .replaceAll("'", "\\'")
    .replaceAll('\n', '\\n')}'`;
}

function splitEffectLines(text) {
  return String(text || '')
    .split(/\n+/)
    .map(s => s.trim())
    .filter(Boolean);
}

function splitBadgeItems(text) {
  return String(text || '')
    .split(/[+、]/)
    .map(s => s.trim())
    .filter(Boolean);
}

function renderBadgeList(items, className = '') {
  if (!items.length) return '';
  return `<div class="card-badges ${className}">${items.map(item => `<span class="card-badge">${escapeHtml(item)}</span>`).join('')}</div>`;
}

function staticCardCatalogCount(cardName) {
  const raw = cardPresentation(cardName)?.count_text;
  const parsed = Number.parseInt(String(raw ?? '').trim(), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function liveStaticSupplyForCard(state, cardName) {
  const raw = state?.static_purchase_supply?.[cardName];
  const parsed = Number.parseInt(String(raw ?? '').trim(), 10);
  if (Number.isFinite(parsed)) return parsed;
  return staticCardCatalogCount(cardName);
}

function supportVariantEffectText(info, variantInfo) {
  const variants = info.support_variants;
  if (!Array.isArray(variants) || !variants.length) return null;
  const idx = variantInfo && Number.isInteger(variantInfo.variant_index) ? variantInfo.variant_index : 0;
  const v = variants[idx] || variants[0];
  const tier2Regions = (v.tier2_regions || []).join('/');
  return [
    `III級（${v.tier3_region}主導）：${v.tier3_text}`,
    `II級（${tier2Regions}其一主導）：${v.tier2_text}`,
    `I級（皆未主導）：${v.tier1_text}`,
  ].join('\n');
}

const SUPPORT_CARD_ART_FILES = {
  '英美奧援': ['01_英美奧援_歐洲-天方.png', '02_英美奧援_東洋-臺灣.png'],
  '東洋奧援': ['03_東洋奧援_臺灣-南洋.png', '04_東洋奧援_北國-英美.png'],
  '南洋奧援': ['05_南洋奧援_臺灣-東洋.png', '06_南洋奧援_印度-天方.png'],
  '印度奧援': ['07_印度奧援_南洋-英美.png', '08_印度奧援_天方-北國.png'],
  '天方奧援': ['09_天方奧援_印度-南洋.png', '10_天方奧援_北國-歐洲.png'],
  '歐洲奧援': ['11_歐洲奧援_北國-天方.png', '12_歐洲奧援_英美-南洋.png'],
  '北國奧援': ['13_北國奧援_歐洲-東洋.png', '14_北國奧援_天方-印度.png'],
  '臺灣奧援': ['15_臺灣奧援_東洋-南洋.png', '16_臺灣奧援_英美-歐洲.png'],
  '紅軍奧援': ['17_紅軍奧援_起始牌.png'],
};

function playableCardArtUrl(cardName, variantInfo = null) {
  const name = String(cardName || '').trim();
  if (!name || !cardPresentation(name)) return '';
  if (/奧援/.test(name)) {
    const files = SUPPORT_CARD_ART_FILES[name];
    if (!files?.length) return '';
    const requestedIndex = variantInfo && Number.isInteger(variantInfo.variant_index)
      ? variantInfo.variant_index
      : 0;
    const file = files[requestedIndex] || files[0];
    const version = name === '紅軍奧援' ? '?v=action-card-layout-20260811' : '';
    return `/static/card-art/support/${encodeURIComponent(file)}${version}`;
  }
  return `/static/card-art/actions/${encodeURIComponent(name)}.png?v=head-safe-20260726`;
}

function renderCardFace(cardName, zone, isStatic = false, compact = false, countOverride = null, variantInfo = null) {
  const info = cardPresentation(cardName) || {};
  const isSupport = /奧援/.test(cardName);
  const color = info.color || (isSupport ? '奧援' : '灰');
  const colorClass = cardColorClass(color);
  const colorStyle = styleVars(cardColorStyle(color));
  const typeLabel = zone === 'hand' ? '手牌' : (isStatic ? '常設購買區' : '隨機購買區');
  const headerMeta = [info.kind, info.strength, info.cost_text].filter(Boolean).join(' ・ ');
  // 這張牌實體只印一組 II 級門檻地區；有 variantInfo（來自 state 的 hand_variants／
  // purchase_area_variants）時只顯示這張牌自己印的那組，而不是奧援目錄裡兩種變體都列出的
  // 通用文字（2026-07-16 使用者裁決：一張牌只看/只顯示自己印的那組）。
  const effectText = supportVariantEffectText(info, variantInfo) || info.effect_text;
  const effectLines = splitEffectLines(effectText || (isSupport ? '奧援卡，依區域主導者判定 I・II・III 級效果。' : '（暫無資料）'));
  const badgeItems = [];
  // 奧援卡的含義行（「奧援卡」）與徽章（「資源 依效果而定」「隨機購買區」）沒有資訊量，
  // 卻佔掉卡面下方空間，導致天方奧援等三級文字較長的卡 I 級文字被截斷；奧援卡一律省略，
  // 把空間留給完整的 I/II/III 級效果文字。
  if (!isSupport && info.resource_text) {
    badgeItems.push(`資源 ${info.resource_text}`);
  }
  const meaning = (info.meaning_text && !isSupport) ? `<div class="card-meaning">${escapeHtml(info.meaning_text)}</div>` : '';
  // 只在常設購買區顯示即時剩餘供應；手牌與隨機牌庫的目錄張數不是目前供應量，
  // 而且會遮住完整卡面的購買費用。
  const countText = isStatic
    ? (countOverride != null ? String(countOverride) : info.count_text)
    : null;
  const count = countText ? `<div class="card-count">剩 ${escapeHtml(countText)}</div>` : '';
  const textFace = `
    <div class="card-face ${colorClass}${compact ? ' compact' : ''}" style="${colorStyle}">
      <div class="card-face-top">
        <div class="purchase-card-title">${escapeHtml(cardName)}</div>
        ${count}
      </div>
      <div class="card-face-meta-row">${escapeHtml(headerMeta || (isSupport ? '奧援 ・ 特殊' : typeLabel))}</div>
      <div class="purchase-card-body card-effect-block">
        ${effectLines.slice(0, compact ? 3 : 6).map(line => `<div>${escapeHtml(line)}</div>`).join('')}
      </div>
      ${meaning}
      ${renderBadgeList(badgeItems)}
    </div>`;
  const artUrl = playableCardArtUrl(cardName, variantInfo);
  if (!artUrl) return textFace;
  return `
    <div class="card-face card-art-face ${colorClass}${compact ? ' compact' : ''}" style="${colorStyle}">
      <img class="playable-card-art-image" src="${artUrl}" alt="${escapeHtml(cardName)}完整卡面" decoding="async" onerror="this.parentElement.classList.add('playable-card-art-load-failed')">
      ${count}
      <div class="playable-card-art-fallback">${textFace}</div>
    </div>`;
}

function closeCardPreview() {
  const overlay = document.getElementById('cardPreviewModal');
  if (overlay) overlay.style.display = 'none';
}

function selectCardDetail(cardElement) {
  const overlay = document.getElementById('cardPreviewModal');
  const preview = document.getElementById('cardPreviewContent');
  if (!overlay || !preview || !(cardElement instanceof HTMLElement)) return;

  const cardName = cardElement.dataset.cardName || '';
  const zone = cardElement.dataset.cardZone || 'purchase';
  const isStatic = cardElement.dataset.cardStatic === 'true';
  const countText = cardElement.dataset.cardCount || null;
  const variantIndex = Number.parseInt(cardElement.dataset.cardVariantIndex || '', 10);
  const variantInfo = Number.isInteger(variantIndex) ? {variant_index: variantIndex} : null;
  if (!cardName) return;

  preview.innerHTML = renderCardFace(cardName, zone, isStatic, false, countText, variantInfo);
  overlay.setAttribute('aria-label', `${cardName} 放大檢視`);
  overlay.style.display = 'flex';
}

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    closeCardPreview();
    closeEventReveal();
  }
});

function factionAbilityText(item) {
  return typeof item === 'string'
    ? item
    : [item?.name_override || item?.name, item?.trigger, item?.effect].filter(Boolean).join('：');
}

function hongKongBaseOverviewItems(faction, currentBase = null) {
  if (!faction || faction.id !== 'hong_kong') return [];
  return (faction.bases || []).map(base => {
    const marker = base.name === currentBase ? '（目前根據地）' : (base.type === 'initial' ? '（初始根據地）' : '（可遷移根據地）');
    const abilities = (base.abilities || []).map(factionAbilityText).join('；') || '無特殊能力';
    return `${baseDisplayName(base.name)}${marker}：${abilities}`;
  });
}

function renderFactionDetails(factionId, selectedBaseName = null, selectedBaseGroupName = null) {
  const panel = document.getElementById('factionDetailPanel');
  const title = document.getElementById('factionDetailTitle');
  const basesEl = document.getElementById('factionDetailBases');
  const abilitiesEl = document.getElementById('factionDetailAbilities');
  const rulesEl = document.getElementById('factionDetailRules');
  const winEl = document.getElementById('factionDetailWin');
  if (!panel || !title || !basesEl || !abilitiesEl || !rulesEl || !winEl) return;

  if (!factionId) {
    panel.style.display = 'none';
    title.textContent = '';
    basesEl.innerHTML = '';
    abilitiesEl.innerHTML = '';
    rulesEl.innerHTML = '';
    winEl.innerHTML = '';
    return;
  }

  const opt = factionOptionById(factionId);
  if (!opt) {
    panel.style.display = 'none';
    return;
  }

  const activeDetailBase = selectedBaseName || pendingFactionBaseChoice;
  const activeDetailBaseGroup = selectedBaseGroupName || pendingFactionBaseGroup;
  const detailSource = (activeDetailBase && opt.variant_details)
    ? (opt.variant_details[activeDetailBase] || null)
    : null;
  const detail = detailSource || opt;
  const selectedBaseData = (detail.bases || []).find(base => base?.name === activeDetailBase) || null;
  const rawAbilities = [
    ...((detail.abilities_text || detail.abilities || [])),
    ...((selectedBaseData?.abilities) || []),
  ];
  const renderFactionDetailItem = item => typeof item === 'string'
    ? item
    : [item.name_override || item.name, item.trigger, item.effect].filter(Boolean).join('：');
  const abilities = rawAbilities.filter(item => !(typeof item === 'object' && item && ['setup', 'restriction'].includes(item.type)));
  const rules = [
    ...(detail.setup_effects || []),
    ...(detail.special_rules || []),
    ...(detail.restrictions || []),
    ...rawAbilities
      .filter(item => typeof item === 'object' && item && ['setup', 'restriction'].includes(item.type))
      .map(renderFactionDetailItem),
  ];
  const wins = detail.win_condition_text
    ? [detail.win_condition_text]
    : (detail.win_conditions || []).map(humanizeWinCondition);

  title.textContent = detailSource ? `${opt.name || factionDisplayName(factionId)}（${detailSource.variant || activeDetailBase}）` : factionDisplayName(factionId);
  const hkBaseOverview = hongKongBaseOverviewItems(detail, activeDetailBase);
  basesEl.innerHTML = hkBaseOverview.length
    ? `<div class="faction-detail-section-title">根據地遷移與能力</div><ul>${hkBaseOverview.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
    : activeDetailBase
      ? `<div class="faction-detail-section-title">根據地</div><ul><li>${baseDisplayName(activeDetailBase)}</li></ul>`
      : (activeDetailBaseGroup ? `<div class="faction-detail-section-title">根據地類別</div><ul><li>${baseDisplayName(activeDetailBaseGroup)}</li></ul>` : '');
  abilitiesEl.innerHTML = `<div class="faction-detail-section-title">能力</div><ul>${abilities.map(a => `<li>${renderFactionDetailItem(a)}</li>`).join('') || '<li>（暫無資料）</li>'}</ul>`;
  rulesEl.innerHTML = `<div class="faction-detail-section-title">規則</div><ul>${rules.map(r => `<li>${r}</li>`).join('') || '<li>（暫無資料）</li>'}</ul>`;
  winEl.innerHTML = `<div class="faction-detail-section-title">獲勝條件</div><ul>${wins.map(w => `<li>${w}</li>`).join('') || '<li>（暫無資料）</li>'}</ul>`;
  panel.style.display = 'block';
}

async function renderFactionPicker() {
  const panel = document.getElementById('factionPicker');
  const info = document.getElementById('factionPickerInfo');
  const list = document.getElementById('factionList');
  const variants = document.getElementById('factionVariantList');
  const bases = document.getElementById('factionBaseList');
  const confirmBar = document.getElementById('factionConfirmBar');
  const confirmBtn = document.getElementById('confirmFactionBtn');
  if (!panel || !info || !list || !variants || !bases || !confirmBar || !confirmBtn || !gameId || !playerId) return;

  const [lobbyRes] = await Promise.all([
    fetch(`/lobby/${gameId}`).then(r => r.json()),
    loadFactions(),
  ]);

  panel.style.display = 'block';
  const chosen = lobbyRes.factions || {};
  const chosenBases = lobbyRes.bases || {};
  renderLobbyRoster(lobbyRes);
  const confirmed = chosen[playerId] || null;
  const confirmedBase = chosenBases[playerId] || null;
  const activeChoice = pendingFactionChoice || confirmed;
  const activeBase = pendingFactionBaseChoice || confirmedBase;
  const activeBaseGroup = pendingFactionBaseGroup || null;
  const requiredFaction = (lobbyRes.required_faction_by_player || {})[playerId] || null;
  if (requiredFaction === 'red_army' && activeChoice && activeChoice !== 'red_army') {
    pendingFactionCategory = null;
    pendingFactionChoice = null;
    pendingFactionBaseChoice = null;
    pendingFactionBaseGroup = null;
  }
  info.textContent = requiredFaction === 'red_army'
    ? '房間尚無紅軍；你是最後一個席位，只能選擇紅軍陣營。'
    : activeChoice
      ? `目前陣營：${factionDisplayName(activeChoice)}${activeBase ? `｜根據地：${baseDisplayName(activeBase)}` : (activeBaseGroup ? `｜根據地類別：${baseDisplayName(activeBaseGroup)}` : '')}`
      : '請先選擇你的陣營';

  list.innerHTML = '';
  variants.innerHTML = '';
  variants.style.display = 'none';
  bases.innerHTML = '';
  bases.style.display = 'none';
  const currentActiveOption = activeChoice ? factionOptionById(activeChoice) : null;
  const needsBaseChoice = !!(activeChoice && currentActiveOption?.base_options?.length);
  const readyForConfirm = !!activeChoice && (!requiredFaction || activeChoice === requiredFaction) && (!needsBaseChoice || !!activeBase);
  confirmBar.style.display = readyForConfirm ? 'block' : 'none';
  confirmBtn.disabled = !readyForConfirm;
  confirmBtn.onclick = confirmFactionChoice;
  renderFactionDetails(readyForConfirm ? activeChoice : null, activeBase, activeBaseGroup);

  const takenCategories = new Set(
    Object.entries(chosen)
      .filter(([pid]) => pid !== playerId)
      .map(([, fid]) => factionCategoryOf(fid))
  );

  availableFactionCategories.forEach(category => {
    const btn = document.createElement('button');
    const isSelectedCategory = activeChoice && factionCategoryOf(activeChoice) === category.id;
    btn.className = `faction-choice-btn faction-primary-btn${isSelectedCategory ? ' active' : ''}`;
    btn.textContent = category.label;
    btn.disabled = takenCategories.has(category.id) || (!!requiredFaction && category.id !== factionCategoryOf(requiredFaction));
    btn.title = requiredFaction && category.id !== factionCategoryOf(requiredFaction)
      ? '房間尚無紅軍；最後一個席位只能選擇紅軍'
      : '';
    btn.onclick = async () => {
      pendingFactionCategory = category;
      pendingFactionChoice = category.mode === 'direct' ? category.options[0].id : null;
      pendingFactionBaseChoice = null;
      pendingFactionBaseGroup = null;
      await renderFactionPicker();
    };
    list.appendChild(btn);
  });

  if (pendingFactionCategory) {
    const currentOption = (pendingFactionCategory.options || []).find(opt => opt.id === pendingFactionChoice) || null;

    if (pendingFactionCategory.mode !== 'direct') {
      variants.innerHTML = '';
      variants.style.display = 'flex';
      pendingFactionCategory.options.forEach(opt => {
        const optId = opt.id;
        const isSelectedVariant = activeChoice === optId;
        const vbtn = document.createElement('button');
        vbtn.className = `faction-choice-btn faction-variant-btn${isSelectedVariant ? ' active' : ''}`;
        vbtn.textContent = `${opt.variant || opt.name || opt.id}`;
        vbtn.onclick = async () => {
          await chooseFaction(optId);
        };
        variants.appendChild(vbtn);
      });
    }

    const baseOptions = currentOption?.base_options || [];
    const baseResolved = currentOption?.base_resolved || {};
    if (baseOptions.length) {
      bases.innerHTML = '';
      bases.style.display = 'flex';

      if (pendingFactionBaseGroup) {
        const back = document.createElement('button');
        back.className = 'base-choice-btn';
        back.textContent = '← 返回根據地類別';
        back.onclick = async () => {
          pendingFactionBaseGroup = null;
          pendingFactionBaseChoice = null;
          await renderFactionPicker();
        };
        bases.appendChild(back);

        const towns = baseResolved[pendingFactionBaseGroup] || [];
        towns.forEach(town => {
          const bbtn = document.createElement('button');
          const isSelectedTown = activeBase === town;
          bbtn.className = `base-choice-btn${isSelectedTown ? ' active' : ''}`;
          bbtn.textContent = baseDisplayName(town);
          bbtn.onclick = async () => {
            pendingFactionBaseChoice = town;
            await renderFactionPicker();
          };
          bases.appendChild(bbtn);
        });
      } else {
        baseOptions.forEach(baseName => {
          const resolvedTowns = baseResolved[baseName] || [baseName];
          const isSelectedBase = activeBaseGroup === baseName || (resolvedTowns.length === 1 && activeBase === resolvedTowns[0]);
          const bbtn = document.createElement('button');
          bbtn.className = `base-choice-btn${isSelectedBase ? ' active' : ''}`;
          bbtn.textContent = baseDisplayName(baseName);
          bbtn.onclick = async () => {
            if (resolvedTowns.length > 1) {
              pendingFactionBaseGroup = baseName;
              pendingFactionBaseChoice = null;
            } else {
              pendingFactionBaseGroup = baseName;
              pendingFactionBaseChoice = resolvedTowns[0];
            }
            await renderFactionPicker();
          };
          bases.appendChild(bbtn);
        });
      }
    }
  }
}

async function joinRoom() {
  gameId = (document.getElementById('roomId')?.value || '').trim();
  lobbyTransientStatus = null;
  const roomInput = document.getElementById('roomId');
  if (roomInput) roomInput.value = gameId;
  syncLobbyRoomCode();
  if (!gameId) {
    updateLobbyStatus('請先把房間代碼貼到「建立 / 加入房間代碼」欄位，再按進入作戰室。');
    return;
  }
  const name = document.getElementById('playerName').value;

  const savedSession = storedRedlineSessions()[gameId] || null;
  const payload = {game_id: gameId, name, device_id: redlineDeviceId()};
  if (savedSession?.player_id && savedSession?.resume_token) {
    payload.player_id = savedSession.player_id;
    payload.resume_token = savedSession.resume_token;
  } else if (playerId && resumeToken) {
    payload.player_id = playerId;
    payload.resume_token = resumeToken;
  }

  const res = await fetch('/join', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (data.error) {
    updateLobbyStatus(playerMessageZhTw(data.error));
    return;
  }

  playerId = data.player_id;
  resumeToken = data.resume_token;
  saveRedlineSession(name);
  await loadFactions();
  startLobbySync();
  await renderFactionPicker();
  updateLobbyStatus('已進入作戰室；請選擇你的陣營與根據地。');
}

async function startGame() {
  const marketMode = document.getElementById('marketModeSelect')?.value || 'sample_53';
  const res = await fetch('/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({game_id: gameId, player_id: playerId, market_mode: marketMode})
  });

  const data = await res.json();
  if (data.error) {
    updateLobbyStatus(playerMessageZhTw(data.error));
    await refreshLobbyState();
    return;
  }

  connect();
}

// Abstract map removed — replaced by Leaflet


function websocketUrl() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${location.host}/ws/${gameId}/${playerId}`;
}

function setSocketDebug(text) {
  const debug = document.getElementById('debugSocketState');
  if (debug) debug.textContent = text;
}

function scheduleReconnect(reason = 'closed') {
  if (!gameId || !playerId) return;
  if (wsReconnectTimer) return;
  const delay = Math.min(5000, 500 + wsReconnectAttempts * 500);
  wsReconnectAttempts += 1;
  setSocketDebug(`websocket:${reason}; reconnecting in ${delay}ms`);
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    connect({reconnect: true});
  }, delay);
}

function flushPendingOutboundActions() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const queued = pendingOutboundActions.splice(0, pendingOutboundActions.length);
  queued.forEach(({action, payload}) => {
    ws.send(JSON.stringify({action, ...payload}));
  });
}

function connect(options = {}) {
  stopLobbySync();
  if (!gameId || !playerId) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }
  ws = resumeToken ? new WebSocket(websocketUrl(), resumeToken) : new WebSocket(websocketUrl());

  ws.onopen = () => {
    wsReconnectAttempts = 0;
    setSocketDebug(options.reconnect ? 'websocket:reconnected' : 'websocket:open');
    flushPendingOutboundActions();
  };

  ws.onmessage = async (event) => {
    const state = JSON.parse(event.data);
    window.lastGameState = state;
    await render(state);
    syncStrategicMap(state);
  };

  ws.onclose = () => {
    ws = null;
    scheduleReconnect('closed');
  };

  ws.onerror = () => {
    setSocketDebug('websocket:error');
    if (ws) ws.close();
  };

  document.getElementById('lobby').style.display = 'none';
  const gameHud = document.getElementById('hud');
  if (gameHud) gameHud.style.display = 'flex';
  const shell = document.getElementById('gameShell');
  if (shell) shell.style.display = 'block';

  const picker = document.getElementById('factionPicker');
  if (picker) picker.style.display = 'none';
  resizeStage();
  if (!stageResizeBound) {
    window.addEventListener('resize', resizeStage);
    window.addEventListener('online', () => scheduleReconnect('online'));
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING)) {
        scheduleReconnect('visible');
      }
    });
    window.addEventListener('pageshow', () => {
      if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) scheduleReconnect('pageshow');
    });
    stageResizeBound = true;
  }

  initTabs();
}

function sendAction(action, payload = {}) {
  setSocketDebug(`sendAction:${action}:readyState=${ws ? ws.readyState : 'null'}`);
  if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
    pendingOutboundActions.push({action, payload});
    connect({reconnect: true});
    return;
  }
  if (ws.readyState === WebSocket.CONNECTING) {
    pendingOutboundActions.push({action, payload});
    return;
  }
  ws.send(JSON.stringify({action, ...payload}));
}

function purchaseSelectionDetails(state = window.lastGameState || {}) {
  const indices = [...selectedPurchaseIndices]
    .filter(index => Number.isInteger(index) && index >= 0 && index < (state.purchase_area || []).length)
    .sort((a, b) => a - b);
  const cards = indices.map(index => {
    const payment = state.purchase_area_payments?.[index] || state.purchase_area_costs?.[index] || {money: 0, propaganda: 0};
    return {
      index,
      name: state.purchase_area[index],
      zone: index < 6 ? '常設購買區' : '隨機購買區',
      money: Number(payment.money || 0),
      propaganda: Number(payment.propaganda || 0),
    };
  });
  const total = cards.reduce((sum, card) => ({
    money: sum.money + card.money,
    propaganda: sum.propaganda + card.propaganda,
  }), {money: 0, propaganda: 0});
  const me = (state.players || []).find(player => player.id === playerId) || null;
  const affordable = !!me
    && Number(me.resources?.money || 0) >= total.money
    && Number(me.resources?.propaganda || 0) >= total.propaganda;
  return {indices, cards, total, me, affordable};
}

function purchaseCostText(cost) {
  const parts = [];
  if (Number(cost.money || 0) > 0) parts.push(`${cost.money} 資金`);
  if (Number(cost.propaganda || 0) > 0) parts.push(`${cost.propaganda} 宣傳`);
  return parts.length ? parts.join(' ＋ ') : '免費';
}

function updatePurchaseSelectionControls(state = window.lastGameState || {}) {
  const controls = document.getElementById('purchaseSelectionControls');
  const summary = document.getElementById('purchaseSelectionSummary');
  const clearBtn = document.getElementById('clearPurchaseSelectionBtn');
  const buyBtn = document.getElementById('openPurchaseConfirmBtn');
  if (!controls || !summary || !clearBtn || !buyBtn) return;
  // 出牌與購買同屬一個行動階段：整個 action 階段都能勾選購買；end 只是結束行動階段的
  // 內部結算標記（香港根據地遷移等待窗口會停在該狀態），一併保留為可購買。
  const rawPhase = String(state.turn_phase || '').toLowerCase();
  const isPurchaseTurn = (rawPhase === 'action' || rawPhase === 'end') && isMyTurnState(state);
  controls.style.display = isPurchaseTurn ? 'flex' : 'none';
  if (!isPurchaseTurn) {
    selectedPurchaseIndices.clear();
    closePurchaseConfirmModal();
    return;
  }
  const selection = purchaseSelectionDetails(state);
  summary.textContent = selection.cards.length
    ? `已選 ${selection.cards.length} 張｜合計 ${purchaseCostText(selection.total)}`
    : '請勾選要購買的卡牌';
  clearBtn.disabled = selection.cards.length === 0;
  buyBtn.disabled = selection.cards.length === 0 || !selection.affordable;
  buyBtn.textContent = selection.cards.length ? `購買所選 ${selection.cards.length} 張` : '購買所選卡牌';
  buyBtn.title = selection.cards.length > 0 && !selection.affordable ? '所選卡牌的合計費用超過目前資源。' : '';
}

function togglePurchaseSelection(event, index) {
  event.stopPropagation();
  if (event.target.checked) selectedPurchaseIndices.add(index);
  else selectedPurchaseIndices.delete(index);
  const card = event.target.closest('.card');
  if (card) card.classList.toggle('purchase-card-selected', event.target.checked);
  updatePurchaseSelectionControls();
}

function clearPurchaseSelection() {
  selectedPurchaseIndices.clear();
  document.querySelectorAll('.purchase-card-checkbox input').forEach(input => { input.checked = false; });
  document.querySelectorAll('.purchase-card-selected').forEach(card => card.classList.remove('purchase-card-selected'));
  updatePurchaseSelectionControls();
}

function openPurchaseConfirmModal() {
  const overlay = document.getElementById('purchaseConfirmModal');
  const cardsEl = document.getElementById('purchaseConfirmCards');
  const totalEl = document.getElementById('purchaseConfirmTotal');
  const warningEl = document.getElementById('purchaseConfirmWarning');
  const confirmBtn = document.getElementById('confirmPurchaseBtn');
  if (!overlay || !cardsEl || !totalEl || !warningEl || !confirmBtn) return;
  const selection = purchaseSelectionDetails();
  if (!selection.cards.length) return;
  cardsEl.innerHTML = selection.cards.map(card => `
    <div class="purchase-confirm-card-row">
      <div><strong>${escapeHtml(card.name)}</strong><span>${escapeHtml(card.zone)}</span></div>
      <div class="purchase-confirm-card-cost">${escapeHtml(purchaseCostText(card))}</div>
    </div>`).join('');
  totalEl.textContent = `共 ${selection.cards.length} 張｜合計 ${purchaseCostText(selection.total)}`;
  warningEl.style.display = selection.affordable ? 'none' : 'block';
  warningEl.textContent = selection.affordable ? '' : '資源不足，請取消後調整勾選的卡牌。';
  confirmBtn.disabled = !selection.affordable;
  overlay.style.display = 'flex';
}

function closePurchaseConfirmModal() {
  const overlay = document.getElementById('purchaseConfirmModal');
  if (overlay) overlay.style.display = 'none';
}

function confirmSelectedPurchase() {
  const selection = purchaseSelectionDetails();
  if (!selection.cards.length || !selection.affordable) return;
  closePurchaseConfirmModal();
  selectedPurchaseIndices.clear();
  updatePurchaseSelectionControls();
  sendAction('buy_cards', {indices: selection.indices});
}

function openCardTargetModal(index, cardName, targetLabel) {
  const state = window.lastGameState || {};
  const players = (state.players || []).filter(p => p.id !== playerId);
  const overlay = document.getElementById('factionActionModal');
  const title = document.getElementById('factionActionModalTitle');
  const desc = document.getElementById('factionActionModalDesc');
  const choices = document.getElementById('factionActionModalChoices');
  const hint = document.getElementById('factionActionModalRewardHint');
  const closeBtn = document.getElementById('closeFactionActionModal');
  const oddBtn = document.getElementById('guessOddBtn');
  const evenBtn = document.getElementById('guessEvenBtn');
  if (!overlay || !title || !desc || !choices || !hint || !closeBtn) return false;

  const actionPayload = {index, mode: 'action'};
  const requiresRange = new Set(['武裝者', '武裝小隊', '武裝集團', '派遣間諜', '內應間諜']);
  if (players.length === 1) {
    sendAction('play_card', {...actionPayload, target_player_id: players[0].id});
    return true;
  }

  title.textContent = cardName;
  desc.textContent = `${cardName}：請選擇${targetLabel}`;
  if (cardName === '走漏風聲') {
    hint.textContent = '目標玩家會棄掉牌庫頂牌；若該牌購買費用為 1 點以上，從常設購買區移動 1 張內鬥到該玩家棄牌堆。';
  } else if (cardName === '模仿戰術') {
    hint.textContent = '目標玩家會展示牌庫頂牌；本回合你可以使用該牌，使用後會放回該玩家的牌庫頂。';
  } else if (cardName === '合作談判') {
    hint.textContent = '指定的玩家會與你各抽 1 張牌。';
  } else if (requiresRange.has(cardName)) {
    hint.textContent = cardName.startsWith('武裝')
      ? '必須指定有組織位在己方組織 1 格內的其他玩家。'
      : '必須指定有組織位在己方組織 1 格內的其他玩家，並對其組織發動間諜效果。';
  } else {
    hint.textContent = '請選擇目標玩家。';
  }
  choices.innerHTML = '';
  if (oddBtn) oddBtn.style.display = 'none';
  if (evenBtn) evenBtn.style.display = 'none';
  players.forEach((p) => {
    const btn = document.createElement('button');
    btn.className = 'modal-choice-btn';
    btn.type = 'button';
    btn.textContent = p.name;
    btn.onclick = () => {
      sendAction('play_card', {...actionPayload, target_player_id: p.id});
      overlay.style.display = 'none';
    };
    choices.appendChild(btn);
  });
  closeBtn.onclick = () => { overlay.style.display = 'none'; };
  overlay.style.display = 'flex';
  return true;
}

function isMyTurnState(state = window.lastGameState) {
  const players = state?.players || [];
  const me = players.find(p => p.id === playerId);
  return !!(me && state?.current_player === me.name);
}

function isSatisfiedStaleEventBuildChoice(state = window.lastGameState) {
  const choice = state?.pending_choice || null;
  if (!choice || choice.choice_key !== 'event_build_organization') return false;
  const owner = (state.players || []).find(p => p.id === choice.player_id) || null;
  if (!owner) return false;
  return (choice.towns || []).some(entry => {
    const town = entry?.town;
    return !!(town && Number(owner.orgs?.[town] || 0) > 0);
  });
}

function pendingChoiceWaitText(state = window.lastGameState) {
  const me = (state?.players || []).find(p => p.id === playerId) || null;
  if (state?.hk_free_base_relocation) {
    const hongKongPlayer = (state.players || []).find(p => p.faction === 'hong_kong') || null;
    if (me && hongKongPlayer && me.id === hongKongPlayer.id) {
      return '請先決定香港根據地要遷移至何處，或選擇留在目前根據地。';
    }
    return `等待 ${hongKongPlayer?.name || '香港玩家'} 決定是否遷移根據地。`;
  }
  const choice = state?.pending_choice || null;
  if (!choice) return '';
  if (isSatisfiedStaleEventBuildChoice(state)) return '';
  const targetName = choice.player_name || (state.players || []).find(p => p.id === choice.player_id)?.name || '指定玩家';
  const localizedPrompt = playerMessageZhTw(choice.prompt, '');
  if (choice.type === 'reaction_choice') {
    const cardName = choice.played_card_name || '這張牌';
    if (me && choice.player_id === me.id) return `${localizedPrompt || `是否要取消 ${cardName}？`}（請選擇「不取消」或使用取消牌）`;
    return `等待 ${targetName} 回應是否取消 ${cardName}；若 10 秒內未回應，系統會自動視同不取消。`;
  }
  if (me && choice.player_id === me.id) return localizedPrompt || '請先處理目前待選擇效果。';
  return `等待 ${targetName} 處理待選擇效果。`;
}

function bindHandCardActionButtons(container) {
  if (!container) return;
  container.querySelectorAll('.hand-card-action-btn').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      const mode = btn.dataset.cardMode || '';
      const index = Number.parseInt(btn.dataset.cardIndex || '', 10);
      const cardName = btn.dataset.cardName || '';
      if (Number.isNaN(index) || !cardName || !mode) return;
      playHandCard(index, cardName, mode);
    });
  });
}

function playHandCard(index, card, mode) {
  if (!isMyTurnState()) return;
  const state = window.lastGameState || {};
  const phase = String(state.turn_phase || '').toLowerCase();
  const me = (state.players || []).find(p => p.id === playerId) || null;
  const cardName = typeof card === 'string' ? card : (card?.name || card?.title || '');
  const isRedSupportPrepAction = phase === 'event' && mode === 'action' && cardName === '紅軍奧援' && me?.faction === 'red_army';
  if (phase !== 'action' && !isRedSupportPrepAction) {
    const message = phase === 'end'
      ? '行動階段已結束，不能再打出手牌。'
      : cardName === '紅軍奧援' && mode === 'resource'
        ? '事件結算中可先發動紅軍奧援的「行動」，資源需等行動階段。'
        : '目前不能打出一般手牌；請先處理事件結算或等待行動階段。';
    setPhaseActionNotice(message);
    return;
  }
  const canQueueMapCard = !!(
    state.pending_choice
    && me
    && state.pending_choice.player_id === me.id
    && ['build_organization', 'dissolve_organization'].includes(state.pending_choice.interaction_kind)
    && (state.pending_choice.queueable_card_names || []).includes(cardName)
    && mode === 'action'
  );
  if (state.pending_choice && me && state.pending_choice.player_id === me.id && !canQueueMapCard) {
    setPhaseActionNotice('請先處理目前待選擇效果。');
    return;
  }
  const payload = {index, mode};
  // 模仿戰術 selects its target on the server (which filters out players with an empty deck
  // and always opens a choice, even against a single opponent), so it is intentionally not
  // in this frontend auto-target set.
  const playerTargetCards = new Set(['合作談判', '走漏風聲', '武裝者', '武裝小隊', '武裝集團', '派遣間諜', '內應間諜']);
  if (mode === 'action' && playerTargetCards.has(cardName)) {
    const labelMap = {
      '合作談判': '抽牌對象',
      '走漏風聲': '棄牌庫頂牌對象',
      '武裝者': '攻擊對象',
      '武裝小隊': '攻擊對象',
      '武裝集團': '攻擊對象',
      '派遣間諜': '滲透對象',
      '內應間諜': '滲透對象',
    };
    if (openCardTargetModal(index, cardName, labelMap[cardName] || '目標玩家')) return;
  }
  sendAction('play_card', payload);
}

window.addEventListener('DOMContentLoaded', resizeStage);
resizeStage();

function closeFactionActionModal() {
  activeFactionActionModal = null;
  const overlay = document.getElementById('factionActionModal');
  if (overlay) overlay.style.display = 'none';
}

function openRedArmyAbilityModal(state = window.lastGameState || {}) {
  const overlay = document.getElementById('factionActionModal');
  const title = document.getElementById('factionActionModalTitle');
  const desc = document.getElementById('factionActionModalDesc');
  const choices = document.getElementById('factionActionModalChoices');
  const hint = document.getElementById('factionActionModalRewardHint');
  const closeBtn = document.getElementById('closeFactionActionModal');
  const oddBtn = document.getElementById('guessOddBtn');
  const evenBtn = document.getElementById('guessEvenBtn');
  if (!overlay || !title || !desc || !choices || !hint || !closeBtn) return false;

  const usedCount = Number(state.red_army_action_count || 0);
  const limitCount = Number(state.red_army_action_limit || 0);
  const usedUp = limitCount > 0 && usedCount >= limitCount;
  const pendingChoice = state.pending_choice || null;
  const me = (state.players || []).find(p => p.id === playerId) || null;
  const hasMyPendingChoice = !!(pendingChoice && me && pendingChoice.player_id === me.id);
  const phase = String(state.turn_phase || '').toLowerCase();
  const beforeOrDuringPurchase = phase === 'event' || phase === 'action';

  activeFactionActionModal = 'red_army';
  overlay.style.display = 'flex';
  title.textContent = '紅軍能力';
  desc.textContent = usedUp
    ? '本回合紅軍能力已達發動上限。'
    : `紅軍可在開始行動階段之前自行選擇何時發動；本回合已用 ${usedCount}/${limitCount} 次。`;
  choices.innerHTML = '';
  choices.classList.add('red-army-action-choices');
  if (oddBtn) oddBtn.style.display = 'none';
  if (evenBtn) evenBtn.style.display = 'none';
  closeBtn.onclick = closeFactionActionModal;

  const helpHtml = `
    <div>政工部／國安部如需目標，會重用既有選擇彈窗與地圖高亮。</div>
    <ul class="red-army-action-help-list">
      <li><strong>統戰部：</strong>抽 1 張牌。</li>
      <li><strong>政工部：</strong>選擇 1 名非紅軍玩家，將 1 張內鬥放到其牌庫頂；同一目標每回合限 1 次。</li>
      <li><strong>國安部：</strong>選擇其他玩家在紅軍組織 1 格內的 1 個牆內組織瓦解；同一目標每回合限 1 次。</li>
      <li><strong>中紀委：</strong>可棄掉任意張手牌，然後抽等量的牌。</li>
    </ul>`;
  if (hasMyPendingChoice) {
    hint.textContent = '請先處理目前的待選擇效果。';
    return true;
  }
  if (!beforeOrDuringPurchase) {
    hint.textContent = '紅軍能力需在事件／購買前流程中發動。';
    return true;
  }
  hint.innerHTML = helpHtml;
  if (usedUp) return true;

  [
    ['統戰部', '抽 1 張牌。'],
    ['政工部', '選擇 1 名非紅軍玩家，將 1 張內鬥放到其牌庫頂；同一目標每回合限 1 次。'],
    ['國安部', '選擇其他玩家在紅軍組織 1 格內的 1 個牆內組織瓦解；同一目標每回合限 1 次。'],
    ['中紀委', '可棄掉任意張手牌，然後抽等量的牌。'],
  ].forEach(([name, helper]) => {
    const btn = document.createElement('button');
    btn.className = 'modal-choice-btn';
    btn.type = 'button';
    btn.textContent = `發動 ${name}`;
    btn.title = helper;
    btn.onclick = () => {
      sendAction('faction_action', { name });
      closeFactionActionModal();
    };
    choices.appendChild(btn);
  });
  return true;
}

function closeEraAchievementModal() {
  const overlay = document.getElementById('eraAchievementModal');
  if (overlay) overlay.style.display = 'none';
}

function closeChoiceModal(preserveMapHighlight = false) {
  activeChoiceModal = null;
  if (!preserveMapHighlight) {
    syncChoiceModalMapHighlight(null);
  }
  const overlay = document.getElementById('choiceModal');
  if (overlay) {
    overlay.classList.remove('choice-modal-map-context');
    overlay.style.display = 'none';
  }
}

function syncChoiceModalMapHighlight(payload) {
  lastSupportChoiceMapHighlightPayload = payload || null;
  const frame = document.getElementById('strategicMapFrame');
  if (!frame || !frame.contentWindow) return;
  try {
    frame.contentWindow.postMessage({
      type: 'redline-choice-highlight',
      payload: lastSupportChoiceMapHighlightPayload,
    }, window.location.origin);
  } catch (err) {
    console.warn('Failed to sync choice highlight to map', err);
  }
}

function syncPlayerErrorToStrategicMap(message) {
  const frame = document.getElementById('strategicMapFrame');
  if (!frame || !frame.contentWindow || !message) return;
  try {
    frame.contentWindow.postMessage({
      type: 'redline-player-error',
      message: playerMessageZhTw(message),
    }, window.location.origin);
  } catch (err) {
    console.warn('Failed to sync player error to map', err);
  }
}

window.addEventListener('message', (event) => {
  if (event.origin !== window.location.origin) return;
  const data = event.data || {};
  if (data.type !== 'redline-map-state' || !data.state) return;
  window.lastGameState = data.state;
  render(data.state).catch(err => console.warn('Failed to render synced map state', err));
});

function eventBuildChoiceMapPayload(choice, sourceName = '', resolvedTitle = '') {
  const isStandardBuildChoice = choice?.interaction_kind === 'build_organization'
    || ['event_build_organization', 'era_red_build_near_target', 'card_build_organization'].includes(choice?.choice_key);
  const isOrientSupportBuildChoice = choice?.choice_key === 'support_interaction'
    && choice?.step === 'town'
    && (choice?.source_name || sourceName) === '東洋奧援';
  if (!choice || (!isStandardBuildChoice && !isOrientSupportBuildChoice)) return null;
  const towns = (choice.towns || []).filter(entry => entry?.town);
  if (!towns.length) return null;
  return {
    mode: 'support-targets',
    actionKind: 'build',
    remainingBuilds: Math.max(1, Number(choice.remaining_builds || 1)),
    choiceKey: choice.choice_key,
    region: choice.region || '',
    sourceName: sourceName || choice.source_name || resolvedTitle || '建立組織',
    prompt: playerMessageZhTw(choice.prompt, '') || '事件卡效果：請在戰略地圖選擇可建立組織的城鎮。',
    towns: towns.map((entry, index) => ({
      town: entry.town,
      label: entry.label || entry.town,
      index,
    })),
  };
}

function renderBusinessNetworkResult(state) {
  const choice = state?.pending_choice || null;
  const result = state?.last_action_result || null;
  const phaseNoticeMessage = document.getElementById('phaseActionNotice')?.textContent || '';

  if (choice?.choice_key === 'use_purchase_area_card') {
    const sourceName = choice?.source_name || '企業人脈';
    const cards = choice.cards || [];
    const countText = `${cards.length} 張可選`;
    return {
      type: 'pending',
      message: `${sourceName}：請從購買區選 1 張牌借用`,
      html: `
        <div class="business-network-result business-network-result-pending">
          <div class="business-network-result-title">企業人脈待選中</div>
          <div class="business-network-result-body">目前正在選擇購買區牌，${countText}。</div>
        </div>
      `,
    };
  }

  if ((result?.chosen_card && /borrowed/.test(phaseNoticeMessage || '')) || result?.purchase_index != null) {
    const chosenCard = result?.chosen_card || '未知卡牌';
    const purchaseIndex = Number.isFinite(result?.purchase_index) ? result.purchase_index + 1 : null;
    const slotText = purchaseIndex != null ? `購買區槽位 ${purchaseIndex}` : '購買區';
    const resultKey = JSON.stringify({ chosenCard, purchaseIndex, phaseNoticeMessage });
    if (lastBusinessNetworkResultKey !== resultKey) {
      lastBusinessNetworkResultKey = resultKey;
      setPhaseActionNotice(`企業人脈：已借用 ${chosenCard}（${slotText}）`);
    }
    return {
      type: 'resolved',
      message: `企業人脈：已借用 ${chosenCard}（${slotText}）`,
      html: `
        <div class="business-network-result business-network-result-resolved">
          <div class="business-network-result-title">企業人脈已完成</div>
          <div class="business-network-result-body">已從 <strong>${escapeHtml(slotText)}</strong> 借用 <strong>${escapeHtml(chosenCard)}</strong>，並視同打出。</div>
        </div>
      `,
    };
  }

  lastBusinessNetworkResultKey = null;
  return { type: 'idle', message: '', html: '' };
}

function renderBusinessNetworkModalHeader(state) {
  const choice = state?.pending_choice || null;
  if (choice?.choice_key !== 'use_purchase_area_card') return null;
  const cards = choice.cards || [];
  return {
    title: '企業人脈｜借用購買區卡牌',
    desc: `請從購買區正面朝上的牌中選 1 張借用。本次共有 ${cards.length} 張可借用。`,
    helperHtml: `
      <div class="business-network-modal-helper">
        <div class="business-network-modal-helper-title">操作提示</div>
        <div class="business-network-modal-helper-body">你選到的牌會直接視同打出；下方每張候選牌都會標示其購買區槽位與「可借用」。</div>
      </div>
    `,
  };
}

function renderChoiceModal(state) {
  const overlay = document.getElementById('choiceModal');
  const title = document.getElementById('choiceModalTitle');
  const desc = document.getElementById('choiceModalDesc');
  const mapHint = document.getElementById('choiceModalMapHint');
  const cards = document.getElementById('choiceModalCards');
  const closeBtn = document.getElementById('closeChoiceModal');
  if (!overlay || !title || !desc || !mapHint || !cards || !closeBtn) return;

  const choice = state.pending_choice || null;
  const me = (state.players || []).find(p => p.id === playerId) || null;
  const isMine = !!(choice && me && choice.player_id === me.id);
  if (!choice || !isMine) {
    overlay.style.display = 'none';
    overlay.classList.remove('choice-modal-map-context');
    mapHint.style.display = 'none';
    mapHint.textContent = '';
    cards.innerHTML = '';
    activeChoiceModal = null;
    syncChoiceModalMapHighlight(null);
    return;
  }

  const choiceType = choice.type;
  const choiceKey = choice.choice_key || '';
  const rawSourceName = choice.source_name || choiceKey || '';
  const sourceName = playerMessageZhTw(rawSourceName, '卡牌效果');

  const isMapBuildChoice = choice.interaction_kind === 'build_organization'
    || ['event_build_organization', 'era_red_build_near_target', 'card_build_organization'].includes(choiceKey)
    || (choiceKey === 'support_interaction' && choice.step === 'town' && sourceName === '東洋奧援');
  if (isMapBuildChoice && (choiceType === 'town_choice' || choice.step === 'town')) {
    const payload = eventBuildChoiceMapPayload(choice, sourceName, sourceName);
    overlay.style.display = 'none';
    overlay.classList.remove('choice-modal-map-context');
    mapHint.style.display = 'none';
    mapHint.textContent = '';
    cards.innerHTML = '';
    activeChoiceModal = null;
    if (payload) {
      lastSupportChoiceMapHighlightPayload = payload;
      const shouldKeepCollectingBuildCards = (choice.queueable_card_names || []).length > 0;
      if (shouldKeepCollectingBuildCards) {
        syncChoiceModalMapHighlight(payload);
      } else {
        setActiveGameView('map')
          .then(() => syncChoiceModalMapHighlight(payload))
          .catch(err => console.warn('Failed to focus strategic map for event build choice', err));
      }
    } else {
      syncChoiceModalMapHighlight(null);
    }
    return;
  }

  // 瓦解選目標（北國/臺灣奧援、間諜卡瓦解互動、情報網、事件紅軍瓦解、時代加成瓦解、國安部）：
  // 建立 pending choice 後自動切到戰略地圖，只在合法瓦解目標的組織 marker 上以 💀 標示，玩家
  // 可直接點選完成瓦解，不必先在指揮中心或這個通用 choice modal 裡找目標
  // （2026-08-02 playtest 建議）。`interaction_kind` 由後端 state() 統一計算，涵蓋所有瓦解來源，
  // 前端不必為每個 choice_key 各自硬編判斷條件。
  const isMapDissolveChoice = choice.interaction_kind === 'dissolve_organization';
  if (isMapDissolveChoice) {
    const targets = (choice.targets || []).filter(entry => entry?.town);
    overlay.style.display = 'none';
    overlay.classList.remove('choice-modal-map-context');
    mapHint.style.display = 'none';
    mapHint.textContent = '';
    cards.innerHTML = '';
    activeChoiceModal = null;
    if (targets.length) {
      const payload = {
        mode: 'support-targets',
        actionKind: 'dissolve',
        choiceKey,
        sourceName: sourceName || choiceKey || '瓦解組織',
        prompt: playerMessageZhTw(choice.prompt, '請在戰略地圖點選要瓦解的組織。'),
        towns: targets.map((entry, index) => ({
          town: entry.town,
          label: entry.label || entry.town,
          index,
        })),
      };
      lastSupportChoiceMapHighlightPayload = payload;
      if ((choice.queueable_card_names || []).length > 0) {
        syncChoiceModalMapHighlight(payload);
      } else {
        setActiveGameView('map')
          .then(() => syncChoiceModalMapHighlight(payload))
          .catch(err => console.warn('Failed to focus strategic map for dissolve choice', err));
      }
    } else {
      syncChoiceModalMapHighlight(null);
    }
    return;
  }

  // 瓦解類 pending choice 已在上方 isMapDissolveChoice 分支處理完畢，不會落到這裡；
  // 此變數只保留給尚未升級的其它 target choice（如玩家目標選擇）沿用既有無地圖情境的樣式。
  const shouldUseMapContextModal = false;
  overlay.classList.toggle('choice-modal-map-context', shouldUseMapContextModal);
  const maxChoiceCount = Math.max(0, Number(choice.count || 1));
  const minChoiceCount = choice.min_count === 0 ? 0 : Math.max(1, Number(choice.min_count ?? maxChoiceCount));
  const exactChoiceCount = maxChoiceCount;
  const businessNetworkState = renderBusinessNetworkResult(state);
  const businessNetworkModalHeader = renderBusinessNetworkModalHeader(state);
  const mimicLikeTargetChoice = choiceType === 'target_choice';
  const targetChoiceTitleMap = {
    bait_exhaustion_target: '誘導虛耗',
  };
  const resolvedTitle = businessNetworkModalHeader?.title
    || (mimicLikeTargetChoice
      ? (targetChoiceTitleMap[choiceKey] || sourceName || '選擇目標玩家')
      : (choiceType === 'underground_party' ? '地下黨' : (sourceName || '卡牌選擇')));
  activeChoiceModal = choiceType;
  title.textContent = resolvedTitle;
  const localizedChoicePrompt = playerMessageZhTw(choice.prompt, '請進行選擇。');
  desc.innerHTML = `${escapeHtml(businessNetworkModalHeader?.desc || localizedChoicePrompt)}${businessNetworkModalHeader?.helperHtml || ''}`;
  cards.innerHTML = businessNetworkState.html || '';

  mapHint.style.display = 'none';
  mapHint.textContent = '';
  syncChoiceModalMapHighlight(null);

  if (choiceType === 'card_choice' || choiceType === 'underground_party') {
    (choice.cards || []).forEach((cardEntry, index) => {
      const cardName = typeof cardEntry === 'string' ? cardEntry : (cardEntry?.name || '未知卡牌');
      const wrapper = document.createElement('button');
      wrapper.className = 'choice-card-btn';
      wrapper.type = 'button';
      wrapper.onclick = () => {
        sendAction('resolve_choice', { index });
        closeChoiceModal();
      };
      const rawZoneLabel = cardEntry && typeof cardEntry === 'object' ? cardEntry.zone_label : '';
      const zoneLabel = playerMessageZhTw(rawZoneLabel, '卡牌區域');
      const canBorrowLabel = sourceName === '企業人脈' ? '<div class="choice-card-action-tag">可借用</div>' : '';
      if (zoneLabel) {
        const zoneBadge = `<div class="choice-card-zone-label">${escapeHtml(zoneLabel)}</div>`;
        wrapper.innerHTML = `${zoneBadge}${canBorrowLabel}${renderCardFace(cardName, 'choice', false, true)}`;
      } else {
        wrapper.innerHTML = `${canBorrowLabel}${renderCardFace(cardName, 'choice', false, true)}`;
      }
      cards.appendChild(wrapper);
    });
  } else if (choiceType === 'multi_card_choice') {
    const selected = new Set();
    const header = document.createElement('div');
    header.className = 'choice-multi-selection-summary';
    const submit = document.createElement('button');
    submit.className = 'modal-choice-btn';
    submit.type = 'button';
    submit.disabled = true;

    const isVariableCountChoice = choiceKey === 'red_army_ccdi_discard_draw' || choiceKey === 'era_red_discard_to_build_near_target';
    const isEraDeckReorderChoice = choiceKey === 'era_inspect_deck_top_and_reorder';
    const isEraVariableBuildChoice = choiceKey === 'era_red_discard_to_build_near_target';
    const updateSummary = () => {
      header.textContent = isVariableCountChoice
        ? `已選 ${selected.size}/${maxChoiceCount} 張（可選 ${minChoiceCount}～${maxChoiceCount} 張）`
        : isEraDeckReorderChoice
          ? `已選 ${selected.size}/${exactChoiceCount} 張置頂（依點選順序放回牌庫頂）`
          : `已選 ${selected.size}/${exactChoiceCount} 張`;
      submit.textContent = isEraVariableBuildChoice
        ? `確認棄掉 ${selected.size} 張並建立 ${selected.size} 個組織`
        : isVariableCountChoice
          ? `確認棄掉 ${selected.size} 張並抽 ${selected.size} 張`
          : isEraDeckReorderChoice
            ? `確認置頂 ${exactChoiceCount} 張`
            : (exactChoiceCount === 1 ? '確認選擇' : `確認棄掉 ${exactChoiceCount} 張`);
      submit.disabled = isVariableCountChoice
        ? selected.size < minChoiceCount || selected.size > maxChoiceCount
        : selected.size !== exactChoiceCount;
    };

    submit.onclick = () => {
      if (isVariableCountChoice) {
        if (selected.size < minChoiceCount || selected.size > maxChoiceCount) return;
      } else if (selected.size !== exactChoiceCount) return;
      sendAction('resolve_choice', { index: Array.from(selected) });
      closeChoiceModal();
    };

    updateSummary();
    cards.appendChild(header);

    (choice.cards || []).forEach((cardEntry, index) => {
      const cardName = typeof cardEntry === 'string' ? cardEntry : (cardEntry?.name || '未知卡牌');
      const wrapper = document.createElement('button');
      wrapper.className = 'choice-card-btn choice-card-btn-multi';
      wrapper.type = 'button';
      wrapper.setAttribute('aria-pressed', 'false');
      wrapper.onclick = () => {
        if (selected.has(index)) {
          selected.delete(index);
        } else {
          if (selected.size >= maxChoiceCount) return;
          selected.add(index);
        }
        const active = selected.has(index);
        wrapper.classList.toggle('selected', active);
        wrapper.setAttribute('aria-pressed', active ? 'true' : 'false');
        updateSummary();
      };
      if (cardEntry && typeof cardEntry === 'object' && cardEntry.zone_label) {
        const zoneLabel = playerMessageZhTw(cardEntry.zone_label, '卡牌區域');
        const zoneBadge = `<div class="choice-card-zone-label">${escapeHtml(zoneLabel)}</div>`;
        wrapper.innerHTML = `${zoneBadge}${renderCardFace(cardName, 'choice', false, true)}`;
      } else {
        wrapper.innerHTML = renderCardFace(cardName, 'choice', false, true);
      }
      cards.appendChild(wrapper);
    });

    cards.appendChild(submit);
  } else if (choiceType === 'option_choice') {
    (choice.options || []).forEach((option, index) => {
      const btn = document.createElement('button');
      btn.className = 'modal-choice-btn';
      btn.type = 'button';
      const optionLabel = option?.label || '';
      btn.textContent = playerMessageZhTw(optionLabel, `選項 ${index + 1}`) || `選項 ${index + 1}`;
      btn.onclick = () => {
        sendAction('resolve_choice', { index });
      };
      cards.appendChild(btn);
    });
  } else if (choiceType === 'reaction_choice') {
    const row = document.createElement('div');
    row.className = 'modal-choice-row';

    const skipBtn = document.createElement('button');
    skipBtn.className = 'modal-choice-btn';
    skipBtn.type = 'button';
    skipBtn.textContent = '不取消';
    skipBtn.onclick = () => {
      sendAction('resolve_choice', { index: 0 });
    };
    row.appendChild(skipBtn);

    (choice.cards || []).forEach((cardEntry, cardIndex) => {
      const btn = document.createElement('button');
      btn.className = 'modal-choice-btn';
      btn.type = 'button';
      const cardName = typeof cardEntry === 'string' ? cardEntry : (cardEntry?.name || `取消牌 ${cardIndex + 1}`);
      btn.textContent = `使用 ${cardName} 取消`;
      btn.onclick = () => {
        sendAction('resolve_choice', { index: cardIndex + 1 });
      };
      row.appendChild(btn);
    });
    cards.appendChild(row);
    closeBtn.onclick = () => {
      sendAction('resolve_choice', { index: 0 });
    };
  } else if (choiceType === 'town_choice' || (choiceType === 'support_flow_choice' && (choice.step === 'town' || choice.step === 'sacrifice_town'))) {
    (choice.towns || []).forEach((entry, index) => {
      const btn = document.createElement('button');
      btn.className = 'modal-choice-btn';
      btn.type = 'button';
      const town = entry?.town || `城鎮 ${index + 1}`;
      const localizedTownLabel = entry?.label ? playerMessageZhTw(entry.label, '') : '';
      const meta = localizedTownLabel ? `｜${localizedTownLabel}` : '';
      btn.textContent = `${town}${meta}`;
      btn.onclick = () => {
        sendAction('resolve_choice', { index });
      };
      cards.appendChild(btn);
    });
  } else if (choiceType === 'target_choice' || (choiceType === 'support_flow_choice' && choice.step === 'target')) {
    const row = document.createElement('div');
    row.className = 'modal-choice-row';
    (choice.targets || []).forEach((entry, index) => {
      const btn = document.createElement('button');
      btn.className = 'modal-choice-btn';
      btn.type = 'button';
      const rawTargetLabel = entry?.label || entry?.town || '';
      const isPlayerName = (state.players || []).some(player => player.name === rawTargetLabel);
      btn.textContent = isPlayerName
        ? rawTargetLabel
        : (playerMessageZhTw(rawTargetLabel, '') || `目標 ${index + 1}`);
      btn.onclick = () => {
        sendAction('resolve_choice', { index });
      };
      row.appendChild(btn);
    });
    cards.appendChild(row);
  }

  // Close-button policy: a cancellable choice (voluntary Red Army ability, nothing spent yet)
  // can be cancelled; a map-context choice closes to finish via the map; every other blocking
  // choice must be resolved, so it gets no close button (closing used to only hide it
  // client-side and strand the player behind a dangling server-side pending choice).
  if (choiceType === 'reaction_choice') {
    closeBtn.style.display = 'none';
  } else if (choice.cancellable) {
    closeBtn.style.display = '';
    closeBtn.textContent = '取消';
    closeBtn.onclick = () => { sendAction('cancel_choice'); closeChoiceModal(); };
  } else if (shouldUseMapContextModal) {
    closeBtn.style.display = '';
    closeBtn.textContent = '關閉';
    closeBtn.onclick = () => closeChoiceModal(shouldUseMapContextModal);
  } else {
    closeBtn.style.display = 'none';
  }
  overlay.style.display = 'flex';
}

const EVENT_CARD_ART_NAMES = new Set([
  '歲月靜好',
  '全國人大召開',
  '香港抗暴之戰',
  '重大災難',
  '藏印邊境軍事對峙',
  '貿易戰加劇',
  '東突厥集中營',
  '北京政爭',
  '紅軍權貴出逃',
  '烏魯木齊七五事件',
  '上海合作組織',
  '一帶一路 南洋',
  '一帶一路 天方',
]);

function eventCardArtUrl(event) {
  const name = String(event?.name || '').trim();
  return EVENT_CARD_ART_NAMES.has(name)
    ? `/static/card-art/events/${encodeURIComponent(name)}.png`
    : '';
}

const ERA_CARD_ART_NAMES = new Set([
  '[香港]香港人被自殺',
  '[蒙古]莫日根事件爆發',
  '[藏國]藏國騷亂',
  '[哈薩克]伊塔事件',
  '[維吾爾]莎車大屠殺',
  '[滿洲]滿洲地方派系凝聚',
  '[反賊]公知世代的終結',
  '[臺灣]綏靖派反對介入對岸',
]);

function eraCardArtUrl(stage) {
  const name = String(stage?.name || '').trim();
  return ERA_CARD_ART_NAMES.has(name)
    ? `/static/card-art/era/${encodeURIComponent(name)}.png`
    : '';
}

function eraCardArtMarkup(stage, fallbackMarkup = '') {
  const artUrl = eraCardArtUrl(stage);
  if (!artUrl) return fallbackMarkup;
  return `
    <div class="era-card-art-shell">
      <img class="era-card-art-image" src="${artUrl}" alt="${escapeHtml(stage.name || '時代關卡')}完整卡面" decoding="async" onerror="this.parentElement.classList.add('era-card-art-load-failed');this.closest('.era-achievement-glass')?.classList.remove('era-card-art-active');this.closest('.my-era-stage-pane')?.classList.remove('era-card-art-active');this.closest('.my-era-stage-body')?.classList.remove('era-card-art-active')">
      <div class="era-card-art-fallback">${fallbackMarkup}</div>
    </div>`;
}

const EVENT_STATUS_TEXT = {
  active: '進行中',
  success_pending: '條件已達成，等待結算',
  success: '成功已結算',
  failure: '失敗已結算',
  idle: '無效果',
  auto: '自動效果已套用',
  auto_pending: '等待指定玩家回合發動',
};

function eventStatusText(event) {
  return EVENT_STATUS_TEXT[event?.status] || event?.status || '進行中';
}

function eventCardMarkup(event, expanded = false) {
  const progress = event.progress || {};
  const current = Number(progress.count || 0);
  const required = Number(progress.required || event.trigger?.count || 0);
  const typeMap = {idle: '歲月靜好', mission: '任務', auto: '自動'};
  const statusText = eventStatusText(event);
  const progressText = event.type === 'mission' ? `達成次數 ${current} / ${required || 0}` : '';
  const resultText = event.result_text || statusText;
  const artUrl = eventCardArtUrl(event);
  const autoEffectLine = event.type === 'auto'
    ? `<div class="event-card-line event-card-effect-row"><strong>自動效果：</strong><span>${escapeHtml(event.effect_text || '無')}</span></div>`
    : '';
  const missionLines = event.type === 'mission'
    ? `
      <div class="event-card-line event-card-effect-row"><strong>任務條件：</strong><span>${escapeHtml(event.trigger_text || '無')}</span></div>
      <div class="event-card-progress">進度：${current}/${required || 0}</div>
      <div class="event-card-line event-card-effect-row event-card-success"><strong>成功獎勵：</strong><span>${escapeHtml(event.success_text || '無')}</span></div>
      <div class="event-card-line event-card-effect-row event-card-failure"><strong>失敗／紅軍效果：</strong><span>${escapeHtml(event.failure_text || '無')}</span></div>`
    : '';
  const dismissHint = expanded
    ? '<div class="event-reveal-dismiss-hint">點擊任意地方關閉</div>'
    : '';
  const textMarkup = `
    <div class="event-card-inner${expanded ? ' expanded' : ''}">
      ${expanded ? '<div class="event-reveal-kicker">本回合事件</div>' : ''}
      <div class="event-card-name">${escapeHtml(event.name || '未知事件')}</div>
      <div class="event-card-meta">${escapeHtml(typeMap[event.type] || event.type || '未知')}事件｜${escapeHtml(statusText)}</div>
      <div class="event-card-result"><strong>事件結果：</strong><span>${escapeHtml(resultText)}</span></div>
      ${autoEffectLine}
      ${missionLines}
      ${dismissHint}
    </div>`;
  if (!artUrl) return textMarkup;

  const runtimeStatus = `<div class="event-art-runtime-status"><strong>${escapeHtml(statusText)}</strong>${progressText ? `<span>${escapeHtml(progressText)}</span>` : ''}<span>${escapeHtml(resultText)}</span></div>`;
  if (!expanded) {
    const compactPrimary = progressText || statusText;
    return `
      <div class="event-card-compact-layout">
        <div class="event-card-art-shell">
          <img class="event-card-art-image" src="${artUrl}" alt="${escapeHtml(event.name || '事件卡')}完整卡面" loading="lazy" decoding="async" onerror="this.parentElement.classList.add('event-card-art-load-failed')">
          <div class="event-card-art-fallback">${textMarkup}</div>
        </div>
        <div class="event-card-compact-status"><strong>${escapeHtml(compactPrimary)}</strong><span>${escapeHtml(statusText)}</span></div>
      </div>`;
  }
  return `
    <div class="event-card-art-shell expanded">
      <img class="event-card-art-image" src="${artUrl}" alt="${escapeHtml(event.name || '事件卡')}完整卡面" decoding="async" onerror="this.parentElement.classList.add('event-card-art-load-failed')">
      ${runtimeStatus}
      ${dismissHint}
      <div class="event-card-art-fallback">${textMarkup}</div>
    </div>`;
}

function closeEventReveal() {
  const overlay = document.getElementById('eventRevealModal');
  if (overlay) overlay.style.display = 'none';
}

function openCurrentEventReveal() {
  const event = window.lastGameState?.current_event || null;
  const overlay = document.getElementById('eventRevealModal');
  const card = document.getElementById('eventRevealCard');
  if (!event || !overlay || !card) return;
  card.innerHTML = eventCardMarkup(event, true);
  overlay.setAttribute('aria-label', `${event.name || '目前事件'} 放大檢視`);
  overlay.style.display = 'flex';
  // Restart the zoom animation when reopening from the pinned event card.
  card.classList.remove('event-reveal-animate');
  void card.offsetWidth;
  card.classList.add('event-reveal-animate');
}

function renderCurrentEvent(state) {
  const tab = document.getElementById('eventCardTab');
  if (!tab) return;
  const event = state.current_event || null;
  if (!event) {
    tab.style.display = 'none';
    tab.textContent = '事件卡';
    tab.removeAttribute('title');
    closeEventReveal();
    return;
  }
  const statusText = eventStatusText(event);
  tab.style.display = 'inline-flex';
  tab.textContent = `事件卡｜${event.name || '目前事件'}`;
  tab.setAttribute('aria-label', `${event.name || '目前事件'}，${statusText}，點擊查看完整事件卡`);
  tab.setAttribute('title', `${event.name || '目前事件'}｜${statusText}｜點擊查看完整事件卡`);

  const revealCard = document.getElementById('eventRevealCard');
  const revealOverlay = document.getElementById('eventRevealModal');
  if (revealOverlay?.style.display === 'flex' && revealCard) {
    revealCard.innerHTML = eventCardMarkup(event, true);
  }
  const revealKey = `${state.turn ?? 0}:${event.id || event.name || 'event'}`;
  if (lastEventRevealKey !== revealKey) {
    lastEventRevealKey = revealKey;
    openCurrentEventReveal();
  }
}

function minimizeEraAchievement() {
  closeEraAchievementModal();
}

function fillEraAchievementModal(info) {
  const overlay = document.getElementById('eraAchievementModal');
  const glass = overlay?.querySelector('.era-achievement-glass');
  const art = document.getElementById('eraAchievementArt');
  const title = document.getElementById('eraAchievementTitle');
  const cond = document.getElementById('eraAchievementCondition');
  const success = document.getElementById('eraAchievementSuccess');
  const fail = document.getElementById('eraAchievementFail');
  const duration = document.getElementById('eraAchievementDuration');
  if (!overlay || !glass || !art || !title || !cond || !success || !fail || !duration || !info) return false;
  const artUrl = eraCardArtUrl(info);
  glass.classList.toggle('era-card-art-active', Boolean(artUrl));
  art.innerHTML = artUrl ? eraCardArtMarkup(info) : '';
  title.textContent = `${info.name}｜條件已達成`;
  cond.textContent = `達成條件：${info.trigger_text || '（暫缺）'}`;
  success.textContent = info.success_text || '（暫缺）';
  fail.textContent = info.fail_text || '（暫缺）';
  duration.textContent = `效果期限：${info.duration_text || '（暫缺）'}${info.remaining == null ? '' : `｜剩餘 ${info.remaining} 回合`}`;
  eraAchievementViewId = info.id ?? null;
  return true;
}

// 縮小後任何玩家（不只觸發者）都能點分頁列中的時代關卡，重新看到完整說明。
function openEraAchievementById(eraId) {
  const info = eraAchievementDetailsById[eraId];
  if (!info) return false;
  if (!fillEraAchievementModal(info)) return false;
  const overlay = document.getElementById('eraAchievementModal');
  if (overlay) overlay.style.display = 'flex';
  return true;
}

function renderEraAchievement(state) {
  const overlay = document.getElementById('eraAchievementModal');
  const glass = overlay?.querySelector('.era-achievement-glass');
  const art = document.getElementById('eraAchievementArt');
  const tabs = document.getElementById('activeEraTabs');
  const minimizeBtn = document.getElementById('eraAchievementMinimizeBtn');
  if (!overlay || !glass || !art || !tabs || !minimizeBtn) return;

  const info = state.era_notification || null;
  const activeDetails = state.active_era_details || [];

  eraAchievementDetailsById = {};
  activeDetails.forEach(item => {
    if (item && item.id != null) eraAchievementDetailsById[item.id] = item;
  });
  if (info && info.id != null && !eraAchievementDetailsById[info.id]) {
    eraAchievementDetailsById[info.id] = info;
  }

  if (!info && !activeDetails.length) {
    overlay.style.display = 'none';
    glass.classList.remove('era-card-art-active');
    art.innerHTML = '';
    tabs.innerHTML = '';
    lastEraNotificationKey = null;
    eraAchievementViewId = null;
    return;
  }

  minimizeBtn.onclick = minimizeEraAchievement;

  const eraTabsHtml = activeDetails.map(item => {
    const remainText = item.remaining == null ? '持續中' : `剩餘 ${item.remaining} 回合`;
    const notifiedClass = info && item.id === info.id ? ' is-notified' : '';
    const eraId = escapeHtml(String(item.id));
    return `<button type="button" class="game-tab era-stage-tab${notifiedClass}" data-era-id="${eraId}" title="${escapeHtml(item.name)}｜條件已達成｜${escapeHtml(remainText)}" aria-label="查看 ${escapeHtml(item.name)} 完整說明" onclick="openEraAchievementById('${eraId}')"><span class="era-stage-tab-name">${escapeHtml(item.name)}</span><span class="era-stage-tab-remaining">${escapeHtml(remainText)}</span></button>`;
  }).join('');
  tabs.innerHTML = eraTabsHtml;

  if (!info) {
    // 通知已結束（時代到期）但仍有其他生效中的時代：浮窗不自動彈出，分頁仍可點開。
    lastEraNotificationKey = null;
    if (overlay.style.display !== 'flex') eraAchievementViewId = null;
    return;
  }

  const key = `${info.id}:${info.remaining ?? 'perm'}`;
  const isOpen = overlay.style.display === 'flex';
  // 浮窗開著，而且玩家正透過分頁查看其他時代時，不要被最新通知蓋掉內容。
  const viewing = isOpen && eraAchievementViewId && eraAchievementViewId !== info.id
    ? eraAchievementDetailsById[eraAchievementViewId]
    : info;
  fillEraAchievementModal(viewing || info);

  if (lastEraNotificationKey !== key) {
    overlay.style.display = 'flex';
    fillEraAchievementModal(info);
    lastEraNotificationKey = key;
  }
}

function openFactionGuessModal(actionName, hintText) {
  activeFactionActionModal = actionName;
  const overlay = document.getElementById('factionActionModal');
  const title = document.getElementById('factionActionModalTitle');
  const desc = document.getElementById('factionActionModalDesc');
  const choices = document.getElementById('factionActionModalChoices');
  const hint = document.getElementById('factionActionModalRewardHint');
  const closeBtn = document.getElementById('closeFactionActionModal');
  if (!overlay || !title || !desc || !choices || !hint || !closeBtn) return;

  overlay.style.display = 'flex';
  title.textContent = actionName;
  desc.textContent = '請猜牌庫頂牌購買費用的奇偶。';
  hint.textContent = hintText;
  choices.innerHTML = '';
  ['odd', 'even'].forEach((guess) => {
    const btn = document.createElement('button');
    btn.className = 'modal-choice-btn';
    btn.type = 'button';
    btn.textContent = guess === 'odd' ? '猜奇數' : '猜偶數';
    btn.onclick = () => {
      sendAction('faction_action', { name: actionName, guess });
      closeFactionActionModal();
    };
    choices.appendChild(btn);
  });
  closeBtn.onclick = closeFactionActionModal;
}

function openGamblerGuessModal() {
  openFactionGuessModal('賭徒耳語', '猜中可獲得 3 點資金與 3 點宣傳。');
}

function openEthnicRitualGuessModal() {
  openFactionGuessModal('民族祭儀', '猜中可獲得 2 點宣傳與 2 點資金；沒猜中則獲得 2 點宣傳或 2 點資金（二選一）。');
}

function strategicMapUrl() {
  const url = new URL('/static/leaflet_game_map.html', window.location.origin);
  url.searchParams.set('v', 'nanyang-legal-build-bounds-20260822');
  if (gameId) url.searchParams.set('gameId', gameId);
  if (playerId) url.searchParams.set('playerId', playerId);
  return url.toString();
}

function connectStrategicMapFrame() {
  const frame = document.getElementById('strategicMapFrame');
  if (!frame || !frame.contentWindow || !gameId || !playerId) return;
  try {
    if (typeof frame.contentWindow.connectGameMap === 'function') {
      frame.contentWindow.connectGameMap({ gameId, playerId, resumeToken });
    }
  } catch (err) {
    console.error('Failed to connect strategic map frame', err);
  }
}

function strategicMapConnected() {
  const frame = document.getElementById('strategicMapFrame');
  if (!frame || !frame.contentWindow) return false;
  try {
    return !!frame.contentWindow.lastGameState;
  } catch {
    return false;
  }
}

async function ensureStrategicMapMounted() {
  const frame = document.getElementById('strategicMapFrame');
  if (!frame) return;
  const url = strategicMapUrl();
  if (frame.dataset.loadedUrl === url) {
    if (!strategicMapConnected()) {
      connectStrategicMapFrame();
    }
    if (lastSupportChoiceMapHighlightPayload) {
      setTimeout(() => syncChoiceModalMapHighlight(lastSupportChoiceMapHighlightPayload), 0);
    }
    return;
  }

  frame.onload = () => {
    setTimeout(() => {
      connectStrategicMapFrame();
      if (lastSupportChoiceMapHighlightPayload) {
        syncChoiceModalMapHighlight(lastSupportChoiceMapHighlightPayload);
      }
      setTimeout(() => {
        if (!strategicMapConnected()) {
          connectStrategicMapFrame();
        }
        if (lastSupportChoiceMapHighlightPayload) {
          syncChoiceModalMapHighlight(lastSupportChoiceMapHighlightPayload);
        }
      }, 250);
    }, 120);
  };

  frame.src = url;
  frame.dataset.loadedUrl = url;
}

function syncStrategicMap(_state) {
  // iframe version uses its own websocket connection via query params.
}

async function getFullMapData() {
  if (cachedFullMapData) return cachedFullMapData;
  const res = await fetch('/map-data');
  cachedFullMapData = await res.json();
  return cachedFullMapData;
}

let pendingBaseSelectionLabel = null;
let lastBusinessNetworkResultKey = null;

function renderFactionActionPanel(state) {
  const panel = document.getElementById('factionActionPanel');
  const info = document.getElementById('factionActionInfo');
  const buttons = document.getElementById('factionActionButtons');
  const modalOverlay = document.getElementById('factionActionModal');
  const modalTitle = document.getElementById('factionActionModalTitle');
  const modalDesc = document.getElementById('factionActionModalDesc');
  const modalChoices = document.getElementById('factionActionModalChoices');
  const modalHint = document.getElementById('factionActionModalRewardHint');
  const closeBtn = document.getElementById('closeFactionActionModal');
  const oddBtn = document.getElementById('guessOddBtn');
  const evenBtn = document.getElementById('guessEvenBtn');
  if (!panel || !info || !buttons || !modalOverlay || !modalTitle || !modalDesc || !modalChoices || !modalHint || !closeBtn) return;

  const me = state.players?.find(p => p.id === playerId) || null;
  const phase = String(state.turn_phase || '').toLowerCase();
  const inAction = phase === 'action';
  const isMine = state.current_player && me && state.current_player === me.name;
  const faction = me?.faction || '';
  const factionActionUsed = !!state.faction_action_used;
  const hasActivePendingChoice = !!(state.pending_choice && me && state.pending_choice.player_id === me.id);

  buttons.innerHTML = '';
  panel.style.display = 'none';
  panel.classList.remove('overlay-active');
  info.textContent = '';
  modalOverlay.style.display = 'none';
  modalChoices.innerHTML = '';
  modalChoices.classList.remove('red-army-action-choices');
  modalHint.textContent = '';
  modalDesc.textContent = '';
  modalTitle.textContent = '';
  if (oddBtn) oddBtn.style.display = 'none';
  if (evenBtn) evenBtn.style.display = 'none';

  const factionResult = renderFactionActionResult(state, faction);
  const hasResult = factionResult.hasResult;

  if (faction === 'red_army' && isMine && (phase === 'event' || phase === 'action')) {
    // 紅軍能力只使用分頁列「結束行動」左側的入口。共用 factionActionPanel
    // 仍保留給其他陣營能力，但不再為紅軍渲染重複的說明、次數與按鈕。
    return;
  }

  if (!inAction || !isMine || hasActivePendingChoice) return;

  // 2026-08-09 使用者 playtest 回報：這幾個陣營（澳門／改革開放派／自由派／民族祭儀
  // 各族）先前用「置中彈窗」呈現能力狀態，但彈窗是在*每一次* render 都被無條件強制
  // 打開（`modalOverlay.style.display = 'flex'` 不看任何前置條件），只要本回合已發動
  // 過能力，之後不管做什麼不相關操作（例如打出手牌拿資源）觸發任何一次 render，都會
  // 把「本回合已發動陣營能力」的彈窗重新蓋回畫面上。改比照紅軍既有的作法（下方
  // `red_army` 分支）：平常用不會擋畫面的小面板顯示「可發動」，本回合已用掉後面板
  // 直接收起，不再強制彈窗；彈窗（`factionActionModal`）只保留給真正需要玩家輸入的
  // 猜奇偶子流程（`openGamblerGuessModal`／`openEthnicRitualGuessModal`），由玩家主動
  // 點擊「發動」才打開，不會被其他操作意外重新叫出來。
  const showActionPanel = (message, buttonLabel, onActivate) => {
    if (factionActionUsed || hasResult) {
      panel.style.display = 'none';
      panel.classList.remove('overlay-active');
      info.textContent = '';
      buttons.innerHTML = '';
      return;
    }
    panel.style.display = 'block';
    info.innerHTML = `<div class="faction-action-placeholder">${escapeHtml(message)}</div>`;
    const btn = document.createElement('button');
    btn.className = 'base-choice-btn';
    btn.type = 'button';
    btn.textContent = buttonLabel;
    btn.onclick = onActivate;
    buttons.appendChild(btn);
  };

  if (faction === 'aomen') {
    showActionPanel(
      '澳門可在行動階段發動一次賭徒耳語：將 1 張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶；若猜中獲得 3 點宣傳與 3 點資金。',
      '發動 賭徒耳語',
      openGamblerGuessModal
    );
    return;
  }

  if (faction === 'reform_opening') {
    showActionPanel(
      '改革開放派可在行動階段發動一次紅軍派系：檢視牌庫頂 3 張牌，以任意順序放回牌庫頂，然後抽 1 張牌。',
      '發動 紅軍派系',
      () => sendAction('faction_action', { name: '紅軍派系' })
    );
    return;
  }

  if (faction === 'liberals') {
    showActionPanel(
      '自由派可在行動階段發動一次立場試探：展示牌庫頂牌；若購買費用為奇數則加入手牌，若為偶數則放入棄牌堆。',
      '發動 立場試探',
      () => sendAction('faction_action', { name: '立場試探' })
    );
    return;
  }

  const ethnicRitualFactions = new Set(['zhuang','yi','bai','hani','dai','miao','tujia','dong','buyei','yao','li']);
  if (ethnicRitualFactions.has(faction)) {
    showActionPanel(
      '可在行動階段發動一次民族祭儀：猜中可獲得 2 點宣傳與 2 點資金；沒猜中則獲得 2 點宣傳或 2 點資金（二選一）。',
      '發動 民族祭儀',
      openEthnicRitualGuessModal
    );
  }
}

function syncPhaseActionMetaOverflow() {
  const meta = document.getElementById('phaseActionMeta');
  const wrap = document.getElementById('phaseActionMetaWrap');
  const tooltip = document.getElementById('phaseActionMetaTooltip');
  if (!meta || !wrap || !tooltip) return;
  const fullText = meta.textContent || '';
  const isOverflowing = Boolean(fullText) && meta.scrollWidth > meta.clientWidth + 1;
  wrap.classList.toggle('is-overflowing', isOverflowing);
  meta.tabIndex = isOverflowing ? 0 : -1;
  if (isOverflowing) {
    meta.setAttribute('aria-describedby', 'phaseActionMetaTooltip');
  } else {
    meta.removeAttribute('aria-describedby');
  }
  tooltip.setAttribute('aria-hidden', isOverflowing ? 'false' : 'true');
}

function setPhaseActionMeta(message = '') {
  const meta = document.getElementById('phaseActionMeta');
  const tooltip = document.getElementById('phaseActionMetaTooltip');
  if (!meta) return;
  const fullText = message || '';
  meta.textContent = fullText;
  meta.title = tooltip ? '' : fullText;
  if (tooltip) tooltip.textContent = fullText;
  requestAnimationFrame(syncPhaseActionMetaOverflow);
}

window.addEventListener('resize', () => requestAnimationFrame(syncPhaseActionMetaOverflow));

function setPhaseActionNotice(message = '') {
  const notice = document.getElementById('phaseActionNotice');
  if (!notice) return;
  notice.textContent = message || '';
  notice.title = message || '';
  notice.classList.toggle('visible', !!message);
}

function clearStickyPlayerErrorNotice() {
  if (stickyPlayerErrorTimer) clearTimeout(stickyPlayerErrorTimer);
  stickyPlayerErrorNotice = '';
  stickyPlayerErrorTimer = null;
  setPhaseActionNotice('');
}

function showUnavailableActionModal(actionName, message) {
  const modal = document.getElementById('unavailableActionModal');
  const title = document.getElementById('unavailableActionTitle');
  const body = document.getElementById('unavailableActionMessage');
  if (!modal || !title || !body) return;
  clearStickyPlayerErrorNotice();
  unavailableActionModalReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  title.textContent = actionName ? `${actionName}無法發動` : '無法發動能力';
  body.textContent = message || '目前沒有合法目標，未發動能力。';
  modal.style.display = 'flex';
  modal.setAttribute('aria-hidden', 'false');
  requestAnimationFrame(() => document.getElementById('closeUnavailableActionModalBtn')?.focus());
}

function closeUnavailableActionModal() {
  const modal = document.getElementById('unavailableActionModal');
  if (!modal || modal.style.display === 'none') return;
  modal.style.display = 'none';
  modal.setAttribute('aria-hidden', 'true');
  if (unavailableActionModalReturnFocus?.isConnected) unavailableActionModalReturnFocus.focus();
  unavailableActionModalReturnFocus = null;
}

document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  const modal = document.getElementById('unavailableActionModal');
  if (modal?.style.display !== 'flex') return;
  event.preventDefault();
  closeUnavailableActionModal();
});

function showStickyPlayerErrorNotice(message, durationMs = 5000) {
  stickyPlayerErrorNotice = message || '';
  if (stickyPlayerErrorTimer) clearTimeout(stickyPlayerErrorTimer);
  setPhaseActionNotice(stickyPlayerErrorNotice);
  stickyPlayerErrorTimer = setTimeout(() => {
    if (stickyPlayerErrorNotice !== message) return;
    stickyPlayerErrorNotice = '';
    stickyPlayerErrorTimer = null;
    setPhaseActionNotice('');
  }, durationMs);
}

function formatFactionActionResult(result) {
  if (!result || !result.name) return '';
  if (result.unavailable) {
    return result.message || `${result.name}：目前沒有可執行的目標或卡牌，未發動能力。`;
  }
  const cardName = result.revealed_card || '未知卡牌';
  const costText = Number.isFinite(result.cost_total) ? `（費用 ${result.cost_total}）` : '';
  if (result.name === '立場試探') {
    const destinationText = result.destination === 'hand' ? '加入手牌' : result.destination === 'discard' ? '放入棄牌堆' : '已處理';
    return `立場試探結果：翻到 ${cardName}${costText}，${destinationText}`;
  }
  if (result.name === '統戰部') {
    return `統戰部結果：抽 ${Number(result.drawn || 0)} 張牌`;
  }
  if (result.name === '政工部') {
    if (result.static_supply_empty) {
      return `政工部結果：內鬥供應已空，未放入 ${result.target_player_name || '目標玩家'} 的牌庫頂`;
    }
    return `政工部結果：已將 ${result.topdecked_card || '內鬥'} 放到 ${result.target_player_name || '目標玩家'} 的牌庫頂`;
  }
  if (result.name === '國安部') {
    return `國安部結果：已瓦解 ${result.target_player_name || '目標玩家'} 在 ${result.town || '目標城鎮'} 的組織`;
  }
  if (result.name === '中紀委') {
    return `中紀委結果：棄 ${Number(result.discarded ?? result.chosen_cards?.length ?? 0)} 張，抽 ${Number(result.drawn || 0)} 張`;
  }
  if (result.name === '賭徒耳語' || result.name === '民族祭儀') {
    const guessText = result.guess === 'odd' ? '奇數' : result.guess === 'even' ? '偶數' : '未知';
    const parityText = Number.isFinite(result.cost_total) ? (result.cost_total % 2 === 1 ? '奇數' : '偶數') : '未知';
    const outcomeText = result.hit ? '猜中' : '沒猜中';
    const reward = result.reward || {};
    const rewardParts = [];
    if (Number(reward.money || 0) > 0) rewardParts.push(`資金 +${Number(reward.money || 0)}`);
    if (Number(reward.propaganda || 0) > 0) rewardParts.push(`宣傳 +${Number(reward.propaganda || 0)}`);
    const rewardText = rewardParts.length ? `，獲得 ${rewardParts.join('、')}` : '，未獲得額外資源';
    return `${result.name}結果：猜${guessText}，翻到 ${cardName}${costText} 是${parityText}，${outcomeText}${rewardText}`;
  }
  return '';
}

function renderFactionActionResult(state, faction) {
  const info = document.getElementById('factionActionInfo');
  if (!info) return {hasResult: false, message: '', html: ''};

  const result = state.last_action_result || null;
  const message = formatFactionActionResult(result);
  const resultActionNames = new Set(['立場試探', '賭徒耳語', '民族祭儀', '統戰部', '政工部', '國安部', '中紀委']);
  if (resultActionNames.has(result?.name) && message) {
    const resultKey = JSON.stringify(result);
    if (lastFactionActionResultKey !== resultKey) {
      lastFactionActionResultKey = resultKey;
      if (result.unavailable) {
        showUnavailableActionModal(result.name, message);
      } else {
        showStickyPlayerErrorNotice(message);
      }
    }
    const html = result.unavailable ? '' : `<div class="faction-action-result">${escapeHtml(message)}</div>`;
    info.innerHTML = html;
    return {hasResult: true, message, html};
  }

  lastFactionActionResultKey = null;
  if (!stickyPlayerErrorNotice) setPhaseActionNotice('');

  if (faction === 'liberals') {
    const html = '<div class="faction-action-placeholder">發動後會在此直接顯示翻到的卡牌與去向。</div>';
    info.innerHTML = html;
    return {hasResult: false, message: '', html};
  }

  if (faction === 'aomen') {
    const html = '<div class="faction-action-placeholder">發動後會在此直接顯示猜測、翻牌與資源結果。</div>';
    info.innerHTML = html;
    return {hasResult: false, message: '', html};
  }

  if (faction === 'red_army') {
    info.textContent = '';
    return {hasResult: false, message: '', html: ''};
  }

  const ethnicRitualFactions = new Set(['zhuang','yi','bai','hani','dai','miao','tujia','dong','buyei','yao','li']);
  if (ethnicRitualFactions.has(faction)) {
    const html = '<div class="faction-action-placeholder">發動後會在此直接顯示猜測、翻牌與資源結果。</div>';
    info.innerHTML = html;
    return {hasResult: false, message: '', html};
  }

  info.textContent = '';
  return {hasResult: false, message: '', html: ''};
}

function renderBaseSelection(state) {
  const panel = document.getElementById('baseSelectionPanel');
  const info = document.getElementById('baseSelectionInfo');
  const choicesEl = document.getElementById('baseSelectionChoices');
  if (!panel || !info || !choicesEl) return;

  const choiceData = state.pending_base_choices?.[playerId] || null;
  const labels = choiceData?.labels || [];
  const resolved = choiceData?.resolved || {};
  const inBaseSelection = state.game_phase === 'base_selection';

  if (!inBaseSelection) {
    panel.style.display = 'none';
    pendingBaseSelectionLabel = null;
    choicesEl.innerHTML = '';
    info.textContent = '';
    return;
  }

  if (!choiceData) {
    panel.style.display = 'none';
    pendingBaseSelectionLabel = null;
    choicesEl.innerHTML = '';
    info.textContent = '';
    setPhaseActionNotice('等待其他玩家選擇根據地');
    return;
  }

  panel.style.display = 'block';
  setPhaseActionNotice('');

  const hasGeneric = labels.some(label => label.startsWith('任意'));
  choicesEl.innerHTML = '';

  if (!hasGeneric) {
    info.textContent = '請選擇你的根據地';
    labels.forEach(label => {
      const btn = document.createElement('button');
      btn.className = 'base-choice-btn';
      btn.textContent = label;
      btn.onclick = () => sendAction('set_base', { label, town: label });
      choicesEl.appendChild(btn);
    });
    return;
  }

  if (!pendingBaseSelectionLabel) {
    info.textContent = '請先選擇你的根據地類別';
    labels.forEach(label => {
      const btn = document.createElement('button');
      btn.className = 'base-choice-btn';
      btn.textContent = label;
      btn.onclick = () => {
        const resolvedTowns = resolved[label] || [];
        if (!label.startsWith('任意') || resolvedTowns.length <= 1) {
          const town = resolvedTowns[0] || label;
          sendAction('set_base', { label, town });
          return;
        }
        pendingBaseSelectionLabel = label;
        renderBaseSelection(state);
      };
      choicesEl.appendChild(btn);
    });
    return;
  }

  const towns = resolved[pendingBaseSelectionLabel] || [];
  info.textContent = `根據地類別：${pendingBaseSelectionLabel}，請選擇具體城鎮`;

  const back = document.createElement('button');
  back.className = 'base-choice-btn';
  back.textContent = '← 返回類別';
  back.onclick = () => {
    pendingBaseSelectionLabel = null;
    renderBaseSelection(state);
  };
  choicesEl.appendChild(back);

  towns.forEach(choice => {
    const btn = document.createElement('button');
    btn.className = 'base-choice-btn';
    btn.textContent = choice;
    btn.onclick = () => sendAction('set_base', { label: pendingBaseSelectionLabel, town: choice });
    choicesEl.appendChild(btn);
  });
}

function factionToneClass(factionId) {
  if (factionId === 'red_army') return ' tone-red';
  if (String(factionId || '').startsWith('taiwan')) return ' tone-taiwan';
  if (String(factionId || '').startsWith('tibet')) return ' tone-tibet';
  if (String(factionId || '').startsWith('uyghur') || factionId === 'kazakh') return ' tone-gold';
  if (factionId === 'hong_kong') return ' tone-hongkong';
  return '';
}

function playerBaseName(player) {
  const orgTowns = Object.keys(player?.orgs || {});
  if (player?.base) return player.base;
  if (player?.base_name) return player.base_name;
  if (orgTowns.length === 1) return orgTowns[0];
  if (orgTowns.length > 1) return orgTowns.join('、');
  return '未部署';
}

function renderPlayerStatusCards(state) {
  const target = document.getElementById('playerStatusOverview');
  if (!target) return;

  const players = state.players || [];
  if (!players.length) {
    target.innerHTML = '<div class="player-status-empty">尚未取得玩家戰況。</div>';
    return;
  }

  target.innerHTML = players.map(player => {
    const derivedTotalOrgs = Object.values(player.orgs || {}).reduce((a, b) => a + b, 0);
    const organizationCounts = player.organization_counts || {};
    const totalOrgs = organizationCounts.total ?? derivedTotalOrgs;
    const insideWallOrgs = organizationCounts.inside_wall ?? 0;
    const outsideWallOrgs = organizationCounts.outside_wall ?? (totalOrgs - insideWallOrgs);
    const money = player.resources?.money ?? 0;
    const propaganda = player.resources?.propaganda ?? 0;
    const handCount = player.hand?.length ?? 0;
    const deckCount = player.deck_count ?? 0;
    const discardPile = player.discard_pile || [];
    const discardVariants = player.discard_variants || [];
    const discardCount = player.discard_count ?? discardPile.length;
    const discardPreview = discardPile.length
      ? discardPile.map((card, index) => {
          const variantIndex = Number.parseInt(discardVariants[index]?.variant_index, 10);
          const variantAttr = Number.isInteger(variantIndex) ? ` data-card-variant-index="${variantIndex}"` : '';
          return `<button type="button" class="player-status-discard-card" data-card-name="${escapeHtml(card)}" data-card-zone="discard"${variantAttr} aria-label="查看 ${escapeHtml(card)} 完整卡面">${escapeHtml(card)}</button>`;
        }).join('')
      : '<span class="player-status-discard-empty">無</span>';
    const moves = player.moves_left ?? 0;
    const isCurrent = state.current_player === player.name;
    const factionName = factionDisplayName(player.faction);
    const baseName = playerBaseName(player);
    const initial = escapeHtml(String(player.name || '?').slice(0, 1).toUpperCase());
    return `
      <article class="player-status-card${isCurrent ? ' current' : ''}${factionToneClass(player.faction)}">
        <div class="player-status-top">
          <div class="player-status-avatar">${initial}</div>
          <div class="player-status-id">
            <div class="player-status-name"${factionNameColor(player.faction) ? ` style="color:${factionNameColor(player.faction)}"` : ''}>${escapeHtml(player.name || '未命名玩家')}</div>
            <div class="player-status-subtitle">${isCurrent ? '當前行動玩家' : '玩家戰況'}</div>
          </div>
          ${isCurrent ? '<span class="player-status-current">當前玩家</span>' : ''}
        </div>
        <div class="player-status-badges">
          <span class="player-status-badge faction">陣營：${escapeHtml(factionName)}</span>
          <span class="player-status-badge">根據地：${escapeHtml(baseName)}</span>
        </div>
        <div class="player-status-stats">
          <div class="player-status-stat player-status-stat-organizations">
            <span>組織</span>
            <strong>${totalOrgs}</strong>
            <small>牆內 ${insideWallOrgs}／牆外 ${outsideWallOrgs}</small>
          </div>
          <div class="player-status-stat"><span>資金</span><strong>${money}</strong></div>
          <div class="player-status-stat"><span>宣傳</span><strong>${propaganda}</strong></div>
          <div class="player-status-stat"><span>手牌</span><strong>${handCount}</strong></div>
          <div class="player-status-stat"><span>牌庫</span><strong>${deckCount}</strong></div>
          <div class="player-status-stat"><span>棄牌</span><strong>${discardCount}</strong></div>
          <div class="player-status-stat"><span>移動</span><strong>${moves}</strong></div>
        </div>
        <div class="player-status-discard-preview">
          <span class="player-status-discard-label">棄牌堆</span>
          <div class="player-status-discard-list">${discardPreview}</div>
        </div>
      </article>`;
  }).join('');

  target.querySelectorAll('.player-status-discard-card[data-card-name]').forEach(cardButton => {
    cardButton.addEventListener('click', () => selectCardDetail(cardButton));
  });
}

// 個人資訊頁內 Tab：遊戲中隨時查看自己陣營的能力/規則限制/獲勝條件。
// 資料萃取邏輯與 lobby 的 renderFactionDetails 相同（能力=abilities 排除 setup/restriction 型；
// 規則與限制=setup_effects+special_rules+restrictions+setup/restriction 型能力；根據地能力併入能力）。
function renderMyFactionView(state = window.lastGameState || {}) {
  const titleEl = document.getElementById('myFactionTitle');
  const bodyEl = document.getElementById('myFactionBody');
  if (!titleEl || !bodyEl) return;
  const me = (state.players || []).find(p => p.id === playerId);
  const myFactionTab = document.getElementById('myFactionBtn');
  if (myFactionTab) {
    const canRelocate = me?.faction === 'hong_kong' && !!state.hk_free_base_relocation;
    myFactionTab.textContent = canRelocate ? '我的陣營（可遷移）' : '我的陣營';
    myFactionTab.classList.toggle('attention', canRelocate);
  }
  if (!me || !me.faction) {
    titleEl.textContent = '尚未選擇陣營';
    bodyEl.innerHTML = '<div class="personal-info-empty">進入遊戲並選定陣營後，即可在這裡查看完整陣營資訊。</div>';
    return;
  }
  const factionId = me.faction;
  let opt = factionOptionById(factionId);
  if (!opt) {
    // family variant 只存在 variant_details 內的情況
    for (const category of availableFactionCategories) {
      for (const parent of (category.options || [])) {
        for (const v of Object.values(parent.variant_details || {})) {
          if (v && v.id === factionId) { opt = v; break; }
        }
      }
    }
  }
  if (!opt) {
    titleEl.textContent = factionDisplayName(factionId);
    bodyEl.innerHTML = '<div class="personal-info-empty">目前找不到這個陣營的詳細資料。</div>';
    return;
  }

  const baseName = me.base || null;
  const detailSource = (baseName && opt.variant_details) ? (opt.variant_details[baseName] || null) : null;
  const detail = detailSource || opt;
  const selectedBaseData = (detail.bases || []).find(base => base?.name === baseName) || null;
  const rawAbilities = [
    ...((detail.abilities_text || detail.abilities || [])),
    ...((selectedBaseData?.abilities) || []),
  ];
  const renderItem = item => typeof item === 'string'
    ? item
    : [item.name_override || item.name, item.trigger, item.effect].filter(Boolean).join('：');
  const abilities = rawAbilities.filter(item => !(typeof item === 'object' && item && ['setup', 'restriction'].includes(item.type)));
  const rules = [
    ...(detail.setup_effects || []),
    ...(detail.special_rules || []),
    ...(detail.restrictions || []),
    ...rawAbilities
      .filter(item => typeof item === 'object' && item && ['setup', 'restriction'].includes(item.type))
      .map(renderItem),
  ];
  const wins = detail.win_condition_text
    ? [detail.win_condition_text]
    : (detail.win_conditions || []).map(humanizeWinCondition);

  const color = factionNameColor(factionId) || '#e5ecf5';
  titleEl.innerHTML = `<span style="color:${color};font-weight:800">${escapeHtml(factionDisplayName(factionId))}</span>`;
  const section = (label, items) => `
    <div class="faction-detail-section-title">${label}</div>
    <ul>${(items.length ? items : ['（暫無資料）']).map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`;
  const hkBaseOverview = hongKongBaseOverviewItems(detail, baseName);
  const occupiedTowns = new Set((state.players || []).flatMap(player =>
    Object.entries(player.orgs || {}).filter(([, count]) => Number(count) > 0).map(([town]) => town)
  ));
  const ownOrganizationTowns = new Set(
    Object.entries(me.orgs || {}).filter(([, count]) => Number(count) > 0).map(([town]) => town)
  );
  const hkRelocationTargets = factionId === 'hong_kong'
    ? (detail.bases || []).filter(base => base?.type === 'relocatable')
    : [];
  const hkRelocationPanel = factionId === 'hong_kong' && state.hk_free_base_relocation
    ? `<section class="hk-base-relocation-panel">
        <div class="faction-detail-section-title">香港抗暴之戰：免費遷移根據地</div>
        <p>請選擇一個新根據地；亦可留在目前的 ${escapeHtml(baseDisplayName(baseName))}。</p>
        <div class="hk-base-relocation-actions">
          ${hkRelocationTargets.map(base => {
            const occupied = occupiedTowns.has(base.name);
            const occupiedByOwnOrganization = ownOrganizationTowns.has(base.name);
            const blockedByOtherOrganization = occupied && !occupiedByOwnOrganization;
            const occupancyLabel = blockedByOtherOrganization ? '（已有其他陣營組織）' : '';
            return `<button type="button" class="base-choice-btn" data-hk-relocate-town="${escapeHtml(base.name)}" ${blockedByOtherOrganization ? 'disabled' : ''}>遷移至${escapeHtml(baseDisplayName(base.name))}${occupancyLabel}</button>`;
          }).join('')}
          <button type="button" class="base-choice-btn" data-hk-keep-base="1">留在${escapeHtml(baseDisplayName(baseName))}</button>
        </div>
      </section>`
    : '';
  bodyEl.innerHTML = [
    hkRelocationPanel,
    hkBaseOverview.length ? section('根據地遷移與能力', hkBaseOverview) : section('根據地', baseName ? [baseDisplayName(baseName)] : []),
    section('目前生效能力', abilities.map(renderItem)),
    section('規則與限制', rules),
    section('獲勝條件', wins),
  ].join('');
  bodyEl.querySelectorAll('[data-hk-relocate-town]').forEach(button => {
    button.addEventListener('click', () => {
      button.disabled = true;
      sendAction('relocate_base', {town: button.dataset.hkRelocateTown});
    });
  });
  bodyEl.querySelector('[data-hk-keep-base]')?.addEventListener('click', event => {
    event.currentTarget.disabled = true;
    sendAction('keep_hong_kong_base');
  });
}

// 「我的陣營」右欄時代關卡：未達成前也可隨時查看自己的完整卡面與雙方效果。
// 後端只投影觀看者所屬陣營大類的關卡，避免把其他玩家的個人資訊混進來。
function renderMyEraStageView(state = window.lastGameState || {}) {
  const paneEl = document.getElementById('myEraStagePane');
  const titleEl = document.getElementById('myEraStageTitle');
  const statusEl = document.getElementById('myEraStageStatus');
  const summaryEl = document.getElementById('myEraStageSummary');
  const bodyEl = document.getElementById('myEraStageBody');
  if (!paneEl || !titleEl || !statusEl || !summaryEl || !bodyEl) return;

  const me = (state.players || []).find(p => p.id === playerId);
  const stage = state.my_era_stage || null;
  const factionColor = factionNameColor(me?.faction) || '#e5ecf5';

  if (!stage) {
    titleEl.textContent = '無個人時代關卡';
    statusEl.textContent = '此陣營沒有專屬時代關卡';
    statusEl.className = 'my-era-stage-status unavailable';
    summaryEl.textContent = me?.faction === 'red_army'
      ? '紅軍沒有個人時代關卡；其他陣營達成關卡後，效果仍會顯示於全桌的時代通知。'
      : '目前找不到這個陣營對應的時代關卡資料。';
    bodyEl.innerHTML = '';
    bodyEl.classList.remove('era-card-art-active');
    paneEl.classList.remove('era-card-art-active');
    return;
  }

  titleEl.innerHTML = `<span style="color:${factionColor};font-weight:800">${escapeHtml(stage.name || '時代關卡')}</span>`;
  const remainText = stage.remaining == null ? '持續至遊戲結束' : `剩餘 ${stage.remaining} 回合`;
  statusEl.textContent = stage.active
    ? `條件已達成｜${remainText}`
    : (stage.achieved ? '條件已達成｜效果已結束' : '尚未達成');
  statusEl.className = `my-era-stage-status ${stage.achieved ? 'active' : 'pending'}`;
  summaryEl.textContent = stage.summary_text || '';
  const section = (label, text) => `
    <section class="my-era-stage-section">
      <div class="era-achievement-section-title">${label}</div>
      <div class="modal-body-text">${escapeHtml(text || '（暫無資料）')}</div>
    </section>`;
  const fallbackMarkup = [
    section('觸發條件', stage.trigger_text),
    section('紅軍壓制', stage.success_text),
    section('革命反撲', stage.fail_text),
    section('效果期限', stage.duration_text),
  ].join('');
  const hasArt = Boolean(eraCardArtUrl(stage));
  bodyEl.innerHTML = eraCardArtMarkup(stage, fallbackMarkup);
  bodyEl.classList.toggle('era-card-art-active', hasArt);
  paneEl.classList.toggle('era-card-art-active', hasArt);
}

// 勝利畫面（2026-07-19）：state.winner 之前從未被前端顯示，遊戲結束毫無提示
//（20 回合自動桌測發現）。winner 的值是「red_army」或獲勝玩家的名字（見 victory.py）。
let victoryModalDismissedFor = null;
const VICTORY_ENDING_ART_VERSION = '20260806-ai-v3';

function victoryEndingArtUrl(sceneKey) {
  return sceneKey
    ? `/static/victory-art/${encodeURIComponent(sceneKey)}.png?v=${VICTORY_ENDING_ART_VERSION}`
    : '';
}

let victoryArtViewerReturnFocus = null;

function victoryArtViewerIsOpen() {
  return document.getElementById('victoryArtViewer')?.getAttribute('aria-hidden') === 'false';
}

function openVictoryArtViewer() {
  const viewer = document.getElementById('victoryArtViewer');
  const viewerImage = document.getElementById('victoryArtViewerImage');
  const sourceImage = document.getElementById('victoryEndingArt');
  const closeButton = document.getElementById('victoryArtViewerClose');
  if (!viewer || !viewerImage || !sourceImage?.complete || !sourceImage.naturalWidth) return;

  victoryArtViewerReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  viewerImage.src = sourceImage.currentSrc || sourceImage.src;
  viewerImage.alt = `${document.getElementById('victoryEndingTitle')?.textContent || '勝利結局'}完整插畫`;
  viewer.style.display = 'flex';
  viewer.setAttribute('aria-hidden', 'false');
  document.body.classList.add('victory-art-viewer-open');
  requestAnimationFrame(() => closeButton?.focus());
}

function closeVictoryArtViewer(restoreFocus = true) {
  const viewer = document.getElementById('victoryArtViewer');
  if (!viewer || !victoryArtViewerIsOpen()) return;
  viewer.style.display = 'none';
  viewer.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('victory-art-viewer-open');
  if (restoreFocus && victoryArtViewerReturnFocus?.isConnected) victoryArtViewerReturnFocus.focus();
  victoryArtViewerReturnFocus = null;
}

// 結局敘事（2026-08-06 使用者需求）：依勝利陣營呈現客製化的「大局勢」文字，把牆內/牆外
// 組織總數直接寫進敘事本身。優先用完整 faction_id（例如 taiwan_green/taiwan_blue 各自
// 獨立一段），沒有專屬敘事的陣營則退回 factionCategoryOf() 分類（tibet/uyghur 的多個
// 流亡據點共用同一段、rebel 分類的十幾個地方勢力共用同一套樣板並帶入陣營名稱）。
const VICTORY_ENDING_NARRATIVES = {
  red_army: (ctx) => ({
    title: '紅色鐵幕，籠罩天下',
    body: `紅軍以絕對優勢碾碎了最後的反抗。牆內組織僅剩 ${ctx.insideWallTotal} 個苟延殘喘，${ctx.outsideWallTotal} 個殘部倉皇退守牆外——但那裡也不再安全。廣播裡只剩一種聲音，街頭只剩一種顏色。這是一個沒有異議、沒有光的年代，其他陣營生靈塗炭，只能在陰影裡等待下一次機會。`,
  }),
  red_army_triumph: (ctx) => ({
    title: '赤旗遍寰宇，天下歸一統',
    body: `最後的抵抗已被掃進歷史。牆內 ${ctx.insideWallTotal} 個組織與牆外 ${ctx.outsideWallTotal} 個據點盡數納入紅色秩序，艦隊橫跨七海，赤旗插遍世界每一座首都。從此只有一種道路、一個意志、一個永不落幕的新時代——在紅軍眼中，這不是征服，而是全人類終於完成了統一。`,
  }),
  taiwan_green: (ctx) => ({
    title: '自由之島，燈火通明',
    body: `本土社團遍地開花，牆內 ${ctx.insideWallTotal} 個組織已經紮根、牆外 ${ctx.outsideWallTotal} 個持續在海外串聯。臺灣人民用選票與街頭守住了得來不易的民主——言論自由、公民社會、經濟活力，一樣不缺。這座島嶼證明了：自由與繁榮，從來不是紅色政權能夠恩賜的東西。`,
  }),
  taiwan_blue: (ctx) => ({
    title: '光復大陸，指日可待',
    body: `自由中國的旗幟重新升起。牆內已滲透 ${ctx.insideWallTotal} 個組織、牆外還有 ${ctx.outsideWallTotal} 個作為後援，反攻大陸的作戰計畫正式啟動——這一次，不再是紙上談兵。街頭巷尾開始流傳同一句話：山河終將光復，只是時間問題。`,
  }),
  hong_kong: (ctx) => ({
    title: '獅子山下，重見天日',
    body: `牆外 ${ctx.outsideWallTotal} 個組織撐住了最艱難的歲月，牆內 ${ctx.insideWallTotal} 個火種也終於燒了起來。石屎森林裡重新響起熟悉的廣東話與自由的歌聲，這座曾經被高牆包圍的城市，終於等到了屬於自己的黎明。`,
  }),
  uyghur: (ctx) => ({
    title: '東突厥斯坦，重獲自由',
    body: `牆內 ${ctx.insideWallTotal} 個組織裡的同胞終於走出鐵絲網，牆外 ${ctx.outsideWallTotal} 個離散的聲音也終於被世界聽見。天山南北重新飄揚起屬於自己的旗幟，那些被抹去的語言、信仰與名字，一件一件被找回來。`,
  }),
  tibet: (ctx) => ({
    title: '雪域高原，經幡再揚',
    body: `牆內 ${ctx.insideWallTotal} 個組織守住了寺院與村莊，牆外 ${ctx.outsideWallTotal} 個流亡多年的聲音終於等到歸鄉的消息。雪山之巔重新掛起五色經幡，誦經聲隨風傳遍整片高原——雪域重光，不再只是一句口號。`,
  }),
  manchuria: (ctx) => ({
    title: '白山黑水，滿洲復國',
    body: `牆內 ${ctx.insideWallTotal} 個組織、牆外 ${ctx.outsideWallTotal} 個海外力量終於等到這一天。白山黑水之間重新立起屬於滿洲的旗幟，那段被刻意遺忘的歷史，終於有人願意重新提起、重新書寫。`,
  }),
  mongol: (ctx) => ({
    title: '長生天下，重歸一統',
    body: `牆內 ${ctx.insideWallTotal} 個組織一路串聯到了內蒙古的每一座敖包，牆外 ${ctx.outsideWallTotal} 個力量也隨之呼應——大蒙古的版圖不再只存在於史書裡。草原重新連成一片，連內蒙古都一併囊括其中，長生天下，終於再次一統。`,
  }),
  kazakh: (ctx) => ({
    title: '伊犁河畔，重見天日',
    body: `牆內 ${ctx.insideWallTotal} 個組織撐過了最漫長的寒冬，牆外 ${ctx.outsideWallTotal} 個力量隨即呼應而來。伊犁河谷重新響起哈薩克的牧歌，那些消失在集中營裡的名字，終於一個一個被找回、被記得。`,
  }),
  // 使用者要求（2026-08-06）：反賊分類底下十幾個地方勢力（滇/苗/傣/晉/齊/吳越/粵…等）
  // 不需要各自獨立一段敘事，統一用「反賊大團結」的角度呈現——以實際獲勝的那個陣營為
  // 號召者，但強調是全體反抗勢力聯合的成果，不是單一地方勢力獨吞天下。
  rebel: (ctx) => ({
    title: '烽火燎原，反賊大團結',
    body: `牆內 ${ctx.insideWallTotal} 個地下組織、牆外 ${ctx.outsideWallTotal} 個海外力量紛紛響應——以${ctx.winnerFactionName}為首，各地反抗勢力放下彼此的歧異，結成統一戰線。從西南到東北，烽火在紅色版圖上連成一片，紅軍再也無法各個擊破。這是屬於全體反賊的勝利，不是任何一方的獨吞。`,
  }),
};

function victoryEndingNarrative(factionId, ctx) {
  if (!factionId) return null;
  const perspectiveKey = factionId === 'red_army' && ctx.viewerFaction === 'red_army'
    ? 'red_army_triumph'
    : factionId;
  const sceneKey = VICTORY_ENDING_NARRATIVES[perspectiveKey] ? perspectiveKey : factionCategoryOf(factionId);
  const template = VICTORY_ENDING_NARRATIVES[sceneKey];
  return template ? { ...template(ctx), sceneKey } : null;
}

function victoryNarrativeOrganizationTotals(players, winnerPlayer, winnerFaction) {
  // 紅軍結局中的「苟延殘喘／殘部」只描述落敗的非紅軍陣營。紅軍自己的組織仍
  // 保留在下方逐玩家摘要表，但不能混進這兩個敘事數字。紅軍觀看者會使用另一套
  // triumph 文案，仍然是在描述被納入紅色秩序的抵抗組織，因此沿用同一組非紅軍
  // 數字。非紅軍結局只描述主獲勝方自己的成果；共同勝利者另列於 UI，不會默認
  // 加進主獲勝方的敘事數字。
  const narrativePlayers = winnerFaction === 'red_army'
    ? (players || []).filter(player => player?.faction !== 'red_army')
    : (winnerPlayer ? [winnerPlayer] : []);
  return narrativePlayers.reduce((totals, player) => {
    totals.insideWallTotal += Number(player?.organization_counts?.inside_wall ?? 0) || 0;
    totals.outsideWallTotal += Number(player?.organization_counts?.outside_wall ?? 0) || 0;
    return totals;
  }, { insideWallTotal: 0, outsideWallTotal: 0 });
}

function renderVictoryModal(state) {
  const overlay = document.getElementById('victoryModal');
  const badge = document.getElementById('victoryBadge');
  if (!overlay || !badge) return;
  const winner = state.winner;
  if (!winner) {
    closeVictoryArtViewer(false);
    overlay.style.display = 'none';
    badge.style.display = 'none';
    victoryModalDismissedFor = null;
    return;
  }
  const players = state.players || [];
  const winnerPlayer = players.find(p => p.name === winner)
    || (winner === 'red_army' ? players.find(p => p.faction === 'red_army') : null);
  const winnerFaction = winnerPlayer?.faction || (winner === 'red_army' ? 'red_army' : null);
  const winnerColor = factionNameColor(winnerFaction) || '#e5ecf5';
  const winnerLabel = escapeHtml(winnerPlayer?.name || winner);
  const factionText = winnerFaction ? factionDisplayName(winnerFaction) : '';

  if (victoryModalDismissedFor === winner) {
    closeVictoryArtViewer(false);
    overlay.style.display = 'none';
    badge.style.display = 'block';
    badge.innerHTML = `遊戲結束：<span style="color:${winnerColor}">${winnerLabel}</span> 獲勝｜點擊查看結果`;
    return;
  }

  document.getElementById('victoryTitle').innerHTML =
    `<span style="color:${winnerColor};font-weight:800">${winnerLabel}</span> 獲勝`;
  document.getElementById('victorySubtitle').textContent =
    factionText ? `${factionText}｜第 ${state.turn ?? '?'} 回合結算` : `第 ${state.turn ?? '?'} 回合結算`;

  const coEl = document.getElementById('victoryCoWinners');
  const coWinners = state.co_winners || [];
  if (coWinners.length) {
    coEl.style.display = 'block';
    coEl.textContent = `共同勝利者：${coWinners.join('、')}`;
  } else {
    coEl.style.display = 'none';
  }

  // 紅軍勝利只統計非紅軍陣營的牆內／牆外組織；其他勝利者只統計主獲勝玩家。
  // 共同勝利者另列，不會默認加總到主獲勝方敘述。
  // 逐玩家摘要表仍顯示每位玩家的真實數字，不受敘事篩選影響。
  const { insideWallTotal, outsideWallTotal } = victoryNarrativeOrganizationTotals(players, winnerPlayer, winnerFaction);

  const endingEl = document.getElementById('victoryEnding');
  const endingSceneEl = document.getElementById('victoryEndingScene');
  const endingArtEl = document.getElementById('victoryEndingArt');
  const endingTitleEl = document.getElementById('victoryEndingTitle');
  const endingBodyEl = document.getElementById('victoryEndingBody');
  if (endingEl && endingTitleEl && endingBodyEl) {
    const ending = victoryEndingNarrative(winnerFaction, {
      insideWallTotal,
      outsideWallTotal,
      winnerFactionName: factionText,
      viewerFaction: players.find(p => p.id === playerId)?.faction || null,
    });
    if (ending) {
      endingEl.style.display = 'block';
      endingEl.style.setProperty('--victory-ending-accent', winnerColor);
      endingTitleEl.textContent = ending.title;
      endingBodyEl.textContent = ending.body;
      if (endingSceneEl) {
        endingSceneEl.className = 'victory-ending-scene' + (ending.sceneKey ? ` victory-ending-scene--${ending.sceneKey}` : '');
        endingSceneEl.setAttribute('aria-label', `查看「${ending.title}」完整插畫`);
      }
      if (endingArtEl) {
        const artUrl = victoryEndingArtUrl(ending.sceneKey);
        endingArtEl.onload = () => endingSceneEl?.classList.add('victory-ending-scene-loaded');
        endingArtEl.onerror = () => endingSceneEl?.classList.add('victory-ending-scene-error');
        if (endingArtEl.getAttribute('src') !== artUrl) endingArtEl.setAttribute('src', artUrl);
        if (endingArtEl.complete && endingArtEl.naturalWidth > 0) {
          endingSceneEl?.classList.add('victory-ending-scene-loaded');
        }
      }
    } else {
      endingEl.style.display = 'none';
    }
  }

  const summary = document.getElementById('victorySummary');
  const rows = players.map(p => {
    const orgCounts = p.organization_counts || {};
    const totalOrgs = orgCounts.total ?? Object.values(p.orgs || {}).reduce((a, b) => a + b, 0);
    const insideWall = orgCounts.inside_wall ?? 0;
    const outsideWall = orgCounts.outside_wall ?? Math.max(0, totalOrgs - insideWall);
    const color = factionNameColor(p.faction) || '#e5ecf5';
    const isWinner = winnerPlayer ? p.name === winnerPlayer.name : false;
    return `
      <div class="victory-summary-row${isWinner ? ' winner-row' : ''}">
        <span class="victory-player-name" style="color:${color}">${escapeHtml(p.name)}${isWinner ? '&nbsp;🏆' : ''}</span>
        <span>${escapeHtml(factionDisplayName(p.faction))}</span>
        <span>組織 ${totalOrgs}</span>
        <span>牆內 ${insideWall}</span>
        <span>牆外 ${outsideWall}</span>
        <span>資金 ${p.resources?.money ?? 0}</span>
        <span>宣傳 ${p.resources?.propaganda ?? 0}</span>
      </div>`;
  }).join('');
  summary.innerHTML = `
    <div class="victory-summary-row header">
      <span>玩家</span><span>陣營</span><span>組織</span><span>牆內</span><span>牆外</span><span>資金</span><span>宣傳</span>
    </div>${rows}`;

  const victoryGlass = overlay.querySelector('.victory-glass');
  if (victoryGlass) {
    victoryGlass.classList.toggle('victory-summary-many-players', players.length >= 5);
    const endingCopyLength = endingEl?.style.display !== 'none' ? (endingBodyEl?.textContent || '').length : 0;
    victoryGlass.classList.toggle('victory-ending-copy-long', endingCopyLength >= 90);
    victoryGlass.scrollTop = 0;
  }

  badge.style.display = 'none';
  overlay.style.display = 'flex';
}

document.addEventListener('DOMContentLoaded', () => {
  const endingScene = document.getElementById('victoryEndingScene');
  if (endingScene) {
    endingScene.addEventListener('click', openVictoryArtViewer);
    endingScene.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();
      openVictoryArtViewer();
    });
  }

  const artViewer = document.getElementById('victoryArtViewer');
  if (artViewer) artViewer.addEventListener('click', (event) => {
    if (event.target === artViewer) closeVictoryArtViewer();
  });
  document.getElementById('victoryArtViewerImage')?.addEventListener('click', event => event.stopPropagation());
  document.getElementById('victoryArtViewerClose')?.addEventListener('click', () => closeVictoryArtViewer());
  document.addEventListener('keydown', (event) => {
    if (!victoryArtViewerIsOpen()) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeVictoryArtViewer();
    } else if (event.key === 'Tab') {
      event.preventDefault();
      document.getElementById('victoryArtViewerClose')?.focus();
    }
  });

  const minimizeBtn = document.getElementById('victoryMinimizeBtn');
  if (minimizeBtn) minimizeBtn.addEventListener('click', () => {
    closeVictoryArtViewer(false);
    victoryModalDismissedFor = (window.lastGameState || {}).winner || null;
    if (window.lastGameState) renderVictoryModal(window.lastGameState);
  });
  const badge = document.getElementById('victoryBadge');
  if (badge) badge.addEventListener('click', () => {
    victoryModalDismissedFor = null;
    if (window.lastGameState) renderVictoryModal(window.lastGameState);
  });

  const peerMinimizeBtn = document.getElementById('peerActionNoticeMinimizeBtn');
  if (peerMinimizeBtn) peerMinimizeBtn.addEventListener('click', () => {
    peerActionNoticeMinimized = !peerActionNoticeMinimized;
    applyPeerActionNoticeMinimizedState();
  });
});

// 其他玩家動態通知（2026-08-06 使用者需求；2026-08-06 兩輪依使用者回饋改版為「預設是
// 真正擋住畫面的大型跳出視窗，主動縮小才變成左下角小卡片」，不是一開始就縮成小卡片、
// 也沒有另一個圓形徽章狀態）。純前端從既有 action_log 逐行比對「這行是不是某個非本人
// 玩家開頭 + 內文含哪張已知卡名」，不需要後端額外欄位——每一行 log 訊息
// （server/game.py 的 self.log(...)）約定俗成都是以 `{player.name}` 開頭，卡名出現的
// 位置不固定，所以用「掃過 cardPresentationCatalog 全部卡名、取內文中最長的相符字串」
// 來避免短卡名誤判成另一張長卡名的子字串。
let peerActionNoticeLogSnapshot = [];
let peerActionNoticeGameId = null;
let peerActionNoticeMinimized = false;
let peerActionNoticeHasContent = false;

function applyPeerActionNoticeMinimizedState() {
  const overlay = document.getElementById('peerActionNotice');
  const btn = document.getElementById('peerActionNoticeMinimizeBtn');
  if (overlay) overlay.classList.toggle('peer-action-notice-minimized', peerActionNoticeMinimized);
  if (btn) {
    btn.textContent = peerActionNoticeMinimized ? '⤢' : '—';
    btn.title = peerActionNoticeMinimized ? '展開通知' : '縮小到左下角';
    btn.setAttribute('aria-label', btn.title);
  }
}

function rememberPeerActionLog(entries) {
  if (Array.isArray(entries)) peerActionNoticeLogSnapshot = entries.slice();
}

function peerActionNoticeNewEntryStart(entries) {
  const previous = peerActionNoticeLogSnapshot;
  if (!previous.length) return 0;
  if (previous.length === entries.length && previous.every((entry, index) => entry === entries[index])) {
    return entries.length;
  }
  for (let overlap = Math.min(previous.length, entries.length); overlap > 0; overlap--) {
    const previousStart = previous.length - overlap;
    if (entries.slice(0, overlap).every((entry, index) => entry === previous[previousStart + index])) {
      return overlap;
    }
  }
  return 0;
}

function closePeerActionNotice(entries = null) {
  const overlay = document.getElementById('peerActionNotice');
  if (Array.isArray(entries)) rememberPeerActionLog(entries);
  peerActionNoticeMinimized = false;
  peerActionNoticeHasContent = false;
  if (overlay) overlay.style.display = 'none';
  applyPeerActionNoticeMinimizedState();
}

function localizePeerActionNoticeText({ actor, text, playerNames = [] }) {
  const actorName = actor?.name || '';
  const detail = text.startsWith(actorName) ? text.slice(actorName.length).trim() : text.trim();
  if (!/[A-Za-z]{3,}/.test(detail)) return text;

  const finish = (localizedDetail) => {
    const residual = [actorName, ...playerNames]
      .filter(Boolean)
      .sort((a, b) => b.length - a.length)
      .reduce((value, name) => value.split(name).join(''), localizedDetail);
    return `${actorName} ${/[A-Za-z]{3,}/.test(residual) ? '完成了一項行動' : localizedDetail}`;
  };

  const patterns = [
    [/^played (.+?) as resource(?: \(no resources from support card\))?$/i, m => `將${m[1]}作為資源使用`],
    [/^played (.+?); waiting up to \d+ seconds for (.+?) to choose cancel reaction$/i, m => `使用了${m[1]}，等待${m[2]}決定是否取消`],
    [/^played (.+?); card returned to (.+?)'s discard pile$/i, m => `使用了${m[1]}，卡牌回到${m[2]}的棄牌堆`],
    [/^played (.+)$/i, m => `使用了${m[1]}`],
    [/^triggered (.+?) and drew (\d+) card\(s\)$/i, m => `發動${m[1]}並抽了${m[2]}張牌`],
    [/^triggered (.+?) and gained (\d+) money$/i, m => `發動${m[1]}並獲得${m[2]}資金`],
    [/^triggered (.+?) and gained (\d+) propaganda$/i, m => `發動${m[1]}並獲得${m[2]}宣傳`],
    [/^triggered (.+)$/i, m => `發動了${m[1]}`],
    [/^built organization in (.+?) from (.+)$/i, m => `從${m[2]}在${m[1]}建立了組織`],
    [/^built organization in (.+?)(?: via .+)?$/i, m => `在${m[1]}建立了組織`],
    [/^moved 1 organization from (.+?) to (.+?) via (road|rail)$/i, m => `經由${m[3].toLowerCase() === 'rail' ? '鐵路' : '道路'}將1個組織從${m[1]}移到${m[2]}`],
    [/^moved 1 shared organization from (.+?) to (.+?) via (road|rail)$/i, m => `經由${m[3].toLowerCase() === 'rail' ? '鐵路' : '道路'}將1個共同組織從${m[1]}移到${m[2]}`],
    [/^dissolved 1 organization from (.+?) at (.+)$/i, m => `在${m[2]}瓦解了${m[1]}的1個組織`],
    [/^dissolved 1 shared organization via (.+?) from (.+?) at (.+)$/i, m => `在${m[3]}經由${m[1]}瓦解了${m[2]}的1個共同組織`],
    [/^bought (.+)$/i, m => `購買了${m[1]}`],
    [/^discarded (.+?) via (.+)$/i, m => `因${m[2]}棄掉${m[1]}`],
    [/^used (.+?) to force (.+?) to discard (.+)$/i, m => `使用${m[1]}迫使${m[2]}棄掉${m[3]}`],
    [/^used (.+?) before drawing new hand$/i, m => `在補充新手牌前使用了${m[1]}`],
    [/^reacted with (.+?) to cancel (.+)$/i, m => `打出${m[1]}取消${m[2]}`],
    [/^'s (.+?) was canceled by reaction(?:; card returned to (.+?)'s discard pile)?$/i, m => `的${m[1]}被反應卡取消${m[2] ? `，卡牌回到${m[2]}的棄牌堆` : ''}`],
    [/^resolved (.+?) and built in (.+)$/i, m => `結算${m[1]}並在${m[2]}建立組織`],
    [/^resolved (.+?) targeting (.+?) and discarded (\d+) random card\(s\)$/i, m => `結算${m[1]}，使${m[2]}隨機棄掉${m[3]}張牌`],
    [/^started interactive support resolution for (.+?) at tier (\d+)$/i, m => `開始結算${m[1]}第${m[2]}級效果`],
    [/^may use (.+?) before drawing new hand$/i, m => `可在補充新手牌前使用${m[1]}`],
    [/^could not play (.+?): no legal target$/i, m => `無法使用${m[1]}：沒有合法目標`],
    [/^End of turn$/i, () => '結束回合'],
  ];
  for (const [pattern, render] of patterns) {
    const match = detail.match(pattern);
    if (match) return finish(render(match));
  }

  const localized = playerMessageZhTw(detail, '');
  return finish(localized || '完成了一項行動');
}

function findLatestPeerActionSinceIndex(state, fromIndex) {
  const entries = state.action_log || [];
  const others = (state.players || []).filter(p => p.id !== playerId);
  if (!others.length) return null;
  for (let i = entries.length - 1; i >= fromIndex; i--) {
    const raw = entries[i];
    if (typeof raw !== 'string') continue;
    const stripped = raw.replace(/^\[Turn \d+\]\s*/, '');
    const actor = others.find(p => p.name && stripped.startsWith(p.name));
    if (!actor) continue;
    let cardName = null;
    let bestLength = 0;
    const catalog = cardPresentationCatalog || {};
    for (const name of Object.keys(catalog)) {
      if (name.length > bestLength && stripped.includes(name)) {
        cardName = name;
        bestLength = name.length;
      }
    }
    return { actor, text: stripped, cardName, playerNames: (state.players || []).map(p => p.name) };
  }
  return null;
}

function renderPeerActionNotice(state) {
  const overlay = document.getElementById('peerActionNotice');
  if (!overlay) return;
  const entries = state.action_log || [];

  if (peerActionNoticeGameId !== gameId) {
    // (Re)connected to a different game: don't replay the whole history as "new".
    peerActionNoticeGameId = gameId;
    peerActionNoticeLogSnapshot = [];
    closePeerActionNotice(entries);
    return;
  }

  const me = (state.players || []).find(p => p.id === playerId);
  if (me && state.current_player === me.name) {
    // 前一位玩家的廣播不應擋住本人新回合；連縮小狀態一併收掉，且消耗到最新 log，
    // 避免之後切回等待狀態時又重播上一回合的舊通知。
    closePeerActionNotice(entries);
    return;
  }

  const hasPendingChoiceForViewer = !!(state.pending_choice && state.pending_choice.player_id === playerId);
  if (hasPendingChoiceForViewer) {
    // 2026-08-09 使用者回報並要求：武裝系列等卡牌會要求對方立即互動（例如選擇要棄掉
    // 哪些手牌），先前只有「取消反應」這種有時限的 choice 才會跳過通知直接讓玩家操作，
    // 其他 pending choice（例如武裝小隊的 armed_target_discard）仍會被「其他玩家動態」
    // 大型轉播疊層蓋住，玩家得先手動縮小通知才能看到、操作選擇視窗。使用者要求只要是
    // 輪到自己要處理的 pending choice，一律直接讓玩家操作，不要再多一道縮小通知的步驟。
    // 消耗這次 log 並關閉通知，待選擇結束後也不重播同一則出牌紀錄。
    closePeerActionNotice(entries);
    return;
  }

  const newEntryStart = peerActionNoticeNewEntryStart(entries);
  rememberPeerActionLog(entries);
  if (newEntryStart >= entries.length) return;
  const found = findLatestPeerActionSinceIndex(state, newEntryStart);
  if (!found) return;
  peerActionNoticeHasContent = true;

  const playerEl = document.getElementById('peerActionNoticePlayer');
  const textEl = document.getElementById('peerActionNoticeText');
  const artEl = document.getElementById('peerActionNoticeArt');
  if (playerEl) {
    const color = factionNameColor(found.actor.faction) || '#e5ecf5';
    playerEl.innerHTML = `<span style="color:${color}">${escapeHtml(found.actor.name)}</span>`;
  }
  if (textEl) textEl.textContent = localizePeerActionNoticeText(found);
  if (artEl) {
    const artUrl = found.cardName ? playableCardArtUrl(found.cardName) : '';
    artEl.classList.remove('peer-action-notice-art-load-failed');
    artEl.classList.toggle('peer-action-notice-art-empty', !artUrl);
    artEl.innerHTML = artUrl
      ? `<img class="peer-action-notice-art-image" src="${artUrl}" alt="${escapeHtml(found.cardName)}" onerror="this.parentElement.classList.add('peer-action-notice-art-load-failed')">`
      : '';
  }

  // Every fresh action re-surfaces as the full "broadcast" view, even if the
  // previous notice had been minimized — minimizing only dismisses that one instance.
  peerActionNoticeMinimized = false;
  overlay.style.display = 'flex';
  applyPeerActionNoticeMinimizedState();
}

async function render(state) {
  const playerError = state.error ? playerMessageZhTw(state.error) : '';
  await Promise.all([loadCardPresentationCatalog(), loadFactions()]);

  const me = state.players?.find(p => p.id === playerId) || null;
  const inBaseSelection = state.game_phase === 'base_selection';
  const businessNetworkState = renderBusinessNetworkResult(state);
  if (businessNetworkState.type === 'idle') {
    lastBusinessNetworkResultKey = null;
  }
  const showLobbyFactionPicker = !inBaseSelection && !ws;
  const factionPicker = document.getElementById('factionPicker');
  if (factionPicker) factionPicker.style.display = showLobbyFactionPicker ? 'block' : 'none';

  const detailFactionId = me?.faction || pendingFactionChoice || null;
  const detailBaseName = me?.base || pendingFactionBaseChoice || null;
  renderFactionDetails(inBaseSelection ? null : detailFactionId, detailBaseName, pendingFactionBaseGroup);
  renderMyFactionView(state);
  renderMyEraStageView(state);
  renderFactionActionPanel(state);
  renderBaseSelection(state);
  renderEraAchievement(state);
  renderCurrentEvent(state);
  renderChoiceModal(state);
  renderVictoryModal(state);
  renderPeerActionNotice(state);

  // HUD
  const hud = document.getElementById('hud');
  const hudMainRow = document.getElementById('hudMainRow');
  if (hud && hudMainRow) {
    const players = state.players || [];
    const orgInfo = players.map(p => {
      const total = Object.values(p.orgs || {}).reduce((a,b)=>a+b,0);
      return `<span class="hud-chip">${escapeHtml(p.name)} 組織 ${total}</span>`;
    }).join('');

    const me = players.find(p => p.id === playerId);
    const myMoney = me?.resources?.money ?? 0;
    const myPropaganda = me?.resources?.propaganda ?? 0;
    const myMoves = me?.moves_left ?? 0;
    const phaseLabel = String(state.turn_phase || '').toLowerCase() === 'action' ? '行動' : String(state.turn_phase || '').toLowerCase() === 'event' ? '事件結算' : String(state.turn_phase || '').toLowerCase() === 'end' ? '購買' : state.turn_phase;
    hudMainRow.innerHTML = `
      <span class="hud-chip hud-chip-primary">回合 ${state.turn}</span>
      <span class="hud-chip">當前玩家 <span${(() => { const f = (state.players || []).find(p => p.name === state.current_player)?.faction; const c = factionNameColor(f); return c ? ` style="color:${c};font-weight:700"` : ''; })()}>${escapeHtml(state.current_player)}</span></span>
      <span class="hud-chip hud-chip-resource">資金 ${myMoney}</span>
      <span class="hud-chip hud-chip-resource">宣傳 ${myPropaganda}</span>
      <span class="hud-chip">移動 ${myMoves}</span>
      ${orgInfo}
    `;

    const phaseActionBar = document.getElementById('phaseActionBar');
    const gameShell = document.getElementById('gameShell');
    const advanceBtn = document.getElementById('advanceStepBtn');
    const redArmyBtn = document.getElementById('redArmyAbilityBtn');
    const isMyTurn = isMyTurnState(state);
    const waitText = pendingChoiceWaitText(state);
    const stepLabel = phaseLabel === '事件結算' ? '開始行動階段' : phaseLabel === '行動' ? '結束行動' : phaseLabel === '購買' ? '結束回合' : '結束目前步驟';
    const phaseMetaText = waitText || (isMyTurn ? `目前：${phaseLabel}｜下一步：${stepLabel}` : `目前：${phaseLabel}｜等待 ${state.current_player} 操作`);
    setPhaseActionMeta(phaseMetaText);
    if (advanceBtn) {
      advanceBtn.style.display = state.game_phase === 'main' ? 'inline-flex' : 'none';
      advanceBtn.textContent = stepLabel;
      advanceBtn.disabled = !isMyTurn || !!waitText;
      advanceBtn.title = waitText || '';
    }
    if (redArmyBtn) {
      const myFaction = me?.faction || '';
      const rawPhase = String(state.turn_phase || '').toLowerCase();
      const usedCount = Number(state.red_army_action_count || 0);
      const limitCount = Number(state.red_army_action_limit || 0);
      const usedUp = limitCount > 0 && usedCount >= limitCount;
      const hasMyPendingChoice = !!(state.pending_choice && me && state.pending_choice.player_id === me.id);
      const canShowRedArmyButton = isMyTurn && myFaction === 'red_army' && (rawPhase === 'event' || rawPhase === 'action');
      redArmyBtn.style.display = canShowRedArmyButton ? 'inline-flex' : 'none';
      redArmyBtn.textContent = `紅軍能力 ${usedCount}/${limitCount}`;
      redArmyBtn.disabled = !canShowRedArmyButton || usedUp || hasMyPendingChoice;
    }
    const topdeckBtn = document.getElementById('topdeckRightBtn');
    if (topdeckBtn) {
      const pendingUses = Number(state.pending_topdeck_uses || 0);
      const candidateCount = Number(state.topdeck_candidates_count || 0);
      const hasMyPendingChoice = !!(state.pending_choice && me && state.pending_choice.player_id === me.id);
      const canShowTopdeckButton = isMyTurn && pendingUses > 0;
      topdeckBtn.style.display = canShowTopdeckButton ? 'inline-flex' : 'none';
      topdeckBtn.textContent = `頂牌 (${pendingUses})`;
      topdeckBtn.disabled = !canShowTopdeckButton || candidateCount === 0 || hasMyPendingChoice;
      topdeckBtn.title = candidateCount === 0 ? '本回合尚未購買可頂的牌' : '';
    }

    const phaseNotice = document.getElementById('phaseActionNotice');
    const showSecondaryBar = state.game_phase === 'main' && Boolean(
      topdeckBtn?.style.display !== 'none'
      || phaseNotice?.classList.contains('visible')
    );
    if (phaseActionBar) phaseActionBar.style.display = showSecondaryBar ? 'flex' : 'none';
    if (phaseActionBar && hud) {
      const barTop = hud.offsetTop + hud.offsetHeight + 8;
      phaseActionBar.style.top = `${barTop}px`;
      if (gameShell) {
        const contentTop = showSecondaryBar ? barTop + phaseActionBar.offsetHeight + 8 : barTop;
        gameShell.style.top = `${contentTop}px`;
        gameShell.style.height = `${Math.max(0, 720 - contentTop)}px`;
      }
    }
  }

  // ✅ 地圖節點不在 render 中重建


  // Hand
  const handDiv = document.getElementById('hand');
  if (handDiv) {
    handDiv.innerHTML = '';
    const me = (state.players || []).find(p => p.id === playerId);
    const isMyTurn = isMyTurnState(state);
    if (businessNetworkState.type === 'resolved') {
      handDiv.innerHTML += businessNetworkState.html;
    }
    if (me && me.hand) {
      const rawPhase = String(state.turn_phase || '').toLowerCase();
      const hasMyPendingChoice = !!(state.pending_choice && state.pending_choice.player_id === me.id);
      const canQueueMapCard = (cardName, mode) => hasMyPendingChoice
        && ['build_organization', 'dissolve_organization'].includes(state.pending_choice?.interaction_kind)
        && (state.pending_choice?.queueable_card_names || []).includes(cardName)
        && mode === 'action';
      const handActionLegality = me.hand_action_legality || [];
      const cardActionLegality = (cardIndex) => handActionLegality[cardIndex] || {playable: true};
      const canPlayHandCardMode = (cardName, mode, cardIndex = null) => {
        if (mode === 'action' && REACTION_ONLY_ACTION_CARDS.has(cardName)) return false;
        if (mode === 'action' && cardIndex !== null && cardActionLegality(cardIndex).playable === false) return false;
        if (!isMyTurn || (hasMyPendingChoice && !canQueueMapCard(cardName, mode))) return false;
        if (rawPhase === 'action') return true;
        return rawPhase === 'event' && mode === 'action' && cardName === '紅軍奧援' && me.faction === 'red_army';
      };
      const handButtonTitle = (cardName, mode, canPlay, cardIndex = null) => {
        if (mode === 'action' && cardIndex !== null && cardActionLegality(cardIndex).playable === false) {
          return cardActionLegality(cardIndex).reason || '目前無法使用這張卡牌。';
        }
        if (canPlay) return '打出這張手牌';
        if (mode === 'action' && REACTION_ONLY_ACTION_CARDS.has(cardName)) {
          return `${cardName}的取消能力只能被動觸發：當其他玩家打出可取消的卡牌時會自動跳出反應視窗。`;
        }
        if (hasMyPendingChoice) return '請先處理目前待選擇效果。';
        if (rawPhase === 'end') return '行動階段已結束，不能再打出手牌。';
        if (rawPhase === 'event') {
          return (cardName === '紅軍奧援' && mode === 'resource')
            ? '事件結算中可先發動紅軍奧援的「行動」，資源需等行動階段。'
            : '目前不能打出一般手牌；請先處理事件結算或等待行動階段。';
        }
        return '只有當前玩家的行動階段可以打出手牌。';
      };
      me.hand.forEach((card, i) => {
        const cardAttr = escapeHtml(card);
        const isSupportCard = /奧援/.test(card);
        const variantInfo = (me.hand_variants || [])[i] || null;
        const colorName = (cardPresentation(card)?.color) || (isSupportCard ? '奧援' : '灰');
        const colorClass = cardColorClass(colorName);
        const canPlayAction = canPlayHandCardMode(card, 'action', i);
        const actionDisabledAttr = canPlayAction ? '' : 'disabled aria-disabled="true"';
        const actionTitle = handButtonTitle(card, 'action', canPlayAction, i);
        const actionLabel = cardActionLegality(i).no_legal_build_town ? '無城鎮可建立' : '行動';
        // 普通奧援只能當「行動」使用，第一顆按鈕維持「棄置」。紅軍奧援是唯一例外：
        // canonical 明載可作為資源取得 1資金＋1宣傳，因此必須顯示真正的「資源」按鈕。
        const firstButtonHtml = isSupportCard
          ? (() => {
              const canUseResourceMode = canPlayHandCardMode(card, 'resource');
              const resourceDisabledAttr = canUseResourceMode ? '' : 'disabled aria-disabled="true"';
              const isRedSupport = card === '紅軍奧援';
              const resourceTitle = canUseResourceMode
                ? (isRedSupport
                    ? '使用紅軍奧援作為資源：取得1資金與1宣傳，不執行抽牌效果。'
                    : '棄置這張奧援卡：直接送進棄牌堆，不使用、不獲得任何效果。')
                : handButtonTitle(card, 'resource', canUseResourceMode);
              const resourceLabel = isRedSupport ? '資源' : '棄置';
              return `<button class="hand-card-action-btn" type="button" ${resourceDisabledAttr} title="${escapeHtml(resourceTitle)}" data-card-index="${i}" data-card-name="${cardAttr}" data-card-mode="resource">${resourceLabel}</button>`;
            })()
          : (() => {
              const canPlayResource = canPlayHandCardMode(card, 'resource');
              const resourceDisabledAttr = canPlayResource ? '' : 'disabled aria-disabled="true"';
              const resourceTitle = handButtonTitle(card, 'resource', canPlayResource);
              return `<button class="hand-card-action-btn" type="button" ${resourceDisabledAttr} title="${escapeHtml(resourceTitle)}" data-card-index="${i}" data-card-name="${cardAttr}" data-card-mode="resource">資源</button>`;
            })();
        handDiv.innerHTML += `
          <div class='card hand-card ${colorClass}' data-card-name="${cardAttr}" data-card-zone="hand" data-card-static="false" data-card-variant-index="${variantInfo?.variant_index ?? ''}" onclick="selectCardDetail(event.currentTarget)">
            ${renderCardFace(card, 'hand', false, true, null, variantInfo)}
            <div class="hand-card-actions">
              ${firstButtonHtml}
              <button class="hand-card-action-btn" type="button" ${actionDisabledAttr} title="${escapeHtml(actionTitle)}" data-card-index="${i}" data-card-name="${cardAttr}" data-card-mode="action">${actionLabel}</button>
            </div>
          </div>`;
      });
      bindHandCardActionButtons(handDiv);
    }
  }

  // Purchase
  const purchaseStaticDiv = document.getElementById('purchaseStatic');
  const purchaseRandomDiv = document.getElementById('purchaseRandom');
  if (purchaseStaticDiv && purchaseRandomDiv) {
    purchaseStaticDiv.innerHTML = '';
    purchaseRandomDiv.innerHTML = '';
    (state.purchase_area || []).forEach((card, i) => {
      const isStatic = i < 6;
      const isSupport = /奧援/.test(card);
      const container = isStatic ? purchaseStaticDiv : purchaseRandomDiv;
      const typeClass = isStatic ? 'purchase-card-static' : 'purchase-card-random';
      const supportClass = isSupport ? ' purchase-card-support' : '';
      const colorName = (cardPresentation(card)?.color) || (isSupport ? '奧援' : '灰');
      const colorClass = cardColorClass(colorName);
      const staticSupply = isStatic ? liveStaticSupplyForCard(state, card) : null;
      const purchasePhase = String(state.turn_phase || '').toLowerCase();
      const inPurchasePhase = purchasePhase === 'action' || purchasePhase === 'end';
      const isMyPurchaseTurn = isMyTurnState(state);
      const hasMyPendingChoice = !!(state.pending_choice && me && state.pending_choice.player_id === me.id);
      const purchaseCost = state.purchase_area_costs?.[i] || {money: 0, propaganda: 0};
      const costParts = [];
      if (Number(purchaseCost.money || 0) > 0) costParts.push(`${purchaseCost.money}資金`);
      if (Number(purchaseCost.propaganda || 0) > 0) costParts.push(`${purchaseCost.propaganda}宣傳`);
      const costText = costParts.length ? costParts.join(' + ') : '免費';
      const canSelect = inPurchasePhase && isMyPurchaseTurn && !hasMyPendingChoice && (!isStatic || (staticSupply != null && staticSupply > 0));
      const selectTitle = !inPurchasePhase
        ? '目前不是行動階段，無法購買。'
        : !isMyPurchaseTurn
          ? '等待當前玩家購買。'
          : hasMyPendingChoice
            ? '請先處理目前待選擇效果。'
            : isStatic && (staticSupply == null || staticSupply <= 0)
              ? '常設供應已售完'
              : `勾選此卡（${costText}）`;
      const variantInfo = (state.purchase_area_variants || [])[i] || null;
      const isSelected = selectedPurchaseIndices.has(i);
      container.innerHTML += `
        <div class='card ${typeClass}${supportClass} ${colorClass}${isSelected ? ' purchase-card-selected' : ''}' data-card-name="${escapeHtml(card)}" data-card-zone="purchase" data-card-static="${isStatic}" data-card-count="${isStatic && staticSupply != null ? staticSupply : ''}" data-card-variant-index="${variantInfo?.variant_index ?? ''}" onclick="selectCardDetail(event.currentTarget)">
          ${renderCardFace(card, 'purchase', isStatic, true, isStatic ? staticSupply : null, variantInfo)}
          <label class="purchase-card-checkbox" title="${escapeHtml(selectTitle)}" onclick="event.stopPropagation()">
            <input type="checkbox" data-purchase-index="${i}" aria-label="勾選 ${escapeHtml(card)}" ${isSelected ? 'checked' : ''} ${canSelect ? '' : 'disabled aria-disabled="true"'} onchange="togglePurchaseSelection(event, ${i})">
          </label>
        </div>`;
    });
    updatePurchaseSelectionControls(state);
  }

  // Log
  renderPlayerStatusCards(state);
  const logTargets = [document.getElementById('log'), document.getElementById('logViewContent')].filter(Boolean);
  if (logTargets.length) {
    const entries = state.action_log || state.log || [];
    const html = entries.slice().reverse().map(entry => `<div>${escapeHtml(entry)}</div>`).join('');
    const businessNetworkLog = businessNetworkState.type === 'resolved'
      ? `<div class="business-network-log-highlight">${escapeHtml(businessNetworkState.message)}</div>`
      : '';
    logTargets.forEach(target => {
      target.innerHTML = `${businessNetworkLog}${html}`;
    });
  }

  if (playerError) {
    showStickyPlayerErrorNotice(playerError);
    syncPlayerErrorToStrategicMap(playerError);
    alert(playerError);
  } else if (stickyPlayerErrorNotice) {
    setPhaseActionNotice(stickyPlayerErrorNotice);
  }

}

document.addEventListener('DOMContentLoaded', initLobbyControls);
