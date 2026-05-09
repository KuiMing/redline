let ws = null;
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
  if (statusText && rosterStatus) rosterStatus.textContent = statusText;
  if (statusText && hint) hint.textContent = statusText;
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
    const everyoneChose = players.length > 0 && Object.keys(chosen).length === players.length;
    const everyoneReady = players.length > 0 && players.every(([pid]) => ready[pid]);
    if (statusText) {
      hint.textContent = statusText;
    } else if (everyoneChose && everyoneReady) {
      hint.textContent = '所有玩家已準備；房主可以啟動行動。';
    } else if (everyoneChose) {
      hint.textContent = '玩家陣營已選定；等待所有玩家按下準備。';
    } else {
      hint.textContent = `已進入 ${players.length}/4 人作戰室；等待玩家選擇陣營。`;
    }
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
  const res = await fetch(`/lobby/${gameId}`);
  const lobbyRes = await res.json();
  if (lobbyRes.error) {
    updateLobbyStatus(lobbyRes.error);
    return null;
  }
  await loadFactions();
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

function syncLobbyRoomCode() {
  const roomInput = document.getElementById('roomId');
  if (!roomInput) return;
  roomInput.title = roomInput.value || '尚未建立房間';
}

function setMarketMode(mode) {
  const select = document.getElementById('marketModeSelect');
  if (select) select.value = mode;
  document.querySelectorAll('.lobby-market-option').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.marketMode === mode);
  });
}

async function copyRoomId() {
  const roomIdValue = document.getElementById('roomId')?.value || '';
  if (!roomIdValue) {
    updateLobbyStatus('尚未建立作戰室，沒有可複製的房間代碼。');
    return;
  }
  try {
    await navigator.clipboard.writeText(roomIdValue);
    updateLobbyStatus('房間代碼已複製，可以分享給其他玩家。');
  } catch (err) {
    updateLobbyStatus('無法自動複製；請手動選取房間代碼。');
  }
}

function initLobbyControls() {
  resizeStage();
  if (!stageResizeBound) {
    window.addEventListener('resize', resizeStage);
    stageResizeBound = true;
  }
  const nameInput = document.getElementById('playerName');
  if (nameInput && nameInput.dataset.bound !== '1') {
    nameInput.dataset.bound = '1';
    nameInput.addEventListener('input', () => updateLobbyStatus());
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

function initTabs() {
  const tabs = document.querySelectorAll('.game-tab');
  const views = document.querySelectorAll('.game-view');
  if (!tabs.length || !views.length) return;

  tabs.forEach(tab => {
    if (tab.dataset.bound === '1') return;
    tab.dataset.bound = '1';
    tab.addEventListener('click', async () => {
      const view = tab.dataset.view;
      tabs.forEach(t => t.classList.toggle('active', t === tab));
      views.forEach(v => v.classList.toggle('active', v.id === `${view}View`));

      if (view === 'map') {
        await ensureStrategicMapMounted();
      }
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
  const res = await fetch('/create', { method: 'POST' });
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
  await loadFactions();
  startLobbySync();
  await renderFactionPicker();
  updateLobbyStatus('作戰室已建立；請選擇陣營，或分享房間代碼。');
}

async function chooseFaction(factionId) {
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
  const res = await fetch('/choose-faction', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ game_id: gameId, player_id: playerId, faction_id: pendingFactionChoice, base_name: pendingFactionBaseChoice })
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

function factionDisplayName(factionId) {
  for (const category of availableFactionCategories) {
    for (const opt of (category.options || [])) {
      if (opt.id !== factionId) continue;
      if (factionId === 'taiwan_green') return '臺灣（綠線）';
      if (factionId === 'taiwan_blue') return '臺灣（藍線）';
      if (category.id === 'uyghur' || category.id === 'tibet') {
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

function renderCardFace(cardName, zone, isStatic = false, compact = false) {
  const info = cardPresentation(cardName) || {};
  const isSupport = /奧援/.test(cardName);
  const color = info.color || (isSupport ? '奧援' : '灰');
  const colorClass = cardColorClass(color);
  const colorStyle = styleVars(cardColorStyle(color));
  const typeLabel = zone === 'hand' ? '手牌' : (isStatic ? '常設購買區' : '隨機購買區');
  const headerMeta = [info.kind, info.strength, info.cost_text].filter(Boolean).join(' ・ ');
  const effectLines = splitEffectLines(info.effect_text || (isSupport ? '奧援卡，依區域主導者判定 I・II・III 級效果。' : '（暫無資料）'));
  const badgeItems = [];
  if (info.resource_text) badgeItems.push(`資源 ${info.resource_text}`);
  if (info.position_text) badgeItems.push(info.position_text);
  else badgeItems.push(typeLabel);
  const meaning = info.meaning_text ? `<div class="card-meaning">${escapeHtml(info.meaning_text)}</div>` : '';
  const count = info.count_text ? `<div class="card-count">剩 ${escapeHtml(info.count_text)}</div>` : '';
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

function renderFactionDetails(factionId) {
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

  const rules = [
    ...(opt.setup_effects || []),
    ...(opt.special_rules || []),
    ...(opt.restrictions || []),
  ];
  const selectedBaseData = (opt.bases || []).find(base => base?.name === pendingFactionBaseChoice) || null;
  const abilities = [
    ...((opt.abilities_text || opt.abilities || [])),
    ...((selectedBaseData?.abilities) || []),
  ];
  const wins = opt.win_condition_text
    ? [opt.win_condition_text]
    : (opt.win_conditions || []).map(humanizeWinCondition);

  title.textContent = factionDisplayName(factionId);
  basesEl.innerHTML = pendingFactionBaseChoice
    ? `<div class="faction-detail-section-title">根據地</div><ul><li>${baseDisplayName(pendingFactionBaseChoice)}</li></ul>`
    : (pendingFactionBaseGroup ? `<div class="faction-detail-section-title">根據地類別</div><ul><li>${baseDisplayName(pendingFactionBaseGroup)}</li></ul>` : '');
  abilitiesEl.innerHTML = `<div class="faction-detail-section-title">能力</div><ul>${abilities.map(a => `<li>${typeof a === 'string' ? a : [a.name_override || a.name, a.trigger, a.effect].filter(Boolean).join('：')}</li>`).join('') || '<li>（暫無資料）</li>'}</ul>`;
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
  renderFactionDetails(readyForConfirm ? activeChoice : null);

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
  gameId = document.getElementById('roomId').value;
  syncLobbyRoomCode();
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


function connect() {
  stopLobbySync();
  ws = new WebSocket(`ws://${location.host}/ws/${gameId}/${playerId}`);

  ws.onmessage = async (event) => {
    const state = JSON.parse(event.data);
    window.lastGameState = state;
    await render(state);
    syncStrategicMap(state);
  };

  document.getElementById('lobby').style.display = 'none';
  const shell = document.getElementById('gameShell');
  if (shell) shell.style.display = 'block';
  const picker = document.getElementById('factionPicker');
  if (picker) picker.style.display = 'none';
  resizeStage();
  if (!stageResizeBound) {
    window.addEventListener('resize', resizeStage);
    stageResizeBound = true;
  }

  initTabs();
}

function sendAction(action, payload = {}) {
  const debug = document.getElementById('debugSocketState');
  if (debug) {
    debug.textContent = `sendAction:${action}:readyState=${ws ? ws.readyState : 'null'}`;
  }
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({action, ...payload}));
}

window.addEventListener('DOMContentLoaded', resizeStage);
resizeStage();

function closeFactionActionModal() {
  activeFactionActionModal = null;
  const overlay = document.getElementById('factionActionModal');
  if (overlay) overlay.style.display = 'none';
}

function closeEraAchievementModal() {
  const overlay = document.getElementById('eraAchievementModal');
  if (overlay) overlay.style.display = 'none';
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

function openGamblerGuessModal() {
  activeFactionActionModal = '賭徒耳語';
  const overlay = document.getElementById('factionActionModal');
  if (!overlay) return;
  overlay.style.display = 'flex';
  document.getElementById('factionActionModalTitle').textContent = '賭徒耳語';
  document.getElementById('factionActionModalDesc').textContent = '請猜牌庫頂牌購買費用的奇偶。';
  document.getElementById('factionActionModalRewardHint').textContent = '猜中可獲得 3 點資金與 3 點宣傳。';
  document.getElementById('guessOddBtn').onclick = () => {
    sendAction('faction_action', { name: '賭徒耳語', guess: 'odd' });
    closeFactionActionModal();
  };
  document.getElementById('guessEvenBtn').onclick = () => {
    sendAction('faction_action', { name: '賭徒耳語', guess: 'even' });
    closeFactionActionModal();
  };
  document.getElementById('closeFactionActionModal').onclick = closeFactionActionModal;
}

function openEthnicRitualGuessModal() {
  activeFactionActionModal = '民族祭儀';
  const overlay = document.getElementById('factionActionModal');
  if (!overlay) return;
  overlay.style.display = 'flex';
  document.getElementById('factionActionModalTitle').textContent = '民族祭儀';
  document.getElementById('factionActionModalDesc').textContent = '請猜牌庫頂牌購買費用的奇偶。';
  document.getElementById('factionActionModalRewardHint').textContent = '猜中可獲得 2 點宣傳與 2 點資金；沒猜中則獲得 2 點宣傳。';
  document.getElementById('guessOddBtn').onclick = () => {
    sendAction('faction_action', { name: '民族祭儀', guess: 'odd' });
    closeFactionActionModal();
  };
  document.getElementById('guessEvenBtn').onclick = () => {
    sendAction('faction_action', { name: '民族祭儀', guess: 'even' });
    closeFactionActionModal();
  };
  document.getElementById('closeFactionActionModal').onclick = closeFactionActionModal;
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
    return;
  }

  frame.onload = () => {
    setTimeout(() => {
      connectStrategicMapFrame();
      setTimeout(() => {
        if (!strategicMapConnected()) {
          connectStrategicMapFrame();
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
  if (!panel || !info || !buttons) return;

  const me = state.players?.find(p => p.id === playerId) || null;
  const inAction = String(state.turn_phase).toLowerCase() === 'action';
  const isMine = state.current_player && me && state.current_player === me.name;
  const faction = me?.faction || '';

  buttons.innerHTML = '';
  panel.style.display = 'none';
  info.textContent = '';

  if (!inAction || !isMine) return;

  if (faction === 'aomen') {
    panel.style.display = 'block';
    info.textContent = '澳門可在行動階段發動一次賭徒耳語，請先選擇猜奇或猜偶。';
    const btn = document.createElement('button');
    btn.className = 'base-choice-btn';
    btn.textContent = '發動 賭徒耳語';
    btn.onclick = openGamblerGuessModal;
    buttons.appendChild(btn);
    return;
  }

  const ethnicRitualFactions = new Set(['dian_zhuang','zhuang','yi','bai','hani','dai','miao','tujia','dong','buyei','yao','li']);
  if (ethnicRitualFactions.has(faction)) {
    panel.style.display = 'block';
    info.textContent = '可在行動階段發動一次民族祭儀，請先猜奇偶。';
    const btn = document.createElement('button');
    btn.className = 'base-choice-btn';
    btn.textContent = '發動 民族祭儀';
    btn.onclick = openEthnicRitualGuessModal;
    buttons.appendChild(btn);
  }
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

  panel.style.display = inBaseSelection ? 'block' : 'none';
  if (!inBaseSelection) {
    pendingBaseSelectionLabel = null;
    choicesEl.innerHTML = '';
    info.textContent = '';
    return;
  }

  if (!choiceData) {
    pendingBaseSelectionLabel = null;
    info.textContent = '等待其他玩家選擇根據地';
    choicesEl.innerHTML = '';
    return;
  }

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
            <div class="player-status-name">${escapeHtml(player.name || '未命名玩家')}</div>
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
          <div class="player-status-stat"><span>移動</span><strong>${moves}</strong></div>
        </div>
      </article>`;
  }).join('');
}

async function render(state) {
  if (state.error) {
    alert(state.error);
  }
  await Promise.all([loadCardPresentationCatalog(), loadFactions()]);

  const me = state.players?.find(p => p.id === playerId) || null;
  const inBaseSelection = state.game_phase === 'base_selection';
  const showLobbyFactionPicker = !inBaseSelection && !ws;
  const factionPicker = document.getElementById('factionPicker');
  if (factionPicker) factionPicker.style.display = showLobbyFactionPicker ? 'block' : 'none';

  const detailFactionId = me?.faction || pendingFactionChoice || null;
  renderFactionDetails(inBaseSelection ? null : detailFactionId);
  await renderBuildSupport(state);
  renderFactionActionPanel(state);
  renderBaseSelection(state);
  renderEraAchievement(state);

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
    const phaseLabel = String(state.turn_phase || '').toLowerCase() === 'action' ? '行動' : String(state.turn_phase || '').toLowerCase() === 'event' ? '事件' : String(state.turn_phase || '').toLowerCase() === 'end' ? '結束' : state.turn_phase;
    const eraStatus = (state.active_era_details || []).map(item => {
      const remainText = item.remaining == null ? '持續中' : `剩餘 ${item.remaining} 回合`;
      return `<span class="hud-era-pill">${escapeHtml(item.name)}｜條件已達成｜${escapeHtml(remainText)}</span>`;
    }).join('');

    const marketModeLabel = state.market_mode === 'all_cards' ? '全部卡牌' : '53 張卡牌';
    hud.innerHTML = `
      <div class="hud-main-row">
        <span class="hud-chip hud-chip-primary">回合 ${state.turn}</span>
        <span class="hud-chip hud-chip-primary">${phaseLabel}階段</span>
        <span class="hud-chip">當前玩家 ${escapeHtml(state.current_player)}</span>
        <span class="hud-chip">手牌 ${myHand}</span>
        <span class="hud-chip hud-chip-resource">資金 ${myMoney}</span>
        <span class="hud-chip hud-chip-resource">宣傳 ${myPropaganda}</span>
        <span class="hud-chip">移動 ${myMoves}</span>
        <span class="hud-chip hud-chip-market">牌庫模式 ${marketModeLabel}</span>
        ${orgInfo}
      </div>
      ${eraStatus ? `<div class="hud-era-row">${eraStatus}</div>` : ''}
    `;

    const phaseActionMeta = document.getElementById('phaseActionMeta');
    const advanceBtn = document.getElementById('advanceStepBtn');
    const isMyTurn = !!(me && state.current_player === me.name);
    const stepLabel = phaseLabel === '事件' ? '結束事件階段' : phaseLabel === '行動' ? '結束行動階段' : phaseLabel === '結束' ? '結束回合' : '結束目前步驟';
    if (phaseActionMeta) {
      phaseActionMeta.textContent = isMyTurn ? `目前：${phaseLabel}｜下一步：${stepLabel}` : `目前：${phaseLabel}｜等待 ${state.current_player} 操作`;
    }
    if (advanceBtn) {
      advanceBtn.textContent = stepLabel;
      advanceBtn.disabled = !isMyTurn;
    }
  }

  // ✅ 地圖節點不在 render 中重建


  // Hand
  const handDiv = document.getElementById('hand');
  if (handDiv) {
    handDiv.innerHTML = '';
    const me = (state.players || []).find(p => p.id === playerId);
    if (me && me.hand) {
      me.hand.forEach((card, i) => {
        const colorName = (cardPresentation(card)?.color) || (/奧援/.test(card) ? '奧援' : '灰');
        const colorClass = cardColorClass(colorName);
        handDiv.innerHTML += `
          <div class='card hand-card ${colorClass}' onclick="selectCardDetail(${JSON.stringify(card)},'hand',false)" ondblclick="sendAction('play_card',{index:${i}})">
            ${renderCardFace(card, 'hand', false, true)}
          </div>`;
      });
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
      const canBuy = !isStatic;
      container.innerHTML += `
        <div class='card ${typeClass}${supportClass} ${colorClass}' onclick="selectCardDetail(${JSON.stringify(card)},'purchase',${isStatic})" ${canBuy ? `ondblclick="sendAction('buy_card',{index:${i}})"` : ''}>
          ${renderCardFace(card, 'purchase', isStatic, true)}
        </div>`;
    });
  }

  // Log
  renderPlayerStatusCards(state);
  const logTargets = [document.getElementById('log'), document.getElementById('logViewContent')].filter(Boolean);
  if (logTargets.length) {
    const entries = state.action_log || state.log || [];
    const html = entries.slice().reverse().map(entry => `<div>${entry}</div>`).join('');
    logTargets.forEach(target => {
      target.innerHTML = html;
    });
  }

}

document.addEventListener('DOMContentLoaded', initLobbyControls);
