# tests/e2e/test_static_guard.py
"""정적 오프라인 가드 — src/ 전체 외부 URL 스캔.

REQUIREMENTS §9 프라이버시: 외부 네트워크 호출 절대 금지.
docs/E2E_SCENARIOS §5-6: test_static_guard.py PASS.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.helpers.static_guard import scan_directory

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]

_SRC_ROOT = Path(__file__).parent.parent.parent / "src"


@pytest.mark.timeout(15)
def test_static_guard_no_external_urls() -> None:
    """src/ 전체에서 외부 URL 리터럴이 0건임을 검증.

    허용:
    - http://127.0.0.1, http://localhost
    - f-string 변수 ({base_url} 등)
    - 사설 IP 대역 (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    - 주석 라인

    FAIL 조건: 위 허용 목록 외 https?:// 로 시작하는 URL 리터럴 발견.
    """
    assert _SRC_ROOT.exists(), f"src/ 디렉토리가 없음: {_SRC_ROOT}"

    violations = scan_directory(_SRC_ROOT)

    if violations:
        lines = [
            f"  {v.file_path}:{v.line_number}: {v.line_content.strip()!r}  [{v.reason}]"
            for v in violations
        ]
        violation_report = "\n".join(lines)
        pytest.fail(
            f"src/ 내 외부 URL {len(violations)}건 발견:\n{violation_report}\n\n"
            "REQUIREMENTS §9 프라이버시: 외부 네트워크 호출 절대 금지."
        )
