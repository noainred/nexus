"""In-app release notes / changelog.

Each entry groups changes as added / changed / removed. The newest version
must stay first and match ``app.__version__``.
"""
from __future__ import annotations

RELEASE_NOTES = [
    {
        "version": "1.3.1",
        "date": "2026-06-16",
        "changes": [
            {"type": "changed", "text": "install-service.sh 안정화 — 설치 폴더 안에서 직접 실행해 소스=설치위치인 경우 'cp: are the same file' 오류 및 소스 삭제 위험 제거(제자리 업그레이드는 복사 건너뜀). 그 외 업그레이드는 app/deploy/wheelhouse를 깨끗이 덮어써 옛 파일이 남지 않게 함(instances.yaml/.env 보존)"},
        ],
    },
    {
        "version": "1.3.0",
        "date": "2026-06-16",
        "changes": [
            {"type": "added", "text": "포탈 자동 업데이트 — 서버 설정 탭의 '자동 업데이트' 카드에서 현재/사용 가능 버전(감시 폴더+원격 소스)과 처리 로그를 확인하고 '지금 업데이트 적용' 버튼으로 즉시 업그레이드. GET /api/update/status · POST /api/update/run. install-service.sh가 앱 계정에 update 유닛 트리거용 sudoers(단일 명령)만 부여"},
        ],
    },
    {
        "version": "1.2.1",
        "date": "2026-06-14",
        "changes": [
            {"type": "changed", "text": "계위 상황판 간선 화살표가 일부 간선에서 안 보이던 문제 수정 — 곡선 끝 접선이 0에 가까우면 마커가 렌더되지 않던 케이스를, 부모로 접근하는 짧은 수직 구간을 둬 항상 방향이 정의되게 함"},
            {"type": "added", "text": "원격(인터넷) 자동 업그레이드 — UPDATE_URL로 GitHub 릴리스(github:owner/repo) 또는 HTTP 디렉터리를 감시해 새 버전 번들을 자동 다운로드 후 업그레이드(폐쇄망은 기존 폴더 투입 방식 유지). install-service.sh가 UPDATE_URL/UPDATE_TAG/GITHUB_TOKEN을 타이머에 전달"},
        ],
    },
    {
        "version": "1.2.0",
        "date": "2026-06-13",
        "changes": [
            {"type": "added", "text": "폴더 감시 자동 업그레이드 — 설치 시 systemd 타이머(5분 주기) 등록, 감시 폴더(updates/)에 더 높은 버전 번들 zip을 넣으면 자동으로 venv 재빌드·서비스 재시작(다운그레이드 안 함, 실패 시 기존 버전 유지). deploy/auto-update.sh + install-service.sh 통합(WITH_AUTOUPDATE=0으로 비활성)"},
            {"type": "changed", "text": "README 현행화 — 매트릭스 열 순서, Blob 추세 차트, 정리 후보, 프록시 차단 일괄 초기화, 자동 업그레이드, 신규 API 반영(테스트 84개)"},
        ],
    },
    {
        "version": "1.1.0",
        "date": "2026-06-13",
        "changes": [
            {"type": "added", "text": "Blob Store 탭에 '사용량 추세 차트' 추가 — 자동 수집 표본으로 blob store별 사용률(%) 변화를 80/90% 경고선과 함께 시각화(기간 14/30/60/200일)"},
            {"type": "added", "text": "'정리 후보' 탭 신설 — 서버를 선택하면 각 저장소에서 한 번도/오랫동안(30·90·180·365일+) 다운로드되지 않은 휴면 자산을 용량 순으로 집계(가장 큰 휴면 자산 표시). Cleanup 정책·증설 판단 근거"},
            {"type": "added", "text": "프록시 원격 상태 보드에 '차단 전체 초기화' 추가 — 차단(Remote Auto Blocked)된 모든 프록시를 전 서버에서 한 번에 차단 초기화(원격/경로 복구 후 사용), 성공/실패 집계"},
        ],
    },
    {
        "version": "1.0.9",
        "date": "2026-06-13",
        "changes": [
            {"type": "added", "text": "비교 매트릭스 인스턴스(열) 순서를 드래그로 지정 — '인스턴스' 칩을 끌어 순서 변경, 브라우저에 자동 저장되어 새로고침 후에도 유지(매트릭스 열도 그 순서로). '순서 초기화'로 기본값 복원"},
        ],
    },
    {
        "version": "1.0.8",
        "date": "2026-06-13",
        "changes": [
            {"type": "changed", "text": "로그인 성공 시 전체 화면을 새로고침하도록 변경 — 기존엔 화면을 제자리에서 펼치기만 해 서버 설정 등 보호 화면에 로그인 이전(공개 모드) 정보가 남던 문제 해결"},
        ],
    },
    {
        "version": "1.0.7",
        "date": "2026-06-13",
        "changes": [
            {"type": "changed", "text": "README 현행화 — 공개 모드(상태 무인증 열람+선택 로그인), 일괄 적용, 계위 상황판 개편(화살표·툴팁·저장소 목록 팝업·드래그 자동확장·수동 계위 tier·권한경고), 보조 주소(alt_url), 한 줄 systemd 설치, 공개 읽기 API 목록, 테스트 81개 등 현재 기능 반영"},
        ],
    },
    {
        "version": "1.0.6",
        "date": "2026-06-13",
        "changes": [
            {"type": "added", "text": "계위 상황판: 노드를 가장자리로 드래그하면 캔버스가 자동으로 커져 잘리지 않음. 배치는 기존대로 자동 저장되어 새로고침·업데이트 후에도 유지"},
            {"type": "added", "text": "서버 설정에 '계위(tier)' 입력 추가 — 1~5로 지정하면 토폴로지 배치가 그 계위대로 줄 배치됨(0=자동). 내부 프록시 링크가 없어도 수동 계위로 배치 가능"},
            {"type": "changed", "text": "권한 경고 분리 — 관리 대상 Nexus가 401/403로 응답(도달은 되나 계정/권한 부족)하면 빨간 '다운'이 아니라 앰버 '권한 경고'로 표시하고 링크도 끊김으로 표시하지 않음. 실제 장애와 구분"},
        ],
    },
    {
        "version": "1.0.5",
        "date": "2026-06-13",
        "changes": [
            {"type": "changed", "text": "로그인 창이 계속 뜨는 진짜 원인 해결 — 자격증명이 틀린 관리 대상 Nexus(예: DMZ1/DMZ2)가 돌려준 401을 매니저 세션 만료로 오인하던 문제. 매니저 인증 게이트 401에만 auth_required 마커를 붙이고, 프런트는 그 마커가 있을 때만 로그인 창을 띄움. 업스트림 Nexus 401은 해당 인스턴스 오류로만 처리"},
        ],
    },
    {
        "version": "1.0.4",
        "date": "2026-06-13",
        "changes": [
            {"type": "changed", "text": "로그인 성공 시 페이지 리로드에만 의존하던 것을 보완 — 인증 즉시 로그인 창을 닫고 전체 메뉴를 드러내도록 변경. '로그인 됐는데 로그인 창이 안 닫히는' 문제 해결"},
        ],
    },
    {
        "version": "1.0.3",
        "date": "2026-06-13",
        "changes": [
            {"type": "changed", "text": "로그인 안정화 — .env의 관리자 비밀번호에 끝 공백·개행·감싼 따옴표가 섞여 있어도 정상 인증되도록 설정값을 정리(strip). '정확한 비밀번호인데 로그인 창이 안 닫히는' 문제 해결. 회귀 테스트 추가"},
        ],
    },
    {
        "version": "1.0.2",
        "date": "2026-06-12",
        "changes": [
            {"type": "removed", "text": "계위 상황판의 단계(tier) 라벨(외부 인터넷/중계/Region) 및 관련 설정 메뉴 제거 — 노드를 자유 배치하면 라벨 위치가 무의미해 혼란만 주던 문제 해소. 왼쪽 여백도 함께 축소"},
        ],
    },
    {
        "version": "1.0.1",
        "date": "2026-06-12",
        "changes": [
            {"type": "added", "text": "한 줄 systemd 설치 스크립트 deploy/install-service.sh 추가 — venv 생성(오프라인 wheelhouse 지원)·전용 계정·서비스 등록·기동까지 자동, 재실행 시 코드만 업그레이드(instances.yaml/.env 보존)"},
            {"type": "changed", "text": "systemd 유닛(nexus-manager.service)이 .env를 EnvironmentFile로 읽도록 변경 — 관리자 비밀번호 등 설정 반영. .env.example에 NEXUS_MANAGER_ADMIN_PASSWORD/AUDIT_FILE 항목 추가"},
        ],
    },
    {
        "version": "1.0.0",
        "date": "2026-06-12",
        "changes": [
            {"type": "added", "text": "공개 모드 — 로그인 없이도 글로벌 서비스 현황(인스턴스 상태/토폴로지/프록시 상태/JVM·디스크/핑/알림)을 볼 수 있고, 설정 변경·민감 정보 접근 시에만 로그인 요구. 비밀번호가 설정돼 있을 때만 적용"},
            {"type": "added", "text": "서버 측 공개 읽기 허용목록(default-deny) — 상태/모니터링 GET만 무인증 허용, 자격증명 export·구성 덤프·감사로그·보안점검·저장소 설정·검색/다운로드 및 모든 쓰기는 항상 보호"},
            {"type": "changed", "text": "프런트엔드 공개 모드 — 비로그인 시 상태 탭만 표시하고 '🔒 로그인' 버튼 제공, 보호 탭/동작 클릭 시 로그인 모달(닫기 가능). 로그인하면 전체 기능 노출"},
        ],
    },
    {
        "version": "0.8.76",
        "date": "2026-06-12",
        "changes": [
            {"type": "changed", "text": "프록시 차단 진단/수정(proxy-status diagnose·fix)에서 상위 서버 조회 실패 시 NameError(500)로 터지던 잠복 버그 수정 — topology.py에 HTTPException import 누락. 이제 의도대로 502/404 반환. 회귀 테스트 2건 추가"},
        ],
    },
    {
        "version": "0.8.75",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "비교 매트릭스 저장소 필터에 '빠른 찾기' 검색창 추가 — 알파벳 입력 시 해당 저장소 칩만 즉시 필터링(강조)되고, 그 상태에서 전체/해제를 누르면 검색된 저장소에만 적용"},
            {"type": "changed", "text": "저장소 칩 목록이 너무 길어 가독성이 낮던 문제 개선 — 칩 영역을 스크롤 박스(최대 높이)로 감싸고 선택/표시 개수 카운터 표시"},
        ],
    },
    {
        "version": "0.8.74",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "계위 상황판 간선에 방향 화살표 추가 — 프록시가 가리키는 업스트림 쪽을 화살표로 표시 (끊긴 링크는 빨간 화살표)"},
            {"type": "added", "text": "간선/숫자에 마우스를 올리면 'OC2a → DMZ1 · 프록시 74개' 형식 툴팁 표시 + 해당 간선 강조"},
            {"type": "added", "text": "간선 또는 숫자를 클릭하면 그 링크를 구성하는 프록시 저장소 목록(원격 URL·상태)을 팝업으로 표시 — 저장소명 클릭 시 서버 간 설정 비교로 이동"},
        ],
    },
    {
        "version": "0.8.73",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "'일괄 적용' 메뉴 신설 — 서버를 선택하면 모든 저장소의 설정값을 항목별(값 분포·저장소 수)로 묶어 보여주고, 새 값을 입력해 그 항목을 가진 모든 저장소에 한 번에 적용 (예: httpClient.autoBlock 일괄 on/off). 항목이 없는 저장소는 자동 건너뜀, 결과는 변경/건너뜀/실패로 집계"},
        ],
    },
    {
        "version": "0.8.72",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "인프라 체크 차트 툴팁을 '응답속도: / 한국시간: / 로컬시간:' 세 줄 라벨 형식으로 변경 (타임존 미설정 서버는 한국시간까지만 표시)"},
        ],
    },
    {
        "version": "0.8.71",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "서버 설정에 보조 주소(alt_url) 입력 추가 — 같은 서버를 IP와 FQDN 두 표기로 등록 가능. 프록시 remoteUrl 비교(슬레이브 인식·토폴로지 내부 링크)에서 둘 중 하나만 맞아도 동일 서버로 처리"},
            {"type": "changed", "text": "모니터링/비교 사용 토글 시 저장된 타임존이 지워지던 문제 수정 (토글 요청에 timezone 미포함이던 버그)"},
        ],
    },
    {
        "version": "0.8.70",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "버그 수정 — '슬레이브 설정 맞추기'(또는 설정 복사) 이후 매트릭스 셀 호버 팝업이 옛 'Slave · 설정 다름' 정보를 계속 보여주던 문제 수정. 호버 툴팁 캐시(slaveCache)를 함께 무효화하고, 매트릭스 새로고침 시 파생 캐시를 모두 초기화하도록 변경"},
        ],
    },
    {
        "version": "0.8.69",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "계위 상황판 단계(tier) 기본 이름 변경 — 최상위→'외부 인터넷', 말단(DC)→'Region'"},
            {"type": "added", "text": "서버 설정 탭에 '계위 상황판 단계 이름' 메뉴 추가 — 최상위/중계/말단 단계 라벨을 원하는 단어로 수정·저장(브라우저별 보관)·기본값 복원 가능"},
        ],
    },
    {
        "version": "0.8.68",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "계위 상황판 패널이 다이어그램 크기에 딱 맞게 줄어들고 가운데 정렬되도록 수정 — 오른쪽의 큰 빈 공간 제거"},
        ],
    },
    {
        "version": "0.8.67",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "계위 상황판 디자인 개선 — 캔버스를 내용 크기에 맞게 트리밍(오른쪽/아래 여백 제거), 계위 간격 축소, 점 격자 배경, 노드 카드 그림자+상태 점, 연결선 강조색·둥근 끝, 간선 숫자 가독성(후광), 계위 라벨이 드래그된 행을 따라가도록 개선"},
        ],
    },
    {
        "version": "0.8.66",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "'인스턴스 상태'를 별도 메뉴로 분리 — 개요 탭은 계위 상황판 전용, 새 '인스턴스 상태' 탭에 플릿 요약 막대+그룹별 서버 카드 표시"},
        ],
    },
    {
        "version": "0.8.65",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "계위 상황판을 개요 탭 상단으로 이동 — 첫 화면에서 전체 계위(드래그 배치·배치 초기화 포함)를 바로 확인. 토폴로지 탭에는 노드별 링크 상세와 프록시 상태 보드 유지"},
        ],
    },
    {
        "version": "0.8.64",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "README 현행화 — 전체 기능 표(모니터링/비교·동기화/운영·백업), 아키텍처(라우터·백그라운드 루프 5종), 환경 변수(로그인·감사·드리프트·백업 등), 런타임 데이터 파일, 주요 API 요약, 호환성 참고를 v0.8.63 기준으로 갱신"},
        ],
    },
    {
        "version": "0.8.63",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "계위 상황판 드래그 배치 — 노드를 끌어 원하는 위치에 배치(연결선 실시간 추적, 브라우저에 자동 저장). 클릭은 기존대로 Nexus 열기, '배치 초기화' 버튼으로 자동 배치 복귀"},
        ],
    },
    {
        "version": "0.8.62",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "관리자 로그인 + 감사 로그 — NEXUS_MANAGER_ADMIN_PASSWORD 설정 시 모든 API에 로그인 필요(세션 쿠키), 화면에 로그인/로그아웃 추가. 모든 쓰기 작업(POST/PUT/DELETE)을 audit.log에 기록하고 About 탭에서 조회(시각/IP/메서드/경로/결과). 테스트 3종 포함(총 70개)"},
        ],
    },
    {
        "version": "0.8.61",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "플릿 기능 테스트 13종 추가 — 예약 동기화·구성 백업(실행/다운로드/경로 탈출 방지)·디스크 예측 수치·DR 점검(정상/누락/일괄 실행)·정리 점검·프록시 차단 보드·통합 검색·복사 검증 (총 67개 테스트)"},
        ],
    },
    {
        "version": "0.8.60",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "서버별 타임존 — 서버 설정에 타임존(IANA, 예: Europe/Berlin) 입력란 추가. 인프라 체크 차트 툴팁에 한국시간/현지시간 2줄로 표시(타임존 미입력 시 기존처럼 1줄)"},
        ],
    },
    {
        "version": "0.8.59",
        "date": "2026-06-11",
        "changes": [
            {"type": "changed", "text": "계위 상황판 렌더링 깨짐 수정 — 최상위(루트) 노드가 없는 구조(서버 간 상호 프록시/순환)에서 좌표가 NaN이 되어 노드가 겹쳐 보이던 문제 해결: 가장 많이 참조되는 서버를 루트로 자동 승격하고 계층을 압축, 계위 라벨도 최상위/중계/말단으로 정리"},
        ],
    },
    {
        "version": "0.8.58",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "계위 상황판 — 토폴로지 탭에 프록시 연결로 계위(DMZ→HQ→글로벌 DC)를 자동 도출한 SVG 트리 대시보드 추가. 노드 색(정상/다운), 끊긴 링크 빨간 점선, 좌측 계위 라벨, 노드 클릭 시 해당 Nexus 새 탭"},
        ],
    },
    {
        "version": "0.8.57",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "DR 준비도 점검 — 서버 설정에 'DR 준비도 점검(DB 백업)' 추가. 모든 서버에 'Export databases for backup' 태스크가 있고 최근 8일 내 성공했는지 점검(구성 백업 상태 요약 포함), 'DB 백업 전체 실행' 일괄 트리거. 신규 /api/dr-audit·/api/dr-run-backup"},
        ],
    },
    {
        "version": "0.8.56",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "Auto-block 진단·해제 — 프록시 상태 보드에서 문제 행의 '진단' 클릭 시 원격 프로브(응답/지연)와 현재 timeout·재시도·auto-block 설정, 권장 조치를 표시. 원클릭 조치: 차단 초기화(재시도)/타임아웃 60초 상향/auto-block 해제. 신규 /api/proxy-status/diagnose·fix"},
        ],
    },
    {
        "version": "0.8.55",
        "date": "2026-06-11",
        "changes": [
            {"type": "added", "text": "디스크 포화 예측 — Blob Store 탭에 예측 보드 추가. 6시간마다 전 서버 blob 사용량을 자동 수집해 일일 증가율로 90% 도달 시점을 예측(위험 7일/90%·주의 21일/80%), '지금 수집 + 갱신' 버튼. 신규 GET /api/disk-forecast"},
        ],
    },
    {
        "version": "0.8.54",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "Docker 2단계 정리 일괄화 — 플릿 정리 점검에 'Docker GC' 컬럼(고아 레이어 정리 작업 유무) 추가, 'Docker 정리(GC) 전체 실행' 버튼으로 전 서버 GC 일괄 실행(이후 Compact로 디스크 회수). 신규 /api/cleanup-docker-run"},
        ],
    },
    {
        "version": "0.8.53",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "플릿 정리 점검 — 정리 정책 탭에서 전 서버의 cleanup 위생을 일괄 점검(정책 수·정책 없는 저장소·Compact blob store 작업 유무·마지막 실행). 'Compact 전체 실행'으로 모든 서버의 Compact 작업을 일괄 실행, 정책을 원본에서 전 서버로 일괄 복사. 신규 /api/cleanup-audit·/api/cleanup-compact-run·/api/cleanup-push-policy"},
        ],
    },
    {
        "version": "0.8.52",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "프록시 원격 상태 보드 — 토폴로지 탭에서 전 서버 프록시의 Remote Auto Blocked/오프라인 상태를 한 표로 조회(차단/문제 우선 정렬, '문제만 보기' 필터, 요약 집계). 신규 GET /api/proxy-status"},
        ],
    },
    {
        "version": "0.8.51",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "예약 콘텐츠 동기화 — 서버 설정에 '예약 콘텐츠 동기화' 추가. 원본→대상(프록시) 저장소 캐시를 매일 지정 시각에 자동으로 채움(Pro 콘텐츠 복제의 OSS 대체). 작업 추가/사용토글/지금실행/삭제 + 백그라운드 스케줄러. 신규 /api/sync-jobs"},
        ],
    },
    {
        "version": "0.8.50",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "일괄 적용(Bulk push) — 저장소 비교 팝업에서 원본 서버의 설정을 선택한 여러 서버에 한 번에 적용(덮어쓰기·없으면 생성, 그룹 멤버 포함)"},
            {"type": "added", "text": "드리프트 자동 감시 — NEXUS_MANAGER_ALERT_DRIFT=true 설정 시 알림 점검에서 저장소 구성 드리프트(서버 간 설정 상이)를 감지해 알림/Webhook으로 통지"},
        ],
    },
    {
        "version": "0.8.49",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "플릿 헬스 대시보드 — 개요 상단에 전체 요약 막대(서버 수, 정상/주의/다운, 저장소 합계, 평균 응답)를 표시"},
        ],
    },
    {
        "version": "0.8.48",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "통합 검색 탭 — 검색어/포맷/저장소로 모든 서버의 컴포넌트(아티팩트)를 한 번에 검색해 어느 서버·저장소에 어떤 버전이 있는지 표시(취약 라이브러리 추적·배포 확인). 신규 GET /api/search"},
        ],
    },
    {
        "version": "0.8.47",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "매트릭스 셀의 'Slave' 표기를 배지 형태로 가독성 개선(정상=초록/다름=주황)"},
            {"type": "added", "text": "저장소 비교 팝업에 '저장소 페이지 열기' 버튼 추가 — 설정이 모두 같아도 각 서버의 admin 저장소 설정을 새 탭으로 열 수 있음"},
        ],
    },
    {
        "version": "0.8.46",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "현재 탭을 URL 해시로 저장 — 어느 메뉴에서 새로고침해도 그 화면이 유지되고, 뒤로/앞으로 가기도 동작"},
        ],
    },
    {
        "version": "0.8.45",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "매트릭스 셀 클릭은 항목별 비교 팝업을 열도록 변경(의도치 않게 Nexus로 이동하던 동작 제거). Nexus admin 저장소 설정은 비교 팝업의 서버 이름 링크로 이동"},
        ],
    },
    {
        "version": "0.8.44",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "슬레이브 설정 맞추기 — 저장소 비교 팝업에 'proxy URL 유지' 버튼 추가. 프록시 remoteUrl(마스터 지향)과 인증정보는 유지하고 나머지 설정을 마스터와 동일하게 맞춤. 신규 POST /api/matrix/sync-slave-config"},
        ],
    },
    {
        "version": "0.8.43",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "Slave 설정 다름 표시를 표(항목/이 서버/마스터)로 한 줄에 하나씩 — 어떤 값이 어떻게 다른지 가독성 있게 표시"},
        ],
    },
    {
        "version": "0.8.42",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "서버 설정 백업에 '백업 저장 경로' 지정 추가 — 사용자가 지정한 디렉터리에 백업 저장(비우면 기본 backups/). '지금 백업' 결과에 실제 저장 경로 표시"},
        ],
    },
    {
        "version": "0.8.41",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "서버 설정 백업 — 서버 설정 맨 아래 '서버 설정 백업' 박스 추가. 지정한 시각에 매일 모든 Nexus 서버 구성을 자동 백업(서버별 JSON, 보관 개수 초과 시 오래된 것 삭제), '지금 백업'·백업 목록 다운로드 제공. 백업 JSON은 서버 행 '복구 ↑'로 신속 복구. 신규 /api/backup-config, /api/backup-run, /api/backups"},
        ],
    },
    {
        "version": "0.8.40",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "프록시 캐시 동기화 — 저장소 비교 팝업에서 원본 서버의 캐시 자산 목록으로 대상 프록시의 캐시를 채움(Range GET 워밍, 재개식 진행, 성공/실패 집계). 신규 POST /api/instances/{id}/cache-warm"},
        ],
    },
    {
        "version": "0.8.39",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "매트릭스 바로가기 — 열 머리글(서버명) 클릭 시 그 서버 Nexus를, 셀 클릭 시 그 서버의 admin 저장소 설정 화면(#admin/repository/repositories:<repo>)을 새 탭으로 열기"},
        ],
    },
    {
        "version": "0.8.38",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "Slave 노드를 전체 설정으로 검증 — remoteUrl만 다르면 정상(✓), 그 외 항목(예: httpClient.autoBlock)이 다르면 drift(≠ '설정 다름')로 표시하고 행 상태에도 반영. 호버 카드는 어떤 항목이 다른지 키 목록을 표시(슬레이브 셀은 매트릭스 로드 시 지연 검증)"},
        ],
    },
    {
        "version": "0.8.37",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "매트릭스에서 slave 노드(프록시 remoteUrl이 관리 서버를 가리킴)는 정상(✓)으로 표시 — drift(≠)로 보지 않고 셀에 '<마스터> Slave' 태그를 달며, 행 상태 계산에서도 정상 처리(다수 기준은 비-slave 셀로 산정)"},
        ],
    },
    {
        "version": "0.8.36",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "매트릭스 호버 카드에 Slave 노드 표시 — 프록시 remoteUrl이 관리 중인 다른 서버를 가리키면 그 서버명/‘Slave’를 두 줄 가운데 정렬 배지로 표시하고, remoteUrl 외 설정이 동일한지(‘설정 동일’/‘일부 설정 다름’)도 함께 표시"},
        ],
    },
    {
        "version": "0.8.35",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "매트릭스 '자동(다수 기준)' 모드에서 행 상태(설정 상이/일부 누락/일치)와 셀 ≠ 표시를 선택한 인스턴스 부분집합 기준으로 재계산 — 인스턴스를 골라 비교하면 그 선택만 반영"},
        ],
    },
    {
        "version": "0.8.34",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "매트릭스 드래그 복사에서 그룹 저장소 복사 시 대상에 없는 멤버 저장소(재귀)도 먼저 생성 — 'Member repository does not exist' 400 오류 해결(멤버는 없을 때만 생성, 그룹 자체는 덮어쓰기)"},
        ],
    },
    {
        "version": "0.8.33",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "비교 매트릭스 셀에 마우스를 올리면 그 저장소의 전체 설정(blob store·write policy·proxy·cleanup·멤버 등)을 카드로 표시 — 호버 시 설정을 불러와 모든 항목을 한눈에. 한 번 본 셀은 캐시"},
        ],
    },
    {
        "version": "0.8.32",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "Maven 저장소 설정 읽기/복사/복구 시 404 나던 문제 수정 — 포맷 'maven2'를 admin API 경로 'maven'으로 매핑(상세 비교·드래그 복사·구성 가져오기 모두 적용)"},
            {"type": "changed", "text": "토스트(알림)가 길면 화면 밖으로 잘리던 문제 수정 — 자동 줄바꿈 및 최대 폭 적용"},
        ],
    },
    {
        "version": "0.8.31",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "매트릭스 드래그 복사 시 확인 창 문구를 '…설정을 업데이트 하시겠습니까?'로 명확화(덮어쓰기 경고 강조)"},
        ],
    },
    {
        "version": "0.8.30",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "비교 매트릭스에서 셀 드래그&드롭으로 저장소 설정 복사 — 설정이 있는 셀을 같은 행의 다른 서버 칸에 놓으면 그 저장소 설정을 대상 서버로 복사(덮어쓰기·없으면 생성). 원본 admin 읽기/대상 쓰기 권한 필요"},
        ],
    },
    {
        "version": "0.8.29",
        "date": "2026-06-10",
        "changes": [
            {"type": "added", "text": "비교 매트릭스에서 비교 대상 선택 기능 — 인스턴스(열)와 저장소(행)를 칩으로 골라 부분집합만 비교(저장소 전체/해제 버튼 포함). 선택한 인스턴스 기준으로 drift(설정 상이) 판정도 다시 계산"},
        ],
    },
    {
        "version": "0.8.28",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "개요 카드의 서버 주소를 클릭하면 새 탭에서 해당 서버의 Nexus(8081)가 열리도록 링크화"},
        ],
    },
    {
        "version": "0.8.27",
        "date": "2026-06-10",
        "changes": [
            {"type": "changed", "text": "서버 추가/수정 등에서 검증 오류(422)가 '[object Object]'로 표시되던 문제 수정 — 어떤 필드가 왜 잘못됐는지 읽을 수 있는 메시지로 표시(예: 식별자(id)는 영문/숫자/._- 만 허용)"},
        ],
    },
    {
        "version": "0.8.26",
        "date": "2026-06-10",
        "changes": [
            {"type": "removed", "text": "네트워크 속도 측정(Spine→Leaf 처리량) 기능 전체 삭제 — '네트워크 속도' 탭/차트, 측정 설정·자동구성·speedtest 저장소 생성, 관련 API/백그라운드 측정 루프 제거"},
        ],
    },
    {
        "version": "0.8.25",
        "date": "2026-06-09",
        "changes": [
            {"type": "changed", "text": "개요 카드의 '저장소' 라벨을 'Repository'로 변경하고 그 숫자를 가운데 정렬"},
        ],
    },
    {
        "version": "0.8.24",
        "date": "2026-06-09",
        "changes": [
            {"type": "added", "text": "구성 가져오기에 방식 선택 추가 — 병합(merge: 기존 유지, 없는 것만 추가) / 덮어쓰기(overwrite: 기존 항목도 PUT으로 갱신). 저장소·라우팅·콘텐츠셀렉터·권한·역할·사용자 갱신 지원(blob store는 데이터 보호상 신규 생성만). 결과에 생성/갱신/건너뜀/실패 집계 표시"},
        ],
    },
    {
        "version": "0.8.23",
        "date": "2026-06-09",
        "changes": [
            {"type": "changed", "text": "측정 저장소 자동 구성의 기본 저장소 이름을 'speedtest' → 'speedtest_hosted'로 변경(hosted 용도를 명확히 하고 옛 proxy 'speedtest'와의 이름 충돌 회피)"},
        ],
    },
    {
        "version": "0.8.22",
        "date": "2026-06-09",
        "changes": [
            {"type": "changed", "text": "측정 저장소 자동 구성: Spine의 'speedtest'가 hosted가 아니면(옛 proxy 잔재 등) 삭제 후 hosted로 재생성 — 더미 파일 업로드가 405(Method Not Allowed)로 실패하던 문제 해결"},
        ],
    },
    {
        "version": "0.8.21",
        "date": "2026-06-09",
        "changes": [
            {"type": "changed", "text": "측정 저장소 자동 구성: 드롭다운에서 고른 Spine을 그대로 사용하고(저장 안 해도 됨), 구성 후 선택한 Spine이 빈칸으로 풀리던 문제 수정"},
        ],
    },
    {
        "version": "0.8.20",
        "date": "2026-06-09",
        "changes": [
            {"type": "added", "text": "구성 복구(가져오기): 서버 행의 '복구 ↑'로 다운로드한 설정 JSON을 대상 Nexus에 재생성 — 저장소·blob store·cleanup/routing 정책을 의존성 순서로 만들고(기존 항목은 건너뜀), 선택 시 보안(역할/권한/콘텐츠셀렉터/사용자)도 복구. 프록시 캐시 등 실데이터는 업스트림에서 자동 재수신되므로 대상 아님"},
            {"type": "changed", "text": "설정 다운로드에 file blob store의 경로(path)를 포함해 복구 시 그대로 재생성되도록 보강"},
        ],
    },
    {
        "version": "0.8.19",
        "date": "2026-06-09",
        "changes": [
            {"type": "added", "text": "서버 설정 다운로드: 서버 목록의 '설정 ↓' 버튼으로 해당 Nexus의 현재 구성(저장소 전체 설정·blob store·cleanup/routing·보안·작업 등)을 JSON 스냅샷으로 내려받기(섹션별 best-effort, 읽기 권한 없는 항목은 errors에 기록)"},
        ],
    },
    {
        "version": "0.8.18",
        "date": "2026-06-09",
        "changes": [
            {"type": "changed", "text": "측정 저장소 자동 구성: Leaf의 'speedtest' 프록시는 항상 재생성하여 remote URL과 Spine 인증을 보장(기존 잘못된 프록시 재사용 시 측정에서 HTTP 500 나던 문제 해결)"},
        ],
    },
    {
        "version": "0.8.17",
        "date": "2026-06-09",
        "changes": [
            {"type": "changed", "text": "측정 저장소 자동 구성: 저장소가 이미 있으면 생성 전에 목록으로 확인해 '재사용'으로 처리(Nexus의 'duplicated key' 400을 오류로 표시하던 문제 수정)"},
        ],
    },
    {
        "version": "0.8.16",
        "date": "2026-06-09",
        "changes": [
            {"type": "added", "text": "'측정 저장소 자동 구성' 버튼 — 적당한 자산이 없을 때 Spine에 raw 저장소+더미 파일(지정 크기)을 만들고 각 Leaf에 프록시를 자동 생성, 측정 설정까지 자동 반영"},
        ],
    },
    {
        "version": "0.8.15",
        "date": "2026-06-09",
        "changes": [
            {"type": "added", "text": "측정 결과에 실제 받은 용량(MB)과 캐시 삭제 결과(OK/없음/실패)를 표시 — 캐시를 안 쓰고 실제 파일을 받는지 검증 가능"},
        ],
    },
    {
        "version": "0.8.14",
        "date": "2026-06-09",
        "changes": [
            {"type": "added", "text": "네트워크 속도 설정에 '자동 설정' 버튼 — Spine 지정 후 누르면 가장 많은 Leaf가 공통으로 프록시하는 자산을 찾아 '이 자산으로 설정할까요?' 확인 후 저장소·경로 자동 입력"},
            {"type": "added", "text": "후보 찾기·자동 설정·연결 테스트·측정 진행 중 메시지에 경과 시간을 5초마다 표시(멈춘 게 아님을 안내)"},
        ],
    },
    {
        "version": "0.8.13",
        "date": "2026-06-09",
        "changes": [
            {"type": "changed", "text": "후보 파일 찾기를 5개씩 탐색하고 '더 찾기'로 이어가도록 변경 — 큰 저장소에서 빠르게 응답(이어가기 커서)"},
            {"type": "changed", "text": "Spine 저장소를 지정하면 그 저장소를 정확히 프록시하는 Leaf만 매칭 — 자산을 바꾸면 연결 테스트 결과·사유가 정확히 갱신되도록 수정"},
        ],
    },
    {
        "version": "0.8.12",
        "date": "2026-06-05",
        "changes": [
            {"type": "added", "text": "릴리스에 zip 압축본 추가 — 오프라인 번들(nexus-manager-offline.zip)과 소스(nexus-manager-src.zip)를 tar.gz와 함께 자동 생성·게시"},
        ],
    },
    {
        "version": "0.8.11",
        "date": "2026-06-05",
        "changes": [
            {"type": "added", "text": "Spine 연결 테스트 결과에서 측정할 서버를 체크해 '측정 대상으로 저장' — 이후 '지금 측정'과 자동 측정이 선택한 서버만 실행(instances.yaml 저장)"},
        ],
    },
    {
        "version": "0.8.10",
        "date": "2026-06-05",
        "changes": [
            {"type": "added", "text": "네트워크 속도 '지금 측정' 시 진행 상황 팝업 — 어떤 서버를 측정 중인지(대기 중→측정 중→완료 Mbps/실패 사유)를 순차로 실시간 표시"},
            {"type": "changed", "text": "측정을 서버(Leaf)별로 나눠 호출(throughput-run-one)하도록 변경해 진행률·서버별 결과를 즉시 확인"},
        ],
    },
    {
        "version": "0.8.9",
        "date": "2026-06-05",
        "changes": [
            {"type": "added", "text": "네트워크 속도 설정에 'Spine 연결 테스트' 버튼 — 매니저→Spine 연결과 각 Leaf의 Spine 프록시·자산 접근 가능 여부를 측정 없이 사전 점검(서버별 ✓/✗·사유 표시)"},
        ],
    },
    {
        "version": "0.8.8",
        "date": "2026-06-05",
        "changes": [
            {"type": "added", "text": "네트워크 속도: 측정 실패한 Leaf에 사유 표시 (프록시 못 찾음/HTTP 404·401/연결 오류 등) — '지금 측정' 결과에 서버별 진단 포함"},
        ],
    },
    {
        "version": "0.8.7",
        "date": "2026-06-05",
        "changes": [
            {"type": "changed", "text": "네트워크 속도 설정 흐름을 ① Spine 서버 선택 → ② 측정 크기 입력 → ③ 후보 파일 찾기 순으로 재배치"},
            {"type": "changed", "text": "후보 파일 탐색을 '지정 크기 이상'(상한 없음)으로 변경, 지정 크기에 가까운 것부터 정렬"},
        ],
    },
    {
        "version": "0.8.6",
        "date": "2026-06-05",
        "changes": [
            {"type": "changed", "text": "네트워크 속도를 Spine→Leaf 방식으로 재구성 — Spine 1대를 기준으로, 각 Leaf 프록시가 Spine에서 자산을 끌어오는 시간(캐시미스−캐시히트 차분)으로 순수 Spine→Leaf 전송 속도 측정"},
            {"type": "added", "text": "서버 설정에서 Spine 서버를 고르면 Spine의 30~50MB 파일을 자동 탐색해 목록에서 선택(저장소·경로 자동 입력)"},
            {"type": "changed", "text": "측정 시 Leaf 캐시 자산을 삭제해 매번 강제 재전송(반복 측정 정확도 확보)"},
        ],
    },
    {
        "version": "0.8.5",
        "date": "2026-06-05",
        "changes": [
            {"type": "added", "text": "네트워크 속도 탭 — 각 서버의 공통 자산(약 30MB)을 8081 포트로 내려받아 처리량(Mbps)을 측정, 1년간 누적·1/7/30/90/365일 차트"},
            {"type": "added", "text": "서버 설정에 네트워크 속도 측정 설정(자산 경로·측정 시각·크기·임계치) 및 '지금 측정' 버튼 추가"},
            {"type": "added", "text": "처리량 차트는 평소(중앙값) 대비 -20% 노랑·-50% 빨강(느릴수록 경고)으로 표시"},
        ],
    },
    {
        "version": "0.8.4",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "인프라 체크 차트를 그룹별로 묶어 3열(각 1/3) 그리드로 배치"},
        ],
    },
    {
        "version": "0.8.3",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "개요: 카드 골격을 즉시 표시하고 상태 데이터는 도착 시 채우도록 변경(체감 로딩 속도 개선)"},
        ],
    },
    {
        "version": "0.8.2",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "인프라 체크 차트에 마우스를 올리면 가장 가까운 측정점의 시간·값 툴팁(+십자선) 표시"},
        ],
    },
    {
        "version": "0.8.1",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "서버 설정에서 Ping 측정 주기·색상 임계치(노랑/빨강 %)를 조정 (instances.yaml 저장)"},
        ],
    },
    {
        "version": "0.8.0",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "인프라 체크 탭 — 각 서버 Ping(TCP 지연)을 1년간 누적, 1/7/30/90/365일 차트 조회"},
            {"type": "added", "text": "Ping 차트에 평소(중앙값) 대비 +20% 노랑·+50% 빨강 색상 표시"},
        ],
    },
    {
        "version": "0.7.2",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "저장소 드롭다운·저장소 관리 목록을 이름순으로 정렬"},
        ],
    },
    {
        "version": "0.7.1",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "비교 매트릭스의 비교 기준 항목(포맷·유형·원격 URL·온라인)을 설정에서 선택, 선택 항목만으로 drift 판단"},
        ],
    },
    {
        "version": "0.7.0",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "서버 설정 화면을 카드(박스)로 묶어 가독성 향상"},
            {"type": "changed", "text": "'새 서버 추가' 폼은 버튼을 눌렀을 때만 표시"},
            {"type": "added", "text": "About 메뉴 추가, 변경 이력을 About으로 이동"},
            {"type": "changed", "text": "변경 이력은 최근 5개만 표시하고 '더 보기'로 나머지 확인"},
        ],
    },
    {
        "version": "0.6.5",
        "date": "2026-06-04",
        "changes": [
            {"type": "removed", "text": "상단 전역 인스턴스 선택 박스 제거"},
            {"type": "added", "text": "저장소 관리·정리 정책 탭에 각자 서버 선택 추가(자립)"},
        ],
    },
    {
        "version": "0.6.4",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "Blob Store 사용량 표의 숫자 열(사용량·가용 공간·사용률·Blob 수) 중앙 정렬"},
        ],
    },
    {
        "version": "0.6.3",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "버전별 릴리스 압축본 파일명에 버전 포함(nexus-manager-offline-vX.Y.Z.tar.gz); latest는 안정 URL 유지"},
            {"type": "added", "text": "변경(푸시)마다 버전별 압축본을 새로 생성·보존"},
        ],
    },
    {
        "version": "0.6.2",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "릴리스 압축본에 버전 표시 파일 ver_<버전>.md 포함 및 릴리스 자산으로 업로드"},
            {"type": "changed", "text": "latest 릴리스 제목·설명이 현재 버전을 반영하도록 자동 갱신"},
        ],
    },
    {
        "version": "0.6.1",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "서버 설정에서 개요 그룹 표시 순서 조정(▲▼) — instances.yaml에 저장"},
        ],
    },
    {
        "version": "0.6.0",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "인스턴스 그룹 지정(서버 설정)과 개요의 그룹별 상태 표시"},
        ],
    },
    {
        "version": "0.5.5",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "개요는 인스턴스 상태만 표시"},
            {"type": "added", "text": "'Blob Store'와 'JVM / 리소스'를 별도 메뉴(탭)로 분리 (개요–토폴로지 사이)"},
        ],
    },
    {
        "version": "0.5.4",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "개요의 상태 배지(주의/연결불가/정상) 클릭 시 원인(실패한 health 점검·연결 에러) 팝업 표시"},
        ],
    },
    {
        "version": "0.5.3",
        "date": "2026-06-04",
        "changes": [
            {"type": "changed", "text": "다운로드 현황 요약 표 중앙 정렬, 열 머리글 클릭 정렬 명확화"},
            {"type": "changed", "text": "진행 조회 시 포맷/유형이 '?/?'로 깨지던 문제 수정"},
        ],
    },
    {
        "version": "0.5.2",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "버전(푸시)마다 오프라인 번들·소스 압축본을 자동 생성하는 릴리스 워크플로(GitHub Actions)"},
        ],
    },
    {
        "version": "0.5.1",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "서버 설정 상단에 '변경 이력 보기' 버튼(메뉴) 추가 — 클릭 시 이력 팝업"},
        ],
    },
    {
        "version": "0.5.0",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "서버 설정 화면에 변경 이력(History) 섹션 추가"},
            {"type": "changed", "text": "수정·업데이트마다 버전을 올리고 변경 이력을 기록하는 정책 적용"},
        ],
    },
    {
        "version": "0.4.0",
        "date": "2026-06-04",
        "changes": [
            {"type": "added", "text": "서버 설정 탭 — 대시보드에서 Nexus 서버 추가/수정/삭제 (instances.yaml 자동 저장)"},
            {"type": "added", "text": "서버 추가 시 실제 연결 확인 후 등록"},
            {"type": "added", "text": "서버별 모니터링/비교 사용 여부 토글, 기준(원본) 서버 별표 지정"},
            {"type": "added", "text": "서버 목록 내보내기(YAML 백업)/가져오기(전체 교체·병합)"},
            {"type": "added", "text": "릴리스 노트 화면, 제목 옆 버전 표시"},
            {"type": "added", "text": "폐쇄망(오프라인) 배포 가이드·스크립트, Rocky/CentOS 7 안내"},
            {"type": "changed", "text": "비교 매트릭스: 기준 서버 지정 반영, ≠ 셀에 기준↔이 서버 차이 표시"},
            {"type": "changed", "text": "비교/토폴로지 화면 전체 너비 사용·셀 폭 제한으로 잘림 해결"},
            {"type": "changed", "text": "다운로드 현황: [시작] 버튼으로만 조회, 열 정렬·조회불가 숨기기, 동시 스캔 제한"},
            {"type": "changed", "text": "다운로드 현황: 전체 목록 먼저 표시 후 5개씩 순차 조회·갱신(진행률 표시)"},
        ],
    },
    {
        "version": "0.3.0",
        "date": "2026-06-03",
        "changes": [
            {"type": "added", "text": "토폴로지 탭 — 프록시 연결 구조 도출 및 끊긴 링크(Auto-block) 감지"},
            {"type": "added", "text": "작업(Tasks) 탭 — 스케줄 작업 상태·실행/중지(Compact, Cleanup)"},
            {"type": "added", "text": "보안 점검 탭 — 익명 접근·기본 admin·관리자 권한 계정 점검"},
            {"type": "added", "text": "콘텐츠 동기화 탭 — 사이트 간 실제 컴포넌트 비교"},
            {"type": "added", "text": "개요 — 노드별 JVM/힙/스레드 메트릭"},
            {"type": "added", "text": "알림 탭 — 노드 다운·Heap·디스크 임계치 + Slack/Webhook 푸시"},
        ],
    },
    {
        "version": "0.2.0",
        "date": "2026-06-02",
        "changes": [
            {"type": "added", "text": "다운로드 현황 탭 — 서버별 요약 + 저장소별 실사용 패키지·용량"},
            {"type": "added", "text": "저장소 1:1 비교 탭 및 항목별 상세 비교(이름 클릭)"},
            {"type": "added", "text": "개요 — Blob 사이트별 사용량·총합·사용률(임계치) 경고"},
            {"type": "changed", "text": "'저장소' 탭을 '저장소 관리'로 이름 변경(비교 탭과 구분)"},
        ],
    },
    {
        "version": "0.1.0",
        "date": "2026-06-01",
        "changes": [
            {"type": "added", "text": "초기 릴리스 — 여러 Nexus 인스턴스 통합 대시보드"},
            {"type": "added", "text": "저장소 관리, 정리(Cleanup) 정책, 상태 모니터링"},
            {"type": "added", "text": "비교 매트릭스 — 저장소 구성 드리프트 비교"},
        ],
    },
]
