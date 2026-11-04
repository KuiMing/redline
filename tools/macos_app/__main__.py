"""python -m tools.macos_app（開發用）；打包後由 packaging/macos/entry.py 進入同一個 main。"""

import sys

from tools.macos_app.launcher import main

if __name__ == "__main__":
    sys.exit(main())
