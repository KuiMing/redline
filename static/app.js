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
let selectedCardDetail = null;
let cardPresentationCatalog = null;

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
  if (roomInput) roomInput.value = gameId;
  await loadFactions();
  alert("ROOM CREATED: " + gameId);
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

  if (factionId === 'uyghur_family') return '維吾爾';
  if (factionId === 'tibet_family') return '西藏';
  return factionId;
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
  const colorClass = cardColorClass(info.color || (isSupport ? '奧援' : ''));
  const typeLabel = zone === 'hand' ? '手牌' : (isStatic ? '常設購買區' : '隨機購買區');
  const headerMeta = [info.kind, info.strength, info.cost_text].filter(Boolean).join('｜');
  const effectLines = splitEffectLines(info.effect_text || (isSupport ? '奧援卡，依區域主導者判定 I・II・III 級效果。' : '（暫無資料）'));
  const badgeItems = [];
  if (info.resource_text) badgeItems.push(`資源 ${info.resource_text}`);
  if (info.position_text) badgeItems.push(info.position_text);
  else badgeItems.push(typeLabel);
  const meaning = info.meaning_text ? `<div class="card-meaning">${escapeHtml(info.meaning_text)}</div>` : '';
  const count = info.count_text ? `<div class="card-count">剩 ${escapeHtml(info.count_text)}</div>` : '';
  return `
    <div class="card-face ${colorClass}${compact ? ' compact' : ''}">
      <div class="card-face-top">
        <div class="purchase-card-title">${escapeHtml(cardName)}</div>
        ${count}
      </div>
      <div class="card-face-meta-row">${escapeHtml(headerMeta || (isSupport ? '奧援｜特殊' : typeLabel))}</div>
      <div class="purchase-card-body card-effect-block">
        ${effectLines.slice(0, compact ? 2 : 4).map(line => `<div>${escapeHtml(line)}</div>`).join('')}
      </div>
      ${meaning}
      ${renderBadgeList(badgeItems)}
    </div>`;
}

function describeCard(cardName, zone, isStatic = false) {
  const info = cardPresentation(cardName);
  const supportHint = /奧援/.test(cardName) ? '奧援卡，會依區域主導者判定 I・II・III 級效果。' : '';
  const zoneHint = zone === 'hand' ? '這是你目前手牌，可直接打出。' : (isStatic ? '這是常設購買區卡牌，不屬於隨機購買區。' : '這是隨機購買區卡牌。');
  if (!info) {
    return `${cardName}\n\n區域：${zone === 'hand' ? '手牌' : (isStatic ? '常設購買區' : '隨機購買區')}\n${zoneHint}${supportHint ? `\n${supportHint}` : ''}`;
  }
  return `${info.name}\n\n顏色：${info.color || '未知'}\n種類：${info.kind || '未知'}\n強度：${info.strength || '未知'}\n購買費用：${info.cost_text || '未知'}\n提供資源：${info.resource_text || '未知'}\n位置：${zone === 'hand' ? '手牌' : (isStatic ? '常設購買區' : '隨機購買區')}\n張數：${info.count_text || '未知'}\n\n效果：${info.effect_text || '（暫無資料）'}\n\n意涵：${info.meaning_text || '（暫無資料）'}${supportHint ? `\n\n${supportHint}` : ''}`;
}

function renderSelectedCardDetail() {
  const detail = document.getElementById('cardDetail');
  if (!detail) return;
  if (!selectedCardDetail) {
    detail.innerHTML = '<div class="card-detail-placeholder">點選購買區或手牌卡牌後，可在此查看詳細資訊。</div>';
    return;
  }
  const info = cardPresentation(selectedCardDetail.name) || {};
  detail.innerHTML = `
    <div class="card-detail-shell">
      ${renderCardFace(selectedCardDetail.name, selectedCardDetail.zone, selectedCardDetail.isStatic, false)}
      <div class="card-detail-note">${escapeHtml(describeCard(selectedCardDetail.name, selectedCardDetail.zone, selectedCardDetail.isStatic))}</div>
    </div>`;
}

function selectCardDetail(name, zone, isStatic = false) {
  selectedCardDetail = { name, zone, isStatic };
  renderSelectedCardDetail();
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
  await renderFactionPicker();
}

async function startGame() {
  const res = await fetch('/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({game_id: gameId, player_id: playerId})
  });

  const data = await res.json();
  if (data.error) {
    alert(data.error);
    return;
  }

  connect();
}

// Abstract map removed — replaced by Leaflet


function connect() {
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

function closeFactionActionModal() {
  activeFactionActionModal = null;
  const overlay = document.getElementById('factionActionModal');
  if (overlay) overlay.style.display = 'none';
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

async function render(state) {
  if (state.error) {
    alert(state.error);
  }
  await loadCardPresentationCatalog();

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

  // HUD
  const hud = document.getElementById('hud');
  if (hud) {
    let orgInfo = '';
    state.players.forEach(p => {
      const total = Object.values(p.orgs || {}).reduce((a,b)=>a+b,0);
      orgInfo += `${p.name}: ${total} | `;
    });

    const me = state.players.find(p => p.id === playerId);
    const myMoney = me?.resources?.money ?? 0;
    const myPropaganda = me?.resources?.propaganda ?? 0;
    const myMoves = me?.moves_left ?? 0;
    const myHand = me?.hand?.length ?? 0;
    const phaseLabel = String(state.turn_phase || '').toLowerCase() === 'action' ? '行動' : String(state.turn_phase || '').toLowerCase() === 'event' ? '事件' : String(state.turn_phase || '').toLowerCase() === 'end' ? '結束' : state.turn_phase;

    hud.innerHTML = `
      回合 ${state.turn}
      | 階段 ${phaseLabel}
      | 當前玩家 ${state.current_player}
      | 手牌 ${myHand}
      | 資金 ${myMoney}
      | 宣傳 ${myPropaganda}
      | 移動 ${myMoves}
      | ${orgInfo}
    `;
  }

  // ✅ 地圖節點不在 render 中重建


  // Hand
  const handDiv = document.getElementById('hand');
  if (handDiv) {
    handDiv.innerHTML = '';
    const me = state.players.find(p => p.id === playerId);
    if (me && me.hand) {
      me.hand.forEach((card, i) => {
        handDiv.innerHTML += `
          <div class='card hand-card' onclick="selectCardDetail(${JSON.stringify(card)},'hand',false)" ondblclick="sendAction('play_card',{index:${i}})">
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
      const canBuy = !isStatic;
      container.innerHTML += `
        <div class='card ${typeClass}${supportClass}' onclick="selectCardDetail(${JSON.stringify(card)},'purchase',${isStatic})" ${canBuy ? `ondblclick="sendAction('buy_card',{index:${i}})"` : ''}>
          ${renderCardFace(card, 'purchase', isStatic, true)}
        </div>`;
    });
  }

  // Log
  const logDiv = document.getElementById('log');
  if (logDiv) {
    logDiv.innerHTML = '';
    const entries = state.action_log || state.log || [];
    entries.slice().reverse().forEach(entry => {
      logDiv.innerHTML += `<div>${entry}</div>`;
    });
  }

  renderSelectedCardDetail();

  // Active Eras
  const eraDiv = document.getElementById('eras');
  if (eraDiv) {
    eraDiv.innerHTML = '';
    if (state.active_eras && state.active_eras.length > 0) {
      state.active_eras.forEach(e => {
        eraDiv.innerHTML += `<div class=\"card\">${e}</div>`;
      });
    } else {
      eraDiv.innerHTML = `<div class=\"card\">無</div>`;
    }
  }
}
