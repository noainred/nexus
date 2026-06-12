#!/usr/bin/env bash
#
# One-shot systemd installer for the Nexus Integrated Manager.
#
# Run as root from the extracted bundle / repo root (the directory that
# contains the `app/` folder):
#
#   sudo bash deploy/install-service.sh
#
# It copies the app to INSTALL_DIR, builds a venv there (offline from
# wheelhouse/ if present, otherwise via pip), creates a dedicated system
# user, installs + enables the systemd service, and starts it.
#
# Re-running upgrades the code in place and keeps your instances.yaml / .env.
#
# Overridable via environment variables:
#   INSTALL_DIR  (default /opt/nexus-manager)
#   SERVICE_USER (default nexusmgr)
#   PORT         (default 8000)
#   PYTHON       (default python3)
#
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/nexus-manager}"
SERVICE_USER="${SERVICE_USER:-nexusmgr}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"
UNIT="/etc/systemd/system/nexus-manager.service"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: root 권한이 필요합니다 →  sudo bash deploy/install-service.sh" >&2
  exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -d "$SRC/app" ]; then
  echo "ERROR: $SRC 에 app/ 폴더가 없습니다. 번들을 푼 폴더에서 실행하세요." >&2
  exit 1
fi

echo "==> 소스:       $SRC"
echo "==> 설치 위치:  $INSTALL_DIR   (user=$SERVICE_USER, port=$PORT)"
echo "==> Python:     $($PYTHON --version 2>&1)"

# 1) Dedicated, non-login system account.
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  echo "==> 시스템 계정 생성: $SERVICE_USER"
  useradd --system --home "$INSTALL_DIR" --shell /sbin/nologin "$SERVICE_USER"
fi

# 2) Copy code (preserve existing instances.yaml / .env on upgrade).
echo "==> 파일 복사 ..."
mkdir -p "$INSTALL_DIR"
cp -r "$SRC/app" "$INSTALL_DIR/"
cp "$SRC/requirements.txt" "$INSTALL_DIR/"
[ -d "$SRC/deploy" ]     && cp -r "$SRC/deploy" "$INSTALL_DIR/"
[ -d "$SRC/wheelhouse" ] && cp -r "$SRC/wheelhouse" "$INSTALL_DIR/"

if [ ! -f "$INSTALL_DIR/instances.yaml" ]; then
  if [ -f "$SRC/instances.yaml" ]; then cp "$SRC/instances.yaml" "$INSTALL_DIR/"
  else cp "$SRC/instances.example.yaml" "$INSTALL_DIR/instances.yaml"; fi
  echo "==> instances.yaml 생성 (나중에 실제 서버 정보로 수정하세요)"
fi
if [ ! -f "$INSTALL_DIR/.env" ]; then
  if [ -f "$SRC/.env" ]; then cp "$SRC/.env" "$INSTALL_DIR/.env"
  else cp "$SRC/.env.example" "$INSTALL_DIR/.env"; fi
  echo "==> .env 생성 (관리자 비밀번호 등은 여기서 설정)"
fi

# 3) Virtualenv in the install dir (absolute path → no relocation issues).
echo "==> 가상환경 생성 ..."
"$PYTHON" -m venv "$INSTALL_DIR/.venv"
if [ -d "$INSTALL_DIR/wheelhouse" ]; then
  echo "==> 의존성 설치 (오프라인: wheelhouse) ..."
  "$INSTALL_DIR/.venv/bin/pip" install --no-index \
    --find-links="$INSTALL_DIR/wheelhouse" -r "$INSTALL_DIR/requirements.txt"
else
  echo "==> 의존성 설치 (pip) ..."
  "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
fi

# 4) Ownership + tighten secrets.
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.env" "$INSTALL_DIR/instances.yaml" 2>/dev/null || true

# 5) systemd unit, rendered with the chosen dir/user/port.
echo "==> 서비스 등록: $UNIT"
cat > "$UNIT" <<UNITEOF
[Unit]
Description=Nexus Integrated Manager (dashboard)
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=-$INSTALL_DIR/.env
Environment=NEXUS_MANAGER_INSTANCES_FILE=$INSTALL_DIR/instances.yaml
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNITEOF

systemctl daemon-reload
systemctl enable --now nexus-manager
sleep 1
systemctl --no-pager --full status nexus-manager | head -n 12 || true

echo ""
echo "==> 완료."
echo "    상태:   systemctl status nexus-manager"
echo "    로그:   journalctl -u nexus-manager -f"
echo "    재시작: systemctl restart nexus-manager   (코드 업데이트 후)"
echo "    접속:   http://<서버IP>:$PORT"
echo ""
echo "  ※ 방화벽이 켜져 있으면 포트를 여세요:"
echo "      firewall-cmd --add-port=${PORT}/tcp --permanent && firewall-cmd --reload"
echo "  ※ 공개 모드(비로그인 현황 열람)를 쓰려면 $INSTALL_DIR/.env 의"
echo "      NEXUS_MANAGER_ADMIN_PASSWORD 를 설정한 뒤 restart 하세요."
