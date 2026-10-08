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
      buttons,
    });
    return { model, buttons: new Map(buttons.map(b => [b.id, b])) };
  }

  function cancelAvailable(info) {
    const cancelBtn = info.buttons.get('cancelDissolveChoiceBtn');
    if (cancelBtn && cancelBtn.visible && !cancelBtn.disabled) return 'cancelDissolveChoiceBtn';
    if (selectedTown) return 'selection';
    return null;
  }

  function snapshotMessage() {
    const info = currentModel();
    const mapEl = document.getElementById('map');
    const origin = mapEl ? mapEl.getBoundingClientRect() : { left: 0, top: 0 };
    const targets = [];
    for (const t of info.model.targets) {
      const town = byName.get(t.town);
      if (!town) continue;
      const p = map.latLngToContainerPoint(townDisplayLatLng(town));
      const target = { town: t.town, role: t.role, x: origin.left + p.x, y: origin.top + p.y };
      if (t.mode !== undefined && t.mode !== null) target.mode = t.mode;
      if (t.cost !== undefined && t.cost !== null) target.cost = t.cost;
      targets.push(target);
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
      selected: info.model.selected,
      pending: info.model.pending,
    };
  }

  function postToParent(message) {
    try {
      if (window.parent && window.parent !== window) window.parent.postMessage(message, window.location.origin);
    } catch (err) {
      console.warn('controller adapter: postMessage failed', err);
    }
  }

  function pushSnapshot() {
    pushTimer = null;
    postToParent(snapshotMessage());
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

  // B：只走既有可取消流程——可見且啟用的「取消瓦解」按鈕，或既有的「取消目前選取」。
  function cancel() {
    const info = currentModel();
    const which = cancelAvailable(info);
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
    else if (command.cmd === 'clearFocus') { focusTown = null; drawFocusRing(); }
    else if (command.cmd === 'activate') result = activate(command.town);
    else if (command.cmd === 'button') result = pressButton(command.id);
    else if (command.cmd === 'cancel') result = cancel();
    // req 原樣回傳：parent 只在對應的 req 收到 ok:true（上面已在執行前重驗）時才視為已執行。
    postToParent({
      type: 'redline-controller-result', v: Core.MAP_MESSAGE_VERSION, cmd: command.cmd, req: command.req,
      ok: result.ok === true, reason: result.reason || null, via: result.via || null,
    });
    pushSnapshot();
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
  window.addEventListener('load', scheduleSnapshot);
  window.__redlineControllerAdapter = { snapshot: snapshotMessage };
})();
