"""取消反應（爆料黑幕／產業滲透／情報網）的兩條觸發路徑與 viewer-scoped 投影。

前端（static/event_reveal_core.js）只依公開的 pending_choice.type === 'reaction_choice' 判斷「這次動作觸發了取消反應」，
不自動揭示事件卡。這裡鎖定伺服器契約：
  - 卡牌（行動模式打出「領導」）與陣營能力（紅軍「統戰部」）都會對持有任一張取消牌的其他玩家開啟 reaction_choice；
  - 反應者看得到自己的取消牌；行動者與旁觀者只看到 type 與遮蔽後的提示，看不到反應者手上的牌（observer privacy）；
  - 反應者不取消（index 0）或取消（index 1）後視窗關閉。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card  # noqa: E402
from server.game import Game, GamePhase, TurnPhase  # noqa: E402

REACTION_CARDS = ("爆料黑幕", "產業滲透", "情報網")


def _card(game, name):
    card_def = next(c for c in game.structured_cards if c.get("name") == name)
    return Card(card_def["name"], card_def.get("type", "command"), dict(card_def.get("resources", {}) or {}))


def _game(path, reaction_card):
    game = Game([("p-actor", "actor"), ("p-reactor", "reactor"), ("p-watch", "watcher")])
    actor, reactor, watcher = game.players
    actor.faction_id, actor.base = ("hong_kong", "香港城") if path == "card" else ("red_army", "北京")
    reactor.faction_id, reactor.base = "taiwan_green", "臺北"
    watcher.faction_id, watcher.base = "tibet_family", "拉薩"
    for p in game.players:
        p.organizations = {p.base: 1}
        p.deck.draw_pile = [_card(game, "領導")]
        p.deck.discard_pile = []
        p.hand = []
    actor.hand = [_card(game, "領導")] if path == "card" else []
    reactor.hand = [_card(game, reaction_card)]
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION
    game.game_phase = GamePhase.MAIN
    game.pending_base_choices = {}
    return game


def _trigger(game, path):
    if path == "card":
        return game.play_card(0, mode="action")
    return game._activated_faction_action(game.players[0], "統戰部")


@pytest.mark.parametrize("path", ["card", "ability"])
@pytest.mark.parametrize("reaction_card", REACTION_CARDS)
@pytest.mark.parametrize("index,outcome", [(0, "decline"), (1, "cancel")])
def test_both_trigger_paths_open_reaction_choice_with_private_cards(path, reaction_card, index, outcome):
    game = _game(path, reaction_card)
    result = _trigger(game, path)
    assert result.get("pending_choice") is True, result
    assert game.pending_choice["type"] == "reaction_choice"
    assert game.pending_choice["player_id"] == "p-reactor"

    reactor_view = game.state("p-reactor")["pending_choice"]
    assert reactor_view["type"] == "reaction_choice"
    assert [c["name"] if isinstance(c, dict) else c for c in reactor_view["cards"]] == [reaction_card]
    for viewer in ("p-actor", "p-watch"):
        view = game.state(viewer)
        public = view["pending_choice"]
        assert public["type"] == "reaction_choice", viewer
        assert public["player_id"] == "p-reactor"
        assert public["cards"] == [], viewer
        assert reaction_card not in str(public), viewer
        reactor_public = next(p for p in view["players"] if p["id"] == "p-reactor")
        assert reaction_card not in str(reactor_public.get("hand")), viewer

    choice_id = game.pending_choice.get("choice_id")
    resolved = game.resolve_pending_choice("p-reactor", index, expected_choice_id=choice_id)
    assert not resolved.get("error"), resolved
    assert not game.pending_choice or game.pending_choice.get("type") != "reaction_choice"
    log = "\n".join(game.action_log[-10:])
    if outcome == "cancel":
        assert f"reacted with {reaction_card} to cancel" in log, log
    else:
        assert "reacted with" not in log, log
