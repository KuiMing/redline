"""執行 townDisplayLatLng 的 node:test（投影非有限時退回原始座標，不產生 NaN LatLng）。"""

import pathlib
import shutil
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_town_display_latlng_node_tests():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    result = subprocess.run(
        ["node", "--test", str(_ROOT / "scripts/tests/js/town_display_latlng.test.js")],
        cwd=_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
