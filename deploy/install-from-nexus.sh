#!/usr/bin/env bash
#
# Install using your OWN Nexus PyPI proxy as the package source.
#
# Use this when the target server cannot reach the public internet but CAN
# reach your Nexus server on the internal network (it must, since this app
# talks to Nexus anyway) and your Nexus has a `pypi` proxy repository.
#
# Usage:
#   NEXUS_PYPI_INDEX="http://<NEXUS-IP>:8081/repository/pypi/simple/" \
#     bash deploy/install-from-nexus.sh
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

: "${NEXUS_PYPI_INDEX:?Set NEXUS_PYPI_INDEX, e.g. http://<nexus-host>:8081/repository/pypi/simple/}"

# Derive the bare host for pip's --trusted-host (plain HTTP / self-signed TLS).
HOST="$(printf '%s' "$NEXUS_PYPI_INDEX" | sed -E 's#^https?://([^:/]+).*#\1#')"
PYTHON="${PYTHON:-python3}"

echo "==> Target Python: $($PYTHON --version)"
echo "==> PyPI index    : $NEXUS_PYPI_INDEX"
echo "==> Trusted host  : $HOST"

echo "==> Creating virtual environment (.venv) ..."
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies from your Nexus PyPI proxy ..."
pip install \
  --index-url "$NEXUS_PYPI_INDEX" \
  --trusted-host "$HOST" \
  -r requirements.txt

if [ ! -f instances.yaml ]; then
  cp instances.example.yaml instances.yaml
  echo "==> Created instances.yaml from the example."
fi

echo ""
echo "==> Install complete. Edit instances.yaml, then run:"
echo "     source .venv/bin/activate"
echo "     uvicorn app.main:app --host 0.0.0.0 --port 8000"
