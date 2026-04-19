# tests/idle_monitor/test_adversarial.py
"""적대적 케이스 (A-1~A-4)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from idle_monitor import IdleMonitor
from idle_monitor.backends.base import BackendInitError
from idle_monitor.backends.noop_backend import NoopBackend
from tests.idle_monitor.conftest import FakeBackend, FakeClock, wire_monitor


class TestAdversarialCases:
    """A-1 ~ A-4 적대적 케이스."""

    @pytest.mark.asyncio
    async def test_a1_pynput_init_error_falls_back_to_win32(self, t0: datetime) -> None:
        """A-1: PynputBackend.start() BackendInitError → Win32 자동 폴백 (R-10 회귀 방지).

        sys.platform을 'win32'로 patch해 비-Windows 환경에서도 실제 폴백 체인을 실행.
        PynputBackend.start()에 BackendInitError를, Win32IdleBackend.start()는 no-op으로 설정.
        _select_backend()가 실제로 pynput → Win32 경로를 거치는지 검증.
        """
        from idle_monitor.backends.win32_backend import Win32IdleBackend

        clock = FakeClock(t0)
        warning_messages: list[str] = []

        from loguru import logger

        def _sink(message: object) -> None:
            warning_messages.append(str(message))

        handler_id = logger.add(_sink, level="WARNING")
        try:
            with (
                patch("idle_monitor.backends.sys") as mock_sys,
                patch(
                    "idle_monitor.backends.pynput_backend.PynputBackend.start",
                    side_effect=BackendInitError("EDR blocked"),
                ),
                patch(
                    "idle_monitor.backends.win32_backend.Win32IdleBackend.start",
                    return_value=None,
                ),
            ):
                mock_sys.platform = "win32"
                monitor = IdleMonitor(clock=clock)
                monitor.start()
        finally:
            logger.remove(handler_id)

        # 결과 백엔드가 Win32IdleBackend 인스턴스여야 함
        assert isinstance(monitor._backend, Win32IdleBackend), (
            f"폴백 후 백엔드가 Win32IdleBackend여야 하지만 {type(monitor._backend)!r}"
        )
        # logger.warning 1회: pynput 폴백 메시지
        assert any("pynput" in msg for msg in warning_messages), (
            f"pynput 폴백 warning 로그가 없음. 수집된 메시지: {warning_messages}"
        )

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_a2_both_backends_fail_noop_degraded(self, t0: datetime) -> None:
        """A-2: pynput + Win32 둘 다 BackendInitError → Noop 강등 + logger.error, 앱 기동 계속.

        sys.platform을 'win32'로 patch해 비-Windows에서도 실제 폴백 체인 전체를 실행.
        pynput, Win32 양쪽 start()에 BackendInitError를 주입 → NoopBackend로 강등됨.
        _select_backend() 내부의 logger.error 1회 + 예외 미전파를 검증.
        """
        clock = FakeClock(t0)
        error_messages: list[str] = []

        from loguru import logger

        def _sink(message: object) -> None:
            error_messages.append(str(message))

        handler_id = logger.add(_sink, level="ERROR")
        try:
            with (
                patch("idle_monitor.backends.sys") as mock_sys,
                patch(
                    "idle_monitor.backends.pynput_backend.PynputBackend.start",
                    side_effect=BackendInitError("pynput EDR blocked"),
                ),
                patch(
                    "idle_monitor.backends.win32_backend.Win32IdleBackend.start",
                    side_effect=BackendInitError("Win32 DLL 없음"),
                ),
            ):
                mock_sys.platform = "win32"
                # 예외 밖으로 나오지 않아야 함
                monitor = IdleMonitor(clock=clock)
                monitor.start()  # start()는 예외 없이 성공해야 함
        finally:
            logger.remove(handler_id)

        # 결과 백엔드가 NoopBackend로 강등됐어야 함
        assert isinstance(monitor._backend, NoopBackend), (
            f"양쪽 실패 후 NoopBackend여야 하지만 {type(monitor._backend)!r}"
        )
        # logger.error 1회: Win32까지 실패 시 error 레벨 로그
        assert any("pynput" in msg or "Win32" in msg or "both" in msg for msg in error_messages), (
            f"Win32 폴백 실패 error 로그가 없음. 수집된 메시지: {error_messages}"
        )

        # _tick 호출도 크래시 없음
        clock.advance(timedelta(hours=1))
        monitor._tick()
        await asyncio.sleep(0)

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_a3_24h_simulation_no_overflow(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """A-3: 24시간 대기 시뮬레이션 — overflow 없음, idle_rest 1회."""
        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=45, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        # 24시간 경과
        t_24h = t0 + timedelta(hours=24)
        monitor._tick(t_24h)
        await asyncio.sleep(0)

        cb.assert_called_once_with("idle_rest")
        # overwork는 idle 상태이므로 미발동
        assert monitor._state == "idle"
        # timedelta 연산 정상 (ValueError 없음)

    def test_a4_tick_bombardment_no_transitions(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """A-4: _tick 1000회 폭격 — 전이 없음, 50ms 이내."""
        cb = MagicMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=45, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)  # type: ignore[arg-type]

        start_ns = time.perf_counter_ns()
        for _ in range(1000):
            monitor._tick(t0)  # 고정 시각 → elapsed=0 → 전이 없음
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

        cb.assert_not_called()
        assert elapsed_ms < 50, f"1000회 _tick이 {elapsed_ms:.1f}ms 소요 (50ms 초과)"
