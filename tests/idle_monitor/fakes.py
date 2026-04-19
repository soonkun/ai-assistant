# tests/idle_monitor/fakes.py
"""FakeBackend 공개 모듈 (스펙 §5.5)."""

from __future__ import annotations

# conftest에서 정의된 클래스를 re-export해 테스트 간 공유
from tests.idle_monitor.conftest import FakeBackend, FakeClock

__all__ = ["FakeBackend", "FakeClock"]
