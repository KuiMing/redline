async function createGame() {
  await fetch('/create', { method: 'POST' });
  refreshState();
}

async function refreshState() {
  const res = await fetch('/state');
  const state = await res.json();
  renderState(state);
}

async function advanceTurn() {
  const res = await fetch('/advance_turn', { method: 'POST' });
  const data = await res.json();
  renderState(data.state);
}

async function playCard(index) {
  const res = await fetch('/play_card', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ index })
  });
  const data = await res.json();
  renderState(data.state);
}

async function buyCard(index) {
  const res = await fetch('/buy_card', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ index })
  });
  const data = await res.json();
  renderState(data.state);
}

async function buildOrg(town) {
  const res = await fetch('/build', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ town })
  });
  const data = await res.json();
  renderState(data.state);
}

async function setMoveFrom(town) {
  document.getElementById('moveFrom').value = town;

  const res = await fetch(`/legal_moves?from_town=${town}`);
  const data = await res.json();

  const container = document.getElementById('legalMoves');
  container.innerHTML = '<strong>Legal Moves:</strong><br>';

  if (data.road) {
    data.road.forEach(t => {
      container.innerHTML += `<span class="card" onclick="setMoveTo('${t}')">🟡 ${t}</span>`;
    });
  }

  if (data.rail) {
    data.rail.forEach(t => {
      container.innerHTML += `<span class="card" onclick="setMoveTo('${t}')">⚫ ${t}</span>`;
    });
  }
}

function setMoveTo(town) {
  document.getElementById('moveTo').value = town;
}

function renderState(state) {
  const container = document.getElementById('game');
  container.innerHTML = '';

  if (state.error) {
    container.innerHTML = `<p>${state.error}</p>`;
    return;
  }

  container.innerHTML += `<div class='section'><strong>Turn:</strong> ${state.turn}</div>`;
  container.innerHTML += `<div class='section'><strong>Game Phase:</strong> ${state.game_phase}</div>`;
  container.innerHTML += `<div class='section'><strong>Turn Phase:</strong> ${state.turn_phase}</div>`;
  container.innerHTML += `<div class='section'><strong>Current Player:</strong> ${state.current_player}</div>`;

  if (state.current_event) {
    container.innerHTML += `<div class='section'><strong>Current Event:</strong> ${state.current_event.name || state.current_event}</div>`;
  }

  if (state.active_eras && state.active_eras.length > 0) {
    container.innerHTML += `<div class='section'><strong>Active Eras:</strong> ${state.active_eras.join(', ')}</div>`;
  }

  container.innerHTML += `<h2>Players</h2>`;

  // Purchase Area
  if (state.purchase_area && state.purchase_area.length > 0) {
    container.innerHTML += `<div class='section'><h2>Purchase Area</h2>`;
    state.purchase_area.forEach((card, index) => {
      container.innerHTML += `<span class='card' onclick='buyCard(${index})'>${card}</span>`;
    });
    container.innerHTML += `</div>`;
  }

  // Map Control View
  if (state.map && state.map.towns) {
    container.innerHTML += `<div class='section'><h2>Map Control</h2>`;
    Object.keys(state.map.towns).forEach(town => {
      const control = state.map.towns[town]
        .map(c => `${c.player}(${c.count})`)
        .join(', ');
      container.innerHTML += `<div><strong>${town}</strong>: ${control}</div>`;
    });
    container.innerHTML += `</div>`;
  }

  state.players.forEach(p => {
    const div = document.createElement('div');
    div.className = 'player';

    div.innerHTML = `
      <strong>${p.name}</strong><br>
      Faction: ${p.faction}<br>
      Resources: 💰 ${p.resources?.money ?? 0} | 📣 ${p.resources?.propaganda ?? 0}<br>
      Total Orgs: ${p.total_orgs}
    `;

    if (p.hand && p.hand.length > 0) {
      div.innerHTML += `<div><strong>Hand:</strong><br>`;
      p.hand.forEach((card, index) => {
        div.innerHTML += `<span class='card' onclick='playCard(${index})'>${card}</span>`;
      });
      div.innerHTML += `</div>`;
    }

    container.appendChild(div);
  });
}
