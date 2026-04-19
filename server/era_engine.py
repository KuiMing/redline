from dataclasses import dataclass


@dataclass
class ActiveEra:
    era_id: str
    owner: str  # faction or player name
    remaining_turns: int  # -1 means permanent
    effect: dict


class EraEngine:
    def __init__(self, era_definitions):
        # era_definitions: list of structured era JSON entries
        self.era_defs = {e["id"]: e for e in era_definitions}
        self.active_eras = []

    def activate_era(self, era_id, owner=None):
        era = self.era_defs.get(era_id)
        if not era:
            return False

        duration = era.get("red_effect", {}).get("duration") or \
                   era.get("rebel_effect", {}).get("duration") or 0

        active = ActiveEra(
            era_id=era_id,
            owner=owner,
            remaining_turns=duration,
            effect=era
        )
        self.active_eras.append(active)
        return True

    def tick(self):
        """
        Advance one turn for all active eras.
        Decrease duration and remove expired ones.
        """
        remaining = []
        for era in self.active_eras:
            if era.remaining_turns == -1:
                remaining.append(era)
                continue

            era.remaining_turns -= 1
            if era.remaining_turns > 0:
                remaining.append(era)

        self.active_eras = remaining

    def get_active_eras(self):
        return [e.era_id for e in self.active_eras]
