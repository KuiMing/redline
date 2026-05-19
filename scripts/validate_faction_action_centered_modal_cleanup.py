import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
sys.path.insert(0, str(ROOT))

from server.game import Game
from server.cards import Card


def check_runtime_state_flag():
    game = Game([('p1', 'P1'), ('p2', 'P2')])
    player = game.players[0]
    player.faction_id = 'liberals'
    player.deck.draw_pile = [Card('追隨者', 'propaganda', {'propaganda': 1})]
    before = game.state().get('faction_action_used') is False
    result = game._activated_faction_action(player, '立場試探')
    after_state = game.state()
    return {
        'name': 'runtime_state_exposes_faction_action_used',
        'passed': before and result.get('success') is True and after_state.get('faction_action_used') is True,
        'before_flag_was_false': before,
        'after_flag': after_state.get('faction_action_used'),
        'result': result,
    }


def check_static_modal_cleanup():
    app_js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    checks = {
        'dynamic_guess_modal_helper_exists': 'function openFactionGuessModal(actionName, hintText)' in app_js,
        'guess_buttons_created_dynamically': "btn.textContent = guess === 'odd' ? '猜奇數' : '猜偶數';" in app_js,
        'centered_panel_suppresses_buttons_after_used': 'if (!factionActionUsed) buildButtons(modalChoices);' in app_js,
        'used_state_message_present': "modalDesc.textContent = factionActionUsed ? '本回合已發動陣營能力。' : message;" in app_js,
        'no_stale_static_guess_onclick_lookup': "document.getElementById('guessOddBtn').onclick" not in app_js and "document.getElementById('guessEvenBtn').onclick" not in app_js,
    }
    return {
        'name': 'static_centered_modal_cleans_stale_buttons',
        'passed': all(checks.values()),
        'checks': checks,
    }


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    tests = [check_runtime_state_flag(), check_static_modal_cleanup()]
    failed = [test for test in tests if not test.get('passed')]
    payload = {
        'summary': {
            'total': len(tests),
            'passed': len(tests) - len(failed),
            'failed': len(failed),
        },
        'tests': tests,
    }
    (RECORD_DIR / 'FACTION_ACTION_CENTERED_MODAL_CLEANUP_VALIDATION.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    lines = [
        '# FACTION ACTION CENTERED MODAL CLEANUP VALIDATION',
        '',
        f"- total: {payload['summary']['total']}",
        f"- passed: {payload['summary']['passed']}",
        f"- failed: {payload['summary']['failed']}",
        '',
    ]
    for test in tests:
        mark = 'PASS' if test.get('passed') else 'FAIL'
        lines.append(f"- [{mark}] {test['name']}")
    (RECORD_DIR / 'FACTION_ACTION_CENTERED_MODAL_CLEANUP_VALIDATION.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
