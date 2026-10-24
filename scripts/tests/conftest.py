import os

# server/main.py gates /test/* HTTP routes behind ENABLE_TEST_ROUTES (off by
# default so production doesn't expose live-state-mutating endpoints). The
# suite here exercises those routes directly, so opt in before any test
# module imports server.main. setdefault() leaves an explicit env value
# (e.g. a developer forcing it off) untouched.
os.environ.setdefault("ENABLE_TEST_ROUTES", "true")


def host_token(game_id, player_id):
    """resume_token of a seat created through /create or /join (lobby mutations are token-gated)."""
    from server import main

    return main.lobby_player_credentials[game_id][player_id]["resume_token"]
