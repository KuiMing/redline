let ws = null;
let wsReconnectTimer = null;
let wsReconnectAttempts = 0;
let pendingOutboundActions = [];
let gameId = null;
let playerId = null;
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
let stageResizeBound = false;
let lobbySyncTimer = null;
let latestLobbyState = null;
let lobbyTransientStatus = null;
let activeChoiceModal = null;
let lastFactionActionResultKey = null;
let lastSupportChoiceMapHighlightPayload = null;
const selectedPurchaseIndices = new Set();

function resizeStage() {
  const scale = Math.min(
    window.innerWidth / 1280,
    window.innerHeight / 720
  );
  document.documentElement.style.setProperty('--stage-scale', String(scale));
}

function playerInitialFromInput(name) {
  const trimmed = (name || '').trim();
  return (trimmed[0] || 'H').toUpperCase();
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
  return {players, chosen, ready, hasRoom, isHost, meChose, meReady, enoughPlayers, everyoneChose, everyoneReady};
}

function updateLobbyActionControls(lobbyRes = latestLobbyState) {
  const startBtn = document.getElementById('startGameBtn');
  const readyBtn = document.getElementById('toggleReadyBtn');
  const status = lobbyReadiness(lobbyRes);

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
    startBtn.disabled = !(status.isHost && status.everyoneChose && status.everyoneReady);
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
              : '所有玩家已準備，可以啟動行動';
  }
}

async function refreshLobbyState(statusText = null) {
  if (!gameId) return null;
  if (statusText) lobbyTransientStatus = statusText;
  const res = await fetch(`/lobby/${gameId}`);
  const lobbyRes = await res.json();
  if (lobbyRes.error) {
    updateLobbyStatus(lobbyRes.error);
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
    updateLobbyStatus(data.error === 'Choose faction before ready' ? '請先選擇陣營與根據地，再按準備。' : data.error);
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

function setMarketMode(mode) {
  const select = document.getElementById('marketModeSelect');
  if (select) select.value = mode;
  document.querySelectorAll('.lobby-market-option').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.marketMode === mode);
  });
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
    if (data.lan_ip) {
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
  connect();
  return true;
}

function initLobbyControls() {
  resizeStage();
  if (initProofSessionFromUrl()) return;
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
  setMarketMode(select?.value || 'sample_53');
  updateLobbyStatus();
  updateLobbyActionControls();
  syncLobbyRoomCode();
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
    body: JSON.stringify({ name: creatorName }),
  });
  const data = await res.json();
  gameId = data.game_id;
  playerId = data.host_id;
  const roomInput = document.getElementById('roomId');
  if (roomInput) {
    roomInput.value = gameId;
    syncLobbyRoomCode();
  }
  const marketSelect = document.getElementById('marketModeSelect');
  if (marketSelect) setMarketMode('sample_53');
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
    alert(data.error);
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
  const countText = countOverride != null ? String(countOverride) : info.count_text;
  const count = countText ? `<div class="card-count">剩 ${escapeHtml(countText)}</div>` : '';
  return `
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
}

function selectCardDetail(_name, _zone, _isStatic = false) {
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
  basesEl.innerHTML = activeDetailBase
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
  info.textContent = activeChoice
    ? `目前陣營：${factionDisplayName(activeChoice)}${activeBase ? `｜根據地：${baseDisplayName(activeBase)}` : (activeBaseGroup ? `｜根據地類別：${baseDisplayName(activeBaseGroup)}` : '')}`
    : '請先選擇你的陣營';

  list.innerHTML = '';
  variants.innerHTML = '';
  variants.style.display = 'none';
  bases.innerHTML = '';
  bases.style.display = 'none';
  const currentActiveOption = activeChoice ? factionOptionById(activeChoice) : null;
  const needsBaseChoice = !!(activeChoice && currentActiveOption?.base_options?.length);
  const readyForConfirm = !!activeChoice && (!needsBaseChoice || !!activeBase);
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
    btn.disabled = takenCategories.has(category.id);
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

  const payload = {game_id: gameId, name};
  if (playerId) {
    payload.player_id = playerId;
  }

  const res = await fetch('/join', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (data.error) {
    alert(data.error);
    return;
  }

  playerId = data.player_id;
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
    updateLobbyStatus(data.error === 'All players must be ready before start' ? '所有玩家都需要先按下準備。' : data.error);
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
  ws = new WebSocket(websocketUrl());

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
  const isPurchaseTurn = String(state.turn_phase || '').toLowerCase() === 'end' && isMyTurnState(state);
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
  const choice = state?.pending_choice || null;
  if (!choice) return '';
  if (isSatisfiedStaleEventBuildChoice(state)) return '';
  const me = (state.players || []).find(p => p.id === playerId) || null;
  const targetName = choice.player_name || (state.players || []).find(p => p.id === choice.player_id)?.name || '指定玩家';
  if (choice.type === 'reaction_choice') {
    const cardName = choice.played_card_name || '這張牌';
    if (me && choice.player_id === me.id) return `${choice.prompt || `是否要取消 ${cardName}？`}（請選擇「不取消」或使用取消牌）`;
    return `等待 ${targetName} 回應是否取消 ${cardName}；若 10 秒內未回應，系統會自動視同不取消。`;
  }
  if (me && choice.player_id === me.id) return choice.prompt || '請先處理目前待選擇效果。';
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
      ? '目前是購買階段；不能再打出手牌，請購買卡牌或結束回合。'
      : cardName === '紅軍奧援' && mode === 'resource'
        ? '事件結算中可先發動紅軍奧援的「行動」，資源需等行動階段。'
        : '目前不能打出一般手牌；請先處理事件結算或等待行動階段。';
    setPhaseActionNotice(message);
    return;
  }
  if (state.pending_choice && me && state.pending_choice.player_id === me.id) {
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

window.addEventListener('message', (event) => {
  if (event.origin !== window.location.origin) return;
  const data = event.data || {};
  if (data.type !== 'redline-map-state' || !data.state) return;
  window.lastGameState = data.state;
  render(data.state).catch(err => console.warn('Failed to render synced map state', err));
});

function eventBuildChoiceMapPayload(choice, sourceName = '', resolvedTitle = '') {
  if (!choice || !['event_build_organization', 'era_red_build_near_target', 'card_build_organization'].includes(choice.choice_key)) return null;
  const towns = (choice.towns || []).filter(entry => entry?.town);
  if (!towns.length) return null;
  return {
    mode: 'support-targets',
    choiceKey: choice.choice_key,
    sourceName: sourceName || choice.source_name || resolvedTitle || '建立組織',
    prompt: choice.prompt || '事件卡效果：請在戰略地圖選擇可建立組織的城鎮。',
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
  const sourceName = choice.source_name || choiceKey || '';

  if (['event_build_organization', 'era_red_build_near_target', 'card_build_organization'].includes(choiceKey) && (choiceType === 'town_choice' || choice.step === 'town')) {
    const payload = eventBuildChoiceMapPayload(choice, sourceName, sourceName);
    overlay.style.display = 'none';
    overlay.classList.remove('choice-modal-map-context');
    mapHint.style.display = 'none';
    mapHint.textContent = '';
    cards.innerHTML = '';
    activeChoiceModal = null;
    if (payload) {
      lastSupportChoiceMapHighlightPayload = payload;
      setActiveGameView('map')
        .then(() => syncChoiceModalMapHighlight(payload))
        .catch(err => console.warn('Failed to focus strategic map for event build choice', err));
    } else {
      syncChoiceModalMapHighlight(null);
    }
    return;
  }

  const targetChoicesWithMapHighlight = new Set(['support_interaction', 'card_dissolve_interaction', 'intel_network_dissolve_target', 'event_red_dissolve', 'red_army_state_security_target', 'era_red_bonus_dissolve_target']);
  const shouldHighlightTargetChoices = targetChoicesWithMapHighlight.has(choiceKey)
    && (choice.step === 'target' || choiceType === 'target_choice');
  const shouldUseMapContextModal = shouldHighlightTargetChoices;
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
  desc.innerHTML = `${escapeHtml(businessNetworkModalHeader?.desc || choice.prompt || '請進行選擇。')}${businessNetworkModalHeader?.helperHtml || ''}`;
  cards.innerHTML = businessNetworkState.html || '';

  let mapHighlightPayload = null;
  if (shouldHighlightTargetChoices) {
    const targets = (choice.targets || []).filter(entry => entry?.town);
    if (targets.length) {
      mapHint.style.display = 'block';
      mapHint.textContent = '地圖會同步高亮可選目標；主操作仍以此處列表為準。你也可以切到「戰略地圖」查看對應城鎮外框。';
      mapHighlightPayload = {
        mode: 'support-targets',
        sourceName: sourceName || resolvedTitle,
        prompt: choice.prompt || '',
        towns: targets.map((entry, index) => ({
          town: entry.town,
          label: entry.label || entry.town,
          index,
        })),
      };
      ensureStrategicMapMounted().catch(err => console.warn('Failed to mount strategic map for choice highlight', err));
    } else {
      mapHint.style.display = 'none';
      mapHint.textContent = '';
    }
  } else {
    mapHint.style.display = 'none';
    mapHint.textContent = '';
  }
  syncChoiceModalMapHighlight(mapHighlightPayload);

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
      const zoneLabel = cardEntry && typeof cardEntry === 'object' ? cardEntry.zone_label : '';
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
        const zoneBadge = `<div class="choice-card-zone-label">${escapeHtml(cardEntry.zone_label)}</div>`;
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
      btn.textContent = option?.label || `選項 ${index + 1}`;
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
      const meta = entry?.label ? `｜${entry.label}` : '';
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
      btn.textContent = entry?.label || entry?.town || entry?.id || `目標 ${index + 1}`;
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

function renderCurrentEvent(state) {
  const panel = document.getElementById('eventCardPanel');
  const content = document.getElementById('eventCardContent');
  if (!panel || !content) return;
  const event = state.current_event || null;
  if (!event) {
    panel.style.display = 'none';
    content.innerHTML = '';
    return;
  }
  panel.style.display = 'block';
  const progress = event.progress || {};
  const current = Number(progress.count || 0);
  const required = Number(progress.required || event.trigger?.count || 0);
  const statusMap = {
    active: '進行中',
    success_pending: '條件已達成，等全體玩家行動結束後結算',
    success: '成功已結算',
    failure: '失敗已結算',
    idle: '無效果',
    auto: '自動效果已套用',
    auto_pending: '等待指定玩家回合發動',
  };
  const typeMap = {idle: '歲月靜好', mission: '任務', auto: '自動'};
  const autoEffectLine = event.type === 'auto'
    ? `<div class="event-card-line"><strong>自動效果：</strong>${escapeHtml(event.effect_text || '無')}</div>`
    : '';
  const missionLines = event.type === 'mission'
    ? `
    <div class="event-card-line"><strong>任務條件：</strong>${escapeHtml(event.trigger_text || '無')}</div>
    <div class="event-card-progress">進度：${current}/${required || 0}</div>
    <div class="event-card-line"><strong>成功獎勵：</strong>${escapeHtml(event.success_text || '無')}</div>
    <div class="event-card-line"><strong>失敗／紅軍效果：</strong>${escapeHtml(event.failure_text || '無')}</div>`
    : '';
  content.innerHTML = `
    <div class="event-card-name">${escapeHtml(event.name || '未知事件')}</div>
    <div class="event-card-meta">類型：${escapeHtml(typeMap[event.type] || event.type || '未知')}｜狀態：${escapeHtml(statusMap[event.status] || event.status || '進行中')}</div>
    <div class="event-card-result"><strong>事件結果：</strong>${escapeHtml(event.result_text || statusMap[event.status] || '進行中')}</div>
    ${autoEffectLine}
    ${missionLines}
  `;
}

function minimizeEraAchievement() {
  closeEraAchievementModal();
}

function renderEraAchievement(state) {
  const overlay = document.getElementById('eraAchievementModal');
  const title = document.getElementById('eraAchievementTitle');
  const cond = document.getElementById('eraAchievementCondition');
  const success = document.getElementById('eraAchievementSuccess');
  const fail = document.getElementById('eraAchievementFail');
  const duration = document.getElementById('eraAchievementDuration');
  const pin = document.getElementById('eraPinnedNotice');
  const minimizeBtn = document.getElementById('eraAchievementMinimizeBtn');
  if (!overlay || !title || !cond || !success || !fail || !duration || !pin || !minimizeBtn) return;

  const info = state.era_notification || null;
  const activeDetails = state.active_era_details || [];

  if (!info) {
    overlay.style.display = 'none';
    pin.style.display = 'none';
    pin.innerHTML = '';
    lastEraNotificationKey = null;
    return;
  }

  const key = `${info.id}:${info.remaining ?? 'perm'}`;
  title.textContent = `${info.name}｜條件已達成`;
  cond.textContent = `達成條件：${info.trigger_text || '（暫缺）'}`;
  success.textContent = info.success_text || '（暫缺）';
  fail.textContent = info.fail_text || '（暫缺）';
  duration.textContent = `效果期限：${info.duration_text || '（暫缺）'}${info.remaining == null ? '' : `｜剩餘 ${info.remaining} 回合`}`;
  minimizeBtn.onclick = minimizeEraAchievement;

  const activeHtml = activeDetails.map(item => {
    const remainText = item.remaining == null ? '持續中' : `剩餘 ${item.remaining} 回合`;
    const activeClass = item.id === info.id ? ' active' : '';
    return `<div class="era-pin-card${activeClass}"><div class="era-pin-title">${escapeHtml(item.name)}</div><div class="era-pin-meta">條件已達成｜${escapeHtml(remainText)}</div></div>`;
  }).join('');
  pin.innerHTML = activeHtml;
  pin.style.display = activeHtml ? 'flex' : 'none';

  if (lastEraNotificationKey !== key) {
    overlay.style.display = 'flex';
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
  if (gameId) url.searchParams.set('gameId', gameId);
  if (playerId) url.searchParams.set('playerId', playerId);
  return url.toString();
}

function connectStrategicMapFrame() {
  const frame = document.getElementById('strategicMapFrame');
  if (!frame || !frame.contentWindow || !gameId || !playerId) return;
  try {
    if (typeof frame.contentWindow.connectGameMap === 'function') {
      frame.contentWindow.connectGameMap({ gameId, playerId });
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
let pendingBuildOrigin = null;
let lastBusinessNetworkResultKey = null;

async function renderBuildSupport(state) {
  const panel = document.getElementById('buildSupportPanel');
  const info = document.getElementById('buildSupportInfo');
  const originsEl = document.getElementById('buildSupportOrigins');
  const targetsEl = document.getElementById('buildSupportTargets');
  if (!panel || !info || !originsEl || !targetsEl) return;

  const me = state.players?.find(p => p.id === playerId) || null;
  const myFaction = me?.faction || null;
  const owned = Object.keys(me?.orgs || {});
  const isSafehouse = myFaction === 'hong_kong' && owned.some(t => ['香港城', '臺北'].includes(t));
  const inAction = String(state.turn_phase).toLowerCase() === 'action';
  const isMine = state.current_player && me && state.current_player === me.name;

  panel.style.display = isSafehouse && inAction && isMine ? 'block' : 'none';
  if (!(isSafehouse && inAction && isMine)) {
    pendingBuildOrigin = null;
    originsEl.innerHTML = '';
    targetsEl.innerHTML = '';
    info.textContent = '';
    return;
  }

  const mapData = await getFullMapData();
  const towns = mapData?.towns || {};
  originsEl.innerHTML = '';
  targetsEl.innerHTML = '';

  info.textContent = pendingBuildOrigin
    ? `起點：${pendingBuildOrigin}，請選擇距離 2 內的建立目標`
    : '安全屋可讓你建立距離 +1。請先選擇建立起點。';

  owned.forEach(origin => {
    const btn = document.createElement('button');
    btn.className = `base-choice-btn${pendingBuildOrigin === origin ? ' active' : ''}`;
    btn.textContent = origin;
    btn.onclick = async () => {
      pendingBuildOrigin = origin;
      await renderBuildSupport(state);
    };
    originsEl.appendChild(btn);
  });

  if (!pendingBuildOrigin) return;

  const maxDistance = 2;
  const visited = new Set([pendingBuildOrigin]);
  let frontier = [[pendingBuildOrigin, 0]];
  const reachable = new Set();
  while (frontier.length) {
    const [town, dist] = frontier.shift();
    if (dist >= maxDistance) continue;
    const data = towns[town] || {};
    const nexts = new Set([...(data.road || []), ...(data.rail || [])]);
    for (const nxt of nexts) {
      if (visited.has(nxt)) continue;
      visited.add(nxt);
      reachable.add(nxt);
      frontier.push([nxt, dist + 1]);
    }
  }

  Array.from(reachable).sort().forEach(target => {
    const btn = document.createElement('button');
    btn.className = 'base-choice-btn';
    btn.textContent = target;
    btn.onclick = () => sendAction('build', { from: pendingBuildOrigin, town: target });
    targetsEl.appendChild(btn);
  });
}

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
    const usedCount = Number(state.red_army_action_count || 0);
    const limitCount = Number(state.red_army_action_limit || 0);
    const usedUp = limitCount > 0 && usedCount >= limitCount;
    if (usedUp || hasResult) {
      panel.style.display = 'none';
      panel.classList.remove('overlay-active');
      info.textContent = '';
      buttons.innerHTML = '';
      return;
    }
    panel.style.display = 'block';
    info.innerHTML = `
      <div class="faction-action-placeholder">
        <div>紅軍能力不再自動彈出；可在開始行動階段前，按上方或此處的「紅軍能力」按鈕自行選擇時機。</div>
        <div>本回合已用 ${usedCount}/${limitCount} 次。</div>
      </div>`;
    const btn = document.createElement('button');
    btn.className = 'base-choice-btn';
    btn.type = 'button';
    btn.textContent = `紅軍能力（${usedCount}/${limitCount}）`;
    btn.disabled = usedUp || hasActivePendingChoice;
    btn.setAttribute('aria-disabled', btn.disabled ? 'true' : 'false');
    btn.onclick = () => openRedArmyAbilityModal(state);
    buttons.appendChild(btn);
    return;
  }

  if (!inAction || !isMine || hasActivePendingChoice) return;

  const showCenteredActionPanel = (title, message, buildButtons, hint = '', resultHtml = '') => {
    panel.style.display = 'none';
    panel.classList.remove('overlay-active');
    info.textContent = '';
    buttons.innerHTML = '';
    modalOverlay.style.display = 'flex';
    modalTitle.textContent = title;
    modalDesc.textContent = factionActionUsed ? '本回合已發動陣營能力。' : message;
    modalHint.innerHTML = resultHtml || escapeHtml(factionActionUsed ? '請進行其他行動，或結束目前行動階段。' : hint);
    modalChoices.innerHTML = '';
    modalChoices.classList.remove('red-army-action-choices');
    if (oddBtn) oddBtn.style.display = 'none';
    if (evenBtn) evenBtn.style.display = 'none';
    if (!factionActionUsed) buildButtons(modalChoices);
    closeBtn.onclick = closeFactionActionModal;
  };

  if (faction === 'aomen') {
    showCenteredActionPanel(
      '賭徒耳語',
      hasResult ? '本回合發動結果如下。' : '澳門可在行動階段發動一次賭徒耳語，請先選擇猜奇或猜偶。',
      (target) => {
        const btn = document.createElement('button');
        btn.className = 'modal-choice-btn';
        btn.type = 'button';
        btn.textContent = '發動 賭徒耳語';
        btn.onclick = openGamblerGuessModal;
        target.appendChild(btn);
      },
      '將 1 張手牌放進牌庫底，猜牌庫頂牌購買費用奇偶；若猜中獲得 3 點宣傳與 3 點資金。',
      factionResult.html
    );
    return;
  }


  if (faction === 'reform_opening') {
    showCenteredActionPanel(
      '紅軍派系',
      hasResult ? '本回合發動結果如下。' : '改革開放派可在行動階段發動一次紅軍派系。',
      (target) => {
        const btn = document.createElement('button');
        btn.className = 'modal-choice-btn';
        btn.type = 'button';
        btn.textContent = '發動 紅軍派系';
        btn.onclick = () => {
          sendAction('faction_action', { name: '紅軍派系' });
          closeFactionActionModal();
        };
        target.appendChild(btn);
      },
      '檢視牌庫頂 3 張牌，以任意順序放回牌庫頂，然後抽 1 張牌。',
      factionResult.html
    );
    return;
  }

  if (faction === 'liberals') {
    showCenteredActionPanel(
      '立場試探',
      hasResult ? '本回合發動結果如下；若仍可操作，可再次查看效果說明。' : '自由派可在行動階段發動一次立場試探。',
      (target) => {
        const btn = document.createElement('button');
        btn.className = 'modal-choice-btn';
        btn.type = 'button';
        btn.textContent = '發動 立場試探';
        btn.onclick = () => {
          sendAction('faction_action', { name: '立場試探' });
        };
        target.appendChild(btn);
      },
      '展示牌庫頂牌；若購買費用為奇數則加入手牌，若為偶數則放入棄牌堆。',
      factionResult.html
    );
    return;
  }

  const ethnicRitualFactions = new Set(['zhuang','yi','bai','hani','dai','miao','tujia','dong','buyei','yao','li']);
  if (ethnicRitualFactions.has(faction)) {
    showCenteredActionPanel(
      '民族祭儀',
      hasResult ? '本回合發動結果如下。' : '可在行動階段發動一次民族祭儀，請先猜奇偶。',
      (target) => {
        const btn = document.createElement('button');
        btn.className = 'modal-choice-btn';
        btn.type = 'button';
        btn.textContent = '發動 民族祭儀';
        btn.onclick = openEthnicRitualGuessModal;
        target.appendChild(btn);
      },
      '猜中可獲得 2 點宣傳與 2 點資金；沒猜中則獲得 2 點宣傳或 2 點資金（二選一）。',
      factionResult.html
    );
  }
}

function setPhaseActionNotice(message = '') {
  const notice = document.getElementById('phaseActionNotice');
  if (!notice) return;
  notice.textContent = message || '';
  notice.classList.toggle('visible', !!message);
}

function formatFactionActionResult(result) {
  if (!result || !result.name) return '';
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
      setPhaseActionNotice(message);
    }
    const html = `<div class="faction-action-result">${escapeHtml(message)}</div>`;
    info.innerHTML = html;
    return {hasResult: true, message, html};
  }

  lastFactionActionResultKey = null;
  setPhaseActionNotice('');

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
    const html = `
      <div class="faction-action-placeholder">
        <div>紅軍可在此發動統戰部、政工部、國安部或中紀委；結果會直接顯示於此。</div>
        <ul class="red-army-action-help-list">
          <li><strong>統戰部：</strong>抽 1 張牌。</li>
          <li><strong>政工部：</strong>選擇 1 名非紅軍玩家，將 1 張內鬥放到其牌庫頂；同一目標每回合限 1 次。</li>
          <li><strong>國安部：</strong>選擇其他玩家在紅軍組織 1 格內的 1 個牆內組織瓦解；同一目標每回合限 1 次。</li>
          <li><strong>中紀委：</strong>可棄掉任意張手牌，然後抽等量的牌。</li>
        </ul>
      </div>`;
    info.innerHTML = html;
    return {hasResult: false, message: '', html};
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
    setPhaseActionNotice('');
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
    const totalOrgs = Object.values(player.orgs || {}).reduce((a, b) => a + b, 0);
    const money = player.resources?.money ?? 0;
    const propaganda = player.resources?.propaganda ?? 0;
    const handCount = player.hand?.length ?? 0;
    const discardPile = player.discard_pile || [];
    const discardCount = player.discard_count ?? discardPile.length;
    const discardPreview = discardPile.length
      ? discardPile.map(card => `<span class="player-status-discard-card">${escapeHtml(card)}</span>`).join('')
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
          <div class="player-status-stat"><span>組織</span><strong>${totalOrgs}</strong></div>
          <div class="player-status-stat"><span>資金</span><strong>${money}</strong></div>
          <div class="player-status-stat"><span>宣傳</span><strong>${propaganda}</strong></div>
          <div class="player-status-stat"><span>手牌</span><strong>${handCount}</strong></div>
          <div class="player-status-stat"><span>棄牌</span><strong>${discardCount}</strong></div>
          <div class="player-status-stat"><span>移動</span><strong>${moves}</strong></div>
        </div>
        <div class="player-status-discard-preview">
          <span class="player-status-discard-label">棄牌堆</span>
          <div class="player-status-discard-list">${discardPreview}</div>
        </div>
      </article>`;
  }).join('');
}

// 我的陣營（2026-07-19 使用者需求）：遊戲中隨時可查看自己陣營的能力/規則限制/獲勝條件。
// 資料萃取邏輯與 lobby 的 renderFactionDetails 相同（能力=abilities 排除 setup/restriction 型；
// 規則與限制=setup_effects+special_rules+restrictions+setup/restriction 型能力；根據地能力併入能力）。
function openMyFactionModal() {
  const overlay = document.getElementById('myFactionModal');
  const titleEl = document.getElementById('myFactionTitle');
  const bodyEl = document.getElementById('myFactionBody');
  if (!overlay || !titleEl || !bodyEl) return;
  const state = window.lastGameState || {};
  const me = (state.players || []).find(p => p.id === playerId);
  if (!me || !me.faction) return;
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
  if (!opt) return;

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
  bodyEl.innerHTML = [
    section('根據地', baseName ? [baseDisplayName(baseName)] : []),
    section('能力', abilities.map(renderItem)),
    section('規則與限制', rules),
    section('獲勝條件', wins),
  ].join('');
  overlay.style.display = 'flex';
}

function closeMyFactionModal() {
  const overlay = document.getElementById('myFactionModal');
  if (overlay) overlay.style.display = 'none';
}

// 勝利畫面（2026-07-19）：state.winner 之前從未被前端顯示，遊戲結束毫無提示
//（20 回合自動桌測發現）。winner 的值是「red_army」或獲勝玩家的名字（見 victory.py）。
let victoryModalDismissedFor = null;

function renderVictoryModal(state) {
  const overlay = document.getElementById('victoryModal');
  const badge = document.getElementById('victoryBadge');
  if (!overlay || !badge) return;
  const winner = state.winner;
  if (!winner) {
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

  const summary = document.getElementById('victorySummary');
  const rows = players.map(p => {
    const totalOrgs = Object.values(p.orgs || {}).reduce((a, b) => a + b, 0);
    const color = factionNameColor(p.faction) || '#e5ecf5';
    const isWinner = winnerPlayer ? p.name === winnerPlayer.name : false;
    return `
      <div class="victory-summary-row${isWinner ? ' winner-row' : ''}">
        <span class="victory-player-name" style="color:${color}">${escapeHtml(p.name)}${isWinner ? '&nbsp;🏆' : ''}</span>
        <span>${escapeHtml(factionDisplayName(p.faction))}</span>
        <span>組織 ${totalOrgs}</span>
        <span>資金 ${p.resources?.money ?? 0}</span>
        <span>宣傳 ${p.resources?.propaganda ?? 0}</span>
      </div>`;
  }).join('');
  summary.innerHTML = `
    <div class="victory-summary-row header">
      <span>玩家</span><span>陣營</span><span>組織</span><span>資金</span><span>宣傳</span>
    </div>${rows}`;

  badge.style.display = 'none';
  overlay.style.display = 'flex';
}

document.addEventListener('DOMContentLoaded', () => {
  const minimizeBtn = document.getElementById('victoryMinimizeBtn');
  if (minimizeBtn) minimizeBtn.addEventListener('click', () => {
    victoryModalDismissedFor = (window.lastGameState || {}).winner || null;
    if (window.lastGameState) renderVictoryModal(window.lastGameState);
  });
  const badge = document.getElementById('victoryBadge');
  if (badge) badge.addEventListener('click', () => {
    victoryModalDismissedFor = null;
    if (window.lastGameState) renderVictoryModal(window.lastGameState);
  });
});

async function render(state) {
  if (state.error) {
    alert(state.error);
  }
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
  await renderBuildSupport(state);
  renderFactionActionPanel(state);
  renderBaseSelection(state);
  renderEraAchievement(state);
  renderCurrentEvent(state);
  renderChoiceModal(state);
  renderVictoryModal(state);

  // HUD
  const hud = document.getElementById('hud');
  if (hud) {
    const players = state.players || [];
    const orgInfo = players.map(p => {
      const total = Object.values(p.orgs || {}).reduce((a,b)=>a+b,0);
      return `<span class="hud-chip">${escapeHtml(p.name)} 組織 ${total}</span>`;
    }).join('');

    const me = players.find(p => p.id === playerId);
    const myMoney = me?.resources?.money ?? 0;
    const myPropaganda = me?.resources?.propaganda ?? 0;
    const myMoves = me?.moves_left ?? 0;
    const myHand = me?.hand?.length ?? 0;
    const phaseLabel = String(state.turn_phase || '').toLowerCase() === 'action' ? '行動' : String(state.turn_phase || '').toLowerCase() === 'event' ? '事件結算' : String(state.turn_phase || '').toLowerCase() === 'end' ? '購買' : state.turn_phase;
    const eraStatus = (state.active_era_details || []).map(item => {
      const remainText = item.remaining == null ? '持續中' : `剩餘 ${item.remaining} 回合`;
      return `<span class="hud-era-pill">${escapeHtml(item.name)}｜條件已達成｜${escapeHtml(remainText)}</span>`;
    }).join('');

    const marketModeLabel = state.market_mode === 'all_cards' ? '全部卡牌' : '53 張卡牌';
    hud.innerHTML = `
      <div class="hud-main-row">
        <span class="hud-chip hud-chip-primary">回合 ${state.turn}</span>
        <span class="hud-chip hud-chip-primary">${phaseLabel}階段</span>
        <span class="hud-chip">當前玩家 <span${(() => { const f = (state.players || []).find(p => p.name === state.current_player)?.faction; const c = factionNameColor(f); return c ? ` style="color:${c};font-weight:700"` : ''; })()}>${escapeHtml(state.current_player)}</span></span>
        <span class="hud-chip">手牌 ${myHand}</span>
        <span class="hud-chip hud-chip-resource">資金 ${myMoney}</span>
        <span class="hud-chip hud-chip-resource">宣傳 ${myPropaganda}</span>
        <span class="hud-chip">移動 ${myMoves}</span>
        <span class="hud-chip hud-chip-market">牌庫模式 ${marketModeLabel}</span>
        ${orgInfo}
      </div>
      ${eraStatus ? `<div class="hud-era-row">${eraStatus}</div>` : ''}
    `;

    const phaseActionBar = document.getElementById('phaseActionBar');
    if (phaseActionBar) phaseActionBar.style.display = state.game_phase === 'main' ? 'flex' : 'none';
    const phaseActionMeta = document.getElementById('phaseActionMeta');
    const advanceBtn = document.getElementById('advanceStepBtn');
    const redArmyBtn = document.getElementById('redArmyAbilityBtn');
    const isMyTurn = isMyTurnState(state);
    const waitText = pendingChoiceWaitText(state);
    const stepLabel = phaseLabel === '事件結算' ? '開始行動階段' : phaseLabel === '行動' ? '開始購買階段' : phaseLabel === '購買' ? '結束回合' : '結束目前步驟';
    if (phaseActionMeta) {
      phaseActionMeta.textContent = waitText || (isMyTurn ? `目前：${phaseLabel}｜下一步：${stepLabel}` : `目前：${phaseLabel}｜等待 ${state.current_player} 操作`);
    }
    if (advanceBtn) {
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
      const canPlayHandCardMode = (cardName, mode) => {
        if (!isMyTurn || hasMyPendingChoice) return false;
        if (rawPhase === 'action') return true;
        return rawPhase === 'event' && mode === 'action' && cardName === '紅軍奧援' && me.faction === 'red_army';
      };
      const handButtonTitle = (cardName, mode, canPlay) => {
        if (canPlay) return '打出這張手牌';
        if (hasMyPendingChoice) return '請先處理目前待選擇效果。';
        if (rawPhase === 'end') return '目前是購買階段；不能再打出手牌。';
        if (rawPhase === 'event') {
          return (cardName === '紅軍奧援' && mode === 'resource')
            ? '事件結算中可先發動紅軍奧援的「行動」，資源需等行動階段。'
            : '目前不能打出一般手牌；請先處理事件結算或等待行動階段。';
        }
        return '只有當前玩家的行動階段可以打出手牌。';
      };
      me.hand.forEach((card, i) => {
        const cardArg = escapeHtml(jsSingleQuotedString(card));
        const cardAttr = escapeHtml(card);
        const isSupportCard = /奧援/.test(card);
        const variantInfo = (me.hand_variants || [])[i] || null;
        const colorName = (cardPresentation(card)?.color) || (isSupportCard ? '奧援' : '灰');
        const colorClass = cardColorClass(colorName);
        const canPlayAction = canPlayHandCardMode(card, 'action');
        const actionDisabledAttr = canPlayAction ? '' : 'disabled aria-disabled="true"';
        const actionTitle = handButtonTitle(card, 'action', canPlayAction);
        // 奧援卡只能當「行動」打出；效果依區域主導者判定 I/II/III 級（完整文字已列在卡面），
        // 本身不提供資源，所以第一顆按鈕不是「資源」而是「棄置」——不使用這張牌，直接送進
        // 棄牌堆，沿用 play_card(mode='resource') 對奧援卡原本就有的「不給資源、直接棄置」
        // 行為（2026-07-16 使用者需求；原本另有一顆只做閃爍聚焦的「詳情」鈕，卡面文字
        // 完整顯示後已無存在意義，2026-07-17 移除）。
        const firstButtonHtml = isSupportCard
          ? (() => {
              const canDiscard = canPlayHandCardMode(card, 'resource');
              const discardDisabledAttr = canDiscard ? '' : 'disabled aria-disabled="true"';
              const discardTitle = canDiscard ? '棄置這張奧援卡：直接送進棄牌堆，不使用、不獲得任何效果。' : handButtonTitle(card, 'resource', canDiscard);
              return `<button class="hand-card-action-btn" type="button" ${discardDisabledAttr} title="${escapeHtml(discardTitle)}" data-card-index="${i}" data-card-name="${cardAttr}" data-card-mode="resource">棄置</button>`;
            })()
          : (() => {
              const canPlayResource = canPlayHandCardMode(card, 'resource');
              const resourceDisabledAttr = canPlayResource ? '' : 'disabled aria-disabled="true"';
              const resourceTitle = handButtonTitle(card, 'resource', canPlayResource);
              return `<button class="hand-card-action-btn" type="button" ${resourceDisabledAttr} title="${escapeHtml(resourceTitle)}" data-card-index="${i}" data-card-name="${cardAttr}" data-card-mode="resource">資源</button>`;
            })();
        handDiv.innerHTML += `
          <div class='card hand-card ${colorClass}' onclick="selectCardDetail(${cardArg},'hand',false)">
            ${renderCardFace(card, 'hand', false, true, null, variantInfo)}
            <div class="hand-card-actions">
              ${firstButtonHtml}
              <button class="hand-card-action-btn" type="button" ${actionDisabledAttr} title="${escapeHtml(actionTitle)}" data-card-index="${i}" data-card-name="${cardAttr}" data-card-mode="action">行動</button>
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
      const inPurchasePhase = String(state.turn_phase || '').toLowerCase() === 'end';
      const isMyPurchaseTurn = isMyTurnState(state);
      const hasMyPendingChoice = !!(state.pending_choice && me && state.pending_choice.player_id === me.id);
      const purchaseCost = state.purchase_area_costs?.[i] || {money: 0, propaganda: 0};
      const costParts = [];
      if (Number(purchaseCost.money || 0) > 0) costParts.push(`${purchaseCost.money}資金`);
      if (Number(purchaseCost.propaganda || 0) > 0) costParts.push(`${purchaseCost.propaganda}宣傳`);
      const costText = costParts.length ? costParts.join(' + ') : '免費';
      const canSelect = inPurchasePhase && isMyPurchaseTurn && !hasMyPendingChoice && (!isStatic || (staticSupply != null && staticSupply > 0));
      const selectTitle = !inPurchasePhase
        ? '行動階段結束後才能購買。'
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
        <div class='card ${typeClass}${supportClass} ${colorClass}${isSelected ? ' purchase-card-selected' : ''}' onclick="selectCardDetail(${JSON.stringify(card)},'purchase',${isStatic})">
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
    const html = entries.slice().reverse().map(entry => `<div>${entry}</div>`).join('');
    const businessNetworkLog = businessNetworkState.type === 'resolved'
      ? `<div class="business-network-log-highlight">${escapeHtml(businessNetworkState.message)}</div>`
      : '';
    logTargets.forEach(target => {
      target.innerHTML = `${businessNetworkLog}${html}`;
    });
  }

}

document.addEventListener('DOMContentLoaded', initLobbyControls);
