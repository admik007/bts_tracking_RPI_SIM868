#!/usr/bin/env bash
# Publish receiver/app.py for one Pico DEVICE_ID (existing Apache OTA layout).
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[0-9a-fA-F]{8,32}$ ]]; then
    echo "Usage: $0 <PICO_DEVICE_ID_HEX>" >&2
    exit 2
fi

DEVICE_ID="${1,,}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$REPO_ROOT/receiver/app.py"
OTA_ROOT="${OTA_ROOT:-/opt/bts_tracking_RPI_SIM868/firmware}"
DEST="$OTA_ROOT/$DEVICE_ID"

test -f "$SOURCE"
mkdir -p "$DEST"

# Publish the source first, then the manifest last.
# The existing main.py checks the manifest and verifies SHA-256.
install -m 0644 "$SOURCE" "$DEST/app.py"
python3 - "$DEST/app.py" "$DEST/manifest.json" <<'PY'
import hashlib
import json
import os
import sys

app_path, manifest_path = sys.argv[1:]
with open(app_path, "rb") as f:
    digest = hashlib.sha256(f.read()).hexdigest()
manifest = {
    "version": "receiver-" + digest[:16],
    "files": {"app.py": digest},
}
temp_path = manifest_path + ".tmp"
with open(temp_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, separators=(",", ":"))
    f.write("\n")
os.replace(temp_path, manifest_path)
PY

echo "Published: $DEST/app.py"
echo "Manifest:  $DEST/manifest.json"
echo "URL:       http://<HOST>/firmware/$DEVICE_ID/manifest.json"
