let ws = null;
let gameId = null;
let playerId = null;

async function createRoom() {
  const res = await fetch('/create', {method: 'POST'});
  const data = await res.json();
  gameId = data.game_id;
  document.getElementById('roomInfo').innerText = 'Room ID: ' + gameId;
}

async function joinRoom() {
  gameId = document.getElementById('roomId').value;
  const name = document.getElementById('playerName').value;

  const res = await fetch('/join', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({game_id: gameId, name})
  });

  const data = await res.json();
  if (data.error) {
    alert(data.error);
    return;
  }

  playerId = data.player_id;
  connect();
}

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws/${gameId}/${playerId}`);

  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);
    render(state);
  };

  document.getElementById('lobby').style.display = 'none';
  document.getElementById('gameUI').style.display = 'block';
}

async function startGame() {
  await fetch('/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({game_id: gameId, player_id: playerId})
  });
}

function sendAction(action, payload = {}) {
  ws.send(JSON.stringify({action, ...payload}));
}

function render(state) {
  if (state.error) {
    alert(state.error);
    return;
  }

  document.getElementById('status').innerHTML =
    `<strong>Turn:</strong> ${state.turn} | ` +
    `<strong>Phase:</strong> ${state.turn_phase} | ` +
    `<strong>Current:</strong> ${state.current_player}` +
    (state.winner ? ` | 🏆 ${state.winner}` : '');

  // Map
  const mapDiv = document.getElementById('map');
  mapDiv.innerHTML = '';
  Object.keys(state.map.towns).forEach(town => {
    const info = state.map.towns[town]
      .map(c => `${c.player}(${c.count})`).join(', ');
    mapDiv.innerHTML += `<div class='card' onclick="sendAction('build',{town:'${town}'})">${town}: ${info}</div>`;
  });

  // Purchase
  const purchaseDiv = document.getElementById('purchase');
  purchaseDiv.innerHTML = '';
  (state.purchase_area || []).forEach((card, i) => {
    purchaseDiv.innerHTML += `<span class='card' onclick="sendAction('buy_card',{index:${i}})">${card}</span>`;
  });

  // Hand
  const handDiv = document.getElementById('hand');
  handDiv.innerHTML = '';
  const me = state.players.find(p => p.name === state.current_player);
  if (me && me.hand) {
    me.hand.forEach((card, i) => {
      handDiv.innerHTML += `<span class='card' onclick="sendAction('play_card',{index:${i}})">${card}</span>`;
    });
  }

  // Log
  const logDiv = document.getElementById('log');
  logDiv.innerHTML = '';
  (state.log || []).slice().reverse().forEach(entry => {
    logDiv.innerHTML += `<div>${entry}</div>`;
  });
}
