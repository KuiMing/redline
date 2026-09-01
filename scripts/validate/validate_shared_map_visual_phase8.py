from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'shared-actions'
RECORD_DIR.mkdir(parents=True, exist_ok=True)
js = (ROOT / 'static' / 'leaflet_game_map_logic.js').read_text(encoding='utf-8')
html = (ROOT / 'static' / 'leaflet_game_map.html').read_text(encoding='utf-8')

checks = {
    'shared_access_helper': 'function sharedAccessForTown(name)' in js,
    'shared_summary_helper': 'function sharedAccessSummary(name)' in js,
    'shared_badge_marker': 'shared-badge' in js,
    'shared_badge_css': '.shared-badge' in html,
    'status_panel_shared_hint': '金色外框與 S 標記' in js,
    'info_panel_shared_badge': '共享中（${shared.length}）' in js,
}

passed = sum(1 for v in checks.values() if v)
failed = sum(1 for v in checks.values() if not v)

json_path = RECORD_DIR / 'SHARED_MAP_VISUAL_PHASE8_VALIDATION.json'
md_path = RECORD_DIR / 'SHARED_MAP_VISUAL_PHASE8_VALIDATION.md'

payload = {
    'summary': {
        'total': len(checks),
        'passed': passed,
        'failed': failed,
    },
    'checks': checks,
}

import json
json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
md_path.write_text(
    '# SHARED MAP VISUAL PHASE8 VALIDATION\n\n' +
    '\n'.join(f'- {k}: {"PASS" if v else "FAIL"}' for k, v in checks.items()) + '\n',
    encoding='utf-8'
)
print(json.dumps(payload, ensure_ascii=False))
if payload['summary']['failed']:
    raise SystemExit(1)
