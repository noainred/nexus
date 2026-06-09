"""In-app release notes / changelog.

Each entry groups changes as added / changed / removed. The newest version
must stay first and match ``app.__version__``.
"""
from __future__ import annotations

RELEASE_NOTES = [
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
