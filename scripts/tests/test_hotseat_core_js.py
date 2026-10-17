"""執行 static/hotseat_core.js 的 node:test 單元測試，並檢查客廳輪流模式的頁面接線。"""

import pathlib
import re
import shutil
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_hotseat_core_node_tests():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/hotseat_core.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_hotseat_scripts_load_before_the_stage_renders():
    html = (_ROOT / "static/index.html").read_text(encoding="utf-8")
    head = html.split("</head>", 1)[0]
    # 遮罩必須在第一次繪製前就能生效，所以兩支腳本都在 <head>。
    assert "/static/hotseat_core.js" in head
    assert "/static/hotseat_ui.js" in head
    assert head.index("/static/hotseat_core.js") < head.index("/static/hotseat_ui.js")


def test_controller_dispatch_passes_through_the_hotseat_gate_first():
    ui = (_ROOT / "static/controller_ui.js").read_text(encoding="utf-8")
    body = ui.split("function dispatch(action) {", 1)[1]
    first_statements = body.split("releaseExcludedFocus();", 1)[0]
    assert "gate.intercept(action" in first_statements
    assert "attachGate" in ui


def test_app_state_is_offered_to_hotseat_before_render():
    app = (_ROOT / "static/app.js").read_text(encoding="utf-8")
    handler = app.split("ws.onmessage = async (event) => {", 1)[1].split("};", 1)[0]
    assert handler.index("RedlineHotSeat") < handler.index("await render(state)")


def _function_body(source: str, signature: str) -> str:
    body = source.split(signature, 1)[1]
    depth, out = 1, []
    for ch in body:
        depth += ch == "{"
        depth -= ch == "}"
        if depth == 0:
            break
        out.append(ch)
    return "".join(out)


def test_single_controller_auto_claim_defers_to_the_hotseat_lobby():
    # 大廳 hot-seat 由 lobby actor 決定 claim 哪一支；舊的「唯一一支就自動 claim」不能搶走它。
    ui = (_ROOT / "static/controller_ui.js").read_text(encoding="utf-8")
    body = _function_body(ui, "function maybeAutoClaim() {")
    assert "gate.managesClaims()" in body
    assert body.index("gate.managesClaims()") < body.index("Core.autoClaimDecision")


def test_lobby_state_is_offered_to_hotseat_after_each_roster_render():
    app = (_ROOT / "static/app.js").read_text(encoding="utf-8")
    current = app.split("window.RedlineSession = {", 1)[1].split("};", 1)[0]
    assert "lobby: latestLobbyState" in current
    roster = _function_body(app, "function renderLobbyRoster(lobbyRes, statusText = null) {")
    assert roster.index("latestLobbyState = lobbyRes") < roster.index("RedlineHotSeat?.onLobbyState")


def test_lobby_seat_switch_is_a_full_reload_with_the_seats_own_token():
    # 不可只切 DOM／playerId：大廳換席位一律記下目標席位後整頁重新載入，由 /resume 以該席位 resumeToken 重新授權。
    app = (_ROOT / "static/app.js").read_text(encoding="utf-8")
    ui = (_ROOT / "static/hotseat_ui.js").read_text(encoding="utf-8")
    assert "adoptLobbySeat" not in app
    assert "adoptLobbySeat" not in ui
    switch = _function_body(ui, "function switchLobbySeat(seat) {")
    assert "Core.switchSession(" in switch
    assert "reloadInto(" in switch
    gate = _function_body(ui, "intercept(action, { owned }) {")
    assert "Core.lobbyInput(" in gate
    assert "switchLobbySeat(" in gate


def test_lobby_listeners_reuse_the_existing_bridge_pipeline_and_only_switch_on_A():
    # 每個已綁定的其他本機席位：一條只 claim 該席 controller 的 bridge 連線；frame 走既有 controller_core 管線，
    # 只有 reducer 產生的 A 才切換（經 Core.listenerSwitchTarget → switchLobbySeat 整頁重新授權），不另做按鍵規則。
    ui = (_ROOT / "static/hotseat_ui.js").read_text(encoding="utf-8")
    body = _function_body(ui, "function onListenerMessage(listener, raw) {")
    for call in ("CtlCore().classifyBridgeMessage(", "CtlCore().acceptControllerFrame(", "CtlCore().stepControllerInput(",
                 "Core.listenerSwitchTarget(", "switchLobbySeat("):
        assert call in body, call
    assert body.index("acceptControllerFrame") < body.index("stepControllerInput") < body.index("listenerSwitchTarget")
    open_body = _function_body(ui, "function openListener(controller) {")
    assert "CtlCore().bridgeHello()" in open_body
    claim = _function_body(ui, "function claimForListener(listener) {")
    assert "type: 'claim', controller: listener.controller" in claim
    sync = _function_body(ui, "function syncListeners() {")
    assert "Core.lobbyListeners(" in sync


def test_changed_scripts_are_cache_busted_together():
    html = (_ROOT / "static/index.html").read_text(encoding="utf-8")
    assert "/static/hotseat_core.js?v=hotseat-codename-p1234-20261017" in html
    assert "/static/hotseat_ui.js?v=hotseat-codename-p1234-20261017" in html
    assert "/static/app.js?v=hotseat-codename-p1234-20261017" in html
    # controller_ui.js 之後又因玩家可見手把名稱改版（test_controller_core_js 檢查其版本）
    assert "/static/controller_ui.js?v=joycon-labels-20261016" in html


def test_player_visible_controller_labels_hide_ports_and_ids():
    # 玩家看到的手把名稱只來自 Core.controllerNames（左右＋同側本機序號）；不從 id 取埠號、不顯示 bridge name 指紋。
    ui = (_ROOT / "static/hotseat_ui.js").read_text(encoding="utf-8")
    label = _function_body(ui, "function controllerText(id) {")
    assert "Core.controllerNames(" in label
    assert "exec(" not in label
    assert "c.name" not in ui
    # 席位列不再有「有訊號」狀態文字（舊的 seatJoyText／STATUS_NOTE 已移除）
    assert "'有訊號'" not in ui
    assert "seatJoyText" not in ui
    # 席位列狀態燈：可存取名稱（aria-label＋title），色調來自 Core.seatJoyStatus（異常不會是綠燈）。
    dot = _function_body(ui, "function joyStatusEl(status) {")
    for needed in ("'role', 'img'", "'aria-label', status.aria", "title = status.aria", "dataset.tone = status.tone"):
        assert needed in dot, needed
    assert "Core.seatJoyStatus(" in _function_body(ui, "function lobbyRow(row, ctx) {")


def test_lobby_row_packs_status_light_and_binding_select_contiguously():
    # 席位列：陣營／準備、安全名稱＋狀態燈、綁定下拉（與切換鈕）在同一行緊湊連續排列；不再有把下拉推到最右邊的 flex:1 空白。
    ui = (_ROOT / "static/hotseat_ui.js").read_text(encoding="utf-8")
    row = _function_body(ui, "function lobbyRow(row, ctx) {")
    assert "hs-seat-line" in row
    packed = row.split("line.append(", 1)[1].split(");", 1)[0]
    assert packed.index("meta") < packed.index("joyStatusEl(") < packed.index("bindSelect(")
    assert ".hs-seat-info { flex: 1" not in ui
    assert ".hotseat-lobby .hs-seat-line {" in ui
    # 已綁定那一支（選中的選項）不附加狀態註記（狀態只看色燈＋aria／title）；其他選項的不可選原因與停用規則不變。
    # 綁定下拉固定為容得下安全名稱（最長「右 Joy-Con 4」）與「— 未綁定 —」＋原生箭頭的緊湊寬度（瀏覽器幾何由 E2E 驗證）；
    # 不再依最長選項（例如「・已綁給〈…〉」）自動撐寬到 130px。
    rule = ui.split(".hotseat-lobby .hs-bind-select {", 1)[1].split("}", 1)[0]
    assert re.search(r"(^|;)\s*width:\s*[\d.]+em\b", rule), rule
    assert "130px" not in rule
    assert "width: 9.25em" in rule and "font-size: 12px" in rule, rule
    # 靠右對齊：安全名稱＋燈 → 下拉 → 切換 是一個緊湊群組，以 margin-left:auto 推到列的右緣（空白只在陣營／準備與群組之間）。
    joy = ui.split(".hotseat-lobby .hs-joy {", 1)[1].split("}", 1)[0]
    assert "margin-left: auto" in joy, joy
    # 安全名稱＋燈 是固定寬度欄（em，靠左起排）：每列名稱的左緣對齊（「左 Joy-Con」與「右 Joy-Con 1」不再錯開）；
    # 不靠 flex:1，也不裁切（容得下最長名稱＋燈的幾何由 E2E 驗證）。
    assert re.search(r"(^|;)\s*width:\s*[\d.]+em\b", joy), joy
    assert "justify-content: flex-start" in joy, joy
    assert "flex: 1" not in joy and "overflow: hidden" not in joy, joy
    # 目前席位沒有「切換」：放同尺寸、不可見、不可聚焦、對輔助技術隱藏的佔位，讓每列下拉的右緣對齊。
    assert ".hotseat-lobby .hs-switch-slot { visibility: hidden; }" in ui
    slot = row.split("if (row.connected)", 1)[1].split("}", 1)[0]
    for needed in ("hs-switch-slot", "sw.disabled = true", "sw.tabIndex = -1", "'aria-hidden', 'true'"):
        assert needed in slot, needed
    select = _function_body(ui, "function bindSelect(row, gameId, seats, list, locked) {")
    assert "c.selected ? ''" in select
    assert "option.disabled = c.disabled;" in select


def test_codename_default_is_distinguished_from_user_input_at_submit_time():
    # 系統預設＝欄位的 HTML 預設值（host）且使用者沒有在欄位輸入過；使用者輸入（即使也是 host）一律是自訂。
    # 在建立／進入作戰室送出時判定並隨 session 記錄（name_auto），不是事後只看字串。
    html = (_ROOT / "static/index.html").read_text(encoding="utf-8")
    assert 'id="playerName" class="lobby-text-input" placeholder="輸入玩家名稱 / 代號" value="host"' in html
    app = (_ROOT / "static/app.js").read_text(encoding="utf-8")
    default = _function_body(app, "function playerNameIsSystemDefault() {")
    assert "input.dataset.userEdited) return false" in default and "defaultValue" in default
    init = _function_body(app, "async function initLobbyControls() {")
    assert "nameInput.dataset.userEdited = '1'" in init
    for sig in ("async function createRoom() {", "async function joinRoom() {"):
        body = _function_body(app, sig)
        assert body.index("playerNameIsSystemDefault()") < body.index("fetch(")
        assert re.search(r"saveRedlineSession\(\w+, nameAuto\)", body), sig
    save = _function_body(app, "function saveRedlineSession(name = '', nameAuto) {")
    assert "name_auto" in save
    assert "rememberSeat?.(gameId, playerId, resumeToken, sessions[gameId].name, sessions[gameId].name_auto)" in save
    current = app.split("window.RedlineSession = {", 1)[1].split("};", 1)[0]
    assert "nameAuto" in current


def test_codenames_are_written_to_the_server_lobby_through_the_authorized_join():
    # 不只改 DOM：代號以既有 /join（該席 player_id＋自己的 resume_token）寫進 server 權威 lobby；只在大廳、依 Core.codenameRenames。
    ui = (_ROOT / "static/hotseat_ui.js").read_text(encoding="utf-8")
    sync = _function_body(ui, "function syncCodenames() {")
    assert "Core.codenameRenames(" in sync and "inLobby()" in sync
    rename = _function_body(ui, "async function renameSeat(gameId, r) {")
    for needed in ("fetch('/join'", "player_id: r.player_id", "resume_token: r.resume_token", "name: r.name", "refreshLobbyState"):
        assert needed in rename, needed
    assert "syncCodenames()" in _function_body(ui, "function onLobbyState() {")
    remember = _function_body(ui, "function rememberSeat(gameId, playerId, resumeToken, name, autoName) {")
    assert "auto_name: autoName" in remember
    enable = _function_body(ui, "function setEnabled(enabled) {")
    assert "cur.nameAuto" in enable


def test_added_local_seats_get_a_codename_without_typing():
    # 新增本機玩家：使用者沒有輸入新名稱 → 依 server lobby 下一個位置的 P 代號（Core.nextSeatCodename），不要求打字；
    # 滿 4 席（沒有代號）不呼叫 /join、不發明 P5。
    ui = (_ROOT / "static/hotseat_ui.js").read_text(encoding="utf-8")
    add = _function_body(ui, "async function addLocalSeat() {")
    assert "Core.nextSeatCodename(" in add
    assert "dataset.userEdited === '1'" in add
    assert "請先在「玩家名稱」輸入新玩家的名稱" not in add
    assert add.index("Core.nextSeatCodename(") < add.index("fetch('/join'")
    assert "auto_name: !explicit" in add


def test_hotseat_css_hides_the_stage_while_masked():
    # 樣式由 <head> 內的 hotseat_ui.js 立即注入（第一次繪製前），不放在 style.css 的客廳模式區段。
    ui = (_ROOT / "static/hotseat_ui.js").read_text(encoding="utf-8")
    assert 'html[data-hotseat="masked"] #stageViewport' in ui
    assert "visibility: hidden" in ui
