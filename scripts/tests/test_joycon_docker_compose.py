"""docker-compose.yml 的 joycon-bridge service：port 發布、Origin 預設、UDP host、healthcheck、game port 不衝突。"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]


def test_bridge_port_is_loopback_only_default_8000():
    assert COMPOSE["joycon-bridge"]["ports"] == ["127.0.0.1:${REDLINE_JOYCON_HOST_PORT:-8000}:8000"]


def test_game_default_host_port_moved_off_bridge_port():
    assert COMPOSE["redline"]["ports"] == ["${REDLINE_HOST_PORT:-8100}:8000"]
    assert COMPOSE["redline-mcp"]["ports"] == ["127.0.0.1:${REDLINE_MCP_HOST_PORT:-8765}:8080"]


def test_bridge_command_binds_all_inside_and_targets_host_ftcw():
    cmd = COMPOSE["joycon-bridge"]["command"]
    assert cmd[cmd.index("--bind-host") + 1] == "0.0.0.0"
    assert cmd[cmd.index("--udp-host") + 1] == "${REDLINE_JOYCON_UDP_HOST:-host.docker.internal}"


def test_bridge_default_origin_follows_game_url_and_is_overridable():
    value = COMPOSE["joycon-bridge"]["environment"]["REDLINE_JOYCON_ALLOW_ORIGINS"]
    assert value.startswith("${REDLINE_JOYCON_ALLOW_ORIGINS:-")
    assert "http://127.0.0.1:${REDLINE_HOST_PORT:-8100}" in value
    assert "http://localhost:${REDLINE_HOST_PORT:-8100}" in value


def test_bridge_healthcheck_uses_stdlib_not_curl():
    test = " ".join(COMPOSE["joycon-bridge"]["healthcheck"]["test"])
    assert "curl" not in test and "urllib.request" in test and "127.0.0.1:8000/health" in test


def test_bridge_dockerfile_has_no_dev_deps_and_no_game_code():
    text = (ROOT / "tools/joycon_bridge/Dockerfile").read_text()
    assert "uv sync --frozen --no-dev" in text
    assert not re.search(r"^COPY (server|static|data)/", text, re.M)


def test_dockerfiles_do_not_require_remote_syntax_frontend():
    """這些 Dockerfile 不使用 frontend 專屬功能，不應為解析檔案再依賴 Docker Hub。"""
    for relative in ("Dockerfile", "mcp_server/Dockerfile", "tools/joycon_bridge/Dockerfile"):
        assert not (ROOT / relative).read_text().startswith("# syntax=")
