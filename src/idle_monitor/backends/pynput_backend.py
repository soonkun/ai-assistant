# src/idle_monitor/backends/pynput_backend.py
"""PynputBackend — pynput 기반 전역 키보드·마우스 훅 (Windows Primary)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from loguru import logger

from idle_monitor.backends.base import _IdleBackend
from idle_monitor.errors import BackendInitError


class PynputBackend(_IdleBackend):
    """pynput.keyboard.Listener + pynput.mouse.Listener 기반 전역 입력 훅.

    훅 핸들러는 단일 필드 쓰기만 수행: self._last_input = clock().
    키·마우스 내용은 기록하지 않음 (프라이버시 원칙).
    """

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self._clock = clock
        self._last_input: datetime = clock()
        self._kb_listener: Any = None
        self._ms_listener: Any = None

    def _on_event(self, *_args: Any, **_kwargs: Any) -> None:
        """키보드/마우스 이벤트 공통 핸들러. 내용 미기록."""
        self._last_input = self._clock()

    def start(self) -> None:
        """두 Listener 초기화. 실패 시 BackendInitError."""
        try:
            from pynput import keyboard as kb
            from pynput import mouse as ms
        except ImportError as exc:
            raise BackendInitError(f"pynput import 실패: {exc}") from exc

        try:
            self._kb_listener = kb.Listener(on_press=self._on_event)
            self._kb_listener.start()
            if not self._kb_listener.is_alive():
                raise BackendInitError("keyboard Listener가 시작 직후 종료됨 (EDR 차단 가능성)")

            self._ms_listener = ms.Listener(
                on_move=self._on_event,
                on_click=self._on_event,
                on_scroll=self._on_event,
            )
            self._ms_listener.start()
            if not self._ms_listener.is_alive():
                # kb_listener는 이미 시작됐으므로 정리
                self._kb_listener.stop()
                raise BackendInitError("mouse Listener가 시작 직후 종료됨 (EDR 차단 가능성)")
        except BackendInitError:
            raise
        except Exception as exc:
            raise BackendInitError(f"pynput Listener 초기화 실패: {exc}") from exc

        logger.debug("PynputBackend: keyboard/mouse listeners started")

    def stop(self) -> None:
        """두 Listener 정지. 멱등."""
        for listener in (self._kb_listener, self._ms_listener):
            if listener is not None:
                try:
                    listener.stop()
                    listener.join(timeout=1.0)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pynput listener stop 오류 (무시): %s", exc)
        self._kb_listener = None
        self._ms_listener = None
        logger.debug("PynputBackend: listeners stopped")

    def last_input_at(self, now: datetime) -> datetime:  # noqa: ARG002
        return self._last_input
