let MAP_DATA = null;
let GEO_COORDS = null;

let rulers = [];
let camps = [];
let types = [];

// 2026-07-18 使用者提供原版桌遊陣營色並依此校正：香港=紫、蒙古=深藍、藏國=綠、
// 哈薩克=青綠、維吾爾=淺藍、滿洲=金黃。藏國取比臺灣綠線（#22c55e）深一階的綠做區隔。
const palette = {
  "臺灣":"#3fb6ff","紅軍":"#f04f56","東洋":"#a78bfa","北國":"#67e8f9","南洋":"#22c55e","印度":"#f59e0b","天方":"#fb7185",
  "香港":"#a855f7","藏國":"#15803d","維吾爾":"#93c5fd","哈薩克":"#14b8a6","蒙古":"#2563eb","滿洲":"#eab308","反賊":"#f97316"
};
const typePalette = {"軍火庫":"#ffcf5a","機場":"#93c5fd","default":"#cbd5e1"};

// Player faction ids (e.g. "taiwan_green") don't match the Chinese palette keys above;
// this maps each faction's data-driven "camp" to the palette key covering its whole camp.
const CAMP_COLOR_KEY = {
  red_army: "紅軍", taiwan: "臺灣", hong_kong: "香港", tibet: "藏國",
  uyghur: "維吾爾", kazakh: "哈薩克", mongol: "蒙古", manchuria: "滿洲", rebel: "反賊"
};
// The Taiwan camp shares one palette hue, but the green line / blue line must read as
// green / blue respectively, so those two factions override the camp colour.
const FACTION_COLOR_OVERRIDE = {
  taiwan_green: "#4ade80",  // 綠線 → green（2026-07-18 使用者要求再淺一階，拉開與藏國深綠的距離）
  taiwan_blue: "#3fb6ff",   // 藍線 → blue
};
let factionMeta = new Map();

async function loadFactionMeta() {
  try {
    const res = await fetch('/factions');
    const data = await res.json();
    const meta = new Map();
    const addEntry = (opt) => {
      if (!opt || !opt.id || !opt.camp) return;
      meta.set(opt.id, { camp: opt.camp, label: opt.variant ? `${opt.name}（${opt.variant}）` : (opt.name || opt.id) });
    };
    (data.categories || []).forEach(category => {
      (category.options || []).forEach(opt => {
        addEntry(opt);
        Object.values(opt.variant_details || {}).forEach(addEntry);
      });
    });
    factionMeta = meta;
    renderMap();
    if (lastGameState) applyGameStateToMap(lastGameState);
  } catch (err) {
    console.warn('Failed to load faction metadata for map labels', err);
  }
}

function factionCampColor(factionId) {
  if (FACTION_COLOR_OVERRIDE[factionId]) return FACTION_COLOR_OVERRIDE[factionId];
  const meta = factionMeta.get(factionId);
  if (!meta) return null;
  return palette[CAMP_COLOR_KEY[meta.camp]] || null;
}

function factionLabel(factionId) {
  const meta = factionMeta.get(factionId);
  return meta ? meta.label : factionId;
}

function addOptions(id, arr) {
  const sel = document.getElementById(id);
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
  addOptions('rulerFilter', rulers);
  addOptions('campFilter', camps);
  addOptions('typeFilter', types);
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

const map = L.map('map', { preferCanvas:true, worldCopyJump:false });
window.__redlinePlayableMap = map;
// Avoid direct use of tile.openstreetmap.org here: local HTML files may be blocked by OSM's tile usage policy
// when Referer is missing. CARTO tiles use OSM data but are more suitable for this standalone viewer.
const cartoLight = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', { maxZoom:19, attribution:'&copy; OpenStreetMap contributors &copy; CARTO' });
const cartoDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', { maxZoom:19, attribution:'&copy; OpenStreetMap contributors &copy; CARTO' });
cartoDark.addTo(map);
let currentBasemap = 'cartoDark';

const roadLayer = L.layerGroup().addTo(map);
const railLayer = L.layerGroup().addTo(map);
const markerLayer = L.layerGroup().addTo(map);
const highlightLayer = L.layerGroup().addTo(map);
const buildHighlightLayer = L.layerGroup().addTo(map);
const supportChoiceHighlightLayer = L.layerGroup().addTo(map);
let labelMode = 'auto', showRoad = true, showRail = true;
let currentMarkers = new Map();
let currentSharedBadges = new Map();
let currentVisible = towns.map(t=>t.name);
let lastGameState = null;
let selectedTown = null;
let selectedMoveTargets = [];
let selectedBuildTargets = [];
let pendingMove = null;
let pendingMoveTarget = null;
let lastResolvedMove = null;
let stickyPlayerErrorMessage = '';
let stickyPlayerErrorTimer = null;
let supportChoiceHighlight = null;
let supportChoiceHighlightFocusKey = null;

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }
function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
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

function townStateEntries(name) {
  return (lastGameState && lastGameState.map && lastGameState.map.towns && lastGameState.map.towns[name]) || [];
}

function totalOrganizationsInTown(name) {
  return townStateEntries(name).reduce((sum, item) => sum + (item.count || 0), 0);
}

function sharedAccessForTown(name) {
  return ((lastGameState && lastGameState.map && lastGameState.map.shared_access && lastGameState.map.shared_access[name]) || []);
}

function sharedAccessSummary(name) {
  const shared = sharedAccessForTown(name);
  if (!shared.length) return '無';
  return `此城鎮可被 ${shared.join(' / ')} 視為共用組織`;
}

function popupHtml(t) {
  const roads = (t.road||[]).map(n=>`<span class="pill">${n}</span>`).join(' ') || '無';
  const rails = (t.rail||[]).map(n=>`<span class="pill">${n}</span>`).join(' ') || '無';
  const entries = townStateEntries(t.name);
  const total = totalOrganizationsInTown(t.name);
  const controller = entries.length ? entries.slice().sort((a,b)=>(b.count||0)-(a.count||0))[0].player : null;
  const shared = sharedAccessForTown(t.name);
  return `
    <div class="name">${t.name}</div>
    <div>座標：<code>${t.lon.toFixed(3)}, ${t.lat.toFixed(3)}</code></div>
    <div>靜態統治者：${(t.ruler||[]).map(x=>`<span class="pill">${x}</span>`).join(' ') || '無'}</div>
    <div>陣營：${(t.camp||[]).map(x=>`<span class="pill">${x}</span>`).join(' ') || '無'}</div>
    <div>城鎮類型：${t.type ? `<span class="pill">${t.type}</span>` : '一般城鎮'}</div>
    <hr style="border-color:#2b385d;border-style:solid;border-width:1px 0 0;margin:10px 0;">
    <div>當前控制者：${controller ? `<span class="pill">${controller}</span>` : '無組織'}</div>
    <div>組織狀態：<span class="pill">${total > 0 ? '有組織' : '無組織'}</span></div>
    <div>共享可用：${shared.length ? shared.map(x=>`<span class="pill">${x}</span>`).join(' ') : '無'}</div>
    <div>共享說明：${shared.length ? `<span class="pill">${sharedAccessSummary(t.name)}</span>` : '無'}</div>
    <hr style="border-color:#2b385d;border-style:solid;border-width:1px 0 0;margin:10px 0;">
    <div>一般道路：${roads}</div>
    <div>鐵路：${rails}</div>`;
}

function resetMoveSelection() {
  selectedMoveTargets = [];
  pendingMove = null;
  pendingMoveTarget = null;
}

function exitMovementSelection() {
  selectedTown = null;
  resetMoveSelection();
  resetBuildSelection();
  highlightLayer.clearLayers();
  renderMap();
  applyGameStateToMap(lastGameState);
  updateStatusPanel();
  refreshDirectBuildUi();
  const info = document.getElementById('info');
  if (info) {
    info.innerHTML = '<div class="name">尚未選取城鎮</div><div>點擊自己的組織城鎮查看後端判定的合法移動目的地。</div>';
  }
}

function resetBuildSelection() {
  selectedBuildTargets = [];
  buildHighlightLayer.clearLayers();
}

function supportChoiceHighlightKey(payload) {
  if (!payload || payload.mode !== 'support-targets') return null;
  const towns = Array.isArray(payload.towns) ? payload.towns : [];
  return JSON.stringify({
    mode: payload.mode,
    sourceName: payload.sourceName || '',
    prompt: payload.prompt || '',
    focusTown: payload.focusTown || '',
    towns: towns.map(entry => entry?.town || '').filter(Boolean).sort(),
  });
}

function focusSupportChoiceTargets(bounds) {
  if (!bounds.length) return;
  if (bounds.length === 1) {
    map.setView(bounds[0], Math.max(map.getZoom(), 8), { animate: false });
    return;
  }
  map.fitBounds(bounds, { padding: [110, 110], maxZoom: 8 });
}

function selectTownForCurrentMapAction(townName, options = {}) {
  const { autoFocus = true } = options;
  updateInfoPanel(townName);
  resetMoveSelection();
  resetBuildSelection();
  renderMap();
  applyGameStateToMap(lastGameState);
  const didHighlight = renderMovementHighlights(townName, { autoFocus });
  refreshDirectBuildUi();
  window.__lastSelectedTown = townName;
  window.__lastHighlightSuccess = didHighlight;
  return didHighlight;
}

function isBuildSupportChoiceHighlight() {
  return !!supportChoiceHighlight && (
    supportChoiceHighlight.actionKind === 'build'
    || ['event_build_organization', 'era_red_build_near_target', 'card_build_organization'].includes(supportChoiceHighlight.choiceKey)
  );
}

function renderSupportChoiceHighlights(options = {}) {
  const { autoFocus = false } = options;
  supportChoiceHighlightLayer.clearLayers();
  if (!supportChoiceHighlight || supportChoiceHighlight.mode !== 'support-targets') return;
  const towns = Array.isArray(supportChoiceHighlight.towns) ? supportChoiceHighlight.towns : [];
  const bounds = [];
  let focusedBounds = null;
  towns.forEach(entry => {
    const townName = entry?.town;
    const town = byName.get(townName);
    if (!town) return;
    const townBounds = [town.lat, town.lon];
    bounds.push(townBounds);
    if (supportChoiceHighlight.focusTown && supportChoiceHighlight.focusTown === townName) {
      focusedBounds = [townBounds];
    }
    const isFocused = supportChoiceHighlight.focusTown && supportChoiceHighlight.focusTown === townName;
    const outerMarker = L.circleMarker([town.lat, town.lon], {
      radius: Math.max(isFocused ? 18 : 14, markerRadius(map.getZoom()) + (isFocused ? 10 : 6)),
      color: isFocused ? '#ffffff' : '#cbd5e1',
      weight: isFocused ? 5 : 4,
      fillColor: '#cbd5e1',
      fillOpacity: isFocused ? 0.14 : 0.08,
      opacity: 1,
    }).addTo(supportChoiceHighlightLayer).bindPopup(`${escapeHtml(supportChoiceHighlight.sourceName || '可選目標')}：${escapeHtml(entry?.label || townName)}`);
    outerMarker.on('click', () => selectTownForCurrentMapAction(townName, { autoFocus: false }));
    const innerMarker = L.circleMarker([town.lat, town.lon], {
      radius: Math.max(isFocused ? 9 : 7, markerRadius(map.getZoom()) + (isFocused ? 2 : 1)),
      color: isFocused ? '#ffffff' : '#e2e8f0',
      weight: 2,
      fillOpacity: 0,
      opacity: 1,
    }).addTo(supportChoiceHighlightLayer);
    innerMarker.on('click', () => selectTownForCurrentMapAction(townName, { autoFocus: false }));
  });
  if (bounds.length) {
    const hintEl = document.getElementById('interactionHint');
    if (hintEl) {
      const isBuildChoice = isBuildSupportChoiceHighlight();
      const focusText = supportChoiceHighlight.focusTown ? ` 已聚焦 ${supportChoiceHighlight.focusTown}。` : '';
      const actionText = isBuildChoice
        ? '請點選中性色外框城鎮，然後使用左側「在目前城鎮建立組織（效果）」按鈕完成建立。'
        : '請點選中性色外框城鎮，然後使用左側「瓦解目前城鎮（效果）」按鈕完成瓦解；也可回到選擇視窗確認。';
      // bounds.length is the number of neutral candidate markers actually placed on the map,
      // exact set of clickable/buildable towns — so the count always matches the highlights.
      const countText = isBuildChoice
        ? `<span class="hint-strong">可建立城鎮：${bounds.length} 個</span>。<span class="hint-strong">尚可建立組織：${Math.max(1, Number(supportChoiceHighlight.remainingBuilds || 1))} 個</span>。`
        : `<span class="hint-strong">可選目標：${bounds.length} 個</span>。`;
      const sourceLabel = escapeHtml(supportChoiceHighlight.sourceName || '當前選擇');
      // The server prompt often already carries a "<source>：" prefix; strip it so the label
      // isn't printed twice (e.g. "宣傳家：宣傳家：…").
      let promptText = supportChoiceHighlight.prompt || '請依列表選擇目標。';
      if (supportChoiceHighlight.sourceName && promptText.startsWith(`${supportChoiceHighlight.sourceName}：`)) {
        promptText = promptText.slice(`${supportChoiceHighlight.sourceName}：`.length);
      }
      hintEl.innerHTML = `${sourceLabel}：<span class="hint-strong">${escapeHtml(promptText)}</span> ${countText}地圖上已用中性色外框標出可選城鎮。${escapeHtml(focusText)}${actionText}`;
    }
    if (autoFocus) {
      focusSupportChoiceTargets(focusedBounds || bounds);
    }
  }
}

function applySupportChoiceHighlight(payload) {
  const nextKey = supportChoiceHighlightKey(payload);
  const shouldAutoFocus = !!nextKey && nextKey !== supportChoiceHighlightFocusKey;
  supportChoiceHighlight = payload || null;
  supportChoiceHighlightFocusKey = nextKey;
  renderSupportChoiceHighlights({ autoFocus: shouldAutoFocus });
}

function finalizeMoveSelection(fromTown, toTown) {
  lastResolvedMove = { from: fromTown, to: toTown };
  selectedTown = toTown;
  updateInfoPanel(toTown);
  renderMap();
  applyGameStateToMap(lastGameState);
  renderMovementHighlights(toTown);
}

function updateStatusPanel() {
  const currentPlayerEl = document.getElementById('statusCurrentPlayer');
  const selectedTownEl = document.getElementById('statusSelectedTown');
  const hintEl = document.getElementById('interactionHint');

  if (currentPlayerEl) {
    const curName = currentPlayerName();
    currentPlayerEl.textContent = curName || '未連線';
    // 玩家名稱字色＝其陣營色（2026-07-18 使用者需求）；注意 currentPlayerFaction() 回傳的是
    // 「觀看者自己」的陣營（mapPlayerId），這裡顯示的名字是「當前行動玩家」，必須用該玩家
    // 自己的陣營查色，否則在對手回合會染成觀看者的顏色（20 回合自動桌測發現的 bug）。
    const curPlayer = (lastGameState?.players || []).find(p => p.name === curName);
    const color = curPlayer ? factionCampColor(curPlayer.faction) : null;
    currentPlayerEl.style.color = color || '';
  }

  if (selectedTownEl) {
    selectedTownEl.textContent = selectedTown || '尚未選取';
  }

  if (hintEl) {
    if (stickyPlayerErrorMessage) {
      hintEl.innerHTML = `操作失敗：<span class="hint-strong">${escapeHtml(stickyPlayerErrorMessage)}</span>`;
    } else if (pendingMove) {
      hintEl.innerHTML = pendingMove.error
        ? `移動失敗：<span class="hint-strong">${escapeHtml(pendingMove.error)}</span>`
        : `正在移動 <span class="hint-strong">${escapeHtml(pendingMove.from)}</span> → <span class="hint-strong">${escapeHtml(pendingMove.to)}</span>（${pendingMove.mode === 'rail' ? '鐵路' : '道路'}）`;
    } else if (lastResolvedMove) {
      hintEl.innerHTML = `已完成移動：<span class="hint-strong">${lastResolvedMove.from}</span> → <span class="hint-strong">${lastResolvedMove.to}</span>`;
    } else if (!selectedTown) {
      hintEl.innerHTML = playerHasSafehouse()
        ? '連上遊戲後，點選自己的香港組織城鎮，可同時查看移動與 <span class="hint-strong">安全屋建立範圍</span>。若城鎮有共享組織，會以 <span class="hint-strong">金色外框與 S 標記</span> 顯示。'
        : '連上遊戲後，只有 <span class="hint-strong">當前玩家自己擁有組織</span> 的城鎮可以高亮合法移動；若城鎮具有共享組織，會以 <span class="hint-strong">金色外框與 S 標記</span> 顯示。';
    } else if (eventBuildChoiceForTown(selectedTown)) {
      hintEl.innerHTML = `已選取 <span class="hint-strong">${selectedTown}</span>：事件卡效果允許在此建立組織，請使用左側「在目前城鎮建立組織（事件卡）」按鈕完成。`;
    } else if (playerOwnsTown(selectedTown)) {
      const opts = movementOptionsForTown(selectedTown);
      const destinationCount = new Set([...opts.road, ...opts.rail].map(entry => entry.town)).size;
      const buildOpts = playerHasSafehouse() ? buildOptionsForTown(selectedTown) : [];
      const sharedHint = playerHasSharedAccessToTown(selectedTown) ? ' 此城鎮也處於共享組織狀態。' : '';
      hintEl.innerHTML = `已選取 <span class="hint-strong">${selectedTown}</span>：合法移動目的地 ${destinationCount} 個` +
        (buildOpts.length ? `，安全屋可建立 ${buildOpts.length} 個目標。` : '。') + sharedHint;
    } else if (playerHasSharedAccessToTown(selectedTown)) {
      hintEl.innerHTML = `已選取 <span class="hint-strong">${escapeHtml(selectedTown)}</span>：此城鎮對當前玩家具有 <span class="hint-strong">共享組織</span> 可用性，但互動高亮規則尚未完全支援共享組織狀態。`;
    } else {
      hintEl.innerHTML = `已選取 <span class="hint-strong">${selectedTown}</span>：這不是當前玩家可操作的城鎮。`;
    }
  }
}

function showStickyMapPlayerError(message, durationMs = 5000) {
  const localizedMessage = playerMessageZhTw(message);
  stickyPlayerErrorMessage = localizedMessage;
  if (stickyPlayerErrorTimer) clearTimeout(stickyPlayerErrorTimer);
  updateStatusPanel();
  stickyPlayerErrorTimer = setTimeout(() => {
    if (stickyPlayerErrorMessage !== localizedMessage) return;
    stickyPlayerErrorMessage = '';
    stickyPlayerErrorTimer = null;
    updateStatusPanel();
  }, durationMs);
}

function updateInfoPanel(name) {
  const t = byName.get(name);
  if (!t) return;
  const total = totalOrganizationsInTown(name);
  const shared = sharedAccessForTown(name);
  const stateBadge = total > 0 ? '有組織' : '無組織';
  const sharedBadge = shared.length ? `共享中（${shared.length}）` : '無共享';
  document.getElementById('info').innerHTML = `${popupHtml(t)}<hr style="border-color:#2b385d;border-style:solid;border-width:1px 0 0;margin:10px 0;"><div>視覺狀態：<span class="pill">${stateBadge}</span> <span class="pill">${sharedBadge}</span></div>`;
}

function shouldShowLabels() {
  return labelMode === 'on' || (labelMode === 'auto' && map.getZoom() >= 5);
}

function townLabelOptions(townName, zoom = map.getZoom()) {
  const distance = markerRadius(zoom) + 4;
  // 金門與廈門在低／中 zoom 幾乎重疊；兩者都置頂時，後渲染的廈門會蓋住金門。
  // 將金門固定放到 marker 下方，保留兩個城鎮名稱且不改動任何地理座標。
  const isKinmen = townName === '金門';
  return {
    permanent: true,
    direction: isKinmen ? 'bottom' : 'top',
    className: isKinmen ? 'town-label town-label-kinmen' : 'town-label',
    offset: [0, isKinmen ? distance : -distance],
  };
}

function clearLayers() {
  roadLayer.clearLayers();
  railLayer.clearLayers();
  markerLayer.clearLayers();
  highlightLayer.clearLayers();
  currentSharedBadges.forEach(marker => {
    try { map.removeLayer(marker); } catch {}
  });
  currentMarkers = new Map();
  currentSharedBadges = new Map();
}

function markerStyleForTown(name, zoom = map.getZoom()) {
  const total = totalOrganizationsInTown(name);
  const ownedByCurrent = playerOwnsTown(name);
  const shared = sharedAccessForTown(name);
  const hasShared = shared.length > 0;
  const base = {
    radius: markerRadius(zoom),
    color: '#07111f',
    weight: markerStroke(zoom),
    fillColor: '#6b7280',
    fillOpacity: 0.32,
    opacity: 0.72,
  };

  if (total <= 0) {
    return hasShared ? {
      ...base,
      color: '#facc15',
      weight: Math.max(base.weight + 1.5, 2.5),
      fillOpacity: 0.46,
      opacity: 0.92,
    } : base;
  }

  const entries = townStateEntries(name);
  const leader = entries.slice().sort((a, b) => (b.count || 0) - (a.count || 0))[0];
  const player = (lastGameState?.players || []).find(p => p.name === leader?.player);
  const controlColor = player?.faction ? (factionCampColor(player.faction) || '#cbd5e1') : '#cbd5e1';

  return {
    radius: Math.max(base.radius + (hasShared ? 3 : 2), hasShared ? 9 : 8),
    color: hasShared ? '#facc15' : (ownedByCurrent ? '#f8fafc' : '#cbd5e1'),
    weight: hasShared ? Math.max(base.weight + 2.5, 3.5) : (ownedByCurrent ? Math.max(base.weight + 1.5, 3) : Math.max(base.weight + 0.5, 2)),
    fillColor: controlColor,
    fillOpacity: ownedByCurrent ? 0.98 : 0.88,
    opacity: 1,
  };
}

function currentPlayerName() {
  return lastGameState && lastGameState.current_player ? lastGameState.current_player : null;
}

function currentPlayerFaction() {
  const player = currentPlayerState();
  return player ? player.faction : null;
}

function canActFromTown(townName) {
  return playerOwnsTown(townName) || playerHasSharedAccessToTown(townName);
}

function playerOwnsTown(townName) {
  if (!lastGameState || !lastGameState.map || !lastGameState.map.towns) return false;
  const entries = lastGameState.map.towns[townName] || [];
  return entries.some(entry => entry.player === currentPlayerName() && (entry.count || 0) > 0);
}

function playerHasSharedAccessToTown(townName) {
  const faction = currentPlayerFaction();
  if (!faction) return false;
  return sharedAccessForTown(townName).includes(faction);
}

function actualTownOwnerName(townName) {
  const entries = townStateEntries(townName);
  if (!entries.length) return null;
  const leader = entries.slice().sort((a, b) => (b.count || 0) - (a.count || 0))[0];
  return leader?.player || null;
}

// 陣營標籤只在 zoom >= FACTION_LABEL_MIN_ZOOM 時附加：北台灣等城鎮密集區在遠視角下，
// 長標籤（如「臺北（臺灣（綠線））」）會互相覆蓋蓋字；遠視角的陣營資訊由圓圈填色承擔。
// 一城一組織 invariant 生效後，組織數永遠只能是 1，因此標籤不再顯示冗餘數字。
const FACTION_LABEL_MIN_ZOOM = 10;

function labelTextForTown(townName) {
  const total = totalOrganizationsInTown(townName);
  if (total <= 0) return townName;
  const owner = actualTownOwnerName(townName);
  const player = (lastGameState?.players || []).find(p => p.name === owner);
  const showFaction = map.getZoom() >= FACTION_LABEL_MIN_ZOOM;
  const factionText = showFaction && player?.faction ? factionLabel(player.faction) : null;
  return factionText ? `${townName}（${factionText}）` : townName;
}

function sharedDissolveTargetForTown(townName) {
  if (!playerHasSharedAccessToTown(townName)) return null;
  const owner = actualTownOwnerName(townName);
  if (!owner || owner === currentPlayerName()) return null;
  return owner;
}

function townHasAnyOrganization(townName) {
  return totalOrganizationsInTown(townName) > 0;
}

function movementOptionsForTown(townName) {
  if (!lastGameState || !townName) return { road: [], rail: [] };
  const projected = lastGameState.map?.legal_organization_moves?.[townName];
  if (!projected) return { road: [], rail: [] };

  const normalize = entries => (Array.isArray(entries) ? entries : [])
    .filter(entry => entry && typeof entry.town === 'string')
    .map(entry => ({ town: entry.town, cost: Number(entry.cost) || 1 }));
  return {
    road: normalize(projected.road),
    rail: normalize(projected.rail),
  };
}

function currentPlayerState() {
  if (!lastGameState || !mapPlayerId) return null;
  return (lastGameState.players || []).find(p => p.id === mapPlayerId) || null;
}

function playerHasSafehouse() {
  const player = currentPlayerState();
  if (!player || player.faction !== 'hong_kong') return false;
  return ['香港城', '臺北'].some(t => (player.orgs || {})[t] > 0);
}

function buildOptionsForTown(originTown) {
  if (!lastGameState || !originTown || !playerHasSafehouse()) return [];
  if (!canActFromTown(originTown)) return [];

  const maxDistance = 2;
  const visited = new Set([originTown]);
  const queue = [[originTown, 0]];
  const reachable = new Set();

  while (queue.length) {
    const [town, dist] = queue.shift();
    if (dist >= maxDistance) continue;
    const data = MAP_DATA.towns[town] || {};
    const neighbors = new Set([...(data.road || []), ...(data.rail || [])]);
    for (const nxt of neighbors) {
      if (visited.has(nxt)) continue;
      visited.add(nxt);
      reachable.add(nxt);
      queue.push([nxt, dist + 1]);
    }
  }

  return Array.from(reachable).filter(town => MAP_DATA.towns[town] && !townHasAnyOrganization(town));
}

function renderMovementHighlights(townName, options = {}) {
  const { autoFocus = false } = options;
  highlightLayer.clearLayers();
  // Reset every marker to its base style first so a prior selection's highlight never
  // lingers — this call must produce a complete, order-independent visual.
  currentMarkers.forEach((marker, name) => {
    if (marker.setStyle) marker.setStyle(markerStyleForTown(name, map.getZoom()));
  });
  selectedTown = townName;
  selectedMoveTargets = [];
  lastResolvedMove = null;
  resetBuildSelection();
  updateStatusPanel();
  refreshDirectBuildUi();
  if (!townName) return false;

  const opts = movementOptionsForTown(townName);
  const origin = byName.get(townName);
  if (!origin) return false;

  const canAct = canActFromTown(townName);
  const ownOnly = playerOwnsTown(townName);
  const sharedOnly = !ownOnly && playerHasSharedAccessToTown(townName);

  const originMarker = currentMarkers.get(townName);
  if (originMarker) {
    const originStyle = {
      color: sharedOnly ? '#facc15' : '#ffffff',
      weight: sharedOnly ? 5 : 4,
      fillOpacity: 1,
      radius: Math.max(10, markerRadius(map.getZoom()) + (sharedOnly ? 3 : 2)),
    };
    // A town that has any organisation (own / shared / enemy) keeps its solid faction
    // fill so ownership stays visible; a selected town with no organisation becomes
    // solid white.
    if (totalOrganizationsInTown(townName) <= 0) originStyle.fillColor = '#f8fafc';
    originMarker.setStyle(originStyle);
  }

  if (!canAct) {
    updateStatusPanel();
    refreshDirectBuildUi();
    return false;
  }

  let highlightCount = 0;

  roadLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ color:'#d8a04a', opacity:0.12, weight:Math.max(1.5, roadWeight(map.getZoom()) - 1) });
  });
  railLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ color:'#ef4444', opacity:0.15, weight:Math.max(2, railWeight(map.getZoom()) - 1), dashArray: railDashArray(map.getZoom()) });
  });

  const candidateStyle = (townName, mode) => {
    const base = markerStyleForTown(townName, map.getZoom());
    return {
      ...base,
      color: '#e2e8f0',
      weight: 5,
      dashArray: mode === 'rail' ? '5 4' : null,
      radius: Math.max(10, (base.radius || markerRadius(map.getZoom())) + 2),
    };
  };

  for (const option of opts.road) {
    const toName = option.town;
    const target = byName.get(toName);
    if (!target) continue;
    selectedMoveTargets.push({ town: toName, mode: 'road', cost: option.cost });
    highlightCount += 1;

    const marker = currentMarkers.get(toName);
    if (marker) marker.setStyle(candidateStyle(toName, 'road'));
  }

  for (const option of opts.rail) {
    const toName = option.town;
    const target = byName.get(toName);
    if (!target) continue;
    selectedMoveTargets.push({ town: toName, mode: 'rail', cost: option.cost });
    highlightCount += 1;

    const marker = currentMarkers.get(toName);
    if (marker) marker.setStyle(candidateStyle(toName, 'rail'));
  }

  if (playerHasSafehouse()) {
    const buildTargets = buildOptionsForTown(townName);
    selectedBuildTargets = buildTargets.slice();
    for (const toName of buildTargets) {
      const target = byName.get(toName);
      if (!target) continue;
      L.circleMarker([target.lat, target.lon], {
        radius: Math.max(9, markerRadius(map.getZoom()) + 2),
        color: '#cbd5e1',
        weight: 3,
        fillColor: '#cbd5e1',
        fillOpacity: 0.08,
        opacity: 1,
      }).addTo(buildHighlightLayer).bindPopup(`安全屋可建立：${townName} → ${toName}`);
    }
  }

  if (sharedOnly) {
    L.circleMarker([origin.lat, origin.lon], {
      radius: Math.max(12, markerRadius(map.getZoom()) + 5),
      color: '#facc15',
      weight: 3,
      fillOpacity: 0,
      opacity: 1,
      dashArray: '6 4',
    }).addTo(highlightLayer).bindPopup(`共享組織起點：${townName}`);
  }

  if (autoFocus) {
    focusSelectedTown(townName);
  }
  refreshDirectBuildUi();
  updateStatusPanel();
  renderSupportChoiceHighlights();
  return highlightCount > 0 || sharedOnly || selectedBuildTargets.length > 0;
}

function moveOptionForTown(townName) {
  return selectedMoveTargets.find(item => item.town === townName) || null;
}

function sendMoveAction(fromTown, toTown, mode) {
  if (!mapWs || mapWs.readyState !== WebSocket.OPEN) {
    pendingMove = { from: fromTown, to: toTown, mode, error: '遊戲連線尚未建立。' };
    updateStatusPanel();
    return { ok: false, reason: 'socket-not-open' };
  }

  lastResolvedMove = null;
  pendingMove = { from: fromTown, to: toTown, mode };
  updateStatusPanel();
  mapWs.send(JSON.stringify({ action: 'move', from: fromTown, to: toTown, mode }));
  return { ok: true };
}

function eventBuildChoiceForTown(townName) {
  if (!supportChoiceHighlight || !isBuildSupportChoiceHighlight()) return null;
  const towns = Array.isArray(supportChoiceHighlight.towns) ? supportChoiceHighlight.towns : [];
  const entry = towns.find(item => item?.town === townName);
  if (!entry) return null;
  const resolvedIndex = Number.isFinite(Number(entry.index))
    ? Number(entry.index)
    : towns.findIndex(item => item?.town === townName);
  if (!Number.isFinite(resolvedIndex) || resolvedIndex < 0) return null;
  return { ...entry, index: resolvedIndex };
}

function supportTargetChoiceForTown(townName) {
  if (!supportChoiceHighlight || supportChoiceHighlight.mode !== 'support-targets') return null;
  if (isBuildSupportChoiceHighlight()) return null;
  const towns = Array.isArray(supportChoiceHighlight.towns) ? supportChoiceHighlight.towns : [];
  const entry = towns.find(item => item?.town === townName);
  if (!entry) return null;
  const resolvedIndex = Number.isFinite(Number(entry.index))
    ? Number(entry.index)
    : towns.findIndex(item => item?.town === townName);
  if (!Number.isFinite(resolvedIndex) || resolvedIndex < 0) return null;
  return { ...entry, index: resolvedIndex };
}

function supportChoiceTownNearLatLng(latlng, maxPixels = 28) {
  if (!supportChoiceHighlight || supportChoiceHighlight.mode !== 'support-targets') return null;
  const towns = Array.isArray(supportChoiceHighlight.towns) ? supportChoiceHighlight.towns : [];
  if (!towns.length || !latlng || !map) return null;
  const clickPoint = map.latLngToContainerPoint(latlng);
  let nearest = null;
  towns.forEach(entry => {
    const townName = entry?.town;
    const town = byName.get(townName);
    if (!town) return;
    const point = map.latLngToContainerPoint([town.lat, town.lon]);
    const distance = clickPoint.distanceTo(point);
    if (distance <= maxPixels && (!nearest || distance < nearest.distance)) {
      nearest = { town: townName, distance };
    }
  });
  return nearest?.town || null;
}

function sendDirectBuildAction(townName) {
  if (!mapWs || mapWs.readyState !== WebSocket.OPEN) {
    return { ok: false, reason: 'socket-not-open' };
  }
  const eventChoice = eventBuildChoiceForTown(townName);
  if (eventChoice) {
    mapWs.send(JSON.stringify({ action: 'resolve_choice', index: eventChoice.index }));
    return { ok: true, eventChoice: true, index: eventChoice.index };
  }
  mapWs.send(JSON.stringify({ action: 'build', town: townName }));
  return { ok: true };
}

function sendDissolveAction(defender, townName) {
  if (!mapWs || mapWs.readyState !== WebSocket.OPEN) {
    return { ok: false, reason: 'socket-not-open' };
  }
  const supportTargetChoice = supportTargetChoiceForTown(townName);
  if (supportTargetChoice) {
    mapWs.send(JSON.stringify({ action: 'resolve_choice', index: supportTargetChoice.index }));
    return { ok: true, supportTargetChoice: true, index: supportTargetChoice.index };
  }
  mapWs.send(JSON.stringify({ action: 'dissolve', defender, town: townName }));
  return { ok: true };
}

function refreshMoveConfirmUi() {
  const confirmBtn = document.getElementById('confirmMoveBtn');
  const cancelBtn = document.getElementById('cancelMoveBtn');
  const hint = document.getElementById('confirmMoveHint');
  if (!confirmBtn || !cancelBtn || !hint) return;

  if (!pendingMoveTarget) {
    confirmBtn.disabled = true;
    cancelBtn.disabled = true;
    hint.innerHTML = '點選可移動城鎮後，這裡會顯示移動確認。';
    return;
  }

  confirmBtn.disabled = false;
  cancelBtn.disabled = false;
  const modeLabel = pendingMoveTarget.mode === 'rail' ? '鐵路' : '道路';
  const costLabel = `消耗 ${pendingMoveTarget.cost || 1} 次移動`;
  hint.innerHTML = `確認將組織從 <span class="hint-strong">${pendingMoveTarget.from}</span> 移動到 <span class="hint-strong">${pendingMoveTarget.to}</span>（${modeLabel}，${costLabel}）？`;
}

function refreshDirectBuildUi() {
  refreshMoveConfirmUi();
  const btn = document.getElementById('directBuildBtn');
  const hint = document.getElementById('directBuildHint');
  const dissolveBtn = document.getElementById('dissolveBtn');
  const dissolveHint = document.getElementById('dissolveHint');
  if (!btn || !hint || !dissolveBtn || !dissolveHint) return;

  if (!selectedTown) {
    btn.disabled = true;
    btn.textContent = '在目前城鎮建立組織';
    dissolveBtn.disabled = true;
    hint.innerHTML = '選取具有自己組織、共享組織可用性或事件卡允許建立的城鎮後，這裡會顯示是否可直接建立。';
    dissolveHint.innerHTML = '選取具有共享可用性的城鎮後，這裡會顯示是否可對實際組織擁有者發動瓦解。';
    return;
  }

  const eventChoice = eventBuildChoiceForTown(selectedTown);
  if (eventChoice) {
    btn.disabled = false;
    btn.textContent = '在目前城鎮建立組織（效果）';
    hint.innerHTML = `目前選取 <span class="hint-strong">${selectedTown}</span>：目前效果允許在此建立組織；按上方按鈕完成建立。`;
  } else {
    btn.textContent = '在目前城鎮建立組織';
    btn.disabled = true;
    const sharedOnly = !playerOwnsTown(selectedTown) && playerHasSharedAccessToTown(selectedTown);
    const canAct = canActFromTown(selectedTown);
    if (!canAct) {
      hint.innerHTML = `目前選取 <span class="hint-strong">${selectedTown}</span>，但這不是你的組織或共享組織起點。`;
    } else if (sharedOnly) {
      hint.innerHTML = `目前選取 <span class="hint-strong">${selectedTown}</span>：這是一個可用的共享組織起點；每城只能有 1 個組織，請改選空城鎮作為建立目標。`;
    } else {
      hint.innerHTML = `目前選取 <span class="hint-strong">${selectedTown}</span>：每城只能有 1 個組織，請改選空城鎮作為建立目標。`;
    }
  }

  const supportTargetChoice = supportTargetChoiceForTown(selectedTown);
  if (supportTargetChoice) {
    dissolveBtn.disabled = false;
    dissolveBtn.textContent = '瓦解目前城鎮（效果）';
    dissolveHint.innerHTML = `目前選取 <span class="hint-strong">${selectedTown}</span>：${supportChoiceHighlight.sourceName || '目前效果'} 允許選擇此目標；按上方按鈕完成瓦解。`;
  } else {
    dissolveBtn.textContent = '瓦解目前城鎮組織';
    const dissolveTarget = sharedDissolveTargetForTown(selectedTown);
    if (!dissolveTarget) {
      dissolveBtn.disabled = true;
      dissolveHint.innerHTML = `目前選取 <span class="hint-strong">${escapeHtml(selectedTown)}</span>：沒有可瓦解的共享組織目標。`;
    } else {
      dissolveBtn.disabled = false;
      dissolveHint.innerHTML = `目前選取 <span class="hint-strong">${selectedTown}</span>：可瓦解實際擁有者 <span class="hint-strong">${dissolveTarget}</span> 的共享組織。`;
    }
  }
}

function updateDynamicStyles() {
  const z = map.getZoom();
  roadLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ color:'#7a6030', weight: roadWeight(z), opacity: 0.24 });
  });
  railLayer.eachLayer(layer => {
    if (layer.setStyle) layer.setStyle({ color: '#42667a', weight: railWeight(z), opacity: 0.28, dashArray: railDashArray(z), lineCap: 'round' });
  });
  markerLayer.eachLayer(layer => {
    const name = [...currentMarkers.entries()].find(([town, marker]) => marker === layer)?.[0];
    if (name && layer.setStyle) {
      layer.setStyle(markerStyleForTown(name, z));
    }
    if (layer.getTooltip && layer.getTooltip() && name) {
      const options = townLabelOptions(name, z);
      layer.getTooltip().options.direction = options.direction;
      layer.getTooltip().options.offset = options.offset;
      layer.setTooltipContent(labelTextForTown(name));
    }
  });
  currentSharedBadges.forEach((badge, townName) => {
    const town = byName.get(townName);
    if (!town || !badge.setLatLng || !badge.getElement) return;
    badge.setLatLng([town.lat, town.lon]);
  });
  renderSupportChoiceHighlights();
}

function renderMap() {
  clearLayers();
  updateStatusPanel();
  const f = filters();
  const visibleTowns = towns.filter(t => townMatches(t, f));
  currentVisible = visibleTowns.map(t => t.name);
  const visibleSet = new Set(currentVisible);

  for (const link of links) {
    if (!visibleSet.has(link.source) || !visibleSet.has(link.target)) continue;
    const a = byName.get(link.source), b = byName.get(link.target);
    const latlngs = [[a.lat, a.lon], [b.lat, b.lon]];
    const style = link.type === 'road'
      ? { color:'#7a6030', weight:roadWeight(), opacity:0.24 }
      : { color:'#42667a', weight:railWeight(), opacity:0.28, dashArray: railDashArray(), lineCap:'round' };
    const linkTypeLabel = link.type === 'rail' ? '鐵路' : '道路';
    const poly = L.polyline(latlngs, style).bindPopup(`${linkTypeLabel}：${escapeHtml(link.source)} ↔ ${escapeHtml(link.target)}`);
    if (link.type === 'road' && showRoad) poly.addTo(roadLayer);
    if (link.type === 'rail' && showRail) poly.addTo(railLayer);
  }

  visibleTowns.forEach(t => {
    const marker = L.circleMarker([t.lat, t.lon], markerStyleForTown(t.name)).addTo(markerLayer);
    marker.bindPopup(popupHtml(t), { maxWidth:380 });

    const shared = sharedAccessForTown(t.name);
    if (shared.length) {
      const badge = L.marker([t.lat, t.lon], {
        interactive: false,
        keyboard: false,
        zIndexOffset: 700,
        icon: L.divIcon({
          className: 'shared-badge-wrap',
          html: `<div class="shared-badge ${shared.length > 1 ? 'shared-badge-multi' : ''}" title="${sharedAccessSummary(t.name)}">S${shared.length > 1 ? shared.length : ''}</div>`,
          iconSize: [26, 22],
          iconAnchor: [-2, 14],
        })
      }).addTo(map);
      currentSharedBadges.set(t.name, badge);
    }
    marker.on('click', () => {
      const eventChoice = eventBuildChoiceForTown(t.name);
      const supportTargetChoice = supportTargetChoiceForTown(t.name);
      if (eventChoice || supportTargetChoice) {
        selectTownForCurrentMapAction(t.name, { autoFocus: true });
        return;
      }

      const moveOption = moveOptionForTown(t.name);
      if (selectedTown && moveOption) {
        pendingMoveTarget = { from: selectedTown, to: t.name, mode: moveOption.mode, cost: moveOption.cost };
        refreshMoveConfirmUi();
        return;
      }

      if (selectedTown && selectedBuildTargets.includes(t.name) && playerHasSafehouse()) {
        if (!mapWs || mapWs.readyState !== WebSocket.OPEN) return;
        mapWs.send(JSON.stringify({ action: 'build', from: selectedTown, town: t.name }));
        return;
      }

      // While choosing a movement destination, unrelated towns are deliberately
      // non-interactive.  Another own/shared organization may still become a new origin.
      if (selectedTown && selectedMoveTargets.length) {
        if (canActFromTown(t.name)) {
          selectTownForCurrentMapAction(t.name, { autoFocus: true });
        }
        return;
      }

      selectTownForCurrentMapAction(t.name, { autoFocus: true });
    });
    currentMarkers.set(t.name, marker);
    if (shouldShowLabels()) marker.bindTooltip(labelTextForTown(t.name), townLabelOptions(t.name));
  });

  updateDynamicStyles();
  if (selectedTown) {
    renderMovementHighlights(selectedTown, { autoFocus: false });
  }
  renderSupportChoiceHighlights();
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

  const moveOptions = movementOptionsForTown(townName);
  const buildOptions = playerHasSafehouse() ? buildOptionsForTown(townName) : [];
  const pts = [[origin.lat, origin.lon]];
  [...moveOptions.road, ...moveOptions.rail].forEach(option => {
    const t = byName.get(option.town);
    if (t) pts.push([t.lat, t.lon]);
  });
  buildOptions.forEach(name => {
    const t = byName.get(name);
    if (t) pts.push([t.lat, t.lon]);
  });

  if (pts.length <= 1) {
    map.setView([origin.lat, origin.lon], 9, { animate: false });
    return;
  }

  map.fitBounds(pts, { padding:[80,80], maxZoom: 9 });
}

['searchBox','rulerFilter','campFilter','typeFilter'].forEach(id =>
  document.getElementById(id).addEventListener('input', () => renderMap())
);
document.getElementById('resetFilter').addEventListener('click', () => {
  ['searchBox','rulerFilter','campFilter','typeFilter'].forEach(id => document.getElementById(id).value = '');
  renderMap();
});
document.getElementById('fitFiltered').addEventListener('click', fitVisible);
document.getElementById('fitAll').addEventListener('click', fitAll);
document.getElementById('focusAsia').addEventListener('click', focusAsia);
document.getElementById('confirmMoveBtn').addEventListener('click', () => {
  if (!pendingMoveTarget) return;
  const { from, to, mode } = pendingMoveTarget;
  const result = sendMoveAction(from, to, mode);
  window.__lastMoveRequest = { from, to, mode, ok: result.ok };
  pendingMoveTarget = null;
  refreshMoveConfirmUi();
});
document.getElementById('cancelMoveBtn').addEventListener('click', () => {
  pendingMoveTarget = null;
  refreshMoveConfirmUi();
  const hint = document.getElementById('confirmMoveHint');
  if (hint && selectedTown) {
    hint.innerHTML = `已取消目的地；仍以 <span class="hint-strong">${selectedTown}</span> 為移動起點，請重新選擇合法目的地。`;
  }
});
document.getElementById('directBuildBtn').addEventListener('click', () => {
  if (!selectedTown) return;
  sendDirectBuildAction(selectedTown);
});
document.getElementById('dissolveBtn').addEventListener('click', () => {
  if (!selectedTown) return;
  const supportTargetChoice = supportTargetChoiceForTown(selectedTown);
  if (supportTargetChoice) {
    sendDissolveAction(null, selectedTown);
    return;
  }
  const target = sharedDissolveTargetForTown(selectedTown);
  if (!target) return;
  sendDissolveAction(target, selectedTown);
});

map.on('click', (event) => {
  const supportTown = supportChoiceTownNearLatLng(event.latlng);
  if (supportTown) {
    selectTownForCurrentMapAction(supportTown, { autoFocus: false });
    return;
  }
  // Leaflet Canvas clicks can carry propagatedFrom even on blank map pixels.  A real
  // path/marker click has a non-map sourceTarget; only the map itself may cancel.
  if (event.sourceTarget && event.sourceTarget !== map) return;
  const hasPendingMapChoice = Boolean(supportChoiceHighlight);
  if (selectedTown && !hasPendingMapChoice) {
    exitMovementSelection();
  }
});
map.on('zoom', updateDynamicStyles);
map.on('zoomend', () => {
  if (labelMode === 'auto') renderMap(); else updateDynamicStyles();
  if (selectedTown) {
    updateStatusPanel();
  }
});
map.on('popupopen', e => {
  const node = [...currentMarkers.entries()].find(([name, marker]) => marker === e.popup._source);
  if (node) updateInfoPanel(node[0]);
});

window.addEventListener('message', (event) => {
  if (event.origin !== window.location.origin) return;
  const data = event.data || {};
  if (data.type !== 'redline-choice-highlight') return;
  applySupportChoiceHighlight(data.payload || null);
});

let initialBaseViewDone = false;

const INITIAL_VIEW_MAP_CHOICE_KEYS = new Set([
  'event_build_organization',
  'era_red_build_near_target',
  'card_build_organization',
  'support_interaction',
  'card_dissolve_interaction',
  'intel_network_dissolve_target',
  'event_red_dissolve',
  'red_army_state_security_target',
  'era_red_bonus_dissolve_target',
]);

function pendingChoiceOwnsInitialMapView(state) {
  const choice = state?.pending_choice || null;
  const choiceKey = choice?.choice_key || '';
  return !!(choice && choice.player_id === mapPlayerId && INITIAL_VIEW_MAP_CHOICE_KEYS.has(choiceKey));
}

function focusOwnBaseOnFirstState(state) {
  // 開局預設視角是整個亞洲（focusAsia），玩家每場都要自己 zoom 到根據地；
  // 改為第一份遊戲狀態進來時直接以觀看者自己的根據地為中心 zoom 9（2026-07-18 使用者需求）。
  if (initialBaseViewDone || !state || state.error) return;
  // A map-target choice can arrive before the iframe's first WebSocket state. Its candidate
  // bounds have already become the meaningful initial view, so do not overwrite that focus
  // with the viewer's base (e.g. 北京 replacing 一帶一路 南洋 candidates).
  if (pendingChoiceOwnsInitialMapView(state)) {
    initialBaseViewDone = true;
    return;
  }
  const me = (state.players || []).find(p => p.id === mapPlayerId);
  const baseTown = me && me.base ? byName.get(me.base) : null;
  if (!baseTown) return;
  map.setView([baseTown.lat, baseTown.lon], 9, { animate: false });
  initialBaseViewDone = true;
}

function applyGameStateToMap(state) {
  const resolvingMove = pendingMove && !state?.error ? { ...pendingMove } : null;
  lastGameState = state;
  focusOwnBaseOnFirstState(state);
  window.__lastMapState = state;
  const pendingChoice = state?.pending_choice || null;
  if (!pendingChoice || !INITIAL_VIEW_MAP_CHOICE_KEYS.has(pendingChoice.choice_key)) {
    applySupportChoiceHighlight(null);
  }
  if (resolvingMove) {
    pendingMove = null;
  }
  updateStatusPanel();
  if (!state || state.error) {
    if (state?.error) {
      showStickyMapPlayerError(state.error);
    }
    return;
  }
  if (!state.map || !state.map.towns) return;

  highlightLayer.clearLayers();

  markerLayer.eachLayer(layer => {
    const name = [...currentMarkers.entries()].find(([town, marker]) => marker === layer)?.[0];
    if (!name) return;

    if (layer.setStyle) {
      layer.setStyle(markerStyleForTown(name));
    }

    const baseTown = byName.get(name);
    if (baseTown) {
      layer.bindPopup(popupHtml(baseTown), { maxWidth: 380 });
      if (layer.getTooltip()) {
        layer.setTooltipContent(labelTextForTown(name));
      }
    }
  });

  if (resolvingMove) {
    finalizeMoveSelection(resolvingMove.from, resolvingMove.to);
    refreshDirectBuildUi();
    return;
  }

  if (selectedTown) {
    updateInfoPanel(selectedTown);
    renderMovementHighlights(selectedTown, { autoFocus: false });
  }
  refreshDirectBuildUi();
}

window.addEventListener('message', (event) => {
  if (!event.data) return;
  if (event.data.type === 'redline-player-error') {
    showStickyMapPlayerError(event.data.message);
    return;
  }
  if (event.data.type === 'redline-state') {
    applyGameStateToMap(event.data.state);
    return;
  }
  if (event.data.type === 'redline-choice-highlight') {
    applySupportChoiceHighlight(event.data.payload || null);
  }
});

let mapWs = null;
let mapGameId = null;
let mapPlayerId = null;

window.connectGameMap = function ({ gameId: gid, playerId: pid }) {
  mapGameId = gid;
  mapPlayerId = pid;
  if (!mapGameId || !mapPlayerId) return { ok: false, reason: 'missing-ids' };
  if (mapWs && [WebSocket.OPEN, WebSocket.CONNECTING].includes(mapWs.readyState)) {
    return { ok: true, reused: true };
  }
  if (mapWs) {
    try { mapWs.close(); } catch {}
  }

  mapWs = new WebSocket(`ws://${location.host}/ws/${mapGameId}/${mapPlayerId}`);
  mapWs.onmessage = (event) => {
    const state = JSON.parse(event.data);
    window.lastGameState = state;
    applyGameStateToMap(state);
    try {
      window.parent?.postMessage({ type: 'redline-map-state', state }, window.location.origin);
    } catch (err) {
      console.warn('Failed to sync map state to parent', err);
    }
  };

  return { ok: true };
};

window.__selectTownForTest = function (townName) {
  const marker = currentMarkers.get(townName);
  if (!marker) return { ok: false, reason: 'marker-not-found' };
  updateInfoPanel(townName);
  resetMoveSelection();
  renderMap();
  applyGameStateToMap(lastGameState);
  const didHighlight = renderMovementHighlights(townName, { autoFocus: true });
  refreshDirectBuildUi();
  window.__lastSelectedTown = townName;
  window.__lastHighlightSuccess = didHighlight;
  return {
    ok: true,
    town: townName,
    highlighted: didHighlight,
    road: movementOptionsForTown(townName).road.length,
    rail: movementOptionsForTown(townName).rail.length,
    owns: playerOwnsTown(townName),
    shared: playerHasSharedAccessToTown(townName),
    canAct: canActFromTown(townName)
  };
};

window.__moveFromToForTest = function (fromTown, toTown) {
  resetMoveSelection();
  renderMap();
  applyGameStateToMap(lastGameState);
  const highlighted = renderMovementHighlights(fromTown);
  const option = moveOptionForTown(toTown);
  if (!highlighted || !option) {
    return { ok: false, reason: 'target-not-reachable', fromTown, toTown, highlighted };
  }
  const result = sendMoveAction(fromTown, toTown, option.mode);
  return { ok: !!result.ok, fromTown, toTown, mode: option.mode };
};

window.__clickMoveTargetForTest = function (townName) {
  const marker = currentMarkers.get(townName);
  if (!marker) return { ok: false, reason: 'marker-not-found', townName };
  marker.fire('click');
  return { ok: true, townName, pendingMoveTarget: pendingMoveTarget ? { ...pendingMoveTarget } : null };
};
window.__confirmPendingMoveForTest = function () {
  const btn = document.getElementById('confirmMoveBtn');
  if (!btn || btn.disabled) return { ok: false, reason: 'confirm-disabled' };
  btn.click();
  return { ok: true };
};
window.__cancelPendingMoveForTest = function () {
  const btn = document.getElementById('cancelMoveBtn');
  if (!btn || btn.disabled) return { ok: false, reason: 'cancel-disabled' };
  btn.click();
  return { ok: true };
};
window.__mapDebugStateForTest = function () {
  return {
    selectedTown,
    pendingMoveTarget: pendingMoveTarget ? { ...pendingMoveTarget } : null,
    reachableFromSelected: selectedMoveTargets.map(t => t.town),
  };
};

window.selectTownForCurrentMapAction = selectTownForCurrentMapAction;
window.__dissolveFromSharedForTest = function (townName) {
  resetMoveSelection();
  renderMap();
  applyGameStateToMap(lastGameState);
  updateInfoPanel(townName);
  renderMovementHighlights(townName, { autoFocus: true });
  refreshDirectBuildUi();
  const defender = sharedDissolveTargetForTown(townName);
  if (!defender) {
    return { ok: false, reason: 'no-shared-dissolve-target', townName };
  }
  const result = sendDissolveAction(defender, townName);
  return { ok: !!result.ok, townName, defender };
};

window.__directBuildForTest = function (townName) {
  resetMoveSelection();
  renderMap();
  applyGameStateToMap(lastGameState);
  updateInfoPanel(townName);
  selectedTown = townName;
  refreshDirectBuildUi();
  const button = document.getElementById('directBuildBtn');
  if (!button || button.disabled) {
    return { ok: false, reason: 'direct-build-disabled', townName, eventChoice: !!eventBuildChoiceForTown(townName) };
  }
  const result = sendDirectBuildAction(townName);
  return { ok: !!result.ok, townName, eventChoice: !!result.eventChoice, index: result.index };
};

window.__advanceToActionForTest = function () {
  if (!mapWs || mapWs.readyState !== WebSocket.OPEN) return { ok: false, reason: 'socket-not-open' };
  mapWs.send(JSON.stringify({ action: 'advance' }));
  return { ok: true };
};

async function bootstrapCanonicalGameMap() {
  const bundle = await window.loadRedlineMapBundle();
  initializeCanonicalMapData(bundle.mapData, bundle.geoCoordinates);
  renderMap();
  if (lastGameState) applyGameStateToMap(lastGameState);
  setTimeout(focusAsia, 100);
  await loadFactionMeta();
  return { towns: towns.length, links: links.length };
}

window.__redlineMapDataReady = bootstrapCanonicalGameMap().catch(error => {
  console.error('Failed to initialize canonical Redline map data', error);
  const hint = document.getElementById('interactionHint');
  const detail = playerMessageZhTw(error?.message, '請重新整理頁面後再試。');
  if (hint) hint.textContent = `地圖資料載入失敗：${detail}`;
  throw error;
});
