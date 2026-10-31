# Joy-Con bridge image。FTCW（Finally the Controller Works）與 Bluetooth 留在 macOS host，
# 容器內的 bridge 以 UDP 連到 host.docker.internal。從 repo 根目錄 build：
#
#   docker build -f tools/joycon_bridge/Dockerfile -t redline-joycon-bridge .
#
# 只複製 tools/（bridge 本體）與共用的 pyproject.toml/uv.lock（fastapi、
# uvicorn[standard]、websockets 版本），不含 server/、static/、data/，也不安裝 dev 相依。

FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY tools/__init__.py ./tools/__init__.py
COPY tools/joycon_bridge/ ./tools/joycon_bridge/

# 容器內綁 0.0.0.0 才能被 Docker port mapping 轉進來；docker-compose.yml 只把
# host port 發布到 127.0.0.1。
EXPOSE 8000

CMD ["uv", "run", "--no-dev", "python", "-m", "tools.joycon_bridge", "--bind-host", "0.0.0.0", "--port", "8000"]
