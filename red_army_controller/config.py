from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def default_state_path() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "redline" / "red-army-controller.json"


@dataclass(frozen=True)
class ControllerConfig:
    mcp_url: str = "http://127.0.0.1:8765/mcp"
    state_file: Path = default_state_path()
    player_name: str = "紅軍 Agent"
    hermes_profile: str = "redarmy"
    hermes_binary: str = "hermes"
    mcp_server_name: str = "redline"
    poll_seconds: float = 2.0
    agent_timeout_seconds: float = 300.0
    max_agent_invocations_per_state: int = 3
    max_agent_invocations_per_action_window: int = 8
    max_consecutive_agent_failures: int = 3
    failure_backoff_seconds: float = 10.0
    post_agent_settle_seconds: float = 0.5

    @classmethod
    def from_env(cls) -> "ControllerConfig":
        return cls(
            mcp_url=os.environ.get("REDLINE_MCP_URL", cls.mcp_url),
            state_file=Path(os.environ.get("REDLINE_RED_ARMY_STATE_FILE", default_state_path())).expanduser(),
            player_name=os.environ.get("REDLINE_RED_ARMY_NAME", cls.player_name),
            hermes_profile=os.environ.get("REDLINE_HERMES_PROFILE", cls.hermes_profile),
            hermes_binary=os.environ.get("REDLINE_HERMES_BINARY", cls.hermes_binary),
            mcp_server_name=os.environ.get("REDLINE_HERMES_MCP_SERVER", cls.mcp_server_name),
            poll_seconds=max(0.2, _float_env("REDLINE_CONTROLLER_POLL_SECONDS", cls.poll_seconds)),
            agent_timeout_seconds=max(10.0, _float_env("REDLINE_AGENT_TIMEOUT_SECONDS", cls.agent_timeout_seconds)),
            max_agent_invocations_per_state=max(1, _int_env("REDLINE_MAX_AGENT_INVOCATIONS_PER_STATE", cls.max_agent_invocations_per_state)),
            max_agent_invocations_per_action_window=max(1, _int_env("REDLINE_MAX_AGENT_INVOCATIONS_PER_ACTION_WINDOW", cls.max_agent_invocations_per_action_window)),
            max_consecutive_agent_failures=max(1, _int_env("REDLINE_MAX_CONSECUTIVE_AGENT_FAILURES", cls.max_consecutive_agent_failures)),
            failure_backoff_seconds=max(1.0, _float_env("REDLINE_AGENT_FAILURE_BACKOFF_SECONDS", cls.failure_backoff_seconds)),
            post_agent_settle_seconds=max(0.0, _float_env("REDLINE_POST_AGENT_SETTLE_SECONDS", cls.post_agent_settle_seconds)),
        )
