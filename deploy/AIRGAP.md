# 폐쇄망(인터넷 차단) 설치 가이드 — Rocky Linux

인터넷이 전혀 안 되는 폐쇄망 Rocky 서버에 설치하는 전체 과정입니다.
설치에 필요한 건 세 가지뿐이며, 각각을 "인터넷 없이" 가져오는 방법을 다룹니다.

1. **OS 패키지** — `python3`(3.9+), `git`
2. **앱 소스 코드** — 이 저장소
3. **파이썬 의존성** — `requirements.txt` 의 패키지들

---

## 먼저: 두 가지 시나리오 중 내 상황 고르기

| | 시나리오 A (권장) | 시나리오 B |
| --- | --- | --- |
| 상황 | 폐쇄망이지만 **사내 Nexus 서버에는 접속 가능** (이 앱이 관리할 그 Nexus) | 대상 서버가 **어떤 것에도 접속 불가** (완전 격리) |
| 방법 | Nexus를 yum/pypi **미러**로 사용 | USB로 **RPM + wheel** 전부 반입 |
| 난이도 | 쉬움 | 보통 |

> 대부분의 폐쇄망은 시나리오 A입니다. 이 앱은 어차피 Nexus와 통신해야 하므로,
> 대상 서버 → Nexus 접속은 보통 열려 있습니다. 또 여러분 Nexus에는 이미
> rocky/epel(yum) 프록시와 pypi 프록시가 있습니다.

---

# 시나리오 A — 사내 Nexus를 미러로 사용

## A-1. Python 3.9 + git 설치

먼저 이미 되는지 확인:

```bash
python3 --version        # 3.9 이상이면 이 단계 건너뜀
sudo dnf install -y python3 python3-pip git
```

위 `dnf install` 이 성공하면(= 사내 dnf 미러가 이미 구성된 것) A-2로.

> ### CentOS 7 (7.9 등) — 시스템 python3(3.6.8)에서 그대로 실행
> 런타임 스택이 **Python 3.6.8** 을 지원하도록 고정돼 있어(fastapi 0.68.1 /
> starlette 0.14.2 / pydantic 1.9.2 / uvicorn 0.13.4 …), CentOS 7 기본 `python3`
> 로 별도 파이썬 설치 없이 설치·실행됩니다.
> ```bash
> python3 --version        # 3.6.8 (CentOS 7 기본) 이면 그대로 진행
> sudo bash deploy/install-service.sh
> ```
> ⚠️ **오프라인 번들은 대상 Python 태그로 빌드**됩니다. CentOS 7(3.6)용 번들은
> 대상과 같은 3.6 환경에서 빌드해야 cp36 wheel(uvloop/httptools 등)이 맞습니다.
> 릴리스 CI는 `python:3.6` 컨테이너에서 번들을 만들어 이 조건을 자동으로 맞춥니다.
>
> 참고: CentOS 7 은 2024-06 EOL 이므로, 스택을 3.6 에 고정하면 fastapi/uvicorn/httpx
> 등도 EOL·보안패치 종료 버전에 묶입니다. 중장기적으로는 Rocky/RHEL 9(기본 3.9)
> 이전을 권장합니다.

**만약 dnf가 "repo에 접근 불가"로 실패**하면, dnf가 Nexus yum 프록시를 보도록
저장소를 추가합니다. (URL은 본인 Nexus의 rocky 프록시 저장소 주소로 교체)

```bash
sudo tee /etc/yum.repos.d/nexus.repo >/dev/null <<'EOF'
[nexus-baseos]
name=Rocky BaseOS via Nexus
baseurl=http://<NEXUS-IP>:8081/repository/rocky/9/BaseOS/x86_64/os/
enabled=1
gpgcheck=0

[nexus-appstream]
name=Rocky AppStream via Nexus
baseurl=http://<NEXUS-IP>:8081/repository/rocky/9/AppStream/x86_64/os/
enabled=1
gpgcheck=0
EOF

sudo dnf clean all
sudo dnf --disablerepo='*' --enablerepo='nexus-*' install -y python3 python3-pip git
```

> `baseurl` 은 본인 환경의 Nexus yum(proxy) 저장소 구조에 맞게 바꾸세요.
> (인프라 담당자가 이미 `/etc/yum.repos.d` 를 Nexus로 구성해 둔 경우가 많습니다.)

## A-2. 코드 받기

```bash
sudo mkdir -p /opt/nexus-manager && cd /opt/nexus-manager

# 사내 git 서버가 있으면:
git clone <사내-git-주소>/nexus.git .
git checkout main

# git 접근이 안 되면: 코드를 받을 수 있는 PC에서 zip/tar 로 만들어 USB 반입 후 압축 해제
```

## A-3. 파이썬 의존성 — Nexus PyPI 프록시로 설치

```bash
cd /opt/nexus-manager
NEXUS_PYPI_INDEX="http://<NEXUS-IP>:8081/repository/pypi/simple/" \
  bash deploy/install-from-nexus.sh
```

→ `.venv` 생성과 의존성 설치가 끝납니다. 이제 [공통 마무리](#공통-마무리) 로.

---

# 시나리오 B — 완전 오프라인 (USB 반입)

대상 서버가 Nexus조차 접속 안 되는 완전 격리 환경입니다.
**인터넷이 되는, 대상과 동일한 OS/CPU/파이썬 버전의 머신(빌드 머신)**이 필요합니다.

> ⚠️ 빌드 머신과 대상 서버의 **Rocky 버전·CPU(x86_64 등)·Python 버전이 같아야**
> 합니다. RPM과 컴파일된 wheel이 환경에 종속적이기 때문입니다.

## B-1. (빌드 머신) RPM 모으기 — python3, git + 의존성

```bash
sudo dnf install -y dnf-plugins-core        # download 플러그인
mkdir -p ~/airgap/rpms
dnf download --resolve --alldeps --destdir ~/airgap/rpms \
  python3 python3-pip git
```

## B-2. (빌드 머신) 파이썬 wheel + 앱 소스 묶기

```bash
git clone <git-주소>/nexus.git && cd nexus
git checkout main
bash deploy/build-offline-bundle.sh
#  -> nexus-manager-offline.tar.gz (앱 소스 + 모든 wheel)
cp nexus-manager-offline.tar.gz ~/airgap/
```

## B-3. USB로 `~/airgap` 폴더 통째로 대상 서버에 반입

`~/airgap/rpms/*.rpm` 와 `~/airgap/nexus-manager-offline.tar.gz` 두 가지가 있으면 됩니다.

## B-4. (대상 서버) OS 패키지 설치 — 오프라인 RPM

```bash
python3 --version        # 이미 3.9+ 면 이 단계 생략 가능
sudo dnf install --disablerepo='*' -y ~/airgap/rpms/*.rpm
#  dnf가 막히면:  sudo rpm -Uvh --replacepkgs ~/airgap/rpms/*.rpm
```

## B-5. (대상 서버) 앱 설치 — 오프라인 wheel

```bash
sudo mkdir -p /opt/nexus-manager && cd /opt/nexus-manager
tar -xzf ~/airgap/nexus-manager-offline.tar.gz --strip-components=1
bash deploy/install-offline.sh      # wheelhouse/ 의 wheel로 오프라인 설치
```

이제 [공통 마무리](#공통-마무리) 로.

---

## 공통 마무리

### 1. 인스턴스 설정

```bash
cd /opt/nexus-manager
nano instances.yaml          # install 스크립트가 예시에서 자동 생성해 둠
```

실제 Nexus 서버 입력 (http/https·포트 주의):

```yaml
instances:
  - id: front1
    name: "Frontend 1"
    base_url: http://<NEXUS-IP>:8081
    username: admin
    password: 실제비밀번호
```

### 2. 테스트 실행

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`Application startup complete.` → 성공. 브라우저: `http://<서버IP>:8000`

### 3. 방화벽

```bash
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

### 4. 상시 구동 (systemd)

```bash
sudo useradd --system --home /opt/nexus-manager --shell /sbin/nologin nexusmgr || true
sudo chown -R nexusmgr:nexusmgr /opt/nexus-manager
sudo cp /opt/nexus-manager/deploy/nexus-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-manager
sudo systemctl status nexus-manager
```

자세한 systemd/SELinux 설명은 [`ROCKY.md`](ROCKY.md) 참고.

---

## 체크리스트

- [ ] 시나리오 A or B 결정
- [ ] `python3 --version` ≥ 3.9 (없으면 dnf/Nexus 또는 오프라인 RPM으로 설치)
- [ ] 앱 소스 `/opt/nexus-manager` 에 배치
- [ ] `.venv` + 의존성 설치 (Nexus PyPI 프록시 또는 오프라인 wheel)
- [ ] `instances.yaml` 작성 (http/https·포트 확인)
- [ ] `uvicorn` 테스트 기동 → 브라우저 접속
- [ ] firewalld 8000 개방
- [ ] systemd 등록

## 자주 막히는 곳

| 증상 | 해결 |
| --- | --- |
| `dnf` 가 repo 접근 실패 | A-1의 `nexus.repo` 추가, 또는 시나리오 B(오프라인 RPM) |
| `pip` 가 PyPI 접속 실패 | Nexus pypi 프록시 URL 사용(`install-from-nexus.sh`) 또는 오프라인 wheel |
| wheel 설치 중 "no matching distribution" | 빌드 머신과 대상의 **Python/OS 버전 불일치** — 같은 환경에서 다시 번들 생성 |
| `TypeError ... bool \| None` | Python 3.9 미만 — 3.9+ 로 실행 |
