"""PyInstaller 進入點。實際邏輯都在 tools/macos_app/launcher.py。"""

import sys

from tools.macos_app.launcher import main

if __name__ == "__main__":
    sys.exit(main())
