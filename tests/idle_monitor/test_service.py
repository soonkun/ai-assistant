# tests/idle_monitor/test_service.py
"""정상 케이스 (N-1~N-7) + 엣지 케이스 (E-4~E-7)."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from idle_monitor import IdleMonitor
from idle_monitor.backends.noop_backend import NoopBackend
from tests.idle_monitor.conftest import FakeBackend, FakeClock, wire_monitor


# ---------------------------------------------------------------------------
# 정상 케이스
# ---------------------------------------------------------------------------


class TestNormalCases:
    """N-1 ~ N-7 정상 케이스."""

    @pytest.mark.asyncio
    async def test_n1_active_to_idle_emits_idle_rest(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """N-1: active→idle 전이 시 idle_rest 1회 방출."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        # t0+61s: 1분(60초) 임계값 초과
        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)

        cb.assert_called_once_with("idle_rest")
        assert monitor._state == "idle"

    @pytest.mark.asyncio
    async def test_n2_overwork_emitted_once_active_maintained(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """N-2: 연속 입력 2분 후 overwork 1회 방출 + active 유지."""
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

        # 10초 간격으로 121초까지 fake_input + _tick
        for i in range(0, 122, 10):
            tick_t = t0 + timedelta(seconds=i)
            fake_backend.simulate_input(tick_t)  # 입력 지속
            monitor._tick(tick_t)

        await asyncio.sleep(0)

        assert cb.call_count == 1
        cb.assert_called_with("overwork")
        assert monitor._state == "active"

    @pytest.mark.asyncio
    async def test_n3_idle_to_active_no_event(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """N-3: idle→active 복귀 시 이벤트 미방출 (조용한 복귀). _overwork_emitted 리셋."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        # active→idle 전이
        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)
        assert monitor._state == "idle"
        assert cb.call_count == 1

        # idle→active 복귀: 최근 입력 시뮬레이션 (elapsed < active_gap_seconds=60)
        t_resume = t0 + timedelta(seconds=120)
        fake_backend.simulate_input(t_resume)
        monitor._tick(t_resume + timedelta(seconds=1))
        await asyncio.sleep(0)

        assert monitor._state == "active"
        assert cb.call_count == 1  # 콜백 추가 호출 없음
        assert monitor._overwork_emitted is False

    @pytest.mark.asyncio
    async def test_n4_dnd_active_blocks_callback(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """N-4: DND 활성 시 전이 발생해도 콜백 호출 안 됨. 내부 state는 갱신됨."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)
        monitor.set_dnd(True)

        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)

        cb.assert_not_called()
        # 내부 state는 idle로 갱신됨 (D-3)
        assert monitor._state == "idle"

    @pytest.mark.asyncio
    async def test_n5_on_event_overwrite(self, t0: datetime, fake_backend: FakeBackend) -> None:
        """N-5: on_event 덮어쓰기 — 최신 콜백만 호출."""
        import asyncio

        cb_a = AsyncMock()
        cb_b = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb_a)
        monitor.on_event(cb_b)

        monitor._tick(t0 + timedelta(seconds=61))
        await asyncio.sleep(0)

        cb_a.assert_not_called()
        cb_b.assert_called_once_with("idle_rest")

    def test_n6_last_input_at_and_seconds_since(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """N-6: last_input_at() / seconds_since_last_input() 조회."""
        query_time = t0 + timedelta(seconds=30)
        clock = FakeClock(query_time)
        monitor = wire_monitor(
            IdleMonitor(clock=clock),
            fake_backend,
        )

        # fake_backend.last = t0, clock = t0+30s
        assert monitor.last_input_at() == t0
        assert abs(monitor.seconds_since_last_input() - 30.0) < 0.1

    @pytest.mark.asyncio
    async def test_n7_tick_with_clock_advance(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """N-7: clock.advance(46분) + _tick(now=None) → idle_rest 1회."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=45, clock=clock),
            fake_backend,
        )
        monitor.on_event(cb)

        # 45분+60초 경과 → idle_rest
        clock.advance(timedelta(minutes=46))
        monitor._tick()  # now=None → self._clock() 사용
        await asyncio.sleep(0)

        cb.assert_called_once_with("idle_rest")


# ---------------------------------------------------------------------------
# 엣지 케이스 (E-4 ~ E-7)
# ---------------------------------------------------------------------------


class TestEdgeCasesService:
    """E-4, E-5, E-6, E-7 엣지 케이스."""

    @pytest.mark.asyncio
    async def test_e4_stop_without_start(self, t0: datetime, fake_backend: FakeBackend) -> None:
        """E-4: start 미호출 상태에서 stop — no-op, 예외 없음."""
        monitor = IdleMonitor(backend=fake_backend)
        await monitor.stop()  # 예외 없음
        assert monitor._task is None

    @pytest.mark.asyncio
    async def test_e5_stop_idempotent(self, t0: datetime, fake_backend: FakeBackend) -> None:
        """E-5: stop 중복 호출 — no-op. backend.stop() 1회만."""
        # wire_monitor로 start 우회 (poll_loop task 미생성)
        monitor = wire_monitor(IdleMonitor(backend=fake_backend), fake_backend)
        await monitor.stop()
        await monitor.stop()

        # backend.stop()이 1회만
        assert fake_backend.stop_called == 1

    def test_e6_clock_skew_seconds_since_clamped(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """E-6: 클록 역행 → seconds_since_last_input() == 0.0."""
        # last_input_at = t0+10s, now = t0 (역행)
        future_last = t0 + timedelta(seconds=10)
        fake_backend.simulate_input(future_last)
        clock = FakeClock(t0)
        monitor = wire_monitor(IdleMonitor(clock=clock), fake_backend)

        assert monitor.seconds_since_last_input() == 0.0

    def test_e6_tick_with_clock_skew_no_transition(
        self, t0: datetime, fake_backend: FakeBackend
    ) -> None:
        """E-6 연속: clock 역행 시 _tick → elapsed=0 → 전이 없음."""
        future_last = t0 + timedelta(seconds=10)
        fake_backend.simulate_input(future_last)
        clock = FakeClock(t0)
        cb = MagicMock()
        monitor = wire_monitor(IdleMonitor(idle_threshold_min=1, clock=clock), fake_backend)
        monitor.on_event(cb)  # type: ignore[arg-type]

        monitor._tick(t0)  # now=t0, last=t0+10s → elapsed 음수 → 0으로 클램프
        cb.assert_not_called()
        assert monitor._state == "active"

    @pytest.mark.asyncio
    async def test_e7_noop_backend_tick_no_crash(self, t0: datetime) -> None:
        """E-7: NoopBackend → _tick 호출해도 크래시 없음, 콜백 없음."""
        import asyncio

        cb = AsyncMock()
        clock = FakeClock(t0)
        monitor = wire_monitor(
            IdleMonitor(idle_threshold_min=1, clock=clock),
            NoopBackend(),
        )
        monitor.on_event(cb)

        # clock 진행
        clock.advance(timedelta(hours=1))
        monitor._tick()
        await asyncio.sleep(0)

        cb.assert_not_called()  # NoopBackend.last_input_at == now → elapsed=0
