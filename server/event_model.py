from enum import Enum


class EventType(str, Enum):
    IDLE = "idle"          # 歲月靜好
    AUTO = "auto"          # 自動執行
    MISSION = "mission"    # 任務型


class EventBase:
    def __init__(self, event_id, name, description, raw_data=None):
        self.id = event_id
        self.name = name
        self.description = description
        self.raw_data = raw_data or {}


class IdleEvent(EventBase):
    def __init__(self, event_id, name, description, raw_data=None):
        super().__init__(event_id, name, description, raw_data)
        self.type = EventType.IDLE


class AutoEvent(EventBase):
    def __init__(self, event_id, name, description, effect, raw_data=None):
        super().__init__(event_id, name, description, raw_data)
        self.type = EventType.AUTO
        self.effect = effect  # structured effect placeholder


class MissionEvent(EventBase):
    def __init__(self, event_id, name, description,
                 trigger_condition,
                 success_effect,
                 failure_effect,
                 raw_data=None):
        super().__init__(event_id, name, description, raw_data)
        self.type = EventType.MISSION
        self.trigger_condition = trigger_condition
        self.success_effect = success_effect
        self.failure_effect = failure_effect


# ---------- Parser Stub ----------


def parse_raw_event(raw_event):
    """
    Convert raw CSV-derived event row into structured Event object.
    Currently minimal — no NLP parsing.
    """
    name = raw_event.get("事件卡名稱") or raw_event.get("name")
    description = raw_event.get("事件簡述") or raw_event.get("description")

    if not name:
        return None

    if "歲月靜好" in name:
        return IdleEvent(name, name, description, raw_event)

    if "自動執行" in str(raw_event):
        return AutoEvent(name, name, description, effect=None, raw_data=raw_event)

    # default mission type
    return MissionEvent(
        event_id=name,
        name=name,
        description=description,
        trigger_condition=None,
        success_effect=None,
        failure_effect=None,
        raw_data=raw_event
    )
