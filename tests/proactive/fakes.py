# tests/proactive/fakes.py
"""ProactiveDispatcher 테스트용 Fake 클래스들."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

# FakeScheduler — APScheduler를 실제로 기동하지 않고 잡 등록을 기록한다.


class FakeScheduler:
    """APScheduler BaseScheduler 최소 Mock.

    - add_job으로 받은 함수를 `trigger_job(name)`으로 직접 호출 가능.
    - start / shutdown 호출 횟수를 기록.
    """

    def __init__(self, *, start_side_effect: Exception | None = None) -> None:
        self._jobs: dict[str, Any] = {}  # id -> func
        self.start_call_count: int = 0
        self.shutdown_call_count: int = 0
        self.add_job_call_count: int = 0
        self._start_side_effect = start_side_effect
        self.running: bool = False

    def add_job(
        self,
        func: Any,
        trigger: Any = None,
        id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """잡을 등록하고 func를 저장한다."""
        job_id = id or f"job_{len(self._jobs)}"
        self._jobs[job_id] = func
        self.add_job_call_count += 1
        return None

    def start(self) -> None:
        """스케줄러 시작. start_side_effect가 설정되면 예외를 발생시킨다."""
        self.start_call_count += 1
        if self._start_side_effect is not None:
            raise self._start_side_effect
        self.running = True

    def shutdown(self, wait: bool = True) -> None:
        """스케줄러 종료."""
        self.shutdown_call_count += 1
        self.running = False

    async def trigger_job(self, job_id: str) -> None:
        """등록된 잡 함수를 직접 호출한다 (테스트용 트리거 시뮬레이션)."""
        func = self._jobs.get(job_id)
        if func is None:
            raise KeyError(f"Job not found: {job_id!r}")
        import inspect

        if inspect.iscoroutinefunction(func):
            await func()
        else:
            func()


class FakeCalendar:
    """CalendarService 최소 Mock.

    events_due_within / get_events / get_event 메서드만 구현.
    """

    def __init__(
        self,
        due_events: list[Any] | None = None,
        all_events: list[Any] | None = None,
    ) -> None:
        self._due_events: list[Any] = due_events or []
        self._all_events: list[Any] = all_events or []
        self.events_due_within_call_count: int = 0
        self.get_events_call_count: int = 0

    def events_due_within(self, minutes: int) -> list[Any]:
        self.events_due_within_call_count += 1
        return list(self._due_events)

    def get_events(self, start: datetime, end: datetime) -> list[Any]:
        self.get_events_call_count += 1
        return list(self._all_events)

    def get_event(self, event_id: int) -> Any | None:
        for ev in self._all_events + self._due_events:
            if ev.id == event_id:
                return ev
        return None


class FakeIdleMonitor:
    """IdleMonitor 최소 Mock.

    on_event(cb) / set_dnd(bool) 만 구현.
    """

    def __init__(self) -> None:
        self._callback: Callable[[str], Awaitable[None]] | None = None
        self.set_dnd_call_count: int = 0
        self.last_dnd_value: bool | None = None

    def on_event(self, callback: Any) -> None:
        self._callback = callback

    def set_dnd(self, enabled: bool) -> None:
        self.set_dnd_call_count += 1
        self.last_dnd_value = enabled

    async def trigger_idle_event(self, topic: str) -> None:
        """콜백을 직접 호출한다 (테스트용)."""
        if self._callback is not None:
            await self._callback(topic)


class FakeClock:
    """테스트용 시계.

    _t 기준으로 advance(delta)로 시각을 전진시킬 수 있다.
    """

    def __init__(self, initial: datetime | None = None) -> None:
        self._t: datetime = initial or datetime(2026, 4, 19, 9, 0, 0)

    def __call__(self) -> datetime:
        return self._t

    def advance(self, delta: timedelta) -> None:
        """시각을 delta만큼 전진시킨다."""
        self._t += delta

    def set(self, dt: datetime) -> None:
        """시각을 직접 설정한다."""
        self._t = dt


class FakeEvent:
    """CalendarService.Event 최소 Mock."""

    def __init__(
        self,
        id: int,
        title: str = "테스트 일정",
        start: datetime | None = None,
        duration_minutes: int = 60,
    ) -> None:
        self.id = id
        self.title = title
        self.start: datetime = start or datetime(2026, 4, 19, 15, 0, 0, tzinfo=timezone.utc)
        self.duration_minutes = duration_minutes
        self.description: str | None = None
        self.created_at: datetime = self.start


async def fake_send_text_noop(payload: dict[str, Any]) -> None:
    """아무것도 하지 않는 send_text 콜러블."""
    pass
