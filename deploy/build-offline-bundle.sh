#!/usr/bin/env bash
#
# Build an OFFLINE deployment bundle for the air-gapped server.
#
# Run this on a machine that CAN reach Python packages (internet, or your
# Nexus PyPI proxy) AND has the SAME OS / CPU architecture / Python version
# as the air-gapped target server. Compiled wheels (pydantic-core, uvloop,
# httptools, watchfiles) are platform + Python-version specific, so matching
# the target matters.
#
# Output: nexus-manager-offline.tar.gz  (app source + all dependency wheels)
# Transfer that single file to the target and follow deploy/README.md.
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
OUT="${1:-nexus-manager-offline.tar.gz}"

echo "==> Build machine Python: $(python3 --version)"
echo "    (Must match the target server's Python, e.g. 3.9)"

rm -rf wheelhouse
mkdir -p wheelhouse

echo "==> Downloading dependency wheels into ./wheelhouse ..."
# --only-binary=:all: keeps everything as pre-built wheels so the target
# needs no compiler. If a package has no wheel for your platform, drop the
# flag and ensure the target has build tools.
python3 -m pip download --only-binary=:all: \
  -r requirements.txt -d wheelhouse

echo "==> Packaging source + wheels into ${OUT} ..."
tar --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='instances.yaml' --exclude='.env' \
    -czf "$OUT" \
    app requirements.txt instances.example.yaml .env.example \
    README.md pytest.ini deploy wheelhouse

echo ""
echo "==> Done: ${OUT}  ($(du -h "$OUT" | cut -f1))"
echo "    1) Copy ${OUT} to the air-gapped server (USB / internal transfer)."
echo "    2) On the server:  tar -xzf ${OUT} && cd nexus-manager  (or repo dir)"
echo "    3) Run:            bash deploy/install-offline.sh"
