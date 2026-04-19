# src/idle_monitor/backends/win32_backend.py
"""Win32IdleBackend — GetLastInputInfo() 폴링 기반 폴백 (Windows Fallback, R-10 필수)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from idle_monitor.backends.base import _IdleBackend
from idle_monitor.errors import BackendInitError


class LASTINPUTINFO(ctypes.Structure):
    """Windows LASTINPUTINFO 구조체."""

    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint),
    ]


class Win32IdleBackend(_IdleBackend):
    """ctypes.windll.user32.GetLastInputInfo() 폴링 기반 유휴 감지.

    - start(): GetLastInputInfo / GetTickCount 심볼 resolve. 실패 시 BackendInitError.
    - stop(): no-op (폴링 기반이므로 해제할 리소스 없음).
    - last_input_at(now): tick count 차이로 마지막 입력 시각 추산.
      wrap 대응: & 0xFFFFFFFF 으로 unsigned 32bit 뺄셈 (49.7일 wrap-safe).
    """

    def __init__(self) -> None:
        self._get_last_input_info: Any = None
        self._get_tick_count: Any = None

    def start(self) -> None:
        """ctypes 심볼 resolve. 비-Windows 또는 DLL 부재 시 BackendInitError."""
        if sys.platform != "win32":
            raise BackendInitError("Win32IdleBackend는 Windows에서만 사용 가능")

        try:
            windll: Any = getattr(ctypes, "windll")
            user32 = windll.user32
            kernel32 = windll.kernel32
            self._get_last_input_info = user32.GetLastInputInfo
            self._get_tick_count = kernel32.GetTickCount
        except Exception as exc:
            raise BackendInitError(f"Win32 심볼 resolve 실패: {exc}") from exc

        # 정상 동작 확인
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not self._get_last_input_info(ctypes.byref(info)):
            raise BackendInitError("GetLastInputInfo() 초기 호출 실패")

        logger.debug("Win32IdleBackend: GetLastInputInfo ready")

    def stop(self) -> None:
        """no-op — 폴링 기반이므로 해제할 리소스 없음."""

    def last_input_at(self, now: datetime) -> datetime:
        """GetLastInputInfo tick count → datetime 환산.

        current_tick - last_tick 차이를 now에서 빼 마지막 입력 시각 추산.
        wrap 안전: & 0xFFFFFFFF.
        """
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        self._get_last_input_info(ctypes.byref(info))
        current_tick: int = self._get_tick_count()
        last_tick: int = info.dwTime
        elapsed_ms = (current_tick - last_tick) & 0xFFFFFFFF
        return now - timedelta(milliseconds=elapsed_ms)
