import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOGIC = (ROOT / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "leaflet_game_map.html").read_text(encoding="utf-8")
VENDOR_HASHES = {
    "static/vendor/maplibre-gl/5.7.1/maplibre-gl.js": "aa49ba072cb2d4621c365e501867cbc0ffead0d4a42dd79cb8f182525082451a",
    "static/vendor/maplibre-gl/5.7.1/maplibre-gl.css": "43c1d886b5fdf0aac4e7135bd6f84b823d9f48283a648012665f9be52c01389f",
    "static/vendor/maplibre-gl-leaflet/0.1.3/leaflet-maplibre-gl.js": "1c33367962e7755c1a16d1f85658fdc96b5baa36f81adfca9493174cd1b526ce",
}


def test_basemap_uses_openfreemap_vector_tiles_without_raster_osm_or_carto():
    assert "https://tiles.openfreemap.org/styles/liberty" in LOGIC
    assert "L.maplibreGL" in LOGIC
    assert "tile.openstreetmap.org" not in LOGIC
    assert "basemaps.cartocdn.com" not in LOGIC
    assert "https://openfreemap.org" in LOGIC
    assert "https://openmaptiles.org" in LOGIC
    assert "https://www.openstreetmap.org/copyright" in LOGIC


def test_basemap_removes_symbols_and_unused_style_metadata():
    assert "minimalRedlineBasemapStyle" in LOGIC
    assert "layer.type !== 'symbol'" in LOGIC
    assert "REDLINE_VECTOR_BASEMAP_LAYER_IDS" in LOGIC
    assert "delete style.sprite" in LOGIC
    assert "delete style.glyphs" in LOGIC
    assert "label_city" not in LOGIC
    assert "poi_r1" not in LOGIC


def test_basemap_requires_core_upstream_style_layers():
    assert "REQUIRED_REDLINE_VECTOR_BASEMAP_LAYER_IDS" in LOGIC
    assert "OpenFreeMap style missing required layers" in LOGIC


def test_basemap_draws_visible_coastline_and_dark_land_contrast():
    assert "paint['background-color'] = '#343841'" in LOGIC
    assert "paint['raster-opacity'] = 0.04" in LOGIC
    assert "paint['fill-color'] = '#071522'" in LOGIC
    assert "paint['fill-outline-color'] = '#6f87a8'" in LOGIC


def test_basemap_self_hosts_pinned_dependencies_and_licenses():
    assert "/static/vendor/maplibre-gl/5.7.1/maplibre-gl.css" in HTML
    assert "/static/vendor/maplibre-gl/5.7.1/maplibre-gl.js" in HTML
    assert "/static/vendor/maplibre-gl-leaflet/0.1.3/leaflet-maplibre-gl.js" in HTML
    assert "unpkg.com/maplibre" not in HTML
    assert "unpkg.com/@maplibre" not in HTML
    assert (ROOT / "static/vendor/maplibre-gl/5.7.1/LICENSE.txt").is_file()
    assert (ROOT / "static/vendor/maplibre-gl-leaflet/0.1.3/LICENSE").is_file()
    for path, expected_hash in VENDOR_HASHES.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected_hash


def test_basemap_handles_initial_runtime_and_timeout_failures():
    assert "BASEMAP_LOAD_TIMEOUT_MS" in LOGIC
    assert "AbortController" in LOGIC
    assert "waitForVectorMapLoad" in LOGIC
    assert "vectorMap.on('error'" in LOGIC
    assert "handleBasemapError()" in LOGIC
    assert "map.removeLayer(vectorBasemap)" in LOGIC
    assert "redline-basemap-unavailable" in LOGIC
    assert "redline-basemap-unavailable" in HTML


def test_basemap_exposes_readiness_for_browser_proof():
    assert "waitForLeafletMapLoad" in LOGIC
    assert "window.__redlineBasemapReady" in LOGIC
    assert "leaflet_game_map_logic.js?v=minimal-vector-basemap-20260901" in HTML
