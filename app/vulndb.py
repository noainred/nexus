"""Known Sonatype Nexus Repository 3 vulnerabilities, matched by version.

The security-posture scan reads each managed instance's version (from the
``Server`` response header) and flags it against this list, so an operator sees
"this node runs a version exposed to CVE-xxxx" at a glance.

Version comparison is numeric on the ``X.Y.Z`` release tuple; the build suffix
(e.g. ``-04``) and edition (OSS/PRO) are ignored. Sources: Sonatype security
advisories (support.sonatype.com / help.sonatype.com/en/security-advisories).
"""

import re
from typing import Dict, List, Optional, Tuple

_VER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

# Each rule flags a version V where ``intro <= V <= last_vuln``.
#   intro      : first affected release (use (0,0,0) for "any up to last_vuln")
#   last_vuln  : last affected release (inclusive)
#   fixed      : human-readable first fixed version / guidance
_CVES: List[dict] = [
    {
        "id": "CVE-2024-4956",
        "severity": "critical",
        "summary": "인증 불필요 Path Traversal/LFI — URL 조작으로 시스템 파일 다운로드(PoC 공개)",
        "intro": (0, 0, 0),
        "last_vuln": (3, 68, 0),
        "fixed": "3.68.1",
    },
    {
        "id": "CVE-2024-5764",
        "severity": "high",
        "summary": "기본값으로 하드코딩된 암호화 패스프레이즈(설정 DB 시크릿 암호화)",
        "intro": (0, 0, 0),
        "last_vuln": (3, 72, 0),
        "fixed": "3.73.0",
    },
    {
        "id": "CVE-2025-13488",
        "severity": "medium",
        "summary": "Stored XSS — 업로드 콘텐츠에 보안 헤더 미적용(업로드 권한 보유자)",
        "intro": (3, 83, 0),
        "last_vuln": (3, 83, 99),
        "fixed": "최신 패치 적용 확인",
    },
]


def parse_version(text: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Extract the first ``X.Y.Z`` triple from a version/Server-header string."""
    if not text:
        return None
    m = _VER_RE.search(text)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def scan_version(text: Optional[str]) -> List[Dict[str, str]]:
    """Return the CVEs that affect the given version string (newest data wins).

    Empty list when the version is unknown/unparseable — callers must treat
    "no version" as "not scanned", never as "safe".
    """
    v = parse_version(text)
    if v is None:
        return []
    hits: List[Dict[str, str]] = []
    for c in _CVES:
        if tuple(c["intro"]) <= v <= tuple(c["last_vuln"]):
            hits.append({
                "id": c["id"],
                "severity": c["severity"],
                "summary": c["summary"],
                "fixed": c["fixed"],
            })
    return hits
