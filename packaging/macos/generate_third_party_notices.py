#!/usr/bin/env python3
"""產生 THIRD-PARTY-NOTICES.txt。用打包環境的 Python 執行（build/macos/venv/bin/python）。

    generate_third_party_notices.py --write   # 相依變更並人工審閱授權後更新
    generate_third_party_notices.py --check   # build.sh 使用：內容不一致就失敗

REVIEWED 是人工審閱過的清單。新增套件、或套件沒有可用的授權原文時都會失敗，
必須有人看過授權後才能加入，不會默默把未審閱的相依打包出去。
"""

from __future__ import annotations

import argparse
import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "packaging/macos/THIRD-PARTY-NOTICES.txt"
LICENSES = ROOT / "packaging/macos/third_party_licenses"
SEPARATOR = "=" * 78

# 正規化名稱 → 審閱後的授權。
REVIEWED = {
    "altgraph": "MIT",
    "annotated-doc": "MIT",
    "annotated-types": "MIT",
    "anyio": "MIT",
    "attrs": "MIT",
    "bottle": "MIT",
    "cffi": "MIT-0",
    "click": "BSD-3-Clause",
    "cryptography": "Apache-2.0 OR BSD-3-Clause",
    "fastapi": "MIT",
    "h11": "MIT",
    "httpcore2": "BSD-3-Clause",
    "httptools": "MIT（內含 http-parser、llhttp，皆 MIT）",
    "httpx2": "BSD-3-Clause",
    "idna": "BSD-3-Clause",
    "jsonschema": "MIT",
    "jsonschema-specifications": "MIT",
    "macholib": "MIT",
    "mcp": "MIT",
    "mcp-types": "MIT",
    "opentelemetry-api": "Apache-2.0",
    "packaging": "Apache-2.0 OR BSD-2-Clause",
    "proxy-tools": "BSD（依上游 LICENSE.txt；套件 metadata 標示 MIT）",
    "pycparser": "BSD-3-Clause",
    "pydantic": "MIT",
    "pydantic-core": "MIT",
    "pyinstaller": "GPL-2.0-or-later WITH Bootloader-exception（App 只含 bootloader 與 runtime hooks，適用例外條款）",
    "pyinstaller-hooks-contrib": "Apache-2.0 / GPL-2.0-or-later（僅建置時使用；runtime hooks 為 Apache-2.0）",
    "pyjwt": "MIT",
    "pyobjc-core": "MIT",
    "pyobjc-framework-cocoa": "MIT",
    "pyobjc-framework-quartz": "MIT",
    "pyobjc-framework-security": "MIT",
    "pyobjc-framework-uniformtypeidentifiers": "MIT",
    "pyobjc-framework-webkit": "MIT",
    "python-dotenv": "BSD-3-Clause",
    "python-multipart": "Apache-2.0",
    "pywebview": "BSD-3-Clause",
    "pyyaml": "MIT",
    "referencing": "MIT",
    "rpds-py": "MIT",
    "setuptools": "MIT（內含多個 vendored 套件，授權同列於下）",
    "sse-starlette": "BSD-3-Clause",
    "starlette": "BSD-3-Clause",
    "truststore": "MIT",
    "typing-extensions": "PSF-2.0",
    "typing-inspection": "MIT",
    "uvicorn": "BSD-3-Clause",
    "uvloop": "Apache-2.0 OR MIT（靜態連結 libuv，見「其他元件」）",
    "watchfiles": "MIT",
    "websockets": "BSD-3-Clause",
}

# 套件內 vendored 的元件（巢狀 .dist-info）。正規化名稱 → 審閱後的授權。
REVIEWED_VENDORED = {
    "autocommand": "LGPL-3.0",
    "backports-tarfile": "MIT",
    "importlib-metadata": "Apache-2.0",
    "jaraco-context": "MIT",
    "jaraco-functools": "MIT",
    "jaraco-text": "MIT",
    "more-itertools": "MIT",
    "packaging": "Apache-2.0 OR BSD-2-Clause",
    "platformdirs": "MIT",
    "tomli": "MIT",
    "wheel": "MIT",
    "zipp": "MIT",
}

# 只把授權宣告留在檔案內的第三方 JS（App 會打包這些檔案）。
EMBEDDED_ATTRIBUTION_FILES = re.compile(r"^webview/js/lib/[^/]+\.js$")
ATTRIBUTION_LINE = re.compile(r"licen[cs]e|copyright|\(c\)", re.IGNORECASE)

LICENSE_FILE_NAME = re.compile(r"(licen[cs]e|copying|notice|authors)", re.IGNORECASE)
TEXT_SUFFIXES = {"", ".txt", ".md", ".rst"}

# wheel 沒有附授權原文的套件。
LICENSE_OVERRIDES = {
    "proxy-tools": "proxy_tools.txt",
    "pyobjc-core": "pyobjc.txt",
    "pyobjc-framework-security": "pyobjc.txt",
    "pyobjc-framework-uniformtypeidentifiers": "pyobjc.txt",
}

# (名稱, 說明, 授權原文相對於 repo 的路徑)
OTHER_COMPONENTS = [
    ("python-build-standalone", "CPython 3.11 建置（build 20260414）。MPL-2.0", "packaging/macos/third_party_licenses/python-build-standalone.txt"),
    ("OpenSSL 3", "靜態連結於 libpython。Apache-2.0", "packaging/macos/third_party_licenses/python-standalone.openssl-3.txt"),
    ("SQLite", "靜態連結於 libpython。Public domain", "packaging/macos/third_party_licenses/python-standalone.sqlite.txt"),
    ("libffi", "靜態連結於 libpython。MIT", "packaging/macos/third_party_licenses/python-standalone.libffi.txt"),
    ("Expat", "靜態連結於 libpython。MIT", "packaging/macos/third_party_licenses/python-standalone.expat.txt"),
    ("mpdecimal", "靜態連結於 libpython。BSD-2-Clause", "packaging/macos/third_party_licenses/python-standalone.mpdecimal.txt"),
    ("bzip2", "靜態連結於 libpython。bzip2-1.0.6", "packaging/macos/third_party_licenses/python-standalone.bzip2.txt"),
    ("liblzma (XZ Utils)", "靜態連結於 libpython。0BSD", "packaging/macos/third_party_licenses/python-standalone.liblzma.txt"),
    ("libuuid", "靜態連結於 libpython。BSD-3-Clause", "packaging/macos/third_party_licenses/python-standalone.libuuid.txt"),
    ("zlib", "Zlib", "packaging/macos/third_party_licenses/python-standalone.zlib.txt"),
    ("libuv", "靜態連結於 uvloop。MIT 等", "packaging/macos/third_party_licenses/libuv.txt"),
    ("MapLibre GL JS 5.7.1", "static/vendor/maplibre-gl。BSD-3-Clause", "static/vendor/maplibre-gl/5.7.1/LICENSE.txt"),
    ("maplibre-gl-leaflet 0.1.3", "static/vendor/maplibre-gl-leaflet。ISC", "static/vendor/maplibre-gl-leaflet/0.1.3/LICENSE"),
]

HEADER = """REDLINE 第三方軟體授權聲明（THIRD-PARTY NOTICES）

本檔列出 REDLINE.app 建置環境中安裝的所有第三方元件與其授權原文。建置環境由 uv.lock 固定
（uv sync --frozen --no-dev --group macos-app）。其中部分套件只在建置或其他執行模式使用，
不一定會進入 App（例如 PyInstaller 本體、mcp、cryptography）；為避免遺漏，這裡一律列出。
套件內 vendored 的元件以「vendored: 名稱 版本 (路徑)」標示，同樣不一定全部進入 App。

REDLINE 自身的授權見 LICENSE.md 與 LICENSE-CODE。本檔由
packaging/macos/generate_third_party_notices.py 產生，請勿手動編輯。
"""


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def clean(text: str) -> str:
    """統一換行並移除行尾空白，讓輸出與平台無關；不改動授權內容。"""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def license_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    found: dict[str, str] = {}
    for file in sorted(dist.files or [], key=str):
        parts = file.parts
        if not parts or not parts[0].endswith(".dist-info"):
            continue
        name = parts[-1].lower()
        if "licenses" in parts or re.match(r"(licen[cs]e|copying|notice|authors)", name):
            text = clean(Path(file.locate()).read_text(encoding="utf-8", errors="replace"))
            if text and text not in found.values():
                found["/".join(parts[1:])] = text
    return list(found.items())


def split_vendored_dir(directory: str) -> tuple[str, str]:
    """"jaraco.text-4.0.0.dist-info" → ("jaraco.text", "4.0.0")。"""
    name, _, version = directory.removesuffix(".dist-info").rpartition("-")
    return name, version


def nested_notices(relative_paths: list[tuple[str, ...]]) -> tuple[list[tuple[str, str, tuple[str, ...]]], list[tuple[str, ...]]]:
    """從套件的檔案清單找出巢狀授權：回傳 (vendored 元件, 其他內嵌的 NOTICE)。

    不是頂層 .dist-info 的檔案才算。vendored 元件是巢狀 .dist-info 內的授權檔；其他只收文字檔，
    避免把 copying.cpython-311-darwin.so 這類同名的二進位檔當成授權。
    """
    vendored: list[tuple[str, str, tuple[str, ...]]] = []
    embedded: list[tuple[str, ...]] = []
    for parts in sorted(relative_paths):
        if not parts or parts[0].endswith(".dist-info"):
            continue
        dist_info = next((part for part in parts[:-1] if part.endswith(".dist-info")), None)
        if dist_info:
            if "licenses" in parts or LICENSE_FILE_NAME.match(parts[-1]):
                name, version = split_vendored_dir(dist_info)
                vendored.append((name, version, parts))
        elif LICENSE_FILE_NAME.match(parts[-1]) and Path(parts[-1]).suffix.lower() in TEXT_SUFFIXES and not any(p.endswith(".dSYM") for p in parts):
            embedded.append(parts)
    return vendored, embedded


def nested_sections(dist: metadata.Distribution, problems: list[str]) -> list[str]:
    files = {tuple(file.parts): file for file in dist.files or []}
    vendored, embedded = nested_notices(list(files))
    sections = []
    for name, version, parts in vendored:
        label = REVIEWED_VENDORED.get(normalize_name(name))
        if label is None:
            problems.append(f"vendored {name}（{dist.metadata['Name']}）: 尚未審閱，請確認授權後加入 REVIEWED_VENDORED")
            continue
        text = clean(Path(files[parts].locate()).read_text(encoding="utf-8", errors="replace"))
        sections.append(f"--- vendored: {name} {version} ({'/'.join(parts)}) ---\n授權：{label}\n{text}")
    for parts in embedded:
        text = clean(Path(files[parts].locate()).read_text(encoding="utf-8", errors="replace"))
        sections.append(f"--- {'/'.join(parts)} ---\n{text}")
    for parts, file in sorted(files.items()):
        if EMBEDDED_ATTRIBUTION_FILES.match("/".join(parts)):
            lines = Path(file.locate()).read_text(encoding="utf-8", errors="replace").splitlines()
            attribution = [line.strip() for line in lines if ATTRIBUTION_LINE.search(line) and len(line) < 200]
            if attribution:
                sections.append(f"--- {'/'.join(parts)}（檔案內的授權宣告）---\n" + "\n".join(attribution))
    return sections


def bundled_vendor_modules(pyz_toc: str) -> set[str]:
    """從 PyInstaller 的 PYZ-00.toc 找出實際打包的 vendored 頂層模組，例如 {"jaraco", "tomli"}。"""
    return set(re.findall(r"'[A-Za-z0-9_.]*\._vendor\.([A-Za-z0-9_]+)[A-Za-z0-9_.]*'", pyz_toc))


def missing_vendor_notices(modules: set[str], notices: str) -> list[str]:
    """打包的 vendored 模組若在聲明中找不到對應元件就列出來。"""
    listed = {normalize_name(name) for name in re.findall(r"^--- vendored: (\S+) ", notices, re.MULTILINE)}
    missing = []
    for module in sorted(modules):
        prefix = normalize_name(module)
        if not any(name == prefix or name.startswith(prefix + "-") for name in listed):
            missing.append(module)
    return missing


def generate() -> str:
    problems: list[str] = []
    sections = [clean(HEADER)]
    dists = sorted(metadata.distributions(), key=lambda d: normalize_name(d.metadata["Name"]))
    sections.append(f"{SEPARATOR}\nPython 套件\n{SEPARATOR}")
    for dist in dists:
        name = normalize_name(dist.metadata["Name"])
        if name not in REVIEWED:
            problems.append(f"{name}: 尚未審閱，請確認授權後加入 REVIEWED")
            continue
        override = LICENSE_OVERRIDES.get(name)
        if override:
            texts = [(override, clean((LICENSES / override).read_text(encoding="utf-8")))]
        else:
            texts = license_texts(dist)
        if not texts:
            problems.append(f"{name}: 找不到授權原文，請加入 LICENSE_OVERRIDES")
            continue
        blocks = [f"--- {label} ---\n{text}" for label, text in texts] + nested_sections(dist, problems)
        body = "\n\n".join(blocks)
        sections.append(f"{SEPARATOR}\n{dist.metadata['Name']} {dist.version}\n授權：{REVIEWED[name]}\n{SEPARATOR}\n{body}")
    stale = sorted(set(REVIEWED) - {normalize_name(d.metadata["Name"]) for d in dists})
    problems.extend(f"{name}: 已不在建置環境，請從 REVIEWED 移除" for name in stale)

    sections.append(f"{SEPARATOR}\nPython 直譯器與其他元件\n{SEPARATOR}")
    python_license = Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"
    version = ".".join(str(part) for part in sys.version_info[:3])
    sections.append(f"{SEPARATOR}\nCPython {version}\n授權：PSF-2.0 等\n{SEPARATOR}\n{clean(python_license.read_text(encoding='utf-8'))}")
    for name, description, path in OTHER_COMPONENTS:
        text = clean((ROOT / path).read_text(encoding="utf-8"))
        sections.append(f"{SEPARATOR}\n{name}\n{description}\n{SEPARATOR}\n{text}")

    if problems:
        raise SystemExit("第三方授權清單需要審閱：\n  " + "\n  ".join(problems))
    return "\n\n".join(sections) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--check-bundle", metavar="PYZ_TOC", type=Path, help="確認 PyInstaller 實際打包的 vendored 模組都列在聲明中")
    args = parser.parse_args()
    if args.check_bundle:
        modules = bundled_vendor_modules(args.check_bundle.read_text(encoding="utf-8"))
        missing = missing_vendor_notices(modules, OUTPUT.read_text(encoding="utf-8"))
        if missing:
            print(f"error: 打包的 vendored 模組沒有授權聲明：{missing}", file=sys.stderr)
            return 1
        print(f"vendored modules in the bundle all have notices: {sorted(modules)}")
        return 0
    content = generate()
    if args.write:
        OUTPUT.write_text(content, encoding="utf-8")
        print(f"wrote {OUTPUT} ({len(content)} chars)")
        return 0
    if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
        print("error: THIRD-PARTY-NOTICES.txt 與目前的相依不一致；審閱後執行 --write 更新", file=sys.stderr)
        return 1
    print("THIRD-PARTY-NOTICES.txt is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
