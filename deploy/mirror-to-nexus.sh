#!/usr/bin/env bash
#
# Mirror the latest GitHub release of this manager into an internal Nexus *raw*
# repository, so air-gapped managers can auto-update from the intranet.
#
# Flow (the "조합"):  GitHub 릴리스(소스)  ──►  사내 Nexus raw(배포 경로)
#   1) GitHub 최신 릴리스에서 nexus-manager-offline.zip + 버전 식별
#   2) versions.json 생성  {"version":"X.Y.Z","file":"nexus-manager-offline-vX.Y.Z.zip"}
#   3) zip + versions.json 을 사내 Nexus raw 폴더에 업로드(PUT)
#   → 매니저 포탈/UPDATE_URL 을 그 raw 폴더 주소로 두면 자동 업그레이드
#
# Required env:
#   NEXUS_RAW_URL   업로드할 사내 raw 폴더 주소(끝에 / 무관). 예:
#                   http://repository.dvc.lgensol.com:8081/repository/manager-upgrade/nexus-manager
#   NEXUS_USER / NEXUS_PASS   Nexus 업로드 계정(raw write 권한)
# Optional env:
#   GITHUB_REPO     (default noainred/nexus)
#   TAG             (default latest)
#   GITHUB_TOKEN    비공개 레포면 지정
#
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-noainred/nexus}"
TAG="${TAG:-latest}"
: "${NEXUS_RAW_URL:?NEXUS_RAW_URL 가 필요합니다 (사내 raw 폴더 주소)}"
: "${NEXUS_USER:?NEXUS_USER 가 필요합니다}"
: "${NEXUS_PASS:?NEXUS_PASS 가 필요합니다}"

base="${NEXUS_RAW_URL%/}/"
gh_auth=(); [ -n "${GITHUB_TOKEN:-}" ] && gh_auth=(-H "Authorization: Bearer $GITHUB_TOKEN")

echo "==> GitHub 릴리스 조회: $GITHUB_REPO@$TAG"
json=$(curl -fsSL "${gh_auth[@]}" "https://api.github.com/repos/$GITHUB_REPO/releases/tags/$TAG")
ver=$(printf '%s' "$json" | grep -oE 'ver_[0-9]+\.[0-9]+\.[0-9]+\.md' | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
durl=$(printf '%s' "$json" | grep -oE 'https://[^"]*nexus-manager-offline\.zip' | head -1 || true)
[ -n "$ver" ] && [ -n "$durl" ] || { echo "ERROR: 릴리스 자산(버전/zip) 식별 실패" >&2; exit 1; }

# Stable file name — matches the versions.json that the release workflow ships.
file="nexus-manager-offline.zip"
vjurl=$(printf '%s' "$json" | grep -oE 'https://[^"]*/versions\.json' | head -1 || true)
echo "==> 최신 버전 v$ver  ($file)"

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
echo "==> 다운로드(GitHub) ..."
curl -fsSL "${gh_auth[@]}" -o "$tmp/$file" "$durl"
# versions.json 은 릴리스 워크플로가 자동 생성한다 — 있으면 그대로 복사, 없으면(구버전 릴리스) 생성.
if [ -n "$vjurl" ]; then
  curl -fsSL "${gh_auth[@]}" -o "$tmp/versions.json" "$vjurl"
else
  printf '{"version":"%s","file":"%s"}\n' "$ver" "$file" > "$tmp/versions.json"
fi

echo "==> 사내 Nexus raw 업로드 → $base"
curl -fsS -u "$NEXUS_USER:$NEXUS_PASS" --upload-file "$tmp/$file"          "${base}${file}"
curl -fsS -u "$NEXUS_USER:$NEXUS_PASS" --upload-file "$tmp/versions.json"  "${base}versions.json"

echo ""
echo "==> 완료. 매니저 포탈 '자동 업그레이드 > 소스=Update Server, Site Info(URL)' 에 아래를 넣으세요:"
echo "      ${base}"
echo "    (versions.json + $file 이 업로드되었습니다)"
