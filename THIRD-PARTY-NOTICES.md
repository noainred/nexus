# 제3자 오픈소스 고지 · Third-Party Notices

본 제품(Nexus Repository 통합 관리)은 아래 오픈소스 구성요소를 포함하거나 함께
배포합니다. 각 구성요소는 해당 라이선스(모두 OSI 승인 허용형: MIT / BSD / Apache-2.0)
조건에 따라 사용됩니다. 각 패키지의 전체 라이선스 전문은 오프라인 번들의 `wheelhouse/`
안에 포함된 각 배포본(wheel)의 메타데이터(`*.dist-info/`)에 포함되어 있습니다.

This product includes/distributes the open-source components below, each used
under its respective permissive license (MIT / BSD / Apache-2.0). The full
license text of each package is included in its wheel metadata
(`*.dist-info/`) inside the offline bundle's `wheelhouse/`.

## 직접 의존성 · Direct dependencies

| 구성요소 | 라이선스 | 프로젝트 |
|---|---|---|
| FastAPI | MIT | https://github.com/fastapi/fastapi |
| Starlette | BSD-3-Clause | https://github.com/encode/starlette |
| Uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn |
| HTTPX | BSD-3-Clause | https://github.com/encode/httpx |
| HTTPCore | BSD-3-Clause | https://github.com/encode/httpcore |
| Pydantic | MIT | https://github.com/pydantic/pydantic |
| pydantic-core | MIT | https://github.com/pydantic/pydantic-core |
| pydantic-settings | MIT | https://github.com/pydantic/pydantic-settings |
| PyYAML | MIT | https://github.com/yaml/pyyaml |

## 전이 의존성 · Transitive dependencies

uvicorn[standard] 및 위 패키지들이 끌어오는 전이 의존성(anyio, sniffio, h11, idna,
certifi, click, typing-extensions, annotated-types, python-dotenv, h2/hpack,
httptools, uvloop, watchfiles, websockets 등)을 포함합니다. 각 패키지는 MIT, BSD,
또는 Apache-2.0 등 허용형 라이선스를 따르며, 전체 라이선스 전문은 `wheelhouse/`의
해당 `*.dist-info/` 에 포함됩니다.

> 참고: 본 제품의 자체 코드는 독점 라이선스입니다(LICENSE 참조). 위 제3자 구성요소는
> 각자의 오픈소스 라이선스를 그대로 유지합니다.
