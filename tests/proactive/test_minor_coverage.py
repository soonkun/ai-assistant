# tests/proactive/test_minor_coverage.py
"""M_11 MINOR 커버리지 보강 — dispatcher.py L200-L203 / L385-L392 분기.

대상 분기 (specs/M_11_ProactiveDispatcher_SPEC.md 기반, MODULES.md L383~L385):
  1. stop() 중 idle_monitor.on_event(None)이 예외를 던져도 삼키는 분기 (L200-L203).
  2. _minutes_until(start)의 tz-naive 입력 분기 (L385-L392).

소스 변경 금지. 테스트만 추가한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from proactive.dispatcher import ProactiveDispatcher

from .fakes import FakeCalendar, FakeClock, FakeIdleMonitor, FakeScheduler


# ──────────────────────────────────────────────────────────────────────
# 로컬 fake — on_event가 예외를 던지는 변종
# ──────────────────────────────────────────────────────────────────────


class BrokenOnEventIdleMonitor(FakeIdleMonitor):  # type: ignore[misc]
    """on_event(callback)가 호출될 때마다 RuntimeError를 던지는 fake.

    stop() 경로에서 on_event(None) 호출 시의 예외 삼킴 분기를 테스트하기 위함.
    """

    def __init__(self, *, raise_on: object = None) -> None:
        super().__init__()
        # raise_on=None이면 '인자가 None일 때만' 예외. 센티넬로 '항상' 구분.
        self._raise_on = raise_on
        self._always = raise_on is _ALWAYS
        self.on_event_call_count: int = 0

    def on_event(self, callback: Any) -> None:
        self.on_event_call_count += 1
        if self._always or callback is self._raise_on:
            raise RuntimeError("boom: on_event failed")
        # 그 외에는 정상 동작으로 위임
        super().on_event(callback)


class _AlwaysSentinel:
    pass


_ALWAYS = _AlwaysSentinel()


def _make_dispatcher(
    idle_monitor: FakeIdleMonitor,
    *,
    send_text: AsyncMock | None = None,
    clock: FakeClock | None = None,
    scheduler: FakeScheduler | None = None,
    calendar: FakeCalendar | None = None,
) -> ProactiveDispatcher:
    return ProactiveDispatcher(
        calendar=calendar or FakeCalendar(),
        idle_monitor=idle_monitor,
        send_text=send_text or AsyncMock(),
        cooldown_min=30,
        dnd_enabled=False,
        clock=clock or FakeClock(),
        scheduler=scheduler or FakeScheduler(),
    )


# ──────────────────────────────────────────────────────────────────────
# L200-L203: stop() 내 idle_monitor.on_event(None) 예외 삼킴
# ──────────────────────────────────────────────────────────────────────


class TestStopIdleMonitorExceptionSwallowed:
    """dispatcher.py L200-L203: stop() 중 on_event(None)이 예외를 던져도 삼켜야 한다."""

    @pytest.mark.asyncio
    async def test_stop_swallows_on_event_none_exception(self) -> None:
        """on_event(None)이 RuntimeError를 던져도 stop()은 예외 없이 종료되고 _started=False."""
        idle = BrokenOnEventIdleMonitor(raise_on=None)
        # start()에서 self._on_idle_event(콜백)를 전달하는 on_event 호출은 예외 없어야 함.
        # 예외는 stop() 경로의 on_event(None)에서만 터지도록 raise_on=None.
        dispatcher = _make_dispatcher(idle)

        await dispatcher.start()
        assert idle.on_event_call_count == 1  # start에서 1회

        # stop()은 on_event(None) 예외를 삼키고 정상 복귀해야 함.
        await dispatcher.stop()

        assert idle.on_event_call_count == 2  # stop에서 1회 더 (예외 발생)
        # 내부 상태: _started는 False로 전이.
        assert dispatcher._started is False

    @pytest.mark.asyncio
    async def test_stop_idempotent_after_exception(self) -> None:
        """예외를 삼킨 뒤 stop()을 재호출해도 no-op이어야 한다 (멱등)."""
        idle = BrokenOnEventIdleMonitor(raise_on=None)
        dispatcher = _make_dispatcher(idle)

        await dispatcher.start()
        await dispatcher.stop()  # 1차: 예외 삼킴
        await dispatcher.stop()  # 2차: _started=False로 조기 반환

        # 2차 호출은 early return이므로 on_event 호출 횟수가 증가하지 않는다.
        assert idle.on_event_call_count == 2
        assert dispatcher._started is False


# ──────────────────────────────────────────────────────────────────────
# L385-L392: _minutes_until(start)의 tz-naive 분기
# ──────────────────────────────────────────────────────────────────────


class TestMinutesUntilTzNaive:
    """dispatcher.py L385-L392: start.tzinfo is None → UTC 가정 후 차이 계산."""

    def test_tz_naive_treated_as_utc(self) -> None:
        """tz-naive datetime은 UTC로 간주되어 차이가 음수 없이 계산된다."""
        idle = FakeIdleMonitor()
        dispatcher = _make_dispatcher(idle)

        # 30분 후 (UTC 기준) tz-naive
        now_utc = datetime.now(timezone.utc)
        future_naive = (now_utc + timedelta(minutes=30)).replace(tzinfo=None)

        minutes = dispatcher._minutes_until(future_naive)

        # 계산 중 now-호출 시차를 감안해 29~30 범위 허용
        assert 28 <= minutes <= 30

    def test_tz_naive_past_returns_zero(self) -> None:
        """과거 시각(tz-naive)은 max(0, ...)에 의해 0을 반환한다."""
        idle = FakeIdleMonitor()
        dispatcher = _make_dispatcher(idle)

        past_naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)

        minutes = dispatcher._minutes_until(past_naive)

        assert minutes == 0

    def test_tz_aware_and_naive_same_utc_moment_agree(self) -> None:
        """tz-aware(KST)와 동일한 UTC 시점의 tz-naive가 같은 분 수를 반환한다 (±1분)."""
        idle = FakeIdleMonitor()
        dispatcher = _make_dispatcher(idle)

        # 20분 후 — aware(KST)와 동일 절대 시각의 naive(UTC 가정) 페어를 만든다.
        now_utc = datetime.now(timezone.utc)
        target_utc = now_utc + timedelta(minutes=20)

        target_aware_kst = target_utc.astimezone(ZoneInfo("Asia/Seoul"))
        target_naive_as_utc = target_utc.replace(tzinfo=None)

        minutes_aware = dispatcher._minutes_until(target_aware_kst)
        minutes_naive = dispatcher._minutes_until(target_naive_as_utc)

        # 호출 간 now() 시차로 1분 차이는 허용.
        assert abs(minutes_aware - minutes_naive) <= 1

    def test_tz_naive_zero_delta_returns_zero(self) -> None:
        """현재 시각과 같은 tz-naive 입력은 0분을 반환한다."""
        idle = FakeIdleMonitor()
        dispatcher = _make_dispatcher(idle)

        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        minutes = dispatcher._minutes_until(now_naive)

        assert minutes == 0
