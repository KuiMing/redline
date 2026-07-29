let MAP_DATA = null;
let GEO_COORDS = null;

let rulers = [];
let camps = [];
let types = [];

const palette = {
  "臺灣":"#3fb6ff","紅軍":"#f04f56","東洋":"#a78bfa","北國":"#67e8f9","南洋":"#22c55e","印度":"#f59e0b","天方":"#fb7185",
  "香港":"#f472b6","藏國":"#eab308","維吾爾":"#34d399","哈薩克":"#60a5fa","蒙古":"#c084fc","滿洲":"#93c5fd","反賊":"#f97316"
};
const typePalette = {"軍火庫":"#ffcf5a","機場":"#93c5fd","default":"#cbd5e1"};

function addOptions(id, arr) {
  const sel = document.getElementById(id);
  if (!sel) return;
  arr.forEach(v => {
    const o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o);
  });
}

let towns = [];
let byName = new Map();
let links = [];

function canonicalEdgeKey(a,b,type) {
  return [type, ...[a,b].sort()].join('::');
}

function initializeCanonicalMapData(mapData, geoCoordinates) {
  MAP_DATA = mapData;
  GEO_COORDS = geoCoordinates;
  rulers = [...new Set(Object.values(MAP_DATA.towns).flatMap(t=>t.ruler||[]))].sort();
  camps = [...new Set(Object.values(MAP_DATA.towns).flatMap(t=>t.camp||[]))].sort();
  types = [...new Set(Object.values(MAP_DATA.towns).map(t=>t.type).filter(Boolean))].sort();
  towns = Object.entries(MAP_DATA.towns).map(([name, raw]) => {
    const c = GEO_COORDS[name];
    return { name, ...raw, lon:c[0], lat:c[1] };
  });
  byName = new Map(towns.map(t=>[t.name, t]));
  const linkMap = new Map();
  for (const [name,t] of Object.entries(MAP_DATA.towns)) {
    for (const n of (t.road||[])) if (MAP_DATA.towns[n]) linkMap.set(canonicalEdgeKey(name,n,'road'), {source:name,target:n,type:'road'});
    for (const n of (t.rail||[])) if (MAP_DATA.towns[n]) linkMap.set(canonicalEdgeKey(name,n,'rail'), {source:name,target:n,type:'rail'});
  }
  links = [...linkMap.values()];
  currentVisible = towns.map(t=>t.name);
}

let map = null;
let cartoLight = null;
let cartoDark = null;
let currentBasemap = 'cartoLight';

function initEmbeddedMap() {
  if (map || !document.getElementById('map')) return;
  map = L.map('map', {
    preferCanvas:true,
    worldCopyJump:false,
    zoomControl: true,
    fadeAnimation: false,
    zoomAnimation: false,
    markerZoomAnimation: false,
  });
  cartoLight = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    maxZoom:19,
    attribution:'&copy; OpenStreetMap contributors &copy; CARTO'
  });
  cartoDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom:19,
    attribution:'&copy; OpenStreetMap contributors &copy; CARTO'
  });
  cartoLight.addTo(map);
  roadLayer = L.layerGroup().addTo(map);
  railLayer = L.layerGroup().addTo(map);
  markerLayer = L.layerGroup().addTo(map);
  highlightLayer = L.layerGroup().addTo(map);
}

let roadLayer = null;
let railLayer = null;
let markerLayer = null;
let highlightLayer = null;
let labelMode = 'auto', showRoad = true, showRail = true;
let currentMarkers = new Map();
let currentVisible = towns.map(t=>t.name);
let lastGameState = null;
let selectedTown = null;

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
function zoomProgress(z = map.getZoom()) { return clamp((z - 2) / 6, 0, 1); }
function roadWeight(z = map.getZoom()) { return 1.6 + zoomProgress(z) * 5.2; }
function railWeight(z = map.getZoom()) { return 1.8 + zoomProgress(z) * 5.6; }
function markerRadius(z = map.getZoom()) { return 3.2 + zoomProgress(z) * 8.8; }
function markerStroke(z = map.getZoom()) { return 0.9 + zoomProgress(z) * 1.8; }
function railDashArray(z = map.getZoom()) {
  const t = zoomProgress(z);
  const dash = 4 + t * 8;
  const gap = 3 + t * 6;
  return `${dash.toFixed(1)} ${gap.toFixed(1)}`;
}

function colorFor(t) {
  if (t.type) return typePalette[t.type] || typePalette.default;
  return palette[(t.ruler||[])[0]] || '#cbd5e1';
}
function filters() {
  return {
    q: document.getElementById('searchBox').value.trim().toLowerCase(),
    ruler: document.getElementById('rulerFilter').value,
    camp: document.getElementById('campFilter').value,
    type: document.getElementById('typeFilter').value
  };
}
function townMatches(t, f=filters()) {
  return (!f.q || t.name.toLowerCase().includes(f.q)) &&
         (!f.ruler || (t.ruler||[]).includes(f.ruler)) &&
         (!f.camp || (t.camp||[]).includes(f.camp)) &&
         (!f.type || t.type === f.type);
}

function popupHtml(t) {
  const roads = (t.road||[]).map(n=>`<span class="pill">${n}</span>`).join(' ') || '無';
  const rails = (t.rail||[]).map(n=>`<span class="pill">${n}</span>`).join(' ') || '無';
  return `
    <div class="name">${t.name}</div>
    <div>座標：<code>${t.lon.toFixed(3)}, ${t.lat.toFixed(3)}</code></div>
    <div>統治者：${(t.ruler||[]).map(x=>`<span class="pill">${x}</span>`).join(' ') || '無'}</div>
    <div>陣營：${(t.camp||[]).map(x=>`<span class="pill">${x}</span>`).join(' ') || '無'}</div>
    <div>城鎮類型：${t.type ? `<span class="pill">${t.type}</span>` : '一般城鎮'}</div>
    <hr style="border-color:#2b385d;border-style:solid;border-width:1px 0 0;margin:10px 0;">
    <div>一般道路：${roads}</div>
    <div>鐵路：${rails}</div>`;
}

function updateInfoPanel(name) {
  const t = byName.get(name);
  if (!t) return;
  document.getElementById('info').innerHTML = popupHtml(t);
}

function shouldShowLabels() {
  return labelMode === 'on' || (labelMode === 'auto' && map.getZoom() >= 5);
}

function clearLayers() {
  roadLayer.clearLayers();
  railLayer.clearLayers();
  markerLayer.clearLayers();
  highlightLayer.clearLayers();
  currentMarkers = new Map();
}

function currentPlayerName() {
  return lastGameState && lastGameState.current_player ? lastGameState.current_player : null;
}

function playerOwnsTown(townName) {
  if (!lastGameState || !lastGameState.map || !lastGameState.map.towns) return false;
  const entries = lastGameState.map.towns[townName] || [];
  return entries.some(entry => entry.player === currentPlayerName() && (entry.count || 0) > 0);
}

function movementOptionsForTown(townName) {
  if (!lastGameState || !townName) return { road: [], rail: [] };
  const town = MAP_DATA.towns[townName];
  if (!town) return { road: [], rail: [] };

  // 第二版：只允許 current player 自己有組織的城鎮顯示可移動鄰接點
  if (!playerOwnsTown(townName)) return { road: [], rail: [] };

  return {
    road: (town.road || []).filter(n => MAP_DATA.towns[n]),
    rail: railOptionsWithinThree(townName)
  };
}

function railOptionsWithinThree(originTown) {
  const visited = new Set([originTown]);
  const queue = [[originTown, 0]];
  const reachable = new Set();

  while (queue.length) {
    const [townName, distance] = queue.shift();
    if (distance >= 3) continue;
    const town = MAP_DATA.towns[townName] || {};
    for (const nextTown of (town.rail || [])) {
      if (!MAP_DATA.towns[nextTown]) continue;
      reachable.add(nextTown);
      if (visited.has(nextTown)) continue;
      visited.add(nextTown);
      queue.push([nextTown, distance + 1]);
    }
  }

  reachable.delete(originTown);
  return Array.from(reachable);
}

function renderMovementHighlights(townName) {
  highlightLayer.clearLayers();
  selectedTown = townName;
  if (!townName) return false;

  const opts = movementOptionsForTown(townName);
  const origin = byName.get(townName);
  if (!origin) return false;

  const originMarker = currentMarkers.get(townName);
  if (originMarker) {
    const selectable = playerOwnsTown(townName);
    originMarker.setStyle({ color: selectable ? '#ffffff' : '#64748b', weight: 4, fillOpacity: 1, radius: Math.max(10, markerRadius(map.getZoom()) + 2) });
  }

  if (!playerOwnsTown(townName)) {
    return false;
  }

  let highlightCount = 0;

  roadLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ color:'#d8a04a', opacity:0.12, weight:Math.max(1.5, roadWeight(map.getZoom()) - 1) });
  });
  railLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ color:'#ef4444', opacity:0.15, weight:Math.max(2, railWeight(map.getZoom()) - 1), dashArray: railDashArray(map.getZoom()) });
  });
  markerLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ opacity:1, fillOpacity:0.12, weight: markerStroke(map.getZoom()) });
  });

  for (const toName of opts.road) {
    const target = byName.get(toName);
    if (!target) continue;
    L.polyline([[origin.lat, origin.lon], [target.lat, target.lon]], {
      color: '#ffd166',
      weight: 4,
      opacity: 0.95
    }).addTo(highlightLayer);
    highlightCount += 1;

    const marker = currentMarkers.get(toName);
    if (marker) marker.setStyle({ color: '#ffd166', weight: 4, fillOpacity: 0.95, radius: Math.max(9, markerRadius(map.getZoom()) + 1) });
  }

  for (const toName of opts.rail) {
    const target = byName.get(toName);
    if (!target) continue;
    L.polyline([[origin.lat, origin.lon], [target.lat, target.lon]], {
      color: '#7dd3fc',
      weight: 5,
      opacity: 0.95,
      dashArray: '10 6'
    }).addTo(highlightLayer);
    highlightCount += 1;

    const marker = currentMarkers.get(toName);
    if (marker) marker.setStyle({ color: '#7dd3fc', weight: 4, fillOpacity: 0.98, radius: Math.max(9, markerRadius(map.getZoom()) + 1) });
  }

  focusSelectedTown(townName);
  return highlightCount > 0;
}

function updateDynamicStyles() {
  const z = map.getZoom();
  roadLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ weight: roadWeight(z), opacity: 0.82 });
  });
  railLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ color: '#ef4444', weight: railWeight(z), opacity: 0.9, dashArray: railDashArray(z), lineCap: 'round' });
  });
  markerLayer.eachLayer(layer => {
    if (layer.setRadius) layer.setRadius(markerRadius(z));
    if (layer.setStyle) layer.setStyle({ weight: markerStroke(z) });
    if (layer.getTooltip && layer.getTooltip()) {
      layer.getTooltip().options.offset = [0, -(markerRadius(z) + 4)];
    }
  });
}

function renderMap() {
  clearLayers();
  const f = filters();
  const visibleTowns = towns.filter(t => townMatches(t, f));
  currentVisible = visibleTowns.map(t => t.name);
  const visibleSet = new Set(currentVisible);

  for (const link of links) {
    if (!visibleSet.has(link.source) || !visibleSet.has(link.target)) continue;
    const a = byName.get(link.source), b = byName.get(link.target);
    const latlngs = [[a.lat, a.lon], [b.lat, b.lon]];
    const style = link.type === 'road'
      ? { color:'#d8a04a', weight:roadWeight(), opacity:0.82 }
      : { color:'#ef4444', weight:railWeight(), opacity:0.9, dashArray: railDashArray(), lineCap:'round' };
    const poly = L.polyline(latlngs, style).bindPopup(`${link.type.toUpperCase()}：${link.source} ↔ ${link.target}`);
    if (link.type === 'road' && showRoad) poly.addTo(roadLayer);
    if (link.type === 'rail' && showRail) poly.addTo(railLayer);
  }

  visibleTowns.forEach(t => {
    const marker = L.circleMarker([t.lat, t.lon], {
      radius: markerRadius(),
      color:'#07111f', weight:markerStroke(),
      fillColor: colorFor(t), fillOpacity:0.95
    }).addTo(markerLayer);
    marker.bindPopup(popupHtml(t), { maxWidth:380 });
    marker.on('click', () => {
      updateInfoPanel(t.name);
      renderMap();
      applyGameStateToMap(lastGameState);
      const didHighlight = renderMovementHighlights(t.name);
      window.__lastSelectedTown = t.name;
      window.__lastHighlightSuccess = didHighlight;
    });
    currentMarkers.set(t.name, marker);
    if (shouldShowLabels()) marker.bindTooltip(t.name, { permanent:true, direction:'top', className:'town-label', offset:[0, -(markerRadius() + 4)] });
  });

  updateDynamicStyles();
  if (selectedTown) {
    renderMovementHighlights(selectedTown);
  }
}

function fitVisible() {
  const pts = currentVisible.map(n => byName.get(n)).filter(Boolean).map(t => [t.lat, t.lon]);
  if (!pts.length) return;
  map.fitBounds(pts, { padding:[30,30] });
}

function fitAll() {
  const pts = towns.map(t => [t.lat, t.lon]);
  if (!pts.length) return;
  map.fitBounds(pts, { padding:[30,30] });
}

function focusAsia() {
  map.fitBounds([[-5, 68], [55, 145]], { padding:[20,20] });
}

function focusSelectedTown(townName) {
  const origin = byName.get(townName);
  if (!origin || !map) return;

  const options = movementOptionsForTown(townName);
  const pts = [[origin.lat, origin.lon]];
  [...options.road, ...options.rail].forEach(name => {
    const t = byName.get(name);
    if (t) pts.push([t.lat, t.lon]);
  });

  if (pts.length <= 1) {
    map.setView([origin.lat, origin.lon], 6, { animate: false });
    return;
  }

  map.fitBounds(pts, { padding:[80,80], maxZoom: 6 });
}

function bindMapEvents() {
  if (!map || bindMapEvents.bound) return;
  bindMapEvents.bound = true;

  map.on('zoom', updateDynamicStyles);
  map.on('zoomend', () => { if (labelMode === 'auto') renderMap(); else updateDynamicStyles(); });
  map.on('popupopen', e => {
    const node = [...currentMarkers.entries()].find(([name, marker]) => marker === e.popup._source);
    if (node) updateInfoPanel(node[0]);
  });
}

function applyGameStateToMap(state) {
  lastGameState = state;
  if (!state || !state.map || !state.map.towns) return;

  highlightLayer.clearLayers();

  markerLayer.eachLayer(layer => {
    const name = [...currentMarkers.entries()].find(([town, marker]) => marker === layer)?.[0];
    if (!name) return;

    const townState = state.map.towns[name] || [];
    if (!townState.length) {
      layer.setStyle({ fillColor: '#cbd5e1', fillOpacity: 0.95 });
      const t = byName.get(name);
      if (t) {
        layer.bindPopup(popupHtml(t), { maxWidth: 380 });
      }
      return;
    }

    const sorted = [...townState].sort((a, b) => b.count - a.count);
    const leader = sorted[0];
    const total = sorted.reduce((sum, item) => sum + (item.count || 0), 0);

    let color = '#cbd5e1';
    const player = (state.players || []).find(p => p.name === leader.player);
    if (player && player.faction) {
      color = palette[player.faction] || color;
    }

    layer.setStyle({ fillColor: color, fillOpacity: 0.98 });

    const baseTown = byName.get(name);
    if (baseTown) {
      const extra = `<hr style="border-color:#2b385d;border-style:solid;border-width:1px 0 0;margin:10px 0;">
      <div>控制者：<span class="pill">${leader.player}</span></div>
      <div>組織總數：<span class="pill">${total}</span></div>`;
      layer.bindPopup(popupHtml(baseTown) + extra, { maxWidth: 380 });
      if (layer.getTooltip()) {
        layer.setTooltipContent(`${name} (${total})`);
      }
    }
  });

  if (selectedTown) {
    renderMovementHighlights(selectedTown);
  }
}

window.applyGameStateToMap = applyGameStateToMap;
window.__selectTownForTest = function (townName) {
  const marker = currentMarkers.get(townName);
  if (!marker) return { ok: false, reason: 'marker-not-found' };
  updateInfoPanel(townName);
  renderMap();
  applyGameStateToMap(lastGameState);
  const didHighlight = renderMovementHighlights(townName);
  window.__lastSelectedTown = townName;
  window.__lastHighlightSuccess = didHighlight;
  return {
    ok: true,
    town: townName,
    highlighted: didHighlight,
    road: movementOptionsForTown(townName).road.length,
    rail: movementOptionsForTown(townName).rail.length,
    owns: playerOwnsTown(townName)
  };
};

window.initializeStrategicMapWhenVisible = async function () {
  if (!document.getElementById('map')) return;
  if (!MAP_DATA) {
    const bundle = await window.loadRedlineMapBundle();
    initializeCanonicalMapData(bundle.mapData, bundle.geoCoordinates);
  }

  if (!window.__redlineMapControlsBound) {
    window.__redlineMapControlsBound = true;

    addOptions('rulerFilter', rulers);
    addOptions('campFilter', camps);
    addOptions('typeFilter', types);

    ['searchBox','rulerFilter','campFilter','typeFilter'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', () => renderMap());
    });

    const resetBtn = document.getElementById('resetFilter');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        ['searchBox','rulerFilter','campFilter','typeFilter'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.value = '';
        });
        renderMap();
      });
    }

    const fitFilteredBtn = document.getElementById('fitFiltered');
    if (fitFilteredBtn) fitFilteredBtn.addEventListener('click', fitVisible);
    const fitAllBtn = document.getElementById('fitAll');
    if (fitAllBtn) fitAllBtn.addEventListener('click', fitAll);
    const focusAsiaBtn = document.getElementById('focusAsia');
    if (focusAsiaBtn) focusAsiaBtn.addEventListener('click', focusAsia);
  }

  if (!map) {
    initEmbeddedMap();
    bindMapEvents();
    renderMap();
  }

  setTimeout(() => {
    if (map) {
      map.invalidateSize(true);
      map.setView([35, 110], 3, { animate: false });
      requestAnimationFrame(() => {
        map.invalidateSize(true);
        map.setView([35, 110], 3, { animate: false });
      });
      setTimeout(() => {
        map.invalidateSize(true);
        focusAsia();
      }, 300);
      setTimeout(() => {
        map.invalidateSize(true);
        focusAsia();
      }, 1200);
    }
  }, 100);
};
