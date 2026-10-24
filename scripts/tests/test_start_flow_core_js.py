"""static/start_flow_core.js 的 node:test，以及開始流程的頁面接線檢查。"""

import pathlib
import shutil
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_start_flow_core_node_tests():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/start_flow_core.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_start_flow_markup_has_three_paths_and_no_player_count_choice():
    html = (_ROOT / "static/index.html").read_text(encoding="utf-8")
    flow = html.split('id="startFlow"', 1)[1].split('<section class="lobby-card"', 1)[0]
    for needle in ("建立真人紅軍遊戲", "建立 AI 紅軍遊戲", "輸入房間代碼加入", "簡單模式", "一般模式", "Joy-Con", "電腦", "SL + SR", "繼續"):
        assert needle in flow, needle
    assert "人數" not in flow and "<select" not in flow


def test_start_flow_scripts_load_after_controller_scripts():
    html = (_ROOT / "static/index.html").read_text(encoding="utf-8")
    order = [html.index(name) for name in (
        "/static/app.js", "/static/controller_core.js", "/static/controller_ui.js",
        "/static/start_flow_core.js", "/static/start_flow_ui.js")]
    assert order == sorted(order)


def test_app_sends_start_settings_to_create_and_shows_start_flow_when_no_session():
    app = (_ROOT / "static/app.js").read_text(encoding="utf-8")
    create = app.split("async function createRoom() {", 1)[1].split("async function chooseFaction", 1)[0]
    assert "RedlineStartFlow?.pendingCreate" in create and "startSettings" in create
    assert "RedlineStartFlow?.onRoomSettings" in app
    init = app.split("async function initLobbyControls() {", 1)[1].split("window.RedlineSession", 1)[0]
    assert "RedlineStartFlow?.show" in init


def test_stage_is_still_fixed_1280x720_and_living_room_hand_zoom_is_kept():
    css = (_ROOT / "static/style.css").read_text(encoding="utf-8")
    assert "#hand .hand-card { zoom: 0.78; }" in css
    assert "width: 1280px;" in css
