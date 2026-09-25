"""Static checks on docker-compose.yml / mcp_server/Dockerfile / the
existing root Dockerfile — catch config regressions (a port mapping
accidentally opened to the LAN, a broken depends_on, a Dockerfile that
starts pulling in server/ code) without needing an actual `docker build`.

Actually building both images and bringing up a real Compose stack is done
separately (not as a pytest test — real `docker build`/`compose up` are slow
and this repo's test suite otherwise runs in seconds) by
scripts/validate/mcp_docker_compose_smoke.py; see docs/mcp_server.md.
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMPOSE_PATH = ROOT / "docker-compose.yml"
MCP_DOCKERFILE_PATH = ROOT / "mcp_server" / "Dockerfile"
ROOT_DOCKERFILE_PATH = ROOT / "Dockerfile"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_compose_defines_exactly_the_two_expected_services():
    services = _compose()["services"]
    assert set(services) == {"redline", "redline-mcp"}


def test_redline_service_builds_from_existing_unmodified_dockerfile():
    redline = _compose()["services"]["redline"]
    assert redline["build"]["context"] == "."
    assert redline["build"].get("dockerfile", "Dockerfile") == "Dockerfile"
    # The existing single-container instructions in README.md map 8000:8000
    # with no host-IP restriction; Compose must not become MORE restrictive
    # than that by default for the game service (only the new MCP service
    # gets the localhost-only default — see the next test).
    ports = redline["ports"]
    assert len(ports) == 1
    assert ports[0].endswith(":8000")
    assert not ports[0].startswith("127.0.0.1:")


def test_mcp_service_builds_from_its_own_dockerfile_and_binds_localhost_only_by_default():
    mcp = _compose()["services"]["redline-mcp"]
    assert mcp["build"]["context"] == "."
    assert mcp["build"]["dockerfile"] == "mcp_server/Dockerfile"
    ports = mcp["ports"]
    assert len(ports) == 1
    # The whole point of this requirement: `docker compose up` with no
    # overrides must never expose the unauthenticated MCP endpoint beyond
    # the Docker host itself.
    assert ports[0].startswith("127.0.0.1:"), f"MCP port mapping must default to 127.0.0.1-only, got: {ports[0]}"
    assert ports[0].endswith(":8080")


def test_mcp_service_reaches_redline_over_compose_network_not_host_docker_internal():
    mcp = _compose()["services"]["redline-mcp"]
    base_url = mcp["environment"]["REDLINE_BASE_URL"]
    assert base_url == "http://redline:8000"
    assert "host.docker.internal" not in base_url
    assert mcp["environment"]["REDLINE_MCP_HTTP_HOST"] == "0.0.0.0"


def test_mcp_service_can_start_without_waiting_on_redline_healthy():
    # Per requirement: the MCP process must be ABLE to start before REDLINE
    # is ready (each tool call surfaces a clear error at call time instead;
    # see mcp_server/tools/errors.py). depends_on must therefore not block
    # startup on redline's healthcheck passing.
    mcp = _compose()["services"]["redline-mcp"]
    depends_on = mcp["depends_on"]
    assert depends_on["redline"]["condition"] != "service_healthy"


def test_both_services_declare_a_healthcheck():
    services = _compose()["services"]
    for name in ("redline", "redline-mcp"):
        assert "healthcheck" in services[name], f"{name} has no healthcheck"
        assert services[name]["healthcheck"]["test"], f"{name} healthcheck has no test command"


def test_mcp_healthcheck_targets_health_endpoint_not_game_state():
    # Must not probe anything that depends on a room/game existing (e.g.
    # /factions after a room was created, or a WS action) — "no rooms yet"
    # must never read as unhealthy.
    mcp = _compose()["services"]["redline-mcp"]
    test_cmd = " ".join(mcp["healthcheck"]["test"])
    assert "/health" in test_cmd
    assert "8080" in test_cmd


def test_mcp_dockerfile_does_not_copy_server_or_data_or_static():
    text = MCP_DOCKERFILE_PATH.read_text(encoding="utf-8")
    for forbidden in ("COPY server", "COPY data", "COPY static"):
        assert forbidden not in text, f"mcp_server/Dockerfile should not need {forbidden!r}"
    assert "COPY mcp_server/" in text
    assert "COPY rules.md" in text


def test_mcp_dockerfile_binds_all_interfaces_inside_container():
    text = MCP_DOCKERFILE_PATH.read_text(encoding="utf-8")
    assert "REDLINE_MCP_HTTP_HOST=0.0.0.0" in text
    assert "streamable-http" in text


def test_server_code_never_imports_the_mcp_package():
    # The root Dockerfile's `uv sync --frozen --no-dev` now also installs
    # `mcp` into the game image (it's a top-level [project.dependencies]
    # entry, added for mcp_server/) — that's harmless ONLY as long as
    # server/*.py genuinely never imports it. Documented as a known,
    # accepted (small) overhead in docs/mcp_server.md.
    import_re = re.compile(r"^\s*(import mcp\b|from mcp\b|from mcp\.)", re.MULTILINE)
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "server").glob("*.py")
        if import_re.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"server/*.py must not import the mcp package: {offenders}"


def test_root_dockerfile_is_untouched_by_the_mcp_work():
    # The existing game image must keep working unmodified; the MCP work
    # adds a *separate* Dockerfile rather than touching this one.
    text = ROOT_DOCKERFILE_PATH.read_text(encoding="utf-8")
    assert "mcp_server" not in text
    assert 'CMD ["uv", "run", "--no-dev", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]' in text
