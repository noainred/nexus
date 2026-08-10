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
echo "    (Must match the target server's Python — CentOS 7.9 target = 3.6.8;"
echo "     the release CI builds this inside a python:3.6 container.)"

# WHEELHOUSE_READY=1 lets CI pre-populate ./wheelhouse inside a python:3.6
# container (so cp36 wheels + environment markers resolve correctly) and then
# run this script on the host only to package. Otherwise download here.
if [ "${WHEELHOUSE_READY:-0}" = "1" ] && [ -d wheelhouse ]; then
  echo "==> Using pre-built ./wheelhouse ($(ls wheelhouse | wc -l | tr -d ' ') files)"
else
  rm -rf wheelhouse
  mkdir -p wheelhouse
  echo "==> Building dependency wheels into ./wheelhouse ..."
  # `pip wheel` (not `pip download --only-binary`): uses prebuilt wheels where
  # available and BUILDS pure-Python sdist-only deps into wheels (e.g. the
  # contextvars backport sniffio needs on Python 3.6). The target then installs
  # entirely from wheels with no compiler.
  python3 -m pip wheel -r requirements.txt -w wheelhouse
fi

# Version marker file so the archive's version is unambiguous.
VERSION=$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' app/__init__.py | head -1)
VERFILE="ver_${VERSION}.md"
printf '# Nexus Repository 통합 관리 — v%s\n\n- 버전: %s\n- 빌드 시각(UTC): %s\n' \
  "$VERSION" "$VERSION" "$(date -u +'%Y-%m-%d %H:%M:%S')" > "$VERFILE"
echo "==> Version marker: ${VERFILE}"

echo "==> Packaging source + wheels into ${OUT} ..."
tar --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='instances.yaml' --exclude='.env' \
    -czf "$OUT" \
    app requirements.txt instances.example.yaml .env.example \
    README.md LICENSE THIRD-PARTY-NOTICES.md pytest.ini deploy wheelhouse "$VERFILE"

# Also produce a .zip alongside the .tar.gz (best-effort; needs `zip`).
ZIPOUT="${OUT%.tar.gz}.zip"
if [ "$ZIPOUT" != "$OUT" ] && command -v zip >/dev/null 2>&1; then
  echo "==> Packaging .zip: ${ZIPOUT} ..."
  rm -f "$ZIPOUT"
  zip -rq "$ZIPOUT" \
    app requirements.txt instances.example.yaml .env.example \
    README.md LICENSE THIRD-PARTY-NOTICES.md pytest.ini deploy wheelhouse "$VERFILE" \
    -x '*/__pycache__/*' '*.pyc'
  echo "    Done: ${ZIPOUT}  ($(du -h "$ZIPOUT" | cut -f1))"
elif [ "$ZIPOUT" != "$OUT" ]; then
  echo "==> 'zip' 명령이 없어 .zip 생성을 건너뜀 (tar.gz만 생성)."
fi

echo ""
echo "==> Done: ${OUT}  ($(du -h "$OUT" | cut -f1))"
echo "    1) Copy ${OUT} to the air-gapped server (USB / internal transfer)."
echo "    2) On the server:  tar -xzf ${OUT} && cd nexus-manager  (or repo dir)"
echo "    3) Run:            bash deploy/install-offline.sh"
