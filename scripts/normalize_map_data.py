#!/usr/bin/env python3
"""Normalize Redline's canonical map topology and extract the canonical Leaflet geo coordinates.

The game rules use data/map.json. Roads and rails are undirected by rule, so this script
normalizes known town-name aliases and adds missing reverse edges. Geographic coordinates
are extracted once from the former Leaflet snapshot into their own canonical data file.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / 'data' / 'map.json'
GEO_PATH = ROOT / 'data' / 'map_geo_coordinates.v1.json'
LEGACY_LEAFLET_PATH = ROOT / 'static' / 'leaflet_game_map_logic.js'
ALIASES: dict[str, str] = {'台東': '臺東'}


def load_or_extract_geo_coordinates() -> dict[str, list[float]]:
    if GEO_PATH.exists():
        return json.loads(GEO_PATH.read_text(encoding='utf-8'))
    text = LEGACY_LEAFLET_PATH.read_text(encoding='utf-8')
    match = re.search(r'^const GEO_COORDS = (\{.*\});$', text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError('No canonical geo file or legacy GEO_COORDS snapshot found')
    return json.loads(match.group(1))


def normalize_topology(data: dict) -> list[str]:
    towns = data['towns']
    changes: list[str] = []
    for source, entry in towns.items():
        for mode in ('road', 'rail'):
            normalized: list[str] = []
            for raw_target in entry.get(mode, []):
                target = ALIASES.get(raw_target, raw_target)
                if target != raw_target:
                    changes.append(f'{source}.{mode}: {raw_target} -> {target}')
                if target not in normalized:
                    normalized.append(target)
            entry[mode] = normalized

    for source, entry in list(towns.items()):
        for mode in ('road', 'rail'):
            for target in list(entry.get(mode, [])):
                if target not in towns:
                    raise RuntimeError(f'Unknown map endpoint: {source}.{mode}->{target}')
                reverse = towns[target].setdefault(mode, [])
                if source not in reverse:
                    reverse.append(source)
                    changes.append(f'added {target}.{mode}->{source}')
    return changes


def render_array_like(original: str, values: list[str]) -> str:
    if not values:
        return '[]'
    if '\n' not in original:
        return json.dumps(values, ensure_ascii=False, separators=(',', ':'))
    body = ',\n'.join(f'        {json.dumps(value, ensure_ascii=False)}' for value in values)
    return f'[\n{body}\n      ]'


def rebuild_from_git_head_preserving_format() -> tuple[dict, list[str]]:
    raw = subprocess.check_output(
        ['git', 'show', 'HEAD:data/map.json'], cwd=ROOT, text=True, encoding='utf-8'
    )
    original = json.loads(raw)
    target = copy.deepcopy(original)
    target['movement_rules'] = {
        'road_range': 1,
        'rail_range': 3,
        'move_cost': 1,
        'wall_crossing_range': 1,
        'wall_crossing_cost': 2,
    }
    changes = normalize_topology(target)

    movement_text = json.dumps(target['movement_rules'], ensure_ascii=False, indent=4)
    movement_text = movement_text.replace('\n', '\n  ')
    raw = re.sub(
        r'  "movement_rules": \{.*?\n  \},',
        f'  "movement_rules": {movement_text},',
        raw,
        count=1,
        flags=re.DOTALL,
    )

    town_pattern = re.compile(
        r'(^    "(?P<name>[^"]+)": \{[ \t]*\n)(?P<body>.*?)(?=^    "[^"]+": \{[ \t]*$|^  \}\n\})',
        flags=re.MULTILINE | re.DOTALL,
    )

    def update_town(match: re.Match[str]) -> str:
        name = match.group('name')
        body = match.group('body')
        for mode in ('road', 'rail'):
            original_values = original['towns'][name].get(mode, [])
            target_values = target['towns'][name].get(mode, [])
            if original_values == target_values:
                continue
            field_pattern = re.compile(rf'(      "{mode}": )(\[[^\]]*\])')
            field_match = field_pattern.search(body)
            if not field_match:
                raise RuntimeError(f'Could not locate {name}.{mode} array')
            replacement = field_match.group(1) + render_array_like(field_match.group(2), target_values)
            body = body[:field_match.start()] + replacement + body[field_match.end():]
        return match.group(1) + body

    raw = town_pattern.sub(update_town, raw)
    rendered = json.loads(raw)
    if rendered != target:
        differences = []
        if rendered.get('movement_rules') != target.get('movement_rules'):
            differences.append(f"movement_rules={rendered.get('movement_rules')!r}")
        for name, expected in target['towns'].items():
            actual = rendered['towns'].get(name)
            if actual != expected:
                differences.append(f'{name}: actual={actual!r}, expected={expected!r}')
                if len(differences) >= 5:
                    break
        raise RuntimeError(f"Preserving-format map rewrite did not match normalized data: {'; '.join(differences)}")
    MAP_PATH.write_text(raw, encoding='utf-8')
    return target, changes


def render_geo_coordinates(geo: dict[str, list[float]]) -> str:
    rows = [
        f'  {json.dumps(name, ensure_ascii=False)}: {json.dumps(coords, ensure_ascii=False, separators=(",", ":"))}'
        for name, coords in geo.items()
    ]
    return '{\n' + ',\n'.join(rows) + '\n}\n'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-git-head', action='store_true', help='rebuild from HEAD while preserving its formatting')
    args = parser.parse_args()
    if args.from_git_head:
        data, changes = rebuild_from_git_head_preserving_format()
    else:
        data = json.loads(MAP_PATH.read_text(encoding='utf-8'))
        changes = normalize_topology(data)
    geo = load_or_extract_geo_coordinates()
    missing_geo = sorted(set(data['towns']) - set(geo))
    extra_geo = sorted(set(geo) - set(data['towns']))
    if missing_geo or extra_geo:
        raise RuntimeError(f'Geo coverage mismatch: missing={missing_geo}, extra={extra_geo}')
    if not args.from_git_head:
        MAP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    GEO_PATH.write_text(render_geo_coordinates(geo), encoding='utf-8')
    print(json.dumps({'topology_changes': len(changes), 'towns': len(data['towns']), 'changes': changes}, ensure_ascii=False))


if __name__ == '__main__':
    main()
