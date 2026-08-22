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

function baseFactionIdForTown(name) {
  const owner = (lastGameState?.players || []).find(p => p?.base === name);
  return owner?.faction || null;
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
const armoryBadgeLayer = L.layerGroup().addTo(map);
const baseBadgeLayer = L.layerGroup().addTo(map);
const highlightLayer = L.layerGroup().addTo(map);
const supportChoiceHighlightLayer = L.layerGroup().addTo(map);
let labelMode = 'auto', showRoad = true, showRail = true;
let currentMarkers = new Map();
let currentSharedBadges = new Map();
let currentArmoryBadges = new Map();
let currentBaseBadges = new Map();
let currentVisible = towns.map(t=>t.name);
let lastGameState = null;
let selectedTown = null;
let selectedMoveTargets = [];
let pendingMove = null;
let pendingMoveTarget = null;
let lastResolvedMove = null;
let stickyPlayerErrorMessage = '';
let stickyPlayerErrorTimer = null;
const MAP_SOCKET_DISCONNECTED_MESSAGE = '與伺服器的連線已中斷，正在自動重新連線；連上後請再按一次。';
let supportChoiceHighlight = null;
let supportChoiceHighlightFocusKey = null;
// The first build-card choice in a loaded game may frame all legal targets so the player can
// discover the interaction. After that, the player's current center/zoom is authoritative across
// separate build-card sessions. Candidate markers still refresh, but a later card must not fit all
// geographically distant targets (for example 香港城 + 洛杉磯) and zoom back out to the world.
let buildChoiceViewportInitialized = false;

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

function supportChoiceHighlightKey(payload) {
  if (!payload || payload.mode !== 'support-targets') return null;
  // 這個 key 只用來判斷「是不是同一個互動 session 的延續」，藉此決定要不要重新
  // fitBounds／setView 搶奪使用者當下的地圖鏡頭。刻意排除 towns／prompt／focusTown／
  // sourceName——同一個 session 內（連續建立多個組織、或連續瓦解多個目標）這幾個欄位
  // 本來就會隨每次成功動作而改變：例如 card_build_organization 的 prompt 會嵌入
  // 「尚可建立 N 個」；更關鍵的是，玩家疊加打出「多張」不同的建立組織卡（例如先組織
  // 經驗丙、再組織經驗乙）時，伺服器會把兩者的建立額度合併成同一個連續 session，但
  // 目前正在作用中的那一批額度用完、換下一批接手時，`source_name` 會從第一張牌的
  // 名字換成第二張牌的名字（同一個 session、同一個 choiceKey，只是 sourceName 換了）
  // ——這正是 2026-08-02 實測抓到的成因：若把 sourceName 也算進 key，換牌那一刻會被
  // 誤判成「新的 session」而重新搶鏡頭，把玩家剛手動調整好的視角沖掉。只有
  // mode/actionKind/choiceKey 這三個在整個連續 session 內保證不變的欄位才代表
  // 「這是不是同一次互動」；session 真正結束時 payload 會變成 null（見
  // applySupportChoiceHighlight），下一個 session 開始時 key 自然會與 null 不同而重新聚焦。
  return JSON.stringify({
    mode: payload.mode,
    actionKind: payload.actionKind || '',
    choiceKey: payload.choiceKey || '',
  });
}

function focusSupportChoiceTargets(bounds) {
  if (!bounds.length) return;
  // 一帶一路南洋有 11 個合法目標，從緬北延伸到雅加達與馬尼拉。把所有點連同
  // 110px padding 一起 fitBounds 會縮到 zoom 3，畫面包含印度、中國與澳洲大片區域，
  // 反而看不清主要南洋城鎮。此事件首次開啟地圖時固定聚焦南洋核心；所有候選 marker
  // 仍完整保留，玩家可平移至雅加達、馬尼拉或北部邊緣目標。
  if (isBeltRoadNanyangSupportChoice()) {
    map.setView([8, 104], 5, { animate: false });
    return;
  }
  if (bounds.length === 1) {
    const currentZoom = Number(map.getZoom());
    map.setView(bounds[0], Math.max(Number.isFinite(currentZoom) ? currentZoom : 4, 8), { animate: false });
    return;
  }
  map.fitBounds(bounds, { padding: [110, 110], maxZoom: 8 });
}

function selectTownForCurrentMapAction(townName, options = {}) {
  const { autoFocus = true } = options;
  updateInfoPanel(townName);
  resetMoveSelection();
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

function isBeltRoadNanyangSupportChoice() {
  return supportChoiceHighlight?.actionKind === 'build'
    && supportChoiceHighlight?.choiceKey === 'event_build_organization'
    && supportChoiceHighlight?.region === 'southeast_asia'
    && supportChoiceHighlight?.sourceName === '一帶一路 南洋';
}

function isDissolveSupportChoiceHighlight() {
  return !!supportChoiceHighlight && supportChoiceHighlight.actionKind === 'dissolve';
}

function renderSupportChoiceHighlights(options = {}) {
  const { autoFocus = false } = options;
  supportChoiceHighlightLayer.clearLayers();
  if (!supportChoiceHighlight || supportChoiceHighlight.mode !== 'support-targets') return false;
  const towns = Array.isArray(supportChoiceHighlight.towns) ? supportChoiceHighlight.towns : [];
  const bounds = [];
  let focusedBounds = null;
  const isDissolveChoice = isDissolveSupportChoiceHighlight();
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
    if (isDissolveChoice) {
      // 瓦解目標：後端判定的合法目標以 💀 標示，但點擊只會「選取」該城鎮
      // （與建立組織候選城鎮的既有互動一致），必須再按左側「瓦解目前城鎮（效果）」
      // 按鈕才會真正執行瓦解。2026-08-02 使用者回饋：單擊直接瓦解對新手太危險——
      // 玩家常只是想點點看，不該不小心觸發不可逆動作，因此改為選取＋明確按鈕確認
      // 兩步驟，選中的目標會以 dissolve-target-badge-armed 樣式標示為「已選取待確認」。
      const selectClick = () => selectTownForCurrentMapAction(townName, { autoFocus: false });
      const isArmed = selectedTown === townName;
      const hitArea = L.circleMarker([town.lat, town.lon], {
        radius: Math.max(isFocused ? 20 : 16, markerRadius(map.getZoom()) + (isFocused ? 12 : 8)),
        color: isArmed ? '#fde68a' : (isFocused ? '#fecaca' : '#f87171'),
        weight: isArmed ? 4 : (isFocused ? 3 : 2),
        fillColor: '#ef4444',
        fillOpacity: isFocused ? 0.3 : 0.16,
        opacity: 1,
      }).addTo(supportChoiceHighlightLayer)
        .bindPopup(`${escapeHtml(supportChoiceHighlight.sourceName || '可瓦解目標')}：${escapeHtml(entry?.label || townName)}（點擊選取，再按左側按鈕確認瓦解）`);
      hitArea.on('click', selectClick);
      const skullMarker = L.marker([town.lat, town.lon], {
        zIndexOffset: 1000,
        icon: L.divIcon({
          className: 'dissolve-target-badge-wrap',
          html: `<div class="dissolve-target-badge${isFocused ? ' dissolve-target-badge-focused' : ''}${isArmed ? ' dissolve-target-badge-armed' : ''}">💀</div>`,
          iconSize: [26, 26],
          iconAnchor: [13, 13],
        }),
      }).addTo(supportChoiceHighlightLayer);
      skullMarker.on('click', selectClick);
      return;
    }
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
        : isDissolveChoice
          ? '請點選 💀 標示的組織，再使用左側「瓦解目前城鎮（效果）」按鈕確認完成瓦解。'
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
      const markerDescText = isDissolveChoice ? '地圖上已用 💀 標出可瓦解的合法目標，點選後請於左側按鈕確認。' : '地圖上已用中性色外框標出可選城鎮。';
      hintEl.innerHTML = `${sourceLabel}：<span class="hint-strong">${escapeHtml(promptText)}</span> ${countText}${markerDescText}${escapeHtml(focusText)}${actionText}`;
    }
    if (autoFocus) {
      focusSupportChoiceTargets(focusedBounds || bounds);
      return true;
    }
  }
  return false;
}

function applySupportChoiceHighlight(payload) {
  const nextKey = supportChoiceHighlightKey(payload);
  supportChoiceHighlight = payload || null;
  const isBuildChoice = isBuildSupportChoiceHighlight();
  const shouldAutoFocus = !!nextKey
    && nextKey !== supportChoiceHighlightFocusKey
    && (!isBuildChoice || !buildChoiceViewportInitialized || isBeltRoadNanyangSupportChoice());
  if (!nextKey) supportChoiceHighlightFocusKey = null;
  const didAutoFocus = renderSupportChoiceHighlights({ autoFocus: shouldAutoFocus });
  // 只有實際找到地圖座標並完成 setView／fitBounds 後才記錄已聚焦。若 choice 比
  // /map-data 更早抵達，保留 null，讓地圖資料完成初始化時再試一次。
  if (didAutoFocus) {
    supportChoiceHighlightFocusKey = nextKey;
    if (isBuildChoice) buildChoiceViewportInitialized = true;
  }
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
      hintEl.innerHTML = '連上遊戲後，只有 <span class="hint-strong">當前玩家自己擁有組織</span> 的城鎮可以高亮合法移動；若城鎮具有共享組織，會以 <span class="hint-strong">金色外框與 S 標記</span> 顯示。';
    } else if (eventBuildChoiceForTown(selectedTown)) {
      hintEl.innerHTML = `已選取 <span class="hint-strong">${selectedTown}</span>：事件卡效果允許在此建立組織，請使用左側「在目前城鎮建立組織（事件卡）」按鈕完成。`;
    } else if (playerOwnsTown(selectedTown)) {
      const opts = movementOptionsForTown(selectedTown);
      const destinationCount = new Set([...opts.road, ...opts.rail].map(entry => entry.town)).size;
      const sharedHint = playerHasSharedAccessToTown(selectedTown) ? ' 此城鎮也處於共享組織狀態。' : '';
      hintEl.innerHTML = `已選取 <span class="hint-strong">${selectedTown}</span>：合法移動目的地 ${destinationCount} 個。` + sharedHint;
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

function clearStickyMapPlayerError() {
  if (stickyPlayerErrorTimer) {
    clearTimeout(stickyPlayerErrorTimer);
    stickyPlayerErrorTimer = null;
  }
  stickyPlayerErrorMessage = '';
  updateStatusPanel();
}

/** 送出任何盤面動作前的連線守門：連線已斷時不再靜默 return，而是明確告知玩家並立刻重連。 */
function requireOpenMapSocket() {
  if (mapSocketIsOpen()) return true;
  showStickyMapPlayerError(MAP_SOCKET_DISCONNECTED_MESSAGE, 8000);
  reconnectMapSocketNow();
  return false;
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
  armoryBadgeLayer.clearLayers();
  baseBadgeLayer.clearLayers();
  highlightLayer.clearLayers();
  currentSharedBadges.forEach(marker => {
    try { map.removeLayer(marker); } catch {}
  });
  currentMarkers = new Map();
  currentSharedBadges = new Map();
  currentArmoryBadges = new Map();
  currentBaseBadges = new Map();
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

  // 根據地城鎮的圓圈外框改用該根據地陣營的代表色，讓根據地在地圖上比其他一般城鎮更
  // 醒目；有共享組織可用時仍優先顯示黃色提示。2026-08-17 使用者實測回饋：光是換色／
  // 加粗外框看不太出來，因為根據地標示（🏕，28px 方形背景，見
  // renderParticipatingFactionBaseBadges）幾乎跟圓圈同大甚至更大，會整個蓋住外框——
  // 真正有效的做法是加大圓圈半徑，讓外框整圈清楚露在 28px 標示背景之外；標示本身大小
  // 與外框粗細都維持不變。
  const baseFactionId = baseFactionIdForTown(name);
  const baseColor = baseFactionId ? factionCampColor(baseFactionId) : null;
  const baseRadiusBoost = (baseColor && !hasShared) ? 8 : 0;
  const strokeWeight = hasShared
    ? Math.max(base.weight + 2.5, 3.5)
    : (ownedByCurrent ? Math.max(base.weight + 1.5, 3) : Math.max(base.weight + 0.5, 2));

  return {
    radius: Math.max(base.radius + (hasShared ? 3 : 2), hasShared ? 9 : 8) + baseRadiusBoost,
    color: hasShared ? '#facc15' : (baseColor || (ownedByCurrent ? '#f8fafc' : '#cbd5e1')),
    weight: strokeWeight,
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
  const ownerPlayer = (lastGameState?.players || []).find(player => player.name === owner);
  if (ownerPlayer?.base === townName && ownerPlayer?.faction !== 'red_army') return null;
  return owner;
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

// 安全屋是被動能力（資料 type: "passive"），只會在「玩家用正常方式建立組織時」把可建立
// 距離 +1，不該有自己的按鈕、面板或地圖高亮捷徑。原本這裡的 playerHasSafehouse()／
// buildOptionsForTown() 會在香港玩家點選自己城鎮時直接標出額外候選、點下去就免出牌建組織，
// 等於把被動能力做成主動動作，已整組移除；安全屋的 +1 只保留在後端卡牌／奧援建立候選清單
// （Game._card_build_town_choices()／_interactive_support_build_towns()）。

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
  // renderMap() 呼叫 renderSupportChoiceHighlights() 的時間點早於這裡設定 selectedTown，
  // 因此瓦解 💀 標記的「已選取待確認」樣式需要在這裡再刷新一次，才能反映最新選取
  // （2026-08-02：瓦解確認流程改為選取＋按鈕兩步驟後新增）。
  renderSupportChoiceHighlights();
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
  return highlightCount > 0 || sharedOnly;
}

function moveOptionForTown(townName) {
  return selectedMoveTargets.find(item => item.town === townName) || null;
}

function sendMoveAction(fromTown, toTown, mode) {
  if (!requireOpenMapSocket()) {
    pendingMove = { from: fromTown, to: toTown, mode, error: MAP_SOCKET_DISCONNECTED_MESSAGE };
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
  if (!requireOpenMapSocket()) {
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
  if (!requireOpenMapSocket()) {
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
  const hint = document.getElementById('confirmMoveHint');
  if (!confirmBtn || !hint) return;

  if (!pendingMoveTarget) {
    confirmBtn.disabled = true;
    hint.innerHTML = '點選可移動城鎮後，這裡會顯示移動確認。';
    return;
  }

  confirmBtn.disabled = false;
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
    dissolveBtn.textContent = '確認瓦解此組織';
    dissolveHint.innerHTML = `確認瓦解 <span class="hint-strong">${selectedTown}</span> 的組織？（${supportChoiceHighlight.sourceName || '目前效果'}）點擊地圖上其他 💀 目標可改選，按上方按鈕才會真正執行。`;
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
  currentArmoryBadges.forEach((badge, townName) => {
    const town = byName.get(townName);
    if (!town || !badge.setLatLng) return;
    badge.setLatLng([town.lat, town.lon]);
  });
  renderSupportChoiceHighlights();
}

function renderParticipatingFactionBaseBadges() {
  const basePlayersByTown = new Map();
  for (const player of (lastGameState?.players || [])) {
    if (!player?.base || !player?.faction || !byName.has(player.base)) continue;
    if (!basePlayersByTown.has(player.base)) basePlayersByTown.set(player.base, []);
    basePlayersByTown.get(player.base).push(player);
  }

  basePlayersByTown.forEach((playersAtBase, townName) => {
    const town = byName.get(townName);
    playersAtBase.forEach((player, index) => {
      const factionName = factionLabel(player.faction) || player.faction;
      const tooltip = `${factionName}根據地：${townName}`;
      const badge = L.marker([town.lat, town.lon], {
        interactive: true,
        keyboard: false,
        zIndexOffset: 800 + index,
        icon: L.divIcon({
          className: 'base-badge-wrap',
          html: `<div class="base-badge" data-base-faction="${escapeHtml(player.faction)}" data-base-town="${escapeHtml(townName)}" title="${escapeHtml(tooltip)}">🏕</div>`,
          iconSize: [28, 28],
          // 根據地置中疊在城鎮圓圈正中央（軍火庫 🧨 維持右上）；瓦解 💀 的 zIndexOffset
          // （1000）高於這裡的 800+index，兩者座標重合時 💀 會直接蓋過根據地標示——
          // 這正是「北京可被瓦解時要用 💀 蓋過根據地圖示」要的效果，不需要另外處理。
          iconAnchor: [14 + index * 10, 14],
        })
      }).bindTooltip(tooltip, { direction: 'top', offset: [0, -18] }).addTo(baseBadgeLayer);
      badge.__redlineBaseTown = townName;
      currentBaseBadges.set(player.id || `${player.faction}:${townName}:${index}`, badge);
    });
  });
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
    if (t.type === '軍火庫' && !currentArmoryBadges.has(t.name)) {
      const armoryBadge = L.marker([t.lat, t.lon], {
        interactive: false,
        keyboard: false,
        zIndexOffset: 600,
        icon: L.divIcon({
          className: 'armory-badge-wrap',
          html: `<div class="armory-badge" data-armory-town="${escapeHtml(t.name)}" title="${escapeHtml(t.name)}：軍火庫">🧨</div>`,
          iconSize: [24, 24],
          // Keep 🧨 above-right of the town. Dissolve 💀 remains centred, so both
          // permanent town type and temporary target state stay visible together.
          iconAnchor: [-3, 25],
        })
      }).addTo(armoryBadgeLayer);
      currentArmoryBadges.set(t.name, armoryBadge);
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

      // While choosing a movement destination, clicking an unrelated town is treated the
      // same as clicking empty map background: cancel the whole selection (2026-08-05
      // 使用者需求，「點地圖其他任意地方就取消」，比照 map.on('click') 對空白背景已有的
      // exitMovementSelection() 行為，讓「哪裡算取消」保持一致，不分背景或不相關城鎮).
      // Another own/shared organization may still become a new origin instead of a cancel.
      if (selectedTown && selectedMoveTargets.length) {
        if (canActFromTown(t.name)) {
          selectTownForCurrentMapAction(t.name, { autoFocus: true });
        } else {
          exitMovementSelection();
        }
        return;
      }

      selectTownForCurrentMapAction(t.name, { autoFocus: true });
    });
    currentMarkers.set(t.name, marker);
    if (shouldShowLabels()) marker.bindTooltip(labelTextForTown(t.name), townLabelOptions(t.name));
  });

  renderParticipatingFactionBaseBadges();
  updateDynamicStyles();
  if (selectedTown) {
    renderMovementHighlights(selectedTown, { autoFocus: false });
  }
  renderSupportChoiceHighlights();
}

function medianNumber(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

function coreClusterTowns(entries) {
  // 2026-08-18 使用者回饋：陣營篩選（例如香港）聚焦後中心點雖然對了，縮放程度還是不夠
  // 近——因為縮放層級沿用「全部篩選結果」（含河內／胡志明／臺灣等同樣合法但明顯偏遠的
  // 據點）算出來的 bounds。篩選結果本身仍要完整保留（使用者要求河內/胡志明/臺灣不能被
  // 排除在外），只是聚焦計算要更看重主要群集：以座標中位數為聚焦中心，用「與中心的距離
  // 中位數」代表主要群集的典型半徑（對離群點本身就穩健，不會被單一極端離群點——例如
  // 曾經實測到的「倫敦」——拉歪），距離超過典型半徑一定倍數的城鎮視為明顯偏遠據點，
  // 聚焦計算時排除，但仍完整顯示在地圖上供玩家平移查看。城鎮本來就分布均勻、切不出明顯
  // 主要群集時，篩選結果會全部落在門檻內，等同於沿用全部結果，不會強行拆分。
  if (entries.length <= 2) return entries;
  const centerLat = medianNumber(entries.map(t => t.lat));
  const centerLon = medianNumber(entries.map(t => t.lon));
  const withDist = entries.map(t => ({ town: t, dist: Math.hypot(t.lat - centerLat, t.lon - centerLon) }));
  const typicalRadius = medianNumber(withDist.map(e => e.dist)) || 0;
  const threshold = Math.max(typicalRadius * 4, 0.5);
  const core = withDist.filter(e => e.dist <= threshold).map(e => e.town);
  return core.length ? core : entries;
}

function fitVisible() {
  const visibleTowns = currentVisible.map(n => byName.get(n)).filter(Boolean);
  const pts = visibleTowns.map(t => [t.lat, t.lon]);
  if (!pts.length) return;

  const faction = document.getElementById('campFilter').value;
  if (faction) {
    // 陣營發展範圍通常含少數海外據點。直接 fitBounds 會被離群點拉回亞洲
    // 全圖，讓「聚焦結果」看起來完全沒有反應。聚焦中心與縮放層級都只依主要群集
    // （coreClusterTowns）計算，並保證至少 zoom 4；篩選結果（含離群據點）仍完整
    // 保留在地圖上，玩家可平移查看。
    const coreTowns = coreClusterTowns(visibleTowns);
    const corePts = coreTowns.map(t => [t.lat, t.lon]);
    const bounds = L.latLngBounds(corePts);
    const fittedZoom = map.getBoundsZoom(bounds, false, L.point(30, 30));
    const targetZoom = Math.min(9, Math.max(4, Number.isFinite(fittedZoom) ? fittedZoom : 4));
    const targetCenter = [
      medianNumber(coreTowns.map(t => t.lat)),
      medianNumber(coreTowns.map(t => t.lon)),
    ];
    window.__lastFilterFocus = {
      faction,
      resultCount: visibleTowns.length,
      coreCount: coreTowns.length,
      strategy: 'median-cluster',
      targetCenter,
      targetZoom,
    };
    map.flyTo(targetCenter, targetZoom, { animate: true, duration: 0.45 });
    return;
  }

  window.__lastFilterFocus = {
    faction: null,
    resultCount: visibleTowns.length,
    strategy: 'fit-all-results',
  };
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
  const pts = [[origin.lat, origin.lon]];
  [...moveOptions.road, ...moveOptions.rail].forEach(option => {
    const t = byName.get(option.town);
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
let mapResumeToken = null;
let mapSocketReconnectTimer = null;
let mapSocketReconnectAttempts = 0;
let mapSocketLifecycleBound = false;

function mapSocketIsOpen() {
  return !!mapWs && mapWs.readyState === WebSocket.OPEN;
}

// 戰略地圖 iframe 自己維持一條 WebSocket。它過去完全沒有 onclose／重連，只要連線斷過一次
// （伺服器重啟、筆電睡眠喚醒、網路閃斷，或伺服器端 broadcast 對某個已死連線丟出例外時
// 連帶關掉本連線），這條 socket 就永遠是 CLOSED。此時父頁 app.js 仍有自己的 scheduleReconnect
// 會重連，指揮中心看起來一切正常，選擇提示也照樣 postMessage 進地圖 → 候選城鎮亮著、
// 「在目前城鎮建立組織（效果）」按鈕也照樣 enabled，但按下去只會走到 sendDirectBuildAction()
// 的 socket-not-open 分支靜默 return，玩家完全看不到任何錯誤。
// （2026-08-08 playtest 回報：組織經驗丙選好廈門、按鈕亮著，按下去卻沒有建立組織。）
function scheduleMapSocketReconnect(reason = 'closed') {
  if (!mapGameId || !mapPlayerId) return;
  if (mapSocketReconnectTimer) return;
  if (mapWs && [WebSocket.OPEN, WebSocket.CONNECTING].includes(mapWs.readyState)) return;
  const delay = Math.min(8000, 500 * (2 ** Math.min(mapSocketReconnectAttempts, 4)));
  mapSocketReconnectAttempts += 1;
  console.warn(`戰略地圖連線${reason}，${delay}ms 後自動重連`);
  mapSocketReconnectTimer = setTimeout(() => {
    mapSocketReconnectTimer = null;
    openMapSocket();
  }, delay);
}

function reconnectMapSocketNow() {
  if (mapSocketReconnectTimer) {
    clearTimeout(mapSocketReconnectTimer);
    mapSocketReconnectTimer = null;
  }
  mapSocketReconnectAttempts = 0;
  return openMapSocket();
}

function bindMapSocketLifecycle() {
  if (mapSocketLifecycleBound) return;
  mapSocketLifecycleBound = true;
  window.addEventListener('online', () => reconnectMapSocketNow());
  window.addEventListener('pageshow', () => {
    if (!mapSocketIsOpen()) reconnectMapSocketNow();
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !mapSocketIsOpen()) reconnectMapSocketNow();
  });
}

function openMapSocket() {
  if (!mapGameId || !mapPlayerId) return { ok: false, reason: 'missing-ids' };
  if (mapWs && [WebSocket.OPEN, WebSocket.CONNECTING].includes(mapWs.readyState)) {
    return { ok: true, reused: true };
  }
  if (mapWs) {
    try { mapWs.close(); } catch {}
  }

  const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socketUrl = `${wsProtocol}//${location.host}/ws/${mapGameId}/${mapPlayerId}`;
  const socket = mapResumeToken ? new WebSocket(socketUrl, mapResumeToken) : new WebSocket(socketUrl);
  mapWs = socket;
  socket.onopen = () => {
    mapSocketReconnectAttempts = 0;
    if (stickyPlayerErrorMessage === MAP_SOCKET_DISCONNECTED_MESSAGE) {
      clearStickyMapPlayerError();
    }
  };
  socket.onmessage = (event) => {
    const state = JSON.parse(event.data);
    window.lastGameState = state;
    applyGameStateToMap(state);
    try {
      window.parent?.postMessage({ type: 'redline-map-state', state }, window.location.origin);
    } catch (err) {
      console.warn('Failed to sync map state to parent', err);
    }
  };
  socket.onclose = () => {
    if (mapWs === socket) mapWs = null;
    scheduleMapSocketReconnect('中斷');
  };
  socket.onerror = () => {
    try { socket.close(); } catch {}
  };
  bindMapSocketLifecycle();
  return { ok: true };
}

window.__armoryBadgeDiagnosticsForTest = function () {
  return [...currentArmoryBadges.entries()].map(([townName, badge]) => {
    const town = byName.get(townName);
    const latLng = badge.getLatLng();
    const townPoint = map.latLngToContainerPoint([town.lat, town.lon]);
    const element = badge.getElement();
    const rect = element?.getBoundingClientRect();
    const mapRect = map.getContainer().getBoundingClientRect();
    return {
      town: townName,
      zoom: map.getZoom(),
      townLat: town.lat,
      townLon: town.lon,
      badgeLat: latLng.lat,
      badgeLon: latLng.lng,
      screenOffsetX: rect ? (rect.left + rect.width / 2) - (mapRect.left + townPoint.x) : null,
      screenOffsetY: rect ? (rect.top + rect.height / 2) - (mapRect.top + townPoint.y) : null,
    };
  });
};
window.__armoryDissolveCoexistenceForTest = function (townName) {
  const armory = document.querySelector(`[data-armory-town="${CSS.escape(townName)}"]`);
  const skull = document.querySelector('.dissolve-target-badge');
  return {
    armoryVisible: !!armory && getComputedStyle(armory).visibility !== 'hidden',
    skullVisible: !!skull && getComputedStyle(skull).visibility !== 'hidden',
    armoryText: armory?.textContent || '',
    skullText: skull?.textContent || '',
  };
};

window.connectGameMap = function ({ gameId: gid, playerId: pid, resumeToken: token = null }) {
  const isDifferentGameOrPlayer = mapGameId !== gid || mapPlayerId !== pid;
  if (isDifferentGameOrPlayer) {
    supportChoiceHighlight = null;
    supportChoiceHighlightFocusKey = null;
    buildChoiceViewportInitialized = false;
    initialBaseViewDone = false;
  }
  mapGameId = gid;
  mapPlayerId = pid;
  mapResumeToken = token;
  if (!mapGameId || !mapPlayerId) return { ok: false, reason: 'missing-ids' };
  return openMapSocket();
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
window.__mapDebugStateForTest = function () {
  return {
    selectedTown,
    pendingMoveTarget: pendingMoveTarget ? { ...pendingMoveTarget } : null,
    reachableFromSelected: selectedMoveTargets.map(t => t.town),
    socketOpen: mapSocketIsOpen(),
    reconnectAttempts: mapSocketReconnectAttempts,
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
  if (!mapSocketIsOpen()) return { ok: false, reason: 'socket-not-open' };
  mapWs.send(JSON.stringify({ action: 'advance' }));
  return { ok: true };
};

async function bootstrapCanonicalGameMap() {
  const bundle = await window.loadRedlineMapBundle();
  initializeCanonicalMapData(bundle.mapData, bundle.geoCoordinates);
  renderMap();
  if (lastGameState) applyGameStateToMap(lastGameState);
  // 新遊戲首次開啟戰略地圖時，choice 可能比地圖資料先抵達。地圖資料完成後要重新
  // 嘗試一次候選範圍聚焦；預設亞洲視角只能在沒有待處理地圖 choice 時執行，否則
  // 延遲的 focusAsia 會把剛完成的宣傳家 setView 沖掉。
  applySupportChoiceHighlight(supportChoiceHighlight);
  setTimeout(() => {
    if (supportChoiceHighlight) {
      applySupportChoiceHighlight(supportChoiceHighlight);
    } else {
      focusAsia();
    }
  }, 100);
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
