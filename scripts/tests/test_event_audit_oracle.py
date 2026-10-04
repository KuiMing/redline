"""The event audit must judge the runtime against a fixed oracle, never against itself.

Each mutation corrupts the runtime-loaded event definitions; the audit (and the oracle comparison)
has to fail. A clean run must stay green.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / 'scripts' / 'validate'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

import event_card_oracle as oracle
import validate_event_outcome_timing_audit as audit


def run_with(mutator):
    audit.RUNTIME_EVENT_MUTATOR = mutator
    try:
        checks, _ = audit.run_all_checks()
    finally:
        audit.RUNTIME_EVENT_MUTATOR = None
    return checks


def failed(checks):
    return [c for c in checks if not c['passed']]


def edit(names, path, value):
    def mutate(events):
        for event in events:
            if event.get('name') in names:
                target = event
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
    return mutate


def test_oracle_covers_all_14_mission_cards_and_main_equals_copy():
    assert len(oracle.MISSION_ORACLE) == 14
    assert len({c['id'] for c in oracle.MISSION_ORACLE}) == 14
    assert all(c['personal'] and c['timing'] == 'full_round_end' for c in oracle.MISSION_ORACLE)
    mains = {c['name']: c for c in oracle.MISSION_ORACLE}
    for name, card in mains.items():
        if name.endswith('（副本）'):
            main = mains[name[:-len('（副本）')]]
            for key in ('trigger', 'success', 'failure'):
                assert card[key] == main[key], name


def test_clean_runtime_matches_oracle_and_audit_is_green():
    import json
    events = json.loads((ROOT / 'data' / 'events_structured.v1.1.json').read_text(encoding='utf-8'))['events']
    assert oracle.definition_mismatches(events) == []
    assert failed(run_with(None)) == []


def test_major_disaster_success_count_1_to_2_fails_audit():
    checks = run_with(edit({'重大災難'}, ('success', 'count'), 2))
    names = [c['name'] for c in failed(checks)]
    assert any(n.startswith('runtime mission definitions') for n in names)
    assert any(n.startswith('重大災難 ') for n in names)           # behavioural delta also catches it
    assert not any(n.startswith('重大災難（副本）') for n in names)


def test_main_and_copy_both_wrong_still_fails_audit():
    checks = run_with(edit({'重大災難', '重大災難（副本）'}, ('success', 'count'), 2))
    names = [c['name'] for c in failed(checks)]
    assert any(n.startswith('runtime mission definitions') for n in names)
    assert any(n.startswith('重大災難 ') for n in names)
    assert any(n.startswith('重大災難（副本）') for n in names)


@pytest.mark.parametrize('label, names, path, value', [
    ('scope', {'藏印邊境軍事對峙'}, ('trigger', 'scope'), '牆外'),
    ('failure scope', {'全國人大召開（副本）'}, ('failure', 'scope'), '牆外'),
    ('card name', {'重大災難'}, ('success', 'card'), '樂捐者'),
    ('trigger count', {'香港抗暴之戰'}, ('trigger', 'count'), 2),
    ('trigger min_cost', {'貿易戰加劇（副本）'}, ('trigger', 'min_cost'), 3),
    ('trigger type', {'北京政爭'}, ('trigger', 'type'), 'buy_card'),
    ('personal flag', {'東突厥集中營'}, ('trigger', 'each_non_red_player'), False),
    ('max_steps distance', {'烏魯木齊七五事件'}, ('success', 'max_steps'), 2),
    ('failure type', {'紅軍權貴出逃（副本）'}, ('failure', 'type'), 'discard_random'),
])
def test_wrong_parameter_fails_audit(label, names, path, value):
    checks = run_with(edit(names, path, value))
    bad = failed(checks)
    assert any(c['name'].startswith('runtime mission definitions') for c in bad), label
    assert any(any(c['name'].startswith(n) for n in names) for c in bad), label


def test_renamed_card_fails_audit():
    checks = run_with(edit({'重大災難'}, ('name',), '重大災難X'))
    assert failed(checks)
    assert any(c['name'].startswith('runtime mission definitions') for c in failed(checks))


def test_extra_runtime_card_or_missing_card_fails():
    def drop(events):
        events[:] = [e for e in events if e.get('name') != '北京政爭']
    assert failed(run_with(drop))


def _mission(events, name):
    return next(e for e in events if e.get('name') == name)


def _duplicate_exact(events):
    events.append(copy.deepcopy(_mission(events, '重大災難')))


def _same_name_different_id(events):
    clone = copy.deepcopy(_mission(events, '重大災難'))
    clone['id'] = 'major_disaster_clone'
    events.append(clone)


def _same_id_different_name(events):
    clone = copy.deepcopy(_mission(events, '重大災難'))
    clone['name'] = '重大災難（另一張）'
    events.append(clone)


def _unknown_extra_card(events):
    clone = copy.deepcopy(_mission(events, '重大災難'))
    clone['id'] = 'unknown_extra'
    clone['name'] = '未知任務'
    events.append(clone)


def _main_copy_id_collision(events):
    _mission(events, '重大災難（副本）')['id'] = _mission(events, '重大災難')['id']


def _main_copy_name_collision(events):
    _mission(events, '重大災難（副本）')['name'] = '重大災難'


@pytest.mark.parametrize('mutator', [
    _duplicate_exact, _same_name_different_id, _same_id_different_name,
    _unknown_extra_card, _main_copy_id_collision, _main_copy_name_collision,
], ids=lambda m: m.__name__.strip('_'))
def test_duplicate_or_extra_mission_entries_fail_audit(mutator):
    events = json.loads((ROOT / 'data' / 'events_structured.v1.1.json').read_text(encoding='utf-8'))['events']
    mutator(events)
    assert oracle.definition_mismatches(events)
    bad = failed(run_with(mutator))
    assert any(c['name'].startswith('runtime mission definitions') for c in bad)


def test_exact_duplicate_reports_cardinality_and_duplicate_identity():
    events = json.loads((ROOT / 'data' / 'events_structured.v1.1.json').read_text(encoding='utf-8'))['events']
    _duplicate_exact(events)
    problems = oracle.definition_mismatches(events)
    assert any('mission count runtime=15 oracle=14' in p for p in problems)
    assert any('duplicated 2x' in p for p in problems)
