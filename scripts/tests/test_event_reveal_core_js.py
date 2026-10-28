"""static/event_reveal_core.js 的 node:test，以及事件卡自動揭示在頁面上的接線檢查。"""

import pathlib
import shutil
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_event_reveal_core_node_tests():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/event_reveal_core.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_event_reveal_core_loads_before_app_and_render_uses_it():
    html = (_ROOT / "static/index.html").read_text(encoding="utf-8")
    core = html.index("/static/event_reveal_core.js?v=")
    assert core < html.index("/static/app.js?v=")
    app = (_ROOT / "static/app.js").read_text(encoding="utf-8")
    body = app.split("function renderCurrentEvent(state) {", 1)[1].split("\nfunction ", 1)[0]
    assert "window.RedlineEventRevealCore.decideAutoReveal(" in body
    # 自動揭示只經過共用判定，不再有直接以事件 key 比對就打開的舊路徑。
    assert body.count("openCurrentEventReveal()") == 1
    assert "if (decision.open) openCurrentEventReveal();" in body
