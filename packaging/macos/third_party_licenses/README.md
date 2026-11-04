# 第三方授權原文

`packaging/macos/generate_third_party_notices.py` 會把這裡的檔案併入 `THIRD-PARTY-NOTICES.txt`。只放「wheel 或直譯器本身沒有附上」的授權原文；其他的直接從安裝的套件讀取。行尾空白已移除，內容未改寫。

| 檔案 | 來源 |
| --- | --- |
| `python-standalone.*.txt`、`python-build-standalone.txt` | `astral-sh/python-build-standalone`，tag `20260414`（uv 0.11.8 的 CPython 3.11.15 建置） |
| `pyobjc.txt` | `ronaldoussoren/pyobjc`，tag `v13.0`，`pyobjc-core/License.txt` |
| `proxy_tools.txt` | `jtushman/proxy_tools`，branch `master`，`LICENSE.txt`（該專案沒有 tag） |
| `libuv.txt` | `libuv/libuv`，branch `v1.x`，`LICENSE`（uvloop 靜態連結） |
