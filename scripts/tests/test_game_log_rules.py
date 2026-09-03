"""Unit tests for server/game_log_rules.py — the pure action-log privacy
projection extracted from game.py (item 13, extract-game-log). The
mutators (Game.log / log_private_draw / log_private_shared_draw) stay in
game.py; this is only the read-side projection.
"""

from server.game_log_rules import project_action_log


def test_project_action_log_returns_full_log_for_none_viewer():
    log = ['[Turn 1] a', '[Turn 1] b']
    visibility = [None, None]
    assert project_action_log(log, visibility) == log


def test_project_action_log_uses_public_message_when_no_private_override():
    log = ['[Turn 1] diagnostic']
    visibility = [{'private_messages': {}, 'public_message': '[Turn 1] public'}]
    assert project_action_log(log, visibility, viewer_player_id='p1') == ['[Turn 1] public']


def test_project_action_log_uses_private_message_for_the_matching_viewer():
    log = ['[Turn 1] diagnostic']
    visibility = [{
        'private_messages': {'p1': '[Turn 1] private for p1'},
        'public_message': '[Turn 1] public',
    }]
    assert project_action_log(log, visibility, viewer_player_id='p1') == ['[Turn 1] private for p1']
    assert project_action_log(log, visibility, viewer_player_id='p2') == ['[Turn 1] public']


def test_project_action_log_falls_back_to_raw_entry_when_no_rule():
    log = ['[Turn 1] plain entry']
    visibility = [None]
    assert project_action_log(log, visibility, viewer_player_id='p1') == ['[Turn 1] plain entry']


def test_project_action_log_handles_a_shorter_visibility_list():
    # log_private_shared_draw-style helpers can append to action_log and
    # _action_log_visibility together, but defensive padding matters if
    # they ever drift — pad from the front with None (oldest entries have
    # no recorded rule) rather than raising.
    log = ['[Turn 1] old', '[Turn 1] new']
    visibility = [{'private_messages': {}, 'public_message': '[Turn 1] public new'}]
    result = project_action_log(log, visibility, viewer_player_id='p1')
    assert result == ['[Turn 1] old', '[Turn 1] public new']
