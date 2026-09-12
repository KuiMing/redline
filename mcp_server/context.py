"""Shared per-process context handed to every tool implementation."""

from __future__ import annotations

from dataclasses import dataclass

from mcp_server.redline_client import RedlineClient
from mcp_server.rules_data import RulesCatalog


@dataclass
class AppContext:
    client: RedlineClient
    rules: RulesCatalog
