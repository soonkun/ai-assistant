# tests/idle_monitor/test_callbacks.py
"""콜백 관련 테스트 — on_event 덮어쓰기, 예외 처리, create_task."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from idle_monitor import IdleMonitor
from tests.idle_monitor.conftest import FakeBackend, FakeClock, wire_monitor


class TestCallbacks:
    """콜백 등록·덮어쓰기·예외 처리 테스트."""

    @pytest.mark.asyncio
    async def test_callback_called_with_idle_rest_literal(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """콜백 페이로드는 정확히 'idle_rest' Literal 문자열 (D-6)."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)

        args, _ = cb.call_args
        assert args[0] == "idle_rest"
        assert isinstance(args[0], str)

    @pytest.mark.asyncio
    async def test_callback_called_with_overwork_literal(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """콜백 페이로드는 정확히 'overwork' Literal 문자열 (D-6)."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(
                overwork_threshold_min=2,
                active_gap_seconds=60,
                clock=clock,
            ),
            fake_backend,
        )
        monitor.on_event(cb)

        for i in range(0, 130, 10):
            tick_t = t0 + timedelta(seconds=i)
            fake_backend.simulate_input(tick_t)
            monitor._tick(tick_t)
        await asyncio.sleep(0)

        cb.assert_called_with("overwork")
        args, _ = cb.call_args
        assert args[0] == "overwork"
        assert isinstance(args[0], str)

    @pytest.mark.asyncio
    async def test_on_event_none_removes_callback(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """on_event(None)으로 콜백 해제 후 전이 발생해도 호출 없음."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)
        monitor.on_event(None)  # 해제

        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)

        cb.assert_not_called()

    @pytest.mark.asyncio
    async def test_dnd_false_after_true_allows_next_transition(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """DND True → False 후 다음 전이에서 콜백 방출."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(
                idle_threshold_min=1,
                active_gap_seconds=10,
                clock=clock,
            ),
            fake_backend,
        )
        monitor.on_event(cb)
        monitor.set_dnd(True)

        # DND 중 idle 전이 → 콜백 없음, state=idle
        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)
        cb.assert_not_called()
        assert monitor._state == "idle"

        # DND 해제
        monitor.set_dnd(False)

        # idle→active 복귀 (입력 발생, elapsed < active_gap_seconds=10)
        t_resume = t0 + timedelta(seconds=70)
        fake_backend.simulate_input(t_resume)
        monitor._tick(t_resume + timedelta(seconds=1))
        assert monitor._state == "active"

        # 다시 idle 전이 → 콜백 방출
        monitor._tick(t_resume + timedelta(seconds=62))
        await asyncio.sleep(0)
        cb.assert_called_once_with("idle_rest")
