"""Static rulebook / card / faction reference data for MCP resources & tools.

Everything here is either read straight off a repo file (rules.md) or comes
back from the real public HTTP endpoints (/factions, /card-presentation) via
RedlineClient — never from server/*.py directly, and never from a live
game's private state. It is fetched once per process and memoized, since it
does not change while a REDLINE server process is running.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_MD_PATH = REPO_ROOT / "rules.md"

# The four red army abilities plus the five generic "activated" abilities
# other factions can have (see server/game.py's _activated_faction_action
# dispatch table — it recognizes exactly these nine name strings and nothing
# else). A faction's resolved ability list can contain other entries (setup
# effects, passive/automatic triggers such as 安全屋); those are never
# player-invoked via the `faction_action` WS message, so they are excluded
# here even if their `type` happens to be "activated".
DISPATCHABLE_FACTION_ACTION_NAMES = frozenset(
    {
        "統戰部",
        "政工部",
        "國安部",
        "中紀委",
        "民主陣線",
        "紅軍派系",
        "立場試探",
        "賭徒耳語",
        "民族祭儀",
    }
)

# Action cards whose "action" mode is target_player_id-related
# (server-enforced in server/game_card_play.py::play_card, ~line 2404-2432).
# Kept as explicit lists rather than derived, because the requirement is
# per-card-name business logic, not a field present in the card catalog.
#
# REQUIRED: server returns an error if target_player_id is None or self
# ("合作談判必須指定任意一名其他玩家" / "武裝卡必須指定其他玩家").
REQUIRED_TARGET_ACTION_CARD_NAMES = frozenset({"合作談判", "武裝者", "武裝小隊", "武裝集團"})
# OPTIONAL: target_player_id narrows an otherwise auto-selected target pool
# (走漏風聲 only validates it "if target_player_id is not None"; 派遣間諜/
# 內應間諜 fall back to `_target_players_for_interaction` when omitted) —
# still useful to expose as a candidate list, but never mandatory.
OPTIONAL_TARGET_ACTION_CARD_NAMES = frozenset({"走漏風聲", "派遣間諜", "內應間諜"})
TARGETED_ACTION_CARD_NAMES = REQUIRED_TARGET_ACTION_CARD_NAMES | OPTIONAL_TARGET_ACTION_CARD_NAMES

HIDDEN_HAND_CARD_LABEL = "未知手牌"

# rules.md「放入分神或內鬥」: these two static-purchase-area cards are only
# ever placed into a *target* player's deck via an ability or another card's
# effect (see server/game.py's DISRUPTION_ONLY_CARD_NAMES) — never something
# a player buys for themselves. server/game.py::buy_cards() rejects a direct
# purchase attempt with this exact error string; excluded here too so
# get_legal_actions() never offers it as a buy_card option in the first
# place (2026-09-13: a live Red Army Agent run bought both before this fix).
DISRUPTION_ONLY_CARD_NAMES = frozenset({"分神", "內鬥"})


def read_rules_markdown() -> str:
    return RULES_MD_PATH.read_text(encoding="utf-8")


def _faction_option_by_id(faction_catalog: dict, faction_id: str) -> dict | None:
    for category in faction_catalog.get("categories") or []:
        for option in category.get("options") or []:
            if option.get("id") == faction_id:
                return option
            for variant in (option.get("variant_details") or {}).values():
                if isinstance(variant, dict) and variant.get("id") == faction_id:
                    return variant
    return None


def resolve_faction_detail(faction_catalog: dict, faction_id: str, base_name: str | None) -> dict | None:
    """Mirrors static/app.js's renderMyFactionView detail resolution: family
    factions (tibet/uyghur) publish shared data on the parent option plus a
    per-base override in `variant_details`; everyone else's own option is
    already the full detail.
    """
    option = _faction_option_by_id(faction_catalog, faction_id)
    if option is None:
        return None
    variant_details = option.get("variant_details") or {}
    if base_name and base_name in variant_details:
        return variant_details[base_name]
    return option


def faction_win_condition_texts(faction_catalog: dict, faction_id: str, base_name: str | None) -> list[str]:
    detail = resolve_faction_detail(faction_catalog, faction_id, base_name)
    if not detail:
        return []
    if detail.get("win_condition_text"):
        return [detail["win_condition_text"]]
    texts = []
    for condition in detail.get("win_conditions") or []:
        if isinstance(condition, str):
            texts.append(condition)
        elif isinstance(condition, dict):
            texts.append(condition.get("text") or _describe_win_condition(condition))
    return texts


def _describe_win_condition(condition: dict) -> str:
    kind = condition.get("type")
    if kind == "count_only":
        return f"回合結束時在{condition.get('scope', '指定區域')}擁有至少 {condition.get('count')} 個有效組織。"
    if kind == "count_and_required":
        required = "、".join(condition.get("required_locations") or [])
        return f"回合結束時在{condition.get('scope', '指定區域')}擁有至少 {condition.get('count')} 個有效組織，且必須包含 {required}。"
    return str(condition)


def faction_dispatchable_action_names(faction_catalog: dict, faction_id: str, base_name: str | None) -> list[str]:
    """Candidate `faction_action` names this player's faction can legally
    attempt right now (subject to the caller's own turn/usage-count gating —
    see summarize.legal_actions). Best-effort: the server remains
    authoritative and may still reject a specific attempt (e.g. no valid
    target for 國安部 this turn).
    """
    detail = resolve_faction_detail(faction_catalog, faction_id, base_name)
    if not detail:
        return []
    names = []
    for ability in detail.get("abilities") or []:
        if not isinstance(ability, dict):
            continue
        name = ability.get("name")
        if name in DISPATCHABLE_FACTION_ACTION_NAMES and ability.get("type") in (None, "activated"):
            names.append(name)
    return names


class RulesCatalog:
    """Per-process memoized cache in front of RedlineClient's static-data calls."""

    def __init__(self, client):
        self._client = client
        self._faction_catalog: dict | None = None
        self._card_catalog: dict | None = None

    async def factions(self) -> dict:
        if self._faction_catalog is None:
            self._faction_catalog = await self._client.list_factions()
        return self._faction_catalog

    async def cards(self) -> dict:
        if self._card_catalog is None:
            self._card_catalog = await self._client.card_presentation()
        return self._card_catalog
