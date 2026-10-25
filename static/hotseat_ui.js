/*
 * REDLINE 客廳輪流（hot-seat）— 瀏覽器端膠合層（在 <head> 載入，第一次繪製前就能遮住舞台）。
 *
 * 同一瀏覽器保存多個席位（各自 playerId／resumeToken／Joy-Con 綁定）。伺服器 state 的行動者
 * （pending_choice 擁有者 ▸ 香港免費遷移根據地 ▸ 選基地 ▸ 目前回合玩家）換人時，先以不透明全螢幕遮罩蓋住整個舞台並停用所有輸入，
 * 接手者用綁給該席位的 Joy-Con 按 A 確認後，整頁以該席位自己的 resumeToken 重新載入：
 * 主頁 WebSocket 與戰略地圖 iframe 都重新授權連線，舊席位的私密 DOM 全部丟棄；
 * 新連線送來的 viewer-scoped state 確認行動者就是這個席位後才解除遮罩。
 * 大廳（尚未開局）：每一席在列上綁定自己的 Joy-Con。主連線（controller_ui）只 claim 目前席位那一支並照既有 routing 操作；
 * 其他已綁定席位各開一條只 claim 自己那一支的 bridge 監聽連線（bridge 一條連線只收得到一支的 frame），它按 A 才記下該席並
 * 整頁重新載入，由 /resume 以該席自己的 resumeToken 重新授權（不只切 DOM）。未綁定的 Joy-Con 沒有監聽、不能操作或切換。
 * 未啟用、或目前遊戲不是本機 hot-seat 席位時，完全不介入（單席位桌面／客廳模式不變）。
 */
(function () {
  'use strict';
  const Core = window.RedlineHotSeatCore;
  if (!Core) return;

  const STYLE = `
html[data-hotseat="masked"] #stageViewport { visibility: hidden !important; }
#hotseatMask { position: fixed; inset: 0; z-index: 2147483000; display: none; align-items: center; justify-content: center;
  background: #05070b; color: #f3f4f6; font: 16px/1.5 "Noto Sans TC", "PingFang TC", system-ui, sans-serif; }
html[data-hotseat="masked"] #hotseatMask { display: flex; }
#hotseatMask .hs-card { width: min(560px, 92vw); padding: 24px 28px; border: 2px solid #b91c1c; border-radius: 12px; background: #0f141c; text-align: center; }
#hotseatMask .hs-kicker { font-size: 13px; letter-spacing: .12em; color: #fca5a5; }
#hotseatMask h2 { margin: 6px 0 4px; font-size: 30px; }
#hotseatMask p { margin: 6px 0; }
#hotseatMask .hs-reason { color: #cbd5e1; font-size: 15px; }
#hotseatMask .hs-error { color: #fca5a5; min-height: 1.5em; }
#hotseatMask .hs-binds { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
#hotseatMask button { font: inherit; padding: 6px 12px; border-radius: 8px; border: 1px solid #475569; background: #1e293b; color: #f8fafc; cursor: pointer; }
/* AI 紅軍公開行動視窗：與舞台同一套 1280×720 設計單位，隨 --stage-scale（桌面與客廳模式）等比縮放並置中。 */
#hotseatMask .hs-ai { display: none; position: absolute; left: 50%; top: 50%; width: 780px; box-sizing: border-box; padding: 22px 28px;
  transform: translate(-50%, -50%) scale(var(--stage-scale, 1)); transform-origin: center; border: 2px solid #b91c1c; border-radius: 14px;
  background: #0f141c; color: #f3f4f6; font-size: 20px; line-height: 1.45; }
#hotseatMask[data-ai-public="on"] .hs-ai { display: block; }
#hotseatMask[data-ai-public="on"] .hs-card { display: none; }
#hotseatMask .hs-ai h2 { margin: 4px 0 2px; font-size: 36px; }
#hotseatMask .hs-ai-sub { margin: 0 0 10px; color: #cbd5e1; font-size: 18px; }
#hotseatMask .hs-ai-steps { list-style: none; margin: 0; padding: 0; max-height: 400px; overflow: hidden; display: flex; flex-direction: column; gap: 8px; }
#hotseatMask .hs-ai-step { padding: 8px 14px; border: 1px solid #334155; border-radius: 10px; background: #111827; }
#hotseatMask .hs-ai-step.hs-ai-latest { border-color: #fbbf24; background: #1f2937; }
#hotseatMask .hs-ai-step-head { display: flex; justify-content: space-between; gap: 12px; color: #fcd34d; font-size: 16px; font-weight: 700; }
#hotseatMask .hs-ai-line { margin: 2px 0 0; font-size: 20px; }
#hotseatMask .hs-ai-empty { padding: 14px; border: 1px dashed #475569; border-radius: 10px; color: #cbd5e1; }
#hotseatMask .hs-ai-foot { margin: 12px 0 0; display: flex; align-items: center; justify-content: space-between; gap: 16px; color: #94a3b8; font-size: 16px; }
#hotseatMask .hs-ai-foot button { flex: none; padding: 8px 22px; font-size: 20px; font-weight: 700; border-color: #fbbf24; }
#hotseatMask .hs-ai-foot button[hidden] { display: none; }
.hotseat-lobby { margin-top: 10px; font-size: 13px; }
.hotseat-lobby .hs-seat { display: flex; flex-direction: column; margin: 2px 0; padding: 2px 6px; border: 1px solid transparent; border-radius: 6px; }
.hotseat-lobby .hs-seat.hs-actor { border-color: #f59e0b; }
.hotseat-lobby .hs-seat-name, .hotseat-lobby .hs-seat-meta { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hotseat-lobby .hs-seat-line { display: flex; align-items: center; gap: 4px; min-width: 0; }
.hotseat-lobby .hs-seat-line > * { flex: none; }
.hotseat-lobby .hs-seat-line > .hs-seat-meta { flex: 0 1 auto; min-width: 0; }
.hotseat-lobby .hs-seat-meta { opacity: .8; font-size: 12px; }
/* 固定緊湊寬度：容得下最長的安全名稱「右 Joy-Con 4」與「— 未綁定 —」＋原生箭頭（Chrome 實測自然寬 8.83em），
   留約 0.4em 餘裕；不再依展開清單裡最長的選項（例如「・已綁給〈…〉」）撐寬。 */
.hotseat-lobby .hs-bind-select { width: 9.25em; font-size: 12px; }
/* 靠右對齊：安全名稱＋燈 → 下拉 → 切換 是一個緊湊群組，margin-left:auto 推到列的右緣；空白只在陣營／準備與群組之間。
   安全名稱＋燈 是固定寬度欄、靠左起排：每列名稱的左緣對齊。7.5em 容得下最長的「右 Joy-Con 4」＋燈（Chrome 實測 7.43em）
   與「未綁定 Joy-Con」；較短的名稱只在燈之後留白，不裁切。 */
.hotseat-lobby .hs-joy { display: inline-flex; align-items: center; justify-content: flex-start; width: 7.5em; white-space: nowrap;
  font-size: 12px; margin-left: auto; }
.hotseat-lobby .hs-switch-slot { visibility: hidden; }
.hotseat-lobby .hs-joy-dot { display: inline-block; box-sizing: border-box; width: 10px; height: 10px; margin: 0 0 0 4px;
  border-radius: 50%; }
.hotseat-lobby .hs-joy-dot[data-tone="ok"] { background: #22c55e; box-shadow: 0 0 0 2px rgba(34, 197, 94, .3); }
.hotseat-lobby .hs-joy-dot[data-tone="warn"] { background: #f59e0b; }
.hotseat-lobby .hs-joy-dot[data-tone="error"] { background: #ef4444; }
.hotseat-lobby .hs-joy-dot[data-tone="off"] { border: 2px solid #94a3b8; background: transparent; }
.hotseat-lobby .hs-prompt { margin-top: 2px; color: #fcd34d; }
.hotseat-lobby .hs-prompt:empty, .hotseat-lobby .hs-notice:empty { display: none; }
.hotseat-lobby .hs-notice { color: #fca5a5; min-height: 1em; }
`;

  const LOBBY_INACTIVE = Object.freeze({ view: 'inactive', actor: null, seat: null, self: false });
  const hs = {
    verdict: { view: 'inactive', actor: null, seat: null, needsBinding: false },
    // 大廳（尚未開局）：onLobby 開始、onConnect（進入遊戲）結束；lobby＝Core.decideLobby 的結果。
    lobbyMode: false,
    lobby: LOBBY_INACTIVE,
    lobbyNotice: '',
    gameId: null,
    connectedSeat: null,
    lastState: null,
    notice: '',
    claimAt: 0,
    reloading: false,
    provisioning: null, // provisionSeats 進行中的 promise：配置期間不 claim／不監聽／不改名，且同時只跑一個
    seqBusy: false,
    maskSig: null,
    lobbySig: null,
    timer: null,
    aiShown: null, // 目前顯示中的 AI 紅軍公開視窗內容（Core.aiPublicView）；沒有視窗時為 null
  };

  // ------------------------------------------------------------ storage（內容不可信，一律經 Core 正規化）
  function loadStore() {
    try { return Core.normalizeStore(JSON.parse(localStorage.getItem(Core.STORE_KEY) || 'null')); } catch { return Core.normalizeStore(null); }
  }
  function saveStore(store) {
    try { localStorage.setItem(Core.STORE_KEY, JSON.stringify(store)); } catch { /* storage may be blocked */ }
  }
  function rawSession() {
    try { return JSON.parse(sessionStorage.getItem(Core.SESSION_KEY) || 'null'); } catch { return null; }
  }
  function loadSession(gameId) { return Core.normalizeSession(rawSession(), gameId); }
  function saveSession(session) {
    try { sessionStorage.setItem(Core.SESSION_KEY, JSON.stringify(session)); } catch { /* storage may be blocked */ }
  }

  // ------------------------------------------------------------ 第一次繪製前：注入樣式；有本機席位時先遮住（之後由 state 決定）
  const style = document.createElement('style');
  style.id = 'hotseatStyle';
  style.textContent = STYLE;
  document.head.appendChild(style);
  {
    const store = loadStore();
    if (store.enabled && Object.keys(store.games).length) document.documentElement.dataset.hotseat = 'masked';
  }

  // ------------------------------------------------------------ helpers
  const ctlApi = () => window.RedlineController || null;
  const ctlState = () => { try { return ctlApi() ? ctlApi().getState() : null; } catch { return null; } };
  const roster = () => { const s = ctlState(); return (s && s.controller && s.controller.roster) || null; };

  function factionLabel(id) {
    if (!id) return '';
    try { return typeof factionDisplayName === 'function' ? (factionDisplayName(id) || '') : ''; } catch { return ''; }
  }

  /** 玩家看到的手把名稱（左右＋同側本機序號）；不含 UDP 埠、名稱指紋或 id。綁定與 claim 仍用完整 id。 */
  function controllerText(id) {
    return Core.controllerNames(roster())(id);
  }

  function cleanUrl() {
    const params = new URLSearchParams(location.search || '');
    const keep = new URLSearchParams();
    if (params.get('display')) keep.set('display', params.get('display'));
    const q = keep.toString();
    return `${location.pathname}${q ? `?${q}` : ''}`;
  }

  // ------------------------------------------------------------ 遮罩
  function maskEl() {
    let el = document.getElementById('hotseatMask');
    if (el || !document.body) return el;
    el = document.createElement('div');
    el.id = 'hotseatMask';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-modal', 'true');
    el.setAttribute('aria-labelledby', 'hotseatTitle');
    el.dataset.controllerOverlay = 'hotseat';
    el.innerHTML = `<div class="hs-card">
      <div class="hs-kicker">客廳輪流</div>
      <h2 id="hotseatTitle"></h2>
      <p id="hotseatReason" class="hs-reason"></p>
      <p id="hotseatStatus"></p>
      <div id="hotseatBinds" class="hs-binds"></div>
      <p id="hotseatNotice" class="hs-error"></p>
    </div>
    <section id="hotseatAiPublic" class="hs-ai" role="status" aria-live="polite" aria-labelledby="hotseatAiTitle" hidden>
      <h2 id="hotseatAiTitle"></h2>
      <p id="hotseatAiSub" class="hs-ai-sub"></p>
      <ol id="hotseatAiSteps" class="hs-ai-steps"></ol>
      <p class="hs-ai-foot"><span id="hotseatAiFoot"></span><button id="hotseatAiDismiss" type="button" hidden>知道了</button></p>
    </section>`;
    document.body.appendChild(el);
    return el;
  }

  function setMasked(on) {
    const html = document.documentElement;
    if (on) html.dataset.hotseat = 'masked';
    else if (hs.verdict.view === 'inactive') delete html.dataset.hotseat;
    else html.dataset.hotseat = 'open';
    // 遮罩時舞台與其他頂層節點全部 inert：滑鼠、鍵盤與原生焦點都到不了已載入的私密 DOM。
    if (!document.body) return;
    for (const child of document.body.children) {
      if (child.id === 'hotseatMask' || child.tagName === 'SCRIPT') continue;
      if (on && !child.inert) { child.inert = true; child.dataset.hotseatInert = '1'; }
      else if (!on && child.dataset.hotseatInert === '1') { child.inert = false; delete child.dataset.hotseatInert; }
    }
  }

  function reasonLine(actor) {
    if (!actor) return '';
    if (actor.kind === 'pending_choice') return '有待處理的選擇，由這位玩家決定';
    if (actor.kind === 'hk_base_relocation') return '香港抗暴之戰：決定是否免費遷移根據地';
    if (actor.kind === 'base_selection') return '輪到選擇根據地';
    if (actor.kind === 'current_player') return '輪到這位玩家行動';
    return '';
  }

  function button(label, onClick) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }

  /**
   * 公開行動的一行：先用 AI 回合常見句型，再沿用「玩家動態」的在地化（只限 AI 自己的行動句）。
   * 仍含英文的行不顯示，避免露出原始 log，也不把別人的事件結果掛在 AI 名下。
   */
  function aiLineText(raw, actorName, playerNames) {
    const text = String(raw).replace(/^\[Turn \d+\]\s*/, '').trim();
    if (!text) return '';
    let out = Core.aiLineText(text);
    if (out === null && text.startsWith(actorName) && typeof localizePeerActionNoticeText === 'function') {
      try { out = localizePeerActionNoticeText({ actor: { name: actorName }, text, playerNames }); } catch { out = null; }
    }
    if (out === null) out = text;
    return !out || /[A-Za-z]{3,}/.test(out) ? '' : out;
  }

  const RESOURCE_TEXT = Object.freeze({ money: '資金', propaganda: '宣傳' });

  function aiDeltaText(delta) {
    return Object.keys(RESOURCE_TEXT).filter(k => delta[k]).map(k => `${RESOURCE_TEXT[k]} ${delta[k] > 0 ? '+' : ''}${delta[k]}`).join('　');
  }

  /** 公開行動視窗內容（最新一步在最上面，超出高度的是較舊的步驟）；ai 為 null 時關閉並清空。 */
  function renderAiPublic(el, ai) {
    const panel = el.querySelector('#hotseatAiPublic');
    if (!panel) return;
    el.dataset.aiPublic = ai ? 'on' : 'off';
    panel.hidden = !ai;
    if (!ai) { el.querySelector('#hotseatAiSteps').replaceChildren(); return; }
    const names = ((hs.lastState && hs.lastState.players) || []).map(p => p && p.name).filter(Boolean);
    el.querySelector('#hotseatAiTitle').textContent = `${ai.actorName}${ai.ended ? '回合結束' : '行動中'}`;
    el.querySelector('#hotseatAiFoot').textContent = ai.ended
      ? `${ai.actorName}的回合已結束，目前仍輪到${ai.actorName}；按「知道了」或 A 後才會輪到下一位${ai.timeoutSeconds ? `（約 ${ai.timeoutSeconds} 秒後自動繼續）` : ''}。`
      : `${ai.actorName}是目前行動的玩家；行動結束後會先停在這裡，按「知道了」或 A（或逾時）才會輪到下一位。`;
    el.querySelector('#hotseatAiDismiss').hidden = !ai.ended;
    const last = ai.steps[ai.steps.length - 1];
    el.querySelector('#hotseatAiSub').textContent = `第 ${ai.turn} 回合｜公開行動摘要${last ? `｜目前資金 ${last.resources.money}、宣傳 ${last.resources.propaganda}` : ''}`;
    const items = ai.steps.slice().reverse().map((step, i) => {
      const li = document.createElement('li');
      li.className = `hs-ai-step${i === 0 ? ' hs-ai-latest' : ''}`;
      li.dataset.seq = String(step.seq);
      const head = document.createElement('div');
      head.className = 'hs-ai-step-head';
      const delta = aiDeltaText(step.delta);
      head.append(Object.assign(document.createElement('span'), { textContent: `${i === 0 ? '最新行動' : '先前行動'} #${step.seq}` }),
        Object.assign(document.createElement('span'), { textContent: delta ? `資源變化：${delta}` : '' }));
      li.appendChild(head);
      const lines = step.lines.map(line => aiLineText(line, ai.actorName, names)).filter(Boolean);
      for (const text of lines.length ? lines : ['完成了一項行動']) {
        li.appendChild(Object.assign(document.createElement('p'), { className: 'hs-ai-line', textContent: text }));
      }
      return li;
    });
    if (!items.length) {
      const empty = document.createElement('li');
      empty.className = 'hs-ai-empty';
      empty.textContent = `${ai.actorName}正在決定行動…`;
      items.push(empty);
    }
    el.querySelector('#hotseatAiSteps').replaceChildren(...items);
  }

  function renderMask() {
    const v = hs.verdict;
    if (!Core.masked(v.view)) {
      const open = document.getElementById('hotseatMask');
      hs.aiShown = null;
      if (open && open.dataset.aiPublic === 'on') renderAiPublic(open, null); // 遮罩解除（已進入某席位畫面）：公開視窗不再存在
      return;
    }
    const el = maskEl();
    if (!el) return;
    // 公開視窗只在 AI 紅軍是權威行動者（state.current_player 仍是紅軍）時顯示；回合結束的等待也是同一個狀態，
    // 由伺服器在確認或逾時後才推進到下一位。視窗不以換人當關閉條件，也不靠前端自己停留。
    const ai = v.view === 'waiting' ? Core.aiPublicView(hs.lastState, v) : null;
    hs.aiShown = ai;
    const cs = ctlState();
    const ctl = cs && cs.controller;
    const list = roster();
    const name = (v.actor && v.actor.name) || (v.seat && v.seat.name) || '';
    let title = '客廳輪流';
    let status = '正在連線…';
    let binds = [];
    if (v.view === 'reconnect') {
      title = `正在切換到〈${name || '本機玩家'}〉`;
      status = '以這個席位重新連線並載入畫面…';
    } else if (v.view === 'waiting') {
      title = name ? `等待〈${name}〉行動` : '等待遊戲狀態';
      status = name ? '這位玩家不在這台裝置上；各席位的私密畫面保持隱藏。' : '尚未取得伺服器狀態；畫面保持隱藏。';
    } else if (v.view === 'handoff') {
      title = Core.handoffTitle(v.actor, factionLabel(v.actor && v.actor.faction));
      const seat = v.seat;
      if (!cs || !cs.enabled) {
        status = '交接需要 Joy-Con：請先啟用搖桿控制。';
        binds = [button('啟用搖桿控制', () => { if (ctlApi()) ctlApi().setEnabled(true); render(); })];
      } else if (v.needsBinding) {
        status = '此席位尚未綁定 Joy-Con：請接手的玩家選擇自己的手把，再用它按 A 確認。';
        const options = Core.bindableControllers(loadStore(), hs.gameId, seat.player_id, list);
        binds = options.length
          ? options.map(c => button(`綁定 ${controllerText(c.id)}`, () => bindSeat(seat.player_id, c.id)))
          : [];
        if (!options.length) status += '（目前沒有可用的手把：確認 bridge 已連線且手把有訊號）';
      } else {
        const entry = (list || []).find(c => c.id === seat.controller) || null;
        const ready = ctl && ctl.owned === seat.controller && cs.status === 'connected';
        if (ready) status = `請〈${name}〉用自己的 ${controllerText(seat.controller)} 按 A 確認接手`;
        else if (entry && entry.owner === 'other') status = `${controllerText(seat.controller)} 正由其他分頁使用`;
        else if (!entry || entry.status !== 'active') status = `${controllerText(seat.controller)} 沒有訊號`;
        else status = `正在連接 ${controllerText(seat.controller)}…`;
        if (Core.bindingLost(seat, list)) {
          binds = [button('更換手把', () => { saveStore(Core.unbindController(loadStore(), hs.gameId, seat.player_id)); hs.notice = ''; refresh(); })];
        }
      }
    }
    const sig = JSON.stringify([v.view, title, status, hs.notice, binds.map(b => b.textContent), reasonLine(v.actor), ai]);
    if (sig === hs.maskSig) return;
    hs.maskSig = sig;
    renderAiPublic(el, ai);
    el.querySelector('#hotseatTitle').textContent = title;
    el.querySelector('#hotseatReason').textContent = v.view === 'handoff' ? reasonLine(v.actor) : '';
    el.querySelector('#hotseatStatus').textContent = status;
    el.querySelector('#hotseatNotice').textContent = hs.notice;
    el.querySelector('#hotseatBinds').replaceChildren(...binds);
  }

  /** 公開視窗的「知道了」／A：通知伺服器放行 AI 紅軍結束回合（伺服器才會把 current player 換到下一位）。 */
  function ackAiTurn() {
    if (typeof sendAction === 'function') sendAction('ack_ai_red_army');
  }

  function bindSeat(playerId, controllerId, gameId = hs.gameId) {
    const result = Core.bindController(loadStore(), gameId, playerId, controllerId);
    const notice = result.ok ? '' : Core.reasonText(result.reason);
    hs.notice = notice;
    hs.lobbyNotice = notice;
    if (result.ok) {
      saveStore(result.store);
      hs.claimAt = 0;
      if (inLobby()) refreshLobbyVerdict();
      syncClaim();
      syncListeners();
    }
    refresh();
    renderLobby();
    return result;
  }

  function unbindSeat(playerId, gameId) {
    saveStore(Core.unbindController(loadStore(), gameId, playerId));
    hs.lobbyNotice = '';
    if (inLobby()) refreshLobbyVerdict();
    syncListeners();
    refresh();
    renderLobby();
  }

  // ------------------------------------------------------------ 大廳判定（只讀 server /lobby 公開資料；不是 hot-seat 大廳＝inactive）
  function inLobby() { return hs.lobbyMode && !session().started; }

  function pickerShown() {
    const el = document.getElementById('factionPicker');
    return !!el && el.style.display !== 'none' && getComputedStyle(el).display !== 'none';
  }

  function refreshLobbyVerdict() {
    const cur = session();
    const next = inLobby() && cur.gameId
      ? Core.decideLobby({ lobby: cur.lobby, store: loadStore(), gameId: cur.gameId, connectedSeatId: cur.playerId })
      : LOBBY_INACTIVE;
    const seatId = v => (v.seat ? v.seat.player_id : null);
    if (next.view !== hs.lobby.view || seatId(next) !== seatId(hs.lobby)) hs.lobbyNotice = '';
    hs.lobby = next;
    return next;
  }

  // ------------------------------------------------------------ Joy-Con 擁有權：主連線只 claim 目前席位（或接手席位）綁定的那一支
  function syncClaim() {
    if (hs.provisioning) return;
    const target = Core.claimTarget(inLobby() ? hs.lobby : hs.verdict);
    const cs = ctlState();
    if (!target || !cs || !cs.enabled || !cs.controller || cs.controller.mode !== 'v2') return;
    if (cs.controller.owned === target || cs.controller.claimInFlight) return;
    const entry = (cs.controller.roster || []).find(c => c.id === target);
    if (!entry || entry.owner === 'other' || entry.status !== 'active') return;
    const now = Date.now();
    if (now - hs.claimAt < 1500) return;
    hs.claimAt = now;
    ctlApi().selectController(target);
  }

  // ------------------------------------------------------------ 大廳監聽連線：其他已綁定本機席位，各一條只 claim 自己那一支的 bridge 連線
  // bridge v2 一條連線最多擁有一支、且只收得到那一支的 frame（bridge 驗證 claim、每支只有一位擁有者）。這裡沿用 controller_core
  // 的訊息驗證、frame 接受與 reducer（重連／換手把第一筆只當 baseline），只看 reducer 產生的 A；不路由任何其他輸入。
  const CtlCore = () => window.RedlineControllerCore || null;
  const listeners = new Map(); // controller id → { controller, socket, binding, roster, pad, claimAt, retryAt }
  const RETRY_MS = 2000;

  function freshPad() { return { input: CtlCore().createInputState(), key: null }; }

  function closeListener(listener) {
    if (listeners.get(listener.controller) === listener) listeners.delete(listener.controller);
    const socket = listener.socket;
    listener.socket = null;
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
      try { socket.close(); } catch { /* ignore */ } // 連線結束＝bridge 釋放這一支
    }
  }

  function openListener(controller) {
    const listener = {
      controller, socket: null, binding: { mode: 'v2', owned: null, side: null }, roster: null,
      pad: freshPad(), claimAt: 0, retryAt: 0,
    };
    listeners.set(controller, listener);
    let socket;
    try { socket = new WebSocket(ctlState().url); } catch { listener.retryAt = Date.now() + RETRY_MS; return listener; }
    listener.socket = socket;
    socket.onopen = () => { try { socket.send(JSON.stringify(CtlCore().bridgeHello())); } catch { /* ignore */ } };
    socket.onmessage = (event) => onListenerMessage(listener, event.data);
    socket.onclose = () => {
      if (listener.socket !== socket) return;
      listener.socket = null;
      listener.binding = { mode: 'v2', owned: null, side: null };
      listener.pad = freshPad();
      listener.retryAt = Date.now() + RETRY_MS;
    };
    socket.onerror = () => { try { socket.close(); } catch { /* ignore */ } };
    return listener;
  }

  /** 只 claim 自己那一支的精確 id；別的連線（例如主連線）正擁有、沒有訊號或不在清單時等待，不搶。 */
  function claimForListener(listener) {
    const socket = listener.socket;
    if (!socket || socket.readyState !== 1 || listener.binding.owned === listener.controller) return;
    const entry = (listener.roster || []).find(c => c.id === listener.controller);
    if (!entry || entry.owner || entry.status !== 'active') return;
    const now = Date.now();
    if (now - listener.claimAt < 1000) return;
    listener.claimAt = now;
    try { socket.send(JSON.stringify({ type: 'claim', controller: listener.controller, v: CtlCore().BRIDGE_PROTOCOL_VERSION })); } catch { /* ignore */ }
  }

  function onListenerMessage(listener, raw) {
    if (listeners.get(listener.controller) !== listener) return;
    let parsed;
    try { parsed = JSON.parse(raw); } catch { return; }
    const msg = CtlCore().classifyBridgeMessage(parsed, 'v2');
    if (!msg) return;
    if (msg.kind === 'roster') {
      const owned = msg.roster.owned ? msg.roster.controllers.find(c => c.id === msg.roster.owned) : null;
      const next = owned ? owned.id : null;
      if (next !== listener.binding.owned) listener.pad = freshPad();
      listener.binding = { mode: 'v2', owned: next, side: owned ? owned.side : null };
      listener.roster = msg.roster.controllers;
      claimForListener(listener);
      return;
    }
    if (msg.kind !== 'frame') return;
    if (document.hidden) { listener.pad = freshPad(); return; }
    // 只有這條連線擁有的那一支（id 與左右都相符）進 reducer。
    if (!CtlCore().acceptControllerFrame(listener.binding, msg)) return;
    const step = CtlCore().stepControllerInput(listener.pad, msg, performance.now());
    listener.pad = step.pad;
    const seat = Core.listenerSwitchTarget({
      verdict: refreshLobbyVerdict(), store: loadStore(), gameId: session().gameId, controller: listener.controller, actions: step.actions,
    });
    if (seat) switchLobbySeat(seat);
  }

  /** 需要的監聽＝其他已綁定、在 server lobby 內的本機席位；不需要的關閉（bridge 釋放），斷線的稍後重開。 */
  function syncListeners() {
    const cs = ctlState();
    const ready = inLobby() && !hs.reloading && !hs.provisioning && !!CtlCore() && !!cs && cs.enabled && !!cs.url;
    const want = ready ? Core.lobbyListeners({ verdict: hs.lobby, store: loadStore(), gameId: session().gameId }) : [];
    const ids = new Set(want.map(w => w.controller));
    for (const listener of [...listeners.values()]) if (!ids.has(listener.controller)) closeListener(listener);
    const now = Date.now();
    for (const id of ids) {
      const listener = listeners.get(id);
      if (!listener) openListener(id);
      else if (!listener.socket && now >= listener.retryAt) { closeListener(listener); openListener(id); }
      else claimForListener(listener);
    }
  }

  function render() {
    setMasked(Core.masked(hs.verdict.view));
    renderMask();
  }

  function refresh() {
    if (hs.verdict.view !== 'inactive' && hs.gameId && hs.lastState) {
      hs.verdict = Core.decide({
        state: hs.lastState, connectedSeatId: hs.connectedSeat, session: loadSession(hs.gameId), store: loadStore(), gameId: hs.gameId,
      });
    }
    render();
  }

  function reloadInto(seat) {
    if (hs.reloading || !seat) return;
    hs.reloading = true;
    // 整頁重新載入：主頁與地圖 iframe 都以這個席位的 resumeToken 重新連線；舊席位的 DOM 不保留。
    setTimeout(() => location.replace(cleanUrl()), 0);
  }

  // ------------------------------------------------------------ app.js hooks
  /** 主頁 WebSocket 即將以 (gameId, playerId) 連線：本機 hot-seat 席位 → 先遮住直到 state 確認；否則不介入。 */
  function onConnect(gameId, playerId) {
    hs.lobbyMode = false;
    hs.lobby = LOBBY_INACTIVE;
    syncListeners(); // 離開大廳：關閉所有監聽連線（bridge 釋放）
    hs.gameId = gameId;
    hs.connectedSeat = playerId;
    hs.lastState = null;
    const store = loadStore();
    if (!Core.isHotSeatGame(store, gameId, playerId)) {
      hs.verdict = { view: 'inactive', actor: null, seat: null, needsBinding: false };
    } else {
      const raw = rawSession();
      if (!raw || raw.gameId !== gameId) saveSession({ gameId, active: null, unlocked: false });
      hs.verdict = { view: 'loading', actor: null, seat: Core.findSeat(store, gameId, playerId), needsBinding: false };
    }
    hs.maskSig = null;
    render();
  }

  /** 每一份主頁 WebSocket state 在 render 前先經過這裡（同步套用遮罩）。 */
  function onState(state, gameId, connectedSeatId) {
    hs.gameId = gameId;
    hs.connectedSeat = connectedSeatId;
    hs.lastState = state;
    const store = loadStore();
    const session = loadSession(gameId);
    const verdict = Core.decide({ state, connectedSeatId, session, store, gameId });
    if (verdict.view !== 'inactive') {
      const locked = Core.lockSession(session, verdict);
      if (locked !== session) saveSession(locked);
    }
    if (verdict.view !== hs.verdict.view || (verdict.seat && verdict.seat.player_id) !== (hs.verdict.seat && hs.verdict.seat.player_id)) hs.notice = '';
    hs.verdict = verdict;
    render();
    syncClaim();
    if (verdict.view === 'reconnect') reloadInto(verdict.seat);
    return verdict.view;
  }

  /** 大廳（尚未開局）沒有私密畫面：解除遮罩；之後由大廳行動者決定要聽哪一席的 Joy-Con。 */
  function onLobby() {
    hs.verdict = { view: 'inactive', actor: null, seat: null, needsBinding: false };
    hs.lobbyMode = true;
    render();
    refreshLobbyVerdict();
    syncClaim();
    syncListeners();
    renderLobby();
  }

  /** app.js 每次畫完 server /lobby 名單後呼叫（席位加入／離開、陣營、準備可能改變）。 */
  function onLobbyState() {
    if (!inLobby()) return;
    refreshLobbyVerdict();
    syncClaim();
    syncListeners();
    syncCodenames();
    syncSequential();
    renderLobby();
  }

  // ------------------------------------------------------------ 行動代號：系統預設的本機席位寫成 server lobby 位置的 P1～P4
  const renaming = new Map(); // player_id → 下次可重送的時間（請求中或失敗後稍候）
  const RENAME_RETRY_MS = 3000;

  function syncCodenames() {
    const cur = session();
    if (!inLobby() || !cur.gameId || cur.started || hs.reloading || hs.provisioning) return;
    const now = Date.now();
    for (const r of Core.codenameRenames({ lobby: cur.lobby, store: loadStore(), gameId: cur.gameId })) {
      if ((renaming.get(r.player_id) || 0) > now) continue;
      renaming.set(r.player_id, now + RENAME_RETRY_MS);
      renameSeat(cur.gameId, r);
    }
  }

  /** 以既有 /join（該席 player_id＋它自己的 resume_token）改 server 權威 lobby 的名稱；成功後才更新本機席位與畫面。 */
  async function renameSeat(gameId, r) {
    let data;
    try {
      const res = await fetch('/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game_id: gameId, player_id: r.player_id, resume_token: r.resume_token, name: r.name,
          device_id: typeof redlineDeviceId === 'function' ? redlineDeviceId() : '',
        }),
      });
      data = await res.json();
    } catch { return; }
    if (!data || data.error || data.player_id !== r.player_id) return;
    const result = Core.addSeat(loadStore(), gameId, { player_id: r.player_id, resume_token: data.resume_token || r.resume_token, name: r.name });
    if (result.ok) saveStore(result.store);
    // 目前席位的「你的行動代號」欄：使用者沒有輸入過才同步顯示（不覆寫正在輸入的文字）。
    const input = document.getElementById('playerName');
    if (input && r.player_id === session().playerId && input.dataset.userEdited !== '1') input.value = r.name;
    if (typeof refreshLobbyState === 'function') refreshLobbyState().catch(() => {});
  }

  /** 恢復連線時要用哪一席：本分頁已確認／正在交接的席位優先；不是 hot-seat 遊戲回 null（沿用原本的單席位恢復）。 */
  function resumeTarget(saved) {
    const store = loadStore();
    if (!store.enabled) return null;
    const raw = rawSession();
    const gameId = raw && Core.seatsFor(store, raw.gameId).length ? raw.gameId : saved && saved.game_id;
    const seats = Core.seatsFor(store, gameId);
    if (!seats.length) return null;
    const session = Core.normalizeSession(raw, gameId);
    const seat = seats.find(s => s.player_id === session.active)
      || seats.find(s => saved && s.player_id === saved.player_id) || seats[0];
    return { game_id: gameId, player_id: seat.player_id, resume_token: seat.resume_token, name: seat.name };
  }

  /**
   * app.js 每次保存單席位 session 時一併記錄席位（hot-seat 啟用時）；同一 player_id 只更新 token，不覆寫其他席位。
   * autoName：送出時行動代號仍是系統預設（true）或使用者輸入（false）；未提供＝保留原值。
   */
  function rememberSeat(gameId, playerId, resumeToken, name, autoName) {
    const store = loadStore();
    if (!store.enabled || !gameId || !playerId || !resumeToken) return;
    const result = Core.addSeat(store, gameId, { player_id: playerId, resume_token: resumeToken, name, auto_name: autoName });
    if (result.ok) saveStore(result.store);
    renderLobby();
  }

  // ------------------------------------------------------------ 控制器閘門（controller_ui.js dispatch 第一個呼叫）
  const gate = {
    // 大廳 hot-seat 由 lobby actor 決定 claim；controller_ui.js 的單手把自動 claim 在此期間不送。
    managesClaims() { return inLobby() && refreshLobbyVerdict().view !== 'inactive'; },
    // 遊戲畫面目前是否可由這支 Joy-Con 操作（未啟用 hot-seat 一律可以；遮罩或不是該席位的手把時不行）。
    // controller_ui.js 用它擋掉沒有按鍵觸發的自動動作（例如必選地圖目標時自動切到戰略地圖）。
    allowsPage({ owned }) {
      if (inLobby()) return true;
      const v = hs.verdict;
      return !v || v.view === 'inactive' || (!Core.masked(v.view) && Core.allowsInput(v, owned));
    },
    intercept(action, { owned }) {
      // Joy-Con 自動建房尚未完成（配置中或失敗待重試）：席位還沒綁完，不可攔截或代為開啟陣營視窗，讓「重試」鈕能用 A 操作。
      if (window.RedlineStartFlow?.autoSetupActive?.()) return false;
      if (inLobby() && hs.verdict.view === 'inactive') {
        const lv = refreshLobbyVerdict();
        if (lv.view === 'inactive') return false;
        const r = Core.lobbyInput({ verdict: lv, owned, action, store: loadStore() });
        if (r.switchTo) { switchLobbySeat(r.switchTo); return true; }
        if (r.reason) { hs.lobbyNotice = Core.reasonText(r.reason); renderLobby(); }
        if (r.pass && Core.lobbyEntersSelection({ verdict: lv, owned, action, pickerOpen: pickerShown() })) {
          const open = document.getElementById('openFactionPickerBtn');
          if (open && !open.disabled) open.click(); // 既有按鈕 handler（以目前席位自己的 playerId）
          return true;
        }
        return !r.pass; // 只有行動席位自己的 Joy-Con 能走既有 focus／modal routing
      }
      const v = hs.verdict;
      if (v.view === 'inactive') return false;
      if (Core.masked(v.view) && hs.aiShown) {
        if (hs.aiShown.ended && action && action.type === 'press' && action.button === 'A') ackAiTurn();
        return true; // 公開視窗開著時所有輸入都不穿透；A 只用來確認（伺服器放行後才會出現交接）
      }
      if (Core.masked(v.view)) {
        if (v.view === 'handoff') {
          const r = Core.confirmVerdict({ verdict: v, owned, action });
          if (r.ok) confirmHandoff(v);
          else if (action && action.type === 'press' && action.button === 'A' && r.reason !== 'not-confirm') {
            hs.notice = Core.reasonText(r.reason);
            renderMask();
          }
        }
        return true; // 遮罩時任何輸入都不穿透到被遮住的頁面
      }
      return !Core.allowsInput(v, owned);
    },
  };

  function confirmHandoff(v) {
    saveSession(Core.confirmSession(hs.gameId, v.seat.player_id));
    hs.notice = '';
    hs.verdict = { view: 'reconnect', actor: v.actor, seat: v.seat, needsBinding: false };
    render();
    reloadInto(v.seat);
  }

  // ------------------------------------------------------------ 大廳：啟用、席位列（陣營／準備／Joy-Con 綁定）、新增本機玩家、切換席位
  const session = () => (window.RedlineSession ? window.RedlineSession.current() : {});

  const CHOICE_NOTE = Object.freeze({ 'other-tab': '・其他分頁使用中', stale: '・訊號中斷', missing: '・未偵測到' });

  /**
   * 席位列的手把狀態（Core.seatJoyStatus）：已綁定＝安全名稱＋對應色燈（綠＝連線正常；異常為非綠色），不加可見狀態文字；
   * 未綁定＝「未綁定 Joy-Con」文字。燈有 aria-label／title（完整狀態）；有燈時可見名稱對輔助技術隱藏，避免重複朗讀。
   */
  function joyStatusEl(status) {
    const wrap = document.createElement('span');
    wrap.className = 'hs-joy';
    wrap.dataset.state = status.state;
    wrap.dataset.tone = status.tone;
    const hasDot = status.tone !== 'none';
    const part = (cls, text) => {
      const el = document.createElement('span');
      el.className = cls;
      el.textContent = text;
      if (hasDot) el.setAttribute('aria-hidden', 'true');
      return el;
    };
    if (status.name) wrap.appendChild(part('hs-joy-name', status.name));
    if (hasDot) {
      const dot = document.createElement('span');
      dot.className = 'hs-joy-dot';
      dot.dataset.tone = status.tone;
      dot.setAttribute('role', 'img');
      dot.setAttribute('aria-label', status.aria);
      dot.title = status.aria;
      wrap.appendChild(dot);
    }
    if (status.text) wrap.appendChild(part('hs-joy-text', status.text));
    return wrap;
  }

  /** 每一席一個下拉：選一支＝綁定／改綁（bridge identity 精確 id），「未綁定」＝解除。已綁給其他席位的不可選。 */
  function bindSelect(row, gameId, seats, list, locked) {
    const select = document.createElement('select');
    select.className = 'hs-bind-select';
    select.dataset.playerId = row.player_id;
    select.setAttribute('aria-label', `〈${row.name || '玩家'}〉的 Joy-Con`);
    const none = document.createElement('option');
    none.value = '';
    none.textContent = '— 未綁定 —';
    select.appendChild(none);
    for (const c of Core.controllerChoices(loadStore(), gameId, row.player_id, list)) {
      const option = document.createElement('option');
      option.value = c.id;
      const holder = c.takenBy ? seats.find(r => r.player_id === c.takenBy) : null;
      // 這一席目前綁定的那一支（選中的選項）不附加狀態註記：狀態只看旁邊的色燈與其 aria-label／title。
      const note = c.selected ? ''
        : c.reason === 'taken' ? `・已綁給〈${(holder && holder.name) || '其他席位'}〉` : (CHOICE_NOTE[c.reason] || '');
      option.textContent = `${c.label}${note}`; // value＝完整 id（綁定身份），文字只有玩家名稱
      option.disabled = c.disabled;
      select.appendChild(option);
    }
    select.value = row.controller || '';
    select.disabled = locked;
    select.addEventListener('change', (e) => {
      const id = e.target.value;
      if (id) bindSeat(row.player_id, id, gameId);
      else unbindSeat(row.player_id, gameId);
    });
    return select;
  }

  function lobbyRow(row, ctx) {
    const { cur, seats, list, cs, actorId, label } = ctx;
    const el = document.createElement('div');
    el.className = `hs-seat${row.player_id === actorId ? ' hs-actor' : ''}`;
    el.dataset.playerId = row.player_id;
    const name = document.createElement('span');
    name.className = 'hs-seat-name';
    name.textContent = `${row.name || '玩家'}${row.connected ? '（目前）' : ''}`;
    const meta = document.createElement('span');
    meta.className = 'hs-seat-meta';
    const faction = !row.inLobby ? '不在作戰室'
      : row.faction ? `${factionLabel(row.faction) || row.faction}${row.base ? `｜${row.base}` : ''}` : '尚未選擇陣營';
    meta.textContent = `${faction}｜${row.ready ? '已準備' : '未準備'}｜`;
    // 第二行緊湊連續排列：陣營／準備 → 安全名稱＋狀態燈 → 綁定下拉 →（切換），中間沒有撐開的空白。
    const line = document.createElement('div');
    line.className = 'hs-seat-line';
    line.append(meta, joyStatusEl(Core.seatJoyStatus(row, { label, enabled: !!(cs && cs.enabled), roster: list })),
      bindSelect(row, cur.gameId, seats, list, !!cur.started || !(cs && cs.enabled)));
    // 滑鼠備援：與 Joy-Con A 同一條路（記下席位後整頁重新載入，以該席位 resumeToken 重新授權）。
    const sw = button('切換', () => switchLobbySeat(Core.findSeat(loadStore(), cur.gameId, row.player_id)));
    sw.className = 'lobby-mini-btn';
    sw.disabled = !!cur.started || !row.inLobby;
    if (row.connected) {
      // 目前席位不能切換到自己：同尺寸的不可見佔位，讓每列下拉的右緣對齊（不可點、不可聚焦、對輔助技術隱藏）。
      sw.classList.add('hs-switch-slot');
      sw.disabled = true;
      sw.tabIndex = -1;
      sw.setAttribute('aria-hidden', 'true');
    }
    line.appendChild(sw);
    el.append(name, line);
    return el;
  }

  function renderLobby() {
    const box = document.getElementById('hotseatLobby');
    if (!box) return;
    const store = loadStore();
    const cur = session();
    const cs = ctlState();
    // 本分頁監聽連線擁有的手把在主連線 roster 裡是 'other'：顯示時視為本分頁的，不誤報「其他分頁使用中」。
    const list = Core.withLocalOwners(roster(),
      [...listeners.values()].filter(l => l.binding.owned === l.controller).map(l => l.controller));
    const rows = store.enabled && cur.gameId
      ? Core.lobbySeats({ lobby: cur.lobby, store, gameId: cur.gameId, connectedSeatId: cur.playerId }) : [];
    const lv = hs.lobby;
    const label = Core.controllerNames(list);
    const prompt = rows.length >= 2 ? Core.lobbyPrompt(lv, label) : '';
    const sig = JSON.stringify([store.enabled, cur.gameId, cur.playerId, !!cur.started, rows, lv.view, lv.seat && lv.seat.player_id,
      lv.actor && lv.actor.kind, !!(cs && cs.enabled), list, prompt, hs.lobbyNotice, box.dataset.hint || '']);
    if (sig === hs.lobbySig) return;
    const listEl = document.getElementById('hotseatSeatList');
    const active = document.activeElement;
    // 下拉選單開著（聚焦）時不重建，避免選到一半被換掉；離開後下一個 tick 再畫。
    if (active && active.tagName === 'SELECT' && listEl.contains(active)) return;
    hs.lobbySig = sig;
    document.getElementById('hotseatEnableChk').checked = store.enabled;
    const add = document.getElementById('hotseatAddSeatBtn');
    add.hidden = !store.enabled;
    add.disabled = !cur.gameId || !!cur.started;
    const ctx = { cur, seats: rows, list, cs, actorId: lv.seat ? lv.seat.player_id : null, label };
    const children = rows.map(row => lobbyRow(row, ctx));
    if (store.enabled && rows.length && !(cs && cs.enabled)) {
      const enable = button('啟用搖桿控制（綁定 Joy-Con 需要）', () => { if (ctlApi()) ctlApi().setEnabled(true); hs.lobbySig = null; renderLobby(); });
      enable.className = 'lobby-mini-btn';
      children.push(enable);
    }
    listEl.replaceChildren(...children);
    fitLobbyBox(box, store.enabled);
    const actorRow = listEl.querySelector('.hs-actor');
    if (actorRow) actorRow.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    document.getElementById('hotseatLobbyPrompt').textContent = prompt;
    document.getElementById('hotseatLobbyNotice').textContent = hs.lobbyNotice;
    document.getElementById('hotseatLobbyHint').textContent = box.dataset.hint
      || (store.enabled ? '先替每位本機玩家綁定自己的 Joy-Con；輪到的玩家用自己的 Joy-Con 按 A 進入自己的陣營選擇。開局後輪到誰時畫面會先遮住，接手者用自己的 Joy-Con 按 A 確認。' : '');
  }

  /**
   * 大廳欄位沒有固定高度、按鈕列是絕對定位：席位列多了會壓到按鈕。只在 hot-seat 啟用時把這一區限制在按鈕列上方
   * （設計單位；桌面與客廳模式的舞台縮放不同），超出就在區內捲動。未啟用時不改任何樣式。
   */
  function fitLobbyBox(box, enabled) {
    const actions = document.querySelector('#lobby .lobby-actions');
    const stage = document.getElementById('designStage');
    let room = 0;
    if (enabled && actions && stage && box.getClientRects().length) {
      const scale = stage.offsetWidth ? stage.getBoundingClientRect().width / stage.offsetWidth : 1;
      room = Math.floor((actions.getBoundingClientRect().top - box.getBoundingClientRect().top) / scale) - 8;
    }
    const max = room >= 60 ? `${room}px` : '';
    if (box.style.maxHeight !== max) {
      box.style.maxHeight = max;
      box.style.overflowY = max ? 'auto' : '';
    }
  }

  /** 換席位：只記下要恢復哪一席（不解鎖遊戲），整頁重新載入；/resume 以該席位自己的 resumeToken 重新授權。 */
  function switchLobbySeat(seat) {
    const cur = session();
    if (!seat || !cur.gameId || cur.started || hs.reloading) return false;
    if (!Core.findSeat(loadStore(), cur.gameId, seat.player_id)) return false;
    saveSession(Core.switchSession(cur.gameId, seat.player_id));
    hs.lobbyNotice = '';
    lobbyHint(`正在切換到〈${seat.name || '本機玩家'}〉…`);
    reloadInto(seat);
    syncListeners(); // reloading：關閉所有監聽連線
    return true;
  }

  // ------------------------------------------------------------ Joy-Con 逐棒：P1→P2→…→Pn→回到房主 P1 啟動
  // 輪到誰完全由 server /lobby 的陣營＋準備狀態決定（Core.sequentialLobby）。這一棒完成（陣營已選且準備）後，目前分頁自動
  // 整頁切換到下一棒（以該席自己的 resumeToken 重新授權＝browser session、bridge 擁有權、焦點一起交接）；
  // 新分頁載入後依 sessionStorage 的一次性意圖開啟陣營選擇，或（最後回到房主）把焦點放在「啟動行動」。
  const SEQ_KEY = 'redline.hotseat.sequence.v1';
  const SEQ_MAX_SWITCHES = 4; // 同一個目標連續自動切換的上限，避免重新授權失敗時無限重新載入
  const SEQ_INTENT_TTL_MS = 60000;

  function readIntent() {
    try {
      const v = JSON.parse(sessionStorage.getItem(SEQ_KEY) || 'null');
      return v && typeof v === 'object' && typeof v.gameId === 'string' && typeof v.playerId === 'string' ? v : null;
    } catch { return null; }
  }
  function writeIntent(v) { try { sessionStorage.setItem(SEQ_KEY, JSON.stringify(v)); } catch { /* ignore */ } }
  function clearIntent() { try { sessionStorage.removeItem(SEQ_KEY); } catch { /* ignore */ } }

  function syncSequential() {
    const cur = session();
    const seq = hs.lobby && hs.lobby.sequential;
    if (!inLobby() || hs.reloading || hs.provisioning || cur.started || !cur.gameId || !seq) return;
    if (cur.playerId !== seq.turn) {
      const seat = Core.findSeat(loadStore(), cur.gameId, seq.turn);
      if (!seat || !seat.controller) return;
      const target = seq.phase === 'start' ? 'start' : 'picker';
      const prev = readIntent();
      const same = prev && prev.gameId === cur.gameId && prev.playerId === seq.turn && prev.target === target;
      const switches = same ? Number(prev.switches) || 0 : 0;
      if (switches >= SEQ_MAX_SWITCHES) { lobbyHint('自動交棒失敗，請重新整理頁面。'); return; }
      writeIntent({ gameId: cur.gameId, playerId: seq.turn, target, switches: switches + 1, at: Date.now() });
      switchLobbySeat(seat);
      return;
    }
    consumeIntent(cur, seq);
  }

  async function nextPaint() { await new Promise(r => requestAnimationFrame(() => r())); await new Promise(r => requestAnimationFrame(() => r())); }

  function consumeIntent(cur, seq) {
    const intent = readIntent();
    if (!intent || intent.gameId !== cur.gameId || intent.playerId !== cur.playerId) return;
    if (Date.now() - (Number(intent.at) || 0) > SEQ_INTENT_TTL_MS) { clearIntent(); return; }
    const lv = hs.lobby;
    const cs = ctlState();
    // 等主連線真的取得這一棒綁定的那一支（上一棒的分頁已隨重新載入釋放）才聚焦。
    if (lv.view !== 'lobby-open' || !lv.seat || !cs || !cs.controller || cs.controller.owned !== lv.seat.controller) return;
    const kind = lv.actor && lv.actor.kind;
    if (intent.target === 'start') {
      const btn = document.getElementById('startGameBtn');
      if (seq.phase !== 'start' || kind !== 'lobby_start' || !btn || btn.disabled) return;
      if (ctlApi() && typeof ctlApi().focusElement === 'function' && ctlApi().focusElement(btn)) clearIntent();
      return;
    }
    if (kind !== 'lobby_select') {
      const ready = document.getElementById('toggleReadyBtn');
      if (ready && !ready.disabled && ctlApi() && ctlApi().focusElement(ready)) clearIntent();
      return;
    }
    if (hs.seqBusy || typeof window.openFactionPickerModal !== 'function') return;
    hs.seqBusy = true;
    (async () => {
      try {
        const opened = pickerShown() || await window.openFactionPickerModal();
        if (!opened) return;
        await nextPaint();
        const first = document.querySelector('#factionPicker #factionList .faction-choice-btn:not(:disabled)');
        if (first && ctlApi() && ctlApi().focusElement(first)) clearIntent();
      } finally { hs.seqBusy = false; }
    })();
  }

  function lobbyHint(text) {
    const box = document.getElementById('hotseatLobby');
    if (box) box.dataset.hint = text || '';
    renderLobby();
  }

  function setEnabled(enabled) {
    const store = loadStore();
    store.enabled = !!enabled;
    saveStore(store);
    const cur = session();
    if (enabled && cur.gameId && cur.playerId && cur.resumeToken) {
      // 名稱是否為系統預設，以建立／進入作戰室送出時的紀錄為準（app.js session name_auto），不是事後看字串。
      rememberSeat(cur.gameId, cur.playerId, cur.resumeToken, cur.name || (document.getElementById('playerName') || {}).value || '', cur.nameAuto);
    }
    lobbyHint('');
  }

  /**
   * opts.codename：固定預期代號（Joy-Con 配置 P2～P4 用），不隨 nextSeatCodename 跳號。
   * opts.resumePlayerId：server 已建立、但回應遺失的席位；改以既有 /join resume（player_id＋device_id）取回同一席，不 append。
   */
  async function addLocalSeat(opts) {
    const { codename, resumePlayerId } = opts || {};
    const cur = session();
    if (!cur.gameId) { lobbyHint('請先建立或進入作戰室。'); return; }
    if (cur.started) return;
    // 行動代號：使用者在欄位輸入過（非空）＝自訂名稱；否則（Joy-Con 玩家不必打字）用 server lobby 下一個位置的 P 代號。
    const nameInput = document.getElementById('playerName');
    const typed = String((nameInput || {}).value || '').trim();
    const explicit = !codename && !!nameInput && nameInput.dataset.userEdited === '1' && !!typed;
    let name = codename || typed;
    if (!explicit && !codename) {
      const lobbyRes = (typeof refreshLobbyState === 'function' ? await refreshLobbyState().catch(() => null) : null) || cur.lobby;
      name = Core.nextSeatCodename(lobbyRes);
      if (!name) { lobbyHint('作戰室已滿，無法新增本機玩家。'); return; }
    }
    if (cur.playerId && cur.resumeToken) rememberSeat(cur.gameId, cur.playerId, cur.resumeToken, '');
    if (Core.seatsFor(loadStore(), cur.gameId).some(s => s.name === name)) { lobbyHint('本機已有同名玩家，請換一個名稱。'); return; }
    let data;
    try {
      const res = await fetch('/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // 一般新增不帶 player_id／resume_token：一定建立新席位，不會恢復（覆寫）既有席位；
        // 只有取回遺失回應的孤兒席位才帶它的公開 player_id（server 以同一 device_id 驗證 resume）。
        body: JSON.stringify({
          game_id: cur.gameId, name, device_id: typeof redlineDeviceId === 'function' ? redlineDeviceId() : '',
          ...(resumePlayerId ? { player_id: resumePlayerId } : {}),
        }),
      });
      data = await res.json();
    } catch {
      lobbyHint('無法連線到伺服器，請再試一次。');
      return;
    }
    if (!data || data.error || !data.player_id || !data.resume_token) {
      lobbyHint(data && data.error && typeof playerMessageZhTw === 'function' ? playerMessageZhTw(data.error) : '無法新增玩家。');
      return;
    }
    const result = Core.addSeat(loadStore(), cur.gameId, { player_id: data.player_id, resume_token: data.resume_token, name, auto_name: !explicit });
    if (!result.ok) { lobbyHint('本機席位已滿。'); return; }
    saveStore(result.store);
    // 不自動切換：留在目前席位，先綁定 Joy-Con，再由那位玩家用自己的 Joy-Con 按 A 進入自己的席位。
    // 輸入的名稱已用掉：下一次新增若沒有再輸入，就用自動代號。
    const me = Core.findSeat(result.store, cur.gameId, cur.playerId);
    if (nameInput && nameInput.dataset.userEdited) nameInput.dataset.userEdited = 'used';
    if (nameInput && me && me.name) nameInput.value = me.name;
    lobbyHint(`已新增〈${name}〉；請在下方替這位玩家綁定 Joy-Con，輪到時用它按 A 進入自己的陣營選擇。`);
    // 席位已在 server 與本機都建立；刷新名單只是顯示。失敗（網路瞬斷）不可讓呼叫端誤判成「席位建立失敗」。
    if (typeof refreshLobbyState === 'function') await refreshLobbyState().catch(() => null);
    return data.player_id;
  }

  /**
   * 開始流程配對了多支 Joy-Con：啟用客廳輪流，目前席位（房主）綁第 1 支，其餘依配對順序各新增一個本機席位（行動代號 P2～P4）
   * 並綁定。沿用上面的 setEnabled／addLocalSeat／bindSeat，且可重入：已存在的本機席位直接沿用、不再 /join，
   * 部分成功後重試不會產生重複席位。最後以本機席位表驗證每支手把都綁在預期席位，才回報成功。
   * 回傳 { ok, error? }。
   */
  function provisionSeats(controllers) {
    // 同時只跑一個：重複呼叫（連點重試、雙重觸發）共用同一次配置，不會重複 /join。
    if (hs.provisioning) return hs.provisioning;
    const run = provisionSeatsOnce(controllers).catch(() => ({ ok: false, error: 'Joy-Con 席位建立失敗，請重試。' }))
      .finally(() => {
        hs.provisioning = null;
        refreshLobbyVerdict(); syncClaim(); syncListeners(); renderLobby();
      });
    hs.provisioning = run;
    return run;
  }

  async function provisionSeatsOnce(controllers) {
    const list = Array.isArray(controllers) ? controllers.filter(Core.isControllerId) : [];
    const cur = session();
    if (list.length < 2 || !cur.gameId || !cur.playerId) return { ok: false, error: '尚無可配置的房間或手把。' };
    setEnabled(true);
    const seatIds = [cur.playerId];
    const others = () => Core.seatsFor(loadStore(), cur.gameId).map(s => s.player_id).filter(id => id !== cur.playerId);
    for (let i = 1; i < list.length; i += 1) {
      let seatId = others()[i - 1];
      if (!seatId) {
        // 固定預期代號 P{i+1}；若上次 /join 已在 server 建立該席位但回應遺失，取回同一席而不是跳號新增。
        const codename = Core.CODENAMES[i];
        const lobbyRes = (typeof refreshLobbyState === 'function' ? await refreshLobbyState().catch(() => null) : null) || session().lobby;
        const created = await addLocalSeat({ codename, resumePlayerId: Core.orphanSeatId(lobbyRes, loadStore(), cur.gameId, codename) || undefined });
        seatId = created || others()[i - 1];
      }
      if (!seatId) return { ok: false, error: `P${i + 1} 席位建立失敗，請重試。` };
      seatIds.push(seatId);
    }
    for (let i = 0; i < list.length; i += 1) {
      if (!bindSeat(seatIds[i], list[i], cur.gameId).ok) return { ok: false, error: `P${i + 1} 的 Joy-Con 綁定失敗，請重試。` };
    }
    const store = loadStore();
    const verified = list.every((controller, i) => {
      const seat = Core.seatForController(store, cur.gameId, controller);
      return !!seat && seat.player_id === seatIds[i];
    });
    return verified ? { ok: true } : { ok: false, error: 'Joy-Con 席位驗證失敗，請重試。' };
  }

  function init() {
    const maskNode = maskEl();
    if (maskNode) maskNode.querySelector('#hotseatAiDismiss').addEventListener('click', ackAiTurn);
    const chk = document.getElementById('hotseatEnableChk');
    if (chk) chk.addEventListener('change', (e) => setEnabled(e.target.checked));
    const add = document.getElementById('hotseatAddSeatBtn');
    if (add) add.addEventListener('click', () => { addLocalSeat(); });
    if (ctlApi() && typeof ctlApi().attachGate === 'function') ctlApi().attachGate(gate);
    // 遮罩時鍵盤也不穿透到被遮住的頁面（遮罩自己的按鈕除外）。
    window.addEventListener('keydown', (e) => {
      if (Core.masked(hs.verdict.view) && !(e.target && e.target.closest && e.target.closest('#hotseatMask'))) {
        e.stopImmediatePropagation();
        e.preventDefault();
      }
    }, true);
    hs.timer = setInterval(() => {
      if (hs.verdict.view !== 'inactive') { syncClaim(); renderMask(); }
      else if (inLobby()) { refreshLobbyVerdict(); syncClaim(); syncSequential(); }
      syncListeners();
      renderLobby();
      const box = document.getElementById('hotseatLobby');
      if (box) fitLobbyBox(box, loadStore().enabled);
    }, 400);
    render();
  }

  window.RedlineHotSeat = {
    onConnect, onState, onLobby, onLobbyState, resumeTarget, rememberSeat, provisionSeats,
    isLocalSeat: (gameId, playerId) => !!Core.findSeat(loadStore(), gameId, playerId),
    /** AI 紅軍公開行動視窗正開著：app.js 據此略過「玩家動態」通知，同一件事不顯示兩次。 */
    /** 客廳輪流遊戲裡有 AI 紅軍、伺服器還沒啟用「結束回合前等公開視窗確認」：app.js 送出 ai_public_hold。 */
    wantsAiPublicHold: (state) => !!state && hs.verdict.view !== 'inactive' && !!state.ai_red_army
      && state.ai_red_army.enabled === true && state.ai_red_army.public_hold !== true,
    aiPublicActive: () => {
      const el = document.getElementById('hotseatMask');
      return !!el && el.dataset.aiPublic === 'on' && Core.masked(hs.verdict.view);
    },
    // 除錯／E2E：三個身份分開回報。
    getState: () => {
      const cs = ctlState();
      const owned = cs && cs.controller ? cs.controller.owned : null;
      const store = loadStore();
      const stateGameId = hs.gameId || session().gameId;
      const ownerSeat = stateGameId ? Core.seatForController(store, stateGameId, owned) : null;
      const aiEl = document.getElementById('hotseatMask');
      return {
        aiPublic: {
          open: !!aiEl && aiEl.dataset.aiPublic === 'on',
          ended: !!(hs.aiShown && hs.aiShown.ended),
          steps: aiEl ? aiEl.querySelectorAll('#hotseatAiSteps .hs-ai-step').length : 0,
          text: aiEl && aiEl.dataset.aiPublic === 'on' ? (aiEl.querySelector('#hotseatAiPublic').textContent || '').replace(/\s+/g, ' ').trim() : '',
        },
        view: hs.verdict.view,
        displayedSeat: hs.connectedSeat,
        controllerOwner: { controller: owned, seat: ownerSeat ? ownerSeat.player_id : null },
        actor: hs.verdict.actor ? { ...hs.verdict.actor } : null,
        handoffSeat: hs.verdict.seat ? hs.verdict.seat.player_id : null,
        session: loadSession(hs.gameId || session().gameId),
        seats: (hs.gameId || session().gameId)
          ? Core.seatsFor(store, hs.gameId || session().gameId).map(s => ({ player_id: s.player_id, name: s.name, controller: s.controller })) : [],
        // 大廳：要聽哪一席的 Joy-Con（lobby actor）；displayedSeat＝目前以哪一席連線（大廳為 RedlineSession 的 playerId）。
        lobby: {
          mode: inLobby(), view: hs.lobby.view, seat: hs.lobby.seat ? hs.lobby.seat.player_id : null,
          actorKind: hs.lobby.actor ? hs.lobby.actor.kind : null, connectedSeat: inLobby() ? session().playerId : null,
          notice: hs.lobbyNotice, prompt: Core.lobbyPrompt(hs.lobby, controllerText),
          // 監聽連線：其他已綁定席位的 controller、該連線目前在 bridge 擁有哪一支
          listeners: [...listeners.values()].map(l => ({ controller: l.controller, owned: l.binding.owned, open: !!l.socket })),
        },
      };
    },
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
