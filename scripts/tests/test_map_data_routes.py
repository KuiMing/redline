import json
from pathlib import Path

from fastapi.testclient import TestClient

from server import main
from server.map_data_routes import (
    BASE_DIR,
    get_map_data,
    get_map_geo_coordinates,
    get_town_coordinates,
    map_test,
    router as map_data_router,
)


MAP_ENDPOINTS = {
    "/town-coordinates": BASE_DIR / "data" / "town_coordinates.v1.json",
    "/map-geo-coordinates": BASE_DIR / "data" / "map_geo_coordinates.v1.json",
    "/map-data": BASE_DIR / "data" / "map.json",
}


def test_map_data_routes_return_canonical_json_payloads():
    client = TestClient(main.app)

    for route, path in MAP_ENDPOINTS.items():
        with path.open(encoding="utf-8") as f:
            expected = json.load(f)
        response = client.get(route)
        assert response.status_code == 200
        assert response.json() == expected


def test_map_test_route_returns_existing_static_page():
    response = TestClient(main.app).get("/map-test")

    assert response.status_code == 200
    assert "<title>Map Test</title>" in response.text
    assert Path("static/map_test.html").exists()


def test_main_keeps_map_route_compatibility_exports():
    assert main.get_town_coordinates is get_town_coordinates
    assert main.get_map_geo_coordinates is get_map_geo_coordinates
    assert main.get_map_data is get_map_data
    assert main.map_test is map_test


def test_each_map_route_is_registered_once():
    router_paths = [getattr(route, "path", None) for route in map_data_router.routes]
    app_paths = [getattr(route, "path", None) for route in main.app.routes]

    for path in [*MAP_ENDPOINTS, "/map-test"]:
        assert router_paths.count(path) == 1
    assert app_paths.count("/test/set-hand") == 1
