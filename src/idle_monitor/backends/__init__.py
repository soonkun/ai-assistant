# src/idle_monitor/backends/__init__.py
"""백엔드 패키지 공개 심볼 (내부용)."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime

from idle_monitor.backends.base import BackendInitError, _IdleBackend
from idle_monitor.backends.noop_backend import NoopBackend

__all__ = [
    "_IdleBackend",
    "BackendInitError",
    "NoopBackend",
    "_select_backend",
]


def _select_backend(clock: Callable[[], datetime]) -> _IdleBackend:  # noqa: C901
    """백엔드 자동 선택 로직.

    순서:
      1. 비-Windows → NoopBackend (즉시 반환, start() 미호출)
      2. PynputBackend 시도 → 성공 시 반환 (start() 호출됨)
      3. PynputBackend 실패 → Win32IdleBackend 시도 → 성공 시 반환
      4. 둘 다 실패 → NoopBackend + logger.error 1회

    Args:
        clock: 현재 시각 공급자 (PynputBackend에 주입).

    Returns:
        선택된 _IdleBackend 인스턴스. start() 호출이 완료된 상태로 반환.
    """
    from loguru import logger

    if sys.platform != "win32":
        # NoopBackend: start()는 IdleMonitor.start()에서 호출 — 여기서 start() 미호출
        return NoopBackend()

    # Primary: PynputBackend
    try:
        from idle_monitor.backends.pynput_backend import PynputBackend

        backend: _IdleBackend = PynputBackend(clock=clock)
        backend.start()
        return backend
    except BackendInitError as e1:
        logger.warning(
            "pynput backend failed: %s; falling back to GetLastInputInfo",
            e1,
        )

    # Fallback: Win32IdleBackend
    try:
        from idle_monitor.backends.win32_backend import Win32IdleBackend

        win_backend: _IdleBackend = Win32IdleBackend()
        win_backend.start()
        return win_backend
    except BackendInitError as e2:
        logger.error(
            "both pynput and Win32 backends failed: %s; IdleMonitor disabled",
            e2,
        )

    return NoopBackend()
