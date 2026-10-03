"""Stage 2 — CandidateGenerator.

A deliberately thin wrapper: this calls `mcp_server.summarize.legal_actions()`
in-process and returns exactly what it returns. Per requirement #3 and plan
section 2, the policy never re-derives a candidate list independently — the
server (via this one already-existing function) remains the sole authority
on what is legal right now.

Known caveat this module does NOT try to work around (by design — fixing it
belongs upstream in summarize.py, not here): `legal_actions()` has at least
one documented false-positive-legality case (`use_topdeck_right` offered
when `pending_topdeck_uses` was being computed from the wrong field — see
mcp_server/summarize.py's comment at the `use_topdeck_right` append site).
ActionSubmitter (submitter.py) is what actually tolerates a legal-looking
candidate the server still rejects, by treating any submission failure as a
signal to re-derive fresh candidates rather than retry the same payload.
"""

from __future__ import annotations

from typing import Any

from mcp_server import summarize

from red_army_policy.catalogs import default_card_catalog, default_faction_catalog


def generate_candidates(
    state: dict,
    player_id: str,
    *,
    faction_catalog: dict[str, Any] | None = None,
    card_catalog: dict[str, Any] | None = None,
) -> dict:
    """Return summarize.legal_actions()'s result unchanged.

    `faction_catalog`/`card_catalog` default to the in-process catalogs
    (catalogs.py) but are accepted as parameters so tests can pass small
    fake catalogs instead of loading the real data files.
    """
    faction_catalog = faction_catalog if faction_catalog is not None else default_faction_catalog()
    card_catalog = card_catalog if card_catalog is not None else default_card_catalog()
    return summarize.legal_actions(state, player_id, faction_catalog, card_catalog)
