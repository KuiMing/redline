"""Pure action-log privacy projection (reads already-recorded log entries,
no mutation).

`Game.log` / `Game.log_private_draw` / `Game.log_private_shared_draw`
(which append to `self.action_log` / `self._action_log_visibility`) stay
in `game.py` — those are the mutators; this is only the read-side
projection consumed by `state()`.
"""


def project_action_log(action_log, action_log_visibility, viewer_player_id=None):
    if viewer_player_id is None:
        return list(action_log)
    visibility = list(action_log_visibility or [])
    if len(visibility) < len(action_log):
        visibility = [None] * (len(action_log) - len(visibility)) + visibility
    elif len(visibility) > len(action_log):
        visibility = visibility[-len(action_log):]
    viewer_key = str(viewer_player_id)
    return [
        ((rule.get('private_messages') or {}).get(viewer_key) or rule.get('public_message') or entry)
        if isinstance(rule, dict)
        else entry
        for entry, rule in zip(action_log, visibility)
    ]
