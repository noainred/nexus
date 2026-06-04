"""In-app release notes / changelog.

Each entry groups changes as added / changed / removed. The newest version
must stay first and match ``app.__version__``.
"""
from __future__ import annotations

RELEASE_NOTES = [
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
