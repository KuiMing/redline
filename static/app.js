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
        if (window.initializeStrategicMapWhenVisible) {
          window.initializeStrategicMapWhenVisible();
        }
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
  if (!ws) return;
  ws.send(JSON.stringify({action, ...payload}));
}

async function ensureStrategicMapMounted() {
  const root = document.getElementById('strategicMapRoot');
  if (!root || root.dataset.mounted === '1') return;

  const fragmentRes = await fetch('/static/leaflet_game_map_embed_fragment.html');
  root.innerHTML = await fragmentRes.text();

  const script = document.createElement('script');
  script.addEventListener('load', () => {
    if (window.connectGameMap && gameId && playerId) {
      window.connectGameMap({ gameId, playerId });
    }
  }, { once: true });
  script.addEventListener('error', () => {
    console.error('Failed to load /static/leaflet_game_map_logic.js');
  }, { once: true });
  script.src = '/static/leaflet_game_map_logic.js';
  script.dataset.redlineMapLogic = '1';
  root.appendChild(script);

  root.dataset.mounted = '1';
}

function syncStrategicMap(state) {
  if (window.applyGameStateToMap) {
    window.applyGameStateToMap(state);
  }
}

function render(state) {
  if (state.error) {
    alert(state.error);
    return;
  }

  // HUD
  const hud = document.getElementById('hud');
  if (hud) {
    let orgInfo = '';
    state.players.forEach(p => {
      const total = Object.values(p.orgs || {}).reduce((a,b)=>a+b,0);
      orgInfo += `${p.name.toUpperCase()}: ${total} | `;
    });

    hud.innerHTML = `
      TURN ${state.turn}
      | PHASE ${state.turn_phase}
      | ACTIVE ${state.current_player.toUpperCase()}
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
    (state.log || []).slice().reverse().forEach(entry => {
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
