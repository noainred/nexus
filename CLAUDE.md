# 프로젝트 메모

## 대화/응답 규칙
- **모든 답변은 한글로 작성한다.** (사용자 요청, 2026-06-05)
- **사용자가 `.` 만 입력하면**, 작업 현황을 아래 형식의 표로 보여준다.
  (사용자 요청, 2026-07-20 / 형식 갱신 2026-08-07)
  - 열 구성: **난이도 | 적합 | 실행 | 작업 | 상태 | 비고**
    - 난이도: 높음/중간/낮음. 적합: 작업에 적합한 모델(예: Opus). 실행: 실제 수행 모델.
    - 상태: ✅ 완료 / 🔄 진행중 / ⏳ 대기 이모지로 표시.
    - 비고: 게시/확인 결과, PR·릴리스 링크, 다음 액션 등.
  - 표 아래에 필요 시 진행 상황·발견 사항을 간단한 서술로 덧붙인다.

## 개발 완료 후 자동화 규칙 (사용자 요청, 2026-08-07)
- 개발 작업이 끝나면(버전·릴리스 노트 갱신, 테스트 통과 확인 후) **따로 묻지 않고 자동으로**
  커밋하고 GitHub에 푸시한다. 이후 아래 '릴리스 확인 규칙'에 따라 파이프라인 완료까지 검증해 보고한다.
- 커밋 메시지는 기존 관례를 따른다: `<변경 요약>(v<version>)`, 버전당 커밋 1개.

## 프로젝트 개요
Sonatype Nexus Repository 여러 인스턴스를 한곳에서 모니터링·비교·관리하는 대시보드.
폐쇄망(인터넷 불가) 환경에 배포: FastAPI + 순수 JS SPA(프레임워크/CDN 사용 안 함).
서버에는 8081(HTTP) 포트만 열려 있다고 가정한다.

## 코드 규칙
- Python 3.9 호환 필수 (PEP 604 `X | None` 평가형 어노테이션 금지, `Optional[...]` 사용).
- 변경/업데이트마다 `app/__init__.py`의 `__version__`을 올리고
  `app/release_notes.py`의 `RELEASE_NOTES` 맨 앞에 항목을 추가한다(테스트가 일치 검증).

## 릴리스 확인 규칙 (사용자 요청, 2026-06-09)
- 버전을 올려 푸시한 뒤에는 **항상** 릴리스 워크플로(`release.yml`)의 완료를 확인하고,
  `latest` 릴리스의 `ver_<version>.md` 마커와 zip 자산(`nexus-manager-offline.zip`)이
  현재 `__version__`과 일치하는지 검증해 사용자에게 보고한다.
- 워크플로가 아직 진행 중이면 완료될 때까지 확인한 뒤 결과를 알린다.
- 캐시로 옛 zip이 받아질 수 있으므로, 필요하면 버전 고정 URL
  (`releases/download/v<version>/nexus-manager-offline-v<version>.zip`)을 함께 안내한다.

## 업그레이드 소스 (어디를 바라보나 — 사용자 요청 기억, 2026-08-07)
- 매니저 자동 업데이터는 **`versions.json` + `nexus-manager-offline.zip`이 있는 위치**를
  바라본다. 설정 위치: **대시보드 → 설정 → ⬆ 자동 업그레이드**의 `소스` + `Site Info(URL)`.
- 환경별 지정:
  - 인터넷 직접(GitHub): 소스 `GitHub`, URL `github:noainred/nexus`
  - 폐쇄망·사내 Nexus가 GitHub 릴리스를 프록시(권장): 소스 `Update Server`,
    URL `http://<사내-Nexus>:8081/repository/<프록시>/nexus/releases/download/latest/` (끝에 `/`)
  - 사내 raw 미러(mirror-to-nexus.sh 업로드): 소스 `Update Server`,
    URL `http://<사내-Nexus>:8081/repository/manager-upgrade/nexus-manager/`
- 비공개 GitHub면 인증토큰(PAT) 함께 저장. 저장 후 "지금 확인"→감지, "지금 적용"→설치·재시작.
