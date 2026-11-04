# PyInstaller spec for REDLINE.app（由 packaging/macos/build.sh 呼叫）。
#
# onedir + BUNDLE：啟動快、容易檢查，且同一個執行檔可重新啟動自己作為 server／bridge 子行程。
import os
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parents[1]
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
ICON = os.environ.get("REDLINE_APP_ICON") or None

# 只打包執行期資源，與 Dockerfile 的 COPY 清單對應；scripts/、docs/ 不進 App。
datas = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "data"), "data"),
    (str(ROOT / "rules.md"), "."),
    (str(ROOT / "LICENSE.md"), "."),
    (str(ROOT / "LICENSE-CODE"), "."),
    (str(ROOT / "packaging/macos/THIRD-PARTY-NOTICES.txt"), "."),
]

# uvicorn 以字串動態載入 protocol／loop 實作；server、red_army_policy 明確列入以防延遲 import 被漏掉。
# mcp_server 只取遊戲 server 用到的兩個模組：整包會把不需要的 mcp SDK 帶進 App。
hiddenimports = [
    *collect_submodules("uvicorn"),
    *collect_submodules("server"),
    *collect_submodules("red_army_policy"),
    *collect_submodules("tools.joycon_bridge"),
    "mcp_server.summarize",
    "mcp_server.rules_data",
]

a = Analysis(
    [str(ROOT / "packaging/macos/entry.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    # pywebview 其他平台的後端與開發用套件。cryptography 只有 pywebview 的選用 SSL 功能才用到
    # （App 走 http://127.0.0.1），排除可避免多帶一份 OpenSSL。
    excludes=[
        "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy", "gi", "clr", "cefpython3", "pytest", "playwright", "mcp",
        "cryptography", "cffi", "pycparser", "jwt",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="REDLINE",
    console=False,
    target_arch="arm64",
    # 不簽署憑證：arm64 核心要求至少 ad-hoc 簽章，PyInstaller 會自動處理。
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="REDLINE")
app = BUNDLE(
    coll,
    name="REDLINE.app",
    icon=ICON,
    bundle_identifier="io.github.kuiming.redline",
    version=VERSION,
    info_plist={
        "CFBundleName": "REDLINE",
        "CFBundleDisplayName": "REDLINE",
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "LSApplicationCategoryType": "public.app-category.board-games",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        # 遊戲頁面與 Joy-Con WebSocket 都是 http／ws 到 loopback。
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        "NSHumanReadableCopyright": "程式碼 MIT；《逆統戰：致地與海的革命者》原作內容屬 ESC Taiwan／原著作權人，僅限非商用。",
    },
)
