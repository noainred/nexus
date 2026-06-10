"""In-app release notes / changelog.

Each entry groups changes as added / changed / removed. The newest version
must stay first and match ``app.__version__``.
"""
from __future__ import annotations

RELEASE_NOTES = [
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
