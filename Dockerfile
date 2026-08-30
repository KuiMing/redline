# syntax=docker/dockerfile:1

FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# pyproject.toml / uv.lock 釘住執行期相依套件版本（fastapi、uvicorn[standard]、
# websockets）；--no-dev 略過 pytest/playwright 這類開發用相依。
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 只複製執行期真正需要的東西：server/（遊戲邏輯與 WebSocket/API）、static/
# （前端與地圖 UI，含 app.mount("/static", ...)）、data/（卡牌／城鎮／陣營／地圖資料）。
# scripts/、docs/、sketches/ 是開發與驗證用（見 README.md「資料夾結構」），不需要進 image。
COPY server/ ./server/
COPY static/ ./static/
COPY data/ ./data/

EXPOSE 8000

# 房間與遊戲狀態存在單一 Python process 的記憶體中（README.md 明講），
# 因此只能跑單一 worker，不能用多 worker 或多副本橫向擴充。
CMD ["uv", "run", "--no-dev", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
