// Executes the real refreshRouteHighlights()/highlightConnectedRoutes() from static/leaflet_game_map_logic.js
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
  'canActFromTown', 'movementOptionsForTown', 'movementProjectionAuthoritativeForTown', 'projectedRailRouteEdges',
  'highlightConnectedRoutes', 'refreshRouteHighlights'];

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const mkLayer = route => ({ __redlineRoute: route, style: null, setStyle(s) { this.style = s; } });
const railLayers = input.rail.map(([source, target]) => mkLayer({ source, target }));
const roadLayers = (input.road || []).map(([source, target]) => mkLayer({ source, target }));
const ctx = {
  lastGameState: input.state,
  mapPlayerId: input.viewer,
  map: { getZoom: () => 10 },
  roadLayer: { eachLayer: fn => roadLayers.forEach(fn) },
  selectedTown: input.town,
  routePreviewTarget: input.preview || null,
  pendingMoveTarget: input.pending || null,
  railLayer: { eachLayer: fn => railLayers.forEach(fn) },
  roadWeight: () => 2, railWeight: () => 2, railDashArray: () => null,
};
vm.createContext(ctx);
vm.runInContext(names.map(grab).join('\n') +
  `\nthis.run = refreshRouteHighlights;`, ctx);
ctx.run();
// refreshRouteHighlights first dims every route (opacity < 0.5), then lights the chosen ones.
const litOf = layers => layers.filter(l => l.style && l.style.opacity >= 0.5).map(l => [l.__redlineRoute.source, l.__redlineRoute.target].sort());
process.stdout.write(JSON.stringify({ rail: litOf(railLayers), road: litOf(roadLayers) }));
