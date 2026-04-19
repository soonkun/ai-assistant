# tests/idle_monitor/test_state_machine.py
"""상태 기계 전이 단위 테스트 — _tick 직접 호출 기반."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from idle_monitor import IdleMonitor
from tests.idle_monitor.conftest import FakeBackend, FakeClock, wire_monitor


class TestStateMachine:
    """_tick 기반 상태 전이 + 불변식 검증."""

    @pytest.mark.asyncio
    async def test_idle_rest_fires_once_not_twice(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """D-7: idle 상태 유지 중 반복 _tick → idle_rest 1회만 방출."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        # 첫 번째 _tick: 전이 발생 → idle_rest 1회
        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)
        assert cb.call_count == 1

        # 두 번째~세 번째 _tick: idle 유지 중 → 추가 방출 없음
        monitor._tick(t0 + timedelta(seconds=120))
        monitor._tick(t0 + timedelta(seconds=180))
        await asyncio.sleep(0)
        assert cb.call_count == 1

    @pytest.mark.asyncio
    async def test_overwork_fires_once_per_active_session(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """D-7: active 세션당 overwork 1회. active→idle→active 후 재방출 가능."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(
                idle_threshold_min=60,
                overwork_threshold_min=2,
                active_gap_seconds=60,
                clock=clock,
            ),
            fake_backend,
        )
        # _active_since를 t0으로 맞춤 (clock=FakeClock(t0)이므로 __init__에서 t0 할당됨)
        monitor.on_event(cb)

        # 121초 동안 입력 유지 → overwork 1회
        for i in range(0, 130, 10):
            tick_t = t0 + timedelta(seconds=i)
            fake_backend.simulate_input(tick_t)
            monitor._tick(tick_t)
        await asyncio.sleep(0)
        overwork_count_before = sum(1 for c in cb.call_args_list if c[0][0] == "overwork")
        assert overwork_count_before == 1

        # 계속 입력해도 overwork 추가 방출 없음
        for i in range(130, 200, 10):
            tick_t = t0 + timedelta(seconds=i)
            fake_backend.simulate_input(tick_t)
            monitor._tick(tick_t)
        await asyncio.sleep(0)
        overwork_count_after = sum(1 for c in cb.call_args_list if c[0][0] == "overwork")
        assert overwork_count_after == 1

        # active→idle 전이 (입력 없이 60분 이상)
        idle_time = t0 + timedelta(hours=2)
        monitor._tick(idle_time)
        await asyncio.sleep(0)
        assert monitor._state == "idle"

        # idle→active 복귀 (elapsed < active_gap_seconds=60)
        resume_t = idle_time + timedelta(seconds=1)
        fake_backend.simulate_input(resume_t)
        monitor._tick(resume_t + timedelta(seconds=1))
        assert monitor._state == "active"
        assert monitor._overwork_emitted is False

        # _active_since를 resume_t+1s로 리셋됐음 (idle→active 전이 시 now=resume_t+1s)
        # active_since 기준 2분(=120s) 이상 경과해야 overwork 발생
        # resume_t + 1s + 130s = resume_t + 131s 까지 입력 유지
        for i in range(0, 140, 10):
            tick_t = resume_t + timedelta(seconds=i)
            fake_backend.simulate_input(tick_t)
            monitor._tick(tick_t)
        await asyncio.sleep(0)
        overwork_count_final = sum(1 for c in cb.call_args_list if c[0][0] == "overwork")
        assert overwork_count_final == 2

    @pytest.mark.asyncio
    async def test_e1_boundary_threshold_minus_1_no_emit(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """E-1: elapsed=45*60 - 1s → idle_rest 미방출."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=45, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        monitor._tick(t0 + timedelta(seconds=45 * 60 - 1))
        await asyncio.sleep(0)

        cb.assert_not_called()
        assert monitor._state == "active"

    @pytest.mark.asyncio
    async def test_e1_boundary_threshold_exact_emit(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """E-1: elapsed=45*60 → idle_rest 방출 (inclusive)."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=45, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        monitor._tick(t0 + timedelta(seconds=45 * 60))
        await asyncio.sleep(0)

        cb.assert_called_once_with("idle_rest")

    @pytest.mark.asyncio
    async def test_e1_boundary_threshold_plus_1_no_duplicate(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """E-1: elapsed=45*60+1s → idle_rest 1회만 (중복 없음, D-7)."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=45, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        monitor._tick(t0 + timedelta(seconds=45 * 60))
        monitor._tick(t0 + timedelta(seconds=45 * 60 + 1))
        await asyncio.sleep(0)

        assert cb.call_count == 1  # 중복 없음

    @pytest.mark.asyncio
    async def test_e2_callback_none_no_crash(self, t0: datetime, fake_backend: FakeBackend) -> None:
        """E-2: 콜백 None에서 이벤트 발생 → 크래시 없음."""
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        # on_event 미호출
        monitor._tick(t0 + timedelta(seconds=61))  # 예외 없음
        assert monitor._state == "idle"

    @pytest.mark.asyncio
    async def test_e3_callback_exception_loop_survives(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """E-3: 콜백이 예외를 던져도 루프 생존 + 후속 _tick 정상."""
        import asyncio

        cb = AsyncMock(side_effect=RuntimeError("boom"))
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        # 전이 발생 → cb 예외 → logger.warning
        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)

        # 상태는 idle로 전이됨
        assert monitor._state == "idle"

        # 입력 후 active 복귀 — 후속 _tick 정상 동작
        t_resume = t0 + timedelta(seconds=120)
        fake_backend.simulate_input(t_resume)
        monitor._tick(t_resume + timedelta(seconds=1))
        assert monitor._state == "active"

    def test_init_validates_idle_threshold(self) -> None:
        """__init__: idle_threshold_min=0 → ValueError."""
        with pytest.raises(ValueError, match="idle_threshold_min"):
            IdleMonitor(idle_threshold_min=0)

    def test_init_validates_overwork_threshold(self) -> None:
        """__init__: overwork_threshold_min=1441 → ValueError."""
        with pytest.raises(ValueError, match="overwork_threshold_min"):
            IdleMonitor(overwork_threshold_min=1441)

    def test_set_dnd_type_error(self) -> None:
        """set_dnd: bool 아닌 값 → TypeError."""
        monitor = IdleMonitor()
        with pytest.raises(TypeError, match="bool"):
            monitor.set_dnd("yes")  # type: ignore[arg-type]

    def test_on_event_type_error(self) -> None:
        """on_event: callable도 None도 아닌 값 → TypeError."""
        monitor = IdleMonitor()
        with pytest.raises(TypeError, match="callable or None"):
            monitor.on_event("not_callable")  # type: ignore[arg-type]
