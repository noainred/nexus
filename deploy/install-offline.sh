#!/usr/bin/env bash
#
# Install on the AIR-GAPPED target server, with NO internet, using the
# wheels bundled by build-offline-bundle.sh.
#
# Run from the extracted bundle / repo root (the directory that contains the
# `app/` folder and `wheelhouse/`).
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

PYTHON="${PYTHON:-python3}"
echo "==> Target Python: $($PYTHON --version)"

if [ ! -d wheelhouse ]; then
  echo "ERROR: wheelhouse/ not found. Did you extract the offline bundle here?" >&2
  exit 1
fi

echo "==> Creating virtual environment (.venv) ..."
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies from local wheelhouse (offline) ..."
pip install --no-index --find-links=wheelhouse -r requirements.txt

if [ ! -f instances.yaml ]; then
  cp instances.example.yaml instances.yaml
  echo "==> Created instances.yaml from the example."
fi

echo ""
echo "==> Install complete."
echo "    1) Edit instances.yaml with your real Nexus servers:"
echo "         nano instances.yaml"
echo "    2) Test run:"
echo "         source .venv/bin/activate"
echo "         uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo "    3) For a permanent service, see deploy/README.md (systemd)."
