# Nexus 통합 관리 (Nexus Integrated Manager)

여러 개의 **Sonatype Nexus Repository Manager 3** 인스턴스를 하나의 웹
대시보드에서 통합 관리하는 도구입니다. FastAPI 백엔드가 각 인스턴스의
REST API를 호출하고, 가벼운 단일 페이지(SPA) 프런트엔드가 이를 시각화합니다.

## 주요 기능

| 영역 | 설명 |
| --- | --- |
| **상태/모니터링** | 모든 인스턴스의 도달 가능성·응답 시간·서브시스템 health를 동시 점검하고, Blob Store 사용량을 표시 |
| **비교 매트릭스** | 저장소(행) × 인스턴스(열) 격자에서 각 저장소의 **존재 여부와 설정 일치 여부**를 색으로 한눈에 비교. Core(타 리전)와 DMZ/사이트 간 구성 드리프트를 즉시 식별 |
| **저장소 관리** | 저장소 목록 조회, 삭제, 컴포넌트(아티팩트) 탐색 및 삭제 (페이지네이션 지원) |
| **다운로드 현황** | 서버 선택 시 모든 저장소의 다운로드 요약(저장소별 자산·용량)을 자동 표시, 저장소 선택 시 실제 다운로드된 패키지 상세 목록 표시 |
| **작업(Tasks)** | 인스턴스의 스케줄 작업 상태·마지막 실행 결과 확인 및 실행/중지(Compact blob store, Cleanup 등) |
| **보안 점검** | 사이트별 익명 접근 허용·기본 admin 계정·관리자 권한 계정 점검 |
| **콘텐츠 동기화** | 사이트 간 실제 컴포넌트(아티팩트) 존재 비교로 콘텐츠 드리프트 탐지 |
| **정리(Cleanup) 정책** | 정책 목록 조회 및 신규 정책 생성 (마지막 업데이트/다운로드 경과일 기준) |
| **서버 설정** | 대시보드에서 Nexus 서버 추가·수정·삭제, 서버별 모니터링/비교 사용 여부 선택 (instances.yaml에 저장) |

> 개요의 Blob Store 사용량에는 **사용률(%) 임계치 경고**(80% 주황 / 90% 빨강)가 표시됩니다.

### 비교 매트릭스 동작 방식

각 저장소를 인스턴스별로 비교하여 행 단위 상태를 산출합니다.

- **설정 지문(signature)** = `포맷 + 타입 + (프록시인 경우) 원격 URL`. 같은 이름이라도 이 셋이 다르면 "설정 상이"로 판단합니다.
- **기준(reference)** = 해당 행에서 가장 많이 나타난 설정. 기준과 다른 셀이 드리프트로 표시됩니다(예: Core만 다른 원격 URL).
- 행 상태:
  - `일치(consistent)` — 모든(조회 가능한) 인스턴스에 존재하고 설정이 동일
  - `설정 상이(drift)` — 같은 저장소가 인스턴스마다 다른 설정 (빨강)
  - `일부 누락(partial)` — 일부 인스턴스에만 존재
  - 조회 불가 인스턴스는 컬럼에 ⚠ 로 표시되고 드리프트 판정에서 제외
- "차이가 있는 항목만 보기" 체크 시 `일치` 행을 숨겨 문제만 빠르게 확인할 수 있습니다.

> 인스턴스 열 순서는 `instances.yaml`에 정의한 순서(예: DMZ → Core → Site1…N)를 그대로 따르므로 네트워크 토폴로지와 동일하게 보입니다.

#### 항목별 상세 비교 (drill-down)

매트릭스 또는 저장소 목록에서 **저장소 이름을 클릭**하면, 그 저장소의 전체
설정(storage, cleanup, proxy.remoteUrl, negativeCache, httpClient 등)을
인스턴스별로 **항목 단위로 비교**하는 표가 팝업으로 열립니다. 값이 서로 다른
항목은 빨갛게 강조되어, 어떤 설정이 어디서 어긋났는지 정확히 짚어줍니다.
("차이나는 항목만" 기본 켜짐 — 끄면 전체 설정을 볼 수 있음)

#### 저장소 1:1 비교 (임의 선택)

매트릭스/상세 비교는 **같은 이름**의 저장소를 맞춰 비교합니다. 이름이 서로
다른 저장소를 비교하고 싶을 때는 **저장소 1:1 비교** 탭을 사용하세요. 양쪽에서
서버와 저장소를 각각 자유롭게 골라(예: `Frontend 1 / epel` ↔ `Backend 1 /
epel-mirror`) 설정을 항목별로 diff 합니다. 동일한 diff 엔진을 재사용하므로 다른
항목은 똑같이 빨갛게 강조됩니다.

## 아키텍처

```
브라우저 SPA (app/static)
        │  fetch /api/...
        ▼
FastAPI (app/main.py)
  ├─ routers/instances.py     인스턴스 목록
  ├─ routers/repositories.py  저장소 · 컴포넌트
  ├─ routers/cleanup.py       정리 정책
  ├─ routers/monitoring.py    상태 · Blob Store
  └─ routers/matrix.py        구성 비교 매트릭스 (app/matrix.py 로직)
        │
        ▼
NexusClient (app/nexus_client.py)  ── httpx ──▶  Nexus REST API
                                                 /service/rest/v1
```

- 자격 증명은 서버의 `instances.yaml`에만 존재하며, `/api/instances`
  응답에는 절대 포함되지 않습니다.
- 모든 Nexus 호출은 비동기(httpx)이며, 상태 점검은 여러 인스턴스를
  동시에 병렬 조회합니다.
- 네트워크/HTTP 오류는 `NexusError`로 정규화되어 일관된 형태로
  프런트엔드에 전달됩니다.

## 설치 및 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 관리할 인스턴스 정의
cp instances.example.yaml instances.yaml
$EDITOR instances.yaml        # base_url / username / password 입력

# (선택) 환경 변수
cp .env.example .env

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000
```

브라우저에서 <http://localhost:8000> 에 접속하면 대시보드가, 
<http://localhost:8000/docs> 에서 OpenAPI 문서가 열립니다.

### 폐쇄망(오프라인) 서버 배포

인터넷이 안 되는 폐쇄망 서버 배포는 [`deploy/README.md`](deploy/README.md)를
참고하세요. 사내 **Nexus PyPI 프록시로 설치**하는 방법과, 완전 격리망을 위한
**오프라인 wheel 번들** 방법, **systemd 서비스 등록**까지 스크립트와 함께
정리되어 있습니다. **Rocky Linux** 서버용 단계별 안내는
[`deploy/ROCKY.md`](deploy/ROCKY.md), **완전 폐쇄망(인터넷 차단) 전용** 통합
가이드(Python·git·의존성 오프라인 반입 포함)는
[`deploy/AIRGAP.md`](deploy/AIRGAP.md)에 있습니다.

## 설정

### `instances.yaml`

관리 대상 인스턴스를 정의합니다. 형식은 `instances.example.yaml` 참고.

```yaml
instances:
  - id: prod                  # URL-safe 고유 식별자 (API 경로에 사용)
    name: "Production Nexus"   # 화면 표시 이름
    base_url: "https://nexus.example.com"
    username: "admin"
    password: "..."
    verify_tls: true           # 선택, 인스턴스별 TLS 검증 오버라이드
```

> `instances.yaml`, `.env` 는 `.gitignore`에 포함되어 있어 자격 증명이
> 커밋되지 않습니다.

### 환경 변수 (`NEXUS_MANAGER_` 접두사)

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `NEXUS_MANAGER_INSTANCES_FILE` | `instances.yaml` | 인스턴스 정의 파일 경로 |
| `NEXUS_MANAGER_REQUEST_TIMEOUT` | `15` | Nexus 호출 타임아웃(초) |
| `NEXUS_MANAGER_VERIFY_TLS` | `true` | 전역 TLS 검증 기본값 |

## REST API 요약

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/api/instances` | 관리 인스턴스 목록 (비밀번호 제외, 사용 플래그 포함) |
| `POST`·`PUT`·`DELETE` | `/api/instances[/{id}]` | 인스턴스 추가·수정·삭제 (instances.yaml에 영속) |
| `GET` | `/api/matrix` | 저장소 × 인스턴스 구성 비교 매트릭스 |
| `GET` | `/api/repository-detail?repository=` | 한 저장소의 설정 항목별 인스턴스 비교(diff) |
| `GET` | `/api/compare?left_instance=&left_repo=&right_instance=&right_repo=` | 임의의 두 저장소(다른 서버·다른 이름) 1:1 설정 비교 |
| `GET` | `/api/content-compare?repository=` | 사이트 간 실제 컴포넌트 존재 비교(콘텐츠 드리프트) |
| `GET` | `/api/security` | 사이트별 보안 점검(익명 접근·admin 계정) |
| `GET` | `/api/instances/{id}/tasks` | 스케줄 작업 목록·상태 |
| `POST` | `/api/instances/{id}/tasks/{taskId}/run` · `/stop` | 작업 실행 / 중지 |
| `GET` | `/api/status` | 전체 인스턴스 상태 동시 점검 |
| `GET` | `/api/instances/{id}/status` | 단일 인스턴스 상태 |
| `GET` | `/api/blobstores` | 전체 인스턴스 Blob Store 사용량 (사이트별) |
| `GET` | `/api/instances/{id}/blobstores` | 단일 인스턴스 Blob Store 사용량 |
| `GET` | `/api/instances/{id}/repositories` | 저장소 목록 |
| `DELETE` | `/api/instances/{id}/repositories/{name}` | 저장소 삭제 |
| `GET` | `/api/instances/{id}/components?repository=` | 컴포넌트 목록(페이지네이션) |
| `DELETE` | `/api/instances/{id}/components/{component_id}` | 컴포넌트 삭제 |
| `GET` | `/api/instances/{id}/downloads-summary` | 서버 내 모든 저장소의 다운로드 요약(저장소별 자산·용량) |
| `GET` | `/api/instances/{id}/downloads?repository=` | 한 저장소의 다운로드 상세(실사용 패키지·용량) |
| `GET` | `/api/instances/{id}/cleanup-policies` | 정리 정책 목록 |
| `POST` | `/api/instances/{id}/cleanup-policies` | 정리 정책 생성 |

## 테스트

```bash
pytest
```

`respx`로 Nexus REST 응답을 모킹하여 클라이언트와 API 계층을 검증합니다
(실제 Nexus 인스턴스 불필요).

## 호환성 참고

- 대상: Nexus Repository Manager **3.x** REST API (`/service/rest/v1`).
- 정리 정책 엔드포인트는 버전에 따라 `v1` 또는 `beta` 네임스페이스를
  사용하므로, 클라이언트가 `v1` → `beta` 순으로 자동 폴백합니다.
- 다운로드 현황은 자산 API의 `lastDownloaded`(마지막 다운로드 시각)와
  `fileSize`를 집계합니다. Nexus 표준 API는 자산별 **정확한 누적 다운로드
  횟수**는 제공하지 않으므로, "다운로드된 자산 = 한 번이라도 받아간 자산"
  기준으로 표시합니다. 자산이 매우 많은 저장소는 안전을 위해 최대 50페이지까지
  스캔하며, 초과 시 수치를 하한으로 표시(truncated)합니다.
