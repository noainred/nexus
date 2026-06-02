# 폐쇄망(오프라인) 배포 가이드

인터넷이 안 되는 폐쇄망 서버에 이 대시보드를 배포하는 방법입니다.
핵심은 **"파이썬 패키지를 어떻게 가져오느냐"** 하나뿐이며, 두 가지 방법이 있습니다.

| 방법 | 언제 쓰나 | 인터넷 필요? |
| --- | --- | --- |
| **A. Nexus PyPI 프록시 사용** | 대상 서버가 사내 Nexus에 접속 가능(이 앱은 어차피 Nexus와 통신하므로 보통 가능) | 대상 서버는 불필요. Nexus 프록시가 패키지를 제공할 수 있으면 됨 |
| **B. 오프라인 번들** | 대상 서버가 어떤 외부에도 접속 불가(완전 격리) | 빌드용 머신에서만 1회 필요 |

> 사전 조건(공통): 대상 서버에 **Python 3.9 이상**이 설치되어 있어야 합니다.
> 확인: `python3 --version` (Rocky/RHEL 9 계열은 기본 3.9 탑재).

---

## 방법 A — 우리 Nexus의 PyPI 프록시로 설치 (권장, 가장 간단)

대상 서버가 Nexus 서버(예: `192.168.139.96:8081`)에 접속만 되면 됩니다.

```bash
# 1) 코드 가져오기 (git 접근이 되면)
git clone <사내 git 주소>/nexus.git
cd nexus
git checkout claude/practical-noether-uPpi9

# 2) Nexus PyPI 프록시를 패키지 공급원으로 지정해 설치
NEXUS_PYPI_INDEX="http://192.168.139.96:8081/repository/pypi/simple/" \
  bash deploy/install-from-nexus.sh

# 3) 인스턴스 설정
nano instances.yaml        # 실제 Nexus 서버 주소/계정 입력

# 4) 테스트 실행
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> `http://...:8081/repository/pypi/simple/` 부분은 본인 Nexus의 pypi **proxy**
> 저장소 URL로 바꾸세요. (Nexus UI에서 pypi 저장소의 URL 확인 가능)
> 프록시가 아직 해당 패키지를 캐시하지 않았다면, 프록시가 업스트림(pypi.org)에
> 접근 가능할 때 최초 1회 받아옵니다. 완전 격리망이면 **방법 B**를 쓰세요.

---

## 방법 B — 오프라인 번들 (완전 격리망)

### B-1. 빌드용 머신에서 (패키지 받을 수 있는 곳)

> ⚠️ **중요**: 빌드 머신의 **OS·CPU·파이썬 버전이 대상 서버와 같아야** 합니다.
> (pydantic-core 등 일부 패키지는 컴파일된 wheel이라 환경이 달라지면 안 맞습니다.)
> 대상이 Rocky 9 + Python 3.9면, 빌드도 Rocky 9 + Python 3.9에서 하세요.

```bash
git clone <사내 git 주소>/nexus.git
cd nexus
git checkout claude/practical-noether-uPpi9

bash deploy/build-offline-bundle.sh
# -> nexus-manager-offline.tar.gz 생성됨 (소스 + 모든 wheel 포함)
```

### B-2. 대상(폐쇄망) 서버로 파일 전송

`nexus-manager-offline.tar.gz` 를 USB/사내 전송 등으로 옮깁니다.

### B-3. 대상 서버에서 설치 (인터넷 불필요)

```bash
tar -xzf nexus-manager-offline.tar.gz
cd nexus-manager        # (또는 압축이 풀린 폴더)

bash deploy/install-offline.sh   # wheelhouse/ 의 wheel로 오프라인 설치

nano instances.yaml              # 실제 Nexus 서버 주소/계정 입력

source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 운영용으로 항상 켜두기 (systemd 서비스)

터미널을 닫아도 계속 돌아가게 하려면 systemd에 등록합니다.

```bash
# 1) 설치 위치를 /opt/nexus-manager 로 둔다고 가정 (원하는 경로로 변경 가능)
sudo mkdir -p /opt/nexus-manager
sudo cp -r app requirements.txt instances.yaml .venv deploy /opt/nexus-manager/
#   (방법 A/B로 .venv 까지 만든 폴더 전체를 옮기는 게 가장 쉽습니다)

# 2) 전용 계정 생성 (선택, 권장)
sudo useradd --system --home /opt/nexus-manager --shell /sbin/nologin nexusmgr
sudo chown -R nexusmgr:nexusmgr /opt/nexus-manager

# 3) 서비스 등록
sudo cp /opt/nexus-manager/deploy/nexus-manager.service /etc/systemd/system/
#   필요하면 User/경로/포트를 환경에 맞게 수정:
sudo nano /etc/systemd/system/nexus-manager.service

sudo systemctl daemon-reload
sudo systemctl enable --now nexus-manager

# 4) 상태 확인
sudo systemctl status nexus-manager
journalctl -u nexus-manager -f      # 로그 실시간 보기
```

> ⚠️ `.venv` 는 절대경로가 박혀 있어, 만든 위치에서 **다른 경로로 옮기면** 동작이
> 안 될 수 있습니다. 가능하면 처음부터 `/opt/nexus-manager` 에서 설치하거나,
> 옮긴 뒤 `python3 -m venv --upgrade /opt/nexus-manager/.venv` 로 경로를 갱신하세요.

---

## 방화벽 (접속이 안 될 때)

대상 서버에서 8000 포트를 열어야 브라우저로 접속됩니다.

```bash
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

접속: `http://<서버IP>:8000`

---

## (선택) 80/443 포트 + HTTPS

운영에서 `http://서버:8000` 대신 `http://서버`(80) 또는 https로 쓰려면
앞단에 nginx 같은 리버스 프록시를 두고 8000 으로 넘기면 됩니다. (사내 표준에 맞춰
구성하세요. 필요하면 nginx 설정 예시도 만들어 드릴 수 있습니다.)

---

## 체크리스트

- [ ] 대상 서버 `python3 --version` ≥ 3.9
- [ ] 방법 A 또는 B로 `.venv` 생성 및 의존성 설치 완료
- [ ] `instances.yaml` 에 실제 Nexus 서버/계정 입력 (`http://` vs `https://` 주의)
- [ ] `uvicorn ...` 로 테스트 기동 → 브라우저 접속 확인
- [ ] systemd 등록 후 `systemctl enable --now`
- [ ] 방화벽 8000 포트 개방
