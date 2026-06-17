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

# Portal-saved config (update-config.json) overrides env, so the dashboard can
# change the source/token/auto-install without touching systemd.
load_portal_config() {
  local f="$INSTALL_DIR/update-config.json"
  [ -f "$f" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0
  local kv
  kv=$(python3 - "$f" <<'PY' 2>/dev/null || true
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
print("URL=%s" % (d.get("url") or ""))
print("TOKEN=%s" % (d.get("token") or ""))
print("AUTO=%s" % ("1" if d.get("auto_install", True) else "0"))
print("INTERVAL=%s" % (d.get("interval") or ""))
PY
)
  local u t a iv
  u=$(printf '%s\n' "$kv" | sed -n 's/^URL=//p')
  t=$(printf '%s\n' "$kv" | sed -n 's/^TOKEN=//p')
  a=$(printf '%s\n' "$kv" | sed -n 's/^AUTO=//p')
  iv=$(printf '%s\n' "$kv" | sed -n 's/^INTERVAL=//p')
  [ -n "$u" ] && UPDATE_URL="$u"
  [ -n "$t" ] && GITHUB_TOKEN="$t"
  [ -n "$a" ] && AUTO_INSTALL="$a"
  [ -n "$iv" ] && INTERVAL="${INTERVAL:-$iv}"
}

# Optional remote source: when UPDATE_URL is set, fetch a newer bundle into the
# watch folder so the normal local-install flow can apply it. Supports:
#   github:owner/repo        (GitHub releases, tag=UPDATE_TAG|latest)
#   https://host/path/       (internal mirror: versions.json, else dir listing)
remote_fetch() {
  [ -z "${UPDATE_URL:-}" ] && return 0
  if ! command -v curl >/dev/null 2>&1; then log "curl 없음 — 원격 확인 건너뜀"; return 0; fi
  local cur auth=(); cur=$(current_version)
  [ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
  case "$UPDATE_URL" in
    *raw.githubusercontent.com/*|*github.com/*/raw/*|*github.com/*/tree/*|*github.com/*/blob/*)
      # GitHub branch *download folder* (no Release needed, works on private
      # repos with a token): convert the raw/tree URL to the contents API and
      # resolve the newest bundle (versions.json, else a directory listing).
      if ! command -v python3 >/dev/null 2>&1; then log "python3 없음 — GitHub 폴더 조회 건너뜀"; return 0; fi
      local out rver fname durl
      out=$(UPDATE_URL="$UPDATE_URL" GITHUB_TOKEN="${GITHUB_TOKEN:-}" python3 - <<'PY' 2>/dev/null || true
import json, os, re, sys, urllib.request
url = os.environ.get("UPDATE_URL", "")
token = os.environ.get("GITHUB_TOKEN", "")
RAW = re.compile(r"^https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/(.+)$")
DIR = re.compile(r"^https?://github\.com/([^/]+)/([^/]+)/(?:raw|tree|blob)/(.+)$")
m = RAW.match(url) or DIR.match(url)
if not m:
    sys.exit(0)
owner, repo, rest = m.groups()
ref, _, dirpath = rest.rpartition("/")
if not ref or not dirpath:
    sys.exit(0)
api = "https://api.github.com/repos/%s/%s/contents/%s?ref=%s" % (owner, repo, dirpath, ref)
def join(base, name):
    head, _, q = base.partition("?")
    return head.rstrip("/") + "/" + name + (("?" + q) if q else "")
def req(u, raw=False):
    h = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json"}
    if token:
        h["Authorization"] = "Bearer " + token
    return urllib.request.Request(u, headers=h)
VER = re.compile(r"(\d+)\.(\d+)\.(\d+)")
def vkey(v):
    mm = VER.search(v or "")
    return tuple(int(x) for x in mm.groups()) if mm else (0, 0, 0)
rver = ""; file = ""
try:
    with urllib.request.urlopen(req(join(api, "versions.json"), raw=True), timeout=10) as r:
        d = json.loads(r.read(4 * 1024 * 1024).decode("utf-8"))
    v = str(d.get("version") or d.get("latest") or "")
    mm = VER.search(v)
    if mm:
        rver = ".".join(mm.groups())
        file = d.get("file") or ""
        if not file:
            for e in (d.get("versions") or []):
                if str(e.get("version")) == v:
                    file = e.get("file") or e.get("zip") or ""
                    break
        if not file:
            file = "nexus-manager-offline-v%s.zip" % rver
except Exception:
    pass
if not rver:
    try:
        with urllib.request.urlopen(req(api), timeout=10) as r:
            arr = json.loads(r.read(2 * 1024 * 1024).decode("utf-8"))
        best = None
        for it in (arr if isinstance(arr, list) else []):
            n = it.get("name", "")
            if re.fullmatch(r"nexus-manager-offline-v\d+\.\d+\.\d+\.zip", n):
                if best is None or vkey(n) > vkey(best):
                    best = n
        if best:
            rver = ".".join(VER.search(best).groups()); file = best
    except Exception:
        pass
if not rver:
    sys.exit(0)
print("RVER=%s" % rver)
print("FILE=%s" % os.path.basename(file))
print("DURL=%s" % join(api, file))
PY
)
      rver=$(printf '%s\n' "$out" | sed -n 's/^RVER=//p')
      fname=$(printf '%s\n' "$out" | sed -n 's/^FILE=//p')
      durl=$(printf '%s\n' "$out" | sed -n 's/^DURL=//p')
      if [ -z "$rver" ] || [ -z "$durl" ]; then log "GitHub 브랜치 폴더에서 버전 식별 실패: $UPDATE_URL"; return 0; fi
      if ! ver_gt "$rver" "$cur"; then log "원격 새 버전 없음 (현재 $cur · 원격 $rver)"; return 0; fi
      log "원격(GitHub 브랜치) 새 버전 $rver 다운로드... ($fname)"
      curl -fsSL ${auth[@]+"${auth[@]}"} -H "Accept: application/vnd.github.raw" -o "$WATCH_DIR/$fname" "$durl" \
        && log "다운로드 완료 → 감시 폴더" || log "다운로드 실패"
      ;;
    github:*|*github.com*)
      local repo tag="${UPDATE_TAG:-latest}" json rver durl
      repo=$(printf '%s' "$UPDATE_URL" | sed -E 's#^github:##; s#https?://github.com/##; s#\.git$##; s#/$##')
      json=$(curl -fsSL ${auth[@]+"${auth[@]}"} "https://api.github.com/repos/$repo/releases/tags/$tag" 2>/dev/null) \
        || { log "GitHub 릴리스 조회 실패: $repo@$tag"; return 0; }
      rver=$(printf '%s' "$json" | grep -oE 'ver_[0-9]+\.[0-9]+\.[0-9]+\.md' | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
      durl=$(printf '%s' "$json" | grep -oE 'https://[^"]*nexus-manager-offline\.zip' | head -1 || true)
      if [ -z "$rver" ] || [ -z "$durl" ]; then log "릴리스 자산 식별 실패"; return 0; fi
      if ! ver_gt "$rver" "$cur"; then log "원격 새 버전 없음 (현재 $cur · 원격 $rver)"; return 0; fi
      log "원격(GitHub) 새 버전 $rver 다운로드..."
      curl -fsSL ${auth[@]+"${auth[@]}"} -o "$WATCH_DIR/nexus-manager-offline-v$rver.zip" "$durl" \
        && log "다운로드 완료 → 감시 폴더" || log "다운로드 실패"
      ;;
    http://*|https://*)
      local base="${UPDATE_URL%/}/" rver vj file
      # Prefer a versions.json manifest (internal mirror), else parse the index.
      vj=$(curl -fsSL ${auth[@]+"${auth[@]}"} "${base}versions.json" 2>/dev/null || true)
      if [ -n "$vj" ]; then
        rver=$(printf '%s' "$vj" | grep -oE '"(version|latest)"[[:space:]]*:[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
        file=$(printf '%s' "$vj" | grep -oE '"file"[[:space:]]*:[[:space:]]*"[^"]+"' | sed -E 's/.*"file"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' | head -1 || true)
      fi
      if [ -z "${rver:-}" ]; then
        local idx; idx=$(curl -fsSL ${auth[@]+"${auth[@]}"} "$UPDATE_URL" 2>/dev/null) || { log "원격 조회 실패: $UPDATE_URL"; return 0; }
        rver=$(printf '%s' "$idx" | grep -oE 'nexus-manager-offline-v[0-9]+\.[0-9]+\.[0-9]+\.zip' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | sort -V | tail -1 || true)
      fi
      if [ -z "${rver:-}" ]; then log "원격에 버전 정보 없음"; return 0; fi
      if ! ver_gt "$rver" "$cur"; then log "원격 새 버전 없음 (현재 $cur · 원격 $rver)"; return 0; fi
      [ -z "${file:-}" ] && file="nexus-manager-offline-v$rver.zip"
      # `file` may be a path with sub-folders (e.g. v1.6.0/nexus-...zip): keep
      # the relative path for the URL but save under the watch folder by name.
      local fname; fname=$(basename "$file")
      log "원격 새 버전 $rver 다운로드... ($file)"
      curl -fsSL ${auth[@]+"${auth[@]}"} -o "$WATCH_DIR/$fname" "${base}${file}" \
        && log "다운로드 완료 → 감시 폴더" || log "다운로드 실패"
      ;;
    *) log "알 수 없는 UPDATE_URL 형식: $UPDATE_URL" ;;
  esac
}

check_once() {
  mkdir -p "$WATCH_DIR" "$PROCESSED"
  if [ "$(id -u)" -ne 0 ]; then log "root 권한이 필요합니다."; return 1; fi
  load_portal_config
  remote_fetch || true

  if [ "${AUTO_INSTALL:-1}" = "0" ]; then
    log "자동 설치 꺼짐 — 새 번들 다운로드만 수행(적용은 수동/포탈)."
    return 0
  fi

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
