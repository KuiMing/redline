"""Stage 1 — StateAssessor.

Reshapes an already-authoritative `Game.state(viewer_player_id=red_army_id)`
payload into the small set of numbers ScoringEngine actually needs. Reads
only fields `state()` already computed (including the `condition_progress`/
`taiwan_organization_count` projection added alongside this module — see
server/game.py's `_project_players`); never recomputes victory proximity,
map adjacency, or legality itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OpponentAssessment:
    player_id: str
    name: str
    faction: str | None
    condition_progress: float
    organization_total: int
    taiwan_organization_count: int


@dataclass(frozen=True)
class Assessment:
    turn: int | None
    game_phase: str | None
    turn_phase: str | None
    current_player_name: str | None
    my_player_id: str
    my_name: str | None
    is_my_turn: bool
    my_resources: dict
    my_hand_size: int
    purchased_cards_this_turn_count: int
    my_organization_total: int
    my_taiwan_organization_count: int
    opponents: list[OpponentAssessment] = field(default_factory=list)

    @property
    def max_opponent_progress(self) -> float:
        if not self.opponents:
            return 0.0
        return max(o.condition_progress for o in self.opponents)

    @property
    def leading_opponent(self) -> OpponentAssessment | None:
        if not self.opponents:
            return None
        return max(self.opponents, key=lambda o: o.condition_progress)

    def opponent_by_id(self, player_id: str | None) -> OpponentAssessment | None:
        for opponent in self.opponents:
            if opponent.player_id == player_id:
                return opponent
        return None


def _find_player(state: dict, player_id: str) -> dict | None:
    for player in state.get("players") or []:
        if player.get("id") == player_id:
            return player
    return None


def assess(state: dict, player_id: str) -> Assessment:
    me = _find_player(state, player_id)
    opponents = [
        OpponentAssessment(
            player_id=p.get("id"),
            name=p.get("name"),
            faction=p.get("faction"),
            condition_progress=float(p.get("condition_progress") or 0.0),
            organization_total=int((p.get("organization_counts") or {}).get("total") or 0),
            taiwan_organization_count=int(p.get("taiwan_organization_count") or 0),
        )
        for p in state.get("players") or []
        if p.get("id") != player_id
    ]
    current_player_name = state.get("current_player")
    is_my_turn = bool(me and me.get("name") == current_player_name)
    return Assessment(
        turn=state.get("turn"),
        game_phase=state.get("game_phase"),
        turn_phase=state.get("turn_phase"),
        current_player_name=current_player_name,
        my_player_id=player_id,
        my_name=me.get("name") if me else None,
        is_my_turn=is_my_turn,
        my_resources=dict(me.get("resources") or {}) if me else {},
        my_hand_size=len(me.get("hand") or []) if me else 0,
        purchased_cards_this_turn_count=int(state.get("purchased_cards_this_turn_count") or 0),
        my_organization_total=int((me.get("organization_counts") or {}).get("total") or 0) if me else 0,
        my_taiwan_organization_count=int(me.get("taiwan_organization_count") or 0) if me else 0,
        opponents=opponents,
    )
