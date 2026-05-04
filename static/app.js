let ws = null;
let gameId = null;
let playerId = null;
let previousEras = [];

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

async function createRoom() {
  const res = await fetch('/create', { method: 'POST' });
  const data = await res.json();
  gameId = data.game_id;
  playerId = data.host_id;
  const roomInput = document.getElementById('roomId');
  if (roomInput) roomInput.value = gameId;
  alert("ROOM CREATED: " + gameId);
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

function renderBaseSelection(state) {
  const panel = document.getElementById('baseSelectionPanel');
  const info = document.getElementById('baseSelectionInfo');
  const choicesEl = document.getElementById('baseSelectionChoices');
  if (!panel || !info || !choicesEl) return;

  const choices = state.pending_base_choices?.[playerId] || [];
  const inBaseSelection = state.game_phase === 'base_selection';

  panel.style.display = inBaseSelection ? 'block' : 'none';
  if (!inBaseSelection) {
    choicesEl.innerHTML = '';
    info.textContent = '';
    return;
  }

  info.textContent = choices.length
    ? '請選擇你的根據地'
    : '等待其他玩家選擇根據地';

  choicesEl.innerHTML = '';
  choices.forEach(choice => {
    const btn = document.createElement('button');
    btn.className = 'base-choice-btn';
    btn.textContent = choice;
    btn.onclick = () => sendAction('set_base', { town: choice });
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
