import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'shared-actions'
RECORD_DIR.mkdir(parents=True, exist_ok=True)
js = (ROOT / 'static' / 'leaflet_game_map_logic.js').read_text(encoding='utf-8')
html = (ROOT / 'static' / 'leaflet_game_map.html').read_text(encoding='utf-8')

checks = {
    'can_act_from_town': 'function canActFromTown(townName)' in js,
    'shared_movement_enabled': 'if (!canActFromTown(townName)) return { road: [], rail: [] };' in js,
    'shared_build_button': 'directBuildBtn' in html and 'sendDirectBuildAction' in js,
    'shared_build_hint_text': '共享組織可用性' in js or '共享組織' in js,
    'shared_origin_highlight': '共享組織起點' in js,
    'test_select_reports_shared': 'shared: playerHasSharedAccessToTown(townName)' in js,
}

payload = {
    'summary': {
        'total': len(checks),
        'passed': sum(1 for v in checks.values() if v),
        'failed': sum(1 for v in checks.values() if not v),
    },
    'checks': checks,
}

(RECORD_DIR / 'SHARED_INTERACTION_UI_PHASE8_VALIDATION.json').write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
)
(RECORD_DIR / 'SHARED_INTERACTION_UI_PHASE8_VALIDATION.md').write_text(
    '# SHARED INTERACTION UI PHASE8 VALIDATION\n\n' +
    '\n'.join(f'- {k}: {"PASS" if v else "FAIL"}' for k, v in checks.items()) + '\n',
    encoding='utf-8'
)
print(json.dumps(payload, ensure_ascii=False))
if payload['summary']['failed']:
    raise SystemExit(1)
