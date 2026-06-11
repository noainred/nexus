# Nexus 통합 관리 (Nexus Integrated Manager)

여러 개의 **Sonatype Nexus Repository Manager 3** 인스턴스(예: DMZ → HQ →
글로벌 DC 15대)를 하나의 웹 대시보드에서 통합 모니터링·비교·관리하는
도구입니다. FastAPI 백엔드가 각 인스턴스의 REST API를 호출하고, 가벼운 단일
페이지(SPA) 프런트엔드가 이를 시각화합니다. 폐쇄망(인터넷 차단) 환경 배포를
전제로 설계되었습니다(8081 REST만 사용, 오프라인 번들 제공).

## 주요 기능

### 모니터링 / 상황판

| 영역 | 설명 |
| --- | --- |
| **개요(플릿 헬스)** | 전체 요약 막대(서버 수·정상/주의/다운·저장소 합계·평균 응답) + 그룹별 인스턴스 상태 카드. 카드 주소 클릭 시 해당 Nexus 새 탭 |
| **계위 상황판** | 토폴로지 탭에서 프록시 연결로 계위(DMZ→HQ→DC)를 자동 도출한 SVG 트리. 노드 색(정상/다운), 끊긴 링크 빨간 점선, **노드 드래그 배치**(자동 저장·배치 초기화), 노드 클릭 시 Nexus 열기 |
| **프록시 원격 상태 보드** | 전 서버 프록시의 **Remote Auto Blocked**/오프라인 상태를 한 표로. 문제 행 '진단' 클릭 → 원격 프로브+현재 설정+권장 조치, 원클릭 **차단 초기화 / 타임아웃 60초 상향 / auto-block 해제** |
| **인프라 체크(ping)** | 주기적 응답시간 기록(1일~365일 그래프), 평소(중앙값) 대비 노랑/빨강 임계치. 서버에 **타임존** 설정 시 툴팁에 한국시간+현지시간 2줄 표시 |
| **Blob Store / 디스크 예측** | 사용량(80%/90% 경고) + 6시간마다 자동 수집한 추세로 **90% 도달 시점 예측**(위험 ≤7일, 주의 ≤21일) |
| **JVM / 리소스** | 노드별 힙/스레드/업타임 메트릭 |
| **알림** | 노드 다운·Heap·디스크 임계치 + (옵션) **구성 드리프트** 주기 점검, Slack 호환 Webhook 푸시 |

### 비교 / 동기화

| 영역 | 설명 |
| --- | --- |
| **비교 매트릭스** | 저장소(행) × 인스턴스(열) 격자로 존재/설정 일치를 색으로 비교. **인스턴스·저장소 칩 선택**으로 부분집합 비교(드리프트 재계산), 셀 호버 시 **전체 설정 카드**, 슬레이브(프록시→관리 서버) 자동 인식(✓ Slave 배지 / 설정 다르면 ≠) |
| **설정 복사** | 셀을 같은 행의 다른 서버 칸으로 **드래그**하면 설정 복사(덮어쓰기·없으면 생성, 그룹이면 멤버도 생성). 비교 팝업의 **일괄 적용**으로 여러 서버에 한 번에, **슬레이브 설정 맞추기**(proxy URL 유지)로 마스터와 정렬 |
| **저장소 1:1 비교** | 서로 다른 서버·다른 이름의 저장소를 자유 선택해 항목별 diff |
| **콘텐츠 동기화(비교)** | 사이트 간 실제 컴포넌트 존재 비교로 콘텐츠 드리프트 탐지 |
| **프록시 캐시 동기화** | 원본 서버의 캐시 자산 목록으로 대상 프록시 캐시를 채움(워밍). 비교 팝업에서 수동 실행 + **예약 콘텐츠 동기화**(매일 지정 시각, Pro 콘텐츠 복제의 OSS 대체) |
| **통합 검색** | 검색어/포맷/저장소로 **모든 서버의 컴포넌트를 한 번에 검색** — 어느 서버·저장소에 어떤 버전이 있는지(취약 라이브러리 추적) |

### 운영 / 정리 / 백업

| 영역 | 설명 |
| --- | --- |
| **저장소 관리** | 저장소 목록·삭제, 컴포넌트 탐색·삭제(페이지네이션) |
| **다운로드 현황** | 서버/저장소별 실제 다운로드된 자산·용량 집계 |
| **작업(Tasks)** | 스케줄 작업 상태·결과 확인, 실행/중지 |
| **플릿 정리 점검** | 전 서버 cleanup 위생 일괄 점검(정책 수·정책 없는 저장소·**Docker GC**·Compact 작업 유무·마지막 실행). **Docker 정리(GC) 전체 실행 → Compact 전체 실행** 2단계 일괄, 정책을 원본에서 전 서버로 복사 |
| **보안 점검** | 사이트별 익명 접근·기본 admin 계정·관리자 계정 점검 |
| **구성 백업/복구** | 서버별 '설정 ↓'로 전체 구성(저장소·blob·정책·보안·작업) JSON 다운로드, '복구 ↑'로 다른 서버에 재생성(**병합/덮어쓰기** 선택). **예약 백업**(매일 지정 시각, 저장 경로·보관 개수 지정) + **DR 준비도 점검**(전 서버 DB 백업 태스크 존재/최근 성공 점검, 일괄 실행) |
| **서버 설정** | 서버 추가·수정·삭제(연결 테스트 포함), 그룹/타임존/모니터링·비교 플래그, 그룹 표시 순서, 비교 기준 항목, 서버 목록 YAML 내보내기/가져오기 |
| **관리자 로그인 + 감사 로그** | `NEXUS_MANAGER_ADMIN_PASSWORD` 설정 시 전체 API 로그인 필요(세션 쿠키). 모든 쓰기 작업을 `audit.log`에 기록, About 탭에서 조회 |

> 현재 탭은 URL 해시로 유지되어 어느 메뉴에서 새로고침해도 그 화면이
> 유지됩니다. 상세 변경 이력은 About 탭의 릴리스 노트를 참고하세요.

### 비교 매트릭스 동작 방식

각 저장소를 인스턴스별로 비교하여 행 단위 상태를 산출합니다.

- **설정 지문(signature)** = `포맷 + 타입 + (프록시인 경우) 원격 URL`
  (서버 설정 › 비교 기준 항목에서 변경 가능).
- **기준(reference)** = 선택한 기준 서버, 또는 자동(다수 기준). 선택한
  인스턴스 부분집합 기준으로 재계산됩니다.
- **슬레이브 인식**: 프록시 remoteUrl이 관리 중인 다른 서버를 가리키면
  의도된 master/slave 구조로 보고, remoteUrl 외 설정이 동일하면 정상(✓
  `<마스터> Slave` 배지), 다르면 드리프트(≠)로 표시하고 호버 카드에 어떤
  항목이 다른지 표로 보여줍니다.
- 행 상태: `일치` / `설정 상이(drift)` / `일부 누락(partial)` / 조회 불가 ⚠.
- 저장소 이름(또는 셀) 클릭 → 항목별 상세 비교 팝업: diff 표, 저장소
  페이지 열기(admin), 슬레이브 맞추기, 일괄 적용, 캐시 동기화.

## 아키텍처

```
브라우저 SPA (app/static: index.html + app.js + style.css)
        │  fetch /api/...   (선택: 로그인 세션 쿠키)
        ▼
FastAPI (app/main.py — 인증/감사 미들웨어 + 백그라운드 루프 5종)
  ├─ routers/instances.py     서버 CRUD · 내보내기/가져오기 · 구성 백업/복구
  ├─ routers/monitoring.py    상태 · Blob Store · 메트릭
  ├─ routers/matrix.py        비교 매트릭스 · 설정 복사 · 슬레이브 맞추기
  ├─ routers/repositories.py  저장소 · 컴포넌트 · 저장소 설정 조회
  ├─ routers/topology.py      토폴로지 · 프록시 상태 보드 · Auto-block 조치
  ├─ routers/sync.py          캐시 워밍 · 예약 동기화(+스케줄러)
  ├─ routers/search.py        전 서버 통합 검색
  ├─ routers/cleanup.py       정리 정책 · 플릿 정리 점검/일괄 실행
  ├─ routers/backup.py        예약 구성 백업 · DR 준비도 점검
  ├─ routers/infra.py         ping 이력 · 디스크 포화 예측
  ├─ routers/auth.py          로그인 · 감사 로그
  └─ routers/(alerts·content·downloads·tasks·security·meta)
        │
        ▼
NexusClient (app/nexus_client.py)  ── httpx ──▶  Nexus REST API
                                                 /service/rest/v1 (+beta 폴백)
```

- 백그라운드 루프: 알림 점검, ping 수집, 예약 구성 백업, 예약 캐시 동기화,
  디스크 사용량 수집(6시간 주기).
- 자격 증명은 서버의 `instances.yaml`에만 존재하며 `/api/instances` 응답에는
  포함되지 않습니다(단, YAML 내보내기에는 포함 — 백업 파일 취급 주의).
- 모든 Nexus 호출은 비동기(httpx) 병렬이며, 오류는 `NexusError`로 정규화되어
  화면에 읽기 좋은 형태로 전달됩니다.

## 설치 및 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 관리할 인스턴스 정의
cp instances.example.yaml instances.yaml
$EDITOR instances.yaml        # base_url / username / password 입력

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000
```

브라우저에서 <http://localhost:8000> 에 접속하면 대시보드가,
<http://localhost:8000/docs> 에서 OpenAPI 문서가 열립니다.

### 폐쇄망(오프라인) 서버 배포 / systemd 서비스

인터넷이 안 되는 폐쇄망 서버 배포는 [`deploy/README.md`](deploy/README.md)를
참고하세요. **오프라인 wheel 번들**(릴리스의 `nexus-manager-offline-*.zip`),
**systemd 서비스 등록**(`deploy/nexus-manager.service`), **Rocky Linux**
단계별 안내([`deploy/ROCKY.md`](deploy/ROCKY.md)), 완전 격리망 통합
가이드([`deploy/AIRGAP.md`](deploy/AIRGAP.md))가 정리되어 있습니다.

```bash
# 요약: 오프라인 번들 설치 → 서비스 등록
unzip nexus-manager-offline-vX.Y.Z.zip -d /opt/nexus-manager
cd /opt/nexus-manager && bash deploy/install-offline.sh
sudo cp deploy/nexus-manager.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now nexus-manager
```

## 설정

### `instances.yaml`

관리 대상 인스턴스를 정의합니다. 형식은 `instances.example.yaml` 참고.
화면(서버 설정)에서 추가·수정하면 이 파일에 영속됩니다. 그룹 순서·비교
기준·ping/백업 설정·예약 동기화 작업도 함께 저장됩니다.

```yaml
instances:
  - id: hq                     # URL-safe 고유 식별자 (API 경로에 사용)
    name: "HQ Nexus"            # 화면 표시 이름
    base_url: "http://10.0.0.10:8081"
    username: "admin"
    password: "..."
    group: "HQ"                # 선택: 개요 그룹/계위 표시
    timezone: "Asia/Seoul"     # 선택: ping 툴팁에 현지시간 2줄 표시
    verify_tls: true            # 선택: 인스턴스별 TLS 검증 오버라이드
```

> `instances.yaml`, `.env`, `*.csv`, `backups/`, `audit.log` 는
> `.gitignore`에 포함됩니다. 업데이트(zip 교체) 시 이 파일들을 보존하세요.

### 환경 변수 (`NEXUS_MANAGER_` 접두사)

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `NEXUS_MANAGER_INSTANCES_FILE` | `instances.yaml` | 인스턴스 정의 파일 경로 |
| `NEXUS_MANAGER_REQUEST_TIMEOUT` | `15` | Nexus 호출 타임아웃(초) |
| `NEXUS_MANAGER_VERIFY_TLS` | `true` | 전역 TLS 검증 기본값 |
| `NEXUS_MANAGER_ADMIN_PASSWORD` | (없음) | 설정 시 **관리자 로그인** 활성화(전체 API 보호) |
| `NEXUS_MANAGER_AUDIT_FILE` | `audit.log` | 쓰기 작업 감사 로그 파일 |
| `NEXUS_MANAGER_ALERT_WEBHOOK` | (없음) | 알림 Webhook URL(Slack 호환) |
| `NEXUS_MANAGER_ALERT_INTERVAL` | `60` | 임계치 점검 주기(초) |
| `NEXUS_MANAGER_ALERT_HEAP_PCT` / `_DISK_PCT` | `90` | Heap/디스크 알림 임계치(%) |
| `NEXUS_MANAGER_ALERT_DRIFT` | `false` | `true`면 저장소 **구성 드리프트**도 알림 |
| `NEXUS_MANAGER_BACKUP_DIR` | `backups` | 예약 구성 백업 기본 디렉터리(화면에서 경로 지정 가능) |
| `NEXUS_MANAGER_PING_FILE` / `_DISK_FILE` | `ping-history.csv` / `disk-history.csv` | 이력 데이터 파일 |

### 런타임 데이터 파일

| 파일/디렉터리 | 내용 |
| --- | --- |
| `instances.yaml` | 서버 목록 + 모든 화면 설정(영속) |
| `ping-history.csv` | ping 이력(인프라 체크 그래프) |
| `disk-history.csv` | blob 사용량 표본(디스크 포화 예측) |
| `backups/<시각>/<서버>.json` | 예약/수동 구성 백업 |
| `audit.log` | 쓰기 작업 감사 기록(JSON lines) |

## REST API 요약 (주요)

전체 목록과 스키마는 `/docs`(OpenAPI)에서 확인하세요.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/api/status` · `/api/blobstores` · `/api/metrics` | 전체 인스턴스 상태/Blob/메트릭 |
| `GET` | `/api/topology` | 프록시 토폴로지(계위 상황판 데이터, `?probe=true` 원격 실점검) |
| `GET` | `/api/proxy-status` | 전 서버 프록시 Auto-block/오프라인 보드 |
| `GET`/`POST` | `/api/proxy-status/diagnose` · `/fix` | 차단 프록시 진단 / 원클릭 조치 |
| `GET` | `/api/matrix` · `/api/repository-detail` · `/api/compare` | 비교 매트릭스 / 항목별 diff / 1:1 비교 |
| `POST` | `/api/matrix/copy-repo` · `/sync-slave-config` | 저장소 설정 복사 / 슬레이브 맞추기 |
| `GET` | `/api/search?q=` | 전 서버 컴포넌트 통합 검색 |
| `POST` | `/api/instances/{id}/cache-warm` | 프록시 캐시 워밍(데이터 동기화) |
| `GET`/`PUT`/`POST` | `/api/sync-jobs[/run]` | 예약 콘텐츠 동기화 작업 관리/즉시 실행 |
| `GET`/`POST` | `/api/instances/{id}/config-export` · `/config-restore?mode=merge\|overwrite` | 구성 백업 다운로드 / 복구(병합·덮어쓰기) |
| `GET`/`PUT`/`POST` | `/api/backup-config` · `/api/backup-run` · `/api/backups…` | 예약 구성 백업 설정/즉시 실행/목록·다운로드 |
| `GET`/`POST` | `/api/dr-audit` · `/api/dr-run-backup` | DR 준비도 점검 / DB 백업 일괄 실행 |
| `GET`/`POST` | `/api/cleanup-audit` · `/api/cleanup-compact-run` · `/api/cleanup-docker-run` · `/api/cleanup-push-policy` | 플릿 정리 점검 / Compact·Docker GC 일괄 / 정책 복사 |
| `GET` | `/api/disk-forecast` | 디스크 포화 예측(`?sample=true` 즉시 수집) |
| `GET` | `/api/ping-history` | ping 이력 |
| `GET` | `/api/alerts` | 현재 알림 상태 (`?refresh=true` 즉시 재평가) |
| `POST` | `/api/login` · `/api/logout` / `GET /api/auth-status` · `/api/audit` | 로그인/로그아웃 / 인증 상태 / 감사 로그 |
| CRUD | `/api/instances…`, `/api/instances/{id}/repositories…`, `/components…`, `/tasks…`, `/cleanup-policies…`, `/downloads…` | 서버·저장소·컴포넌트·작업·정책·다운로드 현황 |

## 테스트

```bash
pytest        # 70개 테스트
```

`respx`로 Nexus REST 응답을 모킹하여 클라이언트·API·플릿 기능(동기화,
백업/복구, 디스크 예측, DR/정리 점검, 프록시 보드, 검색, 인증/감사)을
검증합니다(실제 Nexus 인스턴스 불필요).

## 호환성 참고

- 대상: Nexus Repository Manager **3.x** REST API (`/service/rest/v1`).
- 정리 정책은 버전에 따라 `v1`/`beta` 네임스페이스 자동 폴백, Maven
  저장소의 타입별 admin 경로는 `maven2→maven` 자동 매핑.
- **프록시 상태 보드**는 Nexus 웹 UI가 쓰는 내부 API로 Auto-block 상태를
  읽습니다(일부 버전/권한에서는 '확인불가'로 표시될 수 있음).
- 저장소 설정 읽기/복사/백업에는 해당 계정의 **저장소 admin 읽기 권한**이
  필요합니다(부족 시 403이 항목별로 표시됨). 프록시 원격 비밀번호와 사용자
  비밀번호는 Nexus가 내보내지 않으므로 복구 후 재입력이 필요할 수 있습니다.
- 다운로드 현황은 자산 API의 `lastDownloaded`/`fileSize` 집계 기준이며,
  대형 저장소는 최대 50페이지까지 스캔(초과 시 하한 표시).
- DB 백업 태스크 **생성**은 Nexus REST 미지원 — DR 점검이 없는 서버를
  알려주면 Nexus UI에서 'Admin - Export databases for backup'을 만들어
  두세요.
