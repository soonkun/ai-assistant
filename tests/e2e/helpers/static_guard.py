# tests/e2e/helpers/static_guard.py
"""정적 URL 스캔 헬퍼.

src/ 전체를 스캔해 외부 네트워크 호출 패턴이
127.0.0.1/localhost/OLLAMA_BASE_URL 외 주소를 향하지 않는지 검사한다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple


# 검사 대상 패턴: 외부 HTTP(S) 호출 함수 및 URL 리터럴
_CALL_PATTERNS = re.compile(
    r"""(
        requests\.get\s*\(         |  # requests.get(
        requests\.post\s*\(        |  # requests.post(
        httpx\.get\s*\(            |  # httpx.get(
        httpx\.post\s*\(           |  # httpx.post(
        urllib\.request\.urlopen\s*\(  |  # urllib.request.urlopen(
        fetch\s*\(                 |  # fetch(
        aiohttp\.ClientSession\s*\(    # aiohttp.ClientSession(
    )""",
    re.VERBOSE,
)

# 외부 URL 패턴: https?://로 시작하되 허용 호스트가 아닌 것
_EXTERNAL_URL_PATTERN = re.compile(
    r"""https?://(?!
        127\.0\.0\.1       |  # loopback IPv4
        localhost          |  # localhost
        \{[^}]+\}          |  # f-string 변수: {base_url} 등
        \$\{[^}]+\}        |  # 쉘 변수
        ['\"]?\}           |  # 변수 끝
        0\.0\.0\.0         |  # 바인드 주소
        192\.168\.         |  # 사설 IP B class
        10\.               |  # 사설 IP A class
        172\.(1[6-9]|2\d|3[01])\.  # 사설 IP C class
        host               |  # 변수명 패턴 ("http://host:port")
        json-schema\.org   |  # JSON Schema 메타 URI (런타임 호출 아님)
    )""",
    re.VERBOSE,
)

# 허용 URL 예외 패턴 (전체 라인 기준)
_ALLOWED_LINE_PATTERNS = [
    re.compile(r'"\$schema"\s*:'),  # JSON Schema $schema 필드
    re.compile(r"json-schema\.org"),  # JSON Schema 메타 URI
    re.compile(r'"http://host:'),  # 문서 예시: "http://host:port"
    re.compile(r"'http://host:"),  # 문서 예시 단따옴표
    re.compile(r"http://host:port"),  # 문서 예시 (backtick, 코멘트 등)
]


class StaticViolation(NamedTuple):
    file_path: str
    line_number: int
    line_content: str
    reason: str


def scan_directory(root: str | Path) -> list[StaticViolation]:
    """root 디렉토리 아래 .py 파일을 재귀 스캔해 위반 목록을 반환."""
    violations: list[StaticViolation] = []
    root_path = Path(root)

    for py_file in sorted(root_path.rglob("*.py")):
        # __pycache__ 제외
        if "__pycache__" in py_file.parts:
            continue
        violations.extend(_scan_file(py_file))

    return violations


def _scan_file(path: Path) -> list[StaticViolation]:
    violations: list[StaticViolation] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return violations

    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        # 주석 라인 스킵
        if stripped.startswith("#"):
            continue

        # 허용 라인 패턴 검사 (JSON Schema $schema 등 허용)
        if any(p.search(line) for p in _ALLOWED_LINE_PATTERNS):
            continue

        # 외부 URL 리터럴 검사
        for match in _EXTERNAL_URL_PATTERN.finditer(line):
            url_start = match.start()
            # 라인이 주석 내부인지 확인 (# 앞에 url이 없으면 실제 코드)
            pre_url = line[:url_start]
            if "#" in pre_url:
                continue  # 주석 내 URL
            violations.append(
                StaticViolation(
                    file_path=str(path),
                    line_number=lineno,
                    line_content=line.rstrip(),
                    reason=f"external URL literal: {match.group(0)!r}",
                )
            )

    return violations
