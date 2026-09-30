#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

rm -rf build/pyz
mkdir -p build/pyz
cp -r eiltn build/pyz/eiltn
find build/pyz -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

python3 -m zipapp \
    -p "/usr/bin/env python3" \
    -m "eiltn.cli:main" \
    -o eiltn.pyz \
    build/pyz

chmod +x eiltn.pyz
echo "built eiltn.pyz"
./eiltn.pyz --version
