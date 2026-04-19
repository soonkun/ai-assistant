# tests/e2e/fakes/fake_scheduler.py
"""FakeScheduler — APScheduler 대체 Mock.

tests/proactive/fakes.py의 FakeScheduler를 E2E 전용으로 재export.
이미 검증된 구현을 재사용해 코드 중복 최소화.
"""

from __future__ import annotations

# proactive fakes 재사용 (이미 Critic PASS된 구현)
from tests.proactive.fakes import (  # noqa: F401
    FakeCalendar,
    FakeClock,
    FakeEvent,
    FakeIdleMonitor,
    FakeScheduler,
    fake_send_text_noop,
)
