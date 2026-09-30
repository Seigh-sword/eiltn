#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if python3 -m PyInstaller --version >/dev/null 2>&1; then
    python3 -m PyInstaller --clean --noconfirm eiltn.spec
    echo
    echo "built dist/eiltn"
    ./dist/eiltn --version
    exit 0
fi

echo "pyinstaller unavailable (missing shared libpython?)"
echo "falling back to a single-file zipapp executable"
./make-pyz.sh
