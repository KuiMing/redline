"""執行 static/living_room_core.js 的 node:test 單元測試，並檢查客廳模式 CSS 只在 living-room 屬性下生效。"""

import pathlib
import re
import shutil
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_LR_SECTION_MARKER = "/* ---- 客廳大螢幕模式（controller_living_room.js）"


def test_living_room_core_node_tests():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/living_room_core.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_living_room_css_is_scoped_to_the_display_attribute():
    css = (_ROOT / "static/style.css").read_text(encoding="utf-8")
    assert _LR_SECTION_MARKER in css
    section = css.split(_LR_SECTION_MARKER, 1)[1].split("*/", 1)[1]
    section = re.sub(r"/\*.*?\*/", "", section, flags=re.S)
    selectors = re.findall(r"([^{}]+)\{", section)
    assert selectors
    for group in selectors:
        for selector in group.split(","):
            assert selector.strip().startswith('html[data-display="living-room"]'), selector.strip()


def test_stage_scale_has_no_living_room_safe_area():
    # 客廳大螢幕顯示模式已移除：舞台縮放只剩桌面（不再有 5% title-safe 分支），設定面板也不再有顯示模式選單。
    app = (_ROOT / "static/app.js").read_text(encoding="utf-8")
    assert "LIVING_ROOM_SAFE_AREA_SCALE" not in app and "dataset.display" not in app
    layer = (_ROOT / "static/controller_living_room.js").read_text(encoding="utf-8")
    assert "padDisplaySelect" not in layer and "客廳大螢幕</option>" not in layer
