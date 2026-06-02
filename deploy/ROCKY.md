# Rocky Linux 서버 실행 가이드

Rocky Linux 8/9 서버에서 이 대시보드를 실행하는 단계별 안내입니다.
(폐쇄망 배포는 [`deploy/README.md`](README.md)를, 여기서는 일반 실행을 다룹니다.)

명령은 `root` 또는 `sudo` 권한으로 실행한다고 가정합니다.

---

## 1. 사전 준비 — Python 3.9 + git

먼저 파이썬이 있는지 확인:

```bash
python3 --version
```

`Python 3.9.x` 이상이 나오면 OK. 없거나 낮으면 설치:

```bash
# Rocky 9 (기본 3.9)
sudo dnf install -y python3 python3-pip git

# Rocky 8 (3.9 모듈 설치)
sudo dnf install -y python39 python39-pip git
#  -> 이 경우 아래 명령에서 python3 대신 python3.9 를 쓰세요.
```

---

## 2. 코드 받기

```bash
sudo mkdir -p /opt/nexus-manager
cd /opt/nexus-manager

# 사내 git 또는 GitHub에서 클론
git clone https://github.com/noainred/nexus.git .
git checkout claude/practical-noether-uPpi9
```

> 폐쇄망이라 git 접근이 안 되면 [`deploy/README.md`](README.md)의 오프라인 번들
> 방식을 사용하세요.

---

## 3. 가상환경 + 의존성 설치

인터넷(또는 사내 PyPI 미러)이 되는 경우:

```bash
cd /opt/nexus-manager
python3 -m venv .venv            # Rocky 8이면 python3.9 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

사내 **Nexus PyPI 프록시**를 쓰는 경우(폐쇄망 권장):

```bash
NEXUS_PYPI_INDEX="http://192.168.139.96:8081/repository/pypi/simple/" \
  bash deploy/install-from-nexus.sh
```

---

## 4. 인스턴스 설정

```bash
cp instances.example.yaml instances.yaml
nano instances.yaml
```

실제 Nexus 서버를 입력합니다. **`http`/`https`와 포트**에 주의하세요:

```yaml
instances:
  - id: front1
    name: "Frontend 1"
    base_url: http://192.168.139.96:8081
    username: admin
    password: 실제비밀번호
```

---

## 5. 테스트 실행

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`Application startup complete.` 가 보이면 성공.

---

## 6. 방화벽 열기 (firewalld)

다른 PC 브라우저에서 접속하려면 8000 포트를 엽니다:

```bash
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

접속: `http://<서버IP>:8000`  (서버 IP는 `hostname -I`)

---

## 7. SELinux 참고

- 기본 구성(uvicorn를 systemd로 직접 실행)은 **추가 설정 없이 동작**합니다.
  (외부 Nexus로의 아웃바운드 연결은 SELinux가 기본 허용)
- 만약 **앞단에 nginx 리버스 프록시**를 두어 nginx가 8000 포트로 넘기게 하면,
  nginx의 아웃바운드 연결을 허용해야 합니다:
  ```bash
  sudo setsebool -P httpd_can_network_connect 1
  ```

---

## 8. 상시 구동 — systemd 서비스 등록

터미널을 닫아도 계속 실행되게 합니다.

```bash
# 전용 계정 생성(권장)
sudo useradd --system --home /opt/nexus-manager --shell /sbin/nologin nexusmgr
sudo chown -R nexusmgr:nexusmgr /opt/nexus-manager

# 서비스 파일 복사 (필요시 User/포트/경로 수정)
sudo cp /opt/nexus-manager/deploy/nexus-manager.service /etc/systemd/system/
sudo nano /etc/systemd/system/nexus-manager.service

# 등록 및 시작
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-manager

# 상태 / 로그 확인
sudo systemctl status nexus-manager
journalctl -u nexus-manager -f
```

> 이미 `/opt/nexus-manager` 에서 `.venv` 까지 만들었다면 경로가 맞으므로
> 서비스 파일을 그대로 쓰면 됩니다. 다른 경로에 만들었다면 서비스 파일의
> `WorkingDirectory` / `ExecStart` / `NEXUS_MANAGER_INSTANCES_FILE` 를 맞춰 수정하세요.

---

## 9. 업데이트(새 코드 반영) 방법

```bash
cd /opt/nexus-manager
git pull
sudo systemctl restart nexus-manager     # 코드 바뀌면 재시작 필요
```

---

## 빠른 점검 체크리스트

- [ ] `python3 --version` ≥ 3.9
- [ ] `.venv` 생성 + `pip install -r requirements.txt` 완료
- [ ] `instances.yaml` 작성 (http/https·포트 확인)
- [ ] `uvicorn ...` 테스트 기동 OK
- [ ] `firewall-cmd` 로 8000 포트 개방
- [ ] `systemctl enable --now nexus-manager` 등록
- [ ] 브라우저 `http://서버IP:8000` 접속 확인

---

## 자주 나는 문제

| 증상 | 원인 / 해결 |
| --- | --- |
| `uvicorn: command not found` | `source .venv/bin/activate` 를 안 함 |
| 개요에서 "연결 불가" | `instances.yaml` 의 http/https·포트·비밀번호 확인 |
| 브라우저 접속 안 됨 | firewalld 8000 포트 개방 여부 확인 |
| `TypeError ... bool \| None` | Python 3.9 미만. 3.9 이상으로 실행 |
| 서비스가 자꾸 죽음 | `journalctl -u nexus-manager -f` 로 로그 확인 |
