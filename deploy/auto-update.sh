#!/usr/bin/env bash
#
# Folder-watch auto-updater for the Nexus Integrated Manager (air-gapped).
#
# Drop a newer offline bundle (nexus-manager-offline*.zip) into the watch
# folder; this script detects a higher version, extracts it, runs the bundled
# deploy/install-service.sh (which rebuilds the venv from the bundle's
# wheelhouse and restarts the service), then archives the processed zip.
#
# Run modes:
#   bash deploy/auto-update.sh            # one check (use with a systemd timer)
#   bash deploy/auto-update.sh --watch    # loop forever every INTERVAL seconds
#
# Overridable env: WATCH_DIR, INSTALL_DIR, PYTHON, PORT, SERVICE, INTERVAL.
# Optional REMOTE source (internet) — newer bundles are pulled automatically:
#   UPDATE_URL=github:owner/repo     # GitHub releases (tag = UPDATE_TAG | latest)
#   UPDATE_URL=https://host/path/    # HTTP directory of nexus-manager-offline-vX.Y.Z.zip
#   GITHUB_TOKEN=...                 # optional, for private/rate-limited GitHub
# Only UPGRADES (never downgrades); a failed install keeps the running version.
#
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/nexus-manager}"
WATCH_DIR="${WATCH_DIR:-$INSTALL_DIR/updates}"
PYTHON="${PYTHON:-python3}"
PORT="${PORT:-8000}"
SERVICE="${SERVICE:-nexus-manager}"
LOG="${LOG:-$INSTALL_DIR/auto-update.log}"
PROCESSED="$WATCH_DIR/processed"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG" >&2; }

current_version() {
  grep -oE '[0-9]+\.[0-9]+\.[0-9]+' "$INSTALL_DIR/app/__init__.py" 2>/dev/null | head -1 || echo "0.0.0"
}

# Version from the ver_X.Y.Z.md marker inside the bundle, else from the filename.
zip_version() {
  local z="$1" v
  v=$(unzip -Z1 "$z" 2>/dev/null | grep -oE 'ver_[0-9]+\.[0-9]+\.[0-9]+\.md' | head -1 \
        | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
  [ -z "$v" ] && v=$(basename "$z" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  echo "$v"
}

# 0 (true) when $1 is strictly greater than $2 (semver via sort -V).
ver_gt() {
  [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -1)" = "$1" ]
}

# Optional remote source: when UPDATE_URL is set, fetch a newer bundle into the
# watch folder so the normal local-install flow can apply it. Supports:
#   UPDATE_URL=github:owner/repo            (GitHub releases, tag=UPDATE_TAG|latest)
#   UPDATE_URL=https://host/path/           (directory index of *-vX.Y.Z.zip files)
remote_fetch() {
  [ -z "${UPDATE_URL:-}" ] && return 0
  if ! command -v curl >/dev/null 2>&1; then log "curl 없음 — 원격 확인 건너뜀"; return 0; fi
  local cur; cur=$(current_version)
  case "$UPDATE_URL" in
    github:*)
      local repo="${UPDATE_URL#github:}" tag="${UPDATE_TAG:-latest}"
      local json rver durl
      json=$(curl -fsSL ${GITHUB_TOKEN:+-H "Authorization: Bearer $GITHUB_TOKEN"} \
               "https://api.github.com/repos/$repo/releases/tags/$tag" 2>/dev/null) \
        || { log "GitHub 릴리스 조회 실패: $repo@$tag"; return 0; }
      rver=$(printf '%s' "$json" | grep -oE 'ver_[0-9]+\.[0-9]+\.[0-9]+\.md' | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
      durl=$(printf '%s' "$json" | grep -oE 'https://[^"]*nexus-manager-offline\.zip' | head -1 || true)
      if [ -z "$rver" ] || [ -z "$durl" ]; then log "릴리스 자산 식별 실패"; return 0; fi
      if ! ver_gt "$rver" "$cur"; then log "원격 새 버전 없음 (현재 $cur · 원격 $rver)"; return 0; fi
      log "원격(GitHub) 새 버전 $rver 다운로드..."
      curl -fsSL -o "$WATCH_DIR/nexus-manager-offline-v$rver.zip" "$durl" \
        && log "다운로드 완료 → 감시 폴더" || log "다운로드 실패"
      ;;
    http://*|https://*)
      local idx rver base="${UPDATE_URL%/}/"
      idx=$(curl -fsSL "$UPDATE_URL" 2>/dev/null) || { log "원격 디렉터리 조회 실패: $UPDATE_URL"; return 0; }
      rver=$(printf '%s' "$idx" | grep -oE 'nexus-manager-offline-v[0-9]+\.[0-9]+\.[0-9]+\.zip' \
               | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1 || true)
      if [ -z "$rver" ]; then log "원격에 버전 zip 없음"; return 0; fi
      if ! ver_gt "$rver" "$cur"; then log "원격 새 버전 없음 (현재 $cur · 원격 $rver)"; return 0; fi
      log "원격(디렉터리) 새 버전 $rver 다운로드..."
      curl -fsSL -o "$WATCH_DIR/nexus-manager-offline-v$rver.zip" "${base}nexus-manager-offline-v$rver.zip" \
        && log "다운로드 완료 → 감시 폴더" || log "다운로드 실패"
      ;;
    *) log "알 수 없는 UPDATE_URL 형식: $UPDATE_URL" ;;
  esac
}

check_once() {
  mkdir -p "$WATCH_DIR" "$PROCESSED"
  if [ "$(id -u)" -ne 0 ]; then log "root 권한이 필요합니다."; return 1; fi
  remote_fetch || true

  local cur best="" bestver=""
  cur=$(current_version)
  shopt -s nullglob
  for z in "$WATCH_DIR"/*.zip; do
    [ -e "$z" ] || continue
    local v; v=$(zip_version "$z")
    if [ -z "$v" ]; then log "버전 식별 불가, 건너뜀: $(basename "$z")"; continue; fi
    if [ -z "$bestver" ] || ver_gt "$v" "$bestver"; then bestver="$v"; best="$z"; fi
  done
  shopt -u nullglob

  [ -z "$best" ] && return 0
  if ! ver_gt "$bestver" "$cur"; then
    log "새 버전 없음 (현재 $cur · 후보 $bestver)"; return 0
  fi

  log "업그레이드 발견: $cur -> $bestver  ($(basename "$best"))"
  local work; work=$(mktemp -d)
  if ! unzip -q "$best" -d "$work"; then
    log "압축 해제 실패: $(basename "$best")"; rm -rf "$work"; return 1
  fi
  # The bundle root holds app/; tolerate a single wrapping directory.
  local root="$work"
  if [ ! -d "$root/app" ]; then
    local sub; sub=$(find "$work" -maxdepth 1 -mindepth 1 -type d | head -1)
    [ -n "$sub" ] && [ -d "$sub/app" ] && root="$sub"
  fi
  if [ ! -d "$root/app" ] || [ ! -f "$root/deploy/install-service.sh" ]; then
    log "유효한 번들이 아님(app/ 또는 deploy/install-service.sh 없음) — 보존: $(basename "$best")"
    rm -rf "$work"; return 1
  fi

  log "설치 실행 (install-service.sh)..."
  if INSTALL_DIR="$INSTALL_DIR" PYTHON="$PYTHON" PORT="$PORT" \
       bash "$root/deploy/install-service.sh" >>"$LOG" 2>&1; then
    mkdir -p "$PROCESSED"
    mv -f "$best" "$PROCESSED/" 2>/dev/null || true
    log "업그레이드 완료: -> $bestver. '$SERVICE' 재시작됨."
  else
    log "설치 실패 — 기존 버전 유지. zip 보존: $(basename "$best")"
    rm -rf "$work"; return 1
  fi
  rm -rf "$work"
}

if [ "${1:-}" = "--watch" ]; then
  INTERVAL="${INTERVAL:-300}"
  log "감시 시작: $WATCH_DIR (주기 ${INTERVAL}s, 현재 $(current_version))"
  while true; do check_once || true; sleep "$INTERVAL"; done
else
  check_once
fi
