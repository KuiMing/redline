import os

# server/main.py gates /test/* HTTP routes behind ENABLE_TEST_ROUTES (off by
# default so production doesn't expose live-state-mutating endpoints). The
# suite here exercises those routes directly, so opt in before any test
# module imports server.main. setdefault() leaves an explicit env value
# (e.g. a developer forcing it off) untouched.
os.environ.setdefault("ENABLE_TEST_ROUTES", "true")
