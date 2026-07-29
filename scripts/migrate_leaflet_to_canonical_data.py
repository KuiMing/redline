#!/usr/bin/env python3
"""Remove embedded Leaflet map snapshots and load canonical server data instead."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'static'

DERIVED_OLD = """const rulers = [...new Set(Object.values(MAP_DATA.towns).flatMap(t=>t.ruler||[]))].sort();
const camps = [...new Set(Object.values(MAP_DATA.towns).flatMap(t=>t.camp||[]))].sort();
const types = [...new Set(Object.values(MAP_DATA.towns).map(t=>t.type).filter(Boolean))].sort();"""
DERIVED_NEW = """let rulers = [];
let camps = [];
let types = [];"""

TOPOLOGY_OLD = """addOptions('rulerFilter', rulers); addOptions('campFilter', camps); addOptions('typeFilter', types);

const towns = Object.entries(MAP_DATA.towns).map(([name, raw]) => {
  const c = GEO_COORDS[name];
  return { name, ...raw, lon:c[0], lat:c[1] };
});
const byName = new Map(towns.map(t=>[t.name, t]));

function canonicalEdgeKey(a,b,type) {
  return [type, ...[a,b].sort()].join('::');
}
const linkMap = new Map();
for (const [name,t] of Object.entries(MAP_DATA.towns)) {
  for (const n of (t.road||[])) if (MAP_DATA.towns[n]) linkMap.set(canonicalEdgeKey(name,n,'road'), {source:name,target:n,type:'road'});
  for (const n of (t.rail||[])) if (MAP_DATA.towns[n]) linkMap.set(canonicalEdgeKey(name,n,'rail'), {source:name,target:n,type:'rail'});
}
const links = [...linkMap.values()];"""

TOPOLOGY_NEW = """let towns = [];
let byName = new Map();
let links = [];

function canonicalEdgeKey(a,b,type) {
  return [type, ...[a,b].sort()].join('::');
}

function initializeCanonicalMapData(mapData, geoCoordinates) {
  MAP_DATA = mapData;
  GEO_COORDS = geoCoordinates;
  rulers = [...new Set(Object.values(MAP_DATA.towns).flatMap(t=>t.ruler||[]))].sort();
  camps = [...new Set(Object.values(MAP_DATA.towns).flatMap(t=>t.camp||[]))].sort();
  types = [...new Set(Object.values(MAP_DATA.towns).map(t=>t.type).filter(Boolean))].sort();
  addOptions('rulerFilter', rulers);
  addOptions('campFilter', camps);
  addOptions('typeFilter', types);
  towns = Object.entries(MAP_DATA.towns).map(([name, raw]) => {
    const c = GEO_COORDS[name];
    return { name, ...raw, lon:c[0], lat:c[1] };
  });
  byName = new Map(towns.map(t=>[t.name, t]));
  const linkMap = new Map();
  for (const [name,t] of Object.entries(MAP_DATA.towns)) {
    for (const n of (t.road||[])) if (MAP_DATA.towns[n]) linkMap.set(canonicalEdgeKey(name,n,'road'), {source:name,target:n,type:'road'});
    for (const n of (t.rail||[])) if (MAP_DATA.towns[n]) linkMap.set(canonicalEdgeKey(name,n,'rail'), {source:name,target:n,type:'rail'});
  }
  links = [...linkMap.values()];
  currentVisible = towns.map(t=>t.name);
}"""


def strip_snapshots(text: str) -> str:
    lines = text.splitlines()
    if not lines[0].startswith('const MAP_DATA = ') or not lines[1].startswith('const GEO_COORDS = '):
        raise RuntimeError('Expected embedded MAP_DATA/GEO_COORDS at file start')
    return 'let MAP_DATA = null;\nlet GEO_COORDS = null;\n' + '\n'.join(lines[2:]) + '\n'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f'{label}: expected one match, found {text.count(old)}')
    return text.replace(old, new, 1)


def migrate_game_logic() -> None:
    path = STATIC / 'leaflet_game_map_logic.js'
    text = strip_snapshots(path.read_text(encoding='utf-8'))
    text = replace_once(text, DERIVED_OLD, DERIVED_NEW, 'game derived data')
    text = replace_once(text, TOPOLOGY_OLD, TOPOLOGY_NEW, 'game topology')
    text = replace_once(
        text,
        """renderMap();
setTimeout(focusAsia, 100);
loadFactionMeta();""",
        """async function bootstrapCanonicalGameMap() {
  const bundle = await window.loadRedlineMapBundle();
  initializeCanonicalMapData(bundle.mapData, bundle.geoCoordinates);
  renderMap();
  if (lastGameState) applyGameStateToMap(lastGameState);
  setTimeout(focusAsia, 100);
  await loadFactionMeta();
  return { towns: towns.length, links: links.length };
}

window.__redlineMapDataReady = bootstrapCanonicalGameMap().catch(error => {
  console.error('Failed to initialize canonical Redline map data', error);
  const hint = document.getElementById('interactionHint');
  if (hint) hint.textContent = `地圖資料載入失敗：${error.message}`;
  throw error;
});""",
        'game bootstrap',
    )
    path.write_text(text, encoding='utf-8')


def migrate_embed_logic() -> None:
    path = STATIC / 'leaflet_embed_logic.js'
    text = strip_snapshots(path.read_text(encoding='utf-8'))
    text = replace_once(text, DERIVED_OLD, DERIVED_NEW, 'embed derived data')
    text = replace_once(text, TOPOLOGY_OLD.replace("addOptions('rulerFilter', rulers); addOptions('campFilter', camps); addOptions('typeFilter', types);\n\n", ''), TOPOLOGY_NEW, 'embed topology')
    text = replace_once(
        text,
        """window.initializeStrategicMapWhenVisible = function () {
  if (!document.getElementById('map')) return;

  if (!window.__redlineMapControlsBound) {""",
        """window.initializeStrategicMapWhenVisible = async function () {
  if (!document.getElementById('map')) return;
  if (!MAP_DATA) {
    const bundle = await window.loadRedlineMapBundle();
    initializeCanonicalMapData(bundle.mapData, bundle.geoCoordinates);
  }

  if (!window.__redlineMapControlsBound) {""",
        'embed initializer',
    )
    path.write_text(text, encoding='utf-8')


def migrate_full_map() -> None:
    path = STATIC / 'leaflet_full_map.html'
    text = path.read_text(encoding='utf-8')
    marker = '<script>\nconst MAP_DATA = '
    start = text.find(marker)
    if start < 0:
        raise RuntimeError('full map embedded script start not found')
    end = text.find('</script>', start)
    if end < 0:
        raise RuntimeError('full map embedded script end not found')
    replacement = """<script src="/static/map_data_loader.js?v=map-ssot-20260729"></script>
<script src="/static/leaflet_embed_logic.js?v=map-ssot-20260729"></script>
<script>
window.initializeStrategicMapWhenVisible().catch(error => {
  console.error('Failed to initialize standalone map', error);
});
</script>"""
    text = text[:start] + replacement + text[end + len('</script>'):]
    path.write_text(text, encoding='utf-8')


def add_loader_to_game_map() -> None:
    path = STATIC / 'leaflet_game_map.html'
    text = path.read_text(encoding='utf-8')
    old = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>\n<script src="/static/leaflet_game_map_logic.js?v=playtest-batch2-20260729"></script>'
    new = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>\n<script src="/static/map_data_loader.js?v=map-ssot-20260729"></script>\n<script src="/static/leaflet_game_map_logic.js?v=map-ssot-20260729"></script>'
    text = replace_once(text, old, new, 'game map loader tags')
    path.write_text(text, encoding='utf-8')


def main() -> None:
    game_logic = (STATIC / 'leaflet_game_map_logic.js').read_text(encoding='utf-8')
    if 'const MAP_DATA =' not in game_logic and 'const GEO_COORDS =' not in game_logic:
        print('Leaflet maps already use canonical server data; no migration needed')
        return
    migrate_game_logic()
    migrate_embed_logic()
    migrate_full_map()
    add_loader_to_game_map()
    print('Migrated Leaflet maps to canonical /map-data and /map-geo-coordinates')


if __name__ == '__main__':
    main()
