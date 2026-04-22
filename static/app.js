async function createGame() {
  await fetch('/create', { method: 'POST' });
  refreshState();
}

async function refreshState() {
  const res = await fetch('/state');
  const state = await res.json();
  renderState(state);
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
