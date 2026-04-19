# tests/idle_monitor/conftest.py
"""공용 fixture: FakeClock, FakeBackend, 헬퍼."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from idle_monitor.backends.base import BackendInitError, _IdleBackend
from idle_monitor.service import IdleMonitor


# ---------------------------------------------------------------------------
# FakeClock
# ---------------------------------------------------------------------------


class FakeClock:
    """테스트용 가변 클록."""

    def __init__(self, t0: datetime) -> None:
        self._t = t0

    def __call__(self) -> datetime:
        return self._t

    def advance(self, delta: timedelta) -> None:
        self._t += delta

    def set(self, t: datetime) -> None:
        self._t = t


# ---------------------------------------------------------------------------
# FakeBackend
# ---------------------------------------------------------------------------


class FakeBackend(_IdleBackend):
    """테스트용 Fake 백엔드.

    last_input_at()가 self.last를 반환.
    simulate_input()으로 마지막 입력 시각을 조작.
    init_error가 설정되어 있으면 start() 시 BackendInitError 발생.
    """

    def __init__(self, last: datetime) -> None:
        self.last = last
        self.start_called = 0
        self.stop_called = 0
        self.init_error: BackendInitError | None = None

    def start(self) -> None:
        self.start_called += 1
        if self.init_error is not None:
            raise self.init_error

    def stop(self) -> None:
        self.stop_called += 1

    def last_input_at(self, now: datetime) -> datetime:  # noqa: ARG002
        return self.last

    def simulate_input(self, at: datetime) -> None:
        """마지막 입력 시각 조작 (테스트 전용)."""
        self.last = at


# ---------------------------------------------------------------------------
# 헬퍼 — start() 없이 백엔드를 직접 주입
# ---------------------------------------------------------------------------


def wire_monitor(monitor: IdleMonitor, backend: _IdleBackend) -> IdleMonitor:
    """테스트 전용: start() 없이 _backend와 _started를 직접 설정.

    _poll_loop Task가 생성되지 않으므로 `datetime.now` 클록에 의한
    테스트 오염이 발생하지 않는다.
    """
    monitor._backend = backend  # type: ignore[attr-defined]
    monitor._started = True  # type: ignore[attr-defined]
    return monitor


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def t0() -> datetime:
    """기준 시각 — 2026-01-01 10:00:00."""
    return datetime(2026, 1, 1, 10, 0, 0)


@pytest.fixture
def fake_clock(t0: datetime) -> FakeClock:
    return FakeClock(t0)


@pytest.fixture
def fake_backend(t0: datetime) -> FakeBackend:
    return FakeBackend(last=t0)
