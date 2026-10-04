// Executes the real highlightConnectedRoutes() from static/leaflet_game_map_logic.js
// against a server-produced state and reports which rail edges end up highlighted.
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/leaflet_game_map_logic.js', 'utf8');
const grab = name => {
  const start = source.indexOf(`function ${name}(`);
  if (start < 0) throw new Error(`missing ${name}`);
  const next = source.indexOf('\n}\n', start);
  return source.slice(start, next + 3);
};
const names = ['currentPlayerName', 'currentPlayerFaction', 'currentPlayerState', 'sharedAccessForTown', 'playerOwnsTown', 'playerHasSharedAccessToTown',
  'canActFromTown', 'movementOptionsForTown', 'movementProjectionAuthoritativeForTown', 'highlightConnectedRoutes'];

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const mkLayer = route => ({ __redlineRoute: route, style: null, setStyle(s) { this.style = s; } });
const railLayers = input.rail.map(([source, target]) => mkLayer({ source, target }));
const ctx = {
  lastGameState: input.state,
  mapPlayerId: input.viewer,
  map: { getZoom: () => 10 },
  roadLayer: { eachLayer() {} },
  railLayer: { eachLayer: fn => railLayers.forEach(fn) },
  roadWeight: () => 2, railWeight: () => 2, railDashArray: () => null,
};
vm.createContext(ctx);
vm.runInContext(names.map(grab).join('\n') +
  `\nthis.run = highlightConnectedRoutes;`, ctx);
ctx.run(input.town);
const lit = railLayers.filter(l => l.style).map(l => [l.__redlineRoute.source, l.__redlineRoute.target].sort());
process.stdout.write(JSON.stringify(lit));
