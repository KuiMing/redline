"""In-process faction/card catalogs for CandidateGenerator.

`mcp_server.summarize.legal_actions()` needs a `faction_catalog` (ability
names per faction) and a `card_catalog` (per-card presentation text, used
only to pick between a card's "resource" and "action" play `mode`). The
MCP tool layer fetches both over HTTP from the running REDLINE server
(`mcp_server/rules_data.py`'s `RulesCatalog`, backed by
`mcp_server/redline_client.py`). This module intentionally does NOT do
that — requirement #1 is that the production decision path never depends
on an external API/process. `server.faction_presentation.build_faction_presentation()`
and `server.card_presentation.CARD_PRESENTATION_CATALOG` are the exact same
pure, in-process functions the HTTP endpoints (`/factions`,
`/card-presentation` in server/main.py) call internally — reading them
directly here is calling the same code one layer earlier, not
re-implementing or duplicating it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def default_faction_catalog() -> dict[str, Any]:
    from server.faction_presentation import build_faction_presentation

    return build_faction_presentation()


@lru_cache(maxsize=1)
def default_card_catalog() -> dict[str, Any]:
    from server.card_presentation import CARD_PRESENTATION_CATALOG

    return CARD_PRESENTATION_CATALOG
