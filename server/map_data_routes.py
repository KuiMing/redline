"""Static map-data routes used by the game and map proof page."""

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent


@router.get("/town-coordinates")
def get_town_coordinates():
    path = BASE_DIR / "data" / "town_coordinates.v1.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@router.get("/map-test")
def map_test():
    return FileResponse("static/map_test.html")


@router.get("/map-geo-coordinates")
def get_map_geo_coordinates():
    path = BASE_DIR / "data" / "map_geo_coordinates.v1.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@router.get("/map-data")
def get_map_data():
    path = BASE_DIR / "data" / "map.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)
