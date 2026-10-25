#!/usr/bin/env bash
# Build SalcedoSync.app on macOS (Apple silicon) into build/.
# Usage: scripts/build_macos.sh [--dmg]   (--dmg also makes build/SalcedoSync-<version>-arm64.dmg)
# The bundle id stays com.salcedo.immich-go-gui-mod so saved settings and
# the Keychain API key keep working.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${VERSION:-1.4.4-mod}"
[ -x build/caesiumclt ] || scripts/fetch_caesiumclt.sh build/caesiumclt
uv run python -m nuitka --output-dir=build --output-filename=SalcedoSync \
  --macos-app-name="SalcedoSync" \
  --macos-signed-app-name=com.salcedo.immich-go-gui-mod \
  --macos-app-version="$VERSION" \
  --include-data-files=build/caesiumclt=caesiumclt app.py
rm -rf build/SalcedoSync.app
mv build/app.app build/SalcedoSync.app
echo "Built build/SalcedoSync.app"
if [ "${1:-}" = "--dmg" ]; then
  rm -rf build/dmg-src-salcedosync && mkdir -p build/dmg-src-salcedosync
  cp -R build/SalcedoSync.app build/dmg-src-salcedosync/
  create-dmg --volname "SalcedoSync" --app-drop-link 400 120 --skip-jenkins \
    "build/SalcedoSync-$VERSION-arm64.dmg" build/dmg-src-salcedosync
fi
