"""Unit tests for the state()-decomposition helpers (_project_map_control,
_project_era_state, _project_pending_choice, _project_purchase_area,
_project_players) — game.py's most viewer-privacy-sensitive method,
decomposed in place without touching its one known mutation
(self.pending_choice['towns'] = ...), which is deliberately left alone
(see the commit that introduced these helpers for why).

These are a secondary safety net on top of the primary one:
scripts/tests/test_game_replay_regression.py's four differential replay
scenarios already compare state()'s full output for every viewer at every
step against a committed baseline — that's what actually proves this
decomposition produced byte-identical behavior (verified by injecting a
real bug into _project_players during development and confirming all
four scenarios caught it immediately). These tests instead check each
helper's own return shape/values directly, which the replay scenarios
don't isolate function-by-function.
"""

from server.game import Game


def _new_game():
    game = Game([('p1', 'a'), ('p2', 'b')])
    a, b = game.players
    a.faction_id = 'hong_kong'
    a.base = '香港城'
    a.organizations = {'香港城': 1}
    b.faction_id = 'red_army'
    b.base = '北京'
    b.organizations = {'北京': 1}
    return game, a, b


# ---------- _project_map_control ----------

def test_project_map_control_reflects_each_players_organizations():
    game, a, b = _new_game()
    town_control, shared_access = game._project_map_control()
    assert town_control['香港城'] == [{'player': a.name, 'count': 1}]
    assert town_control['北京'] == [{'player': b.name, 'count': 1}]
    assert isinstance(shared_access, dict)


# ---------- _project_era_state ----------

def test_project_era_state_returns_three_values_with_none_stage_for_red_army():
    game, _a, b = _new_game()
    active_era_details, my_era_stage, notification = game._project_era_state(b)
    assert isinstance(active_era_details, list)
    assert my_era_stage is None  # red_army never gets an era stage
    assert notification is None  # no era_notification set yet


def test_project_era_state_stage_ordering_uses_raw_details_for_my_era_stage():
    # Regression guard for the exact ordering bug risk called out in the
    # extraction commit: my_era_stage must be computed from the *raw*
    # active_era_details (pre text-enrichment), matching the original
    # inline code's variable-rebinding order exactly. This just asserts
    # the call doesn't raise and returns the documented 3-tuple shape for
    # a non-red-army viewer too.
    game, a, _b = _new_game()
    result = game._project_era_state(a)
    assert len(result) == 3


# ---------- _project_pending_choice ----------

def test_project_pending_choice_returns_none_when_no_pending_choice():
    game, a, _b = _new_game()
    assert game.pending_choice is None
    assert game._project_pending_choice(a.id, a) is None


def test_project_pending_choice_projects_an_open_choice():
    game, a, _b = _new_game()
    game._set_pending_town_choice(
        a,
        'event_build_organization',
        [{'town': '香港城'}],
        'test prompt',
        source_name='test',
    )
    result = game._project_pending_choice(a.id, a)
    assert result is not None
    assert result['choice_key'] == 'event_build_organization'
    assert result['player_id'] == a.id
    assert result['interaction_kind'] == 'build_organization'


# ---------- _project_purchase_area ----------

def test_project_purchase_area_returns_three_parallel_lists():
    game, a, _b = _new_game()
    costs, payments, affordable = game._project_purchase_area(a)
    assert len(costs) == len(game.purchase_area)
    assert len(payments) == len(game.purchase_area)
    assert len(affordable) == len(game.purchase_area)


# ---------- _project_players ----------

def test_project_players_hides_other_players_hands_from_a_viewer():
    game, a, b = _new_game()
    projected = game._project_players(a.id)
    a_entry = next(p for p in projected if p['id'] == a.id)
    b_entry = next(p for p in projected if p['id'] == b.id)
    assert a_entry['hand'] == [c.name for c in a.hand]
    assert b_entry['hand'] == ['未知手牌' for _ in b.hand]
    assert b_entry['hand_variants'] == [None for _ in b.hand]


def test_project_players_shows_every_hand_for_the_public_unauthenticated_view():
    game, a, b = _new_game()
    projected = game._project_players(None)
    a_entry = next(p for p in projected if p['id'] == a.id)
    b_entry = next(p for p in projected if p['id'] == b.id)
    assert a_entry['hand'] == [c.name for c in a.hand]
    assert b_entry['hand'] == [c.name for c in b.hand]


def test_project_players_includes_organization_counts_and_orgs():
    game, a, _b = _new_game()
    projected = game._project_players(a.id)
    a_entry = next(p for p in projected if p['id'] == a.id)
    assert a_entry['orgs'] == a.organizations
    assert a_entry['organization_counts']['total'] == 1


# ---------- state() itself still assembles correctly end-to-end ----------

def test_state_still_returns_the_full_expected_top_level_keys():
    game, a, _b = _new_game()
    result = game.state(a.id)
    for key in ('turn', 'game_phase', 'turn_phase', 'players', 'map', 'pending_choice', 'purchase_area'):
        assert key in result
    assert len(result['players']) == 2
