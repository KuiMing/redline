"""Multi-viewer differential replay harness for high-risk game.py refactors.

Function-level characterization tests can't catch interaction bugs across a
multi-step pending_choice / reaction / turn-handoff sequence. This harness
drives a deterministic multi-turn scenario and, at each checkpoint, captures
`Game.state(viewer_id)` for every player (plus the unauthenticated/public
view) so a refactor can be checked for byte-identical behavior across the
whole sequence, not just one function's return value.

Only one source of non-determinism exists in Game beyond `random`-seeded
shuffling: `Game.id` is a fresh `uuid.uuid4()` per instance (state()['id']).
Player ids are NOT random here — `_assign_factions` overwrites them with
whatever id was passed into `Game(players_data)`, so a scenario that passes
fixed ids ('p1', 'p2', ...) gets fully deterministic player ids for free.
"""

import json


def normalize_state(state):
    """Strip the one known non-deterministic field (the game's own uuid4 id)."""
    state = dict(state)
    state.pop('id', None)
    return state


def capture_step(game, label, extra=None):
    """Snapshot every player's view plus the unauthenticated view, normalized."""
    states = {p.id: normalize_state(game.state(p.id)) for p in game.players}
    states['__public__'] = normalize_state(game.state(None))
    return {
        'label': label,
        'extra': extra or {},
        'states': states,
    }


def run_scenario(scenario_fn, seed):
    """Run `scenario_fn(capture)` under a fixed random seed; return the capture list."""
    import random
    random.seed(seed)
    steps = []

    def capture(game, label, extra=None):
        steps.append(capture_step(game, label, extra))

    scenario_fn(capture)
    return steps


def diff_steps(baseline, current):
    """Return a short human-readable description of the first divergence, or None."""
    if len(baseline) != len(current):
        return f'step count differs: baseline={len(baseline)} current={len(current)}'
    for i, (b, c) in enumerate(zip(baseline, current)):
        if b['label'] != c['label']:
            return f'step {i}: label differs: baseline={b["label"]!r} current={c["label"]!r}'
        b_json = json.dumps(b, sort_keys=True, ensure_ascii=False)
        c_json = json.dumps(c, sort_keys=True, ensure_ascii=False)
        if b_json != c_json:
            return _first_key_diff(i, b, c)
    return None


def _first_key_diff(step_index, b, c):
    for viewer_id in sorted(set(b['states']) | set(c['states'])):
        b_state = b['states'].get(viewer_id, '<missing>')
        c_state = c['states'].get(viewer_id, '<missing>')
        if json.dumps(b_state, sort_keys=True, ensure_ascii=False) != json.dumps(c_state, sort_keys=True, ensure_ascii=False):
            for key in sorted(set(b_state) | set(c_state)) if isinstance(b_state, dict) and isinstance(c_state, dict) else []:
                bv = b_state.get(key, '<missing>') if isinstance(b_state, dict) else '<n/a>'
                cv = c_state.get(key, '<missing>') if isinstance(c_state, dict) else '<n/a>'
                if json.dumps(bv, sort_keys=True, ensure_ascii=False) != json.dumps(cv, sort_keys=True, ensure_ascii=False):
                    return (
                        f'step {step_index} ({b["label"]}): viewer {viewer_id!r} key {key!r} differs: '
                        f'baseline={bv!r} current={cv!r}'
                    )
            return f'step {step_index} ({b["label"]}): viewer {viewer_id!r} differs (non-dict or top-level)'
    return f'step {step_index} ({b["label"]}): differs but no single viewer isolated it'
