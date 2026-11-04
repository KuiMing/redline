#!/usr/bin/env bash
# 建置未簽署的 REDLINE.app 與 REDLINE-<version>-macOS-arm64.dmg（僅限 Apple Silicon）。
#
#   packaging/macos/build.sh
#
# 輸出：dist/REDLINE.app、dist/REDLINE-<version>-macOS-arm64.dmg（含 .sha256）。
# 相依由 uv 依 uv.lock 安裝到 build/macos/venv，不影響專案的 .venv，也不需要全域 pip。
set -euo pipefail

# 實際測試過的工具版本。CPython 只用 uv 管理的建置，不採用系統上碰巧存在的 Python。
REQUIRED_UV_VERSION="0.11.8"
REQUIRED_PYTHON_VERSION="3.11.15"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "error: 需要 Apple Silicon（arm64）macOS，目前為 $(uname -s) $(uname -m)" >&2
  exit 1
fi

BUILD_DIR="$ROOT/build/macos"
DIST_DIR="$ROOT/dist"
export UV_PROJECT_ENVIRONMENT="$BUILD_DIR/venv"

UV_ACTUAL_VERSION="$(uv --version | awk '{print $2}')"
if [[ "$UV_ACTUAL_VERSION" != "$REQUIRED_UV_VERSION" ]]; then
  echo "error: 需要 uv $REQUIRED_UV_VERSION，目前為 $UV_ACTUAL_VERSION" >&2
  exit 1
fi
export UV_PYTHON="$REQUIRED_PYTHON_VERSION"
export UV_PYTHON_PREFERENCE="only-managed"

echo "==> 安裝打包相依（uv.lock，--frozen）"
uv sync --frozen --no-dev --group macos-app
PYTHON="$UV_PROJECT_ENVIRONMENT/bin/python"

PYTHON_ACTUAL_VERSION="$("$PYTHON" -c 'import platform; print(platform.python_version())')"
PYTHON_ACTUAL_ARCH="$("$PYTHON" -c 'import platform; print(platform.machine())')"
echo "uv $UV_ACTUAL_VERSION, CPython $PYTHON_ACTUAL_VERSION ($PYTHON_ACTUAL_ARCH), macOS $(sw_vers -productVersion)"
if [[ "$PYTHON_ACTUAL_VERSION" != "$REQUIRED_PYTHON_VERSION" || "$PYTHON_ACTUAL_ARCH" != "arm64" ]]; then
  echo "error: 需要 arm64 CPython $REQUIRED_PYTHON_VERSION" >&2
  exit 1
fi

echo "==> 檢查第三方授權聲明"
"$PYTHON" packaging/macos/generate_third_party_notices.py --check

VERSION="$("$PYTHON" -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
DMG_NAME="REDLINE-$VERSION-macOS-arm64.dmg"
echo "==> REDLINE $VERSION"

echo "==> 產生 App 圖示"
ICON_WORK="$BUILD_DIR/icon"
rm -rf "${ICON_WORK:?}"
mkdir -p "$ICON_WORK/REDLINE.iconset"
"$PYTHON" packaging/macos/generate_icon.py static/war_title.png "$ICON_WORK/base.png"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ICON_WORK/base.png" --out "$ICON_WORK/REDLINE.iconset/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$ICON_WORK/base.png" --out "$ICON_WORK/REDLINE.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICON_WORK/REDLINE.iconset" -o "$ICON_WORK/REDLINE.icns"
export REDLINE_APP_ICON="$ICON_WORK/REDLINE.icns"

echo "==> PyInstaller"
rm -rf "${DIST_DIR:?}/REDLINE.app" "${DIST_DIR:?}/${DMG_NAME:?}" "${DIST_DIR:?}/${DMG_NAME:?}.sha256"
mkdir -p "$DIST_DIR"
"$PYTHON" -m PyInstaller --noconfirm --clean \
  --distpath "$BUILD_DIR/pyinstaller-dist" --workpath "$BUILD_DIR/pyinstaller-work" \
  packaging/macos/REDLINE.spec
"$PYTHON" packaging/macos/generate_third_party_notices.py --check-bundle "$BUILD_DIR/pyinstaller-work/REDLINE/PYZ-00.toc"
# ditto 保留簽章與 symlink。
ditto "$BUILD_DIR/pyinstaller-dist/REDLINE.app" "$DIST_DIR/REDLINE.app"
APP="$DIST_DIR/REDLINE.app"

echo "==> 驗證 .app"
[[ "$(lipo -archs "$APP/Contents/MacOS/REDLINE")" == "arm64" ]] || { echo "error: 主程式不是 arm64" >&2; exit 1; }
# 只有 ad-hoc 簽章（arm64 核心的最低要求），不是開發者簽署。
codesign --verify --deep --strict "$APP"

echo "==> 建立 DMG（hdiutil）"
STAGE="$BUILD_DIR/dmg-stage"
rm -rf "${STAGE:?}"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/REDLINE.app"
ln -s /Applications "$STAGE/Applications"
cp packaging/macos/DMG-README.txt "$STAGE/請先閱讀.txt"
cp LICENSE.md LICENSE-CODE packaging/macos/THIRD-PARTY-NOTICES.txt "$STAGE/"
hdiutil create -volname "REDLINE $VERSION" -srcfolder "$STAGE" -ov -fs HFS+ -format UDZO "$DIST_DIR/$DMG_NAME"
hdiutil verify "$DIST_DIR/$DMG_NAME" >/dev/null
(cd "$DIST_DIR" && shasum -a 256 "$DMG_NAME" > "$DMG_NAME.sha256")

echo "==> 完成"
du -sh "$APP" "$DIST_DIR/$DMG_NAME"
echo "$APP"
echo "$DIST_DIR/$DMG_NAME"
