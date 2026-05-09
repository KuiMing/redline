class EraEngine:
    def __init__(self, era_definitions):
        # era_definitions: list of structured era JSON entries
        self.era_defs = {e["id"]: e for e in era_definitions}
        self.active = {}

    def activate_era(self, era_id):
        era = self.era_defs.get(era_id)
        if not era:
            return False

        duration = era.get("duration", {})

        if duration.get("type") == "turns":
            remaining = duration.get("value", 0)
        elif duration.get("type") == "permanent":
            remaining = None
        else:
            remaining = None

        self.active[era_id] = {
            "remaining": remaining,
            "definition": era
        }

        return True

    def tick(self):
        expired = []

        for era_id, data in list(self.active.items()):
            if data["remaining"] is None:
                continue

            data["remaining"] -= 1

            if data["remaining"] <= 0:
                expired.append(era_id)

        for era_id in expired:
            del self.active[era_id]

        return expired

    def get_active_eras(self):
        return list(self.active.keys())

    def get_active_era_details(self):
        details = []
        for era_id, data in self.active.items():
            era = data.get("definition") or self.era_defs.get(era_id) or {}
            duration = era.get("duration", {})
            details.append({
                "id": era_id,
                "name": era.get("name", era_id),
                "trigger": era.get("trigger"),
                "duration": duration,
                "remaining": data.get("remaining"),
                "effects": era.get("effects", {}),
            })
        return details

    def is_active(self, era_id):
        return era_id in self.active

    def get_definition(self, era_id):
        return self.era_defs.get(era_id)
