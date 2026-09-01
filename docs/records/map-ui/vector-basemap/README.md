# Minimal Vector Basemap

日期：2026-09-01

## 功能

Leaflet 遊戲地圖使用 OpenFreeMap vector tiles，並透過 MapLibre GL Leaflet 顯示底圖。現有城鎮、道路、鐵路、組織、選取與合法行動 overlay 維持 Leaflet 實作。

底圖只保留：

- 陸地與水域
- 海岸線
- 行政邊界
- 主要道路

底圖移除全部 `symbol` layers，因此不顯示 OSM 地名、POI、設施、交通圖示與道路名稱。

## 視覺設定

- 陸地：`#343841`
- 水域：`#071522`
- 海岸線：`#6f87a8`
- Natural Earth relief opacity：`0.04`

此設定維持暗色盤面，並提高深色城鎮圓圈與陸地的對比。

## 依賴與 attribution

- MapLibre GL JS `5.7.1`
- MapLibre GL Leaflet `0.1.3`
- OpenFreeMap style：`https://tiles.openfreemap.org/styles/liberty`
- Attribution：OpenFreeMap、OpenMapTiles、OpenStreetMap contributors

OpenFreeMap 公共服務沒有納入 Redline 的可用性保證。正式部署應保留現有 dark fallback，並依實際流量評估公共服務或自行託管。

## 驗證

執行：

```bash
ENABLE_TEST_ROUTES=1 uv run uvicorn server.main:app --host 127.0.0.1 --port 8781
PYTHONPATH=. uv run python scripts/validate/validate_vector_basemap.py
```

驗證範圍：

- 1280×720
- 1024×768
- 香港 zoom 11
- runtime symbol layer 數量為 0
- OpenFreeMap/OpenStreetMap attribution
- Redline overlay canvas
- 無 `API KEY REQUIRED`
- console 無 JavaScript error
- vector error dark fallback
- town marker interaction remains functional with the MapLibre canvas present

Latest evidence:

- Browser proof：**24/24 passed**
- Focused basemap/map route tests：**10 passed**
- Broad pytest（excluding the pre-existing live websocket script `scripts/tests/test_ws_flow.py`）：**1005 passed**
