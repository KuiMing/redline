from fastapi.testclient import TestClient

from server.main import app


def test_setup_intel_network_cancel_reaction_proof_scenario_has_visible_state():
    client = TestClient(app)
    res = client.post('/test/setup-intel-network-cancel-reaction-proof', json={})
    data = res.json()

    assert data['success'] is True
    assert data['actor_id']
    assert data['reactor_id']

    state = data['state']
    assert state['current_player'] == 'actor'
    actor = next(p for p in state['players'] if p['name'] == 'actor')
    reactor = next(p for p in state['players'] if p['name'] == 'reactor')
    assert actor['hand'] == ['領導']
    assert actor['deck_count'] == 1
    assert actor['discard_count'] == 0
    assert reactor['hand'] == ['情報網']
    assert reactor['discard_count'] == 0
    assert any('情報網取消反應測試' in entry for entry in state['action_log'])


def test_resolve_intel_network_cancel_reaction_proof_cancels_draw_effect():
    client = TestClient(app)
    setup = client.post('/test/setup-intel-network-cancel-reaction-proof', json={}).json()

    resolved = client.post('/test/resolve-intel-network-cancel-reaction-proof', json={
        'game_id': setup['game_id'],
    }).json()

    assert resolved['success'] is True
    assert resolved['result']['success'] is True
    state = resolved['state']
    actor = next(p for p in state['players'] if p['name'] == 'actor')
    reactor = next(p for p in state['players'] if p['name'] == 'reactor')
    assert actor['hand'] == []
    assert actor['deck_count'] == 1, '領導若未被取消會抽走 ShouldNotDraw'
    assert actor['discard_count'] == 1
    assert reactor['hand'] == []
    assert reactor['deck_count'] == 1, '情報網取消不應像產業滲透一樣額外抽牌'
    assert reactor['discard_count'] == 1
    assert any('reactor reacted with 情報網 to cancel 領導' in entry for entry in state['action_log'])
