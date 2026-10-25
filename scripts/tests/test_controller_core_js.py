"""執行 static/controller_core.js 的 node:test 單元測試（輸入 reducer／repeat／context routing／地圖 fail-closed）。"""

import pathlib
import re
import shutil
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_controller_core_node_tests():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/controller_core.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_controller_dual_joycon_node_tests():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/controller_dual.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_controller_map_adapter_node_tests():
    # 戰略地圖 iframe adapter 的 SL 全域地圖聚焦（canonical 城鎮清單、focusTown 精確置中放大、不觸發 action、fail closed）。
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/controller_map_adapter.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_player_visible_controller_names_use_the_current_roster():
    # 🎮 設定面板（我的手把、選擇手把）、提示膠囊與客廳狀態列的手把名稱一律經 Core.controllerLabel／bindingBadge，
    # 並帶目前 roster（同側多支的序號）；不得直接顯示 c.id、c.name 或 endpoint。
    ui = (_ROOT / "static/controller_ui.js").read_text(encoding="utf-8")
    for call in ("Core.controllerLabel(", "Core.bindingBadge("):
        parts = ui.split(call)[1:]
        assert parts, call
        for rest in parts:
            assert "rosterList()" in rest.split(")", 1)[0] + ")", call + rest[:80]
    for leak in ("c.name", "c.endpoint", "${c.id}", "${id}"):
        assert leak not in ui, leak
    assert "左右＋埠" not in ui
    # 下拉選項的停用規則（其他玩家使用中、沒有訊號）不變，且不在註解裡。
    disabled = "disabled: c.owner === 'other' || (c.owner !== 'you' && c.status !== 'active')"
    line = next(row for row in ui.splitlines() if disabled in row)
    assert "//" not in line.split(disabled, 1)[0], line
    html = (_ROOT / "static/index.html").read_text(encoding="utf-8")
    for script in ("controller_core.js", "controller_ui.js"):
        match = re.search(rf'/static/{re.escape(script)}\?v=([^"\']+)', html)
        assert match and match.group(1), script
