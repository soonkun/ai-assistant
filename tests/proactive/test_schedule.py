# tests/proactive/test_schedule.py
"""APScheduler 잡 등록·트리거 호출 테스트 (FakeScheduler 사용)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from proactive.dispatcher import ProactiveDispatcher

from .fakes import FakeCalendar, FakeClock, FakeEvent, FakeIdleMonitor, FakeScheduler


def make_dispatcher(
    send_text: AsyncMock | None = None,
    scheduler: FakeScheduler | None = None,
    calendar: FakeCalendar | None = None,
    idle_monitor: FakeIdleMonitor | None = None,
    clock: FakeClock | None = None,
    cooldown_min: int = 1,
) -> ProactiveDispatcher:
    return ProactiveDispatcher(
        calendar=calendar or FakeCalendar(),
        idle_monitor=idle_monitor or FakeIdleMonitor(),
        send_text=send_text or AsyncMock(),
        cooldown_min=cooldown_min,
        clock=clock or FakeClock(),
        scheduler=scheduler or FakeScheduler(),
    )


@pytest.mark.asyncio
async def test_jobs_registered_on_start() -> None:
    """start() 후 FakeScheduler에 morning_briefing + event_reminder 잡이 등록된다."""
    scheduler = FakeScheduler()
    dispatcher = make_dispatcher(scheduler=scheduler)
    await dispatcher.start()

    assert "morning_briefing" in scheduler._jobs
    assert "event_reminder" in scheduler._jobs
    assert scheduler.add_job_call_count == 2


@pytest.mark.asyncio
async def test_morning_briefing_job_triggers_emit() -> None:
    """_job_morning_briefing() 직접 호출 시 emit이 발생한다."""
    send_text = AsyncMock()
    events = [
        FakeEvent(
            id=1,
            title="스탠드업",
            start=datetime(2026, 4, 19, 9, 30, 0, tzinfo=timezone.utc),
        )
    ]
    calendar = FakeCalendar(all_events=events)
    dispatcher = make_dispatcher(send_text=send_text, calendar=calendar)
    await dispatcher.start()

    await dispatcher._job_morning_briefing()

    send_text.assert_called_once()
    payload = send_text.call_args[0][0]
    assert payload["topic"] == "morning_briefing"
    assert "스탠드업" in payload["text"]


@pytest.mark.asyncio
async def test_event_reminder_job_triggers_emit() -> None:
    """_job_event_reminder() 직접 호출 시 due 이벤트에 대해 emit이 발생한다."""
    send_text = AsyncMock()
    ev = FakeEvent(
        id=42,
        title="팀 회의",
        start=datetime.now(timezone.utc) + timedelta(minutes=8),
    )
    calendar = FakeCalendar(due_events=[ev], all_events=[ev])
    dispatcher = make_dispatcher(send_text=send_text, calendar=calendar, cooldown_min=1)
    await dispatcher.start()

    await dispatcher._job_event_reminder()

    send_text.assert_called_once()
    payload = send_text.call_args[0][0]
    assert payload["topic"] == "event_reminder"
    assert payload["context"]["event_id"] == 42


@pytest.mark.asyncio
async def test_scheduler_di_replaced() -> None:
    """scheduler DI: 주입된 FakeScheduler가 그대로 사용된다."""
    custom_scheduler = FakeScheduler()
    dispatcher = make_dispatcher(scheduler=custom_scheduler)
    await dispatcher.start()

    assert dispatcher._scheduler is custom_scheduler
    assert custom_scheduler.start_call_count == 1
