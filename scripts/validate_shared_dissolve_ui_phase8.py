import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
js = (ROOT / 'static' / 'leaflet_game_map_logic.js').read_text(encoding='utf-8')
html = (ROOT / 'static' / 'leaflet_game_map.html').read_text(encoding='utf-8')

checks = {
    'dissolve_button_html': 'id="dissolveBtn"' in html,
    'dissolve_hint_html': 'id="dissolveHint"' in html,
    'actual_owner_helper': 'function actualTownOwnerName(townName)' in js,
    'shared_dissolve_target_helper': 'function sharedDissolveTargetForTown(townName)' in js,
    'send_dissolve_action': 'function sendDissolveAction(defender, townName)' in js,
    'test_dissolve_helper': 'window.__dissolveFromSharedForTest' in js,
}

payload = {
    'summary': {
        'total': len(checks),
        'passed': sum(1 for v in checks.values() if v),
        'failed': sum(1 for v in checks.values() if not v),
    },
    'checks': checks,
}

(ROOT / 'SHARED_DISSOLVE_UI_PHASE8_VALIDATION.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(ROOT / 'SHARED_DISSOLVE_UI_PHASE8_VALIDATION.md').write_text(
    '# SHARED DISSOLVE UI PHASE8 VALIDATION\n\n' +
    '\n'.join(f'- {k}: {"PASS" if v else "FAIL"}' for k, v in checks.items()) + '\n',
    encoding='utf-8'
)
print(json.dumps(payload, ensure_ascii=False))
