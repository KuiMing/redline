/*
 * 戰略地圖 iframe 端的 controller adapter。
 * 與 parent 的 controller_ui.js 以 postMessage 溝通（協定見 docs/joycon_controller.md）。
 * 焦點集合只由 leaflet_game_map_logic.js 持有的伺服器權威資料建立；每個指令在執行當下重新驗證，
 * 因此 parent 送來過期或偽造的目標也不會讓非法目標可 action。
 */
(function () {
  'use strict';
  const Core = window.RedlineControllerCore;
  if (!Core) return;

  let snapSeq = 0;
  let focusTown = null;
  let focusLayer = null;
  let pushTimer = null;

  function buttonInfo(id) {
    const el = document.getElementById(id);
    if (!el) return { id, visible: false, disabled: true, label: '' };
    const rect = el.getBoundingClientRect();
    const visible = el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    return { id, visible, disabled: el.disabled === true, label: (el.textContent || '').trim(), rect };
  }

  function currentModel() {
    const state = lastGameState;
    const hasState = !!(state && !state.error && state.map && state.map.towns && mapPlayerId);
    const viewer = hasState ? (state.players || []).find(p => p.id === mapPlayerId) : null;
    const viewerCanAct = !!viewer && viewer.name === currentPlayerName();
    const highlight = supportChoiceHighlight && supportChoiceHighlight.mode === 'support-targets'
      ? supportChoiceHighlight : null;
    const originTowns = viewerCanAct ? currentVisible.filter(name => canActFromTown(name)) : [];
    const buttons = Core.MAP_BUTTON_IDS.map(buttonInfo);
    const model = Core.buildMapSnapshotModel({
      hasState,
      viewerCanAct,
      pendingChoiceBlocksMoves: !!(state && state.pending_choice) && !highlight,
      highlight,
      visibleTowns: currentVisible,
      knownTowns: [...byName.keys()],
      moveTargets: selectedTown ? selectedMoveTargets : [],
      selectedTown,
      pendingMoveTarget,
      originTowns,
      // 既有「瓦解組織」按鈕對共享組織的判定（sharedDissolveTargetForTown）：只有這些來源有 Y 瓦解。
      dissolveOrigins: originTowns.filter(name => !!sharedDissolveTargetForTown(name)),
      buttons,
    });
    return { model, buttons: new Map(buttons.map(b => [b.id, b])) };
  }

  /**
   * B 的既有可取消流程。城鎮說明 popup 開著時第一下 B 只關閉說明（'popup'）：不取消選取、預備移動、pending choice，
   * 也不讓 parent 退出地圖；關閉後才回到「取消瓦解」→「取消目前選取」的既有順序。
   */
  function cancelAvailable(info) {
    if (townDetailOpenTown()) return 'popup';
    const cancelBtn = info.buttons.get('cancelDissolveChoiceBtn');
    if (cancelBtn && cancelBtn.visible && !cancelBtn.disabled) return 'cancelDissolveChoiceBtn';
    if (selectedTown) return 'selection';
    return null;
  }

  /**
   * req：只有回應帶 req 的 `snapshot` 指令時才帶（parent 的 SL 聚焦選單只採用對上自己 req 的那一份，避免用到過期推送）。
   * browseTowns 是與 action targets 分離的完整 canonical 導覽清單；缺資料時不宣告 browseMeta，parent 的 SL 選單 fail closed。
   * targets 與既有 groupMeta 保留給 pending target 路徑，兩者互不改寫。
   */
  function snapshotMessage(req) {
    const info = currentModel();
    const mapEl = document.getElementById('map');
    const origin = mapEl ? mapEl.getBoundingClientRect() : { left: 0, top: 0 };
    const targets = [];
    const groups = [];
    for (const t of info.model.targets) {
      const town = byName.get(t.town);
      if (!town) continue;
      const p = map.latLngToContainerPoint(townDisplayLatLng(town));
      const target = { town: t.town, role: t.role, x: origin.left + p.x, y: origin.top + p.y };
      if (t.mode !== undefined && t.mode !== null) target.mode = t.mode;
      if (t.cost !== undefined && t.cost !== null) target.cost = t.cost;
      if (t.act) target.act = t.act;
      targets.push(target);
      groups.push(Core.townGroupMeta(town));
    }
    const groupMeta = groups.every(Boolean);
    if (groupMeta) targets.forEach((target, i) => { target.ruler = groups[i].ruler; target.camp = groups[i].camp; });
    // SL 全域聚焦選單：canonical 地圖的全部城鎮（不受 pending choice、目標或篩選影響）；任一城鎮缺分組資料就整份不帶。
    const browseTowns = [];
    for (const town of towns) {
      const meta = Core.townGroupMeta(town);
      if (!meta) { browseTowns.length = 0; break; }
      browseTowns.push({ town: town.name, ruler: meta.ruler, camp: meta.camp });
    }
    const buttons = info.model.buttons.map(b => {
      const r = info.buttons.get(b.id).rect;
      return { id: b.id, label: b.label || b.id, x: r.left, y: r.top, w: r.width, h: r.height };
    });
    snapSeq += 1;
    return {
      type: 'redline-controller-map-snapshot',
      v: Core.MAP_MESSAGE_VERSION,
      seq: snapSeq,
      scope: info.model.scope,
      targets,
      buttons,
      focusTown: focusTown && targets.some(t => t.town === focusTown) ? focusTown : info.model.focusTown,
      canCancel: !!cancelAvailable(info),
      detail: townDetailOpenTown(),
      selected: info.model.selected,
      pending: info.model.pending,
      ...(groupMeta ? { groupMeta: Core.MAP_GROUP_META_VERSION } : {}),
      ...(browseTowns.length === towns.length && browseTowns.length
        ? { browseMeta: Core.MAP_BROWSE_META_VERSION, browseTowns } : {}),
      ...(Core.isRequestId(req) ? { req } : {}),
    };
  }

  function postToParent(message) {
    try {
      if (window.parent && window.parent !== window) window.parent.postMessage(message, window.location.origin);
    } catch (err) {
      console.warn('controller adapter: postMessage failed', err);
    }
  }

  function pushSnapshot(req) {
    pushTimer = null;
    postToParent(snapshotMessage(req));
  }

  // 任何地圖狀態變更都排一次（合併）推送；parent 只用它來畫焦點，真正執行時 iframe 會重驗。
  function scheduleSnapshot() {
    if (pushTimer !== null) return;
    pushTimer = setTimeout(pushSnapshot, 0);
  }

  function drawFocusRing() {
    if (!focusLayer) focusLayer = L.layerGroup().addTo(map);
    focusLayer.clearLayers();
    if (!focusTown) return;
    const town = byName.get(focusTown);
    if (!town) return;
    const ll = townDisplayLatLng(town);
    const radius = Math.max(22, markerRadius(map.getZoom()) + 16);
    L.circleMarker(ll, { radius: radius + 3, color: '#000000', weight: 9, fill: false, opacity: 0.9, interactive: false }).addTo(focusLayer);
    L.circleMarker(ll, { radius, color: '#ffe14d', weight: 5, fill: false, opacity: 1, interactive: false }).addTo(focusLayer);
    L.marker(ll, {
      interactive: false, keyboard: false, zIndexOffset: 2000,
      icon: L.divIcon({ className: 'pad-focus-label-wrap', html: `<div class="pad-focus-label">${escapeHtml(focusTown)}</div>`, iconSize: [0, 0], iconAnchor: [0, 36] }),
    }).addTo(focusLayer);
  }

  function setFocus(townName) {
    const { model } = currentModel();
    if (!model.targets.some(t => t.town === townName)) return { ok: false, reason: 'not-a-target' };
    focusTown = townName;
    const town = byName.get(townName);
    const ll = townDisplayLatLng(town);
    if (!map.getBounds().pad(-0.1).contains(ll)) map.panInside(ll, { padding: [90, 90], animate: false });
    drawFocusRing();
    return { ok: true };
  }

  function finiteLatLng(ll) { return !!ll && Number.isFinite(ll.lat) && Number.isFinite(ll.lng); }

  /**
   * SL 全域地圖聚焦：canonical 城鎮（/map-data，不限 action target）精確置中，並放大到固定層級 Core.mapFocusZoom
   * （不超過 Leaflet maxZoom）。只用 Leaflet setView（不動畫）與 focus ring／標籤：不走 marker click、不點按鈕、
   * 不改選取／預備移動／pending choice，也不送任何遊戲動作。黑河／海蘭泡／臥龍的顯示位置是依層級的像素偏移，
   * 所以先到目標層級再以該層級的顯示位置置中。驗證城鎮的顯示位置落在容器中心（±1px）且層級正確才回 ok:true；
   * 未知城鎮、缺座標、容器不可見、層級無法判定或驗證不符 → ok:false，不留下 focus ring。
   */
  function focusCanonicalTown(townName) {
    const town = byName.get(townName);
    if (!town) return { ok: false, reason: 'unknown-town' };
    if (!Number.isFinite(town.lat) || !Number.isFinite(town.lon)) return { ok: false, reason: 'town-position-missing' };
    const container = map.getContainer();
    if (document.hidden || !container || !container.isConnected || container.getClientRects().length === 0
      || !(container.clientWidth > 0) || !(container.clientHeight > 0)) return { ok: false, reason: 'map-hidden' };
    const zoom = Core.mapFocusZoom(map.getMinZoom(), map.getMaxZoom());
    if (zoom === null) return { ok: false, reason: 'zoom-unavailable' };
    map.invalidateSize({ pan: false }); // 剛由其他分頁切回戰略地圖時，先取得目前的容器尺寸再計算中心
    map.setView(L.latLng(town.lat, town.lon), zoom, { animate: false });
    const ll = townDisplayLatLng(town);
    if (!finiteLatLng(ll)) return { ok: false, reason: 'town-position-missing' };
    if (!map.getCenter().equals(ll)) map.setView(ll, zoom, { animate: false });
    const size = map.getSize();
    const point = map.latLngToContainerPoint(townDisplayLatLng(town));
    if (map.getZoom() !== zoom || !point || Math.abs(point.x - size.x / 2) > 1 || Math.abs(point.y - size.y / 2) > 1) {
      return { ok: false, reason: 'focus-unverified' };
    }
    focusTown = townName;
    drawFocusRing();
    // 唯讀導覽：只打開城鎮說明（不捲動地圖，置中驗證之後也維持精確置中）；不改選取、預備移動或 pending choice。
    showTownDetail(townName, { autoPan: false });
    return { ok: true };
  }

  /**
   * SL 瀏覽焦點上的 A：重新開啟目前 map focus 城鎮的說明 popup（B 關閉後）。只呼叫 canonical showTownDetail（不捲動），
   * 不走 marker click、不改選取／預備移動／pending choice、不動相機。town 不是 canonical 或不是目前的 map focus → ok:false。
   */
  function showFocusedDetail(townName) {
    if (!byName.has(townName)) return { ok: false, reason: 'unknown-town' };
    if (focusTown !== townName) return { ok: false, reason: 'not-focused' };
    return showTownDetail(townName, { autoPan: false }) ? { ok: true } : { ok: false, reason: 'detail-unavailable' };
  }

  function activate(townName) {
    const { model } = currentModel();
    if (!model.targets.some(t => t.town === townName)) return { ok: false, reason: 'not-a-target' };
    const marker = currentMarkers.get(townName);
    if (!marker) return { ok: false, reason: 'no-marker' };
    focusTown = townName;
    marker.fire('click'); // 與滑鼠點擊同一條既有路徑（selection / pending move / resolve choice 候選）
    drawFocusRing();
    return { ok: true };
  }

  function pressButton(id) {
    const info = currentModel();
    if (!info.model.buttons.some(b => b.id === id)) return { ok: false, reason: 'button-unavailable' };
    const el = document.getElementById(id);
    if (!el || !el.isConnected) return { ok: false, reason: 'button-unavailable' };
    el.click();
    return { ok: true, via: id };
  }

  /** 既有按鈕目前作用的對象：確認移動＝已預備的目的地；建立／瓦解＝目前選取的城鎮。 */
  function actBound(id, townName) {
    if (id === 'confirmMoveBtn') {
      return !!pendingMoveTarget && pendingMoveTarget.to === townName && pendingMoveTarget.from === selectedTown;
    }
    return selectedTown === townName;
  }

  /**
   * 客廳模式 Y：對目標執行它的既有地圖操作（建立組織／確認移動／瓦解組織）。
   * 1. 用權威資料重驗：town 必須是目前目標，且其 act 對應的既有按鈕必須等於 parent 要求的 id；
   * 2. 按鈕尚未作用在這個 town 時，走與 A／滑鼠相同的既有 marker click 路徑選取／預備；
   * 3. 再重驗一次：目標仍在、按鈕可見啟用且作用在這個 town，才點擊既有按鈕（伺服器仍做最終驗證）。
   * 任何一步不符 → ok:false（不點按鈕、不送出遊戲動作；最多留下與按 A 相同的選取／預備狀態）。
   */
  function act(townName, id) {
    const before = currentModel().model;
    const target = before.targets.find(t => t.town === townName);
    if (!target) return { ok: false, reason: 'not-a-target' };
    if (!target.act || Core.MAP_ACTS[target.act] !== id) return { ok: false, reason: 'action-mismatch' };
    if (!actBound(id, townName)) {
      const marker = currentMarkers.get(townName);
      if (!marker) return { ok: false, reason: 'no-marker' };
      focusTown = townName;
      marker.fire('click'); // 與滑鼠點擊同一條既有路徑（選取來源／預備目的地／選擇 pending choice 候選）
      drawFocusRing();
    }
    const after = currentModel().model;
    const still = after.targets.find(t => t.town === townName);
    if (!still || still.act !== target.act || !actBound(id, townName) || !after.buttons.some(b => b.id === id)) {
      return { ok: false, reason: 'button-unavailable' };
    }
    const el = document.getElementById(id);
    if (!el || !el.isConnected) return { ok: false, reason: 'button-unavailable' };
    el.click();
    return { ok: true, via: id };
  }

  /**
   * ZR（兩種顯示模式）：戰略地圖放大一級，已在最大層級時回到最小層級（Core.nextMapZoom；範圍＝Leaflet getMinZoom／getMaxZoom
   * 與 Core.MAP_ZOOM_CYCLE 的交集）。只用 Leaflet setView：中心維持目前中心、不動畫；不碰焦點城鎮、選取、預備移動或 pending choice。
   * 頁面或地圖容器不可見、地圖還沒有視圖、層級無法判定，或縮放後層級／中心驗證不符 → ok:false（parent 不記錄成功）。
   */
  function zoomCycle() {
    const container = map.getContainer();
    if (document.hidden || !container || !container.isConnected || container.getClientRects().length === 0
      || !(container.clientWidth > 0) || !(container.clientHeight > 0)) return { ok: false, reason: 'map-hidden' };
    let center;
    let zoom;
    try {
      center = map.getCenter(); // 還沒有 setView／fitBounds 時 Leaflet 會丟例外
      zoom = map.getZoom();
    } catch {
      return { ok: false, reason: 'map-not-ready' };
    }
    if (!center || !Number.isFinite(center.lat) || !Number.isFinite(center.lng)) return { ok: false, reason: 'map-not-ready' };
    const next = Core.nextMapZoom(zoom, Core.mapZoomBounds(map.getMinZoom(), map.getMaxZoom()));
    if (next === null) return { ok: false, reason: 'zoom-unavailable' };
    map.setView(center, next, { animate: false });
    // 縮放動畫進行中時 Leaflet 不會套用新層級：驗證不符即 fail closed。
    if (map.getZoom() !== next || !map.getCenter().equals(center)) return { ok: false, reason: 'zoom-unverified' };
    return { ok: true };
  }

  // B：只走既有可取消流程——可見且啟用的「取消瓦解」按鈕，或既有的「取消目前選取」。
  function cancel() {
    const info = currentModel();
    const which = cancelAvailable(info);
    if (which === 'popup') {
      closeTownDetail();
      return { ok: true, via: 'popup' };
    }
    if (which === 'cancelDissolveChoiceBtn') {
      document.getElementById('cancelDissolveChoiceBtn').click();
      return { ok: true, via: 'cancelDissolveChoiceBtn' };
    }
    if (which === 'selection') {
      exitMovementSelection();
      return { ok: true, via: 'selection' };
    }
    return { ok: false, reason: 'nothing-to-cancel' };
  }

  window.addEventListener('message', (event) => {
    if (!Core.isTrustedMessage(event, window.location.origin, window.parent)) return;
    if (event.data.type !== 'redline-controller-command') return;
    const command = Core.sanitizeMapCommand(event.data);
    if (!command) return;
    let result = { ok: true };
    if (command.cmd === 'focus') result = setFocus(command.town);
    else if (command.cmd === 'focusTown') result = focusCanonicalTown(command.town);
    else if (command.cmd === 'clearFocus') { focusTown = null; drawFocusRing(); }
    else if (command.cmd === 'activate') result = activate(command.town);
    else if (command.cmd === 'button') result = pressButton(command.id);
    else if (command.cmd === 'cancel') result = cancel();
    else if (command.cmd === 'act') result = act(command.town, command.id);
    else if (command.cmd === 'zoom') result = zoomCycle();
    else if (command.cmd === 'detail') result = showFocusedDetail(command.town);
    // req 原樣回傳：parent 只在對應的 req 收到 ok:true（上面已在執行前重驗）時才視為已執行。
    postToParent({
      type: 'redline-controller-result', v: Core.MAP_MESSAGE_VERSION, cmd: command.cmd, req: command.req,
      ok: result.ok === true, reason: result.reason || null, via: result.via || null,
    });
    // 收到指令當下用權威資料重算一份；`snapshot` 指令的 req 原樣帶回，parent 據此判斷這份不是過期推送。
    pushSnapshot(command.cmd === 'snapshot' ? command.req : null);
  });

  // 既有函式變更地圖狀態時順便通知 parent（不改函式行為，只加掛 hook）。
  for (const name of ['refreshDirectBuildUi', 'applySupportChoiceHighlight', 'applyGameStateToMap', 'exitMovementSelection']) {
    const original = window[name] || (typeof globalThis[name] === 'function' ? globalThis[name] : null);
    if (typeof original !== 'function') continue;
    const wrapped = function (...args) {
      const result = original.apply(this, args);
      scheduleSnapshot();
      return result;
    };
    try { window[name] = wrapped; } catch { /* function declarations are writable on window */ }
  }
  map.on('moveend zoomend', () => { if (focusTown) drawFocusRing(); scheduleSnapshot(); });
  map.on('popupopen popupclose', scheduleSnapshot); // 城鎮說明開／關（含滑鼠 ×）：parent 的 B 路由跟著更新
  window.addEventListener('load', scheduleSnapshot);
  window.__redlineControllerAdapter = { snapshot: snapshotMessage };
})();
