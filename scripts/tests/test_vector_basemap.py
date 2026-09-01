from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOGIC = (ROOT / "static" / "leaflet_game_map_logic.js").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "leaflet_game_map.html").read_text(encoding="utf-8")


def test_basemap_uses_openfreemap_vector_tiles_without_raster_osm_or_carto():
    assert "https://tiles.openfreemap.org/styles/liberty" in LOGIC
    assert "L.maplibreGL" in LOGIC
    assert "tile.openstreetmap.org" not in LOGIC
    assert "basemaps.cartocdn.com" not in LOGIC
    assert "https://openfreemap.org" in LOGIC
    assert "https://openmaptiles.org" in LOGIC
    assert "https://www.openstreetmap.org/copyright" in LOGIC


def test_basemap_removes_symbols_labels_pois_and_minor_detail():
    assert "minimalRedlineBasemapStyle" in LOGIC
    assert "layer.type !== 'symbol'" in LOGIC
    assert "REDLINE_VECTOR_BASEMAP_LAYER_IDS" in LOGIC
    assert "label_city" not in LOGIC
    assert "poi_r1" not in LOGIC


def test_basemap_draws_visible_coastline_and_dark_land_contrast():
    assert "paint['background-color'] = '#343841'" in LOGIC
    assert "paint['raster-opacity'] = 0.04" in LOGIC
    assert "paint['fill-color'] = '#071522'" in LOGIC
    assert "paint['fill-outline-color'] = '#6f87a8'" in LOGIC


def test_basemap_loads_pinned_maplibre_leaflet_dependencies():
    assert "maplibre-gl@5.7.1/dist/maplibre-gl.css" in HTML
    assert "maplibre-gl@5.7.1/dist/maplibre-gl.js" in HTML
    assert "@maplibre/maplibre-gl-leaflet@0.1.3/leaflet-maplibre-gl.js" in HTML


def test_basemap_falls_back_to_dark_background_on_vector_error():
    assert "handleBasemapError" in LOGIC
    assert "map.removeLayer(vectorBasemap)" in LOGIC
    assert "redline-basemap-unavailable" in LOGIC
    assert "redline-basemap-unavailable" in HTML


def test_basemap_exposes_readiness_for_browser_proof():
    assert "if (!map._loaded)" in LOGIC
    assert "window.__redlineBasemapReady" in LOGIC
    assert "leaflet_game_map_logic.js?v=minimal-vector-basemap-20260901" in HTML
