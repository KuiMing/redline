from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.cards import Card
from server.game import Game, TurnPhase


NONVIOLENT_FACTIONS = (
    'tibet_dharamsala',
    'uyghur_munich',
    'minyun',
    'gender_revolution',
)


def test_every_nonviolent_faction_uses_armed_card_wording():
    game = Game([('p1', 'player'), ('red', 'red')])
    player = game.players[0]

    for faction_id in NONVIOLENT_FACTIONS:
        player.faction_id = faction_id
        abilities = game._player_effective_abilities(player)
        nonviolence = next(ability for ability in abilities if ability.get('name') == '非暴力')
        assert nonviolence.get('effect') == '禁止持有武裝類卡牌。'


def test_nonviolent_play_and_purchase_errors_use_armed_card_wording():
    game = Game([('p1', 'player'), ('red', 'red')])
    player = game.players[0]
    player.faction_id = 'tibet_dharamsala'
    player.base = '達蘭薩拉'
    player.organizations = {'達蘭薩拉': 1}
    player.hand = [Card('武裝測試', 'armed', {})]
    game.current_player_index = 0
    game.turn_phase = TurnPhase.ACTION

    played = game.play_card(0, mode='action')
    game.purchase_area = [Card('武裝購買測試', 'armed', {})]
    bought = game.buy_card(0)

    assert played.get('error') == '非暴力：不能打出武裝類卡牌'
    assert bought.get('error') == '非暴力：不能購買武裝類卡牌'
