# src/idle_monitor/backends/noop_backend.py
"""NoopBackend — 비Windows 또는 양쪽 백엔드 실패 시 사용."""

from __future__ import annotations

import sys
from datetime import datetime

from loguru import logger

from idle_monitor.backends.base import _IdleBackend


class NoopBackend(_IdleBackend):
    """비Windows 환경 또는 모든 백엔드 실패 시 사용하는 no-op 구현.

    - start(): logger.warning 1회 + no-op.
    - stop(): no-op.
    - last_input_at(now): 항상 now 반환 → elapsed=0 → 상태 전이 절대 감지 안 됨.
    """

    _warned: bool = False

    def start(self) -> None:
        if not self._warned:
            logger.warning(
                "IdleMonitor disabled on non-Windows platform: %s",
                sys.platform,
            )
            self._warned = True

    def stop(self) -> None:
        pass

    def last_input_at(self, now: datetime) -> datetime:
        return now
