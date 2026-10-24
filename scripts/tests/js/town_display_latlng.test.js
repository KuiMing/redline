// node --test scripts/tests/js/town_display_latlng.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const src = fs.readFileSync(path.join(__dirname, '../../../static/leaflet_game_map_logic.js'), 'utf8');
const match = src.match(/function townDisplayLatLng\(town\) \{[\s\S]*?\n\}\n/);

function build(mapOverrides = {}) {
  const L = {
    latLng: (lat, lon) => ({ lat, lng: lon }),
    point: (x, y) => ({ x, y }),
  };
  const map = {
    _loaded: true,
    latLngToLayerPoint: (ll) => ({ x: ll.lng * 10, y: ll.lat * 10 }),
    layerPointToLatLng: (p) => ({ lat: p.y / 10, lng: p.x / 10 }),
    ...mapOverrides,
  };
  return new Function('L', 'map', `${match[0]}; return townDisplayLatLng;`)(L, map);
}
const town = (name) => ({ name, lat: 50, lon: 127 });

test('townDisplayLatLng source is extractable', () => assert.ok(match));

test('normal projection keeps the pixel offsets for 黑河/海蘭泡/臥龍', () => {
  const f = build();
  assert.deepEqual(f(town('黑河')), { lat: 51.2, lng: 127 });
  assert.deepEqual(f(town('臥龍')), { lat: 51.2, lng: 127 });
  assert.deepEqual(f(town('海蘭泡')), { lat: 48.8, lng: 127 });
});

test('other towns and unloaded maps return the raw latLng', () => {
  assert.deepEqual(build()(town('臺北')), { lat: 50, lng: 127 });
  assert.deepEqual(build({ _loaded: false })(town('黑河')), { lat: 50, lng: 127 });
});

test('non-finite projections fall back to the raw latLng (no NaN LatLng)', () => {
  for (const bad of [{ x: NaN, y: NaN }, { x: 1, y: Infinity }, { x: undefined, y: 3 }, null]) {
    const f = build({ latLngToLayerPoint: () => bad });
    assert.deepEqual(f(town('黑河')), { lat: 50, lng: 127 });
  }
  const f = build({ layerPointToLatLng: () => ({ lat: NaN, lng: NaN }) });
  assert.deepEqual(f(town('海蘭泡')), { lat: 50, lng: 127 });
});
