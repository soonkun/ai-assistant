# src/idle_monitor/errors.py
"""IdleMonitor 예외 계층."""

from __future__ import annotations


class IdleMonitorError(Exception):
    """IdleMonitor 최상위 기본 예외."""


class BackendInitError(IdleMonitorError, RuntimeError):
    """백엔드 초기화 실패(훅 차단·DLL 부재 등).

    backends/base.py에서 re-export. 상위는 폴백 시도 후 최종 실패면 no-op.
    """
