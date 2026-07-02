"""In-app release notes / changelog.

Each entry groups changes as added / changed / removed. The newest version
must stay first and match ``app.__version__``.
"""
from __future__ import annotations

RELEASE_NOTES = [
    {
        "version": "1.7.40",
        "date": "2026-06-20",
        "changes": [
            {"type": "changed", "text": "[안정성] 크래시 안전 저장 도입(app/storage.py) — 설정/토큰/레이아웃 파일과 ping·disk 이력 정리(prune/purge)를 임시파일+fsync+os.replace 원자적 쓰기로 변경. 정전·강제종료 중 저장이 겹쳐도 공유 설정이 깨지지 않음(instances.yaml, update-config, access-log-config, column-order, topo-layout, portal-config, ping/disk CSV)"},
            {"type": "changed", "text": "[보안] 자격증명 파일 권한 강화 — 노드 비밀번호가 담긴 instances.yaml을 0600으로 저장, 감사 로그(audit.log)도 0600 생성. 자동업데이트 토큰(GitHub PAT)은 포탈 백업(_portal.json)에 평문으로 담기지 않도록 마스킹(복원 시 재입력)"},
            {"type": "changed", "text": "[버그] 노드 삭제 시 disk 이력 행도 정리 — 기존에는 ping 이력·상태 캐시만 지우고 disk-history CSV의 행이 영구 누적되던 것을 diskmon.purge로 함께 제거"},
            {"type": "changed", "text": "[최적화] 네트워크 체크 로딩 개선 — ping 시계열 파싱을 고정형식 정수 파싱으로 대체(대량 구간 strptime 오버헤드 제거). disk 이력은 파일 변경(mtime/size) 기준 파싱 캐시를 두어 예측/이력 화면의 반복 조회 시 전체 CSV 재파싱을 생략"},
        ],
    },
    {
        "version": "1.7.39",
        "date": "2026-06-20",
        "changes": [
            {"type": "changed", "text": "보안 점검 후속 — 알림 웹훅·토폴로지 원격 프로브·자동업데이트 버전조회/엣지조회의 외부 HTTP 호출이 TLS 인증서 검증을 무조건 끄던(verify=False) 것을 설정값(NEXUS_MANAGER_VERIFY_TLS, 기본 true)을 따르도록 통일. 특히 자동업데이트가 Bearer 토큰을 검증 없이 보내던 중간자(MITM) 토큰 탈취·가짜 버전 응답 위험을 제거(사내 자체서명 인증서 환경은 false로 옵트아웃)"},
        ],
    },
    {
        "version": "1.7.38",
        "date": "2026-06-20",
        "changes": [
            {"type": "added", "text": "취약 버전 탐지기 — 보안 점검에서 각 Nexus 인스턴스의 버전(Server 헤더)을 읽어 알려진 CVE(CVE-2024-4956 Path Traversal, CVE-2024-5764 하드코딩 암호화 키, CVE-2025-13488 Stored XSS) 룰과 대조해 ⚠️ CVE 뱃지·'취약 버전' 항목으로 표시(버전 미확인 시 '미스캔'으로 안전 단정 안 함). 요약 카드에 '취약 버전(CVE)' 추가"},
            {"type": "changed", "text": "보안 강화 — ① 모든 응답에 보안 헤더(X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy, CSP frame-ancestors 'none') 추가(클릭재킹·MIME 스니핑 방어). ② 세션 쿠키를 만료시각이 서명에 포함된 토큰으로 변경해 유출 시 TTL(12h) 경과 후 자동 무효화(비밀번호 변경 시 전체 무효화는 유지). ③ 로그인 브루트포스 레이트리밋(IP당 5분 내 8회 실패 시 429)"},
        ],
    },
    {
        "version": "1.7.37",
        "date": "2026-06-20",
        "changes": [
            {"type": "added", "text": "납품용(대외 배포) 준비 — 독점 소프트웨어 라이선스(LICENSE, 한/영)와 제3자 오픈소스 고지(THIRD-PARTY-NOTICES.md)를 추가하고 오프라인 번들에 포함"},
            {"type": "added", "text": "보안 기본값 — 설치 스크립트(install-service.sh)가 .env에 관리자 비밀번호가 없으면 무작위 비밀번호를 자동 생성해 출력하고, 비밀번호 미설정으로 기동 시 서버 로그에 보안 경고를 남김"},
            {"type": "changed", "text": "다운로드 로그 by-instance 경로에 경로 탈출(path traversal) 가드 추가 — 인스턴스 id/name/host에 '/'·'\\\\'·'..'가 포함되면 거부"},
            {"type": "changed", "text": "납품 문서 내부 정보 치환 — 사내 Nexus 호스트/IP·개발 브랜치명을 placeholder(<INTERNAL-NEXUS-HOST>·<NEXUS-IP>·main)로 변경"},
        ],
    },
    {
        "version": "1.7.36",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "다운로드 추적(IP)에서 Nexus 서버를 선택하면 매니저가 그 서버의 request.log를 직접 읽어 분석(by-instance). 설정 → 모니터링·백업에 '서버별 로그 경로 템플릿'({id}/{name}/{host} 치환)과 고정 경로를 지정하는 항목 추가(access-log-config.json 저장)"},
            {"type": "changed", "text": "상단 메뉴 '서버 설정'을 '설정'으로 이름 변경하고, 'About'을 별도 탭에서 설정의 하위 메뉴(서브탭)로 이동"},
        ],
    },
    {
        "version": "1.7.35",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "About(소개) 화면을 새로 디자인 — 그라데이션 히어로(제목·버전·기술 뱃지), 저작자/저작권 카드, 주요 기능(KEY FEATURES) 2단 그리드, 저작권 고지 박스, 푸터를 추가해 멋지게 구성. 저작자 박준호(noainred@lgcns.com)·© 2026 표기"},
        ],
    },
    {
        "version": "1.7.34",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "네트워크 체크(서버 Ping) 화면 로딩 속도 개선 — ① 그룹·차트 자리(프레임)를 즉시 표시하고 데이터가 오면 채운다(빈 '불러오는 중' 제거). ② 서버가 1년치 ping CSV 전체를 읽지 않고 파일 끝에서부터 필요한 최근 구간만 읽도록(tail-read) 변경해, 1일/7일 보기가 파일 크기와 무관하게 빨라진다"},
        ],
    },
    {
        "version": "1.7.33",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "계위 상황판(토폴로지) 노드 배치를 서버에 저장해 모든 사용자가 동일한 배치를 보도록 변경 — 한 사람이 드래그로 배치하면 전체 노드 좌표가 서버(topo-layout.json)에 저장되고, 다른 브라우저/사용자도 같은 배치로 로드된다. '배치 초기화'는 공통 배치를 자동 배치로 되돌린다(localStorage는 빠른 폴백)"},
        ],
    },
    {
        "version": "1.7.32",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "서버 설정(노드 관리) 화면의 서버 목록이 뜨는 데 오래 걸리던 문제 개선 — 이미 로딩된 인스턴스 목록(캐시)으로 표를 즉시 그리고, 서버 갱신은 백그라운드로 처리한다. 매니저 재시작 직후 서버가 바빠도 목록이 바로 보인다"},
        ],
    },
    {
        "version": "1.7.31",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "다운로드 추적(IP)을 서버에서 자동 분석 — 매니저가 접근 가능한 request.log를 직접 읽어 IP별 다운로드를 분석한다(파일 업로드 불필요). 설정 request_log_paths(env NEXUS_MANAGER_REQUEST_LOG_PATHS, '라벨=경로' 콤마/줄 구분, glob·.gz 지원)에 등록한 경로만 읽으며, 다운로드 추적 탭의 '서버 로그' 드롭다운에서 선택해 분석한다. /api/access-log/sources·/analyze 엔드포인트 추가(허용 경로만, 경로 탈출 차단)"},
        ],
    },
    {
        "version": "1.7.30",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "'다운로드 추적(IP)' 탭 추가 — Nexus 접속 로그(request.log)를 불러오면 어느 IP가 어떤 패키지를 받아갔는지 분석한다. 최근 접속 IP 목록(다운로드 수·마지막 시각·주요 저장소)을 보여주고, IP를 입력/클릭하면 그 IP가 받은 패키지(시각·저장소·경로·크기)를 나열한다. 저장소 필터 지원, .gz 로그도 지원(브라우저 해제). 로그는 브라우저에서만 처리되어 서버로 전송되지 않음(GET 200/206만 다운로드로 집계)"},
        ],
    },
    {
        "version": "1.7.29",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "집계 정보 제공 API 추가 — GET /api/summary (공개, 인증 불필요)가 전체 서버 수·정상/주의/다운 집계·그룹별 현황·저장소 합계·평균 응답시간·서버별 상태를 JSON으로 반환한다. 백그라운드 상태 캐시 기반이라 즉시 응답하며, 다른 서버/시스템이 폴링해 이 대시보드 현황을 가져갈 수 있다"},
            {"type": "changed", "text": "업데이트 안내 팝업을 첫 방문 시에도 무조건 표시하도록 변경(이전엔 재방문·버전 변경 시에만)"},
        ],
    },
    {
        "version": "1.7.28",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "업그레이드 후 첫 접속 시 '새 버전 안내' 팝업 표시 — 버전이 올라가면 각 사용자(브라우저)마다 한 번씩 최신 변경사항을 팝업으로 알려준다(확인 시 닫힘, 다음 업그레이드 때 다시 표시). 헤더 vX.Y.Z 배지를 누르면 전체 릴리스 노트를 다시 볼 수 있다"},
        ],
    },
    {
        "version": "1.7.27",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "메뉴 표시 설정이 저장해도 반영되지 않던 문제 보완 — 저장 즉시 화면에 적용하고 localStorage에도 저장한다. 백엔드가 아직 옛 버전(hidden_tabs 미지원)이어도 브라우저에서 메뉴 숨김이 동작하며, 백엔드가 새 버전이면 서버 저장값을 우선 적용"},
        ],
    },
    {
        "version": "1.7.26",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "상단 메뉴(탭)를 사용자가 선택해 보이게 — 서버 설정 → 일반 → '메뉴(탭) 표시 설정'에서 탭별 체크로 표시/숨김을 지정한다. 설정은 서버에 저장(portal-config.json)되어 모든 사용자/브라우저에 동일 적용. '개요'와 '서버 설정'은 항상 표시"},
        ],
    },
    {
        "version": "1.7.25",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "팝업(모달)을 헤더를 잡고 드래그해 이동할 수 있게 함 — 저장소 설정 비교 팝업과 일괄 적용·드래그 복사 진행 팝업 모두 적용. 헤더의 닫기(✕)·체크박스 등 컨트롤 클릭은 그대로 동작"},
        ],
    },
    {
        "version": "1.7.24",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "비교 매트릭스에서 표를 아래로 스크롤하면 상단의 범례·설명문이 자동으로 숨겨져 표 영역이 넓어지고, 다시 맨 위로 스크롤하면 나타난다"},
        ],
    },
    {
        "version": "1.7.23",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "일괄 적용 시 진행 상태를 큰 팝업으로 표시 — 전체 진행률(X/Y)·진행바·서버별 성공/실패와, '팝업을 닫아도 이 브라우저 탭에서 백그라운드로 계속, 탭을 닫으면 중단' 안내 포함"},
            {"type": "added", "text": "매트릭스 셀을 드래그해 복사할 때 단계별 진행 팝업 표시 — '원본 접속 → 설정 읽기 → 대상 연결 → 복사 → 완료' 단계를 보여주고, 창을 닫아도 계속 진행되며 완료 시 결과를 팝업/알림으로 안내"},
        ],
    },
    {
        "version": "1.7.22",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "일괄 적용의 '대상' 서버 선택을 명확하게 개선 — 한 줄로 붙어 헷갈리던 체크박스를 '서버명(위) + 체크박스(아래)' 카드 형태로 바꿔, 어느 체크박스가 어느 서버인지 분명해졌다. 카드 전체를 클릭해도 토글되고 선택된 카드는 강조 표시"},
        ],
    },
    {
        "version": "1.7.21",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "비교 매트릭스(및 콘텐츠 동기화) 표에서 아래로 스크롤해도 열 헤더가 상단에 고정되도록 수정 — 표 영역에 높이를 주어 본문만 스크롤되고 헤더(및 좌측 저장소 열)는 sticky로 유지. 헤더가 페이지와 함께 사라지던 문제 해결"},
        ],
    },
    {
        "version": "1.7.20",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "비교 매트릭스 열(인스턴스) 순서를 직접 지정·저장 — 열 헤더를 드래그해 순서를 바꾸면 서버에 저장(column-order.json)되어 어느 브라우저/세션에서 열어도 동일한 순서로 불러온다. 기존 인스턴스 칩 드래그도 동일하게 서버 저장. '열 순서 기본값' 버튼으로 초기화"},
        ],
    },
    {
        "version": "1.7.19",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "상태 캐시를 노드별로 즉시 갱신하고, 온디맨드 조회는 ping까지만(저장소 목록 제외) 빠르게 반환하도록 변경 — ping 응답이 오는 노드부터 카드가 채워진다(저장소 수는 백그라운드 폴러가 곧 채움). 재시작 직후에도 빠른 노드부터 표시"},
            {"type": "changed", "text": "상단 메뉴 순서 변경 및 '인프라 체크'를 '네트워크 체크'로 이름 변경 — 개요 · 인스턴스 상태 · 네트워크 체크 · 토폴로지 · 비교 매트릭스 · 저장소 관리 · 다운로드 현황 순으로 앞배치, 나머지는 뒤로"},
        ],
    },
    {
        "version": "1.7.18",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "인프라 핑 차트에 삭제한 노드가 '쓰레기'로 다시 나타나던 문제 수정 — 핑 히스토리를 현재 등록된 인스턴스로 필터링하고(과거 CSV에 남은 삭제 노드 숨김), 인스턴스 삭제 시 핑 기록(CSV)과 상태 캐시도 함께 정리(purge)한다. (아직 서버 설정에 등록돼 있는 정크 노드는 그 화면에서 삭제하면 즉시 사라짐)"},
        ],
    },
    {
        "version": "1.7.17",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "계위 상황판 배치가 자꾸 초기화되던 문제 수정 — 한 번이라도 노드를 드래그해 배치하면 그 시점의 모든 노드 좌표를 저장해 '완전 고정'한다. 이후 프록시 구조가 바뀌거나 일부 노드가 잠시 안 닿아도 미드래그 노드가 재배치되지 않는다('배치 초기화' 버튼으로 자동 배치로 되돌림)"},
        ],
    },
    {
        "version": "1.7.16",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "백그라운드 상태 폴러 추가 — 메뉴에 들어갈 때 ping하지 않고, 서버가 20초 주기로 모든 노드를 계속 점검해 캐시에 저장한다. /api/status·/api/instances/{id}/status는 캐시값을 즉시 반환(로딩 즉시 표시)하고, 아직 캐시에 없는 노드만 즉석 점검한다. 최신값이 필요하면 ?fresh=true 로 강제 점검. 응답에 checked_at(측정 시각)·cached 표시"},
        ],
    },
    {
        "version": "1.7.15",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "계위 상황판 로딩 스켈레톤은 최초 로드(트리가 아직 없을 때)에만 표시하도록 변경 — 이미 계위 트리가 그려져 있으면(새로고침·탭 복귀) 기존 배치를 유지하고 스켈레톤으로 깜빡이지 않는다. 스켈레톤은 로딩 중 임시 화면이며 /api/topology 완료 시 저장된 드래그 배치의 계위 트리로 교체됨"},
        ],
    },
    {
        "version": "1.7.14",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "개요 '계위 상황판'이 느린 노드 하나 때문에 빈 화면으로 오래 멈추던 문제 개선 — 모든 노드를 즉시 칩으로 표시하고, 각 노드의 상태가 응답하는 대로 색칠(정상=초록·주의=노랑·다운=빨강)한다. 응답 빠른 노드부터 보이고, 전체 트리(간선 포함)는 /api/topology가 끝나면 교체. 느린 노드는 자기 칩만 늦게 칠해질 뿐 보드를 막지 않음"},
        ],
    },
    {
        "version": "1.7.13",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "느린(고지연) 노드를 기다렸다가 응답오면 '정상'으로 표시 — 상태/연결 점검의 읽기(read) 타임아웃을 request_timeout(기본 15초)로 되돌림(800ms~수초 지연도 응답만 오면 정상). 연결(connect)만 ~6초로 짧게 유지해 진짜 안 닿는 노드는 빠르게 실패. 지연(ms)으로 상태를 깎지 않음(이미 응답하면 reachable·healthy). 카드별 개별 로딩과 함께라 느린 노드 하나가 전체를 묶지 않음"},
        ],
    },
    {
        "version": "1.7.12",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "인스턴스 상태 탭이 '측정 중…'에서 오래 멈추던 문제 개선 — 단일 /api/status(전체 묶음) 응답을 통째로 기다리지 않고, 노드별로 개별 조회해 끝나는 대로 카드를 채운다. 안 닿는 노드 하나가 전체 보드를 묶지 않는다"},
            {"type": "changed", "text": "대시보드 상태 점검 타임아웃을 최대 8초로 단축(connect는 6초) — 느리거나 닿지 못하는 노드가 개요를 끌지 않도록"},
        ],
    },
    {
        "version": "1.7.11",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "포탈 '지금 적용' 버튼이 sudo 없이도 동작하도록 변경 — 매니저(비root)가 $INSTALL_DIR/.update-now 트리거 파일을 기록하면, 새로 추가된 root systemd .path 유닛(nexus-manager-update.path)이 이를 감시해 업데이트를 즉시 실행한다. sudo가 nosuid 마운트로 막힌 환경에서도 버튼이 에러 없이 적용된다(미설치 시엔 타이머가 폴백). install-service.sh가 .path 유닛 등록 + 트리거 파일 정리(ExecStartPre)를 포함"},
        ],
    },
    {
        "version": "1.7.10",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "노드 추가/연결 점검이 느리게 멈추던 문제 개선 — connect 타임아웃을 전체 타임아웃과 분리(최대 6초)해, 매니저가 닿지 못하는 서버(포트 미개방·방화벽·다른 서브넷)는 15초가 아니라 몇 초 만에 실패한다. '서버 추가' 점검은 최대 8초로 단축"},
            {"type": "changed", "text": "연결 실패 원인을 명확히 표시 — '연결 시간 초과(주소·포트·방화벽 확인)' / '연결 실패(포트 미개방·거부)' / 401(계정 오류)을 구분해, 계정 문제인지 네트워크 문제인지 바로 알 수 있게 함"},
        ],
    },
    {
        "version": "1.7.9",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "테스트용 버전 올림 — 1.7.8의 '업그레이드 후 자동 재시작' 수정이 1.7.8→1.7.9 자동 업데이트에서 수동 restart 없이 동작하는지 검증용"},
        ],
    },
    {
        "version": "1.7.8",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "자동 업그레이드 후 서비스가 자동 재시작되지 않던 버그 수정 — install-service.sh가 'systemctl enable --now'(이미 실행 중이면 재시작 안 함) 대신 'enable + restart'를 호출하도록 변경. 이제 업그레이드 시 수동 'systemctl restart nexus-manager' 없이 새 코드로 바로 재시작된다(최초 설치도 정상)"},
        ],
    },
    {
        "version": "1.7.7",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "자동 업그레이드 설정의 안내문 가독성 개선 — 좁은 그리드 칸에 갇혀 긴 URL/코드가 한 글자씩 세로로 흐르던 문제를 해결. 체크박스(저장된 토큰 지우기)와 안내문을 분리하고, 안내문을 전체폭으로 펴 소스별(GitHub/비공개 브랜치 폴더/사내 미러) 입력 예시를 줄바꿈되게 정리(긴 code는 자동 줄바꿈)"},
        ],
    },
    {
        "version": "1.7.6",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "auto-update.sh 원격 조회 실패 버그 수정 — 토큰이 없을 때 빈 배열 \"${auth[@]}\" 가 set -u(bash 4.2, CentOS/RHEL 7)에서 'unbound variable'로 죽어 사내 미러 조회가 매번 '원격 조회 실패'로 끝나던 문제를 ${auth[@]+\"${auth[@]}\"} 안전 확장으로 해결. 토큰 없는 공개/사내 Nexus 미러에서 root 타이머 자동 업데이트가 정상 동작"},
        ],
    },
    {
        "version": "1.7.5",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "포탈 '지금 적용'이 매니저가 root로 실행 중이면 sudo 없이 systemctl을 직접 호출하도록 변경 — /usr/bin/sudo가 nosuid 마운트로 막힌 환경에서도 동작. 실패 메시지에 'root로 systemctl start nexus-manager-update.service 실행 또는 감시 폴더 zip→root 타이머 적용' 안내 추가"},
        ],
    },
    {
        "version": "1.7.4",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "자동 업그레이드 안내에 '사내 Nexus가 GitHub를 proxy하는 경우 …/repository/<proxy>/nexus/releases/download/latest/ 릴리스 폴더를 가리키면 자동으로 읽어온다'는 예시 추가(versions.json은 릴리스에 자동 게시되므로 별도 미러/수동 업로드 불필요). 테스트용 버전 올림"},
        ],
    },
    {
        "version": "1.7.3",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "릴리스 워크플로(release.yml)가 versions.json을 자동 생성해 GitHub 릴리스에 포함 — 더 이상 손으로 만들 필요 없음. latest 릴리스엔 {\"version\":\"X.Y.Z\",\"file\":\"nexus-manager-offline.zip\"}(고정 파일명), 버전별 릴리스엔 versioned 파일명으로 게시"},
            {"type": "changed", "text": "사내 Nexus 미러 스크립트(mirror-to-nexus.sh)가 CI가 만든 versions.json을 그대로 복사하고 안정 파일명(nexus-manager-offline.zip)으로 업로드하도록 통일 — GitHub latest 릴리스 폴더와 1:1로 미러되어 경로/파일명이 항상 일치"},
        ],
    },
    {
        "version": "1.7.2",
        "date": "2026-06-17",
        "changes": [
            {"type": "added", "text": "자동 업그레이드 소스에 'GitHub 브랜치 download 폴더' 방식 추가 — GitHub Release를 만들지 않고도, raw.githubusercontent.com/<owner>/<repo>/<브랜치>/download (또는 github.com/.../tree/<브랜치>/download) 주소를 그대로 넣으면 자동으로 contents API로 변환해 인증 조회한다. 비공개(사설) 레포는 토큰(PAT)을 함께 저장하면 동작하며, 브랜치명에 '/'가 있어도 안전하다. 폴더의 versions.json을 우선 읽고, 없으면 폴더 목록에서 가장 높은 nexus-manager-offline-vX.Y.Z.zip을 자동 선택(앱 버전 확인 + auto-update.sh 다운로드 양쪽 지원)"},
        ],
    },
    {
        "version": "1.7.1",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "자동 업그레이드 원격 확인 시, Nexus raw 저장소의 폴더 브라우징 404('You can't browse this way') 대신 'versions.json을 찾을 수 없습니다 — …/versions.json 을 올리세요'라는 명확한 안내를 표시"},
        ],
    },
    {
        "version": "1.7.0",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "서버 설정 화면을 기능별 서브 탭으로 분리 — 🗄️노드 관리(서버 목록·추가/수정·그룹 순서·비교 기준) / 🔑계정·보안(노드 계정 관리) / ⬆자동 업그레이드 / 📈모니터링·백업(Ping·예약 백업·DR·콘텐츠 동기화) / ⚙일반(대시보드 제목). 길게 하나로 나오던 설정을 메뉴로 정리"},
        ],
    },
    {
        "version": "1.6.2",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "자동 업그레이드 versions.json의 file 값이 하위 폴더 경로(예: v1.6.0/nexus-manager-offline-v1.6.0.zip)여도 동작하도록 워처 보완 — URL은 상대경로로 받고 감시 폴더에는 파일명만 저장. 버전별 폴더로 mirror하는 사내 raw 구조 지원"},
        ],
    },
    {
        "version": "1.6.1",
        "date": "2026-06-17",
        "changes": [
            {"type": "changed", "text": "계위 상황판 간선이 상대 노드 위치에 맞춰 붙는 변을 선택 — 연결된 노드가 위에 있으면 위쪽 변에서, 아래 있으면 아래쪽 변에서 선이 시작/도착하도록 적응형으로 변경(드래그 배치 시 선이 자연스럽게 연결)"},
        ],
    },
    {
        "version": "1.6.0",
        "date": "2026-06-16",
        "changes": [
            {"type": "added", "text": "자동 업그레이드 화면 개편 — '포탈 + 전 엣지' 컴팩트 상태줄(현재/최신/확인 시각/엣지 N대·엣지 모두 최신), '엣지에 보낼 배포 코드'·소스 표기. 엣지(다른 매니저) 목록을 등록하면 각 /healthz로 버전을 감시해 구버전/미응답 엣지를 표시(엣지는 같은 소스를 바라보며 자동 업그레이드)"},
            {"type": "added", "text": "서버 설정의 서버 목록 헤더(이름/식별자/그룹/주소/계정) 클릭 정렬 — 오름/내림 토글, 화살표 표시"},
        ],
    },
    {
        "version": "1.5.1",
        "date": "2026-06-16",
        "changes": [
            {"type": "changed", "text": "보안 점검 최적화 — 인스턴스당 익명/사용자 조회를 병렬화(느린 링크에서 약 2배 빠름)하고, 서버별 위험도(양호/점검 필요/확인 불가)·위험 항목 목록·플릿 요약을 추가. 화면 범례·설명과 README 문서화 보강"},
        ],
    },
    {
        "version": "1.5.0",
        "date": "2026-06-16",
        "changes": [
            {"type": "added", "text": "노드 계정 관리 — 서버 설정에서 선택한 서버(들)에 관리자(nx-admin) 유저 생성 및 기존 사용자 비밀번호 변경(여러 노드 일괄). 매니저 접속 계정의 비번을 바꾸면 저장된 자격증명도 자동 동기화해 잠김 방지. GET /api/accounts/instances/{id}/users · POST /api/accounts/create-admin · /change-password, nexus_client.change_password 추가"},
        ],
    },
    {
        "version": "1.4.4",
        "date": "2026-06-16",
        "changes": [
            {"type": "added", "text": "대시보드 제목을 서버 설정에서 변경 가능 — 상단 제목/브라우저 탭 제목을 원하는 문구로 저장(모든 사용자 공유, 비우면 기본값). GET /api/portal(공개)·PUT /api/portal"},
        ],
    },
    {
        "version": "1.4.3",
        "date": "2026-06-16",
        "changes": [
            {"type": "added", "text": "구성 백업에 '포탈 설정' 백업 추가 — 매 백업 시 매니저 자체 설정(instances.yaml = 서버 목록·그룹·계위·비교기준·ping/백업/동기화 설정 + 자동 업데이트 설정)을 _portal.json으로 함께 저장. 매니저가 소실돼도 전체 설정 복구 가능. (각 Nexus 서버의 저장소 설정은 기존대로 포함됨)"},
        ],
    },
    {
        "version": "1.4.2",
        "date": "2026-06-16",
        "changes": [
            {"type": "added", "text": "deploy/mirror-to-nexus.sh 추가 — GitHub 최신 릴리스를 사내 Nexus raw 저장소로 미러(versions.json + 번들 zip 자동 생성·업로드). 폐쇄망 매니저가 사내 주소(UPDATE_URL)만으로 자동 업그레이드되도록 GitHub 소스와 사내 배포 경로를 조합"},
        ],
    },
    {
        "version": "1.4.1",
        "date": "2026-06-16",
        "changes": [
            {"type": "changed", "text": "계위 상황판이 새 노드 추가/특정 상황에서 빈 화면(작은 점)만 나오던 문제 수정 — 저장된 드래그 좌표 검증이 NaN을 통과시켜(typeof NaN==='number') width/height가 깨지던 버그. 유한값만 허용하도록 강화하고, 좌표 누락 시 자동 배치로 폴백 + 드래그 저장 시에도 NaN 차단"},
        ],
    },
    {
        "version": "1.4.0",
        "date": "2026-06-16",
        "changes": [
            {"type": "added", "text": "인터넷(URL) 자동 업그레이드 설정 UI — 서버 설정 탭에서 소스(Update Server/GitHub)·Site Info(URL)·인증 토큰·확인 주기·자동 설치 여부를 입력·저장. 사내 미러는 versions.json(+번들) 폴더 주소, GitHub는 github:owner/repo(비공개는 토큰) 지원. 설정은 update-config.json에 저장되어 앱과 워처(auto-update.sh)가 공유, 토큰은 화면에 다시 노출하지 않음(마스킹)"},
            {"type": "changed", "text": "구성 백업 목록을 시각별로 접어서 표시 — 시각 줄을 클릭하면 그 시점의 서버별 파일이 펼쳐짐(최신 1건만 기본 펼침)"},
        ],
    },
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
