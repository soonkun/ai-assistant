# tests/e2e/test_e2e_32_network_offline_guard.py
"""E2E-32: 외부 네트워크 호출 시도 → 테스트 실패(네트워크 차단 fixture).

시나리오 ID: E2E-32-network-offline-guard
REQUIREMENTS: §9 프라이버시 — 외부 호출 절대 금지
관련 모듈: 전체 (offline_guard autouse fixture)
마커: e2e_fast
실행 시간 목표: ≤ 3초
"""

from __future__ import annotations

import socket

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_fast]


@pytest.mark.timeout(10)
def test_e2e_32_network_offline_guard(offline_guard: None) -> None:
    """외부 호스트(8.8.8.8) 연결 시도 시 offline policy violation 발생 확인.

    수락 기준:
    - RuntimeError("offline policy violation: 8.8.8.8:443") 발생.
    - 테스트 자체는 PASS (에러 발생이 기대 결과).
    - 허용 호스트(127.0.0.1)에 대한 getaddrinfo는 정상 수행.
    """
    # 1. 외부 호스트(8.8.8.8) → RuntimeError 발생해야 한다.
    with pytest.raises(RuntimeError, match="offline policy violation"):
        socket.getaddrinfo("8.8.8.8", 443)

    # 2. 외부 도메인(example.com) → RuntimeError 발생해야 한다.
    with pytest.raises(RuntimeError, match="offline policy violation"):
        socket.getaddrinfo("example.com", 80)

    # 3. 허용 호스트(127.0.0.1) → 정상 수행 (예외 없음)
    result = socket.getaddrinfo("127.0.0.1", 80)
    assert result, "127.0.0.1 getaddrinfo가 빈 결과 반환"

    # 4. 허용 호스트(localhost) → 정상 수행
    result_local = socket.getaddrinfo("localhost", 80)
    assert result_local, "localhost getaddrinfo가 빈 결과 반환"
