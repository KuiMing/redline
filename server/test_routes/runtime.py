"""Late-bound shared stores used by test-only game setup routes."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GameSetupRuntime:
    manager: Any
    lobby: dict
    lobby_hosts: dict
    lobby_factions: dict
    lobby_bases: dict
    lobby_ready: dict = field(default_factory=dict)
