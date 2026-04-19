# tests/proactive/conftest.py
"""pytest fixture — FakeScheduler, FakeCalendar, FakeIdleMonitor, FakeClock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from .fakes import FakeCalendar, FakeClock, FakeEvent, FakeIdleMonitor, FakeScheduler


@pytest.fixture
def fake_scheduler() -> FakeScheduler:
    return FakeScheduler()


@pytest.fixture
def fake_calendar() -> FakeCalendar:
    return FakeCalendar()


@pytest.fixture
def fake_idle_monitor() -> FakeIdleMonitor:
    return FakeIdleMonitor()


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(initial=datetime(2026, 4, 19, 9, 0, 0))


@pytest.fixture
def fake_send_text() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def sample_event() -> FakeEvent:
    """10분 후 시작하는 샘플 이벤트."""
    now_utc = datetime.now(timezone.utc)
    return FakeEvent(
        id=1,
        title="팀 회의",
        start=now_utc + timedelta(minutes=10),
        duration_minutes=60,
    )
