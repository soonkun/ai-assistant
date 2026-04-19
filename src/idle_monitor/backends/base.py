# src/idle_monitor/backends/base.py
"""_IdleBackend ABC 정의."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from idle_monitor.errors import BackendInitError

__all__ = ["_IdleBackend", "BackendInitError"]


class _IdleBackend(ABC):
    """IdleMonitor 내부 백엔드 인터페이스. 외부 모듈은 참조하지 않는다."""

    @abstractmethod
    def start(self) -> None:
        """훅/폴링 초기화. 실패 시 BackendInitError."""

    @abstractmethod
    def stop(self) -> None:
        """훅/폴링 정리. 멱등."""

    @abstractmethod
    def last_input_at(self, now: datetime) -> datetime:
        """마지막 입력 시각을 반환.

        - Pynput 백엔드: 내부 저장된 `self._last_input` (훅이 갱신).
        - Win32 백엔드: `GetLastInputInfo`의 tick count → `now - (현재 tick - last tick) ms` 환산.
        - Noop 백엔드: 항상 `now` 반환 (무입력 간격=0, 전이 미발생).
        """
