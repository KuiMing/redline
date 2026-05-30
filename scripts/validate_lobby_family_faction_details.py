#!/usr/bin/env python3
"""Validate Uyghur/Tibet family faction detail payloads and selected-base UI data.

This is a fast non-browser validator for the lobby detail bug where the UI option
used family ids (uyghur_family/tibet_family) but lacked the selected base variant's
abilities/rules/win conditions.
"""

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD_DIR = ROOT / 'docs' / 'records' / 'faction-ui'
OUT_JSON = RECORD_DIR / 'LOBBY_FAMILY_FACTION_DETAILS_VALIDATION.json'
OUT_MD = RECORD_DIR / 'LOBBY_FAMILY_FACTION_DETAILS_VALIDATION.md'
BASE_URL = 'http://127.0.0.1:8000'
FAMILIES = {
    'uyghur_family': {
        'label': '維吾爾',
        'bases': ['伊斯坦堡', '慕尼黑', '華盛頓', '阿拉木圖'],
    },
    'tibet_family': {
        'label': '西藏',
        'bases': ['達蘭薩拉', '德拉敦', '哲古宗'],
    },
}


def fetch_factions():
    with urllib.request.urlopen(f'{BASE_URL}/factions', timeout=5) as response:
        return json.loads(response.read().decode('utf-8'))


def main():
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    payload = fetch_factions()
    options = {}
    for category in payload.get('categories', []):
        for option in category.get('options', []):
            options[option.get('id')] = option

    checks = []
    failures = []
    for family_id, spec in FAMILIES.items():
        option = options.get(family_id)
        if not option:
            failures.append(f'{family_id}: missing option')
            continue
        variant_details = option.get('variant_details') or {}
        base_resolved = option.get('base_resolved') or {}
        for base_name in spec['bases']:
            detail = variant_details.get(base_name)
            check = {
                'family_id': family_id,
                'label': spec['label'],
                'base': base_name,
                'has_detail': bool(detail),
                'abilities_count': len((detail or {}).get('abilities') or []),
                'win_conditions_count': len((detail or {}).get('win_conditions') or []),
                'resolved_base': base_resolved.get(base_name),
            }
            errors = []
            if not detail:
                errors.append('missing variant detail')
            if base_resolved.get(base_name) != [base_name]:
                errors.append(f'base_resolved mismatch: {base_resolved.get(base_name)}')
            if detail and not detail.get('abilities'):
                errors.append('missing abilities')
            if detail and not detail.get('win_conditions'):
                errors.append('missing win_conditions')
            if detail:
                detail_base_names = [b.get('name') for b in detail.get('bases', []) if isinstance(b, dict)]
                if base_name not in detail_base_names:
                    errors.append(f'detail bases missing {base_name}: {detail_base_names}')
            check['ok'] = not errors
            check['errors'] = errors
            checks.append(check)
            failures.extend(f'{family_id}/{base_name}: {error}' for error in errors)

    summary = {
        'total': len(checks),
        'passed': sum(1 for check in checks if check['ok']),
        'failed': sum(1 for check in checks if not check['ok']),
    }
    OUT_JSON.write_text(json.dumps({'summary': summary, 'checks': checks, 'failures': failures}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Lobby family faction details validation',
        '',
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        '',
    ]
    if failures:
        lines.append('## Failures')
        lines.extend(f'- {failure}' for failure in failures)
    else:
        lines.append('## Result')
        lines.append('All Uyghur/Tibet base variants expose detail data for the lobby UI.')
    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    sys.exit(main())
