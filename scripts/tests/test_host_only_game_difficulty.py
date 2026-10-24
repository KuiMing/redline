import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import main
from server.game import Game, STATIC_PURCHASE_CARD_NAMES


def setup_room():
    game_id = "difficulty-room"
    host_id = "host-player"
    guest_id = "guest-player"
    main.lobby[game_id] = [(host_id, "房主"), (guest_id, "訪客")]
    main.lobby_hosts[game_id] = host_id
    main.lobby_market_mode[game_id] = "sample_53"
    main.manager.games.pop(game_id, None)
    return game_id, host_id, guest_id


def teardown_room(game_id):
    main.lobby.pop(game_id, None)
    main.lobby_hosts.pop(game_id, None)
    main.lobby_market_mode.pop(game_id, None)
    main.manager.games.pop(game_id, None)


def test_only_host_can_change_game_difficulty():
    game_id, host_id, guest_id = setup_room()
    try:
        rejected = main.set_lobby_market_mode({
            "game_id": game_id,
            "player_id": guest_id,
            "market_mode": "all_cards",
        })
        assert rejected == {"error": "Only host can change game difficulty"}
        assert main.lobby_market_mode[game_id] == "sample_53"

        changed = main.set_lobby_market_mode({
            "game_id": game_id,
            "player_id": host_id,
            "market_mode": "all_cards",
        })
        assert changed == {"success": True, "market_mode": "all_cards"}
        assert main.lobby_market_mode[game_id] == "all_cards"
    finally:
        teardown_room(game_id)


def test_host_cannot_set_unknown_game_difficulty():
    game_id, host_id, _ = setup_room()
    try:
        rejected = main.set_lobby_market_mode({
            "game_id": game_id,
            "player_id": host_id,
            "market_mode": "unknown",
        })
        assert rejected == {"error": "Invalid game difficulty"}
        assert main.lobby_market_mode[game_id] == "sample_53"
    finally:
        teardown_room(game_id)


def test_difficulty_tooltip_counts_match_the_runtime_card_pools():
    counts_by_mode = {}
    for market_mode in ("sample_53", "all_cards"):
        game = Game([("one", "one"), ("two", "two")], market_mode=market_mode)
        cards = list(game.purchase_deck.draw_pile)
        cards.extend(card for card in game.purchase_area if card.name not in STATIC_PURCHASE_CARD_NAMES)
        counts_by_mode[market_mode] = Counter(card.card_type for card in cards)

    simple = counts_by_mode["sample_53"]
    assert sum(simple.values()) == 53
    assert simple["support"] == 18
    assert sum(count for card_type, count in simple.items() if card_type != "support") == 35

    general = counts_by_mode["all_cards"]
    assert general == Counter({
        "support": 64,
        "command": 68,
        "spy": 24,
        "money": 20,
        "armed": 16,
        "transport": 15,
        "propaganda_special": 15,
        "purge": 12,
        "organization": 11,
    })
