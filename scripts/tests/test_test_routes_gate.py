import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_PROBE = """
import sys
from fastapi.testclient import TestClient
from server.main import app, test_setup_hand_preview

client = TestClient(app)
response = client.post(
    "/test/setup-hand-preview",
    json={
        "faction_id": "tibet_dehradun",
        "base": "德拉敦",
        "resources": {"money": 0, "propaganda": 0},
        "hand_names": [],
    },
)
print(response.status_code)
# The direct in-process callable must stay available either way: it is not
# an HTTP-reachable surface, so it is not gated.
assert callable(test_setup_hand_preview)
sys.exit(0)
"""


def _run_probe(env_overrides=None, env_unset=()):
    env = dict(os.environ)
    for key in env_unset:
        env.pop(key, None)
    env.update(env_overrides or {})
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return int(result.stdout.strip().splitlines()[-1])


def test_test_routes_are_unreachable_when_env_var_unset():
    status = _run_probe(env_unset=("ENABLE_TEST_ROUTES",))
    assert status == 404


def test_test_routes_are_unreachable_when_env_var_false():
    status = _run_probe({"ENABLE_TEST_ROUTES": "false"})
    assert status == 404


def test_test_routes_are_reachable_when_env_var_true():
    status = _run_probe({"ENABLE_TEST_ROUTES": "true"})
    assert status == 200
