"""情報網 A（「在至多3位玩家棄牌堆各放入1張內鬥」）：打出者必須明確選 1 至 3 位其他玩家。

Bug：選 A 後伺服器自動把內鬥放給所有其他玩家（最多 3 位）。修正後 A 開啟巢狀的
`intel_network_internal_conflict_targets` 多選 target_choice（與 B 的 intel_network_dissolve_target
同一套 context／取消 rollback／延後觸發），伺服器驗證全部合法後才動供應與棄牌堆。
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from server import main
from server.game import Game, GamePhase, TurnPhase
from server.game_card_play import INTEL_NETWORK_RECIPIENT_CHOICE_KEY
from test_action_card_regressions import card, names, pin_noop_event


def _game(player_count=4, names_by_index=None):
    seats = []
    for i in range(1, player_count + 1):
        seats.append((f"p{i}", (names_by_index or {}).get(i - 1, f"P{i}")))
    game = Game(seats)
    game.game_phase = GamePhase.MAIN
    game.turn_phase = TurnPhase.ACTION
    game.current_player_index = 0
    game.pending_base_choices = {}
    pin_noop_event(game)
    for player in game.players:
        # 固定無陣營能力：避免隨機陣營（盟旗學校、游擊隊…）或手上的取消反應牌改變前置條件。
        player.faction_id = "liberals"
        player.hand = []
        player.deck.discard_pile = []
    actor = game.players[0]
    actor.hand = [card(game, "情報網")]
    actor.resources = {"money": 0, "propaganda": 0}
    return game


def _open_picker(game):
    actor = game.players[0]
    played = game.play_card(0, mode="action")
    assert played.get("success") and played.get("pending_choice"), played
    assert game.pending_choice["choice_key"] == "choose_one"
    resolved = game.resolve_pending_choice(actor.id, 0)
    assert resolved.get("success") and resolved.get("pending_choice") is True, resolved
    choice = game.pending_choice
    assert choice["choice_key"] == INTEL_NETWORK_RECIPIENT_CHOICE_KEY
    return choice


def _world(game):
    return {
        "supply": dict(game.static_purchase_supply),
        "discards": {p.id: names(p.deck.discard_pile) for p in game.players},
        "hands": {p.id: names(p.hand) for p in game.players},
        "draws": {p.id: names(p.deck.draw_pile) for p in game.players},
        "log": list(game.action_log),
        "turn_log": copy.deepcopy({k: v for k, v in game.turn_log.items() if k != "pending_topdeck_uses"}),
    }


def _new_log(game, before):
    return game.action_log[len(before["log"]):]


def _line(game, text):
    return f"[Turn {game.turn}] {text}"


def test_option_a_opens_explicit_multi_recipient_picker_instead_of_auto_targeting():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    supply_before = game.static_purchase_supply["內鬥"]

    choice = _open_picker(game)

    # 選 A 當下沒有任何人拿到內鬥、供應不變。
    assert [names(p.deck.discard_pile) for p in (p2, p3, p4)] == [[], [], []]
    assert game.static_purchase_supply["內鬥"] == supply_before
    assert choice["type"] == "target_choice"
    assert choice["player_id"] == actor.id
    state_choice = game.state(actor.id)["pending_choice"]
    assert state_choice["choice_key"] == INTEL_NETWORK_RECIPIENT_CHOICE_KEY
    assert state_choice["type"] == "target_choice"
    assert state_choice["multi_select"] is True
    assert state_choice["count"] == 3
    assert state_choice["min_count"] == 1
    assert state_choice["cancellable"] is True
    assert state_choice["interaction_kind"] is None
    assert state_choice["source_name"] == "情報網"
    assert state_choice["prompt"] == "情報網：選擇 1 至 3 位其他玩家，各在其棄牌堆放入 1 張內鬥。"
    assert [(t["id"], t["label"]) for t in state_choice["targets"]] == [
        (p2.id, "P2"), (p3.id, "P3"), (p4.id, "P4"),
    ]
    # 其他玩家的投影一樣看得到這個（公開的）對象清單，但不會被當成自己的選擇。
    assert game.state(p2.id)["pending_choice"]["player_id"] == actor.id


def test_two_of_three_opponents_only_selected_receive_with_exact_logs():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    p2.deck.discard_pile = [game._starter_card("追隨者")]
    choice = _open_picker(game)
    before = _world(game)

    result = game.resolve_pending_choice(actor.id, None, target_player_ids=[p2.id, p4.id], expected_choice_id=None)

    assert result.get("success") is True, result
    assert result["target_player_ids"] == [p2.id, p4.id]
    assert game.pending_choice is None
    assert names(p2.deck.discard_pile) == ["追隨者", "內鬥"]
    assert names(p3.deck.discard_pile) == []
    assert names(p4.deck.discard_pile) == ["內鬥"]
    assert names(actor.deck.discard_pile) == ["情報網"]
    assert actor.hand == []
    assert game.static_purchase_supply["內鬥"] == before["supply"]["內鬥"] - 2
    assert game.static_purchase_supply["分神"] == before["supply"]["分神"]
    assert _new_log(game, before) == [
        _line(game, "P2 gained 1 card(s): 內鬥"),
        _line(game, "P4 gained 1 card(s): 內鬥"),
    ]
    # 「P1 played 情報網」仍在 log 中且只出現一次。
    assert game.action_log.count(_line(game, "P1 played 情報網")) == 1
    assert choice.get("is_final_confirmation") is True
    state_players = {p["name"]: p for p in game.state(actor.id)["players"]}
    assert state_players["P2"]["discard_pile"] == ["追隨者", "內鬥"]
    assert state_players["P3"]["discard_pile"] == []
    assert state_players["P4"]["discard_pile"] == ["內鬥"]


def test_single_recipient():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    _open_picker(game)
    before = _world(game)

    result = game.resolve_pending_choice(actor.id, None, target_player_ids=[p3.id])

    assert result.get("success") is True, result
    assert [names(p.deck.discard_pile) for p in (p2, p3, p4)] == [[], ["內鬥"], []]
    assert _new_log(game, before) == [_line(game, "P3 gained 1 card(s): 內鬥")]
    assert game.static_purchase_supply["內鬥"] == before["supply"]["內鬥"] - 1


def test_max_three_recipients_all_opponents():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    choice = _open_picker(game)
    assert choice["count"] == 3
    before = _world(game)

    result = game.resolve_pending_choice(actor.id, None, target_player_ids=[p4.id, p2.id, p3.id])

    assert result.get("success") is True, result
    assert [names(p.deck.discard_pile) for p in (p2, p3, p4)] == [["內鬥"], ["內鬥"], ["內鬥"]]
    assert game.static_purchase_supply["內鬥"] == before["supply"]["內鬥"] - 3
    # log 依玩家選擇的順序列出實際拿到牌的對象。
    assert _new_log(game, before) == [
        _line(game, "P4 gained 1 card(s): 內鬥"),
        _line(game, "P2 gained 1 card(s): 內鬥"),
        _line(game, "P3 gained 1 card(s): 內鬥"),
    ]


def test_two_player_game_caps_at_one_and_still_requires_explicit_pick():
    game = _game(2)
    actor, p2 = game.players
    choice = _open_picker(game)
    assert choice["count"] == 1 and choice["min_count"] == 1
    assert names(p2.deck.discard_pile) == []
    assert game.resolve_pending_choice(actor.id, None, target_player_ids=[p2.id]).get("success") is True
    assert names(p2.deck.discard_pile) == ["內鬥"]


@pytest.mark.parametrize(
    "label, submit, error",
    [
        ("actor", lambda g: dict(target_player_ids=["p1"]), "情報網不能選擇自己"),
        ("actor-with-other", lambda g: dict(target_player_ids=["p2", "p1"]), "情報網不能選擇自己"),
        ("duplicate", lambda g: dict(target_player_ids=["p2", "p2"]), "情報網不能重複選擇同一位玩家"),
        ("unknown", lambda g: dict(target_player_ids=["p2", "ghost"]), "情報網只能選擇其他有效玩家"),
        ("too-many", lambda g: dict(target_player_ids=["p2", "p3", "p4", "ghost"]), "情報網必須選擇 1 至 3 位其他玩家"),
        ("empty", lambda g: dict(target_player_ids=[]), "情報網必須選擇 1 至 3 位其他玩家"),
        ("no-selection", lambda g: dict(), "情報網必須選擇 1 至 3 位其他玩家"),
        ("single-int-index", lambda g: dict(index=0), "情報網必須選擇 1 至 3 位其他玩家"),
        ("not-a-list", lambda g: dict(target_player_ids="p2"), "情報網目標格式無效"),
        ("non-string-id", lambda g: dict(target_player_ids=[2]), "情報網目標格式無效"),
        ("ids-and-index", lambda g: dict(index=[0], target_player_ids=["p2"]), "情報網目標格式無效"),
        ("index-out-of-range", lambda g: dict(index=[0, 9]), "Invalid choice index"),
        ("index-bool", lambda g: dict(index=[True]), "Invalid choice index"),
        ("index-duplicate", lambda g: dict(index=[1, 1]), "情報網不能重複選擇同一位玩家"),
        ("index-empty", lambda g: dict(index=[]), "情報網必須選擇 1 至 3 位其他玩家"),
    ],
)
def test_invalid_submissions_are_rejected_without_any_mutation(label, submit, error):
    game = _game(4)
    actor = game.players[0]
    choice = _open_picker(game)
    choice_id = game.state(actor.id)["pending_choice"]["choice_id"]
    before = _world(game)
    kwargs = submit(game)
    index = kwargs.pop("index", None)

    result = game.resolve_pending_choice(actor.id, index, expected_choice_id=choice_id, **kwargs)

    assert result.get("error") == error, (label, result)
    assert _world(game) == before, label
    assert game.pending_choice is choice
    assert game.state(actor.id)["pending_choice"]["choice_id"] == choice_id
    # 被拒絕後仍可正常完成選擇。
    ok = game.resolve_pending_choice(actor.id, None, target_player_ids=["p3"], expected_choice_id=choice_id)
    assert ok.get("success") is True, ok


def test_forged_actor_and_stale_choice_rejected_without_mutation():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    choice = _open_picker(game)
    choice_id = game.state(actor.id)["pending_choice"]["choice_id"]
    before = _world(game)

    forged = game.resolve_pending_choice(p2.id, None, target_player_ids=[p3.id], expected_choice_id=choice_id)
    stale = game.resolve_pending_choice(actor.id, None, target_player_ids=[p3.id], expected_choice_id="stale")
    forged_cancel = game.cancel_pending_choice(p2.id, expected_choice_id=choice_id)

    assert forged == {"error": "Not your pending choice"}
    assert stale == {"error": "Stale pending choice"}
    assert forged_cancel == {"error": "Not your pending choice"}
    assert _world(game) == before
    assert game.pending_choice is choice


def test_indices_submission_for_mcp_and_ai():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    _open_picker(game)

    result = game.resolve_pending_choice(actor.id, [2, 0])

    assert result.get("success") is True, result
    assert result["target_player_ids"] == [p4.id, p2.id]
    assert [names(p.deck.discard_pile) for p in (p2, p3, p4)] == [["內鬥"], [], ["內鬥"]]


def test_finite_supply_falls_back_to_double_distraction_then_nothing():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    game.static_purchase_supply["內鬥"] = 1
    game.static_purchase_supply["分神"] = 3
    _open_picker(game)
    before = _world(game)

    result = game.resolve_pending_choice(actor.id, None, target_player_ids=[p2.id, p3.id, p4.id])

    assert result.get("success") is True, result
    assert names(p2.deck.discard_pile) == ["內鬥"]
    assert names(p3.deck.discard_pile) == ["分神", "分神"]
    assert names(p4.deck.discard_pile) == ["分神"]
    assert game.static_purchase_supply["內鬥"] == 0
    assert game.static_purchase_supply["分神"] == 0
    assert _new_log(game, before) == [
        _line(game, "P2 gained 1 card(s): 內鬥"),
        _line(game, "內鬥供應已空：以 2 張分神替代（情報網）"),
        _line(game, "P3 gained 2 card(s): 分神、分神"),
        _line(game, "內鬥供應已空：以 1 張分神替代（情報網）"),
        _line(game, "P4 gained 1 card(s): 分神"),
    ]


def test_exhausted_supply_logs_no_gain_for_recipients_who_got_nothing():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    game.static_purchase_supply["內鬥"] = 0
    game.static_purchase_supply["分神"] = 0
    _open_picker(game)
    before = _world(game)

    result = game.resolve_pending_choice(actor.id, None, target_player_ids=[p2.id, p4.id])

    assert result.get("success") is True, result
    assert [names(p.deck.discard_pile) for p in (p2, p3, p4)] == [[], [], []]
    assert _new_log(game, before) == [
        _line(game, "內鬥與分神供應皆空，無法放置（情報網）"),
        _line(game, "內鬥與分神供應皆空，無法放置（情報網）"),
    ]
    assert not any("gained" in line for line in _new_log(game, before))
    assert game.pending_choice is None


def test_ai_red_army_is_a_legal_selectable_recipient():
    game = _game(4, names_by_index={1: "AI 紅軍"})
    actor, red, p3, p4 = game.players
    red.faction_id = "red_army"
    game.ai_red_army_player_id = red.id
    choice = _open_picker(game)
    assert [(t["id"], t["label"]) for t in choice["targets"]] == [(red.id, "AI 紅軍"), (p3.id, "P3"), (p4.id, "P4")]
    before = _world(game)

    result = game.resolve_pending_choice(actor.id, None, target_player_ids=[red.id, p3.id])

    assert result.get("success") is True, result
    assert [names(p.deck.discard_pile) for p in (red, p3, p4)] == [["內鬥"], ["內鬥"], []]
    assert _new_log(game, before) == [
        _line(game, "AI 紅軍 gained 1 card(s): 內鬥"),
        _line(game, "P3 gained 1 card(s): 內鬥"),
    ]


def test_red_army_actor_can_pick_recipients_and_never_targets_itself():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    actor.faction_id = "red_army"
    choice = _open_picker(game)
    assert actor.id not in [t["id"] for t in choice["targets"]]
    assert game.resolve_pending_choice(actor.id, None, target_player_ids=[p4.id]).get("success") is True
    assert [names(p.deck.discard_pile).count("內鬥") for p in game.players] == [0, 0, 0, 1]


def test_cancel_picker_rolls_back_whole_play_without_placing_anything():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    pre_play = _world(game)
    choice = _open_picker(game)
    choice_id = game.state(actor.id)["pending_choice"]["choice_id"]
    assert names(actor.deck.discard_pile) == ["情報網"]

    cancelled = game.cancel_pending_choice(actor.id, expected_choice_id=choice_id)

    assert cancelled.get("success") is True and cancelled.get("cancelled") is True, cancelled
    assert cancelled["choice_key"] == INTEL_NETWORK_RECIPIENT_CHOICE_KEY
    assert game.pending_choice is None
    assert names(actor.hand) == ["情報網"]
    assert names(actor.deck.discard_pile) == []
    assert [names(p.deck.discard_pile) for p in (p2, p3, p4)] == [[], [], []]
    assert game.static_purchase_supply == pre_play["supply"]
    assert not any("gained" in line for line in game.action_log)
    # 取消後可以重新打出並改走 B 或 A。
    replay = game.play_card(0, mode="action")
    assert replay.get("success") and game.pending_choice["choice_key"] == "choose_one", replay


def test_deferred_play_triggers_settle_only_on_recipient_confirmation(monkeypatch):
    game = _game(4)
    actor, p2, *_ = game.players
    calls = []
    original = game._apply_card_play_faction_abilities

    def spy(player, **kwargs):
        calls.append((player.id, getattr(kwargs.get("played_card"), "name", None)))
        return original(player, **kwargs)

    monkeypatch.setattr(game, "_apply_card_play_faction_abilities", spy)
    choice = _open_picker(game)
    assert calls == []
    assert "post_play_faction_triggers" in choice["context"]

    game.resolve_pending_choice(actor.id, None, target_player_ids=[p2.id])

    assert calls == [(actor.id, "情報網")]
    assert "post_play_faction_triggers" not in choice["context"]


def test_option_b_still_opens_dissolve_target_choice():
    game = _game(2)
    actor, p2 = game.players
    p2.faction_id = "hong_kong"
    actor.organizations = {"北京": 1}
    p2.organizations = {"天津": 1}
    game.play_card(0, mode="action")

    resolved = game.resolve_pending_choice(actor.id, 1)

    assert resolved.get("pending_choice") is True, resolved
    assert game.pending_choice["choice_key"] == "intel_network_dissolve_target"
    assert "multi_select" not in game.state(actor.id)["pending_choice"]
    assert game.resolve_pending_choice(actor.id, 0).get("success") is True
    assert p2.organizations.get("天津", 0) == 0
    assert names(p2.deck.discard_pile).count("內鬥") == 0


def test_effect_engine_never_auto_targets_intel_network_option_a():
    game = _game(4)
    actor = game.players[0]
    before = _world(game)

    game.effect_engine.execute(
        {"type": "add_internal_conflict", "count": 1},
        actor,
        game,
        context={"card_name": "情報網", "choice_index": 0},
    )

    assert [names(p.deck.discard_pile) for p in game.players] == [[], [], [], []]
    assert game.static_purchase_supply == before["supply"]
    assert _new_log(game, before) == [_line(game, "P1 的 add_internal_conflict 沒有合法目標，未放置內鬥")]


def test_divide_still_uses_its_own_play_time_targets():
    game = _game(4)
    actor, p2, p3, p4 = game.players
    actor.hand = [card(game, "離間")]
    result = game.play_card(0, mode="action", target_player_ids=[p3.id])
    assert result.get("success") is True, result
    assert game.pending_choice is None
    assert [names(p.deck.discard_pile).count("內鬥") for p in (p2, p3, p4)] == [0, 1, 0]


def test_ai_policy_and_mcp_summary_use_indices_for_multi_select():
    from mcp_server.summarize import _pending_choice_action_entry
    from red_army_policy.state_assessor import assess
    from red_army_policy.target_selector import select_pending_choice_submission

    game = _game(4)
    actor, p2, p3, p4 = game.players
    actor.faction_id = "red_army"
    p3.organizations = {"臺北": 1, "臺中": 1, "臺南": 1}
    _open_picker(game)
    state = game.state(actor.id)
    pending = state["pending_choice"]

    submission = select_pending_choice_submission(pending, assess(state, actor.id))
    entry = _pending_choice_action_entry(pending)

    assert len(submission["indices"]) == 3
    assert sorted(submission["indices"]) == submission["indices"] == [0, 1, 2]
    assert entry["use_indices_param"] is True
    assert entry["count"] == 3 and entry["min_count"] == 1
    assert [t["id"] for t in entry["targets"]] == [p2.id, p3.id, p4.id]
    result = game.resolve_pending_choice(actor.id, submission["indices"], expected_choice_id=pending["choice_id"])
    assert result.get("success") is True, result
    assert [names(p.deck.discard_pile).count("內鬥") for p in (p2, p3, p4)] == [1, 1, 1]


def _ws_setup(client, **payload):
    setup = client.post("/test/setup-intel-network-proof", json={"viewer_faction": "liberals", **payload}).json()
    assert setup.get("success") is True, setup
    game = main.manager.games[setup["game_id"]]
    pin_noop_event(game)
    return setup, game


def test_websocket_flow_resolves_only_selected_and_rejects_bad_payloads():
    client = TestClient(main.app)
    setup, game = _ws_setup(client, enemy_a_faction="red_army")
    viewer, enemy_a, enemy_b, enemy_c = game.players
    game_id = setup["game_id"]
    with client.websocket_connect(f"/ws/{game_id}/{viewer.id}") as ws:
        ws.receive_json()
        ws.send_json({"action": "play_card", "index": 0, "mode": "action"})
        state = ws.receive_json()
        option = state["pending_choice"]
        assert option["choice_key"] == "choose_one", option
        ws.send_json({"action": "resolve_choice", "index": 0, "choice_id": option["choice_id"]})
        state = ws.receive_json()
        picker = state["pending_choice"]
        assert picker["choice_key"] == INTEL_NETWORK_RECIPIENT_CHOICE_KEY
        assert picker["multi_select"] is True
        before = _world(game)

        for bad in ([viewer.id], [enemy_a.id, enemy_a.id], ["ghost"], [], None):
            payload = {"action": "resolve_choice", "choice_id": picker["choice_id"]}
            if bad is not None:
                payload["target_player_ids"] = bad
            ws.send_json(payload)
            error_state = ws.receive_json()
            assert error_state.get("error"), (bad, error_state)
            assert error_state["pending_choice"]["choice_id"] == picker["choice_id"]
            assert _world(game) == before, bad

        ws.send_json({
            "action": "resolve_choice",
            "choice_id": picker["choice_id"],
            "target_player_ids": [enemy_a.id, enemy_c.id],
        })
        final = ws.receive_json()
        assert final.get("error") is None, final
        assert final["pending_choice"] is None
    discards = {p["name"]: p["discard_pile"] for p in final["players"]}
    assert discards == {"viewer": ["情報網"], "enemyA": ["內鬥"], "enemyB": [], "enemyC": ["內鬥"]}


def test_websocket_other_seat_cannot_resolve_or_cancel_actors_picker():
    client = TestClient(main.app)
    setup, game = _ws_setup(client)
    viewer, enemy_a, *_ = game.players
    game_id = setup["game_id"]
    choice = _open_picker(game)
    choice_id = game.state(viewer.id)["pending_choice"]["choice_id"]
    before = _world(game)
    with client.websocket_connect(f"/ws/{game_id}/{enemy_a.id}") as ws:
        ws.receive_json()
        ws.send_json({"action": "resolve_choice", "choice_id": choice_id, "target_player_ids": [enemy_a.id]})
        assert ws.receive_json().get("error")
        ws.send_json({"action": "cancel_choice", "choice_id": choice_id})
        assert ws.receive_json().get("error")
    assert _world(game) == before
    assert game.pending_choice is choice


def test_reaction_window_declined_then_picker_and_canceled_play_never_opens_picker():
    # 對手手上有取消反應牌：先開反應視窗。不取消 → 選項 → A 開 picker；取消 → 情報網完全不生效。
    declined = _game(4)
    actor, reactor, p3, p4 = declined.players
    reactor.hand = [card(declined, "爆料黑幕")]
    played = declined.play_card(0, mode="action")
    assert played.get("pending_choice"), played
    assert declined.pending_choice["type"] == "reaction_choice"
    assert declined.resolve_pending_choice(reactor.id, 0).get("success"), declined.pending_choice
    assert declined.pending_choice["choice_key"] == "choose_one"
    resolved = declined.resolve_pending_choice(actor.id, 0)
    assert resolved.get("pending_choice") is True, resolved
    assert declined.pending_choice["choice_key"] == INTEL_NETWORK_RECIPIENT_CHOICE_KEY
    assert [names(p.deck.discard_pile).count("內鬥") for p in declined.players] == [0, 0, 0, 0]
    assert declined.resolve_pending_choice(actor.id, None, target_player_ids=[reactor.id]).get("success")
    assert [names(p.deck.discard_pile).count("內鬥") for p in declined.players] == [0, 1, 0, 0]

    canceled = _game(4)
    actor, reactor, *_ = canceled.players
    reactor.hand = [card(canceled, "爆料黑幕")]
    canceled.play_card(0, mode="action")
    assert canceled.pending_choice["type"] == "reaction_choice"
    result = canceled.resolve_pending_choice(reactor.id, 1)
    assert result.get("success"), result
    assert canceled.pending_choice is None or canceled.pending_choice.get("choice_key") != INTEL_NETWORK_RECIPIENT_CHOICE_KEY
    assert all(names(p.deck.discard_pile).count("內鬥") == 0 for p in canceled.players)
