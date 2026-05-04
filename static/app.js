let ws = null;
let gameId = null;
let playerId = null;
let previousEras = [];
let availableFactionCategories = [];
let pendingFactionCategory = null;

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
  const res = await fetch('/choose-faction', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ game_id: gameId, player_id: playerId, faction_id: factionId })
  });
  const data = await res.json();
  if (data.error) {
    alert(data.error);
    return;
  }
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

async function renderFactionPicker() {
  const panel = document.getElementById('factionPicker');
  const info = document.getElementById('factionPickerInfo');
  const list = document.getElementById('factionList');
  const variants = document.getElementById('factionVariantList');
  if (!panel || !info || !list || !variants || !gameId || !playerId) return;

  const [lobbyRes] = await Promise.all([
    fetch(`/lobby/${gameId}`).then(r => r.json()),
    loadFactions(),
  ]);

  panel.style.display = 'block';
  const chosen = lobbyRes.factions || {};
  const mine = chosen[playerId] || null;
  info.textContent = mine ? `已選陣營：${mine}` : '請先選擇你的陣營';

  list.innerHTML = '';
  variants.innerHTML = '';
  variants.style.display = 'none';

  const takenCategories = new Set(
    Object.entries(chosen)
      .filter(([pid]) => pid !== playerId)
      .map(([, fid]) => factionCategoryOf(fid))
  );

  availableFactionCategories.forEach(category => {
    const btn = document.createElement('button');
    btn.className = 'faction-choice-btn faction-primary-btn';
    btn.textContent = category.label;
    btn.disabled = takenCategories.has(category.id);
    btn.onclick = () => {
      if (category.mode === 'direct') {
        chooseFaction(category.options[0].id);
        return;
      }
      pendingFactionCategory = category;
      variants.innerHTML = '';
      variants.style.display = 'flex';
      category.options.forEach(opt => {
        const vbtn = document.createElement('button');
        vbtn.className = 'faction-choice-btn faction-variant-btn';
        vbtn.textContent = `${opt.variant || opt.name || opt.id}`;
        vbtn.onclick = () => chooseFaction(opt.id);
        variants.appendChild(vbtn);
      });
    };
    list.appendChild(btn);
  });
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

  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);
    window.lastGameState = state;
    render(state);
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

let pendingBaseSelectionLabel = null;

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

function render(state) {
  if (state.error) {
    alert(state.error);
  }

  renderBaseSelection(state);

  // HUD
  const hud = document.getElementById('hud');
  if (hud) {
    let orgInfo = '';
    state.players.forEach(p => {
      const total = Object.values(p.orgs || {}).reduce((a,b)=>a+b,0);
      orgInfo += `${p.name.toUpperCase()}: ${total} | `;
    });

    const me = state.players.find(p => p.id === playerId);
    const myMoney = me?.resources?.money ?? 0;
    const myPropaganda = me?.resources?.propaganda ?? 0;
    const myMoves = me?.moves_left ?? 0;
    const myHand = me?.hand?.length ?? 0;

    hud.innerHTML = `
      TURN ${state.turn}
      | PHASE ${state.turn_phase}
      | ACTIVE ${state.current_player.toUpperCase()}
      | HAND ${myHand}
      | MONEY ${myMoney}
      | PROP ${myPropaganda}
      | MOVES ${myMoves}
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
        handDiv.innerHTML += `<div class='card' onclick="sendAction('play_card',{index:${i}})">${card}</div>`;
      });
    }
  }

  // Purchase
  const purchaseDiv = document.getElementById('purchase');
  if (purchaseDiv) {
    purchaseDiv.innerHTML = '';
    (state.purchase_area || []).forEach((card, i) => {
      purchaseDiv.innerHTML += `<div class='card' onclick="sendAction('buy_card',{index:${i}})">${card}</div>`;
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

  // Active Eras
  const eraDiv = document.getElementById('eras');
  if (eraDiv) {
    eraDiv.innerHTML = '';
    if (state.active_eras && state.active_eras.length > 0) {
      state.active_eras.forEach(e => {
        eraDiv.innerHTML += `<div class=\"card\">${e}</div>`;
      });
    } else {
      eraDiv.innerHTML = `<div class=\"card\">NONE</div>`;
    }
  }
}
