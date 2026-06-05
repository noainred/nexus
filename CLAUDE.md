# 프로젝트 메모

## 대화/응답 규칙
- **모든 답변은 한글로 작성한다.** (사용자 요청, 2026-06-05)

## 프로젝트 개요
Sonatype Nexus Repository 여러 인스턴스를 한곳에서 모니터링·비교·관리하는 대시보드.
폐쇄망(인터넷 불가) 환경에 배포: FastAPI + 순수 JS SPA(프레임워크/CDN 사용 안 함).
서버에는 8081(HTTP) 포트만 열려 있다고 가정한다.

## 코드 규칙
- Python 3.9 호환 필수 (PEP 604 `X | None` 평가형 어노테이션 금지, `Optional[...]` 사용).
- 변경/업데이트마다 `app/__init__.py`의 `__version__`을 올리고
  `app/release_notes.py`의 `RELEASE_NOTES` 맨 앞에 항목을 추가한다(테스트가 일치 검증).
